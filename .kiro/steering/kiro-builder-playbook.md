---
inclusion: auto
---

# Kiro Builder Playbook

This is the master operating guide for building with Kiro on AWS projects. It encodes 52+ lessons learned from real production failures, and defines the mandatory checks that prevent repeating them.

**Read this FIRST on every new session. No exceptions.**

## Session Startup Checklist

Before writing ANY code in a new session:

1. Read `docs/lessons-learned.md` — check for known issues with your approach
2. Read `docs/master-entity-taxonomy.md` — if touching entity extraction
3. Read `docs/session-context-transfer-*.md` — latest session state
4. Check for running EC2 instances: `python scripts/check_dedup_status.py`
5. Check for running Bedrock batch jobs
6. Verify the demo case (ed0b6c27) still works before making changes

---

## Phase 1: Before You Build

### 1.1 Data Quality Gate (MANDATORY for any data pipeline)

Before processing more than 100 items through ANY AI model:

- [ ] Run model bake-off: `python scripts/model_bakeoff.py --case-id <ID>`
- [ ] Test with 10 representative samples (clean, OCR, financial, legal, mixed)
- [ ] Score precision, recall, noise ratio, cost per item
- [ ] Choose model with best precision/cost ratio (not cheapest)
- [ ] Verify output JSON structure matches your parser
- [ ] Document results in `docs/model-bakeoff-{name}.md`
- [ ] Use constrained prompt listing ONLY the entity types you want (reference `docs/master-entity-taxonomy.md`)

**Why**: Nova Lite produced 75% garbage on 75K docs. Cost $15 to run, $150+ to clean up. Testing first would have caught this in 5 minutes.

### 1.2 IAM Pre-Flight (MANDATORY for any EC2/Lambda/cross-service operation)

Before launching ANY process that calls AWS APIs:

- [ ] List every `boto3.client()` and API method in the script
- [ ] Verify the IAM role/profile has permissions for each API call
- [ ] Check VPC security group access (Neptune port 8182, Secrets Manager port 443)
- [ ] Test with a single dry-run call from local before launching EC2

**Common permission matrix:**
| API Call | IAM Action |
|----------|-----------|
| Lambda invoke | lambda:InvokeFunction |
| S3 read/write | s3:GetObject, s3:PutObject |
| Bedrock batch status | bedrock:GetModelInvocationJob |
| EC2 self-terminate | ec2:TerminateInstances |
| EC2 launch (chaining) | ec2:RunInstances, iam:PassRole |

**Why**: Chain EC2 crashed with AccessDeniedException because DOJ-Processing-Role lacked lambda:InvokeFunction. Wasted 30 minutes of polling time.

### 1.3 EC2 Userdata Template (MANDATORY for any EC2 script)

Always use this template — never write userdata from scratch:

```bash
#!/bin/bash
set -e
BUCKET="research-analyst-data-lake-974220725866"
REGION="us-east-1"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

echo "=== SCRIPT_NAME Starting ==="
echo "Instance: $INSTANCE_ID"
echo "Time: $(date)"

# MANDATORY: Install boto3 (NOT pre-installed on Amazon Linux 2023)
pip3 install boto3 || yum install -y python3-pip && pip3 install boto3

# Download script
aws s3 cp s3://$BUCKET/deploy/SCRIPT.py /tmp/SCRIPT.py

# Run
cd /tmp
python3 SCRIPT.py 2>&1 | tee /tmp/log.txt

# Upload log
aws s3 cp /tmp/log.txt s3://$BUCKET/logs/PREFIX/log_$(date +%Y%m%d_%H%M%S).txt

# Self-terminate
echo "=== Complete — Self-Terminating ==="
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
```

**Why**: boto3 not pre-installed on AMI caused immediate crash. `|| true` on pip install suppressed the error silently.

---

## Phase 2: While You Build

### 2.1 The 5-Minute Rule

After ANY deployment or launch:
- **T+0**: Deploy/launch
- **T+90s**: Check console output or CloudWatch logs
- **T+3min**: If no output → investigate immediately
- **T+5min**: Verify the actual metric is changing (entity count, node count, etc.)
- **Every hour**: Re-check running processes

