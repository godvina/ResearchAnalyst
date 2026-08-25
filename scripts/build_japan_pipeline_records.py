"""Normalize the Japan documented-precedent seed into pipeline records (source=JP-SEED).

Honest sourcing note: unlike Spain (archive.org OCR), Russia (archive.org 'Cosmic
Samizdat' OCR), and Ukraine (arXiv papers), there is NO licence-clean BULK Japanese
UFO dataset that can be downloaded. ufojapan.org is a curated editorial site (scraping
would be ToS-dubious) and Enigma Labs' ~380 Japan reports are a commercial product, not
a bulk export. So Japan's contribution to the corpus is the set of rigorously
DOCUMENTED, source-cited cases (JAL1628, Kofu, Senganmori, SDF-nuclear, Kera) — the same
treatment given to the Russia documented cases. These are KNOWN historical events with
citations, not fabricated sightings.

Candidate future NGO/instrument sources (documented in the registry, not yet ingested):
  Galileo Project (Harvard/Loeb) all-sky IR arrays — arXiv/MDPI published data
  Sol Foundation citizen-science initiative
  Enigma Labs public report corpus (licence permitting)

Input:  src/data/conspiracy-seed/japan_uap/japan_seed.json
Output: docs/japan-ufo/japan_uap.json  (source=JP-SEED, country=JP, real coords)
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "src", "data", "conspiracy-seed", "japan_uap", "japan_seed.json")
OUT_DIR = os.path.join(ROOT, "docs", "japan-ufo")


def main():
    d = json.load(open(SEED, encoding="utf-8"))
    recs = []
    for c in d["cases"]:
        recs.append({
            "id": c["id"],
            "source": "JP-SEED",
            "date": c.get("date", ""),
            "description": c["description"],
            "city": c.get("city", ""),
            "district": "",
            "country": c.get("country", "JP"),
            "lat": c.get("lat"), "lng": c.get("lng"),
            "source_url": c.get("source_url", ""),
        })
    doc = {
        "source": "Japan documented-precedent cases (public, source-cited)",
        "licence": "summaries of public historical events with source links",
        "note": ("Japan has no licence-clean BULK dataset; contribution is documented cases. "
                 "NGO/instrument candidates for later: Galileo Project, Sol Foundation, Enigma Labs."),
        "count": len(recs),
        "reports": recs,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(doc, open(os.path.join(OUT_DIR, "japan_uap.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"Built {len(recs)} JP-SEED records -> docs/japan-ufo/japan_uap.json")
    for r in recs:
        print(f"  {r['id']}  {r['date']}  {r['city']} ({r['country']})")


if __name__ == "__main__":
    main()
