"""
Combined Federation Latency + Load Test — CS6650 Final Project
Yaoyi Wang & Yehe Yan

Automatically ramps up Locust load in the background while
measuring federation propagation latency at each stage.

Stages:
  1. idle        —  0 users  (baseline, no Locust)
  2. light       — 20 users
  3. moderate    — 50 users
  4. heavy       — 100 users  (comment out if instance can't handle it)
"""

import time
import requests
import csv
import os
import threading
import subprocess
import sys

# ─── Instance Config ───────────────────────────────────────────────────────────

INSTANCE_A = "https://mastodon-yehe.click"         # your instance (poster)
INSTANCE_B = "https://a.mastodon-yaoyi.online"     # her instance (observer)

TOKEN_A = "M0dvzMtRVxRZwz_A_NLa5jmQdTz7pFaub9br7wlH6-U"   # your token (posts)
TOKEN_B = "NCtVhVoXDfWaDZm-aFARuo-XpePa4N91HDXAoiagFpw"   # her token (polls timeline)

HEADERS_A = {"Authorization": f"Bearer {TOKEN_A}"}
HEADERS_B = {"Authorization": f"Bearer {TOKEN_B}"}

# ─── Federation Test Config ────────────────────────────────────────────────────

RESULTS_FILE = "results/federation_latency.csv"
TIMEOUT = 60        # max seconds to wait for propagation
POLL_INTERVAL = 0.5
N_RUNS = 5          # number of federation tests per load stage

# ─── Load Stages ──────────────────────────────────────────────────────────────
# Each stage: (label, num_users, spawn_rate)
# Set num_users=0 for the idle baseline (no Locust)

LOAD_STAGES = [
    # ("idle",     0,   0),
    # ("light",    20,  2),
    ("moderate", 50,  5),
    ("heavy",    100, 10),
    #    ("semi-heavy", 150, 15),  # comment out if instance can't handle it
    #     ("super-heavy", 200, 20),  # comment out if instance can't handle it
    # ("extreme",  500, 50),  # comment out if instance can't handle it
    # ("max",      1000, 100),  # comment out if instance can't handle it
]

LOCUST_HOST = INSTANCE_A  # Locust hammers the instance you're posting FROM
LOCUST_FILE = "locustfile_yehe.py"  # path to your existing locust file
WARMUP_SECONDS = 15  # seconds to wait after ramping before measuring

# ─── Locust Process Manager ────────────────────────────────────────────────────

locust_process = None

def start_locust(num_users, spawn_rate):
    """Start Locust headlessly with the given user count."""
    global locust_process

    stop_locust()  # stop any existing run first

    cmd = [
        "locust",
        "-f", LOCUST_FILE,
        "--headless",
        "-u", str(num_users),
        "-r", str(spawn_rate),
        "--host", LOCUST_HOST,
        "--run-time", "9999s",   # run until we stop it
        "--csv", f"results/locust_{num_users}users",
    ]

    print(f"  [Locust] Starting {num_users} users (spawn rate: {spawn_rate}/s)...")
    locust_process = subprocess.Popen(
            cmd,
            stdout=open("results/locust_stdout.log", "w"),
            stderr=open("results/locust_stderr.log", "w"),
        )
    print(f"  [Locust] PID {locust_process.pid} — waiting {WARMUP_SECONDS}s for load to ramp up...")
    time.sleep(WARMUP_SECONDS)
    print(f"  [Locust] Load is up.")

def stop_locust():
    """Stop the running Locust process if any."""
    global locust_process
    if locust_process and locust_process.poll() is None:
        print(f"  [Locust] Stopping PID {locust_process.pid}...")
        locust_process.terminate()
        try:
            locust_process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            locust_process.kill()
        locust_process = None

# ─── Federation Test Logic ─────────────────────────────────────────────────────