**Never say "it's running" without verified metric increase.**

### 2.2 Code Change Rules

- **EXTEND, never REPLACE** working code
- **Clean `__pycache__`** before every Lambda deploy
- **Deploy Lambda via S3** — never use `--zip-file fileb://`
- **Test API endpoint directly** before deploying frontend
- **Check CloudWatch logs** after first deploy before telling user to test

### 2.2.1 BULK OPERATIONS — NON-NEGOTIABLE

If processing more than 100 items, you MUST use bulk operations. Individual operations are FORBIDDEN.

| Operation | WRONG (forbidden) | RIGHT (required) |
|-----------|-------------------|-----------------|
| Neptune load | Individual Gremlin addV/upsert in a loop | Neptune CSV Bulk Loader API |
| Aurora insert | Individual INSERT in a loop | execute_values() or multi-row INSERT |
| Lambda invoke | One invoke per item | Batch payload with 100+ items |
| Entity extraction | Serial invoke_model | Bedrock Batch Inference API |

This rule has been violated 5+ times. The preToolUse hook `bulk-operation-gate` now blocks writes that contain individual-operation patterns.

### 2.3 Database Rules

- **NEVER** use `ALTER TABLE ADD COLUMN DEFAULT` on large tables in Aurora Serverless
- **NEVER** insert one row at a time via Lambda for bulk loads (batch 100+)
- **NEVER** use `ON CONFLICT DO UPDATE SET document_id = EXCLUDED.document_id` on tables with UNIQUE constraints that don't include document_id
- **Always** use separate tracking tables for batch processing progress
- **Always** verify Aurora `documents` table row count matches expected after ingestion

### 2.4 Neptune Rules

- **Always** use `__.V()` not `g.V()` for anonymous traversals in `.to()` and `.from()`
- **Always** use fold/coalesce upsert pattern for sync (not blind `addV()`)
- **Always** include `.limit()` clauses on queries for scalability
- **Always** query location nodes separately (not in a limited general query)

### 2.5 Time Estimation Rules

- **NEVER** give an estimate without showing the math: `total_items × time_per_item = total_time`
- **Add 50% buffer** to all estimates
- **If > 30 minutes**, use EC2 (laptop sleeps)
- **If > 1 hour**, tell the honest number, not the optimistic one

---

## Phase 3: Testing (MANDATORY — runs after EVERY task)

Testing is not optional. It is a formal phase that runs after every spec task execution.
The `auto-test-after-task` hook enforces this automatically.

### 3.0 Spec Process: Design → Execute → TEST → Ship

Every spec task follows this cycle:
1. **Design**: Define what to build, including test criteria
2. **Execute**: Write the code
3. **TEST**: Run `python scripts/comprehensive_test.py` — ALL endpoints, not just the one you changed
4. **Ship**: Deploy to S3/Lambda only after tests pass

### 3.1 Testing During Design

When writing requirements and design docs, include for EACH requirement:
- **Test criteria**: What specific API call proves this works?
- **Expected response**: What does success look like (status code, data shape, minimum counts)?
- **Regression check**: What existing features could this break?

### 3.2 Testing After Execution

After EVERY code change, before telling the user it works:

- [ ] Run `python scripts/comprehensive_test.py` — full endpoint test suite
- [ ] Check that ALL previously passing tests still pass (no regressions)
- [ ] For frontend changes: test every button/action that calls an API
- [ ] For backend changes: test the endpoint directly with curl/Python, not just "it deployed"
- [ ] For data changes: verify node counts, edge counts, entity counts changed as expected
- [ ] Verify demo case (ed0b6c27) still works

### 3.3 Frontend-Backend Contract Testing

Before deploying ANY frontend change to S3:
- [ ] List every `api()` call in the changed code
- [ ] Test each endpoint with the exact parameters the frontend sends
- [ ] Cross-check all string constants against backend dispatch maps
- [ ] Test in browser (incognito mode to avoid cache)

