# AWS Account Setup Guide — DataRails Replacement App

## Context
You're deploying a SaaS app that replaces DataRails for a customer. This guide walks you through setting up the AWS account properly from day one so you don't have to redo things later.

The account is under Dad's company. You'll have full admin access via IAM Identity Center.

---

## Phase 1: Account Creation (Dad does this — 10 minutes)

### Step 1: Create the AWS Account
1. Go to https://aws.amazon.com → "Create an AWS Account"
2. Use the COMPANY email (e.g., admin@yourcompany.com) — not a personal email
3. Account name: `[CompanyName]-prod` (or just the company name)
4. Set a strong root password → store it in a password manager and NEVER use root for daily work
5. Add a credit card (company card)
6. Select "Business" account type
7. Choose support plan: "Basic" is fine to start (upgrade to Developer if you need technical support)

### Step 2: Secure Root Account
1. Sign in as root
2. Go to IAM → MFA → enable hardware or virtual MFA on root
3. Go to Account Settings → enable "Require MFA for root" 
4. STOP using root. Everything else below is done via IAM Identity Center.

### Step 3: Enable AWS Organizations
1. Go to AWS Organizations → "Create Organization"
2. This is free and gives you the ability to add more accounts later (e.g., separate customer accounts, dev/staging)
3. Right now you'll just have one account — that's fine

### Step 4: Set Up IAM Identity Center (SSO)
1. Go to IAM Identity Center (formerly AWS SSO)
2. Enable it (takes 30 seconds)
3. Create a user for your son:
   - Username: `[son's name]`
   - Email: his email
   - Permission set: `AdministratorAccess`
4. He'll get an email with SSO portal URL + temporary password
5. He logs in, sets his own password + MFA, and now has full admin without ever touching root

### Step 5: Billing Alerts
1. Go to CloudWatch → Alarms → Create Alarm
2. Select "Billing" → "Total Estimated Charge"
3. Create alarms at: $50, $200, $500
4. Send notifications to both Dad's email and son's email
5. Also: Billing → Budgets → create a monthly budget with auto-alerts

---

## Phase 2: Infrastructure Setup (Son does this with Kiro)

### What to Tell Kiro
Copy this into your Kiro chat as context when you start building:

```
I'm building a SaaS application that replaces DataRails for financial planning & analysis (FP&A). 
The app needs:
- A web frontend (React or Next.js)
- A backend API (Node.js or Python)
- A database (PostgreSQL on RDS or Aurora Serverless)
- User authentication (Cognito)
- File storage (S3) for customer financial data uploads
- The ability to scale for 1 customer initially, up to 50 later

My AWS account is already set up. I'm logged in via IAM Identity Center with AdministratorAccess.
Help me set up the infrastructure using CDK (preferred) or CloudFormation.

Requirements:
- Multi-tenant architecture (start simple, one DB with tenant_id column)
- HTTPS with custom domain (when ready)
- CI/CD pipeline (CodePipeline or GitHub Actions)
- Cost-optimized for low traffic initially (use serverless where possible)
- SOC 2 readiness from day one (encryption at rest, encryption in transit, audit logging)
```

### Recommended Architecture (Cost-Optimized for Startup)

| Component | Service | Why | Est. Cost/Month |
|-----------|---------|-----|-----------------|
| Frontend | CloudFront + S3 (static site) | $0 at low traffic | ~$1 |
| API | Lambda + API Gateway | Pay per request, $0 at idle | ~$5-20 |
| Database | Aurora Serverless v2 (PostgreSQL) | Scales to zero when idle | ~$15-50 |
| Auth | Cognito | Free tier = 50K MAU | $0 |
| File Storage | S3 | Pennies per GB | ~$1 |
| Secrets | Secrets Manager | For DB creds, API keys | ~$2 |
| Monitoring | CloudWatch | Basic metrics free | ~$0 |
| **Total** | | | **~$25-75/month** |

### Day 1 Commands (after SSO login)

```bash
# Install AWS CDK
npm install -g aws-cdk

# Configure SSO profile
aws configure sso
# Follow prompts — use the SSO URL from your Identity Center email

# Bootstrap CDK in your account
cdk bootstrap aws://ACCOUNT_ID/us-east-1

# Create your project
mkdir datarails-replacement && cd datarails-replacement
cdk init app --language typescript
```

---

## Phase 3: Security Checklist (Do This Week 1)

- [ ] MFA on root account
- [ ] MFA on your IAM Identity Center user
- [ ] Billing alerts set
- [ ] CloudTrail enabled (it is by default but verify)
- [ ] S3 buckets: block public access by default
- [ ] RDS/Aurora: encryption at rest enabled (default in Aurora Serverless v2)
- [ ] All secrets in Secrets Manager (never hardcode in code)
- [ ] VPC: database in private subnet, only Lambda/API in public
- [ ] Enable GuardDuty (threat detection — free trial 30 days)
- [ ] Tag everything with `project=datarails-replacement` for cost tracking

---

## Phase 4: When You Get Your First Paying Customer

- Set up a separate AWS account for production (AWS Organizations makes this easy)
- Or keep it in the same account with proper tagging
- Set up automated backups (Aurora handles this by default)
- Consider AWS Backup for S3 versioning
- Set up a WAF (Web Application Firewall) in front of API Gateway/CloudFront
- Get a custom domain, set up Route 53 + ACM certificate

---

## Tips for Working with Kiro

1. **Give Kiro context** — paste the architecture section above into chat when starting infrastructure work
2. **Use CDK** — Kiro is great at writing CDK TypeScript. Say "create a CDK stack for [component]"
3. **Ask for tests** — "write integration tests for the API" 
4. **Use steering files** — create `.kiro/steering/architecture.md` in your project with your tech decisions so Kiro follows them consistently
5. **One thing at a time** — don't ask for "build the whole app." Ask for "set up the database stack" then "set up the API stack" then "connect them"

---

## Cost Guardrails

Your biggest risk as a new AWS user is an unexpected bill. Protect yourself:

1. **Billing alerts** (set up above)
2. **AWS Budgets** — set a hard monthly budget of $100 with email alerts at 50%, 80%, 100%
3. **Never deploy GPU instances** (p3, p4, g4) unless you specifically need ML inference
4. **Use `t3.micro` or `t4g.micro`** if you need EC2 (but prefer Lambda)
5. **Aurora Serverless v2 scales to zero** — this is your friend
6. **Check Cost Explorer weekly** for the first month

---

*Created: 2026-08-09*
*For: AWS account setup for DataRails replacement SaaS app*
