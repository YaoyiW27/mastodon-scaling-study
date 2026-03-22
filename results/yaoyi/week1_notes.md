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

## Pivot Decision
After multiple template simplification attempts, we decided to pivot away from the CloudFormation/Fargate deployment path.

### New Direction
We will use a **tiny Mastodon deployment** based on:
- **EC2**
- **Docker Compose**
- a **minimal working Mastodon architecture**

### Reason for the Pivot
- Learner Lab blocks key IAM-dependent resources required by the original deployment model.
- Continued CloudFormation debugging would likely consume project time without producing a runnable Mastodon instance.
- A simpler EC2-based deployment gives us a better chance of producing:
  - a working demo
  - measurable load-testing results
  - bottleneck and federation observations
  - a stronger final report

## Next Step
- Define the new EC2 + Docker Compose deployment path
- Re-scope the project as a tiny Mastodon deployment and evaluation study
- Continue with one working instance first, then attempt a second instance for federation if time allows