def post_on_instance_a(run_id):
    """Post a uniquely identifiable status on Instance A."""
    marker = f"federation-test-run-{run_id}-{int(time.time())}"
    resp = requests.post(
        f"{INSTANCE_A}/api/v1/statuses",
        json={"status": marker, "visibility": "public"},
        headers=HEADERS_A,
        timeout=30
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
            timeout=30
        )
        if resp.status_code == 200:
            for post in resp.json():
                if marker in post.get("content", "") or marker in post.get("text", ""):
                    return time.time() - post_time

        time.sleep(POLL_INTERVAL)
    return None  # timed out


def run_federation_test(n_runs, load_label):
    """Run n_runs federation latency measurements and save to CSV."""
    os.makedirs("results", exist_ok=True)
    results = []

    print(f"\n  [Federation] Running {n_runs} tests (load: {load_label})")
    print("  " + "-" * 48)

    for i in range(n_runs):
        try:
            uri, marker, post_time = post_on_instance_a(i)
            print(f"  Run {i+1}/{n_runs}: posted {marker[:45]}...")

            latency = wait_for_propagation(marker, post_time)

            if latency is not None:
                print(f"    → propagated in {latency:.2f}s")
                results.append({
                    "run": i + 1,
                    "load": load_label,
                    "latency_s": round(latency, 3),
                    "timed_out": False
                })
            else:
                print(f"    → TIMED OUT after {TIMEOUT}s")
                results.append({
                    "run": i + 1,
                    "load": load_label,
                    "latency_s": None,
                    "timed_out": True
                })

            time.sleep(2)

        except Exception as e:
            print(f"    → ERROR: {e}")
            results.append({
                "run": i + 1,
                "load": load_label,
                "latency_s": None,
                "timed_out": True
            })

    # Save to CSV
    file_exists = os.path.exists(RESULTS_FILE)
    with open(RESULTS_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["run", "load", "latency_s", "timed_out"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)

    # Print summary
    successful = [r for r in results if r["latency_s"] is not None]
    if successful:
        latencies = [r["latency_s"] for r in successful]
        print(f"\n  Summary ({load_label}):")
        print(f"    Successful : {len(successful)}/{n_runs}")
        print(f"    Min        : {min(latencies):.2f}s")
        print(f"    Max        : {max(latencies):.2f}s")
        print(f"    Avg        : {sum(latencies)/len(latencies):.2f}s")
    else:
        print(f"\n  All runs timed out under {load_label} load.")

    return results


# ─── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Combined Federation Latency + Load Test")
    print("=" * 60)

    all_results = {}

    try:
        for label, num_users, spawn_rate in LOAD_STAGES:
            print(f"\n{'='*60}")
            print(f"  STAGE: {label.upper()} ({num_users} users)")
            print(f"{'='*60}")

            if num_users == 0:
                print("  [Locust] Skipping — idle baseline, no load generated.")
            else:
                start_locust(num_users, spawn_rate)

            all_results[label] = run_federation_test(N_RUNS, label)

            stop_locust()
            print(f"\n  [Locust] Stopped. Cooling down 5s before next stage...")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")

    finally:
        stop_locust()

    # ── Final summary across all stages ──────────────────────────────────────
    print(f"\n{'='*60}")
    print("  FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Stage':<12} {'Success':<10} {'Avg(s)':<10} {'Min(s)':<10} {'Max(s)':<10}")
    print(f"  {'-'*52}")

    for label, results in all_results.items():
        successful = [r for r in results if r["latency_s"] is not None]
        if successful:
            latencies = [r["latency_s"] for r in successful]
            print(f"  {label:<12} {len(successful)}/{N_RUNS:<8} "
                  f"{sum(latencies)/len(latencies):<10.2f} "
                  f"{min(latencies):<10.2f} "
                  f"{max(latencies):<10.2f}")
        else:
            print(f"  {label:<12} 0/{N_RUNS:<8} {'TIMEOUT':<10} {'—':<10} {'—':<10}")

    print(f"\n  Results saved to: {RESULTS_FILE}")
    print(f"  Locust CSVs saved to: results/locust_*")