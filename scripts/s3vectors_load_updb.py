#!/usr/bin/env python3
"""S3 Vectors COLD tier loader for the UPDB global UFO corpus (~296K reports).

Three-tier vector strategy (see .kiro/steering/preflight-checklists.md + docs):
  OpenSearch = HOT (hybrid, actively-investigated) ; Aurora pgvector = WARM (SQL-filtered) ;
  S3 Vectors = COLD (massive, cheap, infrequently full-scanned) -> this corpus.

Amazon S3 Vectors: create_vector_bucket -> create_index(dim=1024, cosine) -> put_vectors (batches)
-> query_vectors. ~90% cheaper storage than OpenSearch; ideal for the full UPDB corpus.

Embeddings via Titan Embed Text v2 (1024-dim, matches our other stores).
Resumable: skips vectors already present (tracks a local progress file).

Usage:
    python scripts/s3vectors_load_updb.py --setup                 # create bucket + index
    python scripts/s3vectors_load_updb.py --load --limit 5000     # embed+load first N (test)
    python scripts/s3vectors_load_updb.py --load                  # full corpus
    python scripts/s3vectors_load_updb.py --query "silent triangular craft radar tracked"
"""
import argparse
import json
import os
import time

import boto3

REGION = "us-east-1"
BUCKET = "research-analyst-uap-vectors"      # S3 Vectors bucket (cold tier)
INDEX = "updb-uap"                             # vector index
DIM = 1024
EMBED_MODEL = "amazon.titan-embed-text-v2:0"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPDB = os.path.join(PROJECT_ROOT, "docs", "updb", "updb_reports.json")
PROGRESS = os.path.join(PROJECT_ROOT, "scripts", "s3vectors_progress.json")

s3v = boto3.client("s3vectors", region_name=REGION)
bedrock = boto3.client("bedrock-runtime", region_name=REGION)


def setup():
    try:
        s3v.create_vector_bucket(vectorBucketName=BUCKET)
        print(f"created vector bucket {BUCKET}")
    except Exception as e:
        print(f"bucket: {str(e)[:120]}")
    # Recreate index with 'text' as NON-filterable metadata (filterable metadata is
    # capped at 2048 bytes; non-filterable holds the larger narrative snippet).
    try:
        s3v.delete_index(vectorBucketName=BUCKET, indexName=INDEX)
        print("deleted existing index to reconfigure metadata")
        time.sleep(3)
    except Exception:
        pass
    try:
        s3v.create_index(
            vectorBucketName=BUCKET, indexName=INDEX,
            dataType="float32", dimension=DIM, distanceMetric="cosine",
            metadataConfiguration={"nonFilterableMetadataKeys": ["text"]},
        )
        print(f"created index {INDEX} (dim {DIM}, cosine, text=non-filterable)")
    except Exception as e:
        print(f"index: {str(e)[:160]}")
    print(s3v.get_index(vectorBucketName=BUCKET, indexName=INDEX).get("index", {}))


def embed(text):
    r = bedrock.invoke_model(modelId=EMBED_MODEL,
                             body=json.dumps({"inputText": text[:8000]}))
    return json.loads(r["body"].read())["embedding"]


def load(limit=None):
    reports = json.load(open(UPDB, encoding="utf-8"))["reports"]
    if limit:
        reports = reports[:limit]
    done = set()
    if os.path.exists(PROGRESS):
        done = set(json.load(open(PROGRESS)))
    print(f"UPDB reports: {len(reports)} | already loaded: {len(done)}")

    batch, loaded, t0 = [], 0, time.time()
    for r in reports:
        vid = f"updb-{r['id']}"
        if vid in done:
            continue
        desc = (r.get("description") or "").strip()
        if len(desc) < 20:
            continue
        try:
            vec = embed(f"{desc}")
        except Exception as e:
            print(f"  embed err {vid}: {str(e)[:80]}"); continue
        batch.append({
            "key": vid,
            "data": {"float32": vec},
            # S3 Vectors filterable metadata is capped at 2048 bytes total.
            # Keep filter fields tiny; trim the text snippet so the whole map fits.
            "metadata": {
                "source": (r.get("source") or "")[:48],
                "country": (r.get("country") or "")[:8],
                "city": (r.get("city") or "")[:48],
                "year": str(r.get("date") or "")[:10],
                "text": desc[:2000],
            },
        })
        done.add(vid)
        if len(batch) >= 100:
            s3v.put_vectors(vectorBucketName=BUCKET, indexName=INDEX, vectors=batch)
            loaded += len(batch); batch = []
            json.dump(list(done), open(PROGRESS, "w"))
            if loaded % 1000 == 0:
                rate = loaded / (time.time() - t0)
                print(f"  loaded {loaded} ({rate:.0f}/s)")
    if batch:
        s3v.put_vectors(vectorBucketName=BUCKET, indexName=INDEX, vectors=batch)
        loaded += len(batch)
        json.dump(list(done), open(PROGRESS, "w"))
    print(f"DONE: loaded {loaded} new vectors; total done {len(done)}")


def query(text, k=5):
    vec = embed(text)
    r = s3v.query_vectors(
        vectorBucketName=BUCKET, indexName=INDEX,
        queryVector={"float32": vec}, topK=k,
        returnMetadata=True, returnDistance=True,
    )
    print(f"Top {k} for: {text}")
    for m in r.get("vectors", []):
        md = m.get("metadata", {})
        print(f"  dist={m.get('distance'):.4f} [{md.get('source')}|{md.get('country')}] {md.get('text','')[:90]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--load", action="store_true")
    ap.add_argument("--query", type=str, default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    if args.setup:
        setup()
    if args.load:
        load(args.limit)
    if args.query:
        query(args.query)


if __name__ == "__main__":
    main()
