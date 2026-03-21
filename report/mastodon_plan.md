# CS6650 Final Project Plan
## Scaling a Decentralized Social Network: Stress-Testing Mastodon's Distributed Architecture
**Team:** Yaoyi Wang & Yehe Yan
**Presentation:** Apr 13 / 20
**Final Deadline:** Apr 20

---

## 1. Project Goal

This project studies how a federated social network behaves under load by using Mastodon as a real-world case study.
We aim to deploy Mastodon on AWS, generate traffic with Locust, and analyze system behavior under increasing load and limited horizontal scaling.

Our project focuses on three questions:

1. **Single-instance bottleneck** — which component becomes the bottleneck first under load?
2. **Horizontal scaling** — how much performance improves when increasing ECS task count?
3. **Federation under load** *(nice-to-have)* — how long cross-instance propagation takes under different load levels?

---

## 2. Success Criteria

### Must-have
- One stable Mastodon deployment path in AWS Academy Learner Lab
- At least one working Mastodon instance on AWS
- Valid Locust smoke test
- Single-instance bottleneck experiment with data
- Basic horizontal scaling comparison
- At least 2–3 result graphs for the presentation

### Nice-to-have
- Both team members successfully deploy their own Mastodon instances
- Basic federation propagation experiment (5–10 runs across 2–3 load levels)

### Stretch
- Bulk follower fan-out measurement
- Retry analysis
- Queue / worker tuning analysis

---

## 3. Go / No-Go Checkpoints

**Checkpoint 1 — Mar 22**
If we do not have at least one reliable deployment path by Mar 22, we stop planning around full dual-instance execution and focus on:
- one working instance
- bottleneck analysis
- limited scaling study

**Checkpoint 2 — Mar 30**
If the second instance or federation path is still unstable by Mar 30, federation will be reduced to:
- architecture discussion
- expected propagation path
- future work section

---

## 4. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Learner Lab IAM blocks part of CloudFormation | Deployment delay | Keep modified template, document failed resources, simplify stack |
| Route 53 / ACM / DNS flow unavailable | Public access / HTTPS blocked | Use external domain provider or temporary workaround |
| S3 / CloudFront stack fails | Static/media path affected | Simplify or defer non-critical media/CDN setup |
| ECS exec unavailable | Admin setup delayed | Use alternate bootstrap or manual setup path |
| Second instance unstable | Federation slips | Reduce federation to optional / future work |
| 4-hour lab timeout | Interrupts experiments | Save configs, stop/restart resources, prioritize short runs |

---

## 5. AWS Academy Learner Lab Constraints

| Constraint | Notes |
|-----------|-------|
| Session timeout | Each session expires after about 4 hours |
| Region restrictions | Only `us-east-1` or `us-west-2` available |
| IAM restrictions | Limited permissions; some CloudFormation resources may fail |
| Budget cap | Limited credits per account |
| Resource recovery | Some resources may need manual restart after timeout |

### Operational habits
- Use one agreed region consistently (`us-east-1` unless blocked)
- Stop non-essential resources after each session
- Save deployment outputs, stack events, and screenshots after every major step
- Expect to restart or recover resources after session timeout

---

## 6. Deployment Strategy

Our deployment is **based on** the `widdix/mastodon-on-aws` project, but we are **not using the original template as-is**.

Instead, we are testing a modified CloudFormation template:

- `quickstart-no-ses.yml`

This custom template removes the SES dependency for Learner Lab compatibility.
However, DNS, ACM certificate validation, S3, and CloudFront-related resources may still require additional workarounds or simplification.

### Current plan
- Both teammates attempt to deploy one Mastodon instance in their own AWS Learner Lab account
- Each person works in their own branch first
- `main` keeps shared structure, scripts, and documentation
- Federation is attempted later only if both instances become stable

---

## 7. Team Responsibilities

| Area | Owner | Instance | Main Focus |
|------|-------|----------|------------|
| Traffic / access layer | Yaoyi | Instance A | ALB + ECS scaling, CloudWatch dashboard, scaling experiment |
| Data / messaging layer | Yehe | Instance B | RDS / Redis observations, bottleneck analysis, Sidekiq tuning |
| Federation experiment | Shared | A + B | Cross-instance propagation and latency |
| Shared repo structure / scripts | Shared | - | Locust scripts, result format, report integration |

