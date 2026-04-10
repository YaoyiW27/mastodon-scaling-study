# Milestone 2 Report
## Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## 1. Progress Since Milestone 1

At Milestone 1, both instances were deployed and initial experiments were underway. Since then, we have completed Experiment 2 on both instances and produced a direct vertical scaling comparison between t3.medium and t3.large under identical workload and configuration changes.

Completed since Milestone 1:
- Instance A (Yaoyi): Experiment 2 — bottleneck shifting on t3.medium
- Instance B (Yehe): Experiment 2 — bottleneck shifting on t3.large (4 steps: rate limit, WC=4, WC=6, nginx cache)
- Vertical scaling comparison between the two instances
- CloudWatch dashboard deployed for Instance A monitoring

---

## 2. Experiment 2A — Bottleneck Shifting on Instance B (t3.large, Yehe)

### Overview

Experiment 1 established that Mastodon's `rack-attack` rate limiter activates before hardware saturation under authenticated load. Experiment 2 investigates whether disabling the rate limiter and increasing web-side capacity can shift the bottleneck downstream toward PostgreSQL or Sidekiq.

All steps used 20 concurrent users, 2/s ramp, 180–300s runtime, authenticated mixed workload on t3.large (2 vCPU, 8GB RAM).

### Step 1 — Lift Rate Limiting

| Metric | Default (rate limit ON) | Rate limit OFF |
|--------|------------------------|----------------|
| RPS | 13.5 | 12.8 |
| Failure rate | 55% | 33% |
| p50 latency | 94ms | 170ms |
| p95 latency | 440ms | 750ms |
| Web CPU | normal | 138% |

Removing the rate limiter shifted the failure mode from instant 429 rejections to slower Puma timeouts. Web CPU jumped to 138%, confirming the web layer — not the database — is the true bottleneck.

### Step 2 — WEB_CONCURRENCY=4

| Metric | Rate limit OFF, WC=2 | WC=4 |
|--------|---------------------|------|
| RPS | 12.8 | 9.2 |
| Failure rate | 33% | **0%** |
| p50 latency | 170ms | 530ms |
| p95 latency | 750ms | 2,000ms |
| Web CPU | 138% | 161% |
| DB idle connections | ~11 | ~19 |

Zero failures at WC=4. DB connections grew (consistent with `WEB_CONCURRENCY × MAX_THREADS`) but active connections stayed at 2–3 because 84% of reads were served from Redis cache.

### Step 3 — WEB_CONCURRENCY=6

| Metric | WC=4 | WC=6 |
|--------|------|------|
| RPS | 9.2 | 12.5 |
| Failure rate | 0% | 33% |
| p50 latency | 530ms | 200ms |
| p95 latency | 2,000ms | 790ms |
| DB CPU | ~16% | up to 40% (transient) |

WC=6 overshoots. Failures returned and DB CPU spiked transiently — but active connections remained low, so DB exhaustion was not the cause. Context-switching overhead on 2 vCPUs was the binding constraint.

### Step 4 — Nginx-Level HTTP Caching

| Metric | WC=4, no cache | WC=4, nginx cache |
|--------|---------------|-------------------|
| Public timeline p50 | 500ms | **93ms** |
| Public timeline p95 | 2,000ms | **230ms** |
| Web CPU | 161% | ~150% |

Nginx caching intercepted public timeline requests before they reached Puma, producing a 5× latency improvement. Redis cache hit rate was 84% throughout, confirming PostgreSQL was never the bottleneck.

### Redis Cache Hit Rate

During load testing, Redis reported **72,931 hits vs 13,657 misses (84% hit rate)**. PostgreSQL active connections stayed at 2–3 throughout all steps, confirming the database was not the bottleneck.

### Summary — Instance B

| Step | Change | RPS | Failure Rate | Key Finding |
|------|--------|-----|--------------|-------------|
| Baseline | Default | 13.5 | 55% | rack-attack throttling |
| Step 1 | No rate limit | 12.8 | 33% | Puma exposed, web CPU 138% |
| Step 2 | WC=4 | 9.2 | 0% | Sweet spot — zero failures |
| Step 3 | WC=6 | 12.5 | 33% | Context switching overhead |
| Step 4 | Nginx cache | ~13 | ~7% | 5× public timeline improvement |

