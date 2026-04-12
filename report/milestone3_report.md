# Milestone 3 Report
## Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## 1. Progress Since Milestone 2

At Milestone 2, both instances had completed the bottleneck-shifting experiments and a basic federation validation. The one remaining experiment was federation propagation latency under load. Since Milestone 2, we have completed that experiment and finalized all data collection.

Completed since Milestone 2:
- Federation propagation latency test under idle, light load (20 users), and moderate load (50 users) conditions
- Full `federation_latency.csv` dataset collected
- Component dependency isolation experiments (Sidekiq stopped, Redis stopped, Redis cache disabled)
- Results and graphs document updated with Experiment 3B and Experiment 4 sections
- README status table updated to reflect all experiments complete

---

## 2. Experiment 3 — Federation Propagation Latency Under Load

### Overview

The goal of this experiment is to measure how long it takes for a post created on Instance A to appear on Instance B's home timeline, and how that latency changes as Instance B is placed under increasing concurrent load.

This experiment is motivated by a fundamental question about federated systems: ActivityPub delivery is asynchronous and relies on Sidekiq background workers. Under normal conditions, delivery is fast because Sidekiq processes the inbox queue quickly. Under load, Sidekiq must share CPU with Puma web workers. If Sidekiq falls behind, federation delivery degrades — not because the network is slow, but because the receiving instance cannot process incoming ActivityPub payloads fast enough.

### Setup

- **Instance A** (`a.mastodon-yaoyi.online`, t3.medium): posts a uniquely marked status via the Mastodon API
- **Instance B** (`mastodon-yehe.click`, t3.large): polled every 0.5 seconds on the home timeline until the post appears
- **Tool:** `locust/federation_test.py`
- **Timeout:** 60 seconds per run
- **Runs per condition:** 5
- **Load on Instance B:** applied using `locust/locustfile_yehe.py` (authenticated mixed workload)

The test measures end-to-end federation delivery latency: from the moment the post is created on Instance A to the moment it appears on Instance B's home timeline. This includes Instance A's Sidekiq serializing and delivering the ActivityPub payload, the network round trip, and Instance B's Sidekiq processing the inbox job.

### Results

| Load Condition | Locust Users on Instance B | Successful | Avg Latency | Min | Max | Timeouts |
|---|---|---|---|---|---|---|
| idle | 0 | 5/5 | 0.67s | 0.57s | 0.80s | 0 |
| light_load | 20 | 5/5 | 6.53s | 0.84s | 28.73s | 0 |
| moderate_load | 50 | 4/5 | 4.32s | 1.63s | 5.72s | 1 |

### Analysis

**Idle condition.** At idle, federation latency is stable and fast. All 5 runs completed with an average of 0.67s and a range of only 0.23s. This confirms that the baseline ActivityPub delivery path — serialization, HTTP delivery, and inbox processing — adds less than one second of latency when both instances are unloaded.

**Light load (20 users).** Average latency increased nearly 10× to 6.53s. More significantly, run 1 produced a 28.73s spike before stabilizing at 0.84–1.04s for the remaining four runs. This pattern is consistent with Sidekiq worker starvation on Instance B: when the 20-user Locust workload ramped up, Puma workers competed with Sidekiq for CPU. The first federation delivery job queued behind the initial burst of HTTP request processing and was delayed until Sidekiq caught up. Once the system stabilized, subsequent deliveries completed in under 1.1s — indicating that the starvation was transient rather than sustained.

**Moderate load (50 users).** Average latency remained elevated at 4.32s, with values ranging from 1.63s to 5.72s. Run 5 timed out entirely after 60 seconds. This indicates that at 50 users, the Sidekiq queue on Instance B was no longer recovering between deliveries — it was growing faster than workers could drain it. The timeout on run 5 represents a delivery failure: the ActivityPub inbox job remained queued past the measurement window.

### Key Findings

Federation delivery in Mastodon is not just a network problem — it is a background job scheduling problem. When Instance B is under load, Sidekiq competes with Puma for CPU. The result is non-linear latency degradation: a single spike at light load, sustained elevation at moderate load, and eventual delivery failure at the tail.

This behavior has direct implications for federated system design. A Mastodon instance that is experiencing high user traffic is simultaneously a worse federation participant: it receives ActivityPub payloads more slowly, and its followers on other instances may see delayed or missing posts. This is a form of cascading degradation unique to federated architectures — one instance's load problem becomes another instance's consistency problem.

The t3.large instance (Instance B) with its default Sidekiq configuration was able to absorb light load with only transient delay, but could not sustain reliable delivery under 50 concurrent users. Dedicated Sidekiq worker scaling — separate from web worker scaling — would be the appropriate mitigation.

