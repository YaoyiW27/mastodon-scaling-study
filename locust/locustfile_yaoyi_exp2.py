"""
Mastodon Bottleneck Shifting — CS6650 Final Project
Yaoyi Wang — Experiment 2: Vertical Scaling Comparison
Instance A: a.mastodon-yaoyi.online (t3.medium, 2 vCPU, 4GB RAM)

Mirrors Yehe's locustfile_yehe.py exactly for direct comparison.
Run the same steps as Yehe's Experiment 2 on t3.medium:
  Step 0: Default config (rate limit ON)   → baseline
  Step 1: RACK_ATTACK_ENABLED=false        → lift rate limit
  Step 2: WEB_CONCURRENCY=4               → increase workers
  Step 3: WEB_CONCURRENCY=6               → overshoot test

Compare results with Yehe's t3.large to show vertical scaling impact.
"""

from locust import HttpUser, task, between
import random
import time

ACCOUNTS = [
    {"token": "NCtVhVoXDfWaDZm-aFARuo-XpePa4N91HDXAoiagFpw"},   # yaoyi
    {"token": "oDdAmSqMkGXbJh3EIuvHfdb6BfagxNVmyQARCobxI08"},   # testuser1
    {"token": "M9FkxIYox05QbdjVMUxIkNzKGPPE4eVcTixA1OSTwcY"},   # testuser2
]

class MastodonUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        account = random.choice(ACCOUNTS)
        self.token = account["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.posted_ids = []

    @task(5)
    def get_home_timeline(self):
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

    @task(3)
    def post_status(self):
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

# ─── Experiment Steps ──────────────────────────────────────────────────────────
#
# Same workload for all steps: 20 users, 2/s ramp, 180s
# Change only the server-side config between steps.
#
# Step 0 — Default config (rate limit ON):
#   locust -f locust/locustfile_yaoyi_exp2.py --headless -u 20 -r 2 --run-time 180s \
#   --host https://a.mastodon-yaoyi.online \
#   --csv=results/yaoyi/step0_default
#
# Step 1 — Lift rate limit (RACK_ATTACK_ENABLED=false):
#   [on EC2]: docker compose exec web sh -c "RACK_ATTACK_ENABLED=false"
#   or add to .env.production and restart web container
#   locust -f locust/locustfile_yaoyi_exp2.py --headless -u 20 -r 2 --run-time 180s \
#   --host https://a.mastodon-yaoyi.online \
#   --csv=results/yaoyi/step1_no_rate_limit
#
# Step 2 — Increase web concurrency (WEB_CONCURRENCY=4):
#   [on EC2]: add WEB_CONCURRENCY=4 to .env.production, restart web
#   locust -f locust/locustfile_yaoyi_exp2.py --headless -u 20 -r 2 --run-time 180s \
#   --host https://a.mastodon-yaoyi.online \
#   --csv=results/yaoyi/step2_wc4
#
# Step 3 — Overshoot (WEB_CONCURRENCY=6):
#   locust -f locust/locustfile_yaoyi_exp2.py --headless -u 20 -r 2 --run-time 180s \
#   --host https://a.mastodon-yaoyi.online \
#   --csv=results/yaoyi/step3_wc6