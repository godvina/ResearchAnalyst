"""
Generate AI narratives for Geographic Explorer.
Run once to build static narrative JS file. Re-run when data changes.
Estimated cost: ~$0.15-0.25 for ~36 Bedrock calls (Nova Pro).

Usage:
    python scripts/generate_geographic_narratives.py
"""

import json
import time
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3

# Config
MODEL_ID = "us.amazon.nova-pro-v1:0"
REGION = "us-east-1"
MAX_TOKENS = 500
TEMPERATURE = 0.7

# Load source data — check multiple possible locations
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "src" / "data" / "conspiracy-seed" / "irish_sacred_sites"
OUTPUT_FILE = PROJECT_ROOT / "src" / "frontend" / "geographic-explorer-narratives.js"

# Fallback data dir if primary doesn't exist
if not DATA_DIR.exists():
    alt_dir = PROJECT_ROOT / "data" / "conspiracy-seed" / "irish_sacred_sites"
    if alt_dir.exists():
        DATA_DIR = alt_dir


def load_data():
    """Load all site data from JSON files."""
    main_file = DATA_DIR / "irish_ancient_sites.json"
    continued_file = DATA_DIR / "irish_ancient_sites_continued.json"
    deep_file = DATA_DIR / "tier2_deep_research.json"

    # Verify files exist
    for f in [main_file, continued_file, deep_file]:
        if not f.exists():
            print(f"  ERROR: Required file not found: {f}")
            print(f"  Checked DATA_DIR: {DATA_DIR}")
            sys.exit(1)

    with open(main_file, encoding="utf-8") as f:
        main_data = json.load(f)
    with open(continued_file, encoding="utf-8") as f:
        continued_data = json.load(f)
    with open(deep_file, encoding="utf-8") as f:
        deep_data = json.load(f)

    # Merge sites — handle both key patterns
    sites = main_data.get("sites", []) + continued_data.get("sites_continued", continued_data.get("sites", []))

    # Build deep research lookup (keyed by short id like "irl-001")
    deep_research = {}
    for key, val in deep_data.get("sites", {}).items():
        short_id = key.split("_")[0]  # "irl-001_newgrange" -> "irl-001"
        deep_research[short_id] = val
    for key, val in deep_data.get("additional_sites", {}).items():
        short_id = key.split("_")[0]
        if short_id not in deep_research:
            deep_research[short_id] = val

    cross_patterns = deep_data.get("cross_site_patterns", {})
    global_connections = deep_data.get("global_connections", {})

    # Region mapping by county
    regions = {
        "Boyne Valley": [s for s in sites if s.get("county") == "Meath"],
        "Sligo / Carrowmore": [s for s in sites if s.get("county") == "Sligo"],
        "The Burren": [s for s in sites if s.get("county") == "Clare"],
        "Kerry Coast": [s for s in sites if s.get("county") == "Kerry"],
        "Connemara / Aran Islands": [s for s in sites if "Galway" in s.get("county", "")],
        "West Cork": [s for s in sites if s.get("county") == "Cork"],
    }

    return sites, deep_research, cross_patterns, global_connections, regions


def invoke_bedrock(client, prompt, system_prompt=None, max_tokens=MAX_TOKENS):
    """Call Bedrock with Nova Pro via the converse API.
    
    Returns: (text, input_tokens, output_tokens) or (None, 0, 0) on failure.
    """
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    kwargs = {
        "modelId": MODEL_ID,
        "messages": messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": TEMPERATURE,
        },
    }

    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    try:
        response = client.converse(**kwargs)
        output_text = response["output"]["message"]["content"][0]["text"]
        input_tokens = response["usage"]["inputTokens"]
        output_tokens = response["usage"]["outputTokens"]
        return output_text, input_tokens, output_tokens
    except Exception as e:
        print(f"  ERROR: {str(e)[:120]}")
        return None, 0, 0


