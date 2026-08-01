"""Retry cultural memory research on failed nodes with improved parser."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

# Import research_node from the main script
exec(open("scripts/_research_cultural_memory.py").read().split("def main")[0])

FAILED_NODES = [
    {"id": 17, "name": "Sedona Vortexes", "lat": 31.72, "lng": -112.8},
    {"id": 21, "name": "Nile Savanna (Africa)", "lat": 10.81, "lng": 31.2},
    {"id": 27, "name": "Gulf Savanna (Australia)", "lat": -10.81, "lng": 139.2},
    {"id": 40, "name": "Congo Equator", "lat": 0.0, "lng": 13.2},
]

DATA_DIR = os.path.join("src", "data")

def main():
    print("Retrying 4 failed cultural memory nodes (with improved parser)...")
    results = []
    for node in FAILED_NODES:
        print(f"  [{node['id']}] {node['name']}...")
        result = research_node(node)
        if result:
            traits_yes = [t for t in result.get("traits", []) if t.get("score") == "YES"]
            traits_pos = [t for t in result.get("traits", []) if t.get("score") == "POSSIBLE"]
            print(f"    OK: {len(traits_yes)} confirmed, {len(traits_pos)} possible")
            if traits_yes:
                print(f"    Confirmed: {', '.join(t['id'] for t in traits_yes)}")
            results.append({"node_id": node["id"], "name": node["name"], "cultural": result})
        else:
            print(f"    FAILED again")
            results.append({"node_id": node["id"], "name": node["name"], "cultural": None})
        time.sleep(2)

    # Merge into existing results
    existing_path = os.path.join(DATA_DIR, "cultural-memory-results.json")
    with open(existing_path) as f:
        existing = json.load(f)

    merged = 0
    for new_r in results:
        if new_r["cultural"] is None:
            continue
        found = False
        for i, old_r in enumerate(existing["results"]):
            if old_r["node_id"] == new_r["node_id"]:
                existing["results"][i] = new_r
                found = True
                break
        if not found:
            existing["results"].append(new_r)
        merged += 1

    with open(existing_path, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"\nMerged {merged} results. Saved: {existing_path}")


if __name__ == "__main__":
    main()
