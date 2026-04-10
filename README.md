# Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## Overview

This project studies how a federated social network behaves under load using Mastodon as a real-world distributed systems case study.

Our original plan was to deploy Mastodon with a CloudFormation / ECS-based AWS architecture. Because AWS Academy Learner Lab introduced IAM restrictions that blocked ECS task role creation, we pivoted to EC2 + Docker Compose. This pivot preserved all core research goals while increasing deployment reliability.

The project focuses on five questions:

1. **Single-instance bottleneck** — which component becomes the bottleneck first under anonymous read load?
2. **Authenticated load + rate limiting** — how does Mastodon's application-level rate limiter behave under authenticated traffic?
3. **Bottleneck shifting** — can increasing web-side capacity push the bottleneck from the web layer toward PostgreSQL or Sidekiq?
4. **Vertical scaling** — how does instance size (t3.medium vs t3.large) affect the ability to benefit from worker tuning?
5. **Federation** — can two independently deployed EC2 instances support a federated workflow via ActivityPub?

---

## Architecture Overview

<p align="center">
  <img src="assets/mastodon-study-architecture-v2.svg" alt="Mastodon Scaling Study Architecture" width="600">
</p>

## Video Pitch

[![Watch the pitch](/assets/ytb_image.png)](https://youtu.be/8CD8hdcGNhc)

---

## Current Status

| Item | Status |
|------|--------|
| CloudFormation / ECS deployment | ❌ Blocked by Learner Lab IAM restrictions |
| EC2 + Docker Compose deployment | ✅ Both instances running |
| Instance A — Exp 1 (anonymous read bottleneck) | ✅ Complete |
| Instance A — Exp 2 (bottleneck shifting, t3.medium) | ✅ Complete |
| Instance B — Exp 1 (authenticated load + rate limiter) | ✅ Complete |
| Instance B — Exp 2 (bottleneck shifting, t3.large) | ✅ Complete |
| Federation validation | ✅ Complete |
| Federation propagation latency test | 🔲 Planned |

**Instance A** (Yaoyi): `a.mastodon-yaoyi.online` — t3.medium (2 vCPU, 4GB RAM)
**Instance B** (Yehe): `mastodon-yehe.click` — t3.large (2 vCPU, 8GB RAM)
Both running Mastodon v4.5.7 with PostgreSQL 14 + Redis 7 in Docker Compose.

---

## Key Findings So Far

- Anonymous read load scales to 500 users with zero failures on t3.medium; latency degrades sharply above 200 users
- Mastodon's `rack-attack` rate limiter activates before hardware saturation under authenticated load
- On t3.large: WEB_CONCURRENCY=4 eliminates all failures; nginx caching improves public timeline latency 5×
- On t3.medium: WEB_CONCURRENCY=4 causes 502 Bad Gateway errors — the instance cannot absorb additional workers under load
- Federation requires HTTPS + Nginx; direct HTTP on port 3000 breaks WebFinger discovery

---

## Repository Structure

```text
mastodon-scaling-study/
├── README.md
├── docker-compose.yml
├── cloudformation/             # v1–v5 failed deployment attempts (IAM analysis)
├── infra/
│   └── cloudwatch-dashboard.json
├── locust/
│   ├── locustfile_yaoyi.py         # Exp 1: anonymous read workload
│   ├── locustfile_yaoyi_exp2.py    # Exp 2: authenticated workload (bottleneck shifting)
│   ├── locustfile_yehe.py          # Yehe's authenticated workload
│   └── federation_test.py          # Federation latency test (planned)
├── report/
│   ├── mastodon_plan.md
│   ├── milestone1_report.md
│   ├── milestone2_report.md
│   └── results_graphs.md
└── results/
    ├── yaoyi/
    │   ├── exp2_bottleneck_shifting/   # CSV results
    │   ├── screenshots/
    │   ├── experiment_1_single_instance.md
    │   ├── experiment_2_bottleneck_shifting.md
    │   └── experiment_3_federation_validation.md
    └── yehe/
        ├── exp1_authenticated_baseline/
        ├── exp2_bottleneck_shifting/
        ├── screenshots/
        ├── week1_notes.md
        └── week2_notes.md
```

---

## Next Steps

- [ ] Run federation propagation latency test
- [ ] Write Milestone 3 report (federation latency results)
- [ ] Finalize presentation slides
- [ ] Submit final report by Apr 20

See [report/mastodon_plan.md](report/mastodon_plan.md) for the full project plan.