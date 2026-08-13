#!/usr/bin/env python3
"""Epstein Files — Tiered Processing Pipeline (Cost-Optimized)

Tier 1: FREE keyword/regex scan — filter 345K files to ~30-50K "interesting" ones
Tier 2: Cheap embedding ($3-5) — Titan Embed on filtered set only
Tier 3: Targeted deep scan ($10-15) — Claude Haiku entity extraction on top k-NN matches

Total estimated cost: ~$17-20 instead of $200 for full dataset.

Usage:
    python scripts/epstein_tiered_scan.py --tier 1              # Just keyword filter ($0)
    python scripts/epstein_tiered_scan.py --tier 2              # Embed filtered set ($5)
    python scripts/epstein_tiered_scan.py --tier 3              # Deep scan top matches ($12)
    python scripts/epstein_tiered_scan.py --tier all            # Run full pipeline
    python scripts/epstein_tiered_scan.py --tier 1 --dry-run    # Preview without S3 reads
"""
import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import boto3

# ============================================================
# Configuration
# ============================================================

REGION = "us-east-1"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
DATA_LAKE_BUCKET = "research-analyst-data-lake-974220725866"
DATASETS = ["DataSet1", "DataSet2", "DataSet3", "DataSet4", "DataSet5"]
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

EMBED_MODEL = "amazon.titan-embed-text-v2:0"
HAIKU_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"

# Tier 1 output
TIER1_OUTPUT = "scripts/epstein_tier1_filtered.json"
# Tier 2 output
TIER2_OUTPUT = "scripts/epstein_tier2_embeddings.json"
# Tier 3 output
TIER3_OUTPUT = "scripts/epstein_tier3_entities.json"

# Read full file for Tier 1 (most files are <5KB, and we need the extractedText field)
TIER1_READ_FULL = True
# How many files to embed in Tier 2
TIER2_MAX_FILES = 50000
# How many top matches to deep-scan in Tier 3
TIER3_TOP_K = 10000

# ============================================================
# Tier 1: Keyword/Regex Filter Patterns
# ============================================================

# High-value keywords that indicate investigative relevance
KEYWORD_PATTERNS = {
    "financial": [
        "wire transfer", "offshore", "foundation", "trust fund",
        "LLC", "shell company", "holdings", "account", "payment",
        "transaction", "billion", "million", "laundering", "invoice",
        "bank", "deposit", "withdrawal", "signatory", "beneficiary",
    ],
    "names_associates": [
        "ghislaine", "maxwell", "epstein", "wexner", "brunel",
        "dershowitz", "andrew", "prince", "clinton", "trump",
        "gates", "black", "dubin", "lolita express", "teala",
        "nadia", "virginia", "giuffre", "roberts", "farmer",
    ],
    "locations": [
        "little st. james", "zorro ranch", "new york mansion",
        "71st street", "palm beach", "paris apartment", "ohio",
    ],
    "suppression_indicators": [
        "classified", "sealed", "redacted", "NDA", "confidential",
        "non-prosecution", "immunity", "plea deal", "settlement",
        "destroyed", "shredded", "missing", "deleted", "wiped",
    ],
    "trafficking_indicators": [
        "massage", "recruit", "underage", "minor", "victim",
        "flight log", "passenger", "manifest", "modeling",
        "talent", "scout", "young", "girl", "school",
    ],
    "legal_procedural": [
        "deposition", "testimony", "sworn", "affidavit", "subpoena",
        "grand jury", "indictment", "prosecution", "FBI", "DOJ",
        "investigation", "detective", "agent", "interview",
    ],
    "organizational": [
        "JPMorgan", "Deutsche Bank", "Citibank", "Bear Stearns",
        "Victoria's Secret", "MC2", "Harvard", "MIT", "Gratitude",
        "COUQ Foundation", "Butterfly", "Les Wexner", "Southern Trust",
    ],
}