---

## 3. Experiment 4 — Component Dependency Isolation

### Overview

Having established the web layer as the primary bottleneck and observed Sidekiq starvation through the federation latency experiment, this experiment directly isolates individual components to characterize each one's dependency type and failure mode. Three tests were run sequentially on Instance B (t3.large, WC=4, nginx cache enabled, rate limiting disabled) with Locust at u=20, 2 users/second ramp, 180 second runtime.

The central question is: when a component is removed, does the system fail immediately or degrade gracefully?

---

### Test 1 — Sidekiq Stopped

#### Method

Stopped the Sidekiq container while keeping web, db, and Redis running. Monitored queue depth across all three active queues (default, pull, push) via `redis-cli llen` every 2 seconds. Ran standard Locust profile during the outage.

#### Results

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

#### Observations

Web requests continued to succeed normally — latency actually improved (530ms → 89ms median) because Sidekiq was no longer competing for the t3.large's 2 vCPUs. From Locust's perspective the system appeared healthier than normal.

Meanwhile, 2,680+ jobs silently backed up in Redis with no worker to process them. Federation delivery stopped entirely. Followers never received new posts. Notifications were never sent. Remote timeline updates ceased. All of this was completely invisible to the HTTP layer.

This directly explains the federation latency degradation observed in Experiment 3 — Sidekiq CPU starvation under load produces the same silent queue backup, just more gradually than a full stop.

#### Dependency type: Asynchronous — Silent Degradation

Rails enqueues a job into Redis with a fast in-memory write and immediately returns 200 to the client. It never waits for Sidekiq to process the job. The web layer has no awareness of whether Sidekiq is running. Silent degradation is more dangerous than hard failure in production — Redis failure triggers alerts immediately, but Sidekiq failure might go unnoticed for hours while queues back up to tens of thousands of jobs.

---

### Test 2 — Redis Stopped

#### Method

Restarted Sidekiq and waited for queues to drain. Then stopped the Redis container while keeping web, db, and Sidekiq running. Ran same Locust profile.

#### Results

**Failure rate: 100% immediately.**

Web container error logs:
```
RuntimeError (Temporary failure in name resolution):
  app/models/ip_block.rb:46 IpBlock.blocked_ips_map
  config/initializers/rack_attack.rb:66
```

Every single request failed with a RuntimeError before reaching any application logic.

#### Root Cause

Rack::Attack checks the IP blocklist on every incoming request by calling `IpBlock.blocked_ips_map`, which reads from Redis cache. When Redis is unreachable, this raises a RuntimeError that crashes the entire request at the first middleware layer — before authentication, routing, or any controller logic runs:

```
Request → Rack::Attack middleware → IpBlock.blocked? → Redis lookup → Redis down → RuntimeError → 500
```

#### Dependency type: Synchronous — Immediate Hard Failure

Redis is not merely a performance cache. It is embedded in the synchronous request path at the middleware layer. Every request requires Redis just to pass the IP blocklist check. Additionally Redis serves as session store, timeline cache, Sidekiq queue backend, and rate limit counter store. Losing Redis means losing all of these simultaneously with no fallback path.

---

### Test 3 — Redis Cache Disabled (Force DB Reads)

#### Method

Rather than stopping Redis entirely, the Redis cache namespace was invalidated by adding `REDIS_CACHE_NAMESPACE=invalid_cache` to `.env.production`. This forces every cache lookup to miss and fall through to PostgreSQL, simulating a cold cache scenario while keeping Redis available for sessions and Sidekiq. Verified cache bypass by confirming misses exceeded hits (76 misses vs 64 hits) — a reversal of the normal 84% hit rate. Redis memory dropped from ~17MB to ~5.5MB confirming timeline data was no longer cached.

#### Results

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

#### Observations

**The fast-fail paradox:** Median latency dropped from 530ms to 54ms while failure rate tripled. Requests are failing fast — they attempt a DB query, encounter missing cached data structures, and return a quick failure. This explains why both web CPU (26%) and DB CPU (5.46%) stayed low — failed requests are cheaper than slow successful ones.

**Public timeline stayed at 0% failures** — nginx cache serves it entirely before Rails runs, independent of Redis application cache. HTTP-level caching is more resilient than application-level caching because it survives Redis cache degradation.

**Home timeline collapsed to 67% failure rate** — this endpoint depends on a precomputed per-user feed stored in Redis and maintained by Sidekiq fan-out jobs. Without it, Rails cannot reconstruct the timeline from a simple DB query alone.

