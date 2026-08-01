"""Cultural Memory Deep-Dive — researches WHAT specifically indigenous traditions say about each sacred site.

Goal: Replace generic "Indigenous oral tradition" indicators with SPECIFIC shared traits:
- "Describes buzzing/vibrating energy"
- "Healing ceremony tradition"
- "Forbidden zone / taboo"
- "Creation/emergence myth"
- "Pilgrimage destination"
- "Astronomical observation site"

This creates meaningful network graph connections between sites sharing specific cultural traits.
"""
import boto3
import json
import os
import time
from botocore.config import Config

REGION = "us-east-1"
MODEL = "us.anthropic.claude-sonnet-4-6"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

bedrock = boto3.client("bedrock-runtime", region_name=REGION, 
                       config=Config(read_timeout=120, retries={"max_attempts": 2}))

# Nodes that matched cm-001 (Indigenous Sacred Sites)
SACRED_NODES = [
    {"id": 2, "name": "Pripyat Crossroads (Belarus)", "lat": 52.62, "lng": 31.2},
    {"id": 8, "name": "Buffalo Lake (Alberta)", "lat": 52.62, "lng": -112.8},
    {"id": 9, "name": "Subarctic Quebec", "lat": 58.28, "lng": -76.8},
    {"id": 13, "name": "Sichuan Highland (China)", "lat": 31.72, "lng": 103.2},
    {"id": 17, "name": "Sedona Vortexes", "lat": 31.72, "lng": -112.8},
    {"id": 18, "name": "Abaco Shelf (Bahamas)", "lat": 26.57, "lng": -76.8},
    {"id": 21, "name": "Nile Savanna (Africa)", "lat": 10.81, "lng": 31.2},
    {"id": 22, "name": "Madagascar Channel", "lat": 0.0, "lng": 49.2},
    {"id": 27, "name": "Gulf Savanna (Australia)", "lat": -10.81, "lng": 139.2},
    {"id": 36, "name": "Orinoco Zero (Amazon)", "lat": 0.0, "lng": -58.8},
    {"id": 37, "name": "Sertao (Brazil)", "lat": 10.81, "lng": -40.8},
    {"id": 40, "name": "Congo Equator", "lat": 0.0, "lng": 13.2},
    {"id": 41, "name": "Swazi Crossroads", "lat": -26.57, "lng": 31.2},
    {"id": 44, "name": "Flinders (Australia)", "lat": -31.72, "lng": 139.2},
    {"id": 50, "name": "Patagonia Deep", "lat": -31.72, "lng": -4.8},
]

CULTURAL_PROMPT = """You are a cultural anthropology researcher analyzing indigenous sacred traditions at a specific location.

For the location below, determine which SPECIFIC cultural traits are documented. Score each as YES (documented evidence), POSSIBLE (suggested but unconfirmed), or NO.

TRAITS TO CHECK:
1. ENERGY_SENSATION: Indigenous peoples describe feeling energy, buzzing, vibrating, tingling at this location
2. HEALING_TRADITION: Location used for healing ceremonies, medicinal rituals, or therapeutic practices
3. FORBIDDEN_ZONE: Location designated as taboo, forbidden to uninitiated, or dangerous to enter
4. CREATION_MYTH: Location features in a creation story, emergence myth, or origin narrative
5. PILGRIMAGE: Location is a destination for pilgrimage, ceremonial gathering, or periodic ritual visits
6. ASTRONOMICAL_USE: Location used for sky observation, solstice marking, or celestial tracking
7. SPIRIT_DWELLING: Location believed to be inhabited by spirits, ancestors, or supernatural beings
8. WATER_SACRED: Location's sacredness connected to water (springs, lakes, rivers, rain-calling)
9. BURIAL_GROUND: Location used for burial, funerary rites, or ancestor veneration
10. POWER_TRANSFER: Location believed to transfer power/knowledge to visitors through ritual

Return ONLY valid JSON (no markdown fences):
{"traits": [{"id": "ENERGY_SENSATION", "score": "YES|POSSIBLE|NO", "evidence": "specific tradition/people/practice"}, ...], "primary_tradition": "which indigenous group and what they specifically say about this place", "unique_feature": "what makes THIS site's tradition different from generic sacred sites"}"""


def research_node(node):
    """Research specific cultural traits at one node."""
    prompt = (
        f"LOCATION: {node['name']}\n"
        f"COORDINATES: {node['lat']}°N, {node['lng']}°E\n"
        f"UVG GRID NODE: {node['id']}\n\n"
        f"Research the indigenous/traditional cultural significance of this specific location. "
        f"What do the local indigenous peoples SAY about this place? What ceremonies do they perform? "
        f"What do they feel or experience here? Be SPECIFIC — name the people, the tradition, the practice.\n\n"
        + CULTURAL_PROMPT
    )

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2500,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        body = json.loads(resp["body"].read())
        raw = ""
        for block in body.get("content", []):
            if block.get("type") == "text":
                raw = block["text"]
                break
        
        # Robust parse (handles fences, truncation, repair)
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Truncation repair — find last valid closing point
        for trim_to in [text.rfind('},'), text.rfind('}'), text.rfind('"]')]:
            if trim_to <= 0:
                continue
            candidate = text[:trim_to + 1]
            candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
            candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        
        # Last resort: extract just traits array
        if '"traits"' in text:
            import re
            match = re.search(r'\{[^{}]*"traits"\s*:\s*\[', text)
            if match:
                start = match.start()
                # Find the outermost object
                candidate = text[start:]
                candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
                candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
        
        print(f"  Parse failed, raw length: {len(raw)}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    print("=" * 60)
    print("  CULTURAL MEMORY DEEP-DIVE")
    print(f"  Researching {len(SACRED_NODES)} sacred sites")
    print("=" * 60)

    results = []
    for node in SACRED_NODES:
        print(f"\n  [{node['id']}] {node['name']}...")
        result = research_node(node)
        if result:
            traits_yes = [t for t in result.get("traits", []) if t.get("score") == "YES"]
            traits_pos = [t for t in result.get("traits", []) if t.get("score") == "POSSIBLE"]
            print(f"    ✓ {len(traits_yes)} confirmed, {len(traits_pos)} possible")
            if traits_yes:
                print(f"    Confirmed: {', '.join(t['id'] for t in traits_yes)}")
            results.append({"node_id": node["id"], "name": node["name"], "cultural": result})
        else:
            print(f"    ✗ Failed")
            results.append({"node_id": node["id"], "name": node["name"], "cultural": None})
        time.sleep(1)

    # Save
    output = {"scan_type": "cultural_memory_deep_dive", "total": len(results), "results": results}
    output_path = os.path.join(DATA_DIR, "cultural-memory-results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Summary: find shared traits across sites
    print("\n" + "=" * 60)
    print("  SHARED CULTURAL TRAITS:")
    trait_nodes = {}
    for r in results:
        if not r["cultural"]:
            continue
        for t in r["cultural"].get("traits", []):
            if t["score"] == "YES":
                if t["id"] not in trait_nodes:
                    trait_nodes[t["id"]] = []
                trait_nodes[t["id"]].append(r["name"])
    
    for trait, nodes in sorted(trait_nodes.items(), key=lambda x: -len(x[1])):
        if len(nodes) >= 2:
            print(f"  {trait}: {len(nodes)} sites — {nodes}")
    
    print(f"\n  Saved: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
