# Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## Overview

This project studies how a federated social network behaves under load by using Mastodon as a case study.

We aim to deploy Mastodon on AWS, generate traffic with Locust, and analyze system behavior under increasing load and limited horizontal scaling.

Our project focuses on three questions:

1. **Single-instance bottleneck** — which component becomes the bottleneck first under load?
2. **Horizontal scaling** — how much performance improves when increasing ECS task count?
3. **Federation under load** *(nice-to-have)* — how long cross-instance propagation takes under different load levels?

---

## Current Deployment Status

Our deployment is **based on** the `widdix/mastodon-on-aws` project, but AWS Academy Learner Lab introduces important limitations:

- restricted IAM permissions
- SES email setup unavailable or unreliable
- Route 53 / DNS flow may not work smoothly
- some S3 / CloudFront-related resources may require simplification
- 4-hour lab session timeout

Because of this, we are **not using the original template as-is**.

Instead, we are testing a modified CloudFormation template:

- `quickstart-no-ses.yml` — custom template with SES dependency removed

This template is still being adapted for Learner Lab compatibility.
Our current goal is to achieve a **minimal working Mastodon deployment** first, then move to load testing and analysis.

---

## Current Plan

- **Yaoyi**: traffic/access layer, CloudWatch dashboard, horizontal scaling experiment
- **Yehe**: backend/data layer, deployment adaptation, bottleneck analysis
- **Shared**: deployment validation, Locust scripts, federation experiment, report integration

If both instances become stable, we will also run a basic federation propagation experiment.

---

## Repository Structure

```text
mastodon-scaling-study/
├── README.md
├── cloudformation/
│   ├── v1-no-ses.yml
│   ├── v2-no-ses-no-cloudfront-s3-public.yml
│   ├── v3-no-ses-no-cloudfront-no-s3.yml
│   ├── v4-http-only.yml
│   └── v5-http-only-flowlog-false.yml
├── infra/
│   └── cloudwatch-dashboard.json
├── locust/
│   ├── locustfile.py
│   └── federation_test.py
├── report/
│   └── mastodon_plan.md
└── results/
    ├── yaoyi/
    │   ├── screenshots/
    │   └── week1_notes.md
    └── yehe/
```

---

## Status
Current focus:
- validate one reliable deployment path in Learner Lab
- document blockers and workarounds
- prepare smoke tests and experiment scripts

See [report/mastodon_plan.md](report/mastodon_plan.md) for the detailed project plan.