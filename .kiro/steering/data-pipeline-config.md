---
inclusion: auto
---

# Data Pipeline Configuration — Always Check First

When working with the data pipeline (Lambda deploy, OpenSearch indexing, Bedrock calls, batch research), always check `docs/lessons-learned-data-pipeline.md` for the full reference. Key points below:

## Lambda Deploy
- ALWAYS use `scripts/_deploy_via_s3.py` — never direct upload (42MB times out)
- CaseFiles Lambda: `ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq`

## Bedrock Models
- Use `us.anthropic.claude-sonnet-4-6` (must have `us.` prefix for inference profiles)
- Haiku: `anthropic.claude-3-haiku-20240307-v1:0` (legacy but works)
- Handle extended thinking: iterate content blocks, find `type == "text"`

## OpenSearch Serverless
- Endpoint: `https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com`
- Use `POST /{index}/_doc` (no document ID — AOSS limitation)
- Any index name works (wildcard policy on `research-analyst-search/*`)

## API Gateway
- 29s hard timeout — keep Sonnet calls under 1000 max_tokens for sync endpoints
- For longer research: bypass API Gateway, call Bedrock directly from scripts

## Batch Research
- Set `$env:BRAVE_SEARCH_API_KEY` before running
- Use `scripts/batch_research_direct.py` (bypasses API Gateway timeout)
- Two-pass: broad first, then taxonomy-guided