**DB was never the bottleneck** — even with cache fully disabled, DB CPU peaked at 5.46% and active connections stayed at 1. Failures were caused by missing Redis data structures, not DB saturation. This confirms that Mastodon's architecture deliberately protects PostgreSQL behind multiple caching layers — DB saturation cannot be reached on a single node because the web CPU ceiling is always hit first.

#### Redis as Data Store, Not Just Cache

Redis serves a dual role. For public timelines it acts as a pure performance cache — a miss can fall back to DB. But for home timelines and notifications, Redis stores precomputed materialized views maintained by Sidekiq fan-out jobs that cannot be reconstructed from DB queries alone:

```
Public timeline:  Redis miss → DB query → reconstructed successfully → 200
Home timeline:    Redis miss → DB query → incomplete fan-out data → failure
```

---

### Test 4 — Sidekiq Under Write-Heavy Load

#### Motivation

The previous three tests characterized failure modes by removing components entirely. This test investigates Sidekiq's behavior under sustained write pressure while all components remain running. Prior read-heavy experiments showed Sidekiq at ~10% CPU with queue depth staying at 0 — because 100% of posts were being rate-limited and never reached Sidekiq. With 10 test accounts now available, posts spread across accounts stay under the per-account posting limit and successfully commit to DB, enqueuing real fan-out and notification jobs.

Two load levels were tested using the `HeavyWriteUser` profile (8:2 write-to-read ratio) to specifically stress the write path.

#### Method

Ran `HeavyWriteUser` at u=20 and u=50 with 10 rotating test accounts. Monitored queue depth via `redis-cli llen queue:default` and `queue:push` every 2 seconds alongside `docker stats`.

#### Results

| Metric | Read-heavy u=20 | HeavyWrite u=20 | HeavyWrite u=50 |
|---|---|---|---|
| RPS | 9.2 | 15.9 | 21.7 |
| Post failure rate | 100%* | 30% | 48% |
| Post median latency | 530ms | 150ms | 1200ms |
| Notification median | 530ms | 360ms | 2100ms |
| Web CPU | 161% | 145% | 108% |
| Sidekiq CPU | ~10% | 34% | 37% |
| DB CPU | ~16% | 18% | 23% |
| Redis CPU | ~2% | 8.92% | 5.23% |
| Queue depth | 0 | 0 | ~4 (growing) |

*all posts were per-account rate limited in read-heavy runs with only 3 accounts

#### Observations

**u=20 HeavyWrite:** Sidekiq climbed to 34% CPU and Redis to 8.92% — the highest activity seen on both components across all experiments. Queue depth stayed at 0, meaning Sidekiq processed jobs as fast as they arrived. All downstream components were meaningfully active for the first time.

**u=50 HeavyWrite:** Queue depth climbed to ~4 and stayed there — Sidekiq is no longer keeping up with job intake. This is the first observed Sidekiq bottleneck threshold on this instance. Notification median latency spiked to 2100ms as Sidekiq prioritized fan-out jobs over notification delivery. DB CPU reached 23% — the highest under real load — because write-heavy traffic bypasses the Redis cache entirely, every post requiring a direct DB write.

Web CPU paradoxically dropped to 108% at u=50 despite more users — because HeavyWriteUser issues fewer read requests per user, reducing the Rails processing and cache lookup overhead that normally drives web CPU up.

#### Connection to Federation Findings

This result directly validates the federation latency experiment (Experiment 3). At u=50 HeavyWrite, Sidekiq queue depth growing to ~4 with notification latency at 2100ms is the same CPU starvation mechanism that caused federation delivery to spike to 28.73s under 20-user load and time out entirely under 50-user load. Write pressure and concurrent web load both compete for the same 2 vCPUs, causing Sidekiq to fall behind — whether the symptom is measured as queue depth, notification latency, or cross-instance delivery time.

#### Dependency type: Resource Contention Bottleneck

Unlike the hard failure (Redis) or silent degradation (Sidekiq stopped) patterns, this is a **gradual performance degradation** under sustained write load. The system stays up, requests succeed, but background job processing slows and eventually backs up. On a properly resourced deployment with Sidekiq on dedicated infrastructure, this contention would not exist.

---

### Component Dependency Summary

| | Sidekiq stopped | Redis stopped | Cache disabled | Write-heavy load |
|---|---|---|---|---|
| Dependency type | Asynchronous | Synchronous | Synchronous (partial) | Resource contention |
| Failure mode | Silent degradation | Immediate hard failure | Fast-fail on personalized endpoints | Gradual degradation |
| HTTP requests | Still succeed | 100% fail | Public ok, personalized fail | Succeed, latency climbs |
| Latency effect | Improves (less CPU contention) | N/A | Drops (fast failures) | Climbs steadily |
| Visible to monitoring | No — needs queue depth alerting | Yes — error rate spikes immediately | Partially — failure rate rises | Partially — queue depth + latency |
| User experience | Posts accepted, nothing delivers | Cannot load any page | Public timeline works, home feed broken | Everything works, notifications slow |
| Detection difficulty | High | Low | Medium | Medium |

