"""Build Deep Flat Earth Dataset — OBJECTIVE & FAIR.

This script builds a comprehensive, FAIR dataset on flat earth claims by:
1. Starting with ALL major flat earth claims (not just 8 — targeting 50+)
2. For EACH claim, searching for the BEST evidence both sides present
3. Using Bedrock to research each claim deeply (PRO evidence + CON evidence)
4. Being OBJECTIVE — presenting both sides with equal rigor

The goal is NOT to prove flat earth wrong (that's easy).
The goal is to demonstrate our Proof Engine evaluates evidence OBJECTIVELY
regardless of which side it's evaluating. The engine should:
- Score PRO claims fairly (give credit where evidence exists)
- Score CON rebuttals fairly (acknowledge strength of scientific evidence)
- Let the EVIDENCE determine the verdict, not bias

Sources scraped:
- flattruths.com (already done)
- wiki.tfes.org (already done)
- Reddit r/flatearth (already done)
- Bedrock Claude for deep research on each claim (this script)

Output: A comprehensive JSON with 50+ claims, each with:
- claim_text (the flat earth argument)
- pro_evidence (best evidence FOR the claim)
- con_evidence (best evidence AGAINST the claim)
- testable_prediction (what would need to be true)
- key_experiments (what experiments address this)
- category (observational, physics, conspiracy, model, historical)
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'flat_earth_evidence'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# All major flat earth claims — comprehensive list from multiple sources
FLAT_EARTH_CLAIMS = [
    # === OBSERVATIONAL CLAIMS ===
    {"id": "fe-001", "cat": "observational", "claim": "The horizon always appears perfectly flat and level at any altitude"},
    {"id": "fe-002", "cat": "observational", "claim": "The horizon always rises to meet eye level regardless of altitude"},
    {"id": "fe-003", "cat": "observational", "claim": "Objects can be seen at distances beyond where curvature should hide them"},
    {"id": "fe-004", "cat": "observational", "claim": "The Chicago skyline is visible from 60 miles across Lake Michigan"},
    {"id": "fe-005", "cat": "observational", "claim": "Ships that disappear hull-first can be brought back with a telescope/zoom"},
    {"id": "fe-006", "cat": "observational", "claim": "Water always finds and maintains a level surface and cannot curve"},
    {"id": "fe-007", "cat": "observational", "claim": "The Bedford Level Experiment proved 6 miles of water is flat"},
    {"id": "fe-008", "cat": "observational", "claim": "Laser tests over long distances show no curvature drop"},
    {"id": "fe-009", "cat": "observational", "claim": "No measurable curvature has ever been directly observed or photographed"},
    {"id": "fe-010", "cat": "observational", "claim": "Airplane windows show a flat horizon even at cruising altitude"},
    # === PHYSICS CLAIMS ===
    {"id": "fe-011", "cat": "physics", "claim": "We cannot feel or measure Earth's alleged 1000mph rotation at the equator"},
    {"id": "fe-012", "cat": "physics", "claim": "A hovering helicopter does not drift west as Earth allegedly rotates beneath it"},
    {"id": "fe-013", "cat": "physics", "claim": "Gravity is not a real force — objects fall due to density and buoyancy alone"},
    {"id": "fe-014", "cat": "physics", "claim": "Gravity cannot explain how water sticks to a spinning ball"},
    {"id": "fe-015", "cat": "physics", "claim": "The Coriolis effect does not measurably affect small-scale experiments"},
    {"id": "fe-016", "cat": "physics", "claim": "Rivers cannot flow uphill toward the equator on a globe"},
    {"id": "fe-017", "cat": "physics", "claim": "The Michelson-Morley experiment proved Earth is stationary"},
    {"id": "fe-018", "cat": "physics", "claim": "The Airy's Failure experiment proved Earth does not move"},
    {"id": "fe-019", "cat": "physics", "claim": "The Sagnac experiment detected no orbital motion of Earth"},
    {"id": "fe-020", "cat": "physics", "claim": "Vacuum cannot exist next to a pressurized atmosphere without a physical barrier"},
]

FLAT_EARTH_CLAIMS += [
    # === ASTRONOMY / CELESTIAL CLAIMS ===
    {"id": "fe-021", "cat": "celestial", "claim": "Polaris (North Star) remains fixed directly overhead while all stars rotate around it"},
    {"id": "fe-022", "cat": "celestial", "claim": "Star trails show perfect circles — impossible on a tilted spinning wobbling ball"},
    {"id": "fe-023", "cat": "celestial", "claim": "The sun and moon are the same apparent size because they are local and close"},
    {"id": "fe-024", "cat": "celestial", "claim": "The sun's rays diverge proving it is close and local, not 93 million miles away"},
    {"id": "fe-025", "cat": "celestial", "claim": "Moonlight is cold — objects in moonlight are colder than objects in moon-shadow"},
    {"id": "fe-026", "cat": "celestial", "claim": "The moon produces its own light rather than reflecting sunlight"},
    {"id": "fe-027", "cat": "celestial", "claim": "Solar and lunar eclipses cannot be explained by the ball earth model"},
    {"id": "fe-028", "cat": "celestial", "claim": "Stars are not distant suns — they are small luminaries embedded in the firmament"},
    {"id": "fe-029", "cat": "celestial", "claim": "The sun's path explains seasons on a flat plane via expanding/contracting circles"},
    {"id": "fe-030", "cat": "celestial", "claim": "Planets are wandering stars, not solid spheres — telescope footage shows luminous objects"},
    # === CONSPIRACY / SUPPRESSION CLAIMS ===
    {"id": "fe-031", "cat": "conspiracy", "claim": "NASA is a military deception operation that fakes space imagery"},
    {"id": "fe-032", "cat": "conspiracy", "claim": "All photos of Earth from space are admitted composites or CGI"},
    {"id": "fe-033", "cat": "conspiracy", "claim": "The Antarctic Treaty prevents independent exploration of the ice wall edge"},
    {"id": "fe-034", "cat": "conspiracy", "claim": "Admiral Byrd's Operation Highjump discovered land beyond Antarctica"},
    {"id": "fe-035", "cat": "conspiracy", "claim": "Operation Fishbowl nuclear tests were aimed at the firmament dome"},
    {"id": "fe-036", "cat": "conspiracy", "claim": "The Van Allen radiation belts make human space travel impossible"},
    {"id": "fe-037", "cat": "conspiracy", "claim": "Apollo moon landing footage contains provable anomalies and inconsistencies"},
    {"id": "fe-038", "cat": "conspiracy", "claim": "ISS footage shows evidence of wires, green screens, and air bubbles"},
    {"id": "fe-039", "cat": "conspiracy", "claim": "SpaceX rocket footage shows objects hitting an invisible barrier at altitude"},
    {"id": "fe-040", "cat": "conspiracy", "claim": "All world governments conspire to hide flat earth for control and profit"},
]

FLAT_EARTH_CLAIMS += [
    # === FLIGHT / NAVIGATION CLAIMS ===
    {"id": "fe-041", "cat": "navigation", "claim": "Flight paths make more sense on a flat azimuthal equidistant map than a globe"},
    {"id": "fe-042", "cat": "navigation", "claim": "Southern hemisphere direct flights (e.g., Santiago to Sydney) are suspiciously long"},
    {"id": "fe-043", "cat": "navigation", "claim": "Emergency landings always divert to northern hemisphere locations"},
    {"id": "fe-044", "cat": "navigation", "claim": "Pilots do not continuously adjust for curvature — they fly level"},
    {"id": "fe-045", "cat": "navigation", "claim": "Gyroscopes maintain level without detecting any curvature or rotation"},
    # === HISTORICAL / AUTHORITY CLAIMS ===
    {"id": "fe-046", "cat": "historical", "claim": "Ancient civilizations universally described a flat earth under a dome"},
    {"id": "fe-047", "cat": "historical", "claim": "The globe model was introduced by secret societies to hide God"},
    {"id": "fe-048", "cat": "historical", "claim": "Copernicus, Galileo, and Newton were all connected to secret societies"},
    {"id": "fe-049", "cat": "historical", "claim": "The Bible describes a flat earth with a firmament dome in 17+ passages"},
    {"id": "fe-050", "cat": "historical", "claim": "The UN logo and ICAO aviation maps use the flat earth (AE) projection"},
    # === MODEL CLAIMS ===
    {"id": "fe-051", "cat": "model", "claim": "The flat earth model with dome explains all observations without gravity"},
    {"id": "fe-052", "cat": "model", "claim": "Perspective explains the sunset — sun shrinks to vanishing point, does not go below horizon"},
    {"id": "fe-053", "cat": "model", "claim": "Atmospheric lensing creates the illusion of curvature in some photos"},
    {"id": "fe-054", "cat": "model", "claim": "The firmament is a physical dome structure above the flat plane"},
    {"id": "fe-055", "cat": "model", "claim": "Antarctica is an ice wall surrounding the flat earth disc, not a continent"},
]


RESEARCH_PROMPT = """You are an OBJECTIVE research analyst. Your job is to present BOTH SIDES of a claim fairly.

