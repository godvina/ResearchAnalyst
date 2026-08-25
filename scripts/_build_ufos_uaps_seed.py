#!/usr/bin/env python3
"""Populate the `ufos_uaps` top-10 conspiracy-theory slot from EXISTING data.

This does NOT source new data. It reuses:
  - scripts/ufo_tier1_filtered.json   (Tier-1 filtered NUFORC reports; run ufo_tiered_scan.py --tier 1 first)
  - src/data/conspiracy-seed/ufo_sightings/mufon_records.csv   (MUFON-attributed subset)
  - src/data/conspiracy-seed/ufo_sightings/ufo_analysis.json   (aggregate analysis)

Outputs (the seed layout the pipeline expects for a theory):
  src/data/conspiracy-seed/ufos_uaps/processed_claims.json   (ready for S3 upload)
  src/data/conspiracy-seed/ufos_uaps/README.json             (provenance)

Then (optionally, with --upload) puts processed_claims.json at:
  s3://<data-lake>/data-lake/conspiracy-theories/ufos_uaps/processed_claims.json
which triggers the existing Lambda pipeline (Aurora + OpenSearch + Neptune).

Usage:
    python scripts/_build_ufos_uaps_seed.py                 # build seed files only
    python scripts/_build_ufos_uaps_seed.py --top 2000      # cap number of claims
    python scripts/_build_ufos_uaps_seed.py --upload        # also upload to S3 (medium-risk)
"""
import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIER1_PATH = os.path.join(PROJECT_ROOT, "scripts", "ufo_tier1_filtered.json")
MUFON_CSV = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufo_sightings", "mufon_records.csv")
UFO_ANALYSIS = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufo_sightings", "ufo_analysis.json")
TAXONOMY_PATH = os.path.join(PROJECT_ROOT, "src", "data", "ufo-uap-taxonomy.json")

OUT_DIR = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufos_uaps")
OUT_CLAIMS = os.path.join(OUT_DIR, "processed_claims.json")
OUT_README = os.path.join(OUT_DIR, "README.json")

BUCKET = "research-analyst-data-lake-974220725866"
S3_KEY = "data-lake/conspiracy-theories/ufos_uaps/processed_claims.json"

# Map a report's top Tier-1 category to a taxonomy typology id
CATEGORY_TO_TYPOLOGY = {
    "impossible_kinematics": "flight_kinematics",
    "em_physical_effects": "sensor_em_signatures",
    "radar_visual": "sensor_em_signatures",
    "structured_craft": "craft_morphology",
    "encounter_quality": "encounter_typology",
    "credible_witness": "witness_reliability",
    "institutional": "institutional_response",
}


def _clean(text: str) -> str:
    """Un-escape the HTML entities the NUFORC CSV uses (&#44 etc.)."""
    if not text:
        return ""
    text = text.replace("&#44", ",").replace("&#39", "'").replace("&amp;", "&")
    text = text.replace("&#33", "!").replace("&quot;", '"')
    return re.sub(r"\s+", " ", text).strip()


def primary_typology(categories):
    for cat in categories:
        if cat in CATEGORY_TO_TYPOLOGY:
            return CATEGORY_TO_TYPOLOGY[cat]
    return "craft_morphology"


def load_tier1(top=None):
    if not os.path.exists(TIER1_PATH):
        raise SystemExit("ERROR: run `python scripts/ufo_tiered_scan.py --tier 1` first.")
    with open(TIER1_PATH, "r", encoding="utf-8") as f:
        reports = json.load(f)["reports"]
    if top:
        reports = reports[:top]
    return reports


