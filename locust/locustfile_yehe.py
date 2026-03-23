"""
Mastodon Stress Test - CS6650 Final Project
Yehe Yan - Data & Backend Layer
"""

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import random
import json
import csv
import time
import os

# ─── Config ───────────────────────────────────────────────────────────────────
# Fill these in after your Mastodon instance is up and you've created test users
# Generate tokens via: Settings > Development > New Application on your instance

ACCOUNTS = [
    {"email": "testuser1@mastodon-yehe.click", "token": "5xnsq-NYs95ooDs1xZEW5HeNx4ANOvagxJsl13I7Lj0"},
    {"email": "testuser2@mastodon-yehe.click", "token": "5UZ5kfWkysingUJT6t4BxEGl1j51GFNxQX_OcbpUU78"},
    {"email": "testuser3@mastodon-yehe.click", "token": "NNBJz2yXidbIgTV2m0frowG20Bm2Mccux2h_mGaHeNE"},
]

# ─── CSV Result Logger ─────────────────────────────────────────────────────────
RESULTS_FILE = "results/locust_results.csv"

def ensure_results_dir():
    os.makedirs("results", exist_ok=True)
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "users", "rps", "p50", "p95", "p99", "error_rate"])

ensure_results_dir()
# ─── User Behaviors ────────────────────────────────────────────────────────────

class MastodonUser(HttpUser):
    """
    Simulates a typical Mastodon user:
    - Reads home timeline (most frequent - read-heavy)
    - Reads public timeline
    - Posts statuses (write path - hits Sidekiq)
    - Fetches notifications
    """
    wait_time = between(1, 3)

    def on_start(self):
        """Pick a random test account on startup."""
        account = random.choice(ACCOUNTS)
        self.token = account["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.posted_ids = []  # track our own posts for boost/fav tasks

    # ── Read tasks (weighted heavier - realistic usage) ──────────────────────

    @task(5)
    def get_home_timeline(self):
        """Read home timeline - most common user action."""
        with self.client.get(
            "/api/v1/timelines/home",
            headers=self.headers,
            name="/api/v1/timelines/home",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Got {resp.status_code}")

    @task(3)
    def get_public_timeline(self):
        """Read public timeline - no auth needed, pure read load."""
        with self.client.get(
            "/api/v1/timelines/public",
            name="/api/v1/timelines/public",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Got {resp.status_code}")

    @task(2)
    def get_notifications(self):
        """Check notifications - read path with DB join."""
        with self.client.get(
            "/api/v1/notifications",
            headers=self.headers,
            name="/api/v1/notifications",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Got {resp.status_code}")

    # ── Write tasks (weighted lighter - triggers Sidekiq workers) ─────────────

    @task(3)
    def post_status(self):
        """
        Post a new status.
        Write path: Rails → PostgreSQL insert → Sidekiq fan-out job.
        Key metric: measures end-to-end write latency.
        """
        payload = {
            "status": f"Load test post #{random.randint(1, 999999)} at {time.time():.0f}",
            "visibility": "public"
        }
        with self.client.post(
            "/api/v1/statuses",
            json=payload,
            headers=self.headers,
            name="/api/v1/statuses [POST]",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.posted_ids.append(data.get("id"))
                resp.success()
            else:
                resp.failure(f"Got {resp.status_code}: {resp.text[:100]}")

    @task(1)
    def favourite_status(self):
        """
        Favourite a recent post.
        Triggers background notification job in Sidekiq.
        """
        with self.client.get(
            "/api/v1/timelines/public?limit=5",
            name="/api/v1/timelines/public [fav sample]",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                statuses = resp.json()
                if statuses:
                    status_id = random.choice(statuses)["id"]
                    self.client.post(
                        f"/api/v1/statuses/{status_id}/favourite",
                        headers=self.headers,
                        name="/api/v1/statuses/:id/favourite"
                    )
                resp.success()
            else:
                resp.failure(f"Got {resp.status_code}")

    @task(1)
    def search(self):
        """Search - exercises Elasticsearch / DB full-text search."""
        terms = ["test", "load", "mastodon", "hello", "post"]
        with self.client.get(
            f"/api/v2/search?q={random.choice(terms)}&limit=5",
            headers=self.headers,
            name="/api/v2/search",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Got {resp.status_code}")


class HeavyWriteUser(MastodonUser):
    """
    Write-heavy variant for bottleneck experiments.
    Use this to saturate Sidekiq and RDS write path.
    Run with: locust -f locustfile.py HeavyWriteUser
    """
    wait_time = between(0.5, 1.5)

    @task(8)
    def post_status(self):
        super().post_status()

    @task(2)
    def get_home_timeline(self):
        super().get_home_timeline()


# ─── Experiment Profiles ───────────────────────────────────────────────────────
#
# Smoke test (verify setup):
#   locust -f locustfile.py --headless -u 5 -r 1 --run-time 60s \
#   --host https://mastodon-yehe.click \
#   --csv=results/smoke_test
#
# Baseline (find normal behavior):
#   locust -f locustfile.py --headless -u 20 -r 2 --run-time 300s --host https://mastodon-yehe.click
#
# Bottleneck experiment (ramp to saturation):
#   locust -f locustfile.py --headless -u 100 -r 5 --run-time 600s --host https://mastodon-yehe.click
#
# Write-heavy (stress Sidekiq + RDS):
#   locust -f locustfile.py HeavyWriteUser --headless -u 50 -r 5 --run-time 300s --host https://mastodon-yehe.click
#
# Output CSV for graphing:
#   add --csv=results/experiment_name to any command above