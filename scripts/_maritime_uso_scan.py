#!/usr/bin/env python3
"""Maritime / USO (Unidentified Submerged Object) frontier scan.

Before building a full vision pipeline for PURSUE videos, mine ALL text we already
have (NUFORC, UPDB, GEIPAN, PURSUE OCR) for maritime / trans-medium / submerged cases.
This tells us whether the maritime pattern has enough DENSITY to ground new signatures
(per the master-loop: don't author a signature the data can't support).

Sources scanned (whichever exist):
  docs/updb/updb_reports.json                       (global, incl. water body field)
  src/data/conspiracy-seed/ufo_sightings/ufo_sightings.csv  (NUFORC)
  docs/geipan/geipan_reports.json                   (French, incl. maritime case type)
  docs/pursue/UFO-USA/converted/**/page-*.md        (US govt OCR)

Output: scripts/maritime_uso_scan.json
"""
import csv
import glob
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJECT_ROOT, "scripts", "maritime_uso_scan.json")

# Maritime / trans-medium / submerged terms (EN + FR)
MARITIME = [
    "ocean", "sea", "water", "submerged", "underwater", "dove into", "dived into",
    "entered the water", "out of the water", "rose from the sea", "splash", "wake",
    "into the ocean", "beneath the surface", "submarine", "naval", "off the coast",
    "sonar", "trans-medium", "transmedium", "uso", "vessel", "ship", "buoy",
    # French
    "mer", "ocΘan", "ocean", "sous l'eau", "immergΘ", "immerge", "plongΘ", "plonge",
    "maritime", "navire", "bateau",
]
MARITIME_RE = re.compile("|".join(re.escape(t) for t in MARITIME), re.IGNORECASE)
# stronger trans-medium (air<->water transition) phrases = highest value
TRANSMEDIUM_RE = re.compile(
    r"(into the (ocean|sea|water)|out of the (ocean|sea|water)|entered the water|"
    r"emerged from the (sea|water|ocean)|dove into|no splash|beneath the surface|submerged)",
    re.IGNORECASE)


def scan_text_records(records, text_key, src_label, extra=None):
    hits = []
    tm = 0
    for r in records:
        t = r.get(text_key) or ""
        if len(t) < 15:
            continue
        if MARITIME_RE.search(t):
            is_tm = bool(TRANSMEDIUM_RE.search(t))
            tm += 1 if is_tm else 0
            hits.append({"source": src_label, "transmedium": is_tm,
                         "country": r.get("country", ""), "text": t[:200],
                         **(extra(r) if extra else {})})
    return hits, tm


def main():
    all_hits = []
    tm_total = 0
    per_source = Counter()

    # UPDB
    updb = os.path.join(PROJECT_ROOT, "docs", "updb", "updb_reports.json")
    if os.path.exists(updb):
        recs = json.load(open(updb, encoding="utf-8"))["reports"]
        # UPDB also has an explicit 'water' field from the location table
        for r in recs:
            r["_text"] = (r.get("description") or "") + " " + (r.get("water") or "")
        h, tm = scan_text_records(recs, "_text", "UPDB")
        all_hits += h; tm_total += tm; per_source["UPDB"] = len(h)

    # NUFORC
    nuforc = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufo_sightings", "ufo_sightings.csv")
    if os.path.exists(nuforc):
        recs = []
        with open(nuforc, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                recs.append({"description": row.get("Data.Description excerpt", ""), "country": row.get("Location.Country", "")})
        h, tm = scan_text_records(recs, "description", "NUFORC")
        all_hits += h; tm_total += tm; per_source["NUFORC"] = len(h)

    # GEIPAN
    geipan = os.path.join(PROJECT_ROOT, "docs", "geipan", "geipan_reports.json")
    if os.path.exists(geipan):
        recs = json.load(open(geipan, encoding="utf-8"))["reports"]
        for r in recs:
            r["_text"] = (r.get("details") or "") + " " + (r.get("type") or "")
        h, tm = scan_text_records(recs, "_text", "GEIPAN", extra=lambda r: {"disposition": r.get("disposition", "")})
        all_hits += h; tm_total += tm; per_source["GEIPAN"] = len(h)

    # PURSUE OCR pages
    pursue_glob = os.path.join(PROJECT_ROOT, "docs", "pursue", "UFO-USA", "converted", "*", "page-*.md")
    pfiles = glob.glob(pursue_glob)
    p_hits = 0; p_tm = 0
    for fp in pfiles:
        txt = open(fp, encoding="utf-8", errors="replace").read()
        if MARITIME_RE.search(txt):
            is_tm = bool(TRANSMEDIUM_RE.search(txt))
            p_tm += 1 if is_tm else 0
            p_hits += 1
            if len([x for x in all_hits if x["source"] == "PURSUE"]) < 40:
                all_hits.append({"source": "PURSUE", "transmedium": is_tm, "country": "US",
                                 "text": re.sub(r"\s+", " ", txt)[:200], "file": os.path.basename(os.path.dirname(fp))})
    per_source["PURSUE"] = p_hits; tm_total += p_tm

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "maritime_hits_by_source": dict(per_source),
        "maritime_hits_total": sum(per_source.values()),
        "transmedium_strong_hits": tm_total,
        "geipan_maritime_dispositions": dict(Counter(
            h.get("disposition", "") for h in all_hits if h["source"] == "GEIPAN")),
        "transmedium_samples": [h for h in all_hits if h["transmedium"]][:20],
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=" * 60)
    print("MARITIME / USO FRONTIER SCAN")
    print("=" * 60)
    print(f"  Maritime hits by source: {dict(per_source)}")
    print(f"  Total maritime hits:     {sum(per_source.values())}")
    print(f"  Strong trans-medium (air<->water) hits: {tm_total}")
    print(f"\n  Sample trans-medium cases:")
    for h in out["transmedium_samples"][:10]:
        print(f"    [{h['source']}|{h.get('country','')}] {h['text'][:110]}")
    print(f"\n  Output: {os.path.relpath(OUT, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
