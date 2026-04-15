# Milestone 3 Report
## Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## 1. Progress Since Milestone 2

At Milestone 2, both instances had completed the bottleneck-shifting experiments and a basic federation validation. The one remaining experiment was federation propagation latency under load. Since Milestone 2, we have completed that experiment and finalized all data collection.

Completed since Milestone 2:
- Federation propagation latency test under idle, light load (20 users), and moderate load (50 users) conditions
- Extended federation test: Puma tuning, Locust verification, PostgreSQL connection investigation, and direct Sidekiq stress test
- Full `federation_latency.csv` dataset collected
- Component dependency isolation experiments (Sidekiq stopped, Redis stopped, Redis cache disabled)
- Results and graphs document updated with Experiment 3B, Experiment 3C, and Experiment 4 sections
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

## 3. Experiment 3C — Extended Federation Stress Test (Instance A Under Load)

### Motivation

Experiment 3B measured federation latency by loading the **receiving** instance (Instance B). This extended experiment reverses the direction: load is applied to the **sending** instance (Instance A) using a combined test script that starts Locust in the background and measures federation propagation at each load stage. The goal is to understand whether the sending instance's ability to deliver ActivityPub payloads degrades under increasing concurrent user load, and to identify which component — Puma, Sidekiq, or PostgreSQL — is the binding constraint.

### Setup

- **Instance A** (`mastodon-yehe.click`, t2.large, 2 vCPU, 8GB RAM): both the posting instance and the Locust target
- **Instance B** (`a.mastodon-yaoyi.online`): the observer, polled for post arrival
- **Tool:** `locust/combined_fed_test.py` with background Locust process
- **Locust profile:** `MastodonUser` (mixed read/write workload: 5 home timeline, 3 public timeline, 2 notifications, 1 post, 1 favourite, 1 search — weights out of 13)
- **Puma config:** WEB_CONCURRENCY=4, MAX_THREADS=5 (baseline), later tuned to MAX_THREADS=10
- **Timeout:** 60 seconds per run (later increased to 30 seconds on HTTP request timeout)
- **Runs per condition:** 5

### Phase 1 — Initial Test (Locust Silently Failing)

The first series of runs appeared successful with flat latency across all stages:

| Stage | Users | Success | Avg Latency | Min | Max |
|---|---|---|---|---|---|
| idle | 0 | 5/5 | 0.76s | 0.28s | 1.07s |
| light | 20 | 5/5 | 1.13s | 1.07s | 1.22s |
| moderate | 50 | 5/5 | 1.12s | 1.02s | 1.31s |
| heavy | 100 | 5/5 | 0.95s | 0.45s | 1.13s |

However, investigation revealed that **Locust was not actually running during any of these tests.** The combined script invoked Locust via `sys.executable -m locust`, but the `locust` package was not installed in the base conda environment. With both stdout and stderr redirected to `/dev/null`, the crash was completely silent. No `locust_*users_stats.csv` files were produced.

**Lesson learned:** Always verify background processes are alive. The fix was twofold: (1) invoke `locust` directly instead of `python -m locust`, and (2) redirect Locust output to log files instead of `/dev/null` to surface errors.

### Phase 2 — Locust Running, Timeouts at 150+ Users

After fixing the Locust invocation, the test was re-run with load stages up to 200 users. Results at 150 and 200 users timed out:

```
STAGE: SEMI-HEAVY (150 users)
→ ERROR: HTTPSConnectionPool(host='mastodon-yehe.click', port=443):
  Read timed out. (read timeout=10)
```

The error was not a federation timeout — it was the test script's own `POST /api/v1/statuses` request failing to reach Puma within 10 seconds. With 20 Puma threads (WEB_CONCURRENCY=4, MAX_THREADS=5) handling 150 concurrent Locust users, all threads were occupied, and the federation test script's HTTP request queued behind Locust traffic in the TCP backlog.

**Tuning attempt:** Increased MAX_THREADS from 5 to 10, giving 40 Puma threads. Result: same timeout at 150 users. The t2.large's 2 vCPUs could not context-switch fast enough to serve 40 threads under heavy load.

**Workaround:** Increased the federation test script's HTTP request timeout from 10s to 30s. This allowed the POST request to wait in Puma's queue long enough for a thread to free up.