# Regex patterns for structured data
REGEX_PATTERNS = {
    "phone_number": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    "dollar_amount": r'\$[\d,]+\.?\d{0,2}',
    "date_range": r'\b(19|20)\d{2}\b',
    "email": r'\b[\w.-]+@[\w.-]+\.\w+\b',
    "account_number": r'\b\d{6,12}\b',
    "flight_reference": r'\b(N\d{3,5}[A-Z]{0,2}|tail.?number)\b',
}

# Minimum keyword hits to consider a file "interesting"
MIN_KEYWORD_HITS = 2
# Categories that make a file interesting even with 1 hit
HIGH_VALUE_CATEGORIES = ["financial", "names_associates", "trafficking_indicators"]


# ============================================================
# Helper functions
# ============================================================

def _compile_patterns():
    """Pre-compile all regex patterns for speed."""
    compiled = {}
    for name, pattern in REGEX_PATTERNS.items():
        compiled[name] = re.compile(pattern, re.IGNORECASE)
    return compiled


COMPILED_REGEX = _compile_patterns()


def score_text_tier1(text: str) -> dict:
    """Score a text snippet against keyword and regex patterns.
    
    Returns dict with category hits, total score, and whether to keep.
    """
    text_lower = text.lower()
    hits = {}
    total_hits = 0
    high_value_hit = False

    # Keyword scoring
    for category, keywords in KEYWORD_PATTERNS.items():
        category_hits = []
        for kw in keywords:
            if kw.lower() in text_lower:
                category_hits.append(kw)
        if category_hits:
            hits[category] = category_hits
            total_hits += len(category_hits)
            if category in HIGH_VALUE_CATEGORIES:
                high_value_hit = True

    # Regex scoring
    regex_hits = {}
    for name, pattern in COMPILED_REGEX.items():
        matches = pattern.findall(text)
        if matches:
            regex_hits[name] = len(matches)
            total_hits += len(matches)

    # Decision: keep if enough hits or high-value category match
    keep = total_hits >= MIN_KEYWORD_HITS or high_value_hit

    return {
        "keyword_hits": hits,
        "regex_hits": regex_hits,
        "total_score": total_hits,
        "keep": keep,
    }

# ============================================================
# Tier 1: FREE Keyword/Regex Scan
# ============================================================