def generate_intelligence_briefs(client, sites, deep_research):
    """Generate 3-paragraph intelligence briefs per site."""
    print("\n=== Generating Intelligence Briefs ===")
    print(f"  Sites to process: {len(sites)}")
    briefs = {}

    system = (
        "You are an investigative intelligence analyst writing field briefings for a "
        "researcher visiting ancient archaeological sites. Your tone is authoritative but "
        "open-minded — present mainstream archaeology AND alternative interpretations fairly. "
        "Use specific measurements, dates, and academic sources. Never dismiss alternative "
        "theories — investigate them."
    )

    for i, site in enumerate(sites, 1):
        site_id = site.get("id", "")
        name = site.get("name", "")
        print(f"  [{i}/{len(sites)}] Generating brief for {name}...")

        deep = deep_research.get(site_id, {})
        deep_text = json.dumps(deep, indent=2)[:2000] if deep else "No deep research available."

        prompt = f"""Write a 3-paragraph intelligence brief for the site: {name}

Site data:
- Date built: {site.get('date_built', 'Unknown')}
- Age: {site.get('age_years', 'Unknown')} years
- Category: {site.get('category', 'Unknown')}
- UNESCO: {site.get('unesco', False)}
- Mysteries: {json.dumps(site.get('mysteries', []))}
- Taxonomy scores: {json.dumps(site.get('taxonomy_matches', {}))}
- Cross-domain connections: {json.dumps(site.get('cross_domain_connections', []))}
- Deep research: {deep_text}

Write EXACTLY 3 paragraphs:
1. HOOK (2-3 sentences): Lead with the single most striking anomaly or connection. Make the reader stop and pay attention.
2. EVIDENCE (3-4 sentences): Specific measurements, dates, academic sources. Numbers. Comparisons to other sites.
3. IMPLICATION (2-3 sentences): What this means for the broader investigation. What remains unproven. What field research would advance the case.

Max 200 words total. Be specific — use numbers not adjectives."""

        text, in_tok, out_tok = invoke_bedrock(client, prompt, system)
        if text:
            # Split into paragraphs
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            briefs[site_id] = {
                "hook": paragraphs[0] if len(paragraphs) > 0 else "",
                "evidence": paragraphs[1] if len(paragraphs) > 1 else "",
                "implication": paragraphs[2] if len(paragraphs) > 2 else "",
                "tokens": {"input": in_tok, "output": out_tok},
            }
        else:
            briefs[site_id] = {"hook": "", "evidence": "", "implication": "", "error": True}

        time.sleep(0.5)  # Rate limiting

    print(f"  ✓ Completed {len(briefs)} intelligence briefs")
    return briefs


def generate_research_missions(client, sites, deep_research):
    """Generate field research missions for sites with gap theories."""
    print("\n=== Generating Research Missions ===")
    missions = {}

    system = (
        "You are a field research planner for archaeological investigations. Generate "
        "specific, actionable tasks that a researcher can complete during a site visit. "
        "Each task should be measurable and contribute to advancing a theory's evidence score."
    )

    processed = 0
    for site in sites:
        site_id = site.get("id", "")
        name = site.get("name", "")
        taxonomy = site.get("taxonomy_matches", {})

        # Find gap domains (0.40-0.79 — needs more evidence)
        gaps = {k: v for k, v in taxonomy.items() if 0.40 <= v < 0.80}
        if not gaps:
            continue

        processed += 1
        print(f"  [{processed}] Generating missions for {name} ({len(gaps)} gaps)...")

        prompt = f"""Site: {name} ({site.get('date_built', '')})
Mysteries: {json.dumps(site.get('mysteries', [])[:3])}

These theories need more evidence:
{json.dumps(gaps, indent=2)}

For each gap theory, generate 2-3 specific field research tasks. Each task should:
- Be completable during a single site visit
- Produce measurable evidence (photograph, measurement, observation)
- Target advancing the score by ~0.15-0.20

Format as JSON array:
[{{"domain": "domain_name", "current_score": 0.XX, "target_score": 0.XX, "tasks": ["task 1", "task 2"]}}]"""

        text, in_tok, out_tok = invoke_bedrock(client, prompt, system, max_tokens=400)
        if text:
            try:
                # Try to parse JSON from response
                json_start = text.find("[")
                json_end = text.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    missions[site_id] = json.loads(text[json_start:json_end])
                else:
                    missions[site_id] = [{"raw": text}]
            except json.JSONDecodeError:
                missions[site_id] = [{"raw": text}]

        time.sleep(0.5)

    print(f"  ✓ Completed {len(missions)} research mission sets")
    return missions


