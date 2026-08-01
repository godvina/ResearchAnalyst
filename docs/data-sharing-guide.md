# Data Sharing Guide — Epstein Pre-Processed Files

**For:** Solutions team members who need access to pre-processed Epstein case data  
**Date:** May 1, 2026  
**Code repo:** GitLab (latest pushed)

---

## Quick Start

The solutions team needs two things:
1. **S3 bucket access** (read-only is fine)
2. **This guide** to know where to find what

---

## S3 Buckets

### Bucket 1: `research-analyst-data-lake-974220725866`
**Region:** us-east-1  
**This is the primary data lake.** Pre-processed documents live here.

Key prefixes:
```
cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/    ← DEMO CASE (Epstein Combined) — USE THIS
cases/7f05e8d5-4492-4f19-8894-25367606db96/    ← Epstein Main (Original, larger)
cases/d72b81fc-.../                              ← Ancient Aliens (demo filler)
textract-output/DataSet11/                       ← Raw Textract JSON output (DS11)
```

### Bucket 2: `doj-cases-974220725866-us-east-1`
**Region:** us-east-1  
**This has the raw source PDFs and pre-extracted text.**

Key prefixes:
```
textract-output/DataSet1/    ← Pre-extracted text JSONs (DS1)
textract-output/DataSet2/    ← Pre-extracted text JSONs (DS2)
textract-output/DataSet3/    ← Pre-extracted text JSONs (DS3)
textract-output/DataSet4/    ← Pre-extracted text JSONs (DS4)
textract-output/DataSet5/    ← Pre-extracted text JSONs (DS5)
pdfs/                        ← Raw PDF files
bw-documents/                ← Black & white document scans
```

---

## What's in Each Case

### Demo Case: `ed0b6c27-3b6b-4255-b9d0-efe8f4383a99` (Epstein Combined)
**This is the case to use for demos.** Do NOT break it.

Location: `s3://research-analyst-data-lake-974220725866/cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/`

Contents:
- **Phase 1 (DS1-5):** 1,676 documents (2,128 blanks filtered from 3,804 source files)
- **Phase 2 (DS11):** 3,466 documents (1,534 blanks filtered from 5,000 source files)
- **Additional batches:** ~1,000+ documents from raw PDF processing
- **Total:** ~6,000+ pre-processed documents

Each document in S3 is a `.txt` file with extracted text, ready for embedding/search.

### Original Case: `7f05e8d5-4492-4f19-8894-25367606db96` (Epstein Main)
Location: `s3://research-analyst-data-lake-974220725866/cases/7f05e8d5-4492-4f19-8894-25367606db96/`

Contents:
- **Original load:** 3,362 documents
- **Batches 1-6:** ~25,000+ additional raw PDF extractions
- **Total:** ~33,000+ documents
- Also has `raw/` subfolder with source PDFs

---

## Document Format

Each processed document in S3 follows this structure:

```
cases/{case_id}/{doc_id}.txt
```

The text files contain extracted content from the original PDFs. Extraction methods used:
- **PyPDF2** — direct text extraction (fast, used when PDF has embedded text)
- **Textract OCR** — AWS Textract for scanned/image PDFs
- **Cached** — previously extracted, reused from cache

---

## How to List/Download Data

### List all documents in the demo case:
```bash
aws s3 ls s3://research-analyst-data-lake-974220725866/cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/ --recursive | head -20
```

### Count documents:
```bash
aws s3 ls s3://research-analyst-data-lake-974220725866/cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/ --recursive | wc -l
```

### Download the demo case locally:
```bash
aws s3 sync s3://research-analyst-data-lake-974220725866/cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/ ./epstein-demo-case/
```

### Download just the pre-extracted text JSONs (DS1-5):
```bash
aws s3 sync s3://doj-cases-974220725866-us-east-1/textract-output/ ./textract-output/
```

### Download raw PDFs:
```bash
aws s3 sync s3://doj-cases-974220725866-us-east-1/pdfs/ ./raw-pdfs/
aws s3 sync s3://doj-cases-974220725866-us-east-1/bw-documents/ ./bw-documents/
```

---

## Granting Access

### Option A: Cross-account S3 bucket policy (recommended for SA accounts)
Add their AWS account to the bucket policy for read-only access:

```json
{
  "Sid": "SolutionsTeamReadAccess",
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::THEIR_ACCOUNT_ID::root"
  },
  "Action": [
    "s3:GetObject",
    "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::research-analyst-data-lake-974220725866",
    "arn:aws:s3:::research-analyst-data-lake-974220725866/cases/ed0b6c27-*"
  ]
}
```

### Option B: Pre-signed URLs (quick sharing, no IAM changes)
Generate time-limited download links:

```python
import boto3
s3 = boto3.client('s3', region_name='us-east-1')
url = s3.generate_presigned_url('get_object',
    Params={'Bucket': 'research-analyst-data-lake-974220725866',
            'Key': 'cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/some-doc.txt'},
    ExpiresIn=86400)  # 24 hours
```

### Option C: S3 sync to their bucket
Copy the demo case to their bucket:

```bash
aws s3 sync \
  s3://research-analyst-data-lake-974220725866/cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/ \
  s3://THEIR-BUCKET/epstein-demo-case/
```

---

## API Access (Live Demo)

The live API is at: `https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1`

Key endpoints:
- `GET /case-files` — List all cases
- `GET /case-files/{case_id}` — Get case details
- `POST /search` — Semantic search across documents
- `POST /drill-down` — AI-powered drill-down analysis
- `POST /patterns` — Pattern discovery
- `POST /cross-case` — Cross-case analysis

---

## Important Notes

- **Demo case `ed0b6c27` must never break** — it's the primary demo case
- ~50-60% of raw source PDFs are blank (scanned blank pages) — these were filtered during ingestion
- The `textract-output/` prefixes contain JSON files with Textract results, not plain text
- The `cases/{case_id}/` prefixes contain the final processed `.txt` files ready for use
- Images were also extracted and processed via Rekognition — those are in the graph database (Neptune), not S3
