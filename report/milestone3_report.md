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
- Results and graphs document updated with Experiment 3B section
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

## 3. Complete Experiment Summary

| Experiment | Instance | Key Finding |
|---|---|---|
| 1A — anonymous read bottleneck | A (t3.medium) | Zero failures to 500 users; latency degrades sharply above 200 users; web layer is first bottleneck |
| 1B — authenticated load + rate limiter | B (t3.large) | rack-attack activates at 20 users before hardware saturation; Sidekiq starved at 50 users |
| 2A — bottleneck shifting | B (t3.large) | WC=4 eliminates failures; WC=6 overshoots; nginx cache gives 5× public timeline improvement |
| 2B — bottleneck shifting | A (t3.medium) | WC=4 causes 502 errors; t3.medium cannot absorb additional workers under load |
| 3A — federation validation | A ↔ B | All four ActivityPub checks passed; HTTPS + Nginx required for WebFinger discovery |
| 3B — federation latency under load | A → B | Idle: 0.67s avg; light load: 6.53s avg with 28.73s spike; moderate load: 4.32s avg with 1 timeout |

---

## 4. Discussion

### Bottleneck progression

Across all experiments, the bottleneck in Mastodon follows a consistent pattern. The web layer saturates first, either through rate limiting or Puma worker exhaustion. The database is never the bottleneck in our experiments — PostgreSQL active connections stayed at 2–3 throughout all steps, with Redis absorbing 84% of reads. Sidekiq becomes a bottleneck only indirectly, through CPU contention with web workers rather than through queue depth alone.

### Instance size as a binding constraint

The vertical scaling comparison between t3.medium and t3.large is one of the clearest results in the project. The same configuration change — WEB_CONCURRENCY=4 — eliminated all failures on t3.large and introduced new 502 errors on t3.medium. This shows that worker tuning is not universally beneficial: it is a function of available hardware resources. Tuning recommendations that work for a well-provisioned instance can actively harm a smaller one.

### Federation and eventual consistency

The federation latency experiment adds a distributed systems dimension that goes beyond single-instance performance. ActivityPub delivery is eventually consistent by design: posts propagate to remote instances asynchronously, and delivery time depends on background job scheduling on the receiving end. Under load, this eventual consistency becomes more eventual. A loaded instance is simultaneously a degraded federation participant, creating a coupling between local performance and cross-instance reliability that is absent in centralized architectures.

This connects directly to course themes around CAP tradeoffs and asynchronous systems. Mastodon effectively chooses availability and partition tolerance over consistency: a post will eventually be delivered, but there is no guarantee of when, and under sufficient load the delivery may fail entirely.

### Deployment constraints as a distributed systems lesson

Our pivot from CloudFormation / ECS to EC2 + Docker Compose was not merely a logistical workaround. It became a lesson in how deployment constraints shape system behavior. The IAM restrictions in AWS Academy Learner Lab blocked ECS task roles, which blocked the production-style deployment path entirely. This forced us to build a simpler but more transparent deployment, which turned out to be better suited for observability and experiment control.

---

## 5. What Remains

- **Final report** — integrate all results into the complete written submission
- **Presentation** — Apr 13 or April 20
- **Possible extension** — if time allows, a partial-outage test: take Instance A offline briefly and observe whether federation delivery recovers after restart

---

## 6. Updated Timeline

| Date | Task |
|------|------|
| Apr 9 | Experiment 2 complete on both instances ✅ |
| Apr 10 | Federation latency test complete ✅ |
| Apr 11–12 | Final report draft |
| Apr 12 | Rehearsal |
| Apr 13 | Presentation |
| Apr 14–20 | Final submission |