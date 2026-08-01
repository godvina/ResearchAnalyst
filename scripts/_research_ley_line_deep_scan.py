"""Targeted deep research for ley line dashboard — fills gaps in scored data.

Runs documentary-quality research queries on:
1. Key named sites (Giza, Sedona, Angkor, Nazca, Easter Island, etc.)
2. Ley line alignment evidence between sites
3. Cross-site connection evidence (same technique, same astronomy)

Uses Brave Search + Bedrock Sonnet for synthesis.
Results merge into uvg-grid-scored-findings.json and research-all-nodes.json.
"""
import boto3
import json
import os
import time
import re
import requests

# Config
REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
BRAVE_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# Sites that SHOULD have rich data but currently have 0 signature matches
TARGET_NODES = [
    {"id": 1, "name": "Great Pyramid of Giza", "lat": 31.72, "lng": 31.2, "continent": "Africa"},
    {"id": 17, "name": "Sedona Vortexes", "lat": 31.72, "lng": -112.8, "continent": "North America"},
    {"id": 25, "name": "Angkor Wat", "lat": 10.81, "lng": 103.2, "continent": "Asia"},
    {"id": 35, "name": "Nazca Lines", "lat": -10.81, "lng": -76.8, "continent": "South America"},
    {"id": 47, "name": "Easter Island", "lat": -26.57, "lng": -112.8, "continent": "Oceania"},
    {"id": 4, "name": "Lake Baikal", "lat": 52.62, "lng": 103.2, "continent": "Asia"},
    {"id": 12, "name": "Mohenjo-daro", "lat": 26.57, "lng": 67.2, "continent": "Asia"},
    {"id": 14, "name": "Dragon Triangle", "lat": 26.57, "lng": 139.2, "continent": "Pacific"},
]


def brave_search(query, count=5):
    """Search via Brave API."""
    if not BRAVE_KEY:
        print(f"  [NO KEY] Skipping: {query[:60]}")
        return []
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": BRAVE_KEY, "Accept": "application/json"}
    params = {"q": query[:400], "count": count}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.ok:
            results = r.json().get("web", {}).get("results", [])
            return [{"title": x.get("title",""), "snippet": x.get("description","")} for x in results]
    except Exception as e:
        print(f"  Search error: {e}")
    return []


def invoke_sonnet(system, user_msg, max_tokens=1200):
    """Call Bedrock Sonnet."""
    try:
        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user_msg}]
            })
        )
        body = json.loads(resp["body"].read())
        for block in body.get("content", []):
            if block.get("type") == "text":
                return block["text"]
    except Exception as e:
        print(f"  Bedrock error: {e}")
    return ""

def parse_json_response(raw):
    """Parse JSON from LLM response, handling markdown fences."""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except:
        # Truncation repair
        for trim_to in [text.rfind('},'), text.rfind('}'), text.rfind('"]')]:
            if trim_to <= 0:
                continue
            candidate = text[:trim_to + 1]
            candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
            candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
            try:
                return json.loads(candidate)
            except:
                continue
    return None


DEEP_SCAN_SYSTEM = """You are a documentary research analyst scoring ancient sites against specific investigation signatures.
For each signature, provide evidence with SPECIFIC measurements, dates, researcher names, and publications.
Do NOT give generic answers. Every claim must have a source or measurable data point.

SIGNATURES TO SCORE (return MATCH/POSSIBLE/NO_MATCH for each):
1. MEGALITHIC: Stone blocks >10 tons, precision fitting, quarry source >30km away
2. ASTRONOMICAL: Structure aligned to solstice/equinox/star within 1° precision
3. ALIGNMENT: Site lies on documented great circle connecting 3+ other ancient sites
4. SHARED_TECHNIQUE: Same construction method found at distant site (>3000km)
5. INDIGENOUS_SACRED: Named as sacred/powerful by indigenous tradition for 500+ years
6. GEOMETRIC: Mathematical ratios (phi, pi, Earth measurements) encoded in dimensions
7. CLUSTER: 5+ ancient sites within 300km of this location across multiple eras
8. UNEXPLAINED: Specific measurement or feature that mainstream archaeology cannot explain

Return ONLY JSON:
{
  "codename": "UPPERCASE_NAME",
  "status": "CONFIRMED|PROBABLE|INCONCLUSIVE",
  "situation": "3 sentence documentary narration",
  "smoking_gun": "The single most compelling specific fact",
  "signatures": [
    {"id": "MEGALITHIC", "score": "MATCH|POSSIBLE|NO_MATCH", "evidence": "specific finding with measurement/source", "confidence": "strong|moderate|weak"}
  ],
  "connections": ["Site X: shared technique Y", "Site Z: same alignment"],
  "documentary_hook": "One sentence that makes a producer say 'we need to film this'"
}"""


