# Yaoyi Week 1 Notes

## Goal
Successfully deploy Instance A in the AWS Academy Learner Lab using a simplified version of `quickstart-no-ses.yml`.

## Progress Log
- **Branch**: Created and switched to `yaoyi/instance-a-setup`; synchronized with the latest changes from `main`.
- **Secret Generation**: Successfully generated deployment secrets (SecretKeyBase, OtpSecret, Vapid keys) using the Docker image `mastodon:latest`.
- **Domain Setup**:
    - Purchased domain: `mastodon-yaoyi.online`.
    - Created a Hosted Zone in Route 53.
    - Updated Namecheap Nameservers to the NS records provided by Route 53.

## Deployment History & Debugging

### Attempt 1 (Template: v2)
- **Status**: `FAILED`
- **Root Cause**: `BucketPolicyPublic` failed.
- **Analysis**: Learner Lab blocks Public S3 policies and IAM changes related to bucket permissions.

### Attempt 2 (Template: v3)
- **Status**: `FAILED`
- **Root Cause**: `FlowLogModule` failed within the nested `Vpc` stack.
- **Analysis**: Learner Lab restricts the creation of **VPC Flow Logs** because they require specific IAM permissions to publish logs to CloudWatch, which are prohibited in this environment.
- **Conclusion**: Even "standard" features like VPC monitoring are too "permission-heavy" for this lab.

### Attempt 3 (Template: v4 - The "Total Survival" Edition)
- **Strategy**: **Strip everything but the absolute essentials.**
- **Core Logic**:
    - **VPC**: Set `FlowLog: false` (or delete the parameter) to ensure the network stack can deploy without IAM intervention.
    - **S3 & CloudFront**: Completely removed (same as v3).
    - **ALB Logs**: Disable `AlbAccessLogBucket` if it continues to trigger IAM errors.
- **Objective**: Prioritize a "Green" CloudFormation status to get the Mastodon web interface live for scaling tests.

## Next Steps
- Create `quickstart-no-ses-v4.yml` by disabling VPC Flow Logs.
- Clean up any orphaned resources in the AWS Console before retrying.
- Deploy and verify if the ALB endpoint is reachable via `mastodon-yaoyi.online`.