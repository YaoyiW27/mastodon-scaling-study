# Experiment 2 — Bottleneck Shifting on t3.medium
## Vertical Scaling Comparison: Instance A (t3.medium) vs Instance B (t3.large)

**Instance:** `a.mastodon-yaoyi.online` — EC2 t3.medium (2 vCPU, 4GB RAM)
**Tool:** Locust
**Workload:** 20 concurrent users, 2/s ramp, 180s
**Accounts:** 3 tokens (yaoyi, testuser1, testuser2) to distribute rate limit pressure

---

## Objective

Replicate Yehe's bottleneck shifting experiment on Instance A (t3.medium) to measure how a smaller instance responds to the same tuning steps. The goal is to compare Instance A (t3.medium) vs Instance B (t3.large) under identical workload and configuration changes.

---

## Step 0 — Default Configuration (Rate Limit ON, WEB_CONCURRENCY=2)

### Results

| Metric | Value |
|--------|-------|
| Total requests | 1,674 |
| Failures | 697 (41.6%) |
| Failure type | HTTP 429 Too Many Requests |
| Avg latency | 159ms |
| p50 | 120ms |
| p95 | 300ms |
| p99 | 420ms |
| RPS | 9.3 |
| Web container CPU | ~58% |
| DB CPU | ~3.9% |
| Sidekiq CPU | ~1.5% |

### Per-endpoint failure breakdown

| Endpoint | Requests | Failures | Failure % |
|----------|----------|----------|-----------|
| POST /api/v1/statuses | 309 | 192 | 62.1% |
| GET /api/v1/timelines/home | 519 | 194 | 37.4% |
| GET /api/v1/notifications | 241 | 87 | 36.1% |
| GET /api/v1/timelines/public | 362 | 148 | 40.9% |
| GET /api/v2/search | 108 | 34 | 31.5% |

### Key observation
Rate limiter (`rack-attack`) activates at 20 users even with 3 distributed accounts. Write endpoints (POST /statuses) hit rate limits harder than read endpoints. Web CPU at 58%, DB stays low at 3.9% — web layer is the bottleneck, not the database.

---

## Step 2 — Increased Web Concurrency (WEB_CONCURRENCY=4)

### Configuration change
```bash
echo "WEB_CONCURRENCY=4" >> ~/mastodon/.env.production
docker compose up -d --force-recreate web
```

### Results

| Metric | Value |
|--------|-------|
| Total requests | 1,649 |
| Failures | 704 (42.7%) |
| Failure types | HTTP 429 + **HTTP 502 Bad Gateway** |
| Avg latency | 209ms |
| p50 | 120ms |
| p95 | 380ms |
| p99 | 1,500ms |
| p99.9% | 4,900ms |
| RPS | 9.2 |

### Per-endpoint failure breakdown

| Endpoint | Requests | Failures | Failure % |
|----------|----------|----------|-----------|
| POST /api/v1/statuses | 321 | 214 | 66.7% |
| GET /api/v1/timelines/home | 495 | 195 | 39.4% |
| GET /api/v1/notifications | 210 | 91 | 43.3% |
| GET /api/v1/timelines/public | 332 | 98 | 29.5% |

### Key observation
WEB_CONCURRENCY=4 introduced **502 Bad Gateway errors** that were absent in Step 0. P99 latency jumped from 420ms to 1,500ms, and P99.9 reached 4,900ms. On t3.medium (2 vCPU), adding more Puma workers caused context-switching overhead that degraded performance rather than improving it. The instance began to show signs of resource exhaustion.

---

## Vertical Scaling Comparison: t3.medium vs t3.large

| Metric | Instance A (t3.medium) | Instance B (t3.large) |
|--------|----------------------|----------------------|
| Default failure rate (20u) | 41.6% | 55.1% |
| Default p95 | 300ms | 440ms |
| Default web CPU | ~58% | elevated |
| WC=4 failure rate | 42.7% | **0%** |
| WC=4 p99 | 1,500ms | 530ms |
| WC=4 502 errors | **Yes** | No |

### Key finding
The most significant difference between the two instances emerges at WEB_CONCURRENCY=4:
- On **t3.large**: WC=4 eliminated all failures and reduced latency — the instance had enough CPU headroom to support 4 parallel Puma workers.
- On **t3.medium**: WC=4 made things worse, introducing 502 errors and dramatically increasing tail latency — the 2-vCPU ceiling was already stressed, and adding more workers increased context-switching overhead without adding capacity.

This confirms that **instance size is a binding constraint** for Mastodon's web worker scaling. The t3.medium's 2 vCPUs cannot support WC=4 under authenticated load, while the t3.large's 2 vCPUs (with 2x the memory) handle it cleanly.

---

## CloudWatch Observations

CPU utilization across all steps showed consistent peaks of 30–50% EC2-level CPU, with the web container consuming the majority. CPU Credit Balance remained stable and increasing throughout, indicating the instance was not in sustained burst mode.

See: `screenshots/exp2_bottleneck_shifting/exp2_cloudwatch_all_steps.png`

---

## Conclusion

Instance size materially affects Mastodon's ability to benefit from web worker scaling. A t3.medium instance hits a performance ceiling at WEB_CONCURRENCY=2, while a t3.large can absorb WC=4 without failures. The rate limiter (`rack-attack`) activates on both instances before hardware saturation is reached, but the consequences of bypassing it differ significantly by instance size.
