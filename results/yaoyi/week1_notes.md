# Yaoyi Week 1 Notes

## Goal
Deploy Instance A in AWS Academy Learner Lab using `quickstart-no-ses.yml`.

## Progress Log
- Created branch `yaoyi/instance-a-setup`
- Synced latest main branch
- Preparing AWS Learner Lab deployment

## Secret generation
- Generated local Mastodon deployment secrets successfully
- Will rotate secrets before actual deployment because the first set was exposed in chat
- Waiting for final domain / Route53 setup confirmation before launching stack

## Domain setup
- Purchased domain: `mastodon-yaoyi.online`
- Created Route 53 hosted zone for the domain
- Updated Namecheap nameservers to Route 53 NS records
- DNS propagation may take time, but domain delegation setup is complete

## Deployment attempt 1
- Template: `quickstart-no-ses-v2.yml`
- Result: failed
- First confirmed root cause: `BucketPolicyPublic` creation failed in nested `Bucket` stack
- Interpretation: Learner Lab likely blocks public-read S3 bucket policy
- Next step: simplify template further by removing or disabling S3