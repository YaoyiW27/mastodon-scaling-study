# Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## Overview

This project studies how a federated social network behaves under load using Mastodon as a case study.

Our original plan was to deploy Mastodon with a CloudFormation / ECS-based AWS architecture, generate traffic with Locust, and analyze system behavior under load. Because AWS Academy Learner Lab introduced major deployment restrictions, we pivoted to a simpler EC2 + Docker Compose deployment path.

So far, the project focuses on:

1. **Single-instance bottleneck** — which component becomes the bottleneck first under load?
2. **Minimal federation feasibility** — can a lightweight EC2-hosted Mastodon instance participate in a basic cross-instance federation workflow?

---

## Architecture Overview

![Mastodon Scaling Study Architecture](assets/mastodon-scaling-study-architecture.png)

---

## Current Status

- The original CloudFormation / ECS deployment path was blocked by Learner Lab IAM and nested-stack limitations.
- We pivoted to a **single EC2 + Docker Compose** deployment.
- Yaoyi successfully deployed a working Mastodon instance with **Nginx + HTTPS**.
- Initial **Locust load testing** was completed.
- A minimal **federation workflow** between the two instances was successfully validated.

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
    │   ├── notes.md
    │   ├── experiment_1_single_instance.md
    │   ├── experiment_2_federation.md
    │   └── screenshots/
    └── yehe/
```

## Next Steps
- Finalize Yehe’s notes and screenshots
- Merge Yehe’s branch into main
- Consolidate both teammates’ results into the final report
- Prepare slides / presentation materials

See [report/mastodon_plan.md](report/mastodon_plan.md) for the detailed project plan.