---

## 8. Metrics

### Tier 1 (must-have)
- Request latency (P50 / P95 / P99)
- Throughput (RPS)
- Error rate
- ECS CPU / memory utilization
- ECS task count
- ALB response time
- RDS CPU / connections

### Tier 2 (best effort)
- Redis queue depth
- Sidekiq retries
- Cache hit rate
- Worker-specific processing time

---

## 9. Repository Structure

```text
mastodon-scaling-study/
├── README.md
├── quickstart-no-ses.yml
├── locust/
│   ├── locustfile.py
│   └── federation_test.py
├── infra/
│   └── cloudwatch-dashboard.json
├── results/
│   ├── yaoyi/
│   └── yehe/
└── report/
    └── mastodon_plan.md
```

---

## 	10. Mastodon Architecture Overview
```text
Client Request
   ↓
ALB
   ↓
Web (Ruby on Rails / Puma)  ←→  Redis (queue + cache)
   ↓                                ↓
PostgreSQL                    Sidekiq workers
                                    ↓
                           Federation HTTP POST → Remote Instance
```

**Federation path**
1. A user on Instance A posts a status
2. Sidekiq creates an ActivityPub::DeliveryWorker job
3. Instance A sends an HTTP POST to Instance B’s /inbox
4. Instance B processes the activity through Sidekiq
5. The post appears in Instance B’s timeline

---

## 	11. Week 1 (Mar 20–23): Deployment Validation + Smoke Test Preparation

**Primary objective**

Validate a workable deployment path for Mastodon in AWS Learner Lab while both teammates attempt their own instance deployment.

**Current assumption**

We are using quickstart-no-ses.yml as the primary template.
It removes SES dependency, but Route 53, certificate, S3, and CloudFront compatibility may still require adjustments.

**Shared tasks**
- Review quickstart-no-ses.yml
- Identify which resources are still inherited from the original stack
- Record failed resources in Learner Lab, if any
- Decide whether DNS is handled through Route 53 or externally
- Agree on one result format for reporting metrics
- Confirm which deployment steps are shared vs instance-specific

**Generate Mastodon secrets**
```bash
docker run --rm -it ghcr.io/mastodon/mastodon:latest bin/rails secret
docker run --rm -it ghcr.io/mastodon/mastodon:latest bin/rails secret
docker run --rm -it ghcr.io/mastodon/mastodon:latest bin/rails mastodon:webpush:generate_vapid_key
```
Also collect:
- ACTIVE_RECORD_ENCRYPTION_DETERMINISTIC_KEY
- ACTIVE_RECORD_ENCRYPTION_KEY_DERIVATION_SALT
- ACTIVE_RECORD_ENCRYPTION_PRIMARY_KEY

**Deployment attempt**
- Launch stack using quickstart-no-ses.yml
- Save CloudFormation stack events and screenshots
- Record exact failing resource names if deployment does not complete

**Smoke-test readiness checklist**
- Domain / HTTPS endpoint reachable
- Mastodon web UI loads
- Login / registration flow understood
- Admin creation path confirmed
- CloudWatch basic metrics visible

**Yaoyi**
- Deploy Instance A in personal Learner Lab account
- Prepare CloudWatch dashboard for Tier 1 metrics
- Define experiment result format
- Prepare Locust smoke-test workflow
- Document ALB / ECS / task-count observations

**Yehe**
- Deploy Instance B in personal Learner Lab account
- Continue template adaptation if deployment fails
- Document Learner Lab blockers and workarounds
- Prepare backend-side observation checklist
- Explore Sidekiq / Redis / DB-related bottleneck indicators

**Week 1 deliverables**
- Updated project plan
- Updated README
- Deployment status summary
- At least one confirmed next-step deployment path
- Smoke-test checklist ready

---

## 12. Week 2 (Mar 24–30): Core Experiments
**Yaoyi — Experiment 2: Horizontal Scaling**

Goal: evaluate how throughput and latency change with more web tasks.

Example load steps:
```bash
for users in 50 100 200 300; do
  locust -f locustfile.py --host https://<instance-a-endpoint> \
    --users $users --spawn-rate 10 --run-time 10m --headless \
    --csv=results/yaoyi/exp2_${users}users
  sleep 60
done
```