### 3.4 Verification Checklist

- [ ] Build/compile passes
- [ ] Comprehensive test suite passes (12+ endpoints)
- [ ] API endpoint returns expected response
- [ ] Frontend renders correctly
- [ ] Demo case (ed0b6c27) still works
- [ ] No regression on existing features

### 3.5 Deployment Checklist

- [ ] Clean `__pycache__`: `Get-ChildItem -Path src -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force`
- [ ] Build zip: `Compress-Archive -Path src\* -DestinationPath lambda-update.zip -Force`
- [ ] Upload to S3: `aws s3 cp lambda-update.zip s3://research-analyst-data-lake-974220725866/deploy/lambda-update.zip`
- [ ] Deploy: `aws lambda update-function-code --function-name <NAME> --s3-bucket <BUCKET> --s3-key deploy/lambda-update.zip`
- [ ] Wait 10s for function update
- [ ] Test with simple invoke
- [ ] Check CloudWatch for errors

---

## New Project / New Session Knowledge Transfer

When starting a new Kiro session on this project, share these files in the first message:

### Tier 1 — MUST READ (paste as context or reference):
1. `docs/lessons-learned.md` — all 52+ issues and their fixes
2. `.kiro/steering/kiro-builder-playbook.md` — this file (operating rules)
3. `.kiro/steering/launch-and-verify-protocol.md` — EC2/process launch rules
4. `.kiro/steering/entity-extraction-rules.md` — extraction pipeline rules

### Tier 2 — READ IF RELEVANT:
5. `docs/master-entity-taxonomy.md` — entity type hierarchy (if touching entities)
6. `docs/session-context-transfer-*.md` — latest session state
7. Active spec files (requirements.md, design.md, tasks.md) for current work

### Tier 3 — REFERENCE:
8. `src/lambdas/api/case_files.py` — the mega-dispatcher (all API routes)
9. `infra/cdk/stacks/research_analyst_stack.py` — CDK infrastructure
10. `src/db/schema.sql` — database schema

### What to tell the new session:
```
Read these files before doing anything:
- docs/lessons-learned.md
- .kiro/steering/kiro-builder-playbook.md
- .kiro/steering/launch-and-verify-protocol.md
- .kiro/steering/entity-extraction-rules.md

Key facts:
- AWS account: 974220725866, us-east-1
- Lambda: ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq
- API: https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1
- Demo case: ed0b6c27 (never break this)
- Main case: 7f05e8d5 (82K docs, 75K entities)
- Deploy Lambda via S3, never fileb://
- EC2 AMI: ami-0c1fe732b5494dc14 (needs pip3 install boto3)
- Neptune: neptunedbcluster-qoxzlhiau0ao (use __.V() not g.V())
- Always clean __pycache__ before deploy
- Always use EC2 for processes > 30 min
- Always verify EC2 console output within 2 minutes
- Check running EC2 instances on every prompt
```

---

## Anti-Patterns (Things That Have Failed)

| Anti-Pattern | Times Failed | Fix |
|-------------|-------------|-----|
| Skip model testing, use cheapest model | 1 | Model bake-off mandatory |
| Assume EC2 role has permissions | 3 | IAM pre-flight check |
| Use `pip3 install ... \|\| true` in userdata | 2 | Fail loudly, never suppress |
| Deploy Lambda via `--zip-file fileb://` | 5+ | Always use S3 intermediate |
| Assume EC2 is working because state=running | 4 | Check actual metric, not state |
| ALTER TABLE on large Aurora table | 1 | Use separate tracking table |
| Parallel Lambda workers on shared Lambda | 1 | Serial or separate Lambda |
| Terminate working EC2 to "speed up" | 1 | Never terminate working process |
| Give time estimate without math | 3+ | Show calculation every time |
| Say "go ahead and test" during write load | 1 | Wait for writes to finish |
| Use `g.V()` instead of `__.V()` in Neptune | 2 | Always use anonymous traversals |
| Skip `__pycache__` cleanup before deploy | 3 | Clean every time |