def generate_documentary_chapters(client, regions, deep_research, cross_patterns):
    """Generate History Channel-style chapters per region."""
    print("\n=== Generating Documentary Chapters ===")
    chapters = {}

    system = (
        "You are writing an investigative documentary script for a History Channel / "
        "Discovery Channel program about ancient mysteries. Present mainstream archaeology "
        "AND alternative interpretations fairly. Use specific numbers, academic sources, "
        "and concrete details. Tone: authoritative but open-minded. Never dismiss — investigate."
    )

    for region_name, region_sites in regions.items():
        if not region_sites:
            continue

        print(f"  Generating chapter for {region_name} ({len(region_sites)} sites)...")

        site_summaries = []
        for s in region_sites:
            summary = f"- {s.get('name', '')} ({s.get('date_built', '')}): {s.get('description', '')[:100]}"
            site_summaries.append(summary)

        # Find relevant cross-site patterns
        relevant_patterns = []
        for pattern_name, desc in cross_patterns.items():
            for s in region_sites:
                # Check if any word from site name appears in pattern description
                site_words = s.get("name", "").split("(")[0].strip().lower().split()
                if any(word in desc.lower() for word in site_words if len(word) > 3):
                    relevant_patterns.append(f"{pattern_name}: {desc}")
                    break

        prompt = f"""Write a documentary chapter about the {region_name} region of Ireland.

Sites in this region:
{chr(10).join(site_summaries)}

Cross-site patterns relevant to this region:
{chr(10).join(relevant_patterns[:3]) if relevant_patterns else 'None identified yet.'}

Write 400-600 words in this structure:
1. HOOK: Dramatic opening question or statement that grabs attention
2. THE EVIDENCE: Walk through each site with specific measurements and dates
3. THE PATTERN: What connects these sites? What does the grouping reveal?
4. WHAT REMAINS: Open questions that field research could answer

Tone: Investigative documentary. Concrete details. Specific numbers. Open questions."""

        text, in_tok, out_tok = invoke_bedrock(client, prompt, system, max_tokens=800)
        if text:
            chapters[region_name] = {
                "title": f"Chapter: {region_name}",
                "subtitle": f"{len(region_sites)} sites \u00b7 Ancient mysteries of {region_name}",
                "content": text.replace("\n", "<br><br>"),
                "tokens": {"input": in_tok, "output": out_tok},
            }
        else:
            chapters[region_name] = {
                "title": f"Chapter: {region_name}",
                "subtitle": f"{len(region_sites)} sites",
                "content": "",
                "error": True,
            }

        time.sleep(0.5)

    print(f"  ✓ Completed {len(chapters)} documentary chapters")
    return chapters


def generate_connection_narratives(client, global_connections):
    """Generate 1-2 sentence narrated edge descriptions for global connections."""
    print("\n=== Generating Connection Narratives ===")
    narratives = {}

    if not global_connections:
        print("  No global connections found in data — skipping.")
        return narratives

    for conn_type, site_list in global_connections.items():
        print(f"  Generating narrative for {conn_type}...")

        prompt = f"""Connection type: {conn_type.replace('_', ' ')}
Sites sharing this pattern: {', '.join(site_list) if isinstance(site_list, list) else str(site_list)}

Write a 1-2 sentence explanation of WHY these sites share this pattern and what it implies.
Be specific — use measurements, dates, or techniques. Not vague ("similar") — precise.
Max 50 words."""

        text, in_tok, out_tok = invoke_bedrock(client, prompt, max_tokens=100)
        if text:
            narratives[conn_type] = text.strip()

        time.sleep(0.3)

    print(f"  ✓ Completed {len(narratives)} connection narratives")
    return narratives


