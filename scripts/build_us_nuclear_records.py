"""US nuclear-UAP documented anchor cases for the Nuclear Sentinel dossier.
Public, source-cited (declassified USAF records, congressional testimony, FOIA).
source=US-NUKE-DOCUMENTED, country=US, real coordinates.

Output: docs/us-nuclear/us_nuclear_uap.json
"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "us-nuclear")

RECORDS = [
    {
        "id": "US-NUKE-malmstrom-1967",
        "date": "1967-03-16",
        "city": "Malmstrom AFB (Echo/Oscar Flights)",
        "lat": 47.505, "lng": -111.183,
        "desc": ("On 16 March 1967 at Malmstrom Air Force Base, Montana, a Minuteman ICBM flight "
                 "(Echo Flight) reportedly lost up to ten missiles to a 'no-go' fault in rapid "
                 "succession while security personnel above ground reported an unidentified glowing "
                 "object hovering over the facility; a similar event was described at Oscar Flight. "
                 "Former missile-launch officers (notably Robert Salas) later testified publicly and the "
                 "events are documented in declassified USAF records. The objects loitered over a nuclear "
                 "weapons site and coincided with missiles going off alert.")
    },
    {
        "id": "US-NUKE-sac-wave-1975",
        "date": "1975-10-27",
        "city": "Loring / Wurtsmith / Malmstrom (SAC bases)",
        "lat": 46.95, "lng": -67.88,
        "desc": ("In late October and November 1975 a wave of unidentified craft and lights was reported "
                 "over Strategic Air Command bases including Loring AFB (Maine), Wurtsmith AFB (Michigan), "
                 "and Malmstrom AFB (Montana), several of which stored nuclear weapons. Security teams and "
                 "aircrews reported objects hovering over weapons-storage and alert areas; the events were "
                 "logged in USAF message traffic later released under FOIA. Interceptors were launched in "
                 "some instances without achieving identification.")
    },
    {
        "id": "US-NUKE-rendlesham-bentwaters-1980",
        "date": "1980-12-26",
        "city": "RAF Bentwaters / Woodbridge (Rendlesham)",
        "lat": 52.095, "lng": 1.435,
        "desc": ("Over several nights in late December 1980, US Air Force personnel stationed at the "
                 "twin NATO bases RAF Bentwaters and Woodbridge in England — bases reported to store "
                 "nuclear weapons — observed an unidentified structured craft in Rendlesham Forest. "
                 "Deputy base commander Lt Col Charles Halt recorded a real-time audio log and filed an "
                 "official memorandum describing lights maneuvering near the weapons-storage area and "
                 "beams directed toward the base. One of the most documented military nuclear-adjacent cases.")
    }
]


def main():
    recs = []
    for r in RECORDS:
        recs.append({
            "id": r["id"], "source": "US-NUKE-DOCUMENTED", "date": r["date"],
            "description": r["desc"], "city": r["city"], "district": "",
            "country": ("GB" if "rendlesham" in r["id"] else "US"),
            "lat": r["lat"], "lng": r["lng"],
            "source_url": "https://www.archives.gov/research/military/air-force/ufos",
        })
    doc = {
        "source": "US nuclear-UAP documented anchor cases (declassified USAF / FOIA / testimony)",
        "licence": "summaries of public/declassified events with source links",
        "count": len(recs), "reports": recs,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(doc, open(os.path.join(OUT_DIR, "us_nuclear_uap.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"Built {len(recs)} US-NUKE-DOCUMENTED records -> docs/us-nuclear/us_nuclear_uap.json")
    print("  by country:", dict(Counter(r["country"] for r in recs)))


if __name__ == "__main__":
    main()
