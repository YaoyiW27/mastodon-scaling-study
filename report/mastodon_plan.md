# CS6650 Final Project Plan
## Scaling a Decentralized Social Network: Stress-Testing Mastodon's Distributed Architecture
**Team:** Yaoyi Wang & Yehe Yan | **Presentation:** Apr 13 / 20 · **Final Deadline:** Apr 20

---

## Success Criteria

### Must-have
- One working Mastodon instance on AWS
- Valid Locust workload (smoke test passes)
- Single-instance bottleneck experiment with data
- Horizontal scaling comparison
- At least 2–3 result graphs for presentation

### Nice-to-have
- Second instance deployed
- Basic federation propagation experiment (idle / light / moderate load, 5–10 runs)

### Stretch
- Bulk follower fan-out measurement
- Retry analysis
- Race-condition observations

---

## Go / No-Go Checkpoints

**Checkpoint 1 — Mar 20**
If Instance A is not stably running by Mar 20, stop investing in dual-instance planning and focus entirely on a single-instance bottleneck and scaling study.

**Checkpoint 2 — Mar 30**
If the second instance or federation setup is still unstable by Mar 30, drop bulk federation experiments and keep federation as discussion / future work section only.

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Learner Lab IAM blocks CloudFormation | Deployment delay | Switch to simpler manual deployment path |
| Route53 domain registration unavailable | Federation blocked | Use external low-cost domain or defer federation |
| ECS exec unavailable | Admin account creation blocked | Prepare alternative manual user initialization |
| Metrics too limited | Weak analysis | Prioritize Tier 1 metrics, treat Tier 2 as best-effort |
| Federation setup too unstable | Week 3 slips | Reduce to one basic propagation test |

---

## ⚠️ AWS Academy Learner Lab 限制

| 限制 | 说明 |
|------|------|
| **Session 超时** | 每次 4 小时后自动登出，运行中资源会被 stop |
| **Region** | 只能用 `us-east-1` 或 `us-west-2` |
| **IAM** | 极度受限，只能用预建的 `LabRole` / `LabInstanceProfile` |
| **额度** | 每人 $50，各用各的账号 |
| **资源恢复** | 重开 session 后需手动 start，EC2 public IP 会变 |

**关键习惯：** 每次结束前手动 stop ECS tasks 和 RDS；所有操作用 `us-east-1`

---

## 整体策略

- **Week 1**：各自部署 instance，smoke test + Locust 脚本验证
- **Week 2**：正式实验，各自侧重方向不同
- **Week 3**：若 Checkpoint 2 通过，联通两个 instance 做基础 federation 实验
- **Week 4**：收尾、report、presentation

---

## 分工总览

| 模块 | 负责人 | Instance | 实验侧重 |
|------|--------|----------|----------|
| 流量与接入层 | Yaoyi | Instance A（自己账号） | ALB + ECS 水平扩展；CloudWatch 监控 |
| 数据与消息层 | Yehe | Instance B（自己账号） | RDS + Redis 调优；Sidekiq 并发参数 |
| Federation 实验 | 两人协作 | A + B 联通 | 跨节点消息传播、propagation latency |

---

## Metrics 分层

### Tier 1：一定能拿到
- Request latency (P50 / P95 / P99)
- Throughput (RPS)
- Error rate
- ECS CPU / Memory utilization
- ECS task count
- ALB response time
- RDS connections / CPU

### Tier 2：有条件就拿（best-effort）
- Redis queue depth
- Sidekiq retries
- Cache hit rate
- Worker-specific processing time

---

## GitHub 仓库结构

```
mastodon-scaling-study/
├── README.md
├── locust/
│   ├── locustfile.py             # 基础压测脚本（共用）
│   └── federation_test.py        # federation 延迟测试
├── infra/
│   └── cloudwatch-dashboard.json
├── results/
│   ├── yaoyi/                    # Yaoyi 实验数据
│   └── yehe/                     # Yehe 实验数据
└── report/
    └── draft.md
```

**Branch 策略：**
- `main`：README、目录结构、共用脚本
- `yaoyi/infra`：Yaoyi 的基础设施配置、CloudWatch
- `yehe/backend`：Yehe 的 Sidekiq 调优、压测脚本

---

## Mastodon 架构速览

```
用户请求
   ↓
ALB (负载均衡)
   ↓
Web (Ruby on Rails / Puma)  ←→  Redis (队列 + 缓存)
   ↓                                ↓
PostgreSQL (主数据库)          Sidekiq (后台 job)
                                    ↓
                             Federation HTTP POST → 远程 Instance
```