def research_site_deep(site):
    """Run documentary-quality research on a specific named site."""
    print(f"\n{'='*60}")
    print(f"  Researching: {site['name']} (Node {site['id']})")
    print(f"{'='*60}")

    # Documentary-style queries (specific, measurement-focused)
    queries = [
        f"{site['name']} precise alignment measurement degrees arcminutes astronomical",
        f"{site['name']} largest stone block weight tons quarry source distance kilometers",
        f"{site['name']} great circle alignment connection other ancient sites",
        f"{site['name']} indigenous sacred tradition why considered powerful spiritual",
        f"{site['name']} mathematical precision phi pi dimensions unexplained",
        f"{site['name']} same construction technique found elsewhere similar sites worldwide",
    ]

    all_results = []
    for q in queries:
        print(f"  Q: {q[:70]}...")
        results = brave_search(q, count=4)
        all_results.extend(results)
        time.sleep(1.5)  # Rate limit

    # Deduplicate
    seen = set()
    unique = []
    for r in all_results:
        key = r.get("title", "")[:40]
        if key and key not in seen:
            seen.add(key)
            unique.append(r)

    # Synthesize
    results_text = "\n".join(
        f"[{i+1}] {r['title']} | {r['snippet']}"
        for i, r in enumerate(unique[:14])
    )

    user_msg = (
        f"SITE: {site['name']}\n"
        f"COORDINATES: {site['lat']:.2f}°N, {site['lng']:.2f}°E\n"
        f"UVG GRID NODE: {site['id']}\n"
        f"REGION: {site['continent']}\n\n"
        f"SEARCH RESULTS:\n{results_text}\n\n"
        f"Score this site against ALL 8 signatures. Be SPECIFIC — cite measurements, "
        f"researcher names, publication years. For ALIGNMENT, check if this site lies on "
        f"any documented great circle with other ancient sites."
    )

    print(f"  Synthesizing with Sonnet...")
    raw = invoke_sonnet(DEEP_SCAN_SYSTEM, user_msg)
    result = parse_json_response(raw)

    if result:
        print(f"  ✓ Status: {result.get('status', '?')}")
        print(f"  ✓ Hook: {result.get('documentary_hook', '?')[:80]}")
        sigs = result.get('signatures', [])
        matches = [s for s in sigs if s.get('score') == 'MATCH']
        print(f"  ✓ Signature matches: {len(matches)}/{len(sigs)}")
    else:
        print(f"  ✗ Failed to parse response")

    return result


def main():
    if not BRAVE_KEY:
        print("ERROR: Set BRAVE_SEARCH_API_KEY environment variable")
        print("  $env:BRAVE_SEARCH_API_KEY = 'your-key-here'")
        return

    print("=" * 60)
    print("  LEY LINE DEEP SCAN — Documentary Research")
    print(f"  Targets: {len(TARGET_NODES)} key sites")
    print("=" * 60)

    results = []
    for site in TARGET_NODES:
        result = research_site_deep(site)
        if result:
            results.append({"node_id": site["id"], "site_name": site["name"], "deep_scan": result})
        time.sleep(2)

    # Save results
    output_path = os.path.join(DATA_DIR, "uvg-grid-deep-scan-results.json")
    with open(output_path, "w") as f:
        json.dump({"scan_type": "ley_line_deep_scan", "total": len(results), "results": results}, f, indent=2)
    print(f"\n\n{'='*60}")
    print(f"  DONE! {len(results)} sites researched")
    print(f"  Output: {output_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
