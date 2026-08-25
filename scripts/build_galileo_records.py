"""Build UAP records from the Galileo Project all-sky infrared camera array commissioning
study (Dominé, Loeb et al.) — an NGO scientific INSTRUMENT source, not eyewitness reports.

Honest framing (critical): the Galileo Project explicitly does NOT claim these detections
are anomalous. Their outlier search flags trajectories that are 'likely mundane but cannot
be elucidated' without distance/kinematics or extra sensor modalities. We record the
KNOWN measured facts (instrument, counts, methodology) and label the interpretation as the
authors do — ambiguous, not proof of anything. Same discipline as the Ukraine Kyiv set.

Source (public): arXiv:2411.07956 (v2) = Sensors 2025, 25(3), 783 (MDPI).
  'Commissioning An All-Sky Infrared Camera Array for Detection Of Airborne Objects',
  Galileo Project, Harvard University.

Output: docs/galileo/galileo_uap.json  (source=GALILEO, country=US, observatory coords)
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "galileo")

# Galileo Project observatory (Harvard College Observatory / Harvard property, Massachusetts).
OBS = (42.3770, -71.1167)

RECORDS = [
    {
        "id": "GALILEO-commissioning-2024",
        "date": "2024-11-12",
        "desc": ("Galileo Project (Harvard) all-sky infrared camera array commissioning study. Eight "
                 "uncooled long-wave infrared FLIR Boson 640 cameras continuously monitor the whole sky. "
                 "Calibrated using aircraft positions from ADS-B transponder data. Over five months of "
                 "field operation the system reconstructed approximately 500,000 trajectories of aerial "
                 "objects. This is a rigorous long-term instrument census of ALL aerial phenomena, natural "
                 "and human-made — a multi-band, ground-based scientific observatory, not eyewitness reports.")
    },
    {
        "id": "GALILEO-outlier-search-2024",
        "date": "2024-11-12",
        "desc": ("Galileo Project outlier analysis: a toy search focused on large sinuosity of the 2-D "
                 "reconstructed trajectories flagged about 16 percent of trajectories as outliers. After "
                 "manual review, 144 trajectories remained ambiguous — the authors state these are LIKELY "
                 "MUNDANE objects that simply cannot be elucidated at this stage without distance and "
                 "kinematics estimation or additional sensor modalities. Combined with systematic "
                 "uncertainties this yields an upper limit of 18,271 ambiguous outliers over the five-month "
                 "interval at 95 percent confidence. The project explicitly does NOT claim these are anomalous.")
    },
    {
        "id": "GALILEO-infrared-methodology",
        "date": "2024-11-12",
        "desc": ("Instrument methodology: infrared-only detection of airborne objects, tracked across an "
                 "eight-camera all-sky array with ADS-B extrinsic calibration, reporting acceptance rates "
                 "and detection efficiencies by weather, range and aircraft size. Objects detected in the "
                 "long-wave infrared, some without a correlated ADS-B transponder return, are logged and "
                 "measured for trajectory sinuosity and kinematics — a repeatable, sensor-based census "
                 "designed to separate mundane traffic from genuine unknowns using data, not testimony.")
    }
]


def main():
    recs = []
    for r in RECORDS:
        recs.append({
            "id": r["id"], "source": "GALILEO", "date": r["date"],
            "description": r["desc"], "city": "Harvard Observatory (Massachusetts)",
            "district": "", "country": "US",
            "lat": OBS[0], "lng": OBS[1],
            "arxiv": "2411.07956",
        })
    doc = {
        "source": "Galileo Project (Harvard) all-sky IR camera array — Domine, Loeb et al.",
        "licence": "Public preprint arXiv:2411.07956 = Sensors 2025 25(3) 783 (open access)",
        "note": ("NGO scientific INSTRUMENT source. ~500,000 trajectories in 5 months; 144 ambiguous "
                 "outliers after review that the authors call LIKELY MUNDANE (not anomalous). KNOWN "
                 "instrument facts recorded; interpretation kept as the authors framed it."),
        "count": len(recs), "reports": recs,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(doc, open(os.path.join(OUT_DIR, "galileo_uap.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"Built {len(recs)} GALILEO records -> docs/galileo/galileo_uap.json")
    for r in recs:
        print(f"  {r['id']}")


if __name__ == "__main__":
    main()
