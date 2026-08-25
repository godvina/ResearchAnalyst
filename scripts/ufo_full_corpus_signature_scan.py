#!/usr/bin/env python3
"""Full-corpus needle/signature scan over ALL 60,632 NUFORC reports ($0, local).

The UFO/UAP taxonomy signatures were knowledge-authored and previously validated
on only a 1,500-report sample. This scores the ENTIRE corpus against every
signature's indicators ("needles"), grounding the taxonomy in the full dataset
(per the data-driven-taxonomy steering rule). No sampling, no Bedrock cost.

Method: for each report narrative, count how many of each signature's `indicators`
appear (keyword/phrase presence, case-insensitive). A signature "fires" on a report
when >= MIN_NEEDLES of its indicators are present. Reports the per-signature hit
counts, per-typology rollup, needle frequency, and confirmation rate.

Input:  src/data/conspiracy-seed/ufo_sightings/ufo_sightings.csv  (all 60,632 rows)
        src/data/ufo-uap-taxonomy.json
Output: scripts/ufo_full_corpus_scan.json
"""
import csv
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_CANDIDATES = [
    os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufo_sightings", "ufo_sightings.csv"),
    os.path.join(PROJECT_ROOT, "docs", "ufo_sightings.csv"),
]
TAX = os.path.join(PROJECT_ROOT, "src", "data", "ufo-uap-taxonomy.json")
OUT = os.path.join(PROJECT_ROOT, "scripts", "ufo_full_corpus_scan.json")

DESC = "Data.Description excerpt"
SHAPE = "Data.Shape"

# A signature fires on a report when at least this many of its needles are present.
MIN_NEEDLES = 2

# Map each indicator string to a compact set of match tokens. We use the most
# distinctive words/phrases from each indicator so matching is meaningful, not
# just stopword overlap.
STOP = set("a an the of to in on at and or is are was were with no not this that "
           "it its as for by from up down over under out into within near above "
           "below than then so if would could should may might per each any all "
           "which who whom whose when where how".split())


def needle_tokens(indicator: str):
    """Extract distinctive lowercase tokens/phrases from an indicator string."""
    txt = indicator.lower()
    # keep 2-3 word key phrases where possible, else salient single words
    words = re.findall(r"[a-z0-9']+", txt)
    keep = [w for w in words if w not in STOP and len(w) > 3]
    return keep


def load_signatures():
    tax = json.load(open(TAX, encoding="utf-8"))
    sigs = []
    for typ in tax["typologies"]:
        for method in typ["methods"]:
            for s in method["signatures"]:
                sigs.append({
                    "signature_id": s["signature_id"],
                    "typology": typ["typology_id"],
                    "method": method["method_id"],
                    "severity": s["severity"],
                    "indicators": s["indicators"],
                    # precompute token sets per indicator
                    "needle_tokens": [needle_tokens(i) for i in s["indicators"]],
                })
    return sigs


def find_csv():
    for p in CSV_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("ufo_sightings.csv not found")


