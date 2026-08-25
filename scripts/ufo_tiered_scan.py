#!/usr/bin/env python3
"""UFO / UAP — Tiered Processing Pipeline (Cost-Optimized)

Replicates the manual MUFON pattern-hunting workflow at machine scale, using the
same tiered approach as scripts/epstein_tiered_scan.py.

Tier 1: FREE keyword/regex scan — filter the 60,632-record NUFORC corpus down to
        the "interesting" (anomaly-bearing) reports. $0, seconds.
Tier 2: Titan Embed on the filtered set only (~$0.0001/report). Optional, needs Bedrock.
Tier 3: Score embeddings against the UFO/UAP taxonomy signatures (local cosine),
        then Claude Haiku entity/pattern extraction on top matches. Optional.

The Tier-1 filter here is the important part: it applies the UFO/UAP taxonomy
(src/data/ufo-uap-taxonomy.json) as keyword signatures, scores every report across
ALL domains (cross-domain scoring is mandatory per steering), and DOWN-RANKS reports
that match the witness_reliability hoax/misidentification counter-signatures.

Usage:
    python scripts/ufo_tiered_scan.py --tier 1
    python scripts/ufo_tiered_scan.py --tier 1 --max-records 500
    python scripts/ufo_tiered_scan.py --tier 2        # needs AWS/Bedrock
    python scripts/ufo_tiered_scan.py --tier 3        # needs AWS/Bedrock
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

# Bedrock is only needed for tiers 2/3
try:
    import boto3
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

REGION = "us-east-1"
EMBED_MODEL = "amazon.titan-embed-text-v2:0"
HAIKU_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAXONOMY_PATH = os.path.join(PROJECT_ROOT, "src", "data", "ufo-uap-taxonomy.json")

# Input: prefer the seed copy, fall back to docs/
INPUT_CANDIDATES = [
    os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufo_sightings", "ufo_sightings.csv"),
    os.path.join(PROJECT_ROOT, "docs", "ufo_sightings.csv"),
]

TIER1_OUTPUT = os.path.join(PROJECT_ROOT, "scripts", "ufo_tier1_filtered.json")
TIER2_OUTPUT = os.path.join(PROJECT_ROOT, "scripts", "ufo_tier2_embeddings.jsonl")
TIER3_OUTPUT = os.path.join(PROJECT_ROOT, "scripts", "ufo_tier3_entities.json")

DESC_FIELD = "Data.Description excerpt"
SHAPE_FIELD = "Data.Shape"
CITY_FIELD = "Location.City"
STATE_FIELD = "Location.State"
LAT_FIELD = "Location.Coordinates.Latitude "
LNG_FIELD = "Location.Coordinates.Longitude "
YEAR_FIELD = "Dates.Sighted.Year"
DUR_FIELD = "Data.Encounter duration"

# ============================================================
# Tier 1: Keyword / Regex signatures
# ============================================================

# High-value anomaly keywords grouped by UFO/UAP typology. These are the FREE
# proxy for the taxonomy signatures — a report hitting these is worth embedding.
KEYWORD_PATTERNS = {
    # flight_kinematics — the highest-value physics anomalies
    "impossible_kinematics": [
        "instant", "instantly", "instantaneous", "shot off", "shot up", "sped off",
        "right angle", "90 degree", "sharp turn", "zig zag", "zigzag", "no sound",
        "silent", "accelerat", "disappeared instantly", "vanished", "hovering",
        "hovered", "stationary", "motionless", "against the wind", "changed direction",
    ],
    # sensor_em_signatures — instrumented / physical-effect corroboration
    "em_physical_effects": [
        "engine died", "engine stalled", "car stalled", "electrical", "power went out",
        "radio static", "compass", "interference", "burn", "sunburn", "radiation",
        "paralyz", "could not move", "scorched", "landing marks", "trace", "melted",
    ],
    # sensor_em_signatures — radar-visual
    "radar_visual": [
        "radar", "air traffic", "atc", "flir", "tracked", "confirmed by", "scrambled",
        "tower", "picked up on",
    ],
    # craft_morphology — structured craft (higher value than 'light')
    "structured_craft": [
        "triangle", "triangular", "delta", "disc", "disk", "saucer", "dome", "domed",
        "metallic", "cylinder", "cigar", "sphere", "spherical", "orb", "craft",
        "structured", "solid object", "windows", "portholes",
    ],
    # encounter_typology — close / multi-witness
    "encounter_quality": [
        "close range", "landed", "landing", "occupant", "figure", "being", "entity",
        "abduct", "multiple witnesses", "several people", "everyone saw", "crowd",
        "many people", "family", "we all saw",
    ],
    # witness_reliability — high-credibility observers
    "credible_witness": [
        "pilot", "police", "officer", "sheriff", "military", "air force", "navy",
        "controller", "scientist", "engineer", "retired", "trained observer",
    ],
    # institutional_response — official involvement / suppression
    "institutional": [
        "government", "military", "classified", "cover up", "cover-up", "told not to",
        "confiscated", "officials", "investigation", "base", "restricted airspace",
        "men in black", "denied",
    ],
}

# Negative signal — the ex-cop hoax/misidentification screen. Hits here DON'T
# discard the report, but they lower its priority score.
NEGATIVE_PATTERNS = {
    "likely_misid": [
        "probably a plane", "was a plane", "must have been", "satellite", "starlink",
        "chinese lantern", "sky lantern", "weather balloon", "was venus", "was the moon",
        "shooting star", "meteor", "firework", "drone", "helicopter", "flare",
        "((nuforc note", "hoax", "probably",
    ],
}

REGEX_PATTERNS = {
    "duration_reference": r'\b\d+\s?(second|minute|hour|min|sec)s?\b',
    "altitude_reference": r'\b\d{2,5}\s?(feet|ft|meters|m)\b',
    "count_of_objects": r'\b(\d{1,3})\s?(objects|lights|craft|orbs|discs|triangles)\b',
    "speed_reference": r'\b(mph|knots|km/h)\b',
}

# A report is "interesting" if it clears this many total hits, OR hits any
# high-value category even once.
MIN_KEYWORD_HITS = 2
HIGH_VALUE_CATEGORIES = ["impossible_kinematics", "em_physical_effects", "radar_visual"]


def _compile_regex():
    return {name: re.compile(p, re.IGNORECASE) for name, p in REGEX_PATTERNS.items()}


COMPILED_REGEX = _compile_regex()


def score_report_tier1(text: str, shape: str = "") -> dict:
    """Score one sighting narrative against keyword/regex/negative patterns."""
    blob = f"{text} {shape}".lower()
    hits = {}
    total = 0
    high_value = False

    for category, keywords in KEYWORD_PATTERNS.items():
        cat_hits = [kw for kw in keywords if kw in blob]
        if cat_hits:
            hits[category] = cat_hits
            total += len(cat_hits)
            if category in HIGH_VALUE_CATEGORIES:
                high_value = True

    regex_hits = {}
    for name, pat in COMPILED_REGEX.items():
        m = pat.findall(text)
        if m:
            regex_hits[name] = len(m)
            total += len(m)

    # Negative screen (does not discard; penalizes priority)
    neg_hits = []
    for kws in NEGATIVE_PATTERNS.values():
        neg_hits.extend([kw for kw in kws if kw in blob])
    penalty = len(neg_hits)

    # Priority score = anomaly hits minus prosaic-explanation penalty
    priority = total - penalty
    keep = (total >= MIN_KEYWORD_HITS) or high_value

    return {
        "keyword_hits": hits,
        "regex_hits": regex_hits,
        "negative_hits": neg_hits,
        "raw_score": total,
        "penalty": penalty,
        "priority_score": priority,
        "keep": keep,
    }


# ============================================================
# Taxonomy loading (drives Tier 3 signature scoring)
# ============================================================

def load_taxonomy_signatures():
    """Flatten ufo-uap-taxonomy.json into {signature_id: vector_text} plus metadata."""
    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        tax = json.load(f)
    sigs = {}
    for typ in tax["typologies"]:
        for method in typ["methods"]:
            for sig in method["signatures"]:
                sigs[sig["signature_id"]] = {
                    "typology": typ["typology_id"],
                    "method": method["method_id"],
                    "vector_text": sig["vector_text"],
                    "indicators": sig["indicators"],
                    "severity": sig["severity"],
                }
    return tax, sigs


# ============================================================
# Tier 1 runner
# ============================================================

def find_input():
    for p in INPUT_CANDIDATES:
        if os.path.exists(p):
            return p
    print("ERROR: ufo_sightings.csv not found", file=sys.stderr)
    sys.exit(1)


def run_tier1(max_records=None):
    src = find_input()
    print("=" * 70)
    print("TIER 1: UFO/UAP Keyword+Anomaly Filter (FREE)")
    print("=" * 70)
    print(f"Source: {src}")
    print(f"Min keyword hits to keep: {MIN_KEYWORD_HITS}")
    print(f"High-value categories (1 hit = keep): {HIGH_VALUE_CATEGORIES}")
    print()

    total = 0
    kept = []
    discarded = 0
    cat_stats = defaultdict(int)
    start = time.time()

    with open(src, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if max_records and total > max_records:
                total -= 1
                break
            desc = row.get(DESC_FIELD) or ""
            shape = row.get(SHAPE_FIELD) or ""
            score = score_report_tier1(desc, shape)
            if score["keep"]:
                kept.append({
                    "city": row.get(CITY_FIELD, ""),
                    "state": row.get(STATE_FIELD, ""),
                    "lat": row.get(LAT_FIELD, "").strip(),
                    "lng": row.get(LNG_FIELD, "").strip(),
                    "shape": shape,
                    "year": row.get(YEAR_FIELD, ""),
                    "duration": row.get(DUR_FIELD, ""),
                    "description": desc,
                    "priority_score": score["priority_score"],
                    "raw_score": score["raw_score"],
                    "penalty": score["penalty"],
                    "categories": list(score["keyword_hits"].keys()),
                    "regex_matches": score["regex_hits"],
                    "negative_flags": score["negative_hits"],
                })
                for c in score["keyword_hits"]:
                    cat_stats[c] += 1
            else:
                discarded += 1

    elapsed = time.time() - start
    kept.sort(key=lambda x: x["priority_score"], reverse=True)

    print(f"{'='*70}")
    print("TIER 1 RESULTS")
    print(f"{'='*70}")
    print(f"  Scanned: {total} reports in {elapsed:.2f}s")
    pct = (len(kept) / total * 100) if total else 0
    print(f"  Kept (interesting): {len(kept)} ({pct:.1f}%)")
    print(f"  Discarded (low signal): {discarded} ({100-pct:.1f}%)")
    print("\n  Category breakdown (reports matching each typology proxy):")
    for cat, c in sorted(cat_stats.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {c}")
    print("\n  Top 10 highest-priority reports:")
    for r in kept[:10]:
        loc = f"{r['city']},{r['state']}".strip(",")
        print(f"    P{r['priority_score']:>3} | {r['shape']:>10} | {loc:<22} | {r['description'][:60]}")

    embed_cost = len(kept) * 0.0001
    print("\n  TIER 2 COST ESTIMATE:")
    print(f"    Reports to embed: {len(kept)}")
    print(f"    Titan Embed cost: ~${embed_cost:.2f} (vs ${total*0.0001:.2f} for full corpus)")
    print(f"    SAVINGS: ${(total-len(kept))*0.0001:.2f}")

    output = {
        "tier": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": os.path.relpath(src, PROJECT_ROOT).replace("\\", "/"),
        "taxonomy": "src/data/ufo-uap-taxonomy.json",
        "total_scanned": total,
        "total_kept": len(kept),
        "total_discarded": discarded,
        "filter_rate_pct": round(pct, 2),
        "elapsed_seconds": round(elapsed, 2),
        "category_stats": dict(cat_stats),
        "reports": kept,
    }
    with open(TIER1_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {os.path.relpath(TIER1_OUTPUT, PROJECT_ROOT)}")
    return kept


# ============================================================
# Tier 2: Titan Embed on filtered set (needs Bedrock)
# ============================================================

def run_tier2(max_records=None):
    if not HAS_BOTO:
        print("ERROR: boto3 not available; Tier 2 needs AWS/Bedrock.")
        return []
    if not os.path.exists(TIER1_OUTPUT):
        print("ERROR: run --tier 1 first.")
        return []

    with open(TIER1_OUTPUT, "r", encoding="utf-8") as f:
        reports = json.load(f)["reports"]
    if max_records:
        reports = reports[:max_records]

    print("=" * 70)
    print(f"TIER 2: Titan Embed on {len(reports)} filtered reports")
    print(f"  Estimated cost: ~${len(reports)*0.0001:.2f}")
    print("=" * 70)

    bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    out = []
    errors = 0
    with open(TIER2_OUTPUT, "w", encoding="utf-8") as fout:
        for i, r in enumerate(reports):
            text = f"{r['shape']} shaped object. {r['description']}"[:8000]
            try:
                resp = bedrock.invoke_model(
                    modelId=EMBED_MODEL, contentType="application/json",
                    accept="application/json",
                    body=json.dumps({"inputText": text}),
                )
                emb = json.loads(resp["body"].read())["embedding"]
                rec = {k: r[k] for k in ("city", "state", "lat", "lng", "shape", "year",
                                         "priority_score", "categories")}
                rec["text_preview"] = r["description"][:200]
                rec["embedding"] = emb
                out.append(rec)
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Error: {str(e)[:100]}")
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(reports)} embedded")
                time.sleep(1)
    print(f"  Embedded {len(out)} reports ({errors} errors) -> {os.path.relpath(TIER2_OUTPUT, PROJECT_ROOT)}")
    return out


# ============================================================
# Tier 3: Taxonomy signature scoring + Haiku extraction
# ============================================================

def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def run_tier3(max_records=None):
    if not HAS_BOTO:
        print("ERROR: boto3 not available; Tier 3 needs AWS/Bedrock.")
        return []
    if not os.path.exists(TIER2_OUTPUT):
        print("ERROR: run --tier 2 first.")
        return []

    docs = []
    with open(TIER2_OUTPUT, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                docs.append(json.loads(line))
    if max_records:
        docs = docs[:max_records]

    tax, sigs = load_taxonomy_signatures()
    print("=" * 70)
    print(f"TIER 3: Score {len(docs)} reports against {len(sigs)} UFO/UAP signatures")
    print("=" * 70)

    bedrock = boto3.client("bedrock-runtime", region_name=REGION)

    # Embed the taxonomy signatures once
    sig_emb = {}
    for sid, meta in sigs.items():
        resp = bedrock.invoke_model(
            modelId=EMBED_MODEL, contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": meta["vector_text"]}),
        )
        sig_emb[sid] = json.loads(resp["body"].read())["embedding"]

    for d in docs:
        scores = {}
        for sid, emb in sig_emb.items():
            sim = cosine(d["embedding"], emb)
            if sim >= 0.05:
                scores[sid] = round(sim, 4)
        d["signature_scores"] = dict(sorted(scores.items(), key=lambda kv: -kv[1])[:5])
        d["max_signature_score"] = max(scores.values()) if scores else 0.0
        d["typologies_hit"] = sorted({sigs[s]["typology"] for s in scores})
        d.pop("embedding", None)  # drop to keep output small

    docs.sort(key=lambda x: x["max_signature_score"], reverse=True)

    print("\n  Top 10 reports by best signature match:")
    for d in docs[:10]:
        top_sig = next(iter(d["signature_scores"]), "-")
        print(f"    {d['max_signature_score']:.3f} | {top_sig:<14} | {d['shape']:>9} | {d['text_preview'][:50]}")

    output = {
        "tier": 3,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "taxonomy": "src/data/ufo-uap-taxonomy.json",
        "reports_scored": len(docs),
        "results": docs,
    }
    with open(TIER3_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {os.path.relpath(TIER3_OUTPUT, PROJECT_ROOT)}")
    return docs


def main():
    parser = argparse.ArgumentParser(description="UFO/UAP Tiered Processing Pipeline")
    parser.add_argument("--tier", required=True, choices=["1", "2", "3", "all"])
    parser.add_argument("--max-records", type=int, default=None)
    args = parser.parse_args()

    if args.tier in ("1", "all"):
        run_tier1(args.max_records)
    if args.tier in ("2", "all"):
        run_tier2(args.max_records)
    if args.tier in ("3", "all"):
        run_tier3(args.max_records)


if __name__ == "__main__":
    main()