def run_tier1(dry_run=False, max_files=None):
    """Scan all Textract files with keyword/regex filter.
    
    Reads first 1KB of each file. Cost: $0 (S3 GET requests only).
    Estimated S3 cost for 345K GETs: ~$0.17
    """
    print("=" * 70)
    print("TIER 1: Keyword/Regex Filter (FREE)")
    print("=" * 70)
    print(f"Source: s3://{SOURCE_BUCKET}/textract-output/")
    print(f"Reading full file content (avg <5KB per file)")
    print(f"Min keyword hits to keep: {MIN_KEYWORD_HITS}")
    print(f"High-value categories (1 hit = keep): {HIGH_VALUE_CATEGORIES}")
    print()

    s3 = boto3.client("s3", region_name=REGION)

    # Phase 1: List all files
    print("Phase 1: Listing all Textract files...")
    all_files = []
    for ds in DATASETS:
        prefix = f"textract-output/{ds}/"
        paginator = s3.get_paginator("list_objects_v2")
        ds_count = 0
        for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".json") and obj["Size"] > 100:
                    all_files.append({"key": obj["Key"], "size": obj["Size"]})
                    ds_count += 1
        print(f"  {ds}: {ds_count} valid files")

    print(f"\n  TOTAL: {len(all_files)} files to scan")

    if max_files:
        all_files = all_files[:max_files]
        print(f"  (Limited to {max_files} for testing)")

    if dry_run:
        print("\n  [DRY RUN] Would scan these files. Exiting.")
        return all_files

    # Phase 2: Read and score each file
    print(f"\nPhase 2: Scanning {len(all_files)} files...")
    start = time.time()
    kept_files = []
    discarded = 0
    category_stats = defaultdict(int)
    batch_size = 100
    processed = 0

    def scan_file(file_info):
        """Read full file and score against keywords."""
        try:
            obj = s3.get_object(
                Bucket=SOURCE_BUCKET,
                Key=file_info["key"],
            )
            raw = obj["Body"].read().decode("utf-8", errors="ignore")
            # Parse Textract JSON to get extractedText
            try:
                data = json.loads(raw)
                text = data.get("extractedText", raw)
            except json.JSONDecodeError:
                text = raw  # Use raw content for keyword matching

            score = score_text_tier1(text)
            return file_info, score
        except Exception as e:
            return file_info, {"keep": False, "error": str(e)[:100]}

    # Process with thread pool for speed
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(scan_file, f): f for f in all_files}
        for future in as_completed(futures):
            file_info, score = future.result()
            processed += 1

            if score.get("keep"):
                kept_files.append({
                    "key": file_info["key"],
                    "size": file_info["size"],
                    "score": score["total_score"],
                    "categories": list(score.get("keyword_hits", {}).keys()),
                    "regex_matches": score.get("regex_hits", {}),
                })
                for cat in score.get("keyword_hits", {}).keys():
                    category_stats[cat] += 1
            else:
                discarded += 1

            if processed % 1000 == 0:
                elapsed = time.time() - start
                rate = processed / elapsed
                remaining = (len(all_files) - processed) / rate
                print(f"  Progress: {processed}/{len(all_files)} "
                      f"({len(kept_files)} kept, {discarded} discarded) "
                      f"~{remaining:.0f}s remaining")

    elapsed = time.time() - start
    # Sort by score descending
    kept_files.sort(key=lambda x: x["score"], reverse=True)

    # Results
    print(f"\n{'='*70}")
    print(f"TIER 1 RESULTS")
    print(f"{'='*70}")
    print(f"  Scanned: {len(all_files)} files in {elapsed:.1f}s")
    print(f"  Kept (interesting): {len(kept_files)} ({len(kept_files)/len(all_files)*100:.1f}%)")
    print(f"  Discarded (junk): {discarded} ({discarded/len(all_files)*100:.1f}%)")
    print(f"\n  Category breakdown (files matching):")
    for cat, count in sorted(category_stats.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")
    print(f"\n  Top 10 highest-scoring files:")
    for f in kept_files[:10]:
        print(f"    Score {f['score']:3d} | {f['key'].split('/')[-1][:50]} | {f['categories']}")

    # Cost estimate for Tier 2
    embed_cost = len(kept_files) * 0.0001
    print(f"\n  TIER 2 COST ESTIMATE:")
    print(f"    Files to embed: {len(kept_files)}")
    print(f"    Titan Embed cost: ~${embed_cost:.2f}")
    print(f"    (vs ${len(all_files) * 0.0001:.2f} for full dataset)")
    print(f"    SAVINGS: ${(len(all_files) - len(kept_files)) * 0.0001:.2f}")

    # Save results
    output = {
        "tier": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_bucket": SOURCE_BUCKET,
        "total_scanned": len(all_files),
        "total_kept": len(kept_files),
        "total_discarded": discarded,
        "filter_rate": round(len(kept_files) / len(all_files) * 100, 1),
        "elapsed_seconds": round(elapsed, 1),
        "category_stats": dict(category_stats),
        "files": kept_files,
    }
    with open(TIER1_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {TIER1_OUTPUT}")

    return kept_files

# ============================================================
# Tier 2: Titan Embed on Filtered Set
# ============================================================

def run_tier2(input_file=None, max_files=None):
    """Embed filtered files via Titan Embed Text v2.
    
    Reads full text of each kept file, generates embeddings.
    Cost: ~$0.0001 per doc = $5 for 50K files.
    """
    print("=" * 70)
    print("TIER 2: Titan Embedding (Filtered Set Only)")
    print("=" * 70)

    # Load Tier 1 results
    input_path = input_file or TIER1_OUTPUT
    if not os.path.exists(input_path):
        print(f"ERROR: Tier 1 results not found at {input_path}")
        print("Run --tier 1 first.")
        return []

    with open(input_path, "r", encoding="utf-8") as f:
        tier1_data = json.load(f)

    files = tier1_data["files"]
    if max_files:
        files = files[:max_files]

    print(f"  Input: {len(files)} files from Tier 1")
    print(f"  Embedding model: {EMBED_MODEL}")
    print(f"  Estimated cost: ~${len(files) * 0.0001:.2f}")
    print()

    s3 = boto3.client("s3", region_name=REGION)
    bedrock = boto3.client("bedrock-runtime", region_name=REGION)

    embedded_files = []
    errors = 0
    start = time.time()

    for i, file_info in enumerate(files):
        try:
            # Read full text
            obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=file_info["key"])
            raw = obj["Body"].read().decode("utf-8", errors="ignore")
            try:
                data = json.loads(raw)
                text = data.get("extractedText", "")
            except json.JSONDecodeError:
                text = raw

            if not text or len(text) < 50:
                continue

            # Truncate to 8000 chars (Titan limit is ~8192 tokens)
            text_truncated = text[:8000]

            # Generate embedding
            resp = bedrock.invoke_model(
                modelId=EMBED_MODEL,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text_truncated}),
            )
            body = json.loads(resp["body"].read())
            embedding = body["embedding"]

            embedded_files.append({
                "key": file_info["key"],
                "score": file_info["score"],
                "categories": file_info["categories"],
                "text_length": len(text),
                "text_preview": text[:200],
                "embedding": embedding,
            })

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error on {file_info['key']}: {str(e)[:100]}")

        if (i + 1) % 500 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            remaining = (len(files) - i - 1) / rate
            cost_so_far = len(embedded_files) * 0.0001
            print(f"  Progress: {i+1}/{len(files)} embedded "
                  f"(${cost_so_far:.2f} spent, ~{remaining:.0f}s remaining)")

        # Rate limit: Titan allows ~100 TPS
        if (i + 1) % 100 == 0:
            time.sleep(1)

    elapsed = time.time() - start

    print(f"\n{'='*70}")
    print(f"TIER 2 RESULTS")
    print(f"{'='*70}")
    print(f"  Embedded: {len(embedded_files)} files in {elapsed:.1f}s")
    print(f"  Errors: {errors}")
    print(f"  Cost: ~${len(embedded_files) * 0.0001:.2f}")
    print(f"  Rate: {len(embedded_files)/elapsed:.1f} docs/sec")

    # Save results (embeddings are large — save as JSONL for streaming)
    print(f"\n  Saving embeddings to {TIER2_OUTPUT}...")
    with open(TIER2_OUTPUT, "w", encoding="utf-8") as f:
        for item in embedded_files:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    file_size_mb = os.path.getsize(TIER2_OUTPUT) / (1024 * 1024)
    print(f"  Output size: {file_size_mb:.1f} MB")
    print(f"  Ready for Tier 3 k-NN scoring.")

    return embedded_files

