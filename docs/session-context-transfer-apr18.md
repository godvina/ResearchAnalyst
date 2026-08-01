# Session Context Transfer — April 18, 2026

## NEXT SESSION: Continue from here

### What Happened This Session

**Entity Extraction Load — Root Cause Found and Fixed:**

1. **Root cause identified**: The `entities` table has `UNIQUE(case_file_id, canonical_name, entity_type)`. The backfill's `ON CONFLICT DO UPDATE SET document_id = EXCLUDED.document_id` overwrote previous docs' links, causing the `NOT EXISTS` query to find the same docs again. Docs were re-processed infinitely for 20+ hours with only ~300 actually completing.

2. **Fix deployed**: Created `entity_extraction_done` tracking table. Each processed doc gets tracked independently of the entities table. Batch query uses `LEFT JOIN ... WHERE IS NULL` instead of `NOT EXISTS` on entities.

3. **Bedrock Batch Inference**: Switched from serial invoke_model (237 days estimated) to Bedrock Batch Inference API:
   - Generated 75,069 JSONL prompts from Aurora docs → S3 (~4 min)
   - Submitted batch job to Amazon Nova Lite (Claude Haiku was legacy/unsupported)
   - Bedrock processed all 75K docs internally (~30 min)
   - EC2 loading results into Aurora (~60-90 min, currently running)

4. **Auto-chain running**: Background process monitors the Aurora load. When complete, it automatically:
   - Refreshes case stats
   - Cleans noise entities
   - Launches Neptune sync EC2

### Currently Running

| Process | Instance | Status | What It Does |
|---------|----------|--------|-------------|
| Aurora result loader | `i-0aa1a66b083a0c35d` | Running | Loading 75K Bedrock batch results into Aurora entities table |
| Auto-chain poller | Background (Kiro terminal 7) | Running | Monitors load, then triggers Neptune sync |
| Neptune sync | Not yet launched | Queued | Will launch automatically when load completes |

### Bedrock Batch Job Details
- **Job ARN (v3 — working)**: `arn:aws:bedrock:us-east-1:974220725866:model-invocation-job/ldhi23bwhsje`
- **Model**: Amazon Nova Lite v1 (Claude Haiku was legacy, Claude 3.5 Haiku not supported for batch in us-east-1)
- **Input**: `s3://research-analyst-data-lake-974220725866/batch-inference/entity-extraction/{case_id}/input/`
- **Output**: `s3://research-analyst-data-lake-974220725866/batch-inference/entity-extraction/{case_id}/output-v3/`
- **Records**: 75,069
- **Status**: Completed ✅

### Issues Encountered and Fixed Today

1. **Infinite re-processing loop** (Issue 43-44): ON CONFLICT overwrites document_id → same docs found again
2. **ALTER TABLE locked Aurora** (Issue 45): Adding column with DEFAULT to 82K-row table locked entire DB for 45+ min. Had to reboot Aurora.
3. **Parallel workers saturated Lambda** (Issue 43): 10 workers → all Lambda invocations timeout. 3 workers → same. Must use separate Lambda for parallel extraction.
4. **EC2 S3 AccessDenied**: NikityLoaderEC2Role didn't have s3:PutObject. Fixed with `scripts/s3_batch_policy.json`.
5. **EC2 boto3 too old for Bedrock batch**: AMI has Python 3.7 / boto3 1.33 which lacks `create_model_invocation_job`. Submitted from local Python instead.
6. **Claude Haiku legacy**: `anthropic.claude-3-haiku-20240307-v1:0` marked legacy, can't use for batch. Claude 3.5 Haiku not supported for batch in us-east-1. Amazon Nova Lite works.
7. **Anthropic format rejected by Nova**: `max_tokens` and `anthropic_version` not accepted. Nova uses `inferenceConfig.maxTokens` and `messages[].content[].text` format.

### Case Builder / Prosecution Readiness
- **Backend**: Deployed and working (fixed `suspects` UnboundLocalError)
- **Frontend**: Deployed with mode toggle
- **Tested**: 30 persons scored on Combined case

### AI Investigator Question Click
- Fixed `aiInvAskQuestion` to re-rank person list based on question category
- Auto-selects first person in re-ranked list
- Not yet deployed to S3 frontend (local change only)

### Key Infrastructure
- Lambda: `ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq`
- API: `https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1`
- Epstein Main: `7f05e8d5-4492-4f19-8894-25367606db96` (82,529 docs)
- Epstein Combined: `ed0b6c27-3b6b-4255-b9d0-efe8f4383a99` (demo case, working)
- Bedrock Batch IAM Role: `BedrockBatchInferenceRole`

### Scripts Created This Session
- `scripts/bedrock_batch_entity_extraction.py` — Local CLI for batch inference (generate/submit/status/load)
- `scripts/ec2_batch_generate_submit.py` — EC2 unattended JSONL generation + batch submission
- `scripts/ec2_load_batch_results.py` — EC2 loads batch output into Aurora
- `scripts/auto_chain_after_load.py` — Monitors load, chains Neptune sync
- `scripts/submit_batch_job.py` / `scripts/submit_nova_batch.py` — Local batch job submission
- `scripts/check_batch_status.py` — Quick batch job status check
- `scripts/s3_batch_policy.json` — IAM policy for EC2 S3/Bedrock access

### Still TODO After Load Completes
1. ✅ Aurora load (running now)
2. ✅ Stats refresh (auto-chained)
3. ✅ Noise cleanup (auto-chained)
4. ✅ Neptune sync (auto-chained)
5. Deploy frontend to S3 (AI Investigator question click fix)
6. Test AI Investigator on Epstein Main with new entities
7. Test Case Builder on Epstein Main
8. Fix AI Investigator / Case Builder UI issues user reported
