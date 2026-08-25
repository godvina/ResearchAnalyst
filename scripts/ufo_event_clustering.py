#!/usr/bin/env python3
"""UFO/UAP Event Clustering — collapse same-event reports into corroborated event nodes.

Problem: one real aerial event generates many independent reports. Scored
individually, each report looks isolated, so the multi-witness / mass-sighting
signatures (uap-et-mass-001, uap-wr-cred-002) can never fire, and the graph fills
with near-duplicate report spam instead of high-confidence EVENTS.

This groups reports that plausibly describe the SAME event by:
  - geographic proximity  (rounded lat/lng grid cell)
  - temporal proximity     (same date, within a day window)
  - (soft) shape agreement

Then it emits one corroborated EVENT per cluster with:
  - witness_count            (independent reports)
  - is_mass_sighting         (>= MASS_THRESHOLD witnesses)
  - geographic_footprint     (distinct cities/states)
  - corroboration_score      (drives ranking; multi-witness > single)

Operates on the FREE Tier-1 filtered output (no cost). This is analysis over the
already-ingested corpus, NOT a new data loader.

Input:  scripts/ufo_tier1_filtered.json  (run ufo_tiered_scan.py --tier 1 first)
Output: scripts/ufo_events_clustered.json
        src/data/conspiracy-seed/ufos_uaps/events_clustered.json  (provenance copy)

Usage:
    python scripts/ufo_event_clustering.py
    python scripts/ufo_event_clustering.py --grid 0.5 --day-window 1 --mass 5
"""
import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIER1 = os.path.join(PROJECT_ROOT, "scripts", "ufo_tier1_filtered.json")
OUT = os.path.join(PROJECT_ROOT, "scripts", "ufo_events_clustered.json")
OUT_SEED = os.path.join(PROJECT_ROOT, "src", "data", "conspiracy-seed", "ufos_uaps", "events_clustered.json")

# A "mass sighting" needs at least this many independent reports.
MASS_THRESHOLD = 5


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def cluster_key(report, grid, day_window):
    """Build a clustering key: (geo-cell, date-bucket). None if not clusterable."""
    lat = _to_float(report.get("lat"))
    lng = _to_float(report.get("lng"))
    year = report.get("year", "")
    if lat is None or lng is None or not year:
        return None
    # Geo cell: round to `grid` degrees
    gcell = (round(lat / grid) * grid, round(lng / grid) * grid)
    # Temporal bucket: we only have year in tier1 output; use year as the coarse
    # bucket (day_window is retained for when day-level data is available).
    return (gcell, str(year))


def build_events(reports, grid, day_window, mass):
    clusters = defaultdict(list)
    unclustered = 0
    for r in reports:
        k = cluster_key(r, grid, day_window)
        if k is None:
            unclustered += 1
            continue
        clusters[k].append(r)

    events = []
    for (gcell, year), members in clusters.items():
        witness_count = len(members)
        cities = sorted({m.get("city", "") for m in members if m.get("city")})
        states = sorted({m.get("state", "") for m in members if m.get("state")})
        shapes = defaultdict(int)
        for m in members:
            shapes[m.get("shape", "unknown")] += 1
        dominant_shape = max(shapes.items(), key=lambda kv: kv[1])[0] if shapes else "unknown"
        # Corroboration score: log-ish boost for more independent witnesses,
        # plus geographic spread (multi-city = wider footprint = stronger event).
        corroboration = witness_count + (len(cities) - 1) * 0.5 + (len(states) - 1) * 1.0
        best = max(members, key=lambda m: m.get("priority_score", 0))
        events.append({
            "event_id": f"uapev-{gcell[0]}_{gcell[1]}_{year}".replace(".", "p").replace("-", "m"),
            "geo_cell": {"lat": gcell[0], "lng": gcell[1]},
            "year": year,
            "witness_count": witness_count,
            "is_mass_sighting": witness_count >= mass,
            "is_corroborated": witness_count >= 2,
            "geographic_footprint": {"cities": cities[:20], "n_cities": len(cities),
                                     "states": states, "n_states": len(states)},
            "dominant_shape": dominant_shape,
            "shape_distribution": dict(shapes),
            "corroboration_score": round(corroboration, 2),
            "representative_report": best.get("description", "")[:300],
            "member_report_count": witness_count,
        })

    events.sort(key=lambda e: e["corroboration_score"], reverse=True)
    return events, unclustered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", type=float, default=0.5, help="Geo grid size in degrees (default 0.5 ~ 55km)")
    ap.add_argument("--day-window", type=int, default=1, help="Temporal window in days (reserved; tier1 has year only)")
    ap.add_argument("--mass", type=int, default=MASS_THRESHOLD, help="Min witnesses for mass sighting")
    args = ap.parse_args()

    if not os.path.exists(TIER1):
        raise SystemExit("Run `python scripts/ufo_tiered_scan.py --tier 1` first.")
    reports = json.load(open(TIER1, encoding="utf-8"))["reports"]

    events, unclustered = build_events(reports, args.grid, args.day_window, args.mass)

    mass_events = [e for e in events if e["is_mass_sighting"]]
    corroborated = [e for e in events if e["is_corroborated"]]
    singletons = [e for e in events if e["witness_count"] == 1]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "scripts/ufo_tier1_filtered.json",
        "params": {"grid_degrees": args.grid, "day_window": args.day_window, "mass_threshold": args.mass},
        "input_reports": len(reports),
        "unclustered_no_geo_or_date": unclustered,
        "total_events": len(events),
        "corroborated_events_2plus": len(corroborated),
        "mass_sightings": len(mass_events),
        "singleton_events": len(singletons),
        "reduction": f"{len(reports)} reports -> {len(events)} events "
                     f"({round((1-len(events)/max(1,len(reports)))*100,1)}% collapse)",
        "top_mass_sightings": mass_events[:15],
        "events": events,
    }

    json.dump(summary, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    # Provenance copy alongside the seed
    os.makedirs(os.path.dirname(OUT_SEED), exist_ok=True)
    json.dump(summary, open(OUT_SEED, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print("=" * 68)
    print("UFO EVENT CLUSTERING")
    print("=" * 68)
    print(f"  Input reports:        {len(reports)}")
    print(f"  Unclustered (no geo): {unclustered}")
    print(f"  Total events:         {len(events)}  ({summary['reduction']})")
    print(f"  Corroborated (2+):    {len(corroborated)}")
    print(f"  Mass sightings ({args.mass}+): {len(mass_events)}")
    print(f"  Singletons:           {len(singletons)}")
    print(f"\n  Top corroborated events:")
    for e in events[:10]:
        loc = (e['geographic_footprint']['cities'][:1] or ['?'])[0]
        print(f"    score {e['corroboration_score']:>5} | {e['witness_count']:>3} witnesses | "
              f"{e['year']} | {e['dominant_shape']:>9} | {loc} ({e['geographic_footprint']['n_states']} states)")
    print(f"\n  Output: {os.path.relpath(OUT, PROJECT_ROOT)}")
    print(f"          {os.path.relpath(OUT_SEED, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
