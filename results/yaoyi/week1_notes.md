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
* **Status**: `FAILED`
* **Root Cause**: `BucketPolicyPublic` creation denied.
* **Analysis**: Learner Lab blocks S3 Public Access policies and associated IAM modifications.

### Attempt 2 (Template: v3)
* **Status**: `FAILED`
* **Root Cause**: `FlowLogModule` failed within the nested `Vpc` stack.
* **Analysis**: Creating VPC Flow Logs requires IAM roles/permissions that are blocked in the Lab environment.

---

### Attempt 3 (Template: v4 - "Barebone Survival" Edition)
* **Strategy**: **Infrastructure Decoupling & Protocol Downgrade.**
* **Core Logic (The "No-Go" List)**:
    * **No SES / No CloudFront**: (Carried over from v1/v2).
    * **No S3**: `S3_ENABLED=false` to avoid bucket policy errors.
    * **No VPC Flow Logs**: Hard-disabled in the VPC nested stack to avoid IAM triggers.
    * **No Auto-DNS/SSL**: Removed `HostedZone`, `Certificate`, and `Record` resources from the template.
    * **Protocol**: Switched from **HTTPS (443)** to **HTTP (80)** to remove dependency on AWS Certificate Manager (ACM) and Route 53 automated records.
* **Objective**: Achieve a "Green" status for core services (ECS, RDS, Redis).

---