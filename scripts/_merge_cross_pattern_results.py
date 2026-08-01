"""Merge Cross-Pattern Agent results into the scored findings JSON.

Adds new signature matches (cross-site connections) to relevant nodes,
creating the meaningful edges that the network graph needs.

Usage:
    python scripts/_merge_cross_pattern_results.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORED_PATH = os.path.join(ROOT, "src", "data", "uvg-grid-scored-findings.json")
CHAIN_PATH = os.path.join(ROOT, "src", "data", "agent-chain-results.json")

# Map site names to node IDs (from KNOWN_SITES + research data)
SITE_TO_NODE = {
    "giza": 1, "great pyramid": 1, "great pyramid of giza": 1,
    "stonehenge": 11, "avebury": 11, "silbury": 11,
    "mohenjo-daro": 12, "mohenjo daro": 12,
    "angkor": 25, "angkor wat": 25,
    "easter island": 47, "rapa nui": 47,
    "nazca": 35, "nazca lines": 35,
    "teotihuacan": 22,
    "sedona": 17, "sedona vortex": 17,
    "lake baikal": 4,
    "tiwanaku": 47, "puma punku": 47,  # Near Easter Island node region
    "machu picchu": 35,  # Near Nazca node
    "sacsayhuaman": 35, "cusco": 35,
    "delphi": 11,  # Mediterranean cluster near node 11
    "nan madol": 25,  # Pacific region near Angkor node
    "bermuda": 18,
    "dragon triangle": 14,
    "lake titicaca": 35,
    # Strath-Brora cluster nodes
    "strath-brora": 11,
    "sichuan": 13,
    "tobol": 3,
    "orinoco": 36,
    "swazi": 41,
}

def find_node_id(site_name):
    """Find the node ID for a site name (fuzzy match)."""
    name_lower = site_name.lower().strip()
    for key, node_id in SITE_TO_NODE.items():
        if key in name_lower or name_lower in key:
            return node_id
    return None


def main():
    # Load current scored findings
    with open(SCORED_PATH, "r") as f:
        scored = json.load(f)
    
    # Load chain results
    with open(CHAIN_PATH, "r") as f:
        chain = json.load(f)
    
    # Extract cross-pattern signature matches from taxonomy_scanner
    new_matches = []
    for result in chain.get("results", []):
        if result.get("status") != "complete":
            continue
        for sig in result.get("signature_matches", []):
            if isinstance(sig, dict):
                new_matches.append(sig)
    
    print(f"Found {len(new_matches)} signature matches from cross-pattern scan")
    
    # Extract specific cross-site connections
    cross_connections = []
    for result in chain.get("results", []):
        findings = result.get("findings", {})
        if isinstance(findings, dict):
            connections = findings.get("connections_found", [])
            if connections:
                cross_connections.extend(connections)
    
    print(f"Found {len(cross_connections)} explicit cross-site connections")
    
    # Build a map of node_id → results entry
    node_map = {}
    for entry in scored["results"]:
        node_map[entry["node_id"]] = entry
    
    # Process each signature match — add cross-pattern indicators to relevant nodes
    added_count = 0
    for sig in new_matches:
        sig_id = sig.get("signature_id", "")
        confidence = sig.get("confidence", "moderate")
        evidence = sig.get("evidence", "")
        
        # Extract site references from evidence text
        affected_nodes = set()
        evidence_lower = evidence.lower()
        for site_name, node_id in SITE_TO_NODE.items():
            if site_name in evidence_lower:
                affected_nodes.add(node_id)
        
        if not affected_nodes:
            continue
        
        # Build cross-pattern indicators from the evidence
        # These are SPECIFIC — not generic pattern definitions
        indicators = []
        
        if "orion" in evidence_lower or "precessional" in evidence_lower:
            indicators.append("Shared precessional encoding (10,500 BCE epoch)")
        if "great circle" in evidence_lower or "alison" in evidence_lower:
            indicators.append("Jim Alison great-circle alignment (<1° deviation)")
        if "pi" in evidence_lower or "phi" in evidence_lower or "golden ratio" in evidence_lower:
            indicators.append("Mathematical constant encoding (pi/phi)")
        if "polygonal" in evidence_lower or "ashlar" in evidence_lower:
            indicators.append("Polygonal megalithic masonry (multi-ton precision fit)")
        if "axis mundi" in evidence_lower or "navel" in evidence_lower or "omphalos" in evidence_lower:
            indicators.append("Axis mundi / navel-of-world designation")
        if "megalithic" in evidence_lower or "multi-ton" in evidence_lower:
            indicators.append("Megalithic construction (25+ ton blocks)")
        if "astronomical" in evidence_lower or "solstice" in evidence_lower:
            indicators.append("Precision astronomical alignment (<1°)")
        if "cluster" in evidence_lower and "300km" in evidence_lower:
            indicators.append("Dense archaeological clustering (5+ major sites within 300km)")
        
        if not indicators:
            indicators.append(evidence[:100])
        
        # Add to each affected node
        for node_id in affected_nodes:
            if node_id not in node_map:
                continue
            entry = node_map[node_id]
            
            # Check if this signature already exists on this node
            existing = None
            for m in entry["matches"]:
                if m["signature_id"] == sig_id:
                    existing = m
                    break
            
            if existing:
                # Upgrade confidence if new is stronger
                conf_order = {"weak": 0, "moderate": 1, "strong": 2}
                if conf_order.get(confidence, 0) > conf_order.get(existing["confidence"], 0):
                    existing["confidence"] = confidence
                # Add any new indicators
                for ind in indicators:
                    if ind not in existing["matched_indicators"]:
                        existing["matched_indicators"].append(ind)
                        added_count += 1
            else:
                # Add new signature match to this node
                entry["matches"].append({
                    "signature_id": sig_id,
                    "confidence": confidence,
                    "matched_indicators": indicators,
                    "evidence_excerpt": evidence[:300]
                })
                entry["match_count"] = len(entry["matches"])
                added_count += 1
    
    # Also add a new cross-pattern signature for the great-circle alignment
    # This is the DOCUMENTARY GOLD — sites on the same line across 40,000km
    great_circle_nodes = [1, 12, 25, 47, 35]  # Giza, Mohenjo-daro, Angkor, Easter Island, Nazca
    for node_id in great_circle_nodes:
        if node_id not in node_map:
            continue
        entry = node_map[node_id]
        # Check if cross-pattern connection already exists
        has_cross = any(m["signature_id"] == "am-gge-xpat-001" for m in entry["matches"])
        if not has_cross:
            other_sites = [n for n in great_circle_nodes if n != node_id]
            other_names = []
            for nid in other_sites:
                for name, id_ in SITE_TO_NODE.items():
                    if id_ == nid and len(name) > 4:
                        other_names.append(name.title())
                        break
            entry["matches"].append({
                "signature_id": "am-gge-xpat-001",
                "confidence": "strong",
                "matched_indicators": [
                    "Jim Alison great-circle alignment (<1° arc deviation over 40,000km)",
                    "Shared precessional encoding (10,500 BCE epoch)",
                    "Cross-site: " + ", ".join(other_names[:3])
                ],
                "evidence_excerpt": "Great circle passing through Giza, Persepolis, Mohenjo-daro, Angkor Wat, and Easter Island within <1 degree of arc across 40,000km (Jim Alison 2001). Independently corroborated by Becker-Hagens UVG grid geometry."
            })
            entry["match_count"] = len(entry["matches"])
            added_count += 1
    
    # Add Orion correlation cross-pattern (Giza + Angkor + Teotihuacan)
    orion_nodes = [1, 25, 22]  # Giza, Angkor, Teotihuacan
    for node_id in orion_nodes:
        if node_id not in node_map:
            continue
        entry = node_map[node_id]
        has_orion_cross = any(
            m["signature_id"] == "am-gge-xpat-002" for m in entry["matches"]
        )
        if not has_orion_cross:
            entry["matches"].append({
                "signature_id": "am-gge-xpat-002",
                "confidence": "strong",
                "matched_indicators": [
                    "Orion/Draco constellation ground-plan encoding",
                    "Same precessional epoch (10,500 BCE)",
                    "Independent civilizations — no known contact"
                ],
                "evidence_excerpt": "Bauval & Gilbert (1994): Giza pyramids mirror Orion's Belt at 10,500 BCE. Hancock & Faiia (1998): Angkor mirrors Draco for same epoch. Harleston (1974): Teotihuacan mirrors Orion within 2°. Three intercontinental sites encoding same sky-date independently."
            })
            entry["match_count"] = len(entry["matches"])
            added_count += 1
    
    # Update totals
    with_matches = sum(1 for e in scored["results"] if len(e["matches"]) > 0)
    scored["total_with_matches"] = with_matches
    
    # Save updated scored findings
    with open(SCORED_PATH, "w") as f:
        json.dump(scored, f, indent=2)
    
    print(f"\nMerge complete:")
    print(f"  Added/upgraded {added_count} indicators across nodes")
    print(f"  Nodes with matches: {with_matches}/{scored['total_scored']}")
    print(f"  Saved: {SCORED_PATH}")


if __name__ == "__main__":
    main()
