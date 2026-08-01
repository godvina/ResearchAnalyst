"""Batch research ALL 62 UVG grid nodes (land AND ocean).

For each node, uses a CREATIVE search strategy based on node type:
- Land nodes: ancient sites, ruins, megaliths, sacred sites, folklore
- Ocean nodes: submerged structures, sunken cities, bathymetric anomalies,
  ship disappearances, Atlantis/Lemuria myths, underwater volcanic features

Results are stored in S3 and compiled into a findings database.

Usage:
    python scripts/batch_research_grid_nodes.py [--limit 5] [--dry-run] [--ocean-only]
"""

import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

with open(os.path.join(DATA_DIR, "uvg-grid-investigation-database.json")) as f:
    grid_db = json.load(f)


def build_research_query(node):
    """Build a creative, node-type-specific research query."""
    lat, lng = node["lat"], node["lng"]
    continent = node.get("continent", "")
    classification = node["classification"]
    node_id = node["id"]

    if classification == "ocean":
        # Ocean nodes: search for underwater mysteries
        query = (
            f"submerged ancient ruins underwater structure bathymetric anomaly "
            f"near {lat:.1f} {lng:.1f} sunken city shipwreck disappearance"
        )
        context = (
            f"OCEAN GRID NODE INVESTIGATION: UVG Node {node_id} at {lat:.4f}°, {lng:.4f}° (open ocean). "
            f"Research question: What submerged structures, underwater anomalies, or maritime mysteries "
            f"exist near these coordinates? Look for: "
            f"1) Sonar/bathymetry showing geometric underwater formations "
            f"2) Myths of sunken civilizations (Atlantis, Lemuria, Mu) placed near here "
            f"3) Ship/aircraft disappearances or compass anomalies in this area "
            f"4) Submerged volcanic plateaus or seamounts that could have been above water in the past "
            f"5) Underwater archaeological discoveries (pottery, tools, structures) "
            f"6) Geomagnetic or gravitational anomalies detected by satellites "
            f"7) Ancient maps (Piri Reis, Oronteus Finaeus) showing land where there is now ocean"
        )
    elif classification == "unexplored_land":
        # Land nodes: search for ruins and sacred sites
        query = (
            f"ancient ruins sacred site megalith stone circle pyramid mound "
            f"near {lat:.1f} {lng:.1f} {continent} archaeological discovery"
        )
        context = (
            f"LAND GRID NODE INVESTIGATION: UVG Node {node_id} at {lat:.4f}°, {lng:.4f}° ({continent}). "
            f"Research question: What ancient sites, sacred places, or unexplained structures exist "
            f"within 200km of these coordinates? Look for: "
            f"1) Megaliths, stone circles, dolmens, pyramids, or mounds "
            f"2) Indigenous sacred sites or forbidden zones "
            f"3) Folklore about buried cities or underground chambers "
            f"4) Geomagnetic anomalies or unusual geological formations "
            f"5) LiDAR discoveries revealing hidden structures under vegetation "
            f"6) Archaeological surveys that found anomalies but weren't followed up "
            f"7) Ancient roads, walls, or foundations visible in satellite imagery"
        )
    elif classification == "confirmed_site":
        # Known sites: search for undiscovered connections
        site_name = node.get("nearest_known_site", "")
        query = (
            f"{site_name} alignment connection other ancient sites grid ley line "
            f"shared construction technique unexplained precision"
        )
        context = (
            f"CONFIRMED SITE ANALYSIS: {site_name} near UVG Node {node_id}. "
            f"Research question: What connects this site to OTHER ancient sites on the grid? "
            f"Look for: shared construction techniques, aligned orientations, common astronomical "
            f"alignments, same stone quarry sources, identical measurement units, "
            f"myths of builders coming from the same place."
        )
    else:
        # Near-site: search for additional undocumented sites in the area
        site_name = node.get("nearest_known_site", "")
        query = (
            f"undiscovered ruins near {site_name} {lat:.1f} {lng:.1f} "
            f"archaeological survey LiDAR satellite anomaly"
        )
        context = (
            f"ADJACENT SITE INVESTIGATION: Near {site_name}, UVG Node {node_id}. "
            f"Research question: Are there ADDITIONAL undocumented sites near the known one? "
            f"Look for sites that haven't been excavated, LiDAR reveals, or local legends "
            f"about nearby ruins that academics haven't investigated."
        )

    return query[:400], context  # Cap query length for Brave API


def research_node(node):
    """Call the research/execute API to investigate a grid node."""
    query, context = build_research_query(node)
    
    url = f"{API_URL}/pattern-library/research/execute"
    body = json.dumps({"query": query, "context": context}).encode("utf-8")
    
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("brief", {})
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "detail": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5, help="Max nodes to research")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ocean-only", action="store_true")
    parser.add_argument("--land-only", action="store_true")
    parser.add_argument("--all", action="store_true", help="Research all 62 nodes")
    args = parser.parse_args()
    
    nodes = grid_db["nodes"]
    
    if args.ocean_only:
        targets = [n for n in nodes if n["classification"] == "ocean"]
    elif args.land_only:
        targets = [n for n in nodes if n["classification"] in ("unexplored_land", "confirmed_site", "near_site")]
    elif args.all:
        targets = nodes
        args.limit = len(nodes)
    else:
        # Default: unexplored land first, then ocean
        targets = sorted(nodes, key=lambda n: 0 if n["classification"] == "unexplored_land" else 1 if n["classification"] == "ocean" else 2)
    
    limit = min(args.limit, len(targets))
    
    print(f"UVG Grid Node Research — ALL NODES")
    print(f"  Total targets: {len(targets)}")
    print(f"  Will research: {limit}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()
    
    if args.dry_run:
        for n in targets[:limit]:
            q, _ = build_research_query(n)
            print(f"  Node {n['id']:>2} | {n['classification']:<18} | {n['lat']:>7.2f}°, {n['lng']:>8.2f}° | Query: {q[:60]}...")
        return
    
    results = []
    for i, node in enumerate(targets[:limit]):
        print(f"[{i+1}/{limit}] Node {node['id']} ({node['classification']}) — {node['lat']:.2f}°, {node['lng']:.2f}°")
        
        t0 = time.time()
        brief = research_node(node)
        elapsed = time.time() - t0
        
        if "error" in brief:
            print(f"  ❌ {brief['error'][:80]}")
        else:
            print(f"  ✅ {brief.get('codename', '?')} — {brief.get('investigation_status', '?')}")
            gun = brief.get("smoking_gun", "")
            if gun and "No definitive" not in gun:
                print(f"     💡 {gun[:100]}")
        
        results.append({
            "node_id": node["id"],
            "lat": node["lat"],
            "lng": node["lng"],
            "classification": node["classification"],
            "continent": node.get("continent"),
            "brief": brief,
            "researched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        
        if i < limit - 1:
            time.sleep(3)  # Rate limit
    
    # Save
    output_path = os.path.join(DATA_DIR, "uvg-grid-research-all-nodes.json")
    output = {
        "name": "UVG Grid Research — All Nodes",
        "total_researched": len(results),
        "results": results,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    successful = [r for r in results if "error" not in r["brief"]]
    print(f"\nDone! {len(successful)}/{len(results)} successful. Saved to {output_path}")


if __name__ == "__main__":
    main()
