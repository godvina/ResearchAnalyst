#!/usr/bin/env python3
"""Consolidate PURSUE OCR pages into documents, Tier-1 filter, signature-scan, build seed.

Source: docs/pursue/UFO-USA/converted/<document>/page-*.md  (4,185 OCR pages, Gemini-converted)
Each document = one PURSUE file (FBI/NASA/AARO/State/DoW). We consolidate its pages,
strip the YAML front-matter, Tier-1 keyword-score (reuse ufo_tiered_scan), signature-scan
(reuse full-corpus scan), and emit a processed_claims seed + a gap report.

Outputs:
  src/data/conspiracy-seed/ufos_uaps/pursue_claims.json   (one claim per document, filtered)
  scripts/pursue_scan.json                                (Tier-1 + signature + gap summary)
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
from ufo_tiered_scan import score_report_tier1
from ufo_full_corpus_signature_scan import load_signatures, score_report

CONVERTED = os.path.join(PROJECT_ROOT, "docs", "pursue", "UFO-USA", "converted")
OUT_CLAIMS = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufos_uaps", "pursue_claims.json")
OUT_SCAN = os.path.join(PROJECT_ROOT, "scripts", "pursue_scan.json")

FRONT_MATTER = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
MAX_DOC_CHARS = 20000  # cap per-document text for ingest doc size


def read_doc(doc_dir):
    """Concatenate all page-*.md of a document, stripping front-matter. Returns (text, meta)."""
    pages = sorted([f for f in os.listdir(doc_dir) if f.startswith("page-") and f.endswith(".md")])
    texts = []
    meta = {}
    for p in pages:
        raw = open(os.path.join(doc_dir, p), encoding="utf-8", errors="replace").read()
        if not meta:
            for key in ("source_title", "source_url", "asset_type", "page_count"):
                m = re.search(rf'{key}:\s*"?([^"\n]+)"?', raw)
                if m:
                    meta[key] = m.group(1).strip()
        body = FRONT_MATTER.sub("", raw)
        body = re.sub(r"^#.*Page \d+\s*$", "", body, flags=re.MULTILINE)  # drop page headers
        texts.append(body.strip())
    return "\n".join(texts).strip(), meta


def main():
    sigs = load_signatures()
    sig_meta = {s["signature_id"]: s["typology"] for s in sigs}

    docs = [d for d in os.listdir(CONVERTED) if os.path.isdir(os.path.join(CONVERTED, d))]
    print(f"PURSUE documents: {len(docs)}")

    claims = []
    total = kept = 0
    sig_fire = Counter()
    typ_fire = Counter()
    gap_docs = []  # high-Tier1, zero-signature

    for d in docs:
        total += 1
        text, meta = read_doc(os.path.join(CONVERTED, d))
        if len(text) < 50:
            continue
        t1 = score_report_tier1(text[:MAX_DOC_CHARS], "")
        fired, _ = score_report(text[:MAX_DOC_CHARS].lower(), sigs)
        fired_sids = [s for s, _ in fired]
        for s in fired_sids:
            sig_fire[s] += 1
        for t in {sig_meta[s] for s in fired_sids}:
            typ_fire[t] += 1
        # keep documents that are interesting (Tier-1 pass OR any signature)
        if not (t1["keep"] or fired_sids):
            if t1["priority_score"] >= 3:
                gap_docs.append({"doc": d, "t1": t1["priority_score"], "cats": list(t1["keyword_hits"].keys())})
            continue
        kept += 1
        claims.append({
            "id": f"pursue-{d[:60]}",
            "title": (meta.get("source_title") or d)[:120],
            "source": "PURSUE/war.gov",
            "claim": text[:MAX_DOC_CHARS],
            "dataset": "ufos_uaps",
            "category": (list({sig_meta[s] for s in fired_sids}) or ["institutional_response"])[0],
            "matched_categories": sorted({sig_meta[s] for s in fired_sids}),
            "fired_signatures": fired_sids,
            "priority_score": t1["priority_score"],
            "score": round(min(1.0, 0.5 + len(fired_sids) * 0.08), 3),
            "verdict": "official_government_record",
            "standard": "scientific",
            "source_url": meta.get("source_url", ""),
            "asset_type": meta.get("asset_type", ""),
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
            "source_dataset": "PURSUE Release 01 (US Dept of War / war.gov/UFO) via DenisSergeevitch/UFO-USA OCR",
            "note": "Official US government declassified UAP records (FBI/NASA/AARO/State/DoW), OCR by community (Gemini).",
        },
    }
    os.makedirs(os.path.dirname(OUT_CLAIMS), exist_ok=True)
    json.dump(doc, open(OUT_CLAIMS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    scan = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents": total, "kept": kept,
        "per_signature_fire": dict(sig_fire.most_common()),
        "per_typology_fire": dict(typ_fire.most_common()),
        "never_fired": [s["signature_id"] for s in sigs if sig_fire[s["signature_id"]] == 0],
        "gap_high_t1_no_signature": len(gap_docs),
        "gap_samples": gap_docs[:20],
    }
    json.dump(scan, open(OUT_SCAN, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"  Documents scanned: {total}  | kept (interesting): {kept}")
    print(f"  Claims -> {os.path.relpath(OUT_CLAIMS, PROJECT_ROOT)}")
    print(f"\n  Per-typology fire:")
    for t, c in typ_fire.most_common():
        print(f"    {t:<26} {c}")
    print(f"  Never fired: {scan['never_fired']}")
    print(f"  Gap (high-T1, no sig): {len(gap_docs)}")
    print(f"  Scan -> {os.path.relpath(OUT_SCAN, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
