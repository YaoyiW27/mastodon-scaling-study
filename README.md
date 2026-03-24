# Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## Overview

This project studies how a federated social network behaves under load using Mastodon as a case study.

Our original plan was to deploy Mastodon with a CloudFormation / ECS-based AWS architecture, generate traffic with Locust, and analyze system behavior under load. Because AWS Academy Learner Lab introduced major deployment restrictions, we pivoted to a simpler EC2 + Docker Compose deployment path.

So far, the project focuses on:

1. **Single-instance bottleneck** — which component becomes the bottleneck first under load?
2. **Bottleneck shifting / worker scaling** — can increasing web-side capacity push the bottleneck from the web layer toward PostgreSQL?
3. **Vertical scaling** — how does instance size (t3.medium vs t3.large) affect throughput under identical load?
4. **Component dependency** — how do Redis, Sidekiq queue behavior, and DB connection constraints affect overall system behavior?
5.**Federation feasibility and latency** — can two lightweight EC2-hosted Mastodon instances support a basic federated workflow, and how does cross-instance propagation behave?

---

## Architecture Overview

<p align="center">
  <img src="assets/mastodon-study-architecture-v2.svg" alt="Mastodon Scaling Study Architecture" width="600">
</p>

---

## Current Status

- The original CloudFormation / ECS deployment path was blocked by Learner Lab IAM and nested-stack limitations.
- We pivoted to a **single EC2 + Docker Compose** deployment.
- Both instances pivoted to **EC2 + Docker Compose** with Nginx + HTTPS via Let's Encrypt.
- **Instance A** (Yaoyi): `a.mastodon-yaoyi.online` — t3.medium (4GB RAM) - anonymous read test, 0 failures up to 500 users.
- **Instance B** (Yehe): `mastodon-yehe.click` — t3.large (8GB RAM) - authenticated API test, rate limiter at 20+ users.
- Cross-instance federation has already been validated at a basic level: remote discovery, mutual follow, remote post visibility, and remote like notification.
- Both instances running Mastodon v4.5.7 with PostgreSQL 14 + Redis 7 in Docker.

## Repository Structure

```text
mastodon-scaling-study/
├── README.md
├── docker-compose.yml  # EC2 Docker Compose deployment (replaces CloudFormation after IAM restrictions)
├── cloudformation/
│   ├── v1-no-ses.yml
│   ├── v2-no-ses-no-cloudfront-s3-public.yml
│   ├── v3-no-ses-no-cloudfront-no-s3.yml
│   ├── v4-http-only.yml
│   └── v5-http-only-flowlog-false.yml
├── infra/
│   └── cloudwatch-dashboard.json
├── locust/
│   ├── locustfile_yaoyi.py
│   ├── locustfile_yehe.py
│   └── federation_test.py    # optional draft script for federation experiments
├── report/
│   └── mastodon_plan.md
└── results/
    ├── yaoyi/
    │   ├── notes.md
    │   ├── experiment_1_single_instance.md
    │   ├── experiment_2_federation.md
    │   └── screenshots/
    └── yehe/
        ├── locust_results
        ├── screenshots
        └── week1_notes.md


```

## Next Steps
- [ ] Yaoyi: continue the single-instance line by testing whether increasing web-side capacity can push the bottleneck beyond the web layer
- [ ] Yehe: continue the component-dependency line, focusing on cache / Sidekiq queue / DB connection behavior
- [ ] Run a small federation propagation / partial-outage test between Instance A and B
- [ ] Consolidate both teammates' results into the final report
- [ ] Prepare slides / presentation materials

See [report/mastodon_plan.md](report/mastodon_plan.md) for the detailed project plan.