# Yaoyi Week 1 Notes

## Goal
Deploy Instance A in the AWS Academy Learner Lab using a progressively simplified Mastodon CloudFormation template.

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
- **Status**: In progress
- **Root Change**: Explicitly disabled VPC Flow Logs with `FlowLog: false`.
- **Reason**: Removing the Flow Log settings alone still triggered the nested `FlowLogModule`.
- **Objective**: Achieve a successful deployment of the minimum working infrastructure:
  - ALB
  - ECS
  - RDS
  - Redis