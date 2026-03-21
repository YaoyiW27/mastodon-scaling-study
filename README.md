# Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## Overview

This project studies how a federated social network behaves under load by using Mastodon as a case study.
We aim to deploy Mastodon on AWS, generate traffic with Locust, and measure how the system performs under increasing load and under limited horizontal scaling.

Our project focuses on three questions:

1. **Single-instance bottleneck** — which component becomes the bottleneck first under load?
2. **Horizontal scaling** — how much performance improves when increasing ECS task count?
3. **Federation under load** *(nice-to-have)* — how long cross-instance propagation takes under different load levels?

---

## Current Deployment Status

Our deployment is **based on** the `widdix/mastodon-on-aws` project, but AWS Academy Learner Lab introduces important limitations:

- restricted IAM permissions
- SES email setup unavailable / unreliable
- Route 53 domain flow may not work smoothly
- some S3 / CloudFront-related resources may require manual simplification
- 4-hour lab session timeout

Because of this, we are **not using the original template as-is**.
Instead, we are testing a modified CloudFormation template:

- `quickstart-no-ses.yml` — custom template with SES dependency removed

This custom template is still a work in progress for Learner Lab compatibility.
The current goal is to achieve a **minimal working Mastodon deployment** first, then move to load testing and analysis.

---

## Repository Structure

```text
mastodon-scaling-study/
├── README.md
├── quickstart-no-ses.yml        # Customized CloudFormation template for Learner Lab (SES removed)
├── infra/
│   └── cloudwatch-dashboard.json
├── locust/
│   ├── locustfile.py
│   └── federation_test.py
├── report/
│   └── mastodon_plan.md
└── results/
    ├── yaoyi/
    └── yehe/