def score_report(blob, sigs):
    """Return list of (signature_id, needles_hit) for signatures that fire."""
    fired = []
    needle_hits = defaultdict(int)
    for sig in sigs:
        hit = 0
        matched_needles = []
        for ind, toks in zip(sig["indicators"], sig["needle_tokens"]):
            if not toks:
                continue
            # indicator "present" if a majority of its distinctive tokens appear
            present = sum(1 for t in toks if t in blob)
            if present >= max(1, len(toks) // 2):
                hit += 1
                matched_needles.append(ind)
        if hit >= MIN_NEEDLES:
            fired.append((sig["signature_id"], hit))
            for n in matched_needles:
                needle_hits[f"{sig['signature_id']}::{n}"] += 1
    return fired, needle_hits


def main():
    src = find_csv()
    sigs = load_signatures()
    sig_meta = {s["signature_id"]: s for s in sigs}
    print(f"Scanning {os.path.basename(src)} against {len(sigs)} signatures...")

    total = 0
    reports_with_any = 0
    sig_report_count = defaultdict(int)     # reports where signature fired
    typ_report_count = defaultdict(int)     # reports where any sig of typology fired
    needle_freq = defaultdict(int)
    shape_by_sig = defaultdict(lambda: defaultdict(int))
    signal_reports = []                     # firing reports, for downstream ingest

    LAT = "Location.Coordinates.Latitude "
    LNG = "Location.Coordinates.Longitude "
    CITY, STATE, YEAR = "Location.City", "Location.State", "Dates.Sighted.Year"

    with open(src, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            total += 1
            blob = f"{row.get(DESC,'')} {row.get(SHAPE,'')}".lower()
            fired, nh = score_report(blob, sigs)
            if fired:
                reports_with_any += 1
                fired_sids = [sid for sid, _ in fired]
                for sid, _ in fired:
                    sig_report_count[sid] += 1
                    shape_by_sig[sid][row.get(SHAPE, "unknown")] += 1
                fired_typs = sorted({sig_meta[sid]["typology"] for sid, _ in fired})
                for t in fired_typs:
                    typ_report_count[t] += 1
                for k, v in nh.items():
                    needle_freq[k] += v
                signal_reports.append({
                    "city": row.get(CITY, ""), "state": row.get(STATE, ""),
                    "lat": (row.get(LAT) or "").strip(), "lng": (row.get(LNG) or "").strip(),
                    "shape": row.get(SHAPE, ""), "year": row.get(YEAR, ""),
                    "description": row.get(DESC, ""),
                    "fired_signatures": fired_sids,
                    "typologies": fired_typs,
                    "signature_count": len(fired_sids),
                })

    # Confirmation rate: fraction of corpus each signature fires on
    sig_rows = []
    for s in sigs:
        c = sig_report_count[s["signature_id"]]
        sig_rows.append({
            "signature_id": s["signature_id"],
            "typology": s["typology"],
            "severity": s["severity"],
            "reports_fired": c,
            "confirmation_rate_pct": round(100.0 * c / total, 3),
            "top_shapes": dict(sorted(shape_by_sig[s["signature_id"]].items(),
                                      key=lambda kv: -kv[1])[:5]),
        })
    sig_rows.sort(key=lambda r: r["reports_fired"], reverse=True)

    top_needles = sorted(needle_freq.items(), key=lambda kv: -kv[1])[:40]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": os.path.relpath(src, PROJECT_ROOT).replace("\\", "/"),
        "taxonomy": "src/data/ufo-uap-taxonomy.json",
        "min_needles_to_fire": MIN_NEEDLES,
        "total_reports_scanned": total,
        "reports_with_any_signature": reports_with_any,
        "coverage_pct": round(100.0 * reports_with_any / total, 2),
        "signatures_confirmed_10plus": sum(1 for r in sig_rows if r["reports_fired"] >= 10),
        "signatures_never_fired": [r["signature_id"] for r in sig_rows if r["reports_fired"] == 0],
        "per_typology_reports": dict(sorted(typ_report_count.items(), key=lambda kv: -kv[1])),
        "per_signature": sig_rows,
        "top_needles": [{"needle": k, "count": v} for k, v in top_needles],
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # Emit the firing ("signal") reports separately for downstream ingest.
    signal_reports.sort(key=lambda r: r["signature_count"], reverse=True)
    signal_path = os.path.join(PROJECT_ROOT, "scripts", "ufo_signal_reports.json")
    json.dump({"count": len(signal_reports), "reports": signal_reports},
              open(signal_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  Signal reports written: {len(signal_reports)} -> {os.path.relpath(signal_path, PROJECT_ROOT)}")

    print("=" * 70)
    print("FULL-CORPUS SIGNATURE SCAN (all reports)")
    print("=" * 70)
    print(f"  Reports scanned:        {total}")
    print(f"  Reports w/ >=1 signature: {reports_with_any} ({out['coverage_pct']}%)")
    print(f"  Signatures confirmed (10+ reports): {out['signatures_confirmed_10plus']}/{len(sigs)}")
    print(f"  Signatures never fired: {len(out['signatures_never_fired'])} {out['signatures_never_fired']}")
    print(f"\n  Per-typology (reports where typology fired):")
    for t, c in out["per_typology_reports"].items():
        print(f"    {t:<26} {c:>6}")
    print(f"\n  Top signatures by corpus-wide fire count:")
    for r in sig_rows[:12]:
        print(f"    {r['reports_fired']:>6} ({r['confirmation_rate_pct']:>5}%) | {r['signature_id']:<16} | {r['typology']}")
    print(f"\n  Output: {os.path.relpath(OUT, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