def write_output(briefs, missions, chapters, connections, total_cost):
    """Write all narratives to the output JS file."""
    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output = f"""/**
 * Geographic Explorer — AI-Generated Narratives
 * Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
 * Model: {MODEL_ID}
 * Estimated cost: ${total_cost:.4f}
 * Generated by: scripts/generate_geographic_narratives.py
 *
 * DO NOT EDIT MANUALLY — re-run the generation script to update.
 */

// Intelligence briefs per site (3-paragraph investigative summaries)
const GEO_INTELLIGENCE_BRIEFS = {json.dumps(briefs, indent=2)};

// Research missions per site (field tasks targeting gap theories)
const GEO_RESEARCH_MISSIONS = {json.dumps(missions, indent=2)};

// Documentary chapters per region (History Channel-style narratives)
const GEO_DOCUMENTARY_CHAPTERS = {json.dumps(chapters, indent=2)};

// Connection narratives for graph edges (1-2 sentence explanations)
const GEO_CONNECTION_NARRATIVES = {json.dumps(connections, indent=2)};
"""

    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(f"\n✅ Written to {OUTPUT_FILE}")
    print(f"   File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


def main():
    print("=" * 60)
    print("Geographic Explorer — AI Narrative Generation")
    print(f"Model: {MODEL_ID}")
    print(f"Region: {REGION}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Load data
    sites, deep_research, cross_patterns, global_connections, regions = load_data()
    print(f"\nLoaded: {len(sites)} sites, {len(deep_research)} deep research entries")
    print(f"Regions: {', '.join(regions.keys())}")
    print(f"Global connections: {len(global_connections)} types")
    print(f"Cross-site patterns: {len(cross_patterns)} patterns")

    # Initialize Bedrock client
    try:
        client = boto3.client("bedrock-runtime", region_name=REGION)
        print(f"\n✓ Bedrock client initialized (region: {REGION})")
    except Exception as e:
        print(f"\n✗ Failed to create Bedrock client: {e}")
        print("  Ensure AWS credentials are configured (aws configure / env vars / IAM role)")
        sys.exit(1)

    total_input_tokens = 0
    total_output_tokens = 0

    # Generate all content — each section handles its own errors
    briefs = generate_intelligence_briefs(client, sites, deep_research)
    missions = generate_research_missions(client, sites, deep_research)
    chapters = generate_documentary_chapters(client, regions, deep_research, cross_patterns)
    connections = generate_connection_narratives(client, global_connections)

    # Calculate costs (Nova Pro: $0.0008/1K input, $0.0032/1K output)
    for b in briefs.values():
        if "tokens" in b:
            total_input_tokens += b["tokens"]["input"]
            total_output_tokens += b["tokens"]["output"]
    for c in chapters.values():
        if "tokens" in c:
            total_input_tokens += c["tokens"]["input"]
            total_output_tokens += c["tokens"]["output"]

    input_cost = (total_input_tokens / 1000) * 0.0008
    output_cost = (total_output_tokens / 1000) * 0.0032
    total_cost = input_cost + output_cost

    print(f"\n--- Cost Summary ---")
    print(f"Input tokens:  {total_input_tokens:,}")
    print(f"Output tokens: {total_output_tokens:,}")
    print(f"Input cost:    ${input_cost:.4f}")
    print(f"Output cost:   ${output_cost:.4f}")
    print(f"Total cost:    ${total_cost:.4f}")
    print(f"---")

    # Summary of generated content
    successful_briefs = sum(1 for b in briefs.values() if not b.get("error"))
    successful_chapters = sum(1 for c in chapters.values() if not c.get("error"))
    print(f"\nGenerated content:")
    print(f"  Intelligence briefs: {successful_briefs}/{len(briefs)}")
    print(f"  Research missions:   {len(missions)} sites with gap tasks")
    print(f"  Documentary chapters:{successful_chapters}/{len(chapters)}")
    print(f"  Connection narratives:{len(connections)}/{len(global_connections)}")

    # Write output
    write_output(briefs, missions, chapters, connections, total_cost)

    print(f"\n🎬 Done! Refresh geographic-explorer.html to see AI narratives.")
    print(f"   Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
