#!/usr/bin/env python3
"""Taxonomy Enrichment Loop orchestrator (steps 1-5 of the master loop).

Automates, for ANY dataset, the repeatable core of
.kiro/steering/taxonomy-enrichment-master-loop.md:

  1. Tier-1 filter (keyword scoring)         -> reuses ufo_tiered_scan.score_report_tier1
  2/3. Signature scan + gap analysis          -> reuses full_corpus_signature_scan.score_report
  5. Diminishing-returns verdict              -> AUGMENT vs STOP recommendation

Step 4 (author new signatures) stays human-in-the-loop, but this prints the exact gap
clusters to author from. Prints a machine verdict so the sequence can't be silently skipped.

Input: a JSON file with {"reports":[{...}]}, each record having a text field.
Usage:
    python scripts/taxonomy_enrichment_loop.py --input docs/updb/updb_reports.json --text-field description
    python scripts/taxonomy_enrichment_loop.py --input scripts/ufo_signal_reports.json --text-field description --group-field state
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
from ufo_tiered_scan import score_report_tier1
from ufo_full_corpus_signature_scan import load_signatures, score_report

# Diminishing-returns thresholds
GAP_MIN_T1 = 3            # a record is a "gap candidate" if Tier-1 priority >= this AND no signature
AUGMENT_GAP_FRACTION = 0.03   # if >3% of scored records are high-signal gaps -> worth augmenting
CONFIRM_MIN = 3           # a signature is "confirmed" if it fires on >= this many records


def load_records(path, text_field):
    data = json.load(open(path, encoding="utf-8"))
    recs = data.get("reports") or data.get("claims") or (data if isinstance(data, list) else [])
    out = []
    for r in recs:
        t = r.get(text_field) or r.get("description") or r.get("claim") or r.get("details") or ""
        if t and len(t) >= 20:
            out.append((t, r))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--text-field", default="description")
    ap.add_argument("--group-field", default=None, help="Field to break gaps down by (e.g. source, country, state)")
    ap.add_argument("--max", type=int, default=None)
    args = ap.parse_args()

    sigs = load_signatures()
    sig_typ = {s["signature_id"]: s["typology"] for s in sigs}
    records = load_records(args.input, args.text_field)
    if args.max:
        records = records[: args.max]

    total = len(records)
    t1_pass = 0
    fired_any = 0
    sig_fire = Counter()
    typ_fire = Counter()
    gap_by_group = Counter()
    gap_cats = Counter()
    gaps = 0

    for text, rec in records:
        blob = text[:20000].lower()
        t1 = score_report_tier1(text[:20000], "")
        if t1["keep"]:
            t1_pass += 1
        fired, _ = score_report(blob, sigs)
        if fired:
            fired_any += 1
            for sid, _ in fired:
                sig_fire[sid] += 1
            for t in {sig_typ[sid] for sid, _ in fired}:
                typ_fire[t] += 1
        else:
            if t1["priority_score"] >= GAP_MIN_T1:
                gaps += 1
                for c in t1["keyword_hits"]:
                    gap_cats[c] += 1
                if args.group_field:
                    gap_by_group[str(rec.get(args.group_field, "?"))] += 1

    confirmed = [s for s, c in sig_fire.items() if c >= CONFIRM_MIN]
    never = [s["signature_id"] for s in sigs if sig_fire[s["signature_id"]] == 0]
    gap_frac = gaps / total if total else 0

    # Refined verdict: a gap only justifies AUGMENT if it is NOT dominated by keyword
    # categories that already have confirmed signatures. If the gap categories all map to
    # typologies that are already well-covered, the residual is terse/short records with
    # generic language, NOT a missing pattern -> STOP (author-nothing). This prevents the
    # loop from chasing diminishing generic-language gaps forever.
    covered_typologies = {sig_typ[s] for s in confirmed}
    # keyword category -> typology hint
    CAT_TYP = {
        "structured_craft": "craft_morphology", "impossible_kinematics": "flight_kinematics",
        "radar_visual": "sensor_em_signatures", "em_physical_effects": "sensor_em_signatures",
        "encounter_quality": "encounter_typology", "credible_witness": "witness_reliability",
        "institutional": "institutional_response",
    }
    novel_gap = sum(c for cat, c in gap_cats.items()
                    if CAT_TYP.get(cat) not in covered_typologies)
    novel_gap_frac = novel_gap / total if total else 0

    if gap_frac >= AUGMENT_GAP_FRACTION and novel_gap_frac >= AUGMENT_GAP_FRACTION:
        verdict = "AUGMENT"
    elif gap_frac >= AUGMENT_GAP_FRACTION:
        verdict = "STOP (gap is generic-language in already-covered typologies, not a new pattern)"
    else:
        verdict = "STOP"

    print("=" * 66)
    print("TAXONOMY ENRICHMENT LOOP  (steps 1-5)")
    print("=" * 66)
    print(f"  input:            {os.path.relpath(args.input, PROJECT_ROOT)}")
    print(f"  records scored:   {total}")
    print(f"  Tier-1 pass:      {t1_pass} ({100*t1_pass/max(1,total):.1f}%)")
    print(f"  fired >=1 sig:    {fired_any} ({100*fired_any/max(1,total):.1f}%)")
    print(f"  signatures confirmed (>= {CONFIRM_MIN}): {len(confirmed)}/{len(sigs)}")
    print(f"  never fired:      {len(never)} {never}")
    print(f"  high-signal GAPS (no sig, T1>={GAP_MIN_T1}): {gaps} ({100*gap_frac:.2f}%)")
    if args.group_field and gap_by_group:
        print(f"  gaps by {args.group_field}: {dict(gap_by_group.most_common(10))}")
    if gap_cats:
        print(f"  gap keyword categories: {dict(gap_cats.most_common())}")
    print(f"\n  >>> VERDICT: {verdict}", end="  ")
    if verdict == "AUGMENT":
        print(f"(gap fraction {100*gap_frac:.2f}% >= {100*AUGMENT_GAP_FRACTION:.0f}% — author signatures from the gap clusters above, re-index, re-run)")
    else:
        print(f"(gap fraction {100*gap_frac:.2f}% < {100*AUGMENT_GAP_FRACTION:.0f}% — point of goodness for this dataset; broaden to a new source)")


if __name__ == "__main__":
    main()