CLAIM: "{claim}"

Research this claim thoroughly. Present:

1. BEST PRO EVIDENCE (strongest arguments and evidence that SUPPORT this claim):
   - What specific observations, experiments, or data do proponents cite?
   - What are their strongest logical arguments?
   - Are there any legitimate scientific anomalies they reference?

2. BEST CON EVIDENCE (strongest arguments and evidence that REFUTE this claim):
   - What specific scientific measurements, experiments, or observations contradict this?
   - What is the mainstream scientific explanation?
   - Has this been directly tested and what were the results?

3. TESTABLE PREDICTION: What specific, measurable test would definitively settle this?

4. KEY EXPERIMENTS: What experiments have been done or could be done to test this?

5. OBJECTIVITY CHECK: Rate the strength of evidence on each side (1-10 scale).

Be FAIR to both sides. Do not dismiss the PRO side without addressing their specific evidence.
Do not accept the CON side without citing specific measurements/experiments.

Respond in JSON:
{{
  "pro_evidence": "string (200-400 words, specific citations/observations)",
  "con_evidence": "string (200-400 words, specific measurements/experiments)",
  "testable_prediction": "string (specific measurable test)",
  "key_experiments": ["experiment1", "experiment2", "experiment3"],
  "pro_strength": <1-10>,
  "con_strength": <1-10>,
  "category": "observational|physics|celestial|conspiracy|navigation|historical|model",
  "related_claims": ["claim_id_1", "claim_id_2"]
}}"""


def research_claim(claim_data, bedrock, attempt=0):
    """Use Bedrock to deeply research a single flat earth claim."""
    prompt = RESEARCH_PROMPT.format(claim=claim_data['claim'])

    try:
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            }),
            contentType="application/json",
            accept="application/json"
        )
        result = json.loads(response['body'].read())
        content = result['content'][0]['text']

        # Parse JSON response
        try:
            parsed = json.loads(content)
            return {
                'claim_id': claim_data['id'],
                'category': claim_data['cat'],
                'claim_text': claim_data['claim'],
                'pro_evidence': parsed.get('pro_evidence', ''),
                'con_evidence': parsed.get('con_evidence', ''),
                'testable_prediction': parsed.get('testable_prediction', ''),
                'key_experiments': parsed.get('key_experiments', []),
                'pro_strength': parsed.get('pro_strength', 0),
                'con_strength': parsed.get('con_strength', 0),
                'related_claims': parsed.get('related_claims', []),
                'researched_at': datetime.now(timezone.utc).isoformat(),
            }
        except json.JSONDecodeError:
            # Use raw text if JSON parsing fails
            return {
                'claim_id': claim_data['id'],
                'category': claim_data['cat'],
                'claim_text': claim_data['claim'],
                'raw_research': content[:3000],
                'parse_error': True,
                'researched_at': datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        if attempt < 2:
            time.sleep(3)
            return research_claim(claim_data, bedrock, attempt + 1)
        return {
            'claim_id': claim_data['id'],
            'category': claim_data['cat'],
            'claim_text': claim_data['claim'],
            'error': str(e),
            'researched_at': datetime.now(timezone.utc).isoformat(),
        }


def main():
    import boto3

    print("=" * 70)
    print("BUILDING DEEP FLAT EARTH DATASET — OBJECTIVE & FAIR")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Total claims to research: {len(FLAT_EARTH_CLAIMS)}")
    print(f"Strategy: Deep research BOTH SIDES of each claim via Bedrock")
    print(f"Estimated time: ~5 minutes (55 claims × ~5s each)")
    print()

    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    print("Connected to Bedrock (Claude 3 Haiku)")
    print()

    # Research each claim
    results = []
    categories = {}

    for i, claim_data in enumerate(FLAT_EARTH_CLAIMS):
        cat = claim_data['cat']
        categories[cat] = categories.get(cat, 0) + 1
        print(f"  [{i+1:2d}/{len(FLAT_EARTH_CLAIMS)}] {claim_data['id']}: {claim_data['claim'][:60]}...")

        result = research_claim(claim_data, bedrock)
        results.append(result)

        if result.get('error'):
            print(f"         ERROR: {result['error'][:60]}")
        elif result.get('parse_error'):
            print(f"         (raw text, JSON parse failed)")
        else:
            pro = result.get('pro_strength', 0)
            con = result.get('con_strength', 0)
            print(f"         PRO:{pro}/10  CON:{con}/10")

        # Rate limit
        time.sleep(1.2)

        # Save progress every 10 claims
        if (i + 1) % 10 == 0:
            _save_progress(results, categories)
            print(f"  --- Progress saved ({i+1}/{len(FLAT_EARTH_CLAIMS)}) ---\n")

    # Final save
    _save_progress(results, categories, final=True)

    # Summary
    print("\n" + "=" * 70)
    print("DATASET BUILD COMPLETE")
    print("=" * 70)
    successful = [r for r in results if not r.get('error') and not r.get('parse_error')]
    print(f"  Successfully researched: {len(successful)}/{len(FLAT_EARTH_CLAIMS)}")
    print(f"  Categories: {json.dumps(categories, indent=4)}")

    if successful:
        avg_pro = sum(r.get('pro_strength', 0) for r in successful) / len(successful)
        avg_con = sum(r.get('con_strength', 0) for r in successful) / len(successful)
        print(f"\n  Average PRO strength: {avg_pro:.1f}/10")
        print(f"  Average CON strength: {avg_con:.1f}/10")
        print(f"  Evidence gap (CON - PRO): {avg_con - avg_pro:.1f}")
        print()
        print("  If the engine is OBJECTIVE:")
        print("    - PRO strength should be > 0 (FE proponents DO cite real observations)")
        print("    - CON strength should be >> PRO (scientific evidence is overwhelming)")
        print("    - Both sides should be SPECIFIC (not hand-waving)")

    print(f"\n  Output: {OUTPUT_DIR / 'flat_earth_deep_research.json'}")
    print(f"  Ready for Proof Engine evaluation with: scripts/_run_flat_earth_proof.py")


def _save_progress(results, categories, final=False):
    """Save current progress to JSON."""
    output = {
        'dataset_info': {
            'name': 'Flat Earth Deep Research — Objective Dual-Side Dataset',
            'created': datetime.now(timezone.utc).isoformat(),
            'claims_total': len(FLAT_EARTH_CLAIMS),
            'claims_researched': len(results),
            'methodology': 'Each claim researched for BOTH sides via Bedrock Claude',
            'objectivity_principle': 'Present strongest evidence on both sides, let data determine verdict',
            'status': 'FINAL' if final else 'IN_PROGRESS',
        },
        'categories': categories,
        'claims': results,
    }

    out_path = OUTPUT_DIR / 'flat_earth_deep_research.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
