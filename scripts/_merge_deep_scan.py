"""Merge deep-scan results into the scored-findings file.

Reads uvg-grid-deep-scan-results.json and maps each signature match
into the taxonomy format used by uvg-grid-scored-findings.json, then
updates nodes 1, 4, 12, 14, 17, 25, 35, 47 with new match data.
"""

import json
import os
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "src", "data")

DEEP_SCAN_PATH = os.path.join(DATA_DIR, "uvg-grid-deep-scan-results.json")
SCORED_PATH = os.path.join(DATA_DIR, "uvg-grid-scored-findings.json")

# Mapping: deep-scan signature ID → taxonomy signature_id
SIGNATURE_MAP = {
    "MEGALITHIC": "am-gge-san-001",
    "ASTRONOMICAL": "am-gge-cnp-002",
    "ALIGNMENT": "am-gge-lla-001",
    "SHARED_TECHNIQUE": "am-gge-cnp-001",
    "INDIGENOUS_SACRED": "am-gge-cm-001",
    "GEOMETRIC": "am-gge-ga-002",
    "CLUSTER": "am-gge-cnp-004",
    "UNEXPLAINED": None,  # Keep as general note, no taxonomy ID
}

# Which scores qualify as a match for each signature type
MATCH_CRITERIA = {
    "MEGALITHIC": ["MATCH"],
    "ASTRONOMICAL": ["MATCH"],
    "ALIGNMENT": ["MATCH", "POSSIBLE"],
    "SHARED_TECHNIQUE": ["MATCH"],
    "INDIGENOUS_SACRED": ["MATCH", "POSSIBLE"],  # POSSIBLE only if moderate+ confidence
    "GEOMETRIC": ["MATCH"],
    "CLUSTER": ["MATCH"],
    "UNEXPLAINED": ["MATCH"],
}

# Confidence levels that qualify as "moderate+" for INDIGENOUS_SACRED
MODERATE_PLUS = {"moderate", "strong", "very_strong"}


def qualifies(sig: dict) -> bool:
    """Check if a deep-scan signature qualifies for mapping."""
    sig_id = sig["id"]
    score = sig["score"]
    confidence = sig.get("confidence", "weak")

    valid_scores = MATCH_CRITERIA.get(sig_id, ["MATCH"])
    if score not in valid_scores:
        return False

    # INDIGENOUS_SACRED with POSSIBLE requires moderate+ confidence
    if sig_id == "INDIGENOUS_SACRED" and score == "POSSIBLE":
        if confidence not in MODERATE_PLUS:
            return False

    return True


def map_signature(sig: dict) -> dict | None:
    """Convert a deep-scan signature to the scored-findings match format."""
    sig_id = sig["id"]
    taxonomy_id = SIGNATURE_MAP.get(sig_id)

    if taxonomy_id is None:
        # UNEXPLAINED — no taxonomy mapping, skip
        return None

    # Build matched_indicators from the evidence
    evidence = sig.get("evidence", "")
    indicators = []

    # Extract key indicators based on signature type
    if sig_id == "MEGALITHIC":
        indicators.append("Megalithic construction confirmed")
        if "tons" in evidence.lower():
            indicators.append("Multi-ton stone blocks documented")
    elif sig_id == "ASTRONOMICAL":
        indicators.append("Astronomical alignment verified")
        if "equinox" in evidence.lower():
            indicators.append("Equinox/solstice alignment")
        if "sub-1" in evidence.lower() or "0.1" in evidence or "0.5" in evidence:
            indicators.append("Sub-degree precision")
    elif sig_id == "ALIGNMENT":
        indicators.append("Great circle alignment documented")
        if "UVG" in evidence:
            indicators.append("UVG grid intersection")
    elif sig_id == "SHARED_TECHNIQUE":
        indicators.append("Shared construction technique identified")
        if "km" in evidence.lower():
            indicators.append("Cross-continental similarity")
    elif sig_id == "INDIGENOUS_SACRED":
        indicators.append("Indigenous sacred tradition")
        if "500" in evidence or "pre-" in evidence.lower():
            indicators.append("Pre-contact tradition documented")
    elif sig_id == "GEOMETRIC":
        indicators.append("Geometric precision documented")
    elif sig_id == "CLUSTER":
        indicators.append("Site cluster identified")

    return {
        "signature_id": taxonomy_id,
        "confidence": sig["confidence"],
        "matched_indicators": indicators,
        "evidence_excerpt": evidence[:400],
    }


def merge():
    """Main merge logic."""
    # Load files
    with open(DEEP_SCAN_PATH, "r", encoding="utf-8") as f:
        deep_scan = json.load(f)

    with open(SCORED_PATH, "r", encoding="utf-8") as f:
        scored = json.load(f)

    # Index scored findings by node_id for fast lookup
    node_index = {}
    for i, result in enumerate(scored["results"]):
        node_index[result["node_id"]] = i

    # Process each deep-scan result
    updated_count = 0
    for ds_result in deep_scan["results"]:
        node_id = ds_result["node_id"]
        if node_id not in node_index:
            print(f"  SKIP: Node {node_id} not in scored findings")
            continue

        idx = node_index[node_id]
        existing = scored["results"][idx]

        # Collect new matches from signatures
        new_matches = []
        for sig in ds_result["deep_scan"]["signatures"]:
            if qualifies(sig):
                mapped = map_signature(sig)
                if mapped:
                    new_matches.append(mapped)

        if not new_matches:
            print(f"  Node {node_id} ({ds_result['site_name']}): No qualifying matches")
            continue

        # Update the scored finding
        existing["matches"] = new_matches
        existing["match_count"] = len(new_matches)
        existing["strongest_match"] = new_matches[0]["signature_id"] if new_matches else None

        updated_count += 1
        print(f"  Node {node_id} ({ds_result['site_name']}): {len(new_matches)} matches added")
        for m in new_matches:
            print(f"    → {m['signature_id']} ({m['confidence']})")

    # Update total counts
    total_with_matches = sum(1 for r in scored["results"] if r["match_count"] > 0)
    scored["total_with_matches"] = total_with_matches

    # Save
    with open(SCORED_PATH, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Updated {updated_count} nodes")
    print(f"  Total nodes with matches: {total_with_matches}/{scored['total_scored']}")
    print(f"  Saved to: {SCORED_PATH}")


if __name__ == "__main__":
    print("Merging deep-scan results into scored findings...")
    print(f"  Deep scan: {DEEP_SCAN_PATH}")
    print(f"  Scored findings: {SCORED_PATH}")
    print()
    merge()
