---
inclusion: auto
---

# Entity Extraction Rules

## MANDATORY: Model Bake-Off Before Bulk Extraction

Before processing more than 100 documents through entity extraction on ANY new case or dataset:

1. Run `python scripts/model_bakeoff.py --case-id <CASE_ID>` 
2. Review the precision/cost comparison table
3. Choose the model with the best precision (not the cheapest)
4. Document the choice in `docs/model-bakeoff-{case_name}.md`

**NEVER skip this step.** See `docs/lessons-learned.md` Issue 49 for why.

## MANDATORY: Constrained Extraction Prompt

The entity extraction prompt MUST explicitly list the entity types to extract from `docs/master-entity-taxonomy.md`. Do NOT use an open-ended prompt like "extract named entities" — the model will invent hundreds of useless types.

Use this prompt template:
```
Extract ONLY the following entity types: person, organization, location, 
financial_amount, account_number, phone_number, email, address, date, event, 
flight, legal_case, statute, vehicle, substance, weapon, property, role.

Do NOT extract: document formatting, OCR artifacts, page numbers, 
generic descriptions, measurements, medical terms, food, clothing, colors.
```

## Entity Quality Thresholds

After extraction, verify quality before syncing to Neptune:
- **Minimum occurrence count**: 2 (entities in only 1 document are likely noise)
- **Minimum name length**: 3 characters
- **Maximum noise ratio**: 0.5:1 (if more than 1 noise entity per 2 real entities, the model is wrong)

## Reference Files
- `docs/master-entity-taxonomy.md` — canonical 40-type taxonomy across 10 tiers
- `docs/lessons-learned.md` — Issues 46-52 (extraction and EC2 lessons)
- `scripts/model_bakeoff.py` — automated model comparison tool
- `scripts/entity_extraction_pipeline.py` — production extraction pipeline
- `scripts/ec2_neptune_resync.py` — taxonomy-filtered Neptune sync

## MANDATORY: EC2 Pre-Flight Checklist

Before launching ANY EC2 script, verify ALL of these:

1. **IAM role permissions** — list every boto3 API call in the script, verify the EC2 role has each permission
2. **boto3 installed** — userdata must include `pip3 install boto3 || yum install -y python3-pip && pip3 install boto3`
3. **Neptune SG access** — if script queries Neptune, verify EC2 SG is in Neptune SG inbound on port 8182
4. **S3 access** — verify role has s3:GetObject + s3:PutObject for the bucket
5. **Lambda access** — if script invokes Lambda, verify role has lambda:InvokeFunction
6. **Self-terminate permission** — verify role has ec2:TerminateInstances
7. **Test locally first** — run the first page/batch locally before launching EC2

## MANDATORY: Model Output Format Verification

During the bake-off, for EACH model tested:

1. **Verify response path** — document the exact JSON path to extract text (Nova vs Anthropic format)
2. **Verify entity JSON structure** — confirm each element is a dict with name/type/confidence
3. **Test edge cases** — empty docs, OCR garbage, very long docs
4. **Build the parser during bake-off** — don't write it after choosing the model
5. **Handle all element types** — the entity array may contain dicts, lists, strings, or nulls
