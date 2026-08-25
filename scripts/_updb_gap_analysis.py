#!/usr/bin/env python3
"""UPDB taxonomy gap analysis — augmentation loop step.

Scores the UPDB global corpus (296K, 220 countries, MUFON/BLUEBOOK/UKGOV/etc.)
against the CURRENT 25 UFO/UAP taxonomy signatures, then finds GAPS:
  - which signatures fire / never fire on UPDB
  - high-Tier-1 reports that match NO signature (candidate new patterns)
  - gap breakdown by SOURCE (MUFON, BLUEBOOK, UKGOV, PILOTS...) and COUNTRY

Reuses needle-matching from ufo_full_corpus_signature_scan.py logic.
Output: scripts/updb_gap_analysis.json
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
from ufo_tiered_scan import score_report_tier1  # Tier-1 keyword scoring (reused)
from ufo_full_corpus_signature_scan import load_signatures, score_report  # needle scan (reused)

UPDB = os.path.join(PROJECT_ROOT, "docs", "updb", "updb_reports.json")
OUT = os.path.join(PROJECT_ROOT, "scripts", "updb_gap_analysis.json")

# A report is a "gap" candidate if it clears Tier-1 strongly but fires NO signature.
GAP_MIN_TIER1 = 3


def main():
    reports = json.load(open(UPDB, encoding="utf-8"))["reports"]
    sigs = load_signatures()
    sig_meta = {s["signature_id"]: s for s in sigs}

    total = 0
    fired_any = 0
    sig_fire = Counter()
    typ_fire = Counter()
    gap_reports = []
    gap_by_source = Counter()
    gap_by_country = Counter()
    # keyword-category frequency among gap reports (reveals missing patterns)
    gap_categories = Counter()

    for r in reports:
        desc = r.get("description") or ""
        if len(desc) < 20:
            continue
        total += 1
        blob = f"{desc} ".lower()
        fired, _ = score_report(blob, sigs)
        if fired:
            fired_any += 1
            for sid, _ in fired:
                sig_fire[sid] += 1
            for t in {sig_meta[sid]["typology"] for sid, _ in fired}:
                typ_fire[t] += 1
        else:
            t1 = score_report_tier1(desc, "")
            if t1["priority_score"] >= GAP_MIN_TIER1:
                gap_by_source[r.get("source", "?")] += 1
                gap_by_country[r.get("country", "?") or "?"] += 1
                for c in t1["keyword_hits"]:
                    gap_categories[c] += 1
                if len(gap_reports) < 400:  # sample for inspection
                    gap_reports.append({
                        "source": r.get("source", ""), "country": r.get("country", ""),
                        "t1": t1["priority_score"], "cats": list(t1["keyword_hits"].keys()),
                        "text": desc[:200],
                    })

    never = [s["signature_id"] for s in sigs if sig_fire[s["signature_id"]] == 0]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "docs/updb/updb_reports.json",
        "total_scored": total,
        "fired_any_signature": fired_any,
        "coverage_pct": round(100 * fired_any / max(1, total), 2),
        "signatures_never_fired_on_updb": never,
        "per_typology_fire": dict(typ_fire.most_common()),
        "per_signature_fire": dict(sig_fire.most_common()),
        "gap_high_t1_no_signature": sum(gap_by_source.values()),
        "gap_by_source": dict(gap_by_source.most_common(15)),
        "gap_by_country": dict(gap_by_country.most_common(20)),
        "gap_keyword_categories": dict(gap_categories.most_common()),
        "gap_samples": gap_reports[:60],
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=" * 68)
    print("UPDB TAXONOMY GAP ANALYSIS")
    print("=" * 68)
    print(f"  Scored:              {total}")
    print(f"  Fired >=1 signature: {fired_any} ({out['coverage_pct']}%)")
    print(f"  Never-fired sigs:    {len(never)} {never}")
    print(f"\n  Per-typology fire:")
    for t, c in typ_fire.most_common():
        print(f"    {t:<26} {c}")
    print(f"\n  GAP (high-Tier1, zero-signature): {out['gap_high_t1_no_signature']}")
    print(f"  Gap by SOURCE: {out['gap_by_source']}")
    print(f"  Gap by COUNTRY (top): {dict(list(out['gap_by_country'].items())[:10])}")
    print(f"  Gap keyword categories: {out['gap_keyword_categories']}")
    print(f"\n  Output: {os.path.relpath(OUT, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
