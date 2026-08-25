#!/usr/bin/env python3
"""Fetch the Spanish Air Force declassified UFO files (public domain, CC0) from
archive.org item 'SpanishUFOFiles', and normalize into the pipeline record shape.

We download ONLY the small OCR text derivatives (_djvu.txt), NOT the multi-GB
PDF scans. Each case file name encodes date + Spanish location, e.g.
  1968-03-14_avistamiento_en_villa_cisneros_djvu.txt
The OCR text (Spanish) becomes the description for signature matching.

Source: https://archive.org/details/SpanishUFOFiles
Licence: CC0 / Public Domain Mark 1.0 (Ministerio de Defensa, Espana)

Output:
  docs/spanish-ufo/spain_airforce_ufo.json   (records: id, source, date, description, city, country=ES)
  provenance recorded for the data registry.
"""
import json
import os
import re
import urllib.request
import urllib.parse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJECT_ROOT, "docs", "spanish-ufo")
META_URL = "https://archive.org/metadata/SpanishUFOFiles"
DL_BASE = "https://archive.org/download/SpanishUFOFiles/"

def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "TALOS-demo-research/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", errors="replace")

def parse_name(fn):
    """1968-03-14_avistamiento_en_villa_cisneros_djvu.txt -> (date, place)."""
    base = fn.replace("_djvu.txt", "")
    m = re.match(r"((?:\d{4}-\d{2}-\d{2}|\d{4})(?:[-_].*?)?)_avistamiento_(?:en|entre|de)_(.+)", base)
    date_part, place = "", ""
    dm = re.match(r"(\d{4})-(\d{2})-(\d{2})", base)
    date = ""
    if dm:
        date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)} 00:00:00"
    else:
        ym = re.match(r"(\d{4})", base)
        if ym:
            date = f"{ym.group(1)}-01-01 00:00:00"
    pm = re.search(r"avistamiento_(?:en|entre|de)_(.+)", base)
    if pm:
        place = pm.group(1).replace("_", " ").replace("-", ", ").strip()
        place = re.sub(r"\s*\(.*?\)", "", place)  # drop province parens for city
    return date, place.title()

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Fetching archive.org metadata…")
    meta = json.loads(fetch(META_URL))
    files = meta["files"]
    # per-case OCR text derivatives (skip the master listado/normativa admin docs)
    txts = [f["name"] for f in files if f["name"].endswith("_djvu.txt")
            and f["name"].startswith(("19",))]
    print(f"  {len(txts)} per-case OCR text files")

    records = []
    for i, fn in enumerate(txts):
        date, place = parse_name(fn)
        try:
            text = fetch(DL_BASE + urllib.parse.quote(fn))
        except Exception as e:
            print(f"   skip {fn}: {e}")
            continue
        # clean OCR whitespace; keep it as the Spanish-language description
        desc = re.sub(r"\s+", " ", text).strip()
        records.append({
            "id": "ES-" + fn.replace("_djvu.txt", ""),
            "source": "ES-AIRFORCE",
            "date": date,
            "description": desc[:4000],
            "city": place, "district": "", "country": "ES", "water": "",
            "source_url": "https://archive.org/details/SpanishUFOFiles",
        })
        if (i + 1) % 20 == 0:
            print(f"   {i+1}/{len(txts)} downloaded")

    out = {"count": len(records), "source": "Spanish Air Force / Ministerio de Defensa (CC0)",
           "source_url": "https://archive.org/details/SpanishUFOFiles",
           "reports": records}
    outpath = os.path.join(OUT_DIR, "spain_airforce_ufo.json")
    json.dump(out, open(outpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Wrote {len(records)} Spanish records -> {os.path.relpath(outpath, PROJECT_ROOT)}")

if __name__ == "__main__":
    main()
