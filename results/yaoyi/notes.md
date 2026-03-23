# Yaoyi Notes

## Goal
Identify a workable deployment path for Instance A and determine whether Mastodon can be deployed in AWS Academy Learner Lab for our distributed systems experiments.

## Progress Log
- **Branch**: Created and switched to `yaoyi/instance-a-setup`; synchronized with the latest changes from `main`.
- **Secret Generation**: Successfully generated deployment secrets (`SECRET_KEY_BASE`, VAPID keys, and Active Record encryption keys).
- **Domain Setup**:
  - Purchased domain: `mastodon-yaoyi.online`
  - Created a hosted zone in Route 53
  - Updated Namecheap nameservers to the NS records provided by Route 53

## Deployment History and Debugging

### Template Evolution
- **v1**: Removed SES dependency, but still kept the original S3 + CloudFront architecture.
- **v2**: Removed CloudFront and changed S3 to public-read access.
- **v3**: Removed S3 integration entirely.
- **v4**: Removed template-managed Route 53 / ACM resources and switched to HTTP only.
- **v5**: Explicitly disabled VPC Flow Logs with `FlowLog: false`.

### Attempt 1 — Template `v2`
- **Status**: `FAILED`
- **Root Cause**: `BucketPolicyPublic` creation failed in the nested `Bucket` stack.
- **Analysis**: AWS Academy Learner Lab appears to block public-read S3 bucket policies or related public access settings.

### Attempt 2 — Template `v3`
- **Status**: `FAILED`
- **Root Cause**: `FlowLogModule` failed in the nested `Vpc` stack.
- **Analysis**: VPC Flow Logs likely require IAM permissions or service integrations not available in Learner Lab.

### Attempt 3 — Template `v4`
- **Status**: `FAILED`
- **Root Cause**: `FlowLogModule` failed again in the nested `Vpc` stack.
- **Analysis**: Simply removing Flow Log-related parameters was not enough. The underlying VPC module appears to fall back to its default Flow Log behavior unless Flow Logs are explicitly disabled.

### Attempt 4 — Template `v5`
- **Status**: `FAILED`
- **Root Cause**: `TaskRole` and `TaskExecutionRole` failed in the nested `WebService` stack.
- **Analysis**: The deployment progressed further than previous attempts and successfully created core infrastructure such as VPC, ALB, RDS, and Redis. However, AWS Academy Learner Lab appears to block creation of ECS task-related IAM roles required by the Mastodon application services.

## Conclusion on the Original Deployment Path
- The main blocker is no longer storage, DNS, or Flow Logs.
- The limiting factor is Learner Lab IAM restrictions on ECS task role creation.
- The original ECS/Fargate + CloudFormation deployment path is not a practical fit for the AWS Academy Learner Lab environment.

## Pivot Decision: EC2 + Docker Compose
Due to the IAM blockers, we pivoted to a **Minimal Mastodon Deployment** strategy.

- **Environment**: Single AWS EC2 instance (`t3.medium`)
- **Orchestration**: Docker Compose
- **Reasoning**: This path bypasses the IAM role creation blocker while still allowing us to measure useful system behavior such as response latency, throughput, and container resource usage.

## EC2 Deployment Notes

### Technical Fixes
- **Network Exposure**: Changed container bindings from `127.0.0.1:3000` to `0.0.0.0:3000` so the application could accept external traffic.
- **Domain Alignment**: Updated `LOCAL_DOMAIN` to `a.mastodon-yaoyi.online` so the application host matched the externally exposed subdomain.
- **HTTP-Only Testing**: Patched `config.force_ssl = false` in the production environment to support HTTP-only access in the Learner Lab setup.
- **Image Rebuild**: Rebuilt the local Docker images so the SSL-related configuration patch took effect correctly.

### Environment Stabilization
- **Swap Configuration**: Added a 4 GB swap file on the EC2 host to reduce the chance of OOM failures during Docker image builds and load testing.

## Current Status
- Successfully deployed a working Mastodon instance on a single EC2 host using Docker Compose.
- Verified external web access through:
  - `http://a.mastodon-yaoyi.online:3000`
- Successfully logged in, completed profile setup, and published a test post.
- Confirmed that the application, PostgreSQL, Redis, Sidekiq, and streaming services were all running together on the same host.

## Initial Load Testing
Completed an initial single-instance Locust load test against public read endpoints:

- `/`
- `/about`
- `/explore`
- `/health`

### Load Levels Tested
- 5 users
- 20 users
- 50 users
- 100 users
- 200 users
- 500 users

### Summary of Findings
- No request failures were observed at any tested load level.
- The instance remained stable from 5 to 200 users with moderate latency.
- At 500 users, throughput increased only modestly relative to 200 users, but latency rose sharply into the 2–3.5 second range.
- This suggests that the single-instance deployment approached saturation at higher concurrency.
- Docker stats under higher load showed the web container using the most CPU, suggesting that the web tier was the likely bottleneck under this anonymous read-heavy workload.

## Federation Check
We attempted a minimal federation discovery check against Yehe’s instance (`mastodon-yehe.click`).

- The remote account could not be discovered successfully using the normal `@user@domain` search flow.
- A likely reason is that this Tiny Mastodon deployment is exposed over HTTP on port 3000 rather than a standard HTTPS production endpoint.
- This likely limits WebFinger / ActivityPub discoverability, even though the instance itself is reachable in a browser.

## Next Steps
1. Organize screenshots and raw experiment outputs under `results/yaoyi/`.
2. Write up the single-instance experiment results in a separate experiment note.
3. Continue testing whether a minimal cross-instance federation workflow is possible under the EC2 + Docker Compose deployment path.
4. Merge stable deployment notes and experiment results into the shared project report later.