---

## 3. Experiment 2B — Bottleneck Shifting on Instance A (t3.medium, Yaoyi)

### Overview

The same workload was applied to Instance A (t3.medium, 2 vCPU, 4GB RAM) to measure how a smaller instance responds to the same tuning steps. Three accounts were used to distribute rate limit pressure.

### Step 0 — Default Configuration

| Metric | Value |
|--------|-------|
| Total requests | 1,674 |
| Failure rate | 41.6% (all HTTP 429) |
| p50 latency | 120ms |
| p95 latency | 300ms |
| p99 latency | 420ms |
| RPS | 9.3 |
| Web CPU | ~58% |
| DB CPU | ~3.9% |

### Step 2 — WEB_CONCURRENCY=4

| Metric | Value |
|--------|-------|
| Total requests | 1,649 |
| Failure rate | 42.7% |
| Failure types | HTTP 429 + **HTTP 502 Bad Gateway** |
| p50 latency | 120ms |
| p95 latency | 380ms |
| p99 latency | 1,500ms |
| p99.9 | 4,900ms |
| RPS | 9.2 |

WC=4 introduced 502 errors that were absent at WC=2. Tail latency jumped from 420ms to 1,500ms at p99. The t3.medium could not absorb additional workers under load.

---

## 4. Vertical Scaling Comparison

| Metric | Instance A (t3.medium) | Instance B (t3.large) |
|--------|----------------------|----------------------|
| Default failure rate (20u) | 41.6% | 55.1% |
| Default p95 | 300ms | 440ms |
| Default RPS | 9.3 | 13.5 |
| WC=4 failure rate | **42.7%** (worse) | **0%** (eliminated) |
| WC=4 p99 | 1,500ms | 530ms |
| WC=4 502 errors | **Yes** | No |
| Optimal WEB_CONCURRENCY | 2 | 4 |

### Key finding

The most significant difference between the two instances emerges at WEB_CONCURRENCY=4. On t3.large, WC=4 eliminated all failures — the instance had enough memory and CPU headroom to support 4 parallel Puma workers. On t3.medium, WC=4 caused 502 errors and dramatically increased tail latency — the 2-vCPU ceiling was already stressed, and additional workers increased context-switching overhead without adding capacity.

Instance size is a binding constraint for Mastodon's worker scaling. The t3.medium cannot benefit from the same tuning that eliminates failures on t3.large.

---

## 5. Federation Validation and Propagation Latency

Both instances successfully federated via ActivityPub after HTTPS + Nginx was configured. All four checks passed: remote account discovery, mutual follow, remote post visibility, and remote like notification.

Key finding: federation required HTTPS + Nginx. Direct HTTP on port 3000 broke WebFinger discovery regardless of application configuration.

After completing the validation checks, we ran an initial idle-condition propagation latency measurement using `federation_test.py`. This script posts a uniquely marked status on Instance A and polls Instance B's home timeline until the post appears, recording the end-to-end delivery time.

| Condition | Successful | Avg | Min | Max |
|-----------|-----------|-----|-----|-----|
| idle | 5/5 | 0.67s | 0.57s | 0.80s |

Under idle conditions, cross-instance delivery was fast and consistent. Full latency measurements under load are deferred to Milestone 3.

---

## 6. What Remains

- **Federation propagation latency under load** — measure delivery latency at 20 and 50 concurrent users on Instance B
- **Final report** — integrate all experiment results
- **Presentation** — Apr 13 or April 20

---

## 7. Updated Timeline

| Date | Task |
|------|------|
| Apr 9 | Experiment 2 complete on both instances ✅ |
| Apr 10–11 | Federation latency test |
| Apr 11–12 | Final report draft |
| Apr 12 | Rehearsal |
| Apr 13 | Presentation |
| Apr 14–20 | Final submission |