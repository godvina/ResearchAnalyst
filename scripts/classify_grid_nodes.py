"""Classify all 62 UVG grid nodes by what's known to be at each location.

For each of the 62 vertices of the Becker-Hagens grid, determine:
1. Is it on land or ocean?
2. What's the nearest known ancient/sacred site?
3. What's the investigation priority?
4. What should a field team look for?

This produces the investigation target database.
"""

import json
import math
import os

GRID_FILE = os.path.join(os.path.dirname(__file__), "..", "src", "data", "uvg-grid-62-points.json")

with open(GRID_FILE, "r") as f:
    grid_data = json.load(f)

vertices = grid_data["vertices"]

# Known sites near grid nodes (from literature + common knowledge)
# Format: {node_id: {site_name, distance_km, notes, investigated}}
KNOWN_SITES = {
    7: {"site": "Great Pyramid of Giza", "distance_km": 50, "notes": "Primary UVG node. One of the most studied ancient sites on Earth.", "status": "confirmed"},
    8: {"site": "Mohenjo-daro / Indus Valley", "distance_km": 200, "notes": "Major ancient civilization node. Harappan cities cluster near this point.", "status": "confirmed"},
    10: {"site": "Dragon's Triangle / Devil's Sea", "distance_km": 100, "notes": "Japanese maritime anomaly zone. Numerous ship/aircraft disappearances.", "status": "anomaly"},
    13: {"site": "Sedona Vortexes / Chaco Canyon", "distance_km": 300, "notes": "Multiple vortex sites in Arizona. Chaco Canyon Ancestral Puebloan complex.", "status": "confirmed"},
    14: {"site": "Bermuda Triangle", "distance_km": 150, "notes": "Infamous anomaly zone. Numerous disappearances.", "status": "anomaly"},
    40: {"site": "Uluru / Kata Tjuta", "distance_km": 200, "notes": "Sacred Aboriginal site. Massive sandstone monolith.", "status": "confirmed"},
    41: {"site": "Rotorua geothermal / Waipoua Forest", "distance_km": 300, "notes": "Major geothermal zone. Ancient Kauri forests.", "status": "probable"},
    43: {"site": "Easter Island (Rapa Nui)", "distance_km": 400, "notes": "Moai statues. One of the most remote inhabited sites.", "status": "confirmed"},
    44: {"site": "Nazca Lines / Paracas", "distance_km": 200, "notes": "Giant geoglyphs visible only from air. Pre-Inca.", "status": "confirmed"},
    56: {"site": "Newgrange / Stonehenge region", "distance_km": 400, "notes": "Dense concentration of Neolithic monuments (Newgrange, Avebury, Stonehenge).", "status": "confirmed"},
    2: {"site": "Arkaim (ancient observatory)", "distance_km": 500, "notes": "Bronze Age settlement in Urals with precise astronomical alignments.", "status": "probable"},
    3: {"site": "Lake Baikal sacred sites", "distance_km": 200, "notes": "World's deepest lake. Shamanic traditions. Anomalous methane emissions.", "status": "probable"},
    37: {"site": "Great Zimbabwe / Mapungubwe", "distance_km": 400, "notes": "Medieval stone city. Evidence of advanced engineering.", "status": "confirmed"},
    18: {"site": "Lake Victoria / East African Rift", "distance_km": 100, "notes": "Major geological feature. Cradle of humanity region.", "status": "geological"},
    21: {"site": "Gunung Padang (Indonesia)", "distance_km": 400, "notes": "Potentially oldest pyramid in world (>20,000 years claimed). Active excavation.", "status": "probable"},
    9: {"site": "Angkor Wat / Golden Triangle", "distance_km": 500, "notes": "Massive temple complex. Astronomical alignments documented.", "status": "confirmed"},
}

