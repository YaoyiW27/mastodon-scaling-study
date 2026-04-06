# Experiment 2 — Bottleneck Shifting / Component Dependency

## Overview

Experiment 1 established that the web application layer was the primary bottleneck under load. Experiment 2 investigates whether that bottleneck can be shifted downstream — specifically, whether increasing web-side capacity would push pressure toward PostgreSQL, Redis, or Sidekiq, and how each component behaves as the system is progressively tuned.

All experiments ran on a single EC2 t3.large instance (2 vCPUs, 8GB RAM) running Mastodon v4.5.7 via Docker Compose. Load was generated using Locust with 20 concurrent users, 2 users/second ramp-up, 180–300 second runtime, using a realistic mixed workload (read-heavy: home timeline ×5, public timeline ×3, notifications ×2, post ×3, favourite ×1, search ×1).

---

## Step 1 — Lift Rate Limiting

### Motivation

Experiment 1 showed a ~55% failure rate at u=20 with default settings. The baseline response headers revealed `x-ratelimit-remaining` values dropping rapidly, suggesting Rack::Attack (Mastodon's middleware-level rate limiter, default 300 requests/5 min per IP) was rejecting a large portion of requests before they ever reached Puma. The hypothesis was: if rate limiting is the primary failure source, removing it should reduce failures and expose the true capacity of the web layer.

### Method

Added `RACK_ATTACK_ENABLED=false` to `.env.production` and restarted the web container. Ran the same Locust profile as baseline.

### Results

| Metric | Baseline (rate limit on) | Rate limit off |
|---|---|---|
| RPS | 13.5 | 12.8 |
| Failure rate | 55% | 33% |
| Median latency | 94ms | 170ms |
| p95 latency | 440ms | 750ms |
| Web CPU | normal | 138% |

Failure rate dropped from 55% to 33%, confirming that Rack::Attack was responsible for a significant portion of baseline failures. However, latency increased substantially — requests that previously got rejected quickly now queued inside Puma, waiting for a worker. Web container CPU hit 138%, approaching the 200% hard ceiling of the t3.large's 2 vCPUs.

Notably, `/api/v1/timelines/public` (unauthenticated) showed 0% failures in both runs — confirming Rack::Attack was specifically throttling authenticated endpoints.

**Key insight:** Rate limiting was not just a bottleneck — it was also acting as backpressure, protecting Puma from being overwhelmed. Removing it shifted the failure mode from 429s at the middleware layer to slower, more expensive failures deeper in the stack.

---

## Step 2 — Increase Web Concurrency (WEB_CONCURRENCY=4)

### Motivation

With rate limiting off, web CPU at 138% and 33% failure rate indicated Puma worker capacity was the new ceiling. The default `WEB_CONCURRENCY=2` means only 2 parallel Ruby processes handling requests. Increasing this should allow more concurrent request processing, potentially eliminating failures.

### Method

Added `WEB_CONCURRENCY=4` and `MAX_THREADS=5` to `.env.production`. Restarted web container. Ran same Locust profile.

### Results

| Metric | Rate limit off, WC=2 | WC=4 |
|---|---|---|
| RPS | 12.8 | 9.2 |
| Failure rate | 33% | **0%** |
| Median latency | 170ms | 530ms |
| p95 latency | 750ms | 2000ms |
| Web CPU | 138% | 161% |
| DB idle connections | ~11 | ~19 |

Zero failures — every request was served successfully. RPS dropped because Locust was waiting longer per request (requests were actually being processed rather than dropped), and latency climbed as 4 workers shared the same 2 vCPUs.

DB connection observation: idle connections grew from ~11 to ~19, consistent with the formula `WEB_CONCURRENCY × MAX_THREADS` — each Puma worker pre-allocates its connection pool on startup. However, active connections stayed at 2–3 regardless, because 84% of reads were served from Redis cache and never reached PostgreSQL.

**Key insight:** WC=4 was the sweet spot for this instance — enough workers to handle concurrent requests without dropping them, and not so many that context-switching overhead dominates.

---

## Step 3 — Increase Web Concurrency Further (WEB_CONCURRENCY=6)

### Motivation

If WC=4 eliminated failures, WC=6 should improve throughput further — or reveal a new downstream bottleneck. The hypothesis was that more workers would either improve latency or expose database connection pressure.

### Method

Changed `WEB_CONCURRENCY=6`. Restarted web container. Ran same Locust profile. Monitored `pg_stat_activity` and `docker stats` simultaneously.

### Results

| Metric | WC=4 | WC=6 |
|---|---|---|
| RPS | 9.2 | 12.5 |
| Failure rate | 0% | 33% |
| Median latency | 530ms | 200ms |
| p95 latency | 2000ms | 790ms |
| Web CPU | 161% | 111% (peak 150%+) |
| DB CPU | ~16% | up to 40% (transient) |

Failures returned at 33%. DB CPU spiked transiently to 40% — higher than any previous run. However, `pg_stat_activity` still showed only 2–3 active connections, meaning the failures were not from DB connection exhaustion but from upstream Puma timeouts — workers were context-switching faster than they could complete requests on the 2-vCPU machine.

**Key insight:** WC=6 overshoots the optimal point for a 2-vCPU instance. Beyond 4 workers, context-switching overhead increases and DB begins to feel transient pressure — but the web CPU ceiling is still the binding constraint, not Postgres. The t3.large's 2 vCPUs cap total parallelism at 200%, regardless of worker count.

---

## Step 4 — Nginx-Level HTTP Caching

### Motivation

Even at WC=4, web CPU reached 161% because every request — including unauthenticated public timeline reads — went through the full Rails middleware stack (routing, auth, serialization) before hitting Redis. The public timeline endpoint accounted for ~10 RPS in testing and its responses are identical across users. Caching at the nginx level would intercept these requests before they ever reach Puma.

### Method

Added a `proxy_cache_path` directive and a dedicated `location /api/v1/timelines/public` block to the nginx host config, with `proxy_cache_valid 200 10s` and `X-Cache-Status` header for observability. Reloaded nginx. Verified cache hits with back-to-back curl requests. Ran same Locust profile with WC=4.

### Results

| Metric | WC=4, no nginx cache | WC=4, nginx cache |
|---|---|---|
| Public timeline median | 500ms | **93ms** |
| Public timeline p95 | 2000ms | **230ms** |
| Public timeline failures | 0% | 0% |
| Web CPU | 161% | ~150% |

Public timeline latency improved 5× — from 500ms median to 93ms. Cache hit verification confirmed `X-Cache-Status: HIT` on repeat requests, meaning nginx served these responses entirely without touching Puma, Rails, or PostgreSQL.

Web CPU reduction was modest because public timeline is only one endpoint in the mixed workload. Authenticated endpoints (home timeline, notifications, posts) still go through Rails.

**Key insight:** HTTP-level caching at the reverse proxy is the most effective single-component optimization available within a single-node deployment. It offloads read traffic before it reaches the application layer entirely — unlike Redis caching, which still requires a full Rails request lifecycle to check.

---

## Redis Cache Hit Rate

During load testing, Redis reported **72,931 hits vs 13,657 misses — an 84% cache hit rate**. This explains why PostgreSQL remained under-stressed throughout all experiments: the vast majority of timeline and notification reads were served from Redis without a DB query. The DB connection pool showed 2–3 active connections even at peak load, with 19 connections sitting idle.

This has an important implication: **PostgreSQL is not the bottleneck in a read-heavy workload on this deployment.** The Redis caching layer is highly effective, and the web CPU ceiling is reached long before DB capacity is meaningfully stressed.

---

## Summary

| Experiment | Change | RPS | Failure Rate | Key Finding |
|---|---|---|---|---|
| Baseline | Default config | 13.5 | 55% | Rack::Attack throttling majority of requests |
| Step 1 | Lift rate limit | 12.8 | 33% | Puma exposed as real bottleneck, web CPU 138% |
| Step 2 | WC=4 | 9.2 | 0% | Sweet spot — zero failures, latency climbs |
| Step 3 | WC=6 | 12.5 | 33% | Overshoots — context switching + DB transient pressure |
| Step 4 | Nginx cache | ~13 | ~7%* | 5× public timeline latency improvement |

*Remaining failures are per-account posting rate limit (429s counted as failures by Locust — not true system errors)

---

## What Drives the Next Experiment

All four steps confirm the same root constraint: **the t3.large's 2 vCPUs are the binding limit.** No amount of software tuning — worker count, caching, rate limit configuration — can move the web CPU ceiling beyond 200%. Sidekiq remained under 35% throughout, Redis under 5%, and PostgreSQL never exceeded 40% transiently.

The only path to shifting the bottleneck downstream to Sidekiq or PostgreSQL is **horizontal scaling** — deploying multiple web containers behind a load balancer so the CPU budget multiplies. This is the motivation for Experiment 3: migrating to ECS Fargate with an Application Load Balancer, where web worker capacity can scale independently of the database and job queue layers.