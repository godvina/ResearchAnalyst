"""Build UAP records for Project Hessdalen (Norway) — a long-running NGO/academic field
station, one of the most instrumented recurring-hotspot studies in the world.

Documented public facts (Project Hessdalen, hessdalen.org; Ostfold University College;
Erling Strand). Recurring luminous phenomena in the Hessdalen valley since the 1930s,
peaking 1981-84 (up to 15-20 sightings/week). Project Hessdalen founded 1983 with
military support; instrumented field campaigns (cameras, radar, magnetometers, lasers,
spectrometers, IR) documented dozens of events — famously ~53 in an 18-day 1984 window.
The Automatic Measurement Station (Hessdalen AMS / "Blue Box") has logged data since 1998.

This is the canonical RECURRING HOTSPOT AT A GEOPHYSICAL ANOMALY — it validates the
uap-et-hotspot-001 signature — plus colour-changing, hovering, high-speed orbs.

Output: docs/hessdalen/hessdalen_uap.json  (source=NO-HESSDALEN, country=NO, real coords)
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "hessdalen")
HESSDALEN = (62.783, 11.20)  # Hessdalen valley, Sor-Trondelag, Norway

RECORDS = [
    {
        "id": "NO-HESSDALEN-wave-1984",
        "date": "1984-02-01",
        "desc": ("Project Hessdalen 1984 instrumented field campaign in the Hessdalen valley, Norway. "
                 "Over an 18-day observation window researchers documented about 53 luminous events using "
                 "cameras, radar, magnetometers, lasers and spectrometers. Witnesses and instruments "
                 "recorded self-luminous orbs that hover for minutes, dart across the sky at high speed, "
                 "and change colour. Recurring since the 1930s and peaking 1981-1984 at up to 15-20 "
                 "sightings per week, this is a fixed-location recurring hotspot studied scientifically "
                 "with military support — not a one-off sighting.")
    },
    {
        "id": "NO-HESSDALEN-ams-station",
        "date": "1998-08-01",
        "desc": ("The Hessdalen Automatic Measurement Station (AMS, the 'Blue Box'), operated by Ostfold "
                 "University College, has continuously monitored the valley since 1998 with automated "
                 "cameras and a magnetometer, correlating light events with local geomagnetic activity. "
                 "The station repeatedly records luminous phenomena over the same valley, some coinciding "
                 "with magnetic-field disturbances — an instrument-based recurring hotspot at a geophysical "
                 "anomaly, the reference case for the recurring-hotspot pattern.")
    },
    {
        "id": "NO-HESSDALEN-eml-hypothesis",
        "date": "2007-01-01",
        "desc": ("Scientific field studies of the Hessdalen lights (Teodorani; Strand; Italian CNR "
                 "collaboration) report luminous objects of varying size that pulsate, change colour, and "
                 "occasionally split or move at high angular velocity, sometimes detected on radar without "
                 "a corresponding visual and vice versa. The phenomenon recurs at the same valley over "
                 "decades and remains only partly explained, making it a rigorously documented recurring "
                 "hotspot with colour-change and high-speed characteristics.")
    }
]


def main():
    recs = []
    for r in RECORDS:
        recs.append({
            "id": r["id"], "source": "NO-HESSDALEN", "date": r["date"],
            "description": r["desc"], "city": "Hessdalen valley",
            "district": "Sor-Trondelag", "country": "NO",
            "lat": HESSDALEN[0], "lng": HESSDALEN[1],
            "source_url": "https://www.hessdalen.org/",
        })
    doc = {
        "source": "Project Hessdalen (Norway) — Ostfold University College / Erling Strand",
        "licence": "public (hessdalen.org, published field studies)",
        "note": ("NGO/academic instrumented field station; canonical recurring hotspot at a geophysical "
                 "anomaly. Validates uap-et-hotspot-001. KNOWN documented facts; interpretation left open."),
        "count": len(recs), "reports": recs,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(doc, open(os.path.join(OUT_DIR, "hessdalen_uap.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"Built {len(recs)} NO-HESSDALEN records -> docs/hessdalen/hessdalen_uap.json")


if __name__ == "__main__":
    main()
