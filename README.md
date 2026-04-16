# Mastodon Scaling Study
### CS6650 Distributed Systems — Spring 2026
**Team:** Yaoyi Wang & Yehe Yan

---

## Why We Built This

Mastodon is a real open-source federated social network used by millions of people. Unlike centralized platforms, it runs across thousands of independently operated servers that communicate via the ActivityPub protocol. This makes it an ideal distributed systems case study: a single instance contains a web layer (Rails/Puma), a background job processor (Sidekiq), a cache and job queue (Redis), a relational database (PostgreSQL), and a cross-instance federation protocol — all interacting under load.

We stress-tested two independent Mastodon instances on AWS EC2 to answer five questions:

1. **Single-instance bottleneck** — which component breaks first under anonymous read load?
2. **Authenticated load + rate limiting** — how does Mastodon's application-level rate limiter behave under real user traffic?
3. **Bottleneck shifting** — can increasing web-side capacity push the bottleneck toward PostgreSQL or Sidekiq?
4. **Vertical scaling** — how does instance size (t3.medium vs t3.large) affect the ability to benefit from worker tuning?
5. **Federation under load** — how does cross-instance ActivityPub delivery degrade as the receiving instance is placed under load?

---

## Architecture Overview

<p align="center">
  <img src="assets/mastodon-study-architecture-v2.svg" alt="Mastodon Scaling Study Architecture" width="600">
</p>

| | Instance A (Yaoyi) | Instance B (Yehe) |
|---|---|---|
| Domain | `a.mastodon-yaoyi.online` | `mastodon-yehe.click` |
| EC2 | t3.medium (2 vCPU, 4GB RAM) | t3.large (2 vCPU, 8GB RAM) |
| Stack | EC2 + Docker Compose + Nginx + HTTPS | EC2 + Docker Compose + Nginx + HTTPS |
| Mastodon | v4.5.7 | v4.5.7 |

## Video Pitch

