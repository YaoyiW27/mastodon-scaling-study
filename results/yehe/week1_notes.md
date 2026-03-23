# CS6650 Final Project — Mastodon Deployment Notes
**Yaoyi Wang & Yehe Yan | Week 1–2 | March 2026**

---

## 1. Overview

This document covers the deployment journey for the CS6650 final project — scaling and stress-testing Mastodon's distributed architecture. The goal was to deploy two independent Mastodon instances on AWS, run load tests, and observe backend behavior under increasing load.

| Instance | Owner | Domain | EC2 |
|---|---|---|---|
| Instance A | Yaoyi | a.mastodon-yaoyi.online | t3.medium (4GB) |
| Instance B | Yehe | mastodon-yehe.click | t3.large (8GB) |

---

## 2. CloudFormation Deployment — Attempts and Failures

The original plan used the official `mastodon-on-aws` CloudFormation quickstart template. This approach failed repeatedly due to AWS Academy Learner Lab IAM restrictions.

| Version | Failed Resource | Root Cause | Action |
|---|---|---|---|
| v1 (original) | `EmailIdentity`, `LambdaRole` | SES + IAM role creation blocked | Removed all SES/email resources |
| v2 | `BucketPolicyPublic` | Account-level S3 Block Public Access | Changed `Access=CloudFrontRead` → `Private` |
| v3/v4 | `FlowLogModule` (VPC) | VPC flow logs require IAM role creation | Set `FlowLog: false` |
| v5 | `TaskRole` / `TaskExecutionRole` | ECS Fargate requires IAM task roles — fundamentally blocked | Abandoned CloudFormation entirely |

### Root Cause

AWS Academy Learner Lab enforces a locked-down IAM policy (`LabRole`) that blocks creation of new IAM roles, users, and certain resource policies. The `mastodon-on-aws` template was designed for full-permission AWS accounts and internally creates:

- `AWS::IAM::Role` — ECS task execution (blocked)
- `AWS::IAM::User` — SES email sending (blocked)
- `AWS::CloudFront::CloudFrontOriginAccessIdentity` — S3 media CDN (blocked)
- `AWS::SES::EmailIdentity` — email domain verification (blocked)
- VPC FlowLog IAM role — network logging (blocked)

After 5 failed attempts and progressive template modifications, the decision was made to abandon CloudFormation and switch to EC2 + Docker Compose.

---

## 3. EC2 + Docker Compose Deployment

### Why EC2 + Docker Compose

- No CloudFormation nested stacks — no hidden IAM resource creation
- Docker runs as the EC2 instance's `LabRole` directly — no new roles needed
- All services run as containers on one VM — no ECS task roles required
- Simpler to debug, faster to iterate, easier to control for experiments

> **Note for report:** Core application behavior and API semantics are identical to production. The bottlenecks measured (Rails web layer CPU, PostgreSQL query load, Sidekiq queue depth) behave the same regardless of whether the database is managed or containerized.

### Stack

| Container | Image | Purpose | Port |
|---|---|---|---|
| `web` | `mastodon:v4.5.7` | Rails/Puma — HTTP API | `127.0.0.1:3000` |
| `streaming` | `mastodon-streaming:v4.5.7` | Node.js — WebSocket API | `127.0.0.1:4000` |
| `sidekiq` | `mastodon:v4.5.7` | Background jobs — federation, notifications | internal |
| `db` | `postgres:14-alpine` | PostgreSQL database | internal |
| `redis` | `redis:7-alpine` | Queue backend + cache | internal |

### Deployment Steps

**1. Launch EC2**
- AMI: Ubuntu 24.04 LTS x86_64
- Instance type: t3.large (Instance B) / t3.medium (Instance A)
- Security group: SSH port 22 (My IP), HTTP port 80 (0.0.0.0/0), HTTPS port 443 (0.0.0.0/0)
- Storage: 30 GiB gp3

**2. Elastic IP**
- Allocated from EC2 → Network & Security → Elastic IPs
- Associated to instance — stable IP across Learner Lab session restarts

**3. DNS Setup**
- Domain registered on Namecheap
- Namecheap nameservers pointed to Route53 hosted zone NS records
- Route53 A record created pointing to Elastic IP

