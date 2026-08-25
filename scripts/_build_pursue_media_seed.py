#!/usr/bin/env python3
"""Build ingest seed from PURSUE video/image records (the 42 our PDF-only pass missed).

Source: docs/pursue/all-releases/records.json (vfp2 index; each record has an analyst
`description`). Our first PURSUE pass only ingested the 120 PDFs. The 28 video + 14 image
records carry substantive descriptions — including the USO/maritime cases (Aegean Sea,
Persian Gulf, Gulf of Oman) that validate the maritime signatures. Ingest those.

Output: src/data/conspiracy-seed/ufos_uaps/pursue_media_claims.json
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
from ufo_full_corpus_signature_scan import load_signatures, score_report

REC = os.path.join(PROJECT_ROOT, "docs", "pursue", "all-releases", "records.json")
OUT = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufos_uaps", "pursue_media_claims.json")


def main():
    recs = json.load(open(REC, encoding="utf-8"))
    media = [r for r in recs if r.get("type") in ("VID", "IMG")]
    sigs = load_signatures()

    claims = []
    for r in media:
        title = (r.get("title") or "").strip()
        desc = (r.get("description") or "").strip()
        loc = (r.get("incident_location") or "").strip()
        date = (r.get("incident_date") or "").strip()
        text = f"{title}. {desc} Location: {loc}. Date: {date}. Media type: {r.get('type')}."
        fired = score_report(text.lower(), sigs)[0]
        fired_sids = [s for s, _ in fired]
        title_slug = re.sub(r"[^a-zA-Z0-9]+", "-", title)[:50]
        claims.append({
            "id": f"pursue-media-{title_slug}",
            "title": title[:120] or "PURSUE media record",
            "source": "PURSUE/war.gov",
            "claim": text,
            "dataset": "ufos_uaps",
            "category": "institutional_response",
            "fired_signatures": fired_sids,
            "media_type": r.get("type"),
            "agency": r.get("agency", ""),
            "priority_score": len(fired_sids),
            "score": round(min(1.0, 0.6 + len(fired_sids) * 0.05), 3),
            "verdict": "official_government_record",
            "standard": "scientific",
            "source_url": r.get("pdf_link", ""),
            "location": {"raw": loc},
            "country": "US",
        })

    doc = {
        "dataset_name": "ufos_uaps",
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "claim_count": len(claims),
        "claims": claims,
        "cross_domain_scoring": True,
        "tenant_id": "conspiracy_theories",
        "provenance": {
            "source_dataset": "PURSUE video/image records (analyst descriptions) via vfp2/pursue-ufo-files index",
            "note": "The 28 video + 14 image records our PDF-only first pass missed; includes USO/maritime cases.",
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    from collections import Counter
    print(f"Built {len(claims)} media claims -> {os.path.relpath(OUT, PROJECT_ROOT)}")
    print(f"  media types: {dict(Counter(c['media_type'] for c in claims))}")
    print(f"  with >=1 signature: {sum(1 for c in claims if c['fired_signatures'])}")


if __name__ == "__main__":
    main()
