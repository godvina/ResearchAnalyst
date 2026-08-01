"""Merge cultural memory traits into scored findings as specific indicators.

Creates meaningful network edges between sites sharing specific cultural traits
like SPIRIT_DWELLING, WATER_SACRED, FORBIDDEN_ZONE — not just generic "sacred site".
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")
SCORED_PATH = os.path.join(DATA_DIR, "uvg-grid-scored-findings.json")
CULTURAL_PATH = os.path.join(DATA_DIR, "cultural-memory-results.json")

# Map trait IDs to human-readable indicator labels
TRAIT_LABELS = {
    "ENERGY_SENSATION": "Indigenous energy/vibration tradition at site",
    "HEALING_TRADITION": "Documented healing ceremony tradition",
    "FORBIDDEN_ZONE": "Designated forbidden/taboo zone for uninitiated",
    "CREATION_MYTH": "Site features in creation/emergence myth",
    "PILGRIMAGE": "Active pilgrimage destination (500+ years)",
    "ASTRONOMICAL_USE": "Indigenous sky observation/calendar site",
    "SPIRIT_DWELLING": "Believed inhabited by spirits/ancestors",
    "WATER_SACRED": "Sacredness connected to water (springs/rivers)",
    "BURIAL_GROUND": "Ancestral burial/funerary site",
    "POWER_TRANSFER": "Ritual power/knowledge transfer location",
}


def main():
    with open(SCORED_PATH) as f:
        scored = json.load(f)
    with open(CULTURAL_PATH) as f:
        cultural = json.load(f)

    # Build node map
    node_map = {}
    for entry in scored["results"]:
        node_map[entry["node_id"]] = entry

    added = 0
    for result in cultural.get("results", []):
        node_id = result["node_id"]
        culture = result.get("cultural")
        if not culture or not culture.get("traits"):
            continue

        # Get confirmed traits
        confirmed = [t for t in culture["traits"] if t.get("score") == "YES"]
        if not confirmed:
            continue

        # Build specific indicators from confirmed traits
        indicators = []
        for trait in confirmed:
            label = TRAIT_LABELS.get(trait["id"], trait["id"])
            evidence = trait.get("evidence", "")
            if evidence:
                # Truncate long evidence
                indicators.append(f"{label}: {evidence[:80]}")
            else:
                indicators.append(label)

        # Add/update cm-001 signature on this node
        if node_id not in node_map:
            continue

        entry = node_map[node_id]
        existing = None
        for m in entry["matches"]:
            if m["signature_id"] == "am-gge-cm-001":
                existing = m
                break

        if existing:
            # Replace generic indicators with specific ones
            existing["matched_indicators"] = indicators
            existing["confidence"] = "strong" if len(confirmed) >= 3 else "moderate"
            added += len(indicators)
        else:
            entry["matches"].append({
                "signature_id": "am-gge-cm-001",
                "confidence": "strong" if len(confirmed) >= 3 else "moderate",
                "matched_indicators": indicators,
                "evidence_excerpt": culture.get("primary_tradition", "")[:300],
            })
            entry["match_count"] = len(entry["matches"])
            added += len(indicators)

    # Update totals
    scored["total_with_matches"] = sum(
        1 for r in scored["results"] if len(r.get("matches", [])) > 0
    )

    with open(SCORED_PATH, "w") as f:
        json.dump(scored, f, indent=2)

    print(f"Cultural memory merge complete:")
    print(f"  {added} specific indicators added across nodes")
    print(f"  Nodes with matches: {scored['total_with_matches']}/{scored['total_scored']}")
    print(f"  Saved: {SCORED_PATH}")

    # Show which traits are shared across 2+ sites (network edges)
    print(f"\n  SHARED TRAITS (will create network edges):")
    trait_sites = {}
    for result in cultural.get("results", []):
        culture = result.get("cultural")
        if not culture:
            continue
        for t in culture.get("traits", []):
            if t.get("score") == "YES":
                if t["id"] not in trait_sites:
                    trait_sites[t["id"]] = []
                trait_sites[t["id"]].append(result["name"])

    for trait, sites in sorted(trait_sites.items(), key=lambda x: -len(x[1])):
        if len(sites) >= 2:
            print(f"    {trait}: {len(sites)} sites — {', '.join(sites)}")


if __name__ == "__main__":
    main()
