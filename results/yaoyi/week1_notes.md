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
- **Status**: `FAILED` (ROLLBACK_COMPLETE)
- **Root Cause**: Creation of `BucketPolicyPublic` in the nested stack failed.
- **Analysis**:
    - **v1 Logic**: Removed SES, retained CloudFront, set S3 to `CloudFrontRead`.
    - **v2 Logic**: Removed SES and CloudFront, attempted to set S3 to `PublicRead`.
- **Conclusion**: AWS Learner Lab strictly prohibits the creation of S3 Bucket policies with public access, which blocked the v2 deployment.

### Attempt 2 (Template: v3 - Next Step)
- **Strategy**: **"Lean & Mean"** — Remove SES, CloudFront, and S3 entirely.
- **Core Logic**:
    - **Infrastructure**: Delete all S3-related resource blocks (`Bucket`, `BucketPolicy`) from the template to bypass IAM permission restrictions.
    - **Application Config**:
        - Set environment variable `S3_ENABLED=false`.
        - Remove all `S3_*` related configurations from the ECS Task Definition.
    - **Trade-off**: Media files will be stored on the container's ephemeral local storage. For the **Scaling Study** project, this is sufficient to test core ECS and RDS performance.

## Next Steps
- Modify `quickstart-no-ses.yml` to create the v3 version.
- Re-run CloudFormation deployment to verify core functionality of Instance A.
- Once the instance is live, rotate secrets by generating a new set of production keys and update `.env.yaoyi.local`.