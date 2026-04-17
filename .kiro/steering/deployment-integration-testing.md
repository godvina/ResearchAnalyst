---
inclusion: auto
---

# Deployment & Integration Testing Rules

## After Every Spec Task Execution

When implementing API endpoints or Lambda handler changes:

1. Always add an integration test that invokes `dispatch_handler` directly with a realistic API Gateway proxy event including `path`, `httpMethod`, `pathParameters`, and `resource` fields
2. Test the full routing chain: event → dispatch_handler → sub-handler → response
3. Verify the response status code is not 404 (routing works) and not 500 (handler doesn't crash)

## After Every Lambda Deployment

After building lambda-update.zip and deploying:

1. Run a smoke test against the live API endpoint to verify the new route returns a non-error response
2. Check CloudWatch logs for import errors or handler crashes on first invocation
3. If the endpoint returns 404 with "No handler for", the routing in case_files.py is not matching — check the path format

## Deployment Checklist

- Build zip: `Compress-Archive -Path src\* -DestinationPath lambda-update.zip -Force`
- Upload to S3: `aws s3 cp lambda-update.zip s3://research-analyst-data-lake-974220725866/deploy/lambda-update.zip`
- Deploy from S3: `aws lambda update-function-code --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq --s3-bucket research-analyst-data-lake-974220725866 --s3-key deploy/lambda-update.zip`
- **NEVER use `--zip-file fileb://`** — it times out for large zips (Issue 31 in lessons-learned.md)
- Smoke test: `python -c "import urllib.request; r=urllib.request.urlopen('https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/<new-endpoint>',timeout=30); print(r.status, r.read().decode()[:200])"`
- Open investigator.html in incognito (Issue 30 - cache)

## Common Failure Patterns

- API Gateway uses `/{proxy+}` — all routing is in case_files.py dispatch_handler, NOT in API Gateway resource definitions
- New routes must be added to case_files.py BEFORE any catch-all patterns
- The `path` variable in dispatch_handler comes from `event["path"]` which does NOT include the `/v1/` stage prefix
- Unit tests with mocked dependencies don't catch routing issues — always include a dispatch_handler integration test