Tasks:
- Compare 1 / 2 / 4 web tasks
- Enable or simulate ECS scaling if feasible
- Observe scaling trigger timing and performance effects
- Record RPS, P95/P99 latency, error rate, and task count

**Yehe — Experiment 1: Single-Instance Bottleneck**

Goal: identify which subsystem becomes the bottleneck first.

Example load steps:
```bash
for users in 50 100 200 300 500; do
  locust -f locustfile.py --host https://<instance-b-endpoint> \
    --users $users --spawn-rate 10 --run-time 10m --headless \
    --csv=results/yehe/exp1_${users}users
  sleep 60
done
```

Bottleneck signals:
| Component | Signal | Interpretation |
| :--- | :--- | :--- |
| Web | ECS CPU > 80% | Web tier saturation |
| PostgreSQL | RDS connections / CPU spike | DB pressure |
| Sidekiq | Queue depth grows continuously | Worker backlog |
| ALB | 5xx errors increase | Application overload |

Optional tuning:
- test SIDEKIQ_CONCURRENCY
- compare worker behavior under higher load
- observe whether queue processing improves or DB contention worsens

Shared Week 2 outputs
- Push experiment data to individual branches
- Merge stable scripts / docs into main
- Start report draft for Experiment 1 and Experiment 2

---

## 13. Week 3 (Mar 31–Apr 6): Federation Experiment (Conditional)
**Condition**: only proceed if both instances are stable enough by Checkpoint 2.

**Goal**

Measure propagation latency across two Mastodon instances under:
- idle
- light load
- moderate load

**Preparation**
- Create accounts on both instances
- Make Instance B follow a user on Instance A
- Confirm federation works functionally before measuring latency

**Measurement idea**
- post on Instance A
- poll timeline on Instance B
- measure delay until the status appears

Example:
```python
import time, requests

def measure_propagation(token_a, token_b, run_id):
    t0 = time.time()
    resp = requests.post(
        "https://<instance-a-endpoint>/api/v1/statuses",
        json={"status": f"Federation test run {run_id} t={t0}"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    uri = resp.json()["uri"]

    while True:
        timeline = requests.get(
            "https://<instance-b-endpoint>/api/v1/timelines/home",
            headers={"Authorization": f"Bearer {token_b}"}
        ).json()
        if any(uri in p.get("uri", "") for p in timeline):
            return time.time() - t0
        time.sleep(0.5)
```

**Runs**
- Idle: 5–10 runs
- Light load: 5–10 runs
- Moderate load: 5–10 runs

If federation is still unstable, this section becomes:
- architecture explanation
- expected delay path
- future work

---

## 14. Final Week: Analysis, Report, Presentation
### Project Timeline

| Date Range | Task |
| :--- | :--- |
| Apr 4–5 | Finish data collection and tear down AWS resources |
| Apr 6–8 | Complete report draft and merge stable work into main |
| Apr 9–11 | Create slides with at least 2–3 result figures |
| Apr 12 | Rehearsal |
| Apr 13 / 20 | Presentation / final submission window |

### Planned report structure

1. Introduction & Motivation
2. Mastodon Architecture Overview
3. Experiment Setup
4. Experiment 1: Single-Instance Bottleneck
5. Experiment 2: Horizontal Scaling
6. Experiment 3: Federation Under Load *(if completed)*
7. Discussion: bottlenecks, consistency, tradeoffs, and limitations
8. Conclusion & Future Work

---

## 15. Cost Strategy
Because Learner Lab credits are limited, our strategy is to minimize runtime and avoid keeping all resources active simultaneously.

| **Item** | **Strategy** |
| :--- | :--- |
| Week 1 deployment | prioritize fast validation and short sessions |
| Week 2 experiments | short headless Locust runs |
| Week 3 federation | only attempt if both stability and credits allow |

We will stop ECS tasks and other non-essential resources after each session.

---

### 16. Tech Stack

| **Component** | **Tool** |
| :--- | :--- |
| Deployment | CloudFormation (adapted from widdix/mastodon-on-aws using quickstart-no-ses.yml) |
| Compute | ECS Fargate |
| Database | RDS PostgreSQL |
| Cache / Queue | ElastiCache Redis |
| Storage | S3 |
| Load Balancer | ALB |
| Monitoring | CloudWatch + RDS Performance Insights |
| Load Testing | Locust (Python) |
| Version Control | GitHub (mastodon-scaling-study) |