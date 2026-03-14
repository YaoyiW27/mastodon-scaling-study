# Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## Overview

This project stress-tests [Mastodon](https://github.com/mastodon/mastodon)'s distributed architecture on AWS to understand how a real-world federated social network scales under load.

We deploy Mastodon instances on AWS ECS Fargate and run three experiments:
1. **Single-instance bottleneck** — find which component breaks first under increasing load
2. **Horizontal scaling** — measure throughput improvement when adding ECS tasks behind an ALB
3. **Federation under load** — measure cross-instance message propagation latency via ActivityPub

---

## Repository Structure

```
mastodon-scaling-study/
├── locust/
│   ├── locustfile.py         # Load test script (Locust)
│   └── federation_test.py    # Federation latency measurement
├── infra/
│   └── cloudwatch-dashboard.json  # CloudWatch Dashboard config
├── results/
│   ├── yaoyi/                # Experiment results - traffic/scaling layer
│   └── yehe/                 # Experiment results - data/backend layer
├── report/
│   └── mastodon_plan.md      # Full project plan
└── README.md
```

---

## Setup

See [`report/mastodon_plan.md`](report/mastodon_plan.md) for the full deployment guide.

**Quick summary:**
- AWS Academy Learner Lab (us-east-1 / us-west-2)
- Deployed via [`widdix/mastodon-on-aws`](https://github.com/widdix/mastodon-on-aws) CloudFormation template
- Load testing with [Locust](https://locust.io/)
- Monitoring via CloudWatch + RDS Performance Insights

---

## Tech Stack

| Component | Tool |
|-----------|------|
| Compute | AWS ECS Fargate |
| Database | RDS PostgreSQL |
| Cache / Queue | ElastiCache Redis |
| Storage | S3 |
| Load Balancer | ALB |
| Monitoring | CloudWatch |
| Load Testing | Locust |