#!/usr/bin/env python3
"""Build the GEIPAN ingest seed (processed_claims format) from parsed cases.

Input:  docs/geipan/geipan_reports.json  (from _geipan_calibrate.py)
Output: src/data/conspiracy-seed/ufos_uaps/geipan_claims.json

Carries the OFFICIAL A/B/C/D disposition into each claim as ground-truth metadata
(this is what makes GEIPAN uniquely valuable in the graph). All 3,381 cases.
Ingest with scripts/_ingest_ufos_uaps.py --claims-file geipan_claims.json.
"""
import json
import os
import re
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(PROJECT_ROOT, "docs", "geipan", "geipan_reports.json")
OUT = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufos_uaps", "geipan_claims.json")


def _clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def main():
    reports = json.load(open(REPORTS, encoding="utf-8"))["reports"]
    claims = []
    for r in reports:
        loc = ", ".join([p for p in (r.get("departement", ""), "France") if p])
        narrative = _clean(r.get("details", ""))
        official = _clean(r.get("official_identification", ""))
        # include official identification + classification in the text so the
        # pipeline's entity extraction sees the disposition context
        text = narrative
        if official:
            text += f"  [Official GEIPAN identification: {official}]"
        claims.append({
            "id": f"geipan-{r['id']}",
            "title": _clean(r.get("title", "")) or f"GEIPAN case {r['id']}",
            "source": "GEIPAN",
            "claim": text,
            "dataset": "ufos_uaps",
            "category": "institutional_response",
            "geipan_classification": r.get("classification", ""),
            "disposition": r.get("disposition", ""),
            "phenomenon": _clean(r.get("phenomene", "")),
            "case_type": _clean(r.get("type", "")),
            "verdict": "official_" + r.get("disposition", "unknown"),
            "standard": "scientific",
            "location": {"departement": r.get("departement", ""), "country": "FR",
                         "lat": r.get("lat", ""), "lng": r.get("lng", "")},
            "country": "FR",
            "year": r.get("year", ""),
        })

    doc = {
        "dataset_name": "ufos_uaps",
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "claim_count": len(claims),
        "claims": claims,
        "cross_domain_scoring": True,
        "tenant_id": "conspiracy_theories",
        "provenance": {
            "source_dataset": "GEIPAN / CNES (official French UAP investigations), export_cas.xlsx",
            "ground_truth": "each case carries official A/B/C/D classification + disposition",
            "calibration": "scripts/geipan_calibration.json",
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    from collections import Counter
    print(f"Built {len(claims)} GEIPAN claims -> {os.path.relpath(OUT, PROJECT_ROOT)}")
    print(f"  dispositions: {dict(Counter(c['disposition'] for c in claims))}")


if __name__ == "__main__":
    main()
