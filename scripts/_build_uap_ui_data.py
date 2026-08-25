#!/usr/bin/env python3
"""Build the data file the UAP Command Center UI renders.

Combines:
  - scripts/ufo_full_corpus_scan.json      (signature fire counts, needles)
  - scripts/ufo_events_clustered.json       (mass sightings, hotspots, corroboration)
  - scripts/ufo_signal_reports.json         (the firing reports w/ geo)
  - src/data/ufo-uap-taxonomy.json          (typologies/methods/signatures)

Output: src/frontend/uap-command-data.js  (window.UAP_DATA = {...})
Produces the 4-tier findings board, map points (priority + hotspots), and needle drill-down
per docs/uap-analysis-and-investigator-design.md.
"""
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def L(p): return os.path.join(ROOT, p)

tax = json.load(open(L("src/data/ufo-uap-taxonomy.json"), encoding="utf-8"))
scan = json.load(open(L("scripts/ufo_full_corpus_scan.json"), encoding="utf-8")) if os.path.exists(L("scripts/ufo_full_corpus_scan.json")) else {}
events = json.load(open(L("scripts/ufo_events_clustered.json"), encoding="utf-8")) if os.path.exists(L("scripts/ufo_events_clustered.json")) else {}
signal = json.load(open(L("scripts/ufo_signal_reports.json"), encoding="utf-8")) if os.path.exists(L("scripts/ufo_signal_reports.json")) else {"reports": []}

# signature metadata (severity, typology, description, needles)
sigmeta = {}
for t in tax["typologies"]:
    for m in t["methods"]:
        for s in m["signatures"]:
            sigmeta[s["signature_id"]] = {
                "typology": t["typology_id"], "typology_name": t["name"],
                "method": m["method_id"], "severity": s["severity"],
                "description": s["description"], "needles": s["indicators"],
            }

# per-signature fire counts (from full corpus scan)
fire = {}
for row in scan.get("per_signature", []):
    fire[row["signature_id"]] = row.get("reports_fired", 0)

# Typology rollup for the board
typ_rollup = defaultdict(lambda: {"reports": 0, "signatures": [], "name": "", "critical": 0})
for sid, meta in sigmeta.items():
    tr = typ_rollup[meta["typology"]]
    tr["name"] = meta["typology_name"]
    tr["reports"] += fire.get(sid, 0)
    tr["signatures"].append({
        "id": sid, "severity": meta["severity"], "fired": fire.get(sid, 0),
        "description": meta["description"], "needles": meta["needles"],
    })
    if meta["severity"] == "critical":
        tr["critical"] += 1

# 4-tier findings board
mass = [e for e in events.get("events", []) if e.get("is_mass_sighting")]
corroborated = [e for e in events.get("events", []) if e.get("is_corroborated")]
tiers = {
    "tier1_bring_me_these": {
        "label": "Tier 1 — Highest priority (critical + corroborated)",
        "desc": "Cases firing critical signatures (impossible kinematics, radar-visual, trans-medium/USO, military).",
        "typologies": ["flight_kinematics", "sensor_em_signatures"],
        "top_signatures": sorted(
            [{"id": s, "fired": fire.get(s, 0), "sev": sigmeta[s]["severity"], "typ": sigmeta[s]["typology"], "desc": sigmeta[s]["description"]}
             for s in sigmeta if sigmeta[s]["severity"] == "critical"],
            key=lambda x: -x["fired"])[:8],
    },
    "tier2_waves_clusters": {
        "label": "Tier 2 — Waves & clusters (multi-witness / hotspots)",
        "desc": f"{len(mass)} mass sightings (5+ witnesses), {len(corroborated)} corroborated events.",
        "mass_sightings": mass[:15],
    },
    "tier3_cross_cutting": {
        "label": "Tier 3 — Cross-cutting anomalies (institutional/suppression)",
        "desc": "Cases bridging to conspiracy/crime domains (official involvement, suppression).",
        "typologies": ["institutional_response", "witness_reliability", "encounter_typology"],
    },
    "tier4_explained": {
        "label": "Tier 4 — Explained / low-signal (down-ranked)",
        "desc": "Prosaic/misID down-ranked via GEIPAN-calibrated negative signals.",
    },
}

# Map points: hotspots (from events geo_cell) + top-priority reports with geo
hotspots = []
for e in sorted(events.get("events", []), key=lambda x: -x.get("corroboration_score", 0))[:60]:
    gc = e.get("geo_cell", {})
    if gc.get("lat") is not None:
        hotspots.append({
            "lat": gc["lat"], "lng": gc["lng"], "witnesses": e.get("witness_count", 1),
            "shape": e.get("dominant_shape", ""), "year": e.get("year", ""),
            "score": e.get("corroboration_score", 0), "mass": e.get("is_mass_sighting", False),
            "city": (e.get("geographic_footprint", {}).get("cities", []) or [""])[0],
        })

# geo distribution from analysis (if present) for country coverage
countries = scan.get("countries") or {}

out = {
    "generated_from": "ufo_full_corpus_scan + ufo_events_clustered + taxonomy",
    "corpus_total": scan.get("total_reports_scanned", 60632),
    "reports_firing": scan.get("reports_with_any_signature", 0),
    "signatures_total": len(sigmeta),
    "typology_rollup": {k: v for k, v in typ_rollup.items()},
    "tiers": tiers,
    "map_points": hotspots,
    "per_signature_fire": fire,
    "sig_meta": sigmeta,
}

outpath = L("src/frontend/uap-command-data.js")
with open(outpath, "w", encoding="utf-8") as f:
    f.write("// UAP Command Center data — generated by scripts/_build_uap_ui_data.py\n")
    f.write("window.UAP_DATA = " + json.dumps(out, ensure_ascii=False) + ";\n")
print(f"wrote {outpath}")
print(f"  typologies: {len(typ_rollup)} | signatures: {len(sigmeta)} | map points: {len(hotspots)} | mass sightings: {len(mass)}")
