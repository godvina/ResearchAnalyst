# Investigative Intelligence Platform — Clean-Room Deployment Guide

## What's in this package

- `ResearchAnalystStack.template.json` — CloudFormation template (deploy via console or CLI)
- `deploy-clean.zip` — Lambda code package (uploaded to S3 during deploy)
- `investigator.html` — Frontend (upload to S3 after deploy)
- `schema.sql` — Aurora database schema (run via migrate script after deploy)
- This README

## Prerequisites

- AWS account with admin access (Isengard or customer account)
- Region: us-east-1 (or any commercial region with Bedrock access)
- Bedrock model access enabled for: Claude 3 Haiku, Titan Embed Text v2
- AWS CLI v2 configured with credentials

## Deployment Steps

### Step 1: Deploy CloudFormation Stack (~20 minutes)

**Option A: Console**
1. Open CloudFormation console → Create Stack → Upload Template
2. Upload `ResearchAnalystStack.template.json`
3. Stack name: `ResearchAnalystStack` (or any name)
4. Fill in parameters (defaults work for demo)
5. Check "I acknowledge that AWS CloudFormation might create IAM resources"
6. Click Create Stack → wait ~20 minutes

**Option B: CDK CLI (if you have the repo)**
```bash
cd infra/cdk
pip install -r requirements.txt
npx cdk bootstrap aws://ACCOUNT_ID/REGION
npx cdk deploy
```

### Step 2: Note the Stack Outputs

After CREATE_COMPLETE, go to the Outputs tab and note:
- `ApiGatewayUrl` — your API endpoint (e.g., https://xxxxx.execute-api.us-east-1.amazonaws.com/v1)
- `DataBucketName` — S3 bucket for data and frontend
- `AuroraClusterEndpoint` — Aurora cluster endpoint
- `RdsProxyEndpoint` — RDS Proxy endpoint

### Step 3: Run Aurora Migrations

```bash
# Option A: Via the migrate Lambda (if available)
python scripts/migrate_via_lambda.py

# Option B: Connect to Aurora directly and run schema.sql
# Use the RDS Proxy endpoint from Stack Outputs
# Credentials are in Secrets Manager (see AURORA_SECRET_ARN in Lambda env vars)
```

### Step 4: Upload Lambda Code

The CDK deploy packages Lambda code automatically. If deploying via CloudFormation console template, the Lambda code is embedded in the template via CDK asset.

If you need to update Lambda code later:
```bash
aws s3 cp deploy-clean.zip s3://DATA_BUCKET_NAME/deploy/lambda-update.zip
aws lambda update-function-code --function-name LAMBDA_FUNCTION_NAME --s3-bucket DATA_BUCKET_NAME --s3-key deploy/lambda-update.zip
```

### Step 5: Upload Frontend

```bash
aws s3 cp investigator.html s3://DATA_BUCKET_NAME/frontend/investigator.html --content-type "text/html"
```

Access the frontend at: `https://DATA_BUCKET_NAME.s3.amazonaws.com/frontend/investigator.html`

### Step 6: Create a Test Case

1. Open the frontend URL in a browser
2. Click "New Case" → enter a name (e.g., "Test Case")
3. The case will appear in the sidebar

### Step 7: Load Sample Data (Optional)

Upload sample text files to S3:
```bash
aws s3 cp sample-data/ s3://DATA_BUCKET_NAME/cases/CASE_ID/raw/ --recursive
```

Then trigger the batch loader:
```bash
python scripts/batch_loader.py --confirm --max-batches 1
```

Or use the HuggingFace loader for quick text data:
```bash
pip install datasets huggingface_hub
python scripts/load_huggingface_text.py --skip-entity-extraction --skip-embeddings
```

### Step 8: Verify

```bash
# Check API health
curl API_GATEWAY_URL/health

# Check case stats
curl API_GATEWAY_URL/case-files
```

## Estimated Costs

| Component | Idle Cost | Active Cost |
|-----------|-----------|-------------|
| Aurora Serverless v2 | ~$5/day | ~$15/day |
| Neptune Serverless | ~$3/day | ~$10/day |
| Lambda | ~$0/day | ~$1/day |
| S3 | ~$0.02/GB/month | same |
| API Gateway | ~$0/day | ~$0.50/day |
| Total | ~$8-10/day | ~$25-50/day |

## Cleanup

```bash
# Delete the stack (removes all resources)
aws cloudformation delete-stack --stack-name ResearchAnalystStack

# Or via CDK
npx cdk destroy
```

Note: If S3 removal policy is RETAIN (production config), the S3 bucket will NOT be deleted. Delete it manually if needed.