### Phase 3 — Federation Latency Under Verified Load

With the increased timeout, all stages completed successfully:

| Stage | Users | Success | Avg Latency | Min | Max |
|---|---|---|---|---|---|
| heavy | 100 | 5/5 | 0.28s | 0.25s | 0.37s |
| semi-heavy | 150 | 5/5 | 0.30s | 0.27s | 0.41s |
| super-heavy | 200 | 5/5 | 0.29s | 0.26s | 0.38s |

Federation latency remained flat at ~0.3s across all load stages. The Sidekiq dashboard confirmed 0 enqueued jobs throughout all tests.

**Locust stats at 200 users** revealed where the actual stress was occurring:

| Endpoint | Requests | Failures | Median Latency |
|---|---|---|---|
| GET /timelines/public | 295 | 0 | 95ms |
| GET /timelines/home | 507 | 0 | 9,700ms |
| GET /notifications | 178 | 0 | 12,000ms |
| POST /statuses | 355 | 355 (100%) | 7,700ms |
| GET /search | 86 | 0 | 7,600ms |

All authenticated endpoints experienced multi-second latencies. POST /statuses had a **100% failure rate** — every Locust write request failed. Since Locust writes never succeeded, they never generated Sidekiq federation jobs. The Sidekiq queue stayed at 0 not because federation was resilient, but because no federation work was being created.

### Phase 4 — PostgreSQL Connection Exhaustion

After the 200-user test, attempting to open a Rails console on the server produced:

```
FATAL: sorry, too many clients already
```

PostgreSQL had exhausted its `max_connections` limit. Checking connection count after a restart showed the baseline was only 7 connections (Puma + Sidekiq), confirming that the 200-user test had leaked connections that were never released after failed requests.

This revealed the actual bottleneck chain during high-load tests:

1. **Locust floods Puma** with 200 concurrent users
2. **Puma threads grab PostgreSQL connections** for each request
3. **Failed or slow requests hold connections** without releasing them cleanly
4. **PostgreSQL hits max_connections** (~100 default)
5. **New requests cannot get a database connection** → cascade failure
6. **Connections leak** — even after the test ends, connections remain held

The bottleneck was not Puma thread count alone — it was PostgreSQL connection exhaustion caused by connection leaking under sustained overload.

### Phase 5 — Direct Sidekiq Stress Test via Rails Console

To bypass the Puma bottleneck entirely and stress-test the federation delivery pipeline directly, 500 posts were created via the Rails console:

```ruby
account = Account.find_local('testuser1')
500.times do |i|
  PostStatusService.new.call(account, text: "flood #{i} #{Time.now.to_i}")
end
```

This bypassed Puma and injected federation delivery jobs directly into Sidekiq. Results:

- PostgreSQL connections jumped from 7 to 81
- Sidekiq processed all jobs with **0 enqueued** at any point — queue depth never exceeded 0
- `ActivityPub::DistributionWorker` average execution time: 0.08 seconds
- Sidekiq dashboard showed 1 Busy, 0 Enqueued throughout the flood

Even with 500 rapid-fire posts generating federation delivery jobs, Sidekiq processed them faster than they arrived. With ~5 Sidekiq threads at 0.08s per job, throughput was approximately 60 jobs/second — far exceeding the arrival rate.

### Analysis

This extended experiment reveals a layered bottleneck architecture where each component can only become the bottleneck once the layer above it is scaled past its limit:

```
Layer 1: Puma (HTTP entry point)
  → Saturates first: all requests must pass through Puma
  → At 150+ users on t2.large, TCP queue backs up

Layer 2: PostgreSQL connections
  → Saturates second: each Puma thread holds a DB connection
  → Under sustained overload, connections leak and exhaust max_connections
  → Even after load stops, leaked connections persist until restart

Layer 3: Sidekiq (async federation delivery)
  → Never reached saturation in any test
  → Processes jobs at ~60/second, far exceeding arrival rates
  → Queue depth remained at 0 even under direct flooding via Rails console
```

The key insight is that **Sidekiq federation delivery cannot be stressed through normal HTTP traffic on a single-node deployment**, because Puma and PostgreSQL will always fail first. Locust writes fail at the HTTP layer, so they never create Sidekiq jobs. This creates a paradox: the system appears to have resilient federation, but only because the bottleneck upstream prevents enough work from reaching the federation layer.

