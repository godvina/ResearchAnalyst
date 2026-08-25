#!/usr/bin/env python3
"""GEIPAN calibration — validate signatures/negatives against OFFICIAL A/B/C/D dispositions.

GEIPAN (French CNES) officially classifies each case:
  A = identified (certain)      -> EXPLAINED
  B = probably identified       -> EXPLAINED
  C = insufficient information   -> UNCLASSIFIABLE
  D = unexplained (D1/D2)        -> UNEXPLAINED (genuine anomaly)

This is ground truth. We test whether our taxonomy behaves correctly against it:
  - Do the hoax/misidentification NEGATIVE signals concentrate in A/B (explained)?
  - Do high-anomaly signatures (kinematics, EM, radar-visual) concentrate in D (unexplained)?
If yes, our scoring is calibrated: it down-ranks the prosaic and up-ranks the genuine.

Narratives are FRENCH, so we add a small French anomaly/prosaic lexicon on top of the
English needles for a meaningful signal.

Input:  docs/geipan/export_cas.xlsx
Output: docs/geipan/geipan_reports.json  (normalized, for ingest)
        scripts/geipan_calibration.json  (calibration result)
"""
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

import openpyxl

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(PROJECT_ROOT, "docs", "geipan", "export_cas.xlsx")
OUT_REPORTS = os.path.join(PROJECT_ROOT, "docs", "geipan", "geipan_reports.json")
OUT_CALIB = os.path.join(PROJECT_ROOT, "scripts", "geipan_calibration.json")

DISPOSITION = {"A": "explained", "B": "explained", "C": "insufficient",
               "D": "unexplained", "D1": "unexplained", "D2": "unexplained"}

# French prosaic/misID lexicon (maps to our hoax/misID negative concept)
FR_PROSAIC = ["lune", "vΘnus", "venus", "planΦte", "planete", "Θtoile", "etoile",
              "satellite", "ballon", "lanterne", "avion", "hΘlicoptΦre", "helicoptere",
              "mΘtΘore", "meteore", "bolide", "rentrΘe", "rentree", "nuage", "foudre",
              "lampadaire", "drone", "feu d'artifice", "montgolfiΦre", "aΘronef",
              "confusion", "mΘprise", "meprise"]
# French anomaly lexicon (maps to our high-anomaly signatures)
FR_ANOMALY = ["silencieux", "instantanΘ", "instantane", "accΘlΘr", "acceler",
              "disparu", "disparaεt", "immobile", "stationnaire", "vol stationnaire",
              "trΦs Θtrange", "tres etrange", "Θtrange", "etrange", "radar",
              "haute vitesse", "angle droit", "mΘtallique", "metallique", "disque",
              "triangulaire", "sphΦre", "sphere", "trace au sol", "brⁿlure", "brulure"]


def _norm(s):
    return (s or "").lower()


def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))
    # column indices by position (header names have encoding noise)
    #  0 id, 1 titre, 2 details, 3 annee, 4 identification, 5 classification,
    #  6 code_dept, 7 date_obs, 8 departement, 13 lat, 14 lng, 15 phenomene, 18 type
    reports = []
    for r in rows:
        if not r or not r[0]:
            continue
        cls = (r[5] or "").strip().upper()
        cls_base = cls[0] if cls else ""
        reports.append({
            "id": str(r[0]),
            "title": r[1] or "",
            "details": r[2] or "",
            "year": r[3] or "",
            "official_identification": r[4] or "",
            "classification": cls,
            "disposition": DISPOSITION.get(cls, DISPOSITION.get(cls_base, "unknown")),
            "departement": r[8] or "",
            "lat": r[13] or "", "lng": r[14] or "",
            "phenomene": r[15] or "",
            "type": r[18] if len(r) > 18 else "",
            "country": "FR",
            "source": "GEIPAN",
        })

    # Save normalized reports for ingest
    json.dump({"count": len(reports), "reports": reports},
              open(OUT_REPORTS, "w", encoding="utf-8"), ensure_ascii=False)

    # --- Calibration ---
    disp_counts = Counter(r["disposition"] for r in reports)
    # per-disposition: prosaic-hit rate and anomaly-hit rate
    stats = defaultdict(lambda: {"n": 0, "prosaic": 0, "anomaly": 0})
    for r in reports:
        blob = _norm(r["details"] + " " + r["official_identification"] + " " + r["phenomene"])
        d = r["disposition"]
        stats[d]["n"] += 1
        if any(k in blob for k in FR_PROSAIC):
            stats[d]["prosaic"] += 1
        if any(k in blob for k in FR_ANOMALY):
            stats[d]["anomaly"] += 1

    calib = {"disposition": {}}
    for d, s in stats.items():
        n = s["n"] or 1
        calib["disposition"][d] = {
            "cases": s["n"],
            "prosaic_hit_pct": round(100 * s["prosaic"] / n, 1),
            "anomaly_hit_pct": round(100 * s["anomaly"] / n, 1),
        }

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "docs/geipan/export_cas.xlsx (GEIPAN / CNES official)",
        "total_cases": len(reports),
        "disposition_counts": dict(disp_counts),
        "calibration": calib,
        "interpretation": (
            "If calibrated: prosaic_hit_pct should be HIGHER in explained(A/B) than "
            "unexplained(D); anomaly_hit_pct should be HIGHER in unexplained(D) than explained(A/B)."
        ),
    }
    json.dump(out, open(OUT_CALIB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=" * 64)
    print("GEIPAN CALIBRATION (official A/B/C/D ground truth)")
    print("=" * 64)
    print(f"  Total cases: {len(reports)}")
    print(f"  Dispositions: {dict(disp_counts)}")
    print(f"\n  {'disposition':<14}{'cases':>7}{'prosaic%':>10}{'anomaly%':>10}")
    order = ["explained", "insufficient", "unexplained", "unknown"]
    for d in order:
        if d in calib["disposition"]:
            c = calib["disposition"][d]
            print(f"  {d:<14}{c['cases']:>7}{c['prosaic_hit_pct']:>10}{c['anomaly_hit_pct']:>10}")
    print(f"\n  Output: {os.path.relpath(OUT_CALIB, PROJECT_ROOT)}")
    print(f"          {os.path.relpath(OUT_REPORTS, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