---

## 4. Complete Experiment Summary

| Experiment | Instance | Key Finding |
|---|---|---|
| 1A — anonymous read bottleneck | A (t3.medium) | Zero failures to 500 users; latency degrades sharply above 200 users; web layer is first bottleneck |
| 1B — authenticated load + rate limiter | B (t3.large) | rack-attack activates at 20 users before hardware saturation; Sidekiq starved at 50 users |
| 2A — bottleneck shifting | B (t3.large) | WC=4 eliminates failures; WC=6 overshoots; nginx cache gives 5× public timeline improvement |
| 2B — bottleneck shifting | A (t3.medium) | WC=4 causes 502 errors; t3.medium cannot absorb additional workers under load |
| 3A — federation validation | A ↔ B | All four ActivityPub checks passed; HTTPS + Nginx required for WebFinger discovery |
| 3B — federation latency under load | A → B | Idle: 0.67s avg; light load: 6.53s avg with 28.73s spike; moderate load: 4.32s avg with 1 timeout |
| 4 — component dependency isolation | B (t3.large) | Sidekiq: silent degradation; Redis: immediate hard failure; Cache disabled: personalized endpoints break; Write-heavy u=50: Sidekiq queue backs up, notification latency 2100ms |

---

## 5. Discussion

### Bottleneck progression

Across all experiments, the bottleneck in Mastodon follows a consistent pattern. The web layer saturates first, either through rate limiting or Puma worker exhaustion. The database is never the bottleneck in our experiments — PostgreSQL active connections stayed at 2–3 throughout all steps, with Redis absorbing 84% of reads. Sidekiq becomes a bottleneck only indirectly, through CPU contention with web workers rather than through queue depth alone.

### Deliberate DB protection

Mastodon's architecture is designed to protect PostgreSQL from direct load. Every layer above DB exists partly to absorb traffic before it reaches the relational store:

```
Request
   ↓
Nginx cache       ← serves public content, never hits Rails
   ↓
Rack::Attack      ← blocks abusive traffic before any DB touch
   ↓
Redis cache       ← absorbs 84% of reads
   ↓
PostgreSQL        ← sees only ~16% of traffic, mostly writes
```

This design treats PostgreSQL as a precious resource to be protected rather than a workhorse to be scaled. The consequence observed across all experiments is that DB saturation cannot be reached on a single node — the web CPU ceiling is always hit first.

### Instance size as a binding constraint

The vertical scaling comparison between t3.medium and t3.large is one of the clearest results in the project. The same configuration change — WEB_CONCURRENCY=4 — eliminated all failures on t3.large and introduced new 502 errors on t3.medium. Worker tuning is not universally beneficial: it is a function of available hardware resources.

### Federation and eventual consistency

The federation latency experiment and the component dependency experiment together reveal a coupling unique to federated architectures. Sidekiq starvation under load (Experiment 3) and Sidekiq being fully stopped (Experiment 4) produce the same outcome through different mechanisms — queue backup, delayed delivery, and eventual federation failure. A loaded instance is simultaneously a degraded federation participant, meaning one instance's local performance problem becomes another instance's consistency problem. Mastodon effectively chooses availability over consistency: a post will eventually be delivered, but there is no guarantee of when.

### Deployment constraints as a distributed systems lesson

Our pivot from CloudFormation / ECS to EC2 + Docker Compose was not merely a logistical workaround. It became a lesson in how deployment constraints shape system behavior. The IAM restrictions in AWS Academy Learner Lab blocked ECS task roles entirely. This forced us to build a simpler but more transparent deployment, which turned out to be better suited for observability and experiment control.

---

## 6. What Remains

- **Final report** — integrate all results into the complete written submission
- **Presentation** — Apr 13 or April 20
- **Possible extension** — if time allows, a partial-outage test: take Instance A offline briefly and observe whether federation delivery recovers after restart

---

## 7. Updated Timeline

| Date | Task |
|------|------|
| Apr 9 | Experiment 2 complete on both instances ✅ |
| Apr 10 | Federation latency test complete ✅ |
| Apr 11–12 | Component dependency isolation complete ✅ |
| Apr 11–12 | Final report draft |
| Apr 12 | Rehearsal |
| Apr 13 | Presentation |
| Apr 14–20 | Final submission |