#!/usr/bin/env python3
"""Diminishing-returns / coverage assessment for the UFO Tier-3 signature scoring.

Reads scripts/ufo_tier3_entities.json and reports, per the enrichment-loop SOP:
  - which signatures fired (>=3 independent confirmations at moderate/strong)
  - which signatures NEVER fired (gap: taxonomy has a signature the data doesn't support, or vice versa)
  - high-keyword / low-signature reports (gap: real pattern the taxonomy is missing)
  - typology coverage distribution
"""
import json
import os
from collections import Counter, defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIER3 = os.path.join(PROJECT_ROOT, "scripts", "ufo_tier3_entities.json")
TAXONOMY = os.path.join(PROJECT_ROOT, "src", "data", "ufo-uap-taxonomy.json")

STRONG, MODERATE, WEAK = 0.80, 0.60, 0.40

with open(TIER3, encoding="utf-8") as f:
    results = json.load(f)["results"]
with open(TAXONOMY, encoding="utf-8") as f:
    tax = json.load(f)

all_sigs = {}
for t in tax["typologies"]:
    for m in t["methods"]:
        for s in m["signatures"]:
            all_sigs[s["signature_id"]] = t["typology_id"]

# Best-signature match per report
best_sig_counts = Counter()
best_sig_moderate = Counter()   # reports whose BEST match >= MODERATE
sig_any_hit = Counter()         # times a signature appears in any report's top-5
typology_best = Counter()
score_buckets = {"strong>=0.80": 0, "moderate 0.60-0.80": 0, "weak 0.40-0.60": 0, "none <0.40": 0}
low_signal_reports = []         # high keyword priority but low best-signature score

for r in results:
    sigs = r.get("signature_scores", {})
    best = r.get("max_signature_score", 0.0)
    if sigs:
        top_sig = next(iter(sigs))
        best_sig_counts[top_sig] += 1
        typology_best[all_sigs.get(top_sig, "?")] += 1
        for sid in sigs:
            sig_any_hit[sid] += 1
        if best >= MODERATE:
            best_sig_moderate[top_sig] += 1
    if best >= STRONG:
        score_buckets["strong>=0.80"] += 1
    elif best >= MODERATE:
        score_buckets["moderate 0.60-0.80"] += 1
    elif best >= WEAK:
        score_buckets["weak 0.40-0.60"] += 1
    else:
        score_buckets["none <0.40"] += 1
    # Gap detector: strong keyword priority but weak signature match
    if r.get("priority_score", 0) >= 4 and best < MODERATE:
        low_signal_reports.append(r)

never_fired = [s for s in all_sigs if s not in sig_any_hit]
confirmed = [s for s, c in best_sig_moderate.items() if c >= 3]

print("=" * 70)
print("UFO TIER-3 COVERAGE / DIMINISHING-RETURNS ASSESSMENT")
print("=" * 70)
print(f"Reports scored: {len(results)}")
print(f"\nBest-match score distribution:")
for k, v in score_buckets.items():
    print(f"  {k:<22} {v:>5}  ({v/len(results)*100:.1f}%)")

print(f"\nTypology coverage (by each report's best match):")
for t, c in typology_best.most_common():
    print(f"  {t:<26} {c:>5}")

print(f"\nSignatures CONFIRMED (>=3 reports at moderate+): {len(confirmed)}/{len(all_sigs)}")
for s in sorted(confirmed):
    print(f"  + {s} ({best_sig_moderate[s]} confirmations)")

print(f"\nSignatures that NEVER fired (0 hits in any top-5): {len(never_fired)}")
for s in sorted(never_fired):
    print(f"  - {s} ({all_sigs[s]})")

print(f"\nGAP: high-keyword but low-signature reports (real patterns taxonomy may miss): {len(low_signal_reports)}")
# Show the shapes/keywords of these gap reports to reveal missing signatures
gap_shapes = Counter(r.get("shape", "?") for r in low_signal_reports)
gap_cats = Counter()
for r in low_signal_reports:
    for c in r.get("categories", []):
        gap_cats[c] += 1
print(f"  gap report shapes: {dict(gap_shapes.most_common(8))}")
print(f"  gap report categories: {dict(gap_cats.most_common(8))}")
print(f"  sample gap reports:")
for r in low_signal_reports[:6]:
    print(f"    P{r.get('priority_score')} best={r.get('max_signature_score'):.2f} {r.get('shape'):>9} | {r.get('text_preview','')[:55]}")
