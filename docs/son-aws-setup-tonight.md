# AWS Setup Tonight — DataRails Replacement App

## What You Need to Do Manually (Kiro Can't Do This Part)

These steps require a browser, credit card, and phone. Takes 10 minutes.

1. Go to https://aws.amazon.com → "Create an AWS Account"
2. Use your personal email
3. Use your personal credit/debit card (you won't be charged — Free Tier covers 12 months)
4. Account type: Personal
5. Complete verification (phone number)
6. Select "Basic Support" (free)
7. Sign in to the console

Once you're in the console:
1. Go to IAM → Security credentials (top right, click your name)
2. Enable MFA → Virtual MFA device → scan with your phone authenticator app
3. Go to IAM → Users → Create User → give it your name → attach `AdministratorAccess` policy → create access keys (CLI access)
4. Save the Access Key ID and Secret Access Key somewhere safe

## What Kiro CAN Do (Everything After Account Creation)

Once you have:
- An AWS account
- Access Key ID + Secret Access Key
- AWS CLI installed (`winget install Amazon.AWSCLI` on Windows or `brew install awscli` on Mac)

Configure your CLI:
```bash
aws configure
# Enter your Access Key ID
# Enter your Secret Access Key  
# Region: us-east-1
# Output: json
```

Then open Kiro and paste this as your first message:

---

## PASTE THIS INTO KIRO:

```
I'm building a SaaS application that replaces DataRails for financial planning & analysis (FP&A).

My AWS account is set up and my CLI is configured (aws configure is done, I have AdministratorAccess).

Here's what I need you to help me build tonight:

1. FIRST — Bootstrap CDK in my account:
   - Install CDK: npm install -g aws-cdk
   - Create project folder: mkdir fp-analytics && cd fp-analytics
   - Init: cdk init app --language typescript
   - Bootstrap: cdk bootstrap

2. THEN — Create the infrastructure stack with these components:
   - Aurora Serverless v2 PostgreSQL (scales to zero when idle)
   - Lambda functions for API (Node.js or Python)
   - API Gateway (REST)
   - S3 bucket for file uploads (financial spreadsheets)
   - Cognito User Pool for authentication
   - CloudFront + S3 for static frontend hosting

3. Architecture requirements:
   - Multi-tenant from day one (tenant_id column in every table)
   - All data encrypted at rest and in transit
   - Database in private subnet
   - API in public subnet via API Gateway
   - CORS enabled for localhost dev
   - Cost-optimized: must stay under $50/month at low usage

4. After infra, help me create:
   - Database schema for FP&A (chart of accounts, budgets, actuals, forecasts)
   - CRUD API endpoints
   - File upload endpoint that parses Excel/CSV
   - Basic React frontend with login

IMPORTANT: Use CDK for ALL infrastructure. No clicking in the console. Everything must be reproducible via `cdk deploy` so I can migrate to a production account later.

Start with step 1 (CDK bootstrap) and confirm it works before moving to step 2.
```

---

## What This Gets You

After tonight you'll have:
- A working AWS account with proper security
- CDK project that can be redeployed anywhere
- Database, API, auth, and file storage — all on Free Tier
- A starting point to build the actual application logic

## Free Tier Limits (What You Get for $0/month for 12 months)

| Service | Free Amount | More Than Enough For |
|---------|-------------|---------------------|
| Lambda | 1M requests + 400K GB-seconds | Your entire API |
| API Gateway | 1M API calls | All your endpoints |
| S3 | 5 GB storage | File uploads |
| RDS/Aurora | 750 hours t3.micro | Dev database |
| Cognito | 50,000 monthly active users | Auth for all customers |
| CloudFront | 1 TB transfer | Frontend hosting |
| DynamoDB | 25 GB + 25 read/write units | If you need NoSQL |

## Migration Plan (When You Have Your LLC — Weeks/Months from Now)

Because you built with CDK:
1. Form LLC, get EIN
2. Create new AWS account under LLC email + LLC credit card
3. `aws configure` with new account credentials
4. `cdk bootstrap` in new account
5. `cdk deploy` — entire infrastructure recreated in 5 minutes
6. Migrate data: `pg_dump` old database → `pg_restore` into new
7. Update DNS to point to new account
8. Done. Old personal account can be deleted.

## Tips

- **Don't click-create things in the AWS console.** Everything should be in CDK code. This is the #1 thing that makes migration painless.
- **Use `.env` files for secrets locally, AWS Secrets Manager in production.** Never commit secrets to git.
- **Commit to git early and often.** Your CDK code IS your infrastructure documentation.
- **Set a billing alarm:** Console → Billing → Budgets → $50/month → email alert. Do this TONIGHT.
- **If Kiro suggests something expensive** (GPU instances, NAT Gateways, Elasticsearch), ask "is there a cheaper alternative that stays in Free Tier?"

## If You Get Stuck

Common issues:
- "CDK bootstrap failed" → make sure `aws configure` is done and your access keys work. Test with `aws sts get-caller-identity`
- "Permission denied" → your IAM user needs `AdministratorAccess` policy
- "Region not available" → use `us-east-1` (it has everything)
- "Billing exceeds expectations" → check for NAT Gateway ($30/month!), use VPC endpoints instead

---

Good luck. Build it with CDK, keep it in git, and the production migration later will be trivial.
