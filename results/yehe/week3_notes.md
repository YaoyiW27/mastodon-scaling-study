# Experiment 3 — Component Dependency Isolation

## Overview

Having established the web layer as the primary bottleneck in Experiment 2, Experiment 3 investigates how Mastodon behaves when individual downstream components are removed entirely. The goal is to characterize each component's dependency type — synchronous vs asynchronous — and understand what failure mode each produces.

Two tests were run sequentially on the same t3.large EC2 instance with WC=4, nginx cache enabled, and rate limiting disabled. Load was generated using Locust at u=20, 2 users/second ramp, 180 second runtime.

---

## Test 1 — Sidekiq Stopped

### Method

Stopped the Sidekiq container while keeping web, db, and Redis running. Monitored queue depth across all three active queues (default, pull, push) in real time via `redis-cli llen`. Ran standard Locust profile during the outage.

### Results

**Locust results:**

| Metric | Normal (WC=4) | Sidekiq stopped |
|---|---|---|
| RPS | 9.2 | 14.0 |
| Real failure rate* | ~7% | ~13% |
| Median latency | 530ms | 89ms |
| p95 latency | 2000ms | 380ms |
| Web CPU | 161% | ~120% |

*excluding 429 post rate limit rejections

**Queue depth during outage:**

| Queue | Purpose | Growth during test |
|---|---|---|
| default | Fan-out, notifications, media | 0 → 1,544+ |
| push | ActivityPub delivery to remote instances | 0 → 716+ |
| pull | Pulling content from remote instances | 0 → 714+ |
| Total enqueued | — | 2,680 → 4,000+ |
| Queue latency | Time since oldest job | 627 seconds |

### Observations

Web requests continued to succeed normally — in fact latency improved significantly (530ms → 89ms median) because Sidekiq was no longer competing for the t3.large's 2 vCPUs. From Locust's perspective the system looked healthier than normal.

Meanwhile, 2,680+ jobs silently backed up in Redis with no worker to process them. Federation delivery stopped entirely. Followers never received new posts. Notifications were never sent. Remote timeline updates ceased. All of this was completely invisible to the HTTP layer.

### Dependency type: Asynchronous — Silent Degradation

Rails enqueues a job into Redis with a fast in-memory write and immediately returns 200 to the client. It never waits for Sidekiq to process the job. The web layer has no awareness of whether Sidekiq is running — the decoupling is by design.

The result is a system that appears healthy from the outside but is functionally broken at the social layer. A user posting receives a 200 response but their followers never see the post. Likes and mentions generate no notifications. Federation with other instances stops completely.

> This is the most dangerous failure mode in distributed systems — **silent degradation**. Unlike a hard crash, there are no error logs, no 500s, no alerts firing. The system accepts work indefinitely while delivering nothing. Queue depth climbs for hours before anyone notices.

---

## Test 2 — Redis Stopped

### Method

Brought Sidekiq back and waited for queues to drain to zero. Then stopped the Redis container while keeping web, db, and Sidekiq running. Ran the same Locust profile.

### Results

**Failure rate: 100% immediately.**

Web container error logs:
```
RuntimeError (Temporary failure in name resolution):
  app/models/ip_block.rb:46 IpBlock.blocked_ips_map
  config/initializers/rack_attack.rb:66
```

Every single request failed with a RuntimeError before reaching any application logic.

### Root cause

Rack::Attack — Mastodon's middleware-level rate limiter — checks the IP blocklist on every incoming request by calling `IpBlock.blocked_ips_map`, which reads from Redis cache. When Redis is unreachable, this call raises a RuntimeError that propagates up and crashes the entire request. No request gets past the first middleware layer.

```
Request → Rack::Attack middleware → IpBlock.blocked? → Redis lookup → Redis down → RuntimeError → 500
```

The web container itself keeps running — Puma doesn't crash — but it cannot serve a single request successfully.

### Dependency type: Synchronous — Immediate Hard Failure

Redis is not merely a performance cache. It is embedded in the synchronous request path at the middleware layer, before authentication, before routing, before any Rails controller logic runs. Every request requires Redis to be available just to pass the IP blocklist check.

Additionally Redis serves as:
- Session store — user authentication state
- Timeline cache — 84% of read traffic served from Redis
- Sidekiq queue backend — job storage and delivery
- Rate limit counters — per-user and per-IP throttling

Losing Redis means losing all of these simultaneously. There is no fallback path.

---

## Comparison

| | Sidekiq stopped | Redis stopped |
|---|---|---|
| Dependency type | Asynchronous | Synchronous |
| Failure mode | Silent degradation | Immediate hard failure |
| HTTP requests | Still succeed | 100% fail |
| Latency | Improves (less CPU contention) | N/A — all 500s |
| Visible to monitoring | No — requires queue depth monitoring | Yes — error rate spikes immediately |
| User experience | Posts accepted, nothing delivers | Cannot log in or load any page |
| Detection difficulty | High — needs queue depth alerting | Low — obvious from error rate |

---

## Significance

These two tests reveal the fundamental architectural split in Mastodon's design:

**Redis is the nervous system.** It sits in the synchronous request path and touches every layer — middleware, sessions, cache, and job queue. It is the single most critical component in the stack. Taking it down is equivalent to taking down the entire application.

**Sidekiq is the muscle.** It does the heavy lifting asynchronously — federation, fan-out, notifications — but the web layer doesn't wait for it. The decoupling allows the UI to remain responsive even when background processing is degraded, at the cost of silent failure when Sidekiq is down.