**4. Install Docker**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker ubuntu
```

**5. Configure .env.production**

Key settings:
```bash
LOCAL_DOMAIN=mastodon-yehe.click   # instance identity for federation
S3_ENABLED=false                    # we don't need that for now; nice-to-have feature
ES_ENABLED=false                    # Elasticsearch disabled
SMTP_SERVER=localhost               # email disabled
```

**6. Start Mastodon**
```bash
mkdir -p public/system postgres14 redis
docker compose pull
docker compose run --rm web bundle exec rails db:setup
docker compose up -d
```

```bash
ubuntu@ip-172-31-84-151:~/mastodon$ docker compose ps
NAME                   IMAGE                                        COMMAND                  SERVICE     CREATED          STATUS                    PORTS
mastodon-db-1          postgres:14-alpine                           "docker-entrypoint.s…"   db          37 minutes ago   Up 36 minutes (healthy)
mastodon-redis-1       redis:7-alpine                               "docker-entrypoint.s…"   redis       37 minutes ago   Up 36 minutes (healthy)
mastodon-sidekiq-1     ghcr.io/mastodon/mastodon:v4.5.7             "/usr/bin/tini -- bu…"   sidekiq     36 minutes ago   Up 36 minutes (healthy)   3000/tcp
mastodon-streaming-1   ghcr.io/mastodon/mastodon-streaming:v4.5.7   "docker-entrypoint.s…"   streaming   36 minutes ago   Up 36 minutes (healthy)   127.0.0.1:4000->4000/tcp
mastodon-web-1         ghcr.io/mastodon/mastodon:v4.5.7             "/usr/bin/tini -- bu…"   web         36 minutes ago   Up 36 minutes (healthy)   127.0.0.1:3000->3000/tcp

ubuntu@ip-172-31-84-151:~/mastodon$ curl -s https://mastodon-yehe.click/health
OK
```

**7. SSL Certificate**

Port 80 must be open in security group first. Certbot auto-modifies nginx config but introduced a redirect loop — config was manually replaced:
```bash
sudo certbot --nginx -d mastodon-yehe.click \
  --non-interactive --agree-tos --email yan.ye@northeastern.edu
```

**8. Create Admin Account**
```bash
docker compose exec web tootctl accounts create admin \
  --email admin@mastodon-yehe.click --confirmed --role Owner
```

![yehe-mastodon-up](screenshots/yehe_mastodon.png)
---

## 4. Operational Notes

### Learner Lab Session Management

- Sessions expire every 4 hours — EC2 **stops** but is NOT terminated
- PostgreSQL and Redis data persists across sessions (Docker volumes on EBS)
- Elastic IP association may drop after restart — re-associate if needed
- On session resume:
```bash
# Start Lab → wait for green light → EC2 → Start instance
cd ~/mastodon && docker compose up -d
```

### Budget

| Resource | Cost |
|---|---|
| EC2 t3.large | $0.0832/hr (~$0.67/8hr session) |
| EC2 t3.medium | $0.0416/hr (~$0.33/8hr session) |
| Elastic IP (instance stopped) | $0.005/hr |
| EBS 30GB gp3 | ~$2.40/month |
| **Both running 8hr/day** | **~$1/day total** |

### Known Limitations vs Production

| Component | Production | This Deployment |
|---|---|---|
| Database | Managed RDS (multi-AZ) | PostgreSQL in Docker |
| Cache | ElastiCache cluster | Redis in Docker |
| Media storage | S3 + CloudFront | Disabled |
| Email | SES | Disabled |
| Scaling | ECS autoscaling | Manual `docker compose --scale` |
| Monitoring | CloudWatch dashboards | `docker stats` + Sidekiq dashboard |

### Vertical Scaling Comparison (Built-in Experiment)

Instance A (t3.medium, 4GB) vs Instance B (t3.large, 8GB) provides a natural vertical scaling comparison. Running identical Locust workloads on both shows the impact of memory/CPU provisioning on throughput.

---

## 5. Federation Between Instances

Both instances successfully federated via ActivityPub after Instance A completed nginx/SSL setup.

**Verified by:**
- Searching `@admin@a.mastodon-yaoyi.online` from `mastodon-yehe.click`
- Cross-instance follow worked
- Posts appearing in remote instance's home timeline

**Requirements for federation:**
- Valid HTTPS on port 443 with trusted SSL certificate
- Accessible `/.well-known/webfinger` endpoint
- `LOCAL_DOMAIN` set correctly in `.env.production` (not `localhost`)

---

## 6. Load Test Results — Instance B (mastodon-yehe.click)

Locust task weights: GET home timeline (5x), GET public timeline (3x), POST status (3x), GET notifications (2x), favourite (1x), search (1x).

![sidekiq-monitor](screenshots/sidekiq_monitor.png)

### Smoke Test — 5 Users, 60s

| Endpoint | Requests | Failures | p50 | p95 | p99 | RPS |
|---|---|---|---|---|---|---|
| POST /api/v1/statuses | 77 | 0 (0%) | 95ms | 150ms | 310ms | 1.30 |
| GET /timelines/home | 67 | 0 (0%) | 180ms | 280ms | 410ms | 1.14 |
| GET /timelines/public | 22 | 0 (0%) | 170ms | 210ms | 370ms | 0.37 |
| GET /notifications | 22 | 0 (0%) | 110ms | 190ms | 240ms | 0.37 |
| GET /api/v2/search | 11 | 0 (0%) | 62ms | 180ms | 180ms | 0.19 |
| **Aggregated** | **213** | **0 (0%)** | **130ms** | **230ms** | **310ms** | **3.61** |

✅ Clean baseline — 0 failures across all endpoints.

### Baseline — 20 Users, 300s

| Endpoint | Requests | Failures | Failure % | p50 | p95 | p99 | RPS |
|---|---|---|---|---|---|---|---|
| POST /api/v1/statuses | 1,383 | 834 | 60.3% | 82ms | 400ms | 670ms | 4.62 |
| GET /timelines/home | 1,153 | 668 | 57.9% | 100ms | 470ms | 790ms | 3.85 |
| GET /timelines/public | 591 | 280 | 47.4% | 170ms | 430ms | 700ms | 1.97 |
| GET /notifications | 404 | 215 | 53.2% | 110ms | 570ms | 970ms | 1.35 |
| GET /api/v2/search | 184 | 103 | 56.0% | 61ms | 200ms | 310ms | 0.61 |
| **Aggregated** | **4,041** | **2,226** | **55.1%** | **94ms** | **440ms** | **740ms** | **13.49** |

All failures: HTTP 429 Too Many Requests. Rate limiter already activating at 20 users.

### Stress Test — 50 Users, 300s

| Endpoint | Requests | Failures | Failure % | p50 | p95 |
|---|---|---|---|---|---|
| POST /api/v1/statuses | 3,129 | 3,029 | 96.8% | 92ms | 1,300ms |
| GET /timelines/home | 2,669 | 2,011 | 75.3% | 91ms | 1,700ms |
| GET /timelines/public | 1,276 | 819 | 64.2% | 100ms | 1,500ms |
| GET /notifications | 853 | 663 | 77.7% | 89ms | 1,900ms |
| GET /api/v2/search | 474 | 344 | 72.6% | 96ms | 1,200ms |
| **Aggregated** | **8,990** | **7,212** | **80.2%** | **94ms** | **1,500ms** |

All failures: HTTP 429 Too Many Requests (Mastodon rate limiter).

### EC2 CloudWatch CPU During Load Tests

![stress-test-cloudwatch-cpu](screenshots/cloudwatch_cpu.png)

| Test | EC2 CPU Peak | Web Container CPU | DB CPU | Sidekiq |
|---|---|---|---|---|
| 5 users (smoke) | ~5% | normal | normal | processing |
| 20 users (baseline) | **35.9%** | elevated | 11% | processing |
| 50 users (stress) | **~26%** | **177%** (1 core) | 11% | idle (no jobs) |

> **Key insight:** EC2 showed only 35.9% peak at 20 users and ~26% at 50 users because the rate limiter rejected 80% of requests before they reached the CPU-intensive Rails stack. The web container hitting 177% (of one core = 88.5% of instance) at 50 users confirms the rate limiter activated near the application's processing capacity.

### Key Findings

1. **Rate limiter activates before hardware saturation** — at 50 users, Mastodon's `rack-attack` middleware returned 429s before PostgreSQL or Redis became bottlenecks
2. **Web layer is the bottleneck** — web container hit 177% CPU while DB stayed at 11% and Sidekiq stayed idle
3. **Sidekiq starved under rate limiting** — no successful POST requests = no jobs enqueued = Sidekiq idle
4. **p50 paradox** — median latency *improved* at 50 users (130ms → 94ms) because 429 responses are instant failures, pulling the median down
5. **True hardware limit not yet found** — next step: disable rate limiting (`RACK_ATTACK_ENABLED=false`) and rerun

### Load Test Progression Summary

| Load Level | Error Rate | p50 | p95 | p99 | RPS | Bottleneck |
|---|---|---|---|---|---|---|
| 5 users (smoke) | 0% | 130ms | 230ms | 310ms | 3.6 | None |
| 20 users (baseline) | 55.1% | 94ms | 440ms | 740ms | 13.5 | Rate limiter begins |
| 50 users (stress) | 80.2% | 94ms | 1,500ms | 2,300ms | 30.0 | Rate limiter + CPU 177% |

---

## 7. Next Steps — Week 2 Experiments

- [ ] Disable rate limiting (`RACK_ATTACK_ENABLED=false`) and rerun 50-user test to find true CPU/DB saturation
- [ ] Scale web containers (`docker compose up --scale web=2`) — horizontal scaling experiment
- [ ] Compare Instance A (t3.medium) vs Instance B (t3.large) under identical load — vertical scaling data
- [ ] Monitor Sidekiq queue depth during experiments: `watch -n 2 'docker compose exec -T redis redis-cli LLEN queue:default'`
- [ ] Federation propagation latency measurement between Instance A and B

---

*Document generated: March 22, 2026*