# ============================================================
# Tier 3: Claude Haiku Deep Scan on Top k-NN Matches
# ============================================================

# Taxonomy signatures for k-NN scoring (local cosine similarity)
EPSTEIN_TAXONOMY_SIGNATURES = {
    "financial_network": (
        "Offshore banking transactions, shell companies, trust funds used to move "
        "large sums of money between entities with hidden beneficial ownership."
    ),
    "trafficking_operations": (
        "Recruitment of young women and girls through modeling agencies, massage "
        "services, and personal referrals for exploitation and trafficking."
    ),
    "evidence_suppression": (
        "Destruction, sealing, or classification of documents, witness intimidation, "
        "and non-prosecution agreements that prevent investigation."
    ),
    "institutional_complicity": (
        "Banks, universities, intelligence agencies, or government officials who "
        "enabled, facilitated, or ignored criminal activity for personal gain."
    ),
    "network_hierarchy": (
        "Organizational structure showing recruiters, handlers, financiers, "
        "beneficiaries, and enablers in a criminal enterprise."
    ),
    "victim_testimony": (
        "Sworn depositions, affidavits, and witness statements describing "
        "abuse, coercion, trafficking, and exploitation of minors."
    ),
    "flight_travel_patterns": (
        "Private jet travel logs, flight manifests, passport records showing "
        "movement patterns between properties and international locations."
    ),
    "legal_obstruction": (
        "Actions by prosecutors, judges, or attorneys that limited investigation "
        "scope, granted unusual immunity, or sealed critical evidence."
    ),
    "cross_entity_financial": (
        "Money flows between Epstein, associates, foundations, universities, "
        "and political entities suggesting quid pro quo arrangements."
    ),
    "surveillance_blackmail": (
        "Hidden cameras, recordings, compromising materials used for leverage, "
        "intelligence connections, and coercive control over powerful people."
    ),
}


