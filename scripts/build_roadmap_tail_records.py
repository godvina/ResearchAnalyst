"""Build UAP records for the roadmap-tail documented cases not yet ingested:
Mexico 2004 Campeche FLIR (Air Force / SEDENA) and Italy (CUN / Aeronautica Militare).
Documented-case pattern; public, source-cited; real coordinates.

Output: docs/roadmap-tail/roadmap_tail_uap.json
"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "roadmap-tail")

RECORDS = [
    {
        "id": "MX-SEDENA-campeche-2004",
        "source": "MX-SEDENA",
        "date": "2004-03-05",
        "city": "Campeche (Gulf of Mexico patrol)",
        "country": "MX",
        "lat": 18.64, "lng": -91.83,
        "desc": ("On 5 March 2004 a Mexican Air Force Merlin C26A surveillance aircraft on an anti-drug "
                 "patrol over Campeche recorded, on forward-looking infrared (FLIR), multiple unidentified "
                 "objects that the crew could not see visually and that were not on primary radar. The "
                 "objects appeared to surround the aircraft. Mexico's Defence Secretariat (SEDENA) released "
                 "the FLIR footage publicly — a rare official military infrared UAP record."),
        "sigs": ["uap-em-rv-002", "uap-cm-formation-001", "uap-wr-cred-001", "uap-ir-off-001"],
        "url": "https://en.wikipedia.org/wiki/2004_Mexican_UFO_incident"
    },
    {
        "id": "IT-CUN-national",
        "source": "IT-CUN",
        "date": "2000-01-01",
        "city": "Rome (national reporting)",
        "country": "IT",
        "lat": 41.902, "lng": 12.496,
        "desc": ("Italy's Centro Ufologico Nazionale (CUN) and the Italian Air Force (Aeronautica "
                 "Militare, which maintains an official reporting channel) have collected and analysed "
                 "unidentified-aerial-object reports for decades, including radar-visual military cases "
                 "and multi-witness civilian sightings of disc and luminous objects across Italy."),
        "sigs": ["uap-cm-disc-001", "uap-em-rv-001", "uap-et-mass-001", "uap-ir-off-001"],
        "url": "https://en.wikipedia.org/wiki/Centro_Ufologico_Nazionale"
    }
]


def main():
    recs = []
    for r in RECORDS:
        recs.append({
            "id": r["id"], "source": r["source"], "date": r["date"],
            "description": r["desc"], "city": r["city"], "district": "",
            "country": r["country"], "lat": r["lat"], "lng": r["lng"],
            "source_url": r["url"],
        })
    doc = {
        "source": "Roadmap-tail documented cases (Mexico SEDENA, Italy CUN)",
        "licence": "summaries of public events with source links",
        "count": len(recs), "reports": recs,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(doc, open(os.path.join(OUT_DIR, "roadmap_tail_uap.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"Built {len(recs)} roadmap-tail records -> docs/roadmap-tail/roadmap_tail_uap.json")
    print("  by source:", dict(Counter(r["source"] for r in recs)))


if __name__ == "__main__":
    main()
