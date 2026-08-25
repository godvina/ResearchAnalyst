#!/usr/bin/env python3
"""Tier-1 filter the UPDB global corpus and build an ingest-ready seed.

Reuses the Tier-1 scoring from scripts/ufo_tiered_scan.py (KEYWORD_PATTERNS,
NEGATIVE_PATTERNS, score_report_tier1) — does NOT redefine the taxonomy.

Input:  docs/updb/updb_reports.json  (296,600 global reports; from _parse_updb_dump.py)
Output: src/data/conspiracy-seed/ufos_uaps/updb_claims.json  (processed_claims format)

Priority for the seed (global-pattern value):
  1. All non-US reports that pass Tier-1  (global coverage — the whole point)
  2. MUFON-sourced reports that pass Tier-1 (priority-1 source)
  3. Fill remaining slots with highest-priority US reports
Capped by --top (default 8000) to keep ingest cost bounded (~$9).
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
from ufo_tiered_scan import score_report_tier1  # reuse built Tier-1 scoring

UPDB = os.path.join(PROJECT_ROOT, "docs", "updb", "updb_reports.json")
OUT = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufos_uaps", "updb_claims.json")


def _clean(t):
    if not t:
        return ""
    return re.sub(r"\s+", " ", t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=8000, help="Max claims in the seed")
    args = ap.parse_args()

    reports = json.load(open(UPDB, encoding="utf-8"))["reports"]
    print(f"UPDB reports: {len(reports)}")

    kept = []
    for r in reports:
        desc = r.get("description") or ""
        if len(desc) < 20:
            continue
        score = score_report_tier1(desc, "")
        if not score["keep"]:
            continue
        kept.append({
            "id": f"updb-{r['id']}",
            "source": r.get("source", "UPDB"),
            "country": r.get("country", ""),
            "city": r.get("city", ""),
            "district": r.get("district", ""),
            "date": r.get("date", ""),
            "description": _clean(desc),
            "priority_score": score["priority_score"],
            "categories": list(score["keyword_hits"].keys()),
        })

    print(f"Passed Tier-1: {len(kept)} ({round(100*len(kept)/max(1,len(reports)),1)}%)")

    # Prioritize: non-US first, then MUFON, then highest-priority US
    non_us = [k for k in kept if k["country"] and k["country"] != "US"]
    mufon_us = [k for k in kept if k["country"] == "US" and k["source"] == "MUFON"]
    rest_us = [k for k in kept if k["country"] == "US" and k["source"] != "MUFON"]
    for grp in (non_us, mufon_us, rest_us):
        grp.sort(key=lambda x: x["priority_score"], reverse=True)
    ordered = (non_us + mufon_us + rest_us)[: args.top]

    claims = []
    for i, k in enumerate(ordered):
        loc = ", ".join([p for p in (k["city"], k["district"], k["country"]) if p])
        claims.append({
            "id": k["id"],
            "title": f"UAP sighting — {loc or k['country'] or 'unknown'}",
            "source": k["source"],
            "claim": k["description"],
            "dataset": "ufos_uaps",
            "category": "craft_morphology",
            "matched_categories": k["categories"],
            "priority_score": k["priority_score"],
            "score": round(min(1.0, 0.4 + k["priority_score"] * 0.05), 3),
            "verdict": "unverified",
            "standard": "intelligence",
            "location": {"city": k["city"], "district": k["district"], "country": k["country"]},
            "country": k["country"],
            "date": k["date"],
        })

    doc = {
        "dataset_name": "ufos_uaps",
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "claim_count": len(claims),
        "claims": claims,
        "cross_domain_scoring": True,
        "tenant_id": "conspiracy_theories",
        "provenance": {
            "source_dataset": "UPDB (uapublius/updb-importers) — global, 296,600 reports, 220 countries",
            "selection": "Tier-1 survivors, prioritized non-US + MUFON + top US",
            "sources_present": "NUFORC, MUFON, UFODNA, BLUEBOOK, NICAP, UKGOV, CANADAGOV, PILOTS, NIDS, SKINWALKER",
            "tier1": "scripts/ufo_tiered_scan.py score_report_tier1 (reused)",
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    cc = Counter(c["country"] for c in claims if c["country"])
    sc = Counter(c["source"] for c in claims)
    print(f"Seed claims: {len(claims)} -> {os.path.relpath(OUT, PROJECT_ROOT)}")
    print(f"  countries in seed: {len(cc)}  | top: {dict(cc.most_common(10))}")
    print(f"  sources in seed: {dict(sc.most_common(8))}")


if __name__ == "__main__":
    main()