### Comparison with Experiment 3B

Experiment 3B (loading the receiving instance) and Experiment 3C (loading the sending instance) stress different parts of the federation pipeline and produce different results:

| | 3B (Receiver Under Load) | 3C (Sender Under Load) |
|---|---|---|
| Load target | Instance B (receiver) | Instance A (sender) |
| Federation latency | Degraded to 6.53s avg, timeouts at 50 users | Flat at ~0.3s up to 200 users |
| Sidekiq queue | Backed up under load | Never backed up |
| Primary bottleneck | CPU contention between Puma and Sidekiq | Puma thread saturation → PostgreSQL connection exhaustion |
| Failure mode | Gradual degradation | Cliff — works until Puma queue overflows |

The asymmetry is explained by what happens after the post is created. On the **sending** side, creating the post is a single Puma request followed by a fast Sidekiq job. On the **receiving** side, the incoming ActivityPub delivery must be processed by Sidekiq, which competes with Puma for CPU. When the receiver is under load, Sidekiq is starved; when the sender is under load, Sidekiq is unaffected because the bottleneck is upstream at Puma.

### Implications for Production Federation

These findings have direct implications for how federated Mastodon instances should be scaled:

1. **Puma is always the first bottleneck** on a single-node deployment. Scaling federation delivery (more Sidekiq threads) is ineffective unless Puma can handle enough requests to generate federation work.

2. **PostgreSQL connection management is critical under sustained load.** Connection leaking under overload is a failure mode that persists after the load subsides, requiring a restart to recover. Connection pooling (e.g., PgBouncer) would mitigate this.

3. **Sidekiq federation delivery is inherently resilient** — on the sending side, each delivery job is fast (~0.08s) and the queue never backs up even under direct flooding. The federation degradation observed in Experiment 3B is a receiving-side problem, not a sending-side problem.

4. **Scaling the sending instance requires scaling Puma horizontally** (more workers, more instances behind a load balancer) so that write requests succeed and generate federation jobs. Scaling Sidekiq on the sender provides no benefit until Puma is no longer the bottleneck.

5. **Scaling the receiving instance requires separating Sidekiq from Puma** onto dedicated infrastructure so that incoming federation deliveries are not starved by local web traffic.

---

## 4. Experiment 4 — Component Dependency Isolation

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

## 5. Complete Experiment Summary

| Experiment | Instance | Key Finding |
|---|---|---|
| 1A — anonymous read bottleneck | A (t3.medium) | Zero failures to 500 users; latency degrades sharply above 200 users; web layer is first bottleneck |
| 1B — authenticated load + rate limiter | B (t3.large) | rack-attack activates at 20 users before hardware saturation; Sidekiq starved at 50 users |
| 2A — bottleneck shifting | B (t3.large) | WC=4 eliminates failures; WC=6 overshoots; nginx cache gives 5× public timeline improvement |
| 2B — bottleneck shifting | A (t3.medium) | WC=4 causes 502 errors; t3.medium cannot absorb additional workers under load |
| 3A — federation validation | A ↔ B | All four ActivityPub checks passed; HTTPS + Nginx required for WebFinger discovery |
| 3B — federation latency under load (receiver) | A → B | Idle: 0.67s avg; light load: 6.53s avg with 28.73s spike; moderate load: 4.32s avg with 1 timeout |
| 3C — federation latency under load (sender) | A ← B | Federation latency flat at ~0.3s up to 200 users; Puma and PostgreSQL connections are the bottleneck, not Sidekiq; direct Sidekiq flooding via Rails console shows 0 queue depth |
| 4 — component dependency isolation | B (t3.large) | Sidekiq: silent degradation; Redis: immediate hard failure; Cache disabled: personalized endpoints break; Write-heavy u=50: Sidekiq queue backs up, notification latency 2100ms |

---

## 6. Discussion

### Bottleneck progression