The latency improvement observed when Sidekiq was stopped is an artifact of the single-node deployment — all containers share 2 vCPUs on the t3.large, so removing Sidekiq frees CPU for the web container. In a properly architected deployment this resource contention would not exist.

---

## Test 3 — Redis Cache Disabled (Force DB Reads)

### Motivation

Throughout all previous experiments, PostgreSQL remained under-stressed because Redis absorbed 84% of read traffic. Simply stopping Postgres would produce the same hard failure story as Redis. A more interesting question is: what does DB look like under real read pressure? By invalidating the Redis cache namespace, every timeline and notification read is forced through to PostgreSQL, revealing the true DB capacity and the cost of cache absence.

### Method

Added `REDIS_CACHE_NAMESPACE=invalid_cache` to `.env.production` and restarted the web container. This causes Rails to look for cache keys under a namespace that doesn't exist, forcing every cache lookup to miss and fall through to PostgreSQL. Verified cache bypass by resetting Redis stats and confirming misses exceeded hits (76 misses vs 64 hits) after a few requests — a complete reversal of the normal 84% hit rate. Redis memory also dropped from ~17MB to ~5.5MB confirming timeline data was no longer being cached. Ran same Locust profile with WC=4.

### Results

| Metric | Cache enabled (WC=4) | Cache disabled |
|---|---|---|
| RPS | 9.2 | 14.2 |
| Real failure rate* | ~7% | ~35% |
| Median latency | 530ms | 54ms |
| p95 latency | 2000ms | 340ms |
| Web CPU | 161% | 26% |
| DB CPU | ~16% | 5.46% |
| DB active connections | 2–3 | 1 |

*excluding 429 post rate limit rejections

**Per-endpoint failure rates:**

| Endpoint | Cache enabled | Cache disabled |
|---|---|---|
| Public timeline | 0% | **0%** |
| Public timeline [fav] | 0% | **0%** |
| Home timeline | ~7% | **67%** |
| Notifications | ~10% | **58%** |
| Search | ~5% | **63%** |
| Posts (429s excluded) | ~7% | ~7% |

### Observations

**The fast-fail paradox:** Median latency dropped from 530ms to 54ms while failure rate tripled. Requests are failing fast — they attempt a DB query, encounter an error or missing cached data structure, and return a quick failure rather than a slow successful response. This explains low CPU on both web (26%) and DB (5.46%) — failed requests consume fewer resources than slow successful ones.

**Public timeline stayed at 0% failures** — nginx cache is serving it entirely before Rails runs, independent of Redis application cache. This validates the nginx caching experiment finding: HTTP-level caching is more resilient than application-level caching because it survives Redis degradation.

**Home timeline collapsed to 67% failure rate** — this endpoint depends most heavily on Redis. The cached home timeline feed is a precomputed per-user data structure maintained by Sidekiq fan-out jobs and stored in Redis. Without it, Rails attempts to reconstruct the timeline from DB queries, which either fails or returns incomplete data for accounts with complex follow graphs.

**DB was never the bottleneck** — even with cache fully disabled, DB CPU peaked at 5.46% and active connections stayed at 1. The failures were not caused by DB saturation but by missing Redis data structures that the application depends on for correctness, not just performance.

### Dependency type: Redis as Data Store, Not Just Cache

This experiment reveals that Redis serves a dual role in Mastodon. For public timelines it acts as a pure performance cache — if the cache is cold, DB can reconstruct the data. But for home timelines and notifications, Redis stores **precomputed materialized views** that are maintained by Sidekiq and cannot be trivially reconstructed from a DB query. Removing Redis cache doesn't just slow these endpoints down — it breaks them entirely.

```
Public timeline:  Redis miss → DB query → reconstructed successfully → 200
Home timeline:    Redis miss → DB query → incomplete/missing fan-out data → failure
```

This is a critical architectural distinction: Redis is simultaneously a cache, a session store, a job queue backend, and a primary data store for materialized timeline views. Its failure modes are therefore more complex than a simple cache invalidation.

---

## What Should Be Done Properly

### 1. Redis High Availability
Redis should never be a single point of failure. Production deployments should use **Redis Sentinel** (automatic failover with a standby replica) or **Redis Cluster** (sharded, multi-node). AWS ElastiCache provides both as managed services. A Redis failure in production without HA is a complete outage.

### 2. Sidekiq Queue Depth Alerting
Since Sidekiq failure is silent at the HTTP layer, explicit monitoring is essential. CloudWatch or Prometheus should alert when queue depth exceeds a threshold (e.g., default queue > 500 jobs, latency > 60 seconds). Without this, a Sidekiq outage can go undetected for hours.

### 3. Separate Services onto Separate Machines
Running web, Sidekiq, Redis, and PostgreSQL on the same EC2 instance means they compete for the same 2 vCPUs. In production each service should run on dedicated infrastructure — web containers on ECS Fargate, Redis on ElastiCache, PostgreSQL on RDS, Sidekiq workers on separate ECS tasks with independent scaling policies. This eliminates the CPU contention observed in this experiment and allows each component to scale independently.

### 4. Sidekiq Redundancy
Multiple Sidekiq worker containers should run in parallel. If one crashes, others continue processing. ECS Fargate with a desired count of 2+ Sidekiq tasks provides this automatically, with auto-restart on failure.

### 5. Health Check Integration
Docker Compose health checks exist for web and streaming but Sidekiq's check (`ps aux | grep sidekiq`) only verifies the process is running, not that it is processing jobs. A proper health check should verify queue latency is below a threshold and alert if jobs are backing up even with the process running.