def cosine_similarity(vec_a, vec_b):
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def run_tier3(input_file=None, max_files=None):
    """Score embedded files against taxonomy, then Claude Haiku on top matches.
    
    Phase A: Local cosine similarity against taxonomy signatures (~$0.50 for embeddings)
    Phase B: Claude Haiku entity extraction on top-scoring files (~$12 for 10K docs)
    """
    print("=" * 70)
    print("TIER 3: Taxonomy Scoring + Claude Haiku Deep Extraction")
    print("=" * 70)

    # Load Tier 2 embeddings
    input_path = input_file or TIER2_OUTPUT
    if not os.path.exists(input_path):
        print(f"ERROR: Tier 2 results not found at {input_path}")
        print("Run --tier 2 first.")
        return []

    print(f"  Loading embeddings from {input_path}...")
    embedded_files = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                embedded_files.append(json.loads(line))
    print(f"  Loaded {len(embedded_files)} embedded documents")

    bedrock = boto3.client("bedrock-runtime", region_name=REGION)

    # Phase A: Embed taxonomy signatures and compute local k-NN
    print(f"\n  Phase A: Embedding {len(EPSTEIN_TAXONOMY_SIGNATURES)} taxonomy signatures...")
    taxonomy_embeddings = {}
    for sig_name, sig_text in EPSTEIN_TAXONOMY_SIGNATURES.items():
        resp = bedrock.invoke_model(
            modelId=EMBED_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": sig_text}),
        )
        body = json.loads(resp["body"].read())
        taxonomy_embeddings[sig_name] = body["embedding"]
        print(f"    ✓ {sig_name}")

    print(f"\n  Phase A: Scoring {len(embedded_files)} docs against taxonomy...")
    start = time.time()

    for i, doc in enumerate(embedded_files):
        doc_embedding = doc["embedding"]
        scores = {}
        for sig_name, sig_embedding in taxonomy_embeddings.items():
            sim = cosine_similarity(doc_embedding, sig_embedding)
            if sim >= 0.05:  # Titan Embed v2 (1024-dim): scores are typically 0.05-0.20
                scores[sig_name] = round(sim, 4)

        doc["taxonomy_scores"] = scores
        doc["max_taxonomy_score"] = max(scores.values()) if scores else 0.0
        doc["taxonomy_matches"] = len(scores)
        # Cross-cutting: matches 3+ different signatures above threshold
        doc["is_cross_cutting"] = len(scores) >= 3

        if (i + 1) % 5000 == 0:
            elapsed = time.time() - start
            print(f"    Scored {i+1}/{len(embedded_files)} "
                  f"({elapsed:.1f}s)")

    # Sort by taxonomy relevance
    embedded_files.sort(key=lambda x: x["max_taxonomy_score"], reverse=True)

    # Stats
    high_relevance = [d for d in embedded_files if d["max_taxonomy_score"] >= 0.10]
    medium_relevance = [d for d in embedded_files if 0.07 <= d["max_taxonomy_score"] < 0.10]
    cross_cutting = [d for d in embedded_files if d["is_cross_cutting"]]

    print(f"\n  Taxonomy scoring results:")
    print(f"    High relevance (≥0.10): {len(high_relevance)} files")
    print(f"    Medium relevance (0.07-0.10): {len(medium_relevance)} files")
    print(f"    Cross-cutting (3+ signatures): {len(cross_cutting)} files")
    print(f"\n  Top taxonomy signature coverage:")
    sig_counts = defaultdict(int)
    for doc in embedded_files:
        for sig in doc.get("taxonomy_scores", {}):
            sig_counts[sig] += 1
    for sig, count in sorted(sig_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {sig}: {count} docs")

    # Phase B: Claude Haiku deep extraction on top matches
    top_k = min(TIER3_TOP_K, len(high_relevance) + len(cross_cutting))
    candidates = embedded_files[:top_k]

    if max_files:
        candidates = candidates[:max_files]

    print(f"\n  Phase B: Claude Haiku entity extraction on top {len(candidates)} files")
    haiku_cost_estimate = len(candidates) * 0.0012  # ~$0.0012 per doc (avg)
    print(f"  Estimated cost: ~${haiku_cost_estimate:.2f}")
    print()

    s3 = boto3.client("s3", region_name=REGION)
    results = []
    errors = 0

    for i, doc in enumerate(candidates):
        try:
            # Read full text from S3
            obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=doc["key"])
            raw = obj["Body"].read().decode("utf-8", errors="replace")
            try:
                # Clean control characters before JSON parse
                clean_raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', raw)
                data = json.loads(clean_raw)
                text = data.get("extractedText", "")
            except json.JSONDecodeError:
                # If JSON parse fails, use raw text after the first quote
                text = raw[raw.find('"extractedText"'):] if '"extractedText"' in raw else raw
                # Strip JSON wrapper
                text = re.sub(r'^.*?":\s*"', '', text)
                text = text.rsplit('"', 1)[0] if text else raw

            if not text or len(text) < 50:
                continue

            # Truncate for Haiku (keep first 4000 chars for cost)
            text_for_llm = text[:4000]

            # Claude Haiku entity extraction
            prompt = f"""Extract all named entities from this Epstein case document. Focus on:
- People (names, roles, relationships)
- Organizations (banks, companies, foundations, agencies)
- Financial data (amounts, accounts, transactions)
- Locations (addresses, properties, countries)
- Dates and events
- Legal references (case numbers, depositions, agreements)
- Suspicious patterns (connections between entities)

Document text:
{text_for_llm}

Return a JSON object with:
- "entities": array of {{"name", "type", "confidence", "context"}}
- "relationships": array of {{"source", "target", "type", "evidence"}}
- "red_flags": array of strings noting suspicious patterns
- "summary": one paragraph summary of what this document reveals"""

            resp = bedrock.invoke_model(
                modelId=HAIKU_MODEL,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            haiku_result = json.loads(resp["body"].read())
            extraction_text = haiku_result["content"][0]["text"]

            # Try to parse as JSON
            try:
                extraction = json.loads(extraction_text)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                json_match = re.search(r'\{.*\}', extraction_text, re.DOTALL)
                if json_match:
                    extraction = json.loads(json_match.group())
                else:
                    extraction = {"raw_response": extraction_text[:500]}

            results.append({
                "key": doc["key"],
                "taxonomy_scores": doc["taxonomy_scores"],
                "max_taxonomy_score": doc["max_taxonomy_score"],
                "is_cross_cutting": doc["is_cross_cutting"],
                "categories": doc["categories"],
                "extraction": extraction,
            })

        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"  Error on {doc['key']}: {str(e)[:100]}")

        if (i + 1) % 100 == 0:
            cost_so_far = (i + 1) * 0.0012
            print(f"  Progress: {i+1}/{len(candidates)} extracted "
                  f"(${cost_so_far:.2f} spent, {errors} errors)")

        # Rate limit for Haiku
        if (i + 1) % 50 == 0:
            time.sleep(1)

    # Aggregate findings
    all_entities = []
    all_relationships = []
    all_red_flags = []
    entity_freq = defaultdict(int)

    for r in results:
        ext = r.get("extraction", {})
        for ent in ext.get("entities", []):
            all_entities.append(ent)
            entity_freq[ent.get("name", "unknown")] += 1
        for rel in ext.get("relationships", []):
            all_relationships.append(rel)
        for flag in ext.get("red_flags", []):
            all_red_flags.append(flag)

    print(f"\n{'='*70}")
    print(f"TIER 3 RESULTS")
    print(f"{'='*70}")
    print(f"  Documents processed: {len(results)}")
    print(f"  Errors: {errors}")
    print(f"  Total entities extracted: {len(all_entities)}")
    print(f"  Total relationships found: {len(all_relationships)}")
    print(f"  Red flags identified: {len(all_red_flags)}")
    print(f"\n  Top 20 most-referenced entities:")
    for name, count in sorted(entity_freq.items(), key=lambda x: -x[1])[:20]:
        print(f"    {name}: {count} mentions")
    print(f"\n  Sample red flags:")
    for flag in all_red_flags[:10]:
        print(f"    ⚠️  {flag}")

    # Save results
    output = {
        "tier": 3,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "documents_processed": len(results),
        "total_entities": len(all_entities),
        "total_relationships": len(all_relationships),
        "total_red_flags": len(all_red_flags),
        "top_entities": dict(sorted(entity_freq.items(), key=lambda x: -x[1])[:100]),
        "red_flags": all_red_flags[:200],
        "results": results,
    }
    with open(TIER3_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    file_size_mb = os.path.getsize(TIER3_OUTPUT) / (1024 * 1024)
    print(f"\n  Results saved to: {TIER3_OUTPUT} ({file_size_mb:.1f} MB)")

    # Cost summary
    actual_cost = len(results) * 0.0012 + len(EPSTEIN_TAXONOMY_SIGNATURES) * 0.0001
    print(f"\n  COST SUMMARY:")
    print(f"    Taxonomy embeddings: ~${len(EPSTEIN_TAXONOMY_SIGNATURES) * 0.0001:.4f}")
    print(f"    Claude Haiku extraction: ~${len(results) * 0.0012:.2f}")
    print(f"    TOTAL Tier 3: ~${actual_cost:.2f}")

    return results

# ============================================================
# Main / CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Epstein Files — Tiered Processing Pipeline (Cost-Optimized)"
    )
    parser.add_argument(
        "--tier", required=True,
        choices=["1", "2", "3", "all"],
        help="Which tier to run (1=keyword filter, 2=embed, 3=deep scan, all=full pipeline)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without making S3 reads (Tier 1 only)"
    )
    parser.add_argument(
        "--max-files", type=int, default=None,
        help="Limit number of files to process (for testing)"
    )
    parser.add_argument(
        "--input", type=str, default=None,
        help="Override input file for Tier 2/3"
    )
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  EPSTEIN FILES — TIERED PROCESSING PIPELINE                    ║")
    print("║  Cost-optimized: $17-20 instead of $200                        ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Tier 1: Keyword/regex filter (FREE — S3 reads only)")
    print(f"  Tier 2: Titan Embed filtered set (~$5)")
    print(f"  Tier 3: Claude Haiku on top matches (~$12)")
    print(f"  Total pipeline: ~$17-20")
    print()

    if args.tier == "1" or args.tier == "all":
        tier1_results = run_tier1(dry_run=args.dry_run, max_files=args.max_files)
        if args.dry_run or args.tier == "1":
            return

    if args.tier == "2" or args.tier == "all":
        run_tier2(input_file=args.input, max_files=args.max_files)
        if args.tier == "2":
            return

    if args.tier == "3" or args.tier == "all":
        run_tier3(input_file=args.input, max_files=args.max_files)

    if args.tier == "all":
        print()
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║  FULL PIPELINE COMPLETE                                        ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(f"  Tier 1 output: {TIER1_OUTPUT}")
        print(f"  Tier 2 output: {TIER2_OUTPUT}")
        print(f"  Tier 3 output: {TIER3_OUTPUT}")
        print()
        print("  Next steps:")
        print("  1. Review top entities and relationships in Tier 3 output")
        print("  2. Upload results to S3 for Lambda pipeline processing")
        print("  3. Check Neptune for cross-entity graph connections")


if __name__ == "__main__":
    main()
