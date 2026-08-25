#!/usr/bin/env python3
"""Build the full NUFORC signal-set seed (all signature-firing reports) for ingest.

Input:  scripts/ufo_signal_reports.json  (from ufo_full_corpus_signature_scan.py)
Output: src/data/conspiracy-seed/ufos_uaps/signal_claims.json  (processed_claims format)

These are ALL ~8,764 reports that fired >=1 taxonomy signature across the full
60,632-report corpus — the pattern-bearing subset (skips the ~52K non-firing noise
reports). Ingest with scripts/_ingest_ufos_uaps.py --claims-file signal_claims.json.
"""
import json
import os
import re
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNAL = os.path.join(PROJECT_ROOT, "scripts", "ufo_signal_reports.json")
OUT = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufos_uaps", "signal_claims.json")


def _clean(t):
    if not t:
        return ""
    t = t.replace("&#44", ",").replace("&#39", "'").replace("&amp;", "&").replace("&#33", "!").replace("&quot;", '"')
    return re.sub(r"\s+", " ", t).strip()


def main():
    data = json.load(open(SIGNAL, encoding="utf-8"))["reports"]
    claims = []
    for i, r in enumerate(data):
        loc = ", ".join([p for p in (r.get("city", ""), r.get("state", "")) if p])
        primary_typ = (r.get("typologies") or ["craft_morphology"])[0]
        claims.append({
            "id": f"uapsig-{i:05d}",
            "title": f"{(r.get('shape') or 'unknown').title()} sighting — {loc or 'unknown'}",
            "source": "NUFORC",
            "claim": _clean(r.get("description", "")),
            "dataset": "ufos_uaps",
            "category": primary_typ,
            "typology": primary_typ,
            "matched_categories": r.get("typologies", []),
            "fired_signatures": r.get("fired_signatures", []),
            "priority_score": r.get("signature_count", 0),
            "score": round(min(1.0, 0.4 + r.get("signature_count", 0) * 0.1), 3),
            "verdict": "unverified",
            "standard": "intelligence",
            "location": {"city": r.get("city", ""), "state": r.get("state", ""),
                         "lat": r.get("lat", ""), "lng": r.get("lng", "")},
            "year": r.get("year", ""),
            "shape": r.get("shape", ""),
        })

    doc = {
        "dataset_name": "ufos_uaps",
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "claim_count": len(claims),
        "claims": claims,
        "cross_domain_scoring": True,
        "tenant_id": "conspiracy_theories",
        "provenance": {
            "source_dataset": "NUFORC 60,632 (CORGIS) — full signal set (all signature-firing reports)",
            "selection": "all reports that fired >=1 UFO/UAP taxonomy signature in the full-corpus scan",
            "scan": "scripts/ufo_full_corpus_signature_scan.py",
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Built {len(claims)} signal claims -> {os.path.relpath(OUT, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