Across all experiments, the bottleneck in Mastodon follows a consistent layered pattern. The web layer (Puma) saturates first, either through rate limiting or thread exhaustion. PostgreSQL connection exhaustion emerges as a secondary bottleneck under sustained overload, with leaked connections persisting even after load subsides. Sidekiq becomes a bottleneck only in two scenarios: (1) indirectly through CPU contention with web workers on the receiving instance (Experiment 3B), or (2) under sustained write-heavy load (Experiment 4, Test 4). On the sending side, Sidekiq federation delivery never saturated in any test — including direct flooding of 500 posts via Rails console.

The bottleneck progression on a single-node deployment follows a strict ordering:

```
Puma thread saturation
  ↓ (scale Puma)
PostgreSQL connection exhaustion
  ↓ (add connection pooling, increase max_connections)
Sidekiq CPU starvation (receiving instance)
  ↓ (separate Sidekiq onto dedicated infrastructure)
Sidekiq queue depth growth (sending instance)
  ↓ (add Sidekiq workers)
PostgreSQL write throughput
```

Each layer can only become the bottleneck once the layer above it has been scaled past its limit.

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

This design treats PostgreSQL as a precious resource to be protected rather than a workhorse to be scaled. The consequence observed across all experiments is that DB saturation cannot be reached on a single node — the web CPU ceiling is always hit first. The one exception is connection exhaustion under sustained overload (Experiment 3C, Phase 4), which is a connection management failure rather than a throughput failure.

### Instance size as a binding constraint

The vertical scaling comparison between t3.medium and t3.large is one of the clearest results in the project. The same configuration change — WEB_CONCURRENCY=4 — eliminated all failures on t3.large and introduced new 502 errors on t3.medium. Worker tuning is not universally beneficial: it is a function of available hardware resources. The extended federation test (Experiment 3C) further demonstrated this: on a t2.large with 2 vCPUs, increasing MAX_THREADS from 5 to 10 (20 to 40 Puma threads) provided no benefit because the CPU could not context-switch fast enough to serve them.

### Federation and eventual consistency

The federation latency experiments (3B and 3C) together reveal an asymmetry in how load affects federation. Loading the **receiving** instance degrades federation delivery through Sidekiq CPU starvation — latency spikes and eventually times out. Loading the **sending** instance does not degrade federation delivery at all — latency remains flat because the bottleneck is upstream at Puma, and Sidekiq on the sender processes delivery jobs in ~0.08s each.

This asymmetry has practical implications: in a federated network, the instance that is under the most user load is also the worst federation participant as a **receiver**, but remains a reliable federation participant as a **sender**. A popular instance that is struggling under its own traffic will still deliver posts outward efficiently, but will receive posts from other instances with increasing delay. This is a form of cascading degradation unique to federated architectures — one instance's local performance problem becomes another instance's consistency problem, but only in one direction.

Mastodon effectively chooses availability over consistency: a post will eventually be delivered, but there is no guarantee of when.

### PostgreSQL connection leaking as a hidden failure mode

Experiment 3C revealed that sustained HTTP overload causes PostgreSQL connections to leak — they are acquired by Puma threads for requests that fail or hang, but are never released. After a 200-user Locust run, the connection count remained at max even after the test ended, requiring a container restart to recover. This is a failure mode that would not be visible in standard monitoring (the web layer would show errors, but the root cause — connection pool exhaustion — would be obscured). In production, connection pooling middleware such as PgBouncer would mitigate this by managing connections independently of Puma's request lifecycle.

### Deployment constraints as a distributed systems lesson

Our pivot from CloudFormation / ECS to EC2 + Docker Compose was not merely a logistical workaround. It became a lesson in how deployment constraints shape system behavior. The IAM restrictions in AWS Academy Learner Lab blocked ECS task roles entirely. This forced us to build a simpler but more transparent deployment, which turned out to be better suited for observability and experiment control.

---

## 7. What Remains

- **Final report** — integrate all results into the complete written submission
- **Presentation** — Apr 13 or April 20
- **Possible extension** — if time allows, a partial-outage test: take Instance A offline briefly and observe whether federation delivery recovers after restart

---

## 8. Updated Timeline

| Date | Task |
|------|------|
| Apr 9 | Experiment 2 complete on both instances ✅ |
| Apr 10 | Federation latency test complete ✅ |
| Apr 11–12 | Component dependency isolation complete ✅ |
| Apr 13–14 | Extended federation stress test (Experiment 3C) complete ✅ |
| Apr 14–20 | Final report and submission |