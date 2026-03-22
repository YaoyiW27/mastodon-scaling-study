# Yaoyi Week 1 Notes

## Goal
Investigate a workable deployment path for Instance A and determine whether Mastodon can be deployed in AWS Academy Learner Lab using the original CloudFormation-based approach.

## Progress Log
- **Branch**: Created and switched to `yaoyi/instance-a-setup`; synchronized with the latest changes from `main`.
- **Secret Generation**: Successfully generated deployment secrets (`SecretKeyBase`, `OtpSecret`, VAPID keys, and Active Record encryption keys).
- **Domain Setup**:
  - Purchased domain: `mastodon-yaoyi.online`
  - Created a hosted zone in Route 53
  - Updated Namecheap nameservers to the NS records provided by Route 53

## Deployment History & Debugging

### Template Evolution
- **v1**: Removed SES dependency, but still kept the original S3 + CloudFront architecture.
- **v2**: Removed CloudFront and changed S3 to public-read access.
- **v3**: Removed S3 integration entirely.
- **v4**: Removed template-managed Route 53 / ACM resources and switched to HTTP only.
- **v5**: Explicitly disabled VPC Flow Logs with `FlowLog: false`.

### Attempt 1 — Template: `v2`
- **Status**: `FAILED`
- **Root Cause**: `BucketPolicyPublic` creation failed in the nested `Bucket` stack.
- **Analysis**: AWS Academy Learner Lab appears to block public-read S3 bucket policy creation or related account-level public access settings.

### Attempt 2 — Template: `v3`
- **Status**: `FAILED`
- **Root Cause**: `FlowLogModule` failed in the nested `Vpc` stack.
- **Analysis**: VPC Flow Logs likely require IAM permissions or service integrations not available in Learner Lab.

### Attempt 3 — Template: `v4`
- **Status**: `FAILED`
- **Root Cause**: `FlowLogModule` failed again in the nested `Vpc` stack.
- **Analysis**: Simply removing the Flow Log parameters from the template was not enough. The underlying VPC module appears to fall back to its default Flow Log behavior unless Flow Logs are explicitly disabled.

### Attempt 4 — Template: `v5`
- **Status**: `FAILED`
- **Root Cause**: `TaskRole` and `TaskExecutionRole` failed in the nested `WebService` stack.
- **Analysis**: The deployment progressed further than previous attempts and successfully created core infrastructure components such as VPC, ALB, RDS, and Redis. However, AWS Academy Learner Lab appears to block creation of ECS task-related IAM roles required by the Mastodon application services.

## Current Conclusion
- The main blocker is no longer storage, DNS, or Flow Logs.
- The current limiting factor is Learner Lab IAM restrictions on ECS task role creation.
- The original ECS/Fargate + CloudFormation deployment path is not a practical fit for the AWS Academy Learner Lab environment.

## Pivot Decision: EC2 + Docker Compose
Due to the IAM blockers, we have pivoted to a **Minimal Mastodon Deployment** strategy:
- **Environment**: Single AWS EC2 Instance (`t3.medium`).
- **Orchestration**: Docker Compose for local service management.
- [cite_start]**Reasoning**: This path bypasses the "IAM Role Creation" blocker while still allowing us to measure distributed system metrics like job queue latency and database load[cite: 111, 122].

## Implementation Strategy & Current Status
### Technical Fixes
* **Network Exposure**: Adjusted container bindings from `127.0.0.1:3000` to `0.0.0.0:3000` to allow external traffic.
* **Domain Validation**: Aligned the `LOCAL_DOMAIN` environment variable with `mastodon-yaoyi.online` to resolve application-layer 403 errors.
* **HTTPS Bypass**: Patched `config.force_ssl = false` in the production environment to support HTTP-only testing within the sandbox.
* **Local Image Rebuild**: Initiated a local `docker compose build` to bake the SSL patch directly into the images, ensuring configuration changes take effect.

### Environment Stabilization
* **Memory Management**: Successfully configured a **4GB Swap file** on the EC2 host. This is critical for the `t3.medium` instance to handle resource-intensive Docker builds and future load testing without OOM (Out of Memory) crashes.

## 6. Next Steps
1. **Verify Web Access**: Confirm the application is reachable via `http://mastodon-yaoyi.online:3000` after the local build completes.
2. [cite_start]**Baseline Testing**: Conduct the first "Single Instance Bottleneck" experiment using Locust to find the initial breaking point of the 4GB RAM setup[cite: 119, 122].
3. [cite_start]**Second Instance**: If the single-node setup is stable, begin deployment of Instance B to test cross-node federation[cite: 128].