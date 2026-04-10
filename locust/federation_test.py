"""
Federation Propagation Latency Test — CS6650 Final Project
Yaoyi Wang & Yehe Yan

Measures how long it takes for a post on Instance A to appear
on Instance B's home timeline under different load conditions.

Requirements:
- Instance A and B must be federated (mutual follow already set up)
- TOKEN_A: access token for yaoyi@a.mastodon-yaoyi.online
- TOKEN_B: access token for admin@mastodon-yehe.click
"""

import time
import requests
import csv
import os

INSTANCE_A = "https://a.mastodon-yaoyi.online"
INSTANCE_B = "https://mastodon-yehe.click"

TOKEN_A = "NCtVhVoXDfWaDZm-aFARuo-XpePa4N91HDXAoiagFpw"  # yaoyi@a.mastodon-yaoyi.online
TOKEN_B = "5xnsq-NYs95ooDs1xZEW5HeNx4ANOvagxJsl13I7Lj0"  # testuser1@mastodon-yehe.click

HEADERS_A = {"Authorization": f"Bearer {TOKEN_A}"}
HEADERS_B = {"Authorization": f"Bearer {TOKEN_B}"}

RESULTS_FILE = "results/federation_latency.csv"
TIMEOUT = 60  # max seconds to wait for propagation
POLL_INTERVAL = 0.5


def post_on_instance_a(run_id):
    """Post a uniquely identifiable status on Instance A."""
    marker = f"federation-test-run-{run_id}-{int(time.time())}"
    resp = requests.post(
        f"{INSTANCE_A}/api/v1/statuses",
        json={"status": marker, "visibility": "public"},
        headers=HEADERS_A,
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    return data["uri"], marker, time.time()


def wait_for_propagation(marker, post_time):
    """Poll Instance B's home timeline until the post appears."""
    deadline = post_time + TIMEOUT
    while time.time() < deadline:
        resp = requests.get(
            f"{INSTANCE_B}/api/v1/timelines/home?limit=20",
            headers=HEADERS_B,
            timeout=10
        )
        if resp.status_code == 200:
            for post in resp.json():
                if marker in post.get("content", "") or marker in post.get("text", ""):
                    return time.time() - post_time
        time.sleep(POLL_INTERVAL)
    return None  # timed out


def run_federation_test(n_runs=10, load_label="idle"):
    """
    Run n_runs federation latency measurements.
    load_label: 'idle', 'light_load', 'moderate_load'
    """
    os.makedirs("results", exist_ok=True)
    results = []

    print(f"\nRunning {n_runs} federation latency tests (load: {load_label})")
    print("-" * 50)

    for i in range(n_runs):
        try:
            uri, marker, post_time = post_on_instance_a(i)
            print(f"Run {i+1}/{n_runs}: posted {marker[:40]}...")

            latency = wait_for_propagation(marker, post_time)

            if latency is not None:
                print(f"  → propagated in {latency:.2f}s")
                results.append({
                    "run": i + 1,
                    "load": load_label,
                    "latency_s": round(latency, 3),
                    "timed_out": False
                })
            else:
                print(f"  → TIMED OUT after {TIMEOUT}s")
                results.append({
                    "run": i + 1,
                    "load": load_label,
                    "latency_s": None,
                    "timed_out": True
                })

            time.sleep(2)  # brief pause between runs

        except Exception as e:
            print(f"  → ERROR: {e}")
            results.append({
                "run": i + 1,
                "load": load_label,
                "latency_s": None,
                "timed_out": True
            })

    # Save results
    file_exists = os.path.exists(RESULTS_FILE)
    with open(RESULTS_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["run", "load", "latency_s", "timed_out"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)

    # Summary
    successful = [r for r in results if r["latency_s"] is not None]
    if successful:
        latencies = [r["latency_s"] for r in successful]
        print(f"\nSummary ({load_label}):")
        print(f"  Successful: {len(successful)}/{n_runs}")
        print(f"  Min: {min(latencies):.2f}s")
        print(f"  Max: {max(latencies):.2f}s")
        print(f"  Avg: {sum(latencies)/len(latencies):.2f}s")
    else:
        print(f"\nAll runs timed out.")

    return results


if __name__ == "__main__":
    # Run under idle conditions first
    # Then run while Locust is applying load on both instances

    # Idle test
    run_federation_test(n_runs=5, load_label="idle")

    # After running Locust at 20 users on both instances, run:
    # run_federation_test(n_runs=5, load_label="light_load")

    # After running Locust at 50 users on both instances, run:
    # run_federation_test(n_runs=5, load_label="moderate_load")