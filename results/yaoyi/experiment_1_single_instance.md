# Experiment 1 — Single-Instance Anonymous Read Load Test

## Objective
Measure how a single EC2-hosted Mastodon instance behaves under increasing anonymous read traffic.

## Environment
- Deployment: Tiny Mastodon on EC2 with Docker Compose
- Instance type: t3.medium
- Access path: http://a.mastodon-yaoyi.online:3000
- Endpoints tested:
  - /
  - /about
  - /explore
  - /health

## Key Results

| Load Level | Avg Latency (ms) | P95 (ms) | P99 (ms) | RPS | Failures |
|-----------|------------------:|---------:|---------:|----:|---------:|
| 5 users   | 173.34 | 220 | 290 | 2.2 | 0 |
| 20 users  | 170.32 | 200 | 290 | 9.4 | 0 |
| 50 users  | 185.42 | 240 | 670 | 22.8 | 0 |
| 100 users | 178.90 | 220 | 370 | 46.6 | 0 |
| 200 users | 225.41 | 390 | 690 | 91.2 | 0 |
| 500 users | 2343.75 | 2900 | 3400 | 112.9 | 0 |

## Result Interpretation

| Load Level | Observation |
|-----------|-------------|
| 5 users   | Stable baseline with low latency and no failures. |
| 20 users  | Still stable; latency remained almost unchanged from baseline. |
| 50 users  | Throughput increased while tail latency began to rise. |
| 100 users | System remained stable with zero failures and strong throughput growth. |
| 200 users | Noticeable increase in tail latency, but the instance was still operational and failure-free. |
| 500 users | No request failures, but latency increased sharply into the 2–3.5 s range, indicating the system was approaching saturation. |

## Bottleneck Summary

| Metric | 200 users | 500 users | Interpretation |
|-------|----------:|----------:|----------------|
| Avg latency (ms) | 225.41 | 2343.75 | Latency increased dramatically under heavier load. |
| P95 (ms) | 390 | 2900 | Tail latency became severe at 500 users. |
| P99 (ms) | 690 | 3400 | High-percentile response times indicate significant queuing or contention. |
| RPS | 91.2 | 112.9 | Throughput increased only modestly compared with the latency cost. |
| Failures | 0 | 0 | The system degraded gracefully rather than failing outright. |

## Supporting Observation
A Docker stats snapshot under higher load showed the web container consuming the highest CPU usage, while PostgreSQL, Redis, and the other services remained comparatively lighter.