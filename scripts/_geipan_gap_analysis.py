#!/usr/bin/env python3
"""GEIPAN taxonomy gap analysis (French govt cases) — augmentation loop step.

Finds patterns in GEIPAN that the current 28 signatures miss, focusing on:
  - D-class (officially unexplained) cases that fire NO signature -> real gaps
  - case-TYPE distribution (aeronautical/military vs terrestrial) -> new modalities
  - phenomenon categories GEIPAN uses that we don't model

GEIPAN narratives are FRENCH. We map French anomaly phrases to our typologies and
report which GEIPAN case types / phenomena are under-covered.

Input:  docs/geipan/geipan_reports.json
Output: scripts/geipan_gap_analysis.json
"""
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(PROJECT_ROOT, "docs", "geipan", "geipan_reports.json")
OUT = os.path.join(PROJECT_ROOT, "scripts", "geipan_gap_analysis.json")

# French phrase -> our typology (does the current taxonomy cover this concept?)
FR_TYPOLOGY = {
    "craft_morphology": ["disque", "triangulaire", "sphΦre", "sphere", "cigare",
                         "soucoupe", "mΘtallique", "metallique", "ovale", "cylindre"],
    "flight_kinematics": ["silencieux", "instantanΘ", "instantane", "immobile",
                          "stationnaire", "accΘlΘr", "acceler", "disparu", "haute vitesse",
                          "angle droit", "dΘplacement", "deplacement"],
    "sensor_em_signatures": ["radar", "Θlectromagn", "electromagn", "panne", "moteur",
                             "interfΘrence", "interference", "trace au sol", "brⁿlure",
                             "brulure", "rΘmanence"],
    "encounter_typology": ["atterri", "posΘ au sol", "pose au sol", "occupant", "Ωtre",
                           "humano�de", "humanoide", "tΘmoins multiples", "plusieurs tΘmoins"],
    "institutional_response": ["gendarme", "militaire", "armΘe", "armee", "pilote",
                               "aΘroport", "aeroport", "contr⌠le aΘrien", "enquΩte",
                               "PV", "procΦs-verbal"],
}


def main():
    reports = json.load(open(REPORTS, encoding="utf-8"))["reports"]

    by_type = Counter(r.get("type", "") for r in reports)
    by_phenom = Counter(r.get("phenomene", "") for r in reports)
    # D-class cases and what typology-concepts they contain
    d_cases = [r for r in reports if r.get("disposition") == "unexplained"]
    aero = [r for r in reports if "aΘro" in (r.get("type", "") or "").lower()
            or "aero" in (r.get("type", "") or "").lower()]

    # For D cases, which typology concepts are present? which are absent (gap)?
    d_typology_hits = Counter()
    d_no_typology = []
    for r in d_cases:
        blob = (r.get("details", "") + " " + r.get("phenomene", "")).lower()
        hit = set()
        for typ, kws in FR_TYPOLOGY.items():
            if any(k in blob for k in kws):
                hit.add(typ)
        for t in hit:
            d_typology_hits[t] += 1
        if not hit:
            d_no_typology.append({"id": r["id"], "type": r.get("type", ""),
                                  "phenom": r.get("phenomene", ""),
                                  "text": r.get("details", "")[:200]})

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "docs/geipan/geipan_reports.json",
        "total": len(reports),
        "case_types": dict(by_type.most_common()),
        "top_phenomena": dict(by_phenom.most_common(12)),
        "d_class_unexplained": len(d_cases),
        "aeronautical_cases": len(aero),
        "d_typology_concept_hits": dict(d_typology_hits.most_common()),
        "d_cases_no_typology_concept": len(d_no_typology),
        "d_gap_samples": d_no_typology[:20],
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=" * 64)
    print("GEIPAN TAXONOMY GAP ANALYSIS (French govt)")
    print("=" * 64)
    print(f"  Total cases: {len(reports)}  | D-class unexplained: {len(d_cases)}  | aeronautical: {len(aero)}")
    print(f"\n  Case TYPE distribution:")
    for t, c in by_type.most_common():
        print(f"    {c:>5}  {t}")
    print(f"\n  Top phenomena categories (GEIPAN's own labels):")
    for p, c in by_phenom.most_common(10):
        print(f"    {c:>5}  {p[:60]}")
    print(f"\n  Among D-class (unexplained), typology-concept coverage:")
    for t, c in d_typology_hits.most_common():
        print(f"    {c:>4}/{len(d_cases)}  {t}")
    print(f"  D-class cases with NO modeled typology concept: {len(d_no_typology)}")
    print(f"\n  Output: {os.path.relpath(OUT, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