[![Watch the pitch](/assets/ytb_image.png)](https://youtu.be/8CD8hdcGNhc)

---

## Key Findings

- Anonymous read load scales to 500 users with zero failures on t3.medium; latency degrades sharply above 200 users
- Mastodon's `rack-attack` rate limiter activates at 20 users before any hardware saturation under authenticated load
- `WEB_CONCURRENCY=4` eliminates all failures on t3.large but causes 502 errors on t3.medium — instance size is a binding constraint for worker tuning
- Nginx caching reduces public timeline latency 5× (500ms → 93ms) by intercepting requests before they reach Rails
- Federation latency is 0.67s at idle; spikes to 28.73s under 20-user load due to Sidekiq/Puma CPU contention on the receiving instance
- Sidekiq failure is silent — HTTP layer appears healthy while 2,680+ jobs queue up unprocessed
- Redis is a synchronous hard dependency — stopping it produces 100% immediate failure via Rack::Attack middleware

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
| Federation propagation latency test | ✅ Complete |
| Extended federation stress test (sender loaded) | ✅ Complete |
| Component dependency isolation (Exp 4) | ✅ Complete |

---

## Reproducing the Deployment

### Prerequisites

- AWS account with EC2 access (t3.medium or t3.large)
- A domain name with DNS control (we used Namecheap + Route53)
- SSH key pair for EC2

### 1. Launch EC2

- AMI: Ubuntu 24.04 LTS x86_64
- Instance type: t3.medium (4GB) or t3.large (8GB) recommended
- Security group: open ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
- Storage: 30 GiB gp3
- Allocate an Elastic IP and associate it to the instance

### 2. Install dependencies

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker ubuntu
```

### 3. Configure DNS

Create an A record pointing your domain to the Elastic IP.

### 4. Clone and configure Mastodon

```bash
git clone https://github.com/mastodon/mastodon.git
cd mastodon
cp .env.production.sample .env.production
```

Edit `.env.production`:
```bash
LOCAL_DOMAIN=your-domain.com
S3_ENABLED=false
ES_ENABLED=false
SMTP_SERVER=localhost
```

Generate secrets:
```bash
docker compose run --rm web bundle exec rails secret        # SECRET_KEY_BASE
docker compose run --rm web bundle exec rails mastodon:webpush:generate_vapid_key
docker compose run --rm web bundle exec rails db:encryption:init
```

### 5. Start Mastodon

```bash
mkdir -p public/system postgres14 redis
docker compose run --rm web bundle exec rails db:setup
docker compose up -d
```

### 6. Configure HTTPS

```bash
sudo certbot --nginx -d your-domain.com \
  --non-interactive --agree-tos --email your@email.com
```

### 7. Create admin account

```bash
docker compose exec web tootctl accounts create admin \
  --email admin@your-domain.com --confirmed --role Owner
```

### 8. Verify

```bash
curl -s https://your-domain.com/health  # should return OK
```

### Federation

Federation between two instances works automatically once both are configured with HTTPS. To verify:
1. Search `@user@other-instance.com` from your instance
2. Follow the remote account
3. Posts from the remote instance should appear on your home timeline

> **Note:** Federation requires valid HTTPS with a trusted certificate. Direct HTTP on port 3000 breaks WebFinger discovery.

---

## Running the Load Tests

### Prerequisites

```bash
pip install locust
```

### Experiment 1 — Anonymous read load (Instance A)

```bash
locust -f locust/locustfile_yaoyi.py --headless \
  -u 500 -r 50 --run-time 120s \
  --host https://a.mastodon-yaoyi.online \
  --csv=results/yaoyi/exp1
```

### Experiment 2 — Authenticated load (Instance B)

```bash
locust -f locust/locustfile_yehe.py --headless \
  -u 20 -r 2 --run-time 300s \
  --host https://mastodon-yehe.click \
  --csv=results/yehe/exp1_baseline
```

### Federation latency test

```bash
# Edit TOKEN_A and TOKEN_B in federation_test.py first
python3 locust/federation_test.py
```

---

## Repository Structure

```text
mastodon-scaling-study/
├── README.md
├── docker-compose.yml
├── cloudformation/             # v1–v5 failed deployment attempts (IAM analysis)
├── infra/
│   └── cloudwatch_dashboard_t3.medium.json
├── locust/
│   ├── locustfile_yaoyi.py         # Exp 1: anonymous read workload
│   ├── locustfile_yaoyi_exp2.py    # Exp 2: authenticated workload (bottleneck shifting)
│   ├── locustfile_yehe.py          # Yehe's authenticated workload
│   ├── federation_test.py          # Federation latency test
│   └── combined_fed_test.py        # Combined sender load + federation test
├── report/
│   ├── mastodon_plan.md
│   ├── milestone1_report.md
│   ├── milestone2_report.md
│   ├── milestone3_report.md
│   └── results_graphs.md
└── results/
    ├── federation_latency.csv
    ├── locust_results.csv
    ├── yaoyi/
    │   ├── exp2_bottleneck_shifting/
    │   └── screenshots/
    └── yehe/
        ├── exp1_authenticated_baseline/
        ├── exp2_bottleneck_shifting/
        ├── exp3_disable_components/
        ├── federation_test_results/
        └── screenshots/
```

---

## Project Activity

- **72 commits** by 2 authors across 3 branches
- **4 pull requests** merged
- **189 files** changed, 11,592 additions
- Milestone reports: [Milestone 1](report/milestone1_report.md) · [Milestone 2](report/milestone2_report.md) · [Milestone 3](report/milestone3_report.md)
- Full results and graphs: [results_graphs.md](report/results_graphs.md)

---

## Tech Stack

| Component | Tool |
|-----------|------|
| Deployment | EC2 + Docker Compose |
| Web / App | Mastodon v4.5.7 (Rails/Puma) |
| Background jobs | Sidekiq |
| Cache + Queue | Redis 7 |
| Database | PostgreSQL 14 |
| Reverse proxy | Nginx + Let's Encrypt |
| Load testing | Locust (Python) |
| Monitoring | CloudWatch EC2 + Docker stats + Sidekiq dashboard |
| Federation protocol | ActivityPub |