def load_mufon_keys():
    """Return a set of (city,state,year,shape) tuples for MUFON-attributed reports,
    so we can tag those claims with source=MUFON for provenance."""
    keys = set()
    if not os.path.exists(MUFON_CSV):
        return keys
    with open(MUFON_CSV, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            keys.add((
                (row.get("Location.City") or "").lower().strip(),
                (row.get("Location.State") or "").lower().strip(),
                (row.get("Dates.Sighted.Year") or "").strip(),
                (row.get("Data.Shape") or "").lower().strip(),
            ))
    return keys


def build_claims(reports, mufon_keys):
    claims = []
    for i, r in enumerate(reports):
        key = (r["city"].lower().strip(), r["state"].lower().strip(),
               str(r["year"]).strip(), r["shape"].lower().strip())
        source = "MUFON/NUFORC" if key in mufon_keys else "NUFORC"
        typ = primary_typology(r["categories"])
        loc = ", ".join([p for p in (r["city"], r["state"]) if p])
        desc = _clean(r["description"])
        # Priority -> pseudo-confidence in [0,1]; penalty already baked into priority_score
        score = max(0.0, min(1.0, 0.4 + r["priority_score"] * 0.05))
        claims.append({
            "id": f"uap-{i:05d}",
            "title": f"{r['shape'].title()} sighting — {loc or 'unknown location'}",
            "source": source,
            "claim": desc,
            "dataset": "ufos_uaps",
            "category": typ,
            "typology": typ,
            "matched_categories": r["categories"],
            "priority_score": r["priority_score"],
            "score": round(score, 3),
            "verdict": "unverified",
            "standard": "intelligence",
            "location": {"city": r["city"], "state": r["state"],
                         "lat": r["lat"], "lng": r["lng"]},
            "year": r["year"],
            "shape": r["shape"],
            "negative_flags": r.get("negative_flags", []),
        })
    return claims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=2000,
                    help="Max claims to include (default 2000 highest-priority)")
    ap.add_argument("--upload", action="store_true",
                    help="Upload processed_claims.json to S3 (triggers the live pipeline)")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    reports = load_tier1(top=args.top)
    mufon_keys = load_mufon_keys()
    claims = build_claims(reports, mufon_keys)
    mufon_count = sum(1 for c in claims if c["source"] == "MUFON/NUFORC")

    doc = {
        "dataset_name": "ufos_uaps",
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "claim_count": len(claims),
        "claims": claims,
        "cross_domain_scoring": True,
        "tenant_id": "conspiracy_theories",
        "taxonomy": "src/data/ufo-uap-taxonomy.json",
        "provenance": {
            "source_dataset": "NUFORC 60,632 sightings (CORGIS) + MUFON-attributed subset",
            "tier1_filter": "scripts/ufo_tiered_scan.py --tier 1",
            "note": "Reuses existing ufo_sightings data; no new data sourced. Feeds the ufos_uaps top-10 conspiracy slot.",
            "mufon_tagged_claims": mufon_count,
        },
    }
    with open(OUT_CLAIMS, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    with open(OUT_README, "w", encoding="utf-8") as f:
        json.dump({
            "slot": "ufos_uaps (top-10 conspiracy theory)",
            "built_from": ["scripts/ufo_tier1_filtered.json", "mufon_records.csv", "ufo_analysis.json"],
            "taxonomy": "src/data/ufo-uap-taxonomy.json",
            "claim_count": len(claims),
            "mufon_tagged": mufon_count,
            "s3_target": f"s3://{BUCKET}/{S3_KEY}",
            "built_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)

    print(f"Built {len(claims)} claims ({mufon_count} MUFON-tagged) -> {os.path.relpath(OUT_CLAIMS, PROJECT_ROOT)}")

    if args.upload:
        import boto3
        s3 = boto3.client("s3")
        body = json.dumps(doc, ensure_ascii=False).encode("utf-8")
        s3.put_object(Bucket=BUCKET, Key=S3_KEY, Body=body,
                      ContentType="application/json",
                      Metadata={"dataset": "ufos_uaps",
                                "claim_count": str(len(claims)),
                                "tenant": "conspiracy_theories"})
        print(f"Uploaded to s3://{BUCKET}/{S3_KEY} ({len(body)//1024} KB) — pipeline triggered.")
    else:
        print("Seed files written. Re-run with --upload to push to S3 and trigger the live pipeline.")


if __name__ == "__main__":
    main()
