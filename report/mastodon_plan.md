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

## 	Week 1 (Mar 20–23): Deployment Validation + Smoke Test Preparation

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