**Federation 完整流程：**
1. Instance A 用户发帖
2. Sidekiq 创建 `ActivityPub::DeliveryWorker` job
3. HTTP POST 到 Instance B 的 `/inbox`
4. Instance B 的 Sidekiq `ActivityPub::ProcessingWorker` 接收并入库
5. Instance B 用户 timeline 出现该帖子

---

## Week 1（Mar 14–20）：部署 + Smoke Test

### 两人都要做：部署自己的 Mastodon Instance

**Step 1：进入 Learner Lab**
1. 登录 https://awsacademy.instructure.com
2. Modules → Learner Lab → Start Lab，等绿灯
3. 进入 Console，确认 region = `us-east-1`

**Step 2：注册域名**
- Route53 → Registered Domains → Register Domain
- Yaoyi：`mastodon-yaoyi.click`，Yehe：`mastodon-yehe.click`
- ⚠️ 如果 Route53 域名注册被限制或延迟，改用外部域名（Namecheap 等），不要让域名成为 Week 1 的阻塞点

**Step 3：生成 Mastodon secrets（本地运行）**
```bash
docker run --rm -it ghcr.io/mastodon/mastodon:latest bin/rails secret
# 运行两次 → SECRET_KEY_BASE, OTP_SECRET
docker run --rm -it ghcr.io/mastodon/mastodon:latest bin/rails mastodon:webpush:generate_vapid_key
# → VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY
```

**Step 4：CloudFormation 部署（主路径）**
- CloudFormation → Create Stack
- Template URL：`https://s3.eu-central-1.amazonaws.com/mastodon-on-aws-cloudformation/latest/quickstart.yml`
- 所有 IAM Role 参数改为 `LabRole`
- 等待 20–30 分钟，Status 变 `CREATE_COMPLETE`
- ⚠️ 如果 CloudFormation 因 IAM 限制失败，pivot 到手动部署（EC2 + Docker Compose），保留 federation 为后续目标

**Step 5：创建 Admin 账号**
```bash
aws ecs execute-command \
  --cluster <cluster-name> --task <task-id> --container web \
  --command "tootctl accounts create admin --email admin@yourdomain.com --role Owner" \
  --interactive
```
⚠️ 如果 ECS exec 不可用，通过 Mastodon Web 界面手动注册后用 Rails console 提权

**Step 6：Smoke Test（部署完第一件事）**
- [ ] 能访问域名，页面加载正常
- [ ] 能注册账号、登录
- [ ] 能发帖、刷 timeline
- [ ] CloudWatch 能看到 ECS / RDS 指标
- [ ] logs 无异常错误

**Smoke test 通过后才开始跑 Locust**

---

### Yaoyi — 流量层准备

- [ ] 搭建 CloudWatch Dashboard（Tier 1 指标全部加进去）
- [ ] 配置 ALB 健康检查路径改为 `/robots.txt`
- [ ] 跑初步 Locust smoke test：5–10 users，验证脚本正确

### Yehe — 数据层准备 + Locust 脚本

- [ ] 开启 RDS Performance Insights
- [ ] 编写 `locustfile.py` 基础脚本

```python
from locust import HttpUser, task, between
import random

class MastodonUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.token = "your_access_token_here"
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def post_status(self):
        self.client.post("/api/v1/statuses",
            json={"status": f"Test post {random.randint(1,99999)}"},
            headers=self.headers)

    @task(5)
    def get_home_timeline(self):
        self.client.get("/api/v1/timelines/home", headers=self.headers)

    @task(2)
    def get_public_timeline(self):
        self.client.get("/api/v1/timelines/public")
```

- [ ] 跑 smoke test：5–10 users，确认脚本 no errors
- [ ] 记录 RDS / Redis baseline 指标

### 两人一起（Week 1 结束前）
- [ ] 建好 GitHub repo，push 初始目录结构 + `locustfile.py`
- [ ] 对齐 CSV 格式：`timestamp, users, rps, p50, p95, p99, error_rate`
- [ ] 确认双方 smoke test 都通过

---

## Week 2（Mar 21–27）：正式实验

### Yaoyi — 水平扩展实验（Experiment 2）

**压测梯度：**
```bash
for users in 50 100 200 300; do
  locust -f locustfile.py --host https://mastodon-yaoyi.click \
    --users $users --spawn-rate 10 --run-time 10m --headless \
    --csv=results/yaoyi/exp2_${users}users
  sleep 60
done
```

- [ ] 对比 1 / 2 / 4 个 Web task 的吞吐量差异
- [ ] 配置 ECS Auto Scaling（目标 CPU 70%，最大 4 tasks）
- [ ] 观察 scale-out 触发时机和速度
- [ ] 记录：RPS 提升幅度、P99 latency 变化、task count 曲线

### Yehe — 瓶颈定位实验（Experiment 1）

