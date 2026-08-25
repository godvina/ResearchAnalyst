"""Fetch the public 'UFO Chronicles of the Soviet Union: A Cosmic Samizdat' OCR text
from archive.org and normalize it into the global UAP pipeline record shape.

We download ONLY the small OCR text derivative (_djvu.txt, ~380KB), NOT the 92MB scan zip
(mirrors fetch_spanish_ufo_files.py). The book is a compiled English-language chronicle of
Soviet-era UFO reports (the samizdat/self-published tradition). We segment the OCR text into
report-sized chunks and keep those that read like sighting accounts.

This is the "creative-search" real Russian corpus the user asked for: a Russian/Soviet body
of UFO knowledge, publicly readable, distinct from the (not-cleanly-obtainable) raw KGB files.

Source item: https://archive.org/details/B-001-002-573
Provenance also cites the smuggled Soviet 'anomalous phenomena' archive associated with
cosmonaut Pavel Popovich (revealed publicly 2026), documented as a precedent (not ingested).

Output:
  docs/russia-ufo/soviet_ufo_chronicles.txt          (raw OCR text, cached)
  docs/russia-ufo/russia_ufo.json                    (records: id, source=RU-SAMIZDAT, ...)
"""
import json
import os
import re
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJECT_ROOT, "docs", "russia-ufo")
ITEM = "B-001-002-573"
# The generic /download/ path 302s to a data node that can 500; hit the workable data
# nodes directly (from the item metadata), with mirrors as fallback.
TXT_URLS = [
    f"https://archive.org/download/{ITEM}/{ITEM}_djvu.txt",
    f"https://ia600406.us.archive.org/20/items/{ITEM}/{ITEM}_djvu.txt",
    f"https://ia800406.us.archive.org/20/items/{ITEM}/{ITEM}_djvu.txt",
    f"https://dn760100.eu.archive.org/0/items/{ITEM}/{ITEM}_djvu.txt",
    f"https://dn790009.ca.archive.org/0/items/{ITEM}/{ITEM}_djvu.txt",
]

# Russian/Soviet cities with public coords, for placing chunks that name them.
RU_CITIES = {
    "moscow": (55.751, 37.618), "petrozavodsk": (61.785, 34.346),
    "voronezh": (51.672, 39.184), "dalnegorsk": (44.556, 135.567),
    "leningrad": (59.939, 30.314), "st petersburg": (59.939, 30.314),
    "kiev": (50.4501, 30.5234), "kyiv": (50.4501, 30.5234),
    "gorky": (56.297, 43.936), "sverdlovsk": (56.838, 60.605),
    "novosibirsk": (55.008, 82.935), "vladivostok": (43.115, 131.886),
    "minsk": (53.902, 27.562), "tbilisi": (41.716, 44.783),
    "kharkov": (49.994, 36.230), "rostov": (47.235, 39.701),
    "murmansk": (68.969, 33.075), "arkhangelsk": (64.539, 40.518),
    "baikal": (53.5, 108.0), "siberia": (60.0, 90.0), "crimea": (45.0, 34.0),
}
RU_CENTROID = (55.75, 37.62)  # fallback: Moscow-ish, jittered

SIGHTING_HINTS = ("ufo", "object", "disc", "disk", "sphere", "craft", "light",
                  "hovered", "hovering", "glowing", "sky", "witness", "landed",
                  "luminous", "flying", "silent", "beam")


def fetch_text():
    os.makedirs(OUT_DIR, exist_ok=True)
    cache = os.path.join(OUT_DIR, "soviet_ufo_chronicles.txt")
    if os.path.exists(cache) and os.path.getsize(cache) > 10000:
        return open(cache, encoding="utf-8", errors="replace").read()
    last_err = None
    for url in TXT_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (TALOS-demo-research)"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read().decode("utf-8", errors="replace")
            if len(data) > 10000:
                open(cache, "w", encoding="utf-8").write(data)
                print(f"  fetched from {url}")
                return data
        except Exception as e:
            last_err = e
            print(f"  (miss: {url} -> {e})")
            continue
    raise RuntimeError(f"All archive.org mirrors failed. Last error: {last_err}")


def geocode_chunk(text):
    low = text.lower()
    for city, (lat, lng) in RU_CITIES.items():
        if city in low:
            return city.title(), lat, lng
    return "", RU_CENTROID[0], RU_CENTROID[1]


def main():
    text = fetch_text()
    # normalize whitespace, split into paragraph-ish chunks on blank lines / big gaps
    text = re.sub(r"\r", "", text)
    raw_chunks = re.split(r"\n\s*\n", text)
    records = []
    seen = set()
    n = 0
    for ch in raw_chunks:
        c = re.sub(r"\s+", " ", ch).strip()
        if len(c) < 120:            # too short to be a report
            continue
        low = c.lower()
        if sum(1 for h in SIGHTING_HINTS if h in low) < 2:
            continue                # not sighting-like
        key = low[:80]
        if key in seen:
            continue
        seen.add(key)
        city, lat, lng = geocode_chunk(c)
        # crude year extraction
        ym = re.search(r"\b(19[3-9]\d|20[0-2]\d)\b", c)
        year = ym.group(1) if ym else ""
        n += 1
        records.append({
            "id": f"RU-SAMIZDAT-{n:04d}",
            "source": "RU-SAMIZDAT",
            "date": f"{year}-01-01" if year else "",
            "description": c[:1200],
            "city": city,
            "district": "",
            "country": "RU",
            "lat": lat, "lng": lng,   # pipeline honors these
        })

    doc = {
        "source": "UFO Chronicles of the Soviet Union: A Cosmic Samizdat (archive.org item B-001-002-573)",
        "licence": "Public (archive.org text derivative); English-language compiled chronicle",
        "precedent_note": ("Related precedent (NOT ingested): the smuggled Soviet 'anomalous "
                           "phenomena' archive associated with cosmonaut Pavel Popovich, "
                           "publicly revealed 2026 — the ~127-page KGB record and Program Setka files."),
        "count": len(records),
        "reports": records,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(doc, open(os.path.join(OUT_DIR, "russia_ufo.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    placed = sum(1 for r in records if r["city"])
    print(f"Built {len(records)} RU-SAMIZDAT records -> docs/russia-ufo/russia_ufo.json")
    print(f"  city-placed: {placed}/{len(records)} (rest use Russia centroid)")
    from collections import Counter
    print(f"  top cities: {dict(Counter(r['city'] for r in records if r['city']).most_common(8))}")


if __name__ == "__main__":
    main()