# Classify each node
def classify_nodes():
    classified = []
    
    for v in vertices:
        node_id = v["id"]
        lat = v["lat"]
        lng = v["lng"]
        
        # Skip poles
        if abs(lat) >= 89:
            classified.append({
                **v,
                "classification": "polar",
                "priority": "none",
                "known_site": None,
                "research_status": "not_applicable",
                "investigation_notes": "Polar vertex — geometric only, not investigable."
            })
            continue
        
        # Check if on land
        land = is_on_land(lat, lng)
        
        # Check known sites
        known = KNOWN_SITES.get(node_id)
        
        if known:
            priority = "confirmed" if known["status"] == "confirmed" else "high"
            classified.append({
                **v,
                "classification": "land" if land else "ocean",
                "continent": land,
                "priority": priority,
                "known_site": known["site"],
                "distance_to_site_km": known["distance_km"],
                "research_status": known["status"],
                "investigation_notes": known["notes"],
            })
        elif land:
            classified.append({
                **v,
                "classification": "land",
                "continent": land,
                "priority": "high",
                "known_site": None,
                "research_status": "unexplored",
                "investigation_notes": f"Grid node on land ({land}) — no documented site. HIGH PRIORITY for research: what's within 100km of this point?",
            })
        else:
            classified.append({
                **v,
                "classification": "ocean",
                "continent": None,
                "priority": "low",
                "known_site": None,
                "research_status": "ocean",
                "investigation_notes": "Ocean location. Check for: submerged plateaus, underwater anomalies, nearby island sites.",
            })
    
    return classified


def is_on_land(lat, lng):
    """Rough land check."""
    landmasses = [
        (-35, 37, -20, 55, "Africa"),
        (35, 72, -12, 45, "Europe"),
        (8, 78, 25, 180, "Asia"),
        (-48, -10, 112, 155, "Australia"),
        (-55, 12, -82, -34, "South America"),
        (7, 85, -170, -50, "North America"),
        (-50, -30, 165, 180, "New Zealand"),
    ]
    for min_lat, max_lat, min_lng, max_lng, name in landmasses:
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            return name
    return None


def main():
    classified = classify_nodes()
    
    # Stats
    confirmed = [n for n in classified if n.get("research_status") == "confirmed"]
    high_priority = [n for n in classified if n["priority"] == "high"]
    unexplored_land = [n for n in classified if n.get("research_status") == "unexplored"]
    ocean = [n for n in classified if n["classification"] == "ocean"]
    
    print(f"UVG Grid Node Classification:")
    print(f"  Total nodes: {len(classified)}")
    print(f"  Confirmed sites: {len(confirmed)}")
    print(f"  High priority (investigate): {len(high_priority)}")
    print(f"  Unexplored land nodes: {len(unexplored_land)}")
    print(f"  Ocean nodes: {len(ocean)}")
    
    print(f"\n{'='*60}")
    print("CONFIRMED SITES (grid nodes with known ancient/sacred sites):")
    print(f"{'='*60}")
    for n in confirmed:
        print(f"  Node {n['id']:>2} | {n['lat']:>7.2f}°, {n['lng']:>8.2f}° | {n['known_site']}")
        print(f"          {n['investigation_notes'][:80]}")
        print()
    
    print(f"\n{'='*60}")
    print("HIGH PRIORITY — UNEXPLORED LAND NODES:")
    print(f"{'='*60}")
    for n in unexplored_land:
        print(f"  Node {n['id']:>2} | {n['lat']:>7.2f}°, {n['lng']:>8.2f}° | {n['continent']}")
        print(f"          {n['investigation_notes'][:80]}")
        print()
    
    # Save classified data
    output = {
        "name": "UVG Grid — Classified Investigation Targets",
        "total_nodes": len(classified),
        "confirmed_sites": len(confirmed),
        "unexplored_land": len(unexplored_land),
        "high_priority": len(high_priority),
        "nodes": classified,
    }
    
    output_path = os.path.join(os.path.dirname(__file__), "..", "src", "data", "uvg-grid-classified.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