**压测梯度：**
```bash
for users in 50 100 200 300 500; do
  locust -f locustfile.py --host https://mastodon-yehe.click \
    --users $users --spawn-rate 10 --run-time 10m --headless \
    --csv=results/yehe/exp1_${users}users
  sleep 60
done
```

**定位瓶颈：**

| 组件 | 检查方式 | 瓶颈信号 |
|------|----------|----------|
| Web | ECS CPU > 80% | 加 Web tasks |
| PostgreSQL | RDS Connections 接近 max | 升级规格 |
| Sidekiq | Queue depth 持续增长 | 加 concurrency |
| ALB | 5xx 增加 | Web 层过载 |

**Sidekiq 并发调整（Tier 2，best-effort）：**
- ECS → Task Definition → sidekiq container → 环境变量
- `SIDEKIQ_CONCURRENCY`: 5 → 15 → 25，对比 queue 处理速度
- `DB_POOL` = concurrency + 5

### 两人一起（Week 2 结束前）
- [ ] 把数据 push 到各自 branch，merge 到 main
- [ ] 开始写 report Background + Experiment 1&2 初稿

---

## Week 3（Mar 28–Apr 3）：Federation 实验
*前提：Checkpoint 2（Mar 30）通过*

### 基础 Federation 实验（Nice-to-have）

**目标：** 在 idle / light load / moderate load 三种条件下各测 5–10 次 propagation latency，做对比

**准备：**
- Yehe 在 Instance B 创建 1–2 个账号，手动 follow Instance A 的 alice
- 验证 federation 正常（参考之前的验证步骤）

**测量脚本：**
```python
# federation_test.py
import time, requests

def measure_propagation(token_a, token_b, run_id):
    # 发帖
    t0 = time.time()
    resp = requests.post("https://mastodon-yaoyi.click/api/v1/statuses",
        json={"status": f"Federation test run {run_id} t={t0}"},
        headers={"Authorization": f"Bearer {token_a}"})
    uri = resp.json()["uri"]

    # 轮询 Instance B
    while True:
        timeline = requests.get("https://mastodon-yehe.click/api/v1/timelines/home",
            headers={"Authorization": f"Bearer {token_b}"}).json()
        if any(uri in p.get("uri","") for p in timeline):
            return time.time() - t0
        time.sleep(0.5)

# 跑 10 次，记录延迟
for i in range(10):
    latency = measure_propagation(TOKEN_A, TOKEN_B, i)
    print(f"Run {i}: {latency:.2f}s")
```

**三种负载下各跑 5–10 次：**
- Idle（无 Locust 压测）
- Light load（50 users）
- Moderate load（200 users）

**Stretch goals（时间够再做）：**
- 批量 follower fan-out（10 / 50 / 100）
- Retry rate 分析
- Race condition 观察（同时 boost 同一帖子，like 计数是否一致）

---

## Week 4（Apr 4–13）：收尾

| 日期 | 任务 |
|------|------|
| Apr 4–5 | 完成数据收集，**tear down AWS 资源** |
| Apr 6–8 | 完成 report 初稿，merge 所有 branch 到 main |
| Apr 9–11 | 制作 Presentation slides（至少 2–3 张结果图） |
| Apr 12 | 排练 |
| Apr 13 | 🎤 Presentation |
| Apr 14–20 | 完善 final report |

### Report 结构
1. Introduction & Motivation
2. Mastodon Architecture Overview
3. Experiment Setup（AWS 架构图 + 工具）
4. Experiment 1: Single Instance Bottleneck — Yehe 主写
5. Experiment 2: Horizontal Scaling — Yaoyi 主写
6. Experiment 3: Federation Under Load — 两人（若完成）
7. Discussion：CAP theorem + 最终一致性 + race condition（即使未完成实验也可从理论角度讨论）
8. Conclusion + Future Work

---

## 成本估算

| 账号 | 内容 | 预计费用 |
|------|------|----------|
| Yaoyi | Week 1–2 Instance A | ~$30 |
| Yehe | Week 1–2 Instance B | ~$30 |
| 其中一人 | Week 3 federation（两 instance 同时开） | ~$15 |
| 零散（S3、数据传输） | - | ~$5 |

各自 $100 额度完全够用。实验完立即将 ECS desired count 设为 0，RDS stop。

---

## 技术栈

| 组件 | 工具 |
|------|------|
| 部署 | CloudFormation (`widdix/mastodon-on-aws`) |
| 计算 | ECS Fargate |
| 数据库 | RDS PostgreSQL |
| 缓存/队列 | ElastiCache Redis |
| 存储 | S3 |
| 负载均衡 | ALB |
| 监控 | CloudWatch + RDS Performance Insights |
| 压测 | Locust (Python) |
| 代码管理 | GitHub (`mastodon-scaling-study`) |
