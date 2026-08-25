#!/usr/bin/env python3
"""Build ingest seed from PURSUE Release 02 OCR docs + curated case writeups.

Source (wretcher207/the-ufo-files):
  raw/pursue-release-02-ocr/*.txt   (full OCR of the 6 R02 documents: CIA/DOE/DOW/ODNI)
  pursue-release-02/cases/*.md      (curated per-case analyst writeups)

These are the NEW text records from Release 02 (our R01 pass didn't have them).
Signature-scan and emit a processed_claims seed.

Output: src/data/conspiracy-seed/ufos_uaps/pursue_r02_claims.json
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
from ufo_full_corpus_signature_scan import load_signatures, score_report

BASE = os.path.join(PROJECT_ROOT, "docs", "pursue", "the-ufo-files")
OCR_DIR = os.path.join(BASE, "raw", "pursue-release-02-ocr")
CASES_DIR = os.path.join(BASE, "pursue-release-02", "cases")
OUT = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufos_uaps", "pursue_r02_claims.json")

FRONT = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def collect():
    items = []
    if os.path.isdir(OCR_DIR):
        for f in os.listdir(OCR_DIR):
            if f.endswith(".txt"):
                txt = open(os.path.join(OCR_DIR, f), encoding="utf-8", errors="replace").read()
                items.append((f, txt, "ocr_document"))
    if os.path.isdir(CASES_DIR):
        for f in os.listdir(CASES_DIR):
            if f.endswith(".md"):
                txt = FRONT.sub("", open(os.path.join(CASES_DIR, f), encoding="utf-8", errors="replace").read())
                items.append((f, txt, "case_writeup"))
    return items


def main():
    sigs = load_signatures()
    items = collect()
    claims = []
    for name, text, kind in items:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 50:
            continue
        fired = score_report(text[:20000].lower(), sigs)[0]
        fired_sids = [s for s, _ in fired]
        claims.append({
            "id": f"pursue-r02-{re.sub(r'[^a-zA-Z0-9]+','-', name)[:50]}",
            "title": name.rsplit(".", 1)[0][:120],
            "source": "PURSUE/war.gov (Release 02)",
            "claim": text[:20000],
            "dataset": "ufos_uaps",
            "category": "institutional_response",
            "record_kind": kind,
            "fired_signatures": fired_sids,
            "priority_score": len(fired_sids),
            "score": round(min(1.0, 0.6 + len(fired_sids) * 0.05), 3),
            "verdict": "official_government_record",
            "standard": "scientific",
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
            "source_dataset": "PURSUE Release 02 (US Dept of War / war.gov) OCR + curated cases via wretcher207/the-ufo-files",
            "note": "R02 documents: CIA USSR Sary-Shagan, DOE Los Alamos/Sandia green fireballs, ODNI USPER narrative, DOW.",
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    from collections import Counter
    print(f"Built {len(claims)} R02 claims -> {os.path.relpath(OUT, PROJECT_ROOT)}")
    print(f"  kinds: {dict(Counter(c['record_kind'] for c in claims))}")
    print(f"  with >=1 signature: {sum(1 for c in claims if c['fired_signatures'])}")
    for c in claims:
        print(f"    {c['title'][:50]:<52} sigs={len(c['fired_signatures'])}")


if __name__ == "__main__":
    main()
