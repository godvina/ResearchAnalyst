"""Process Flat Earth theories through the Proof Engine.

All claims should be evaluated as UNPROVEN (actively disproven by evidence).
This demonstrates the Proof Engine correctly identifying debunked theories.
"""
import json
import os
import sys
import boto3
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.services.proof_engine import ProofEngine

DATA_PATH = 'src/data/conspiracy-seed/flat_earth/flat_earth_theories.json'
OUTPUT_PATH = 'src/data/proof-engine-results-flat-earth.json'

with open(DATA_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

theories = data['theories']

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
engine = ProofEngine(bedrock_client=bedrock)

print(f"FLAT EARTH PROOF ENGINE EVALUATION")
print(f"{'='*50}")
print(f"Theories to evaluate: {len(theories)}")
print(f"Standard: SCIENTIFIC")
print()

results = []

for i, theory in enumerate(theories):
    print(f"[{i+1}/{len(theories)}] {theory['title']}...", end=" ", flush=True)

    evidence_parts = ["EVIDENCE SUPPORTING THE CLAIM:"]
    for e in theory.get('evidence_for', []):
        evidence_parts.append(f"  + {e}")
    evidence_parts.append("\nEVIDENCE AGAINST THE CLAIM:")
    for e in theory.get('evidence_against', []):
        evidence_parts.append(f"  - {e}")
    evidence_parts.append(f"\nTESTABLE PREDICTION: {theory.get('testable_prediction', 'None')}")
    evidence = "\n".join(evidence_parts)

    finding_data = {
        "description": theory['claim'],
        "theory_name": "flat_earth",
        "title": theory['title'],
    }

    verdict = engine.evaluate(
        finding_id=theory['id'],
        finding_data=finding_data,
        evidence=evidence,
        standard_name="scientific",
        tenant_id="conspiracy_theories"
    )

    results.append({
        "theory_id": theory['id'],
        "title": theory['title'],
        "claim": theory['claim'],
        "verdict": verdict.verdict,
        "overall_score": verdict.overall_score,
        "checklist_items": [
            {"item": item.description, "score": item.score, "justification": item.justification[:200]}
            for item in verdict.checklist_items
        ],
        "research_directions": verdict.research_directions,
    })
    print(f"{verdict.verdict} (score: {verdict.overall_score:.2f})")

# Save
output = {
    "evaluation_run": {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "standard": "scientific",
        "model": "us.anthropic.claude-3-haiku-20240307-v1:0",
        "theories_evaluated": len(results),
    },
    "summary": {
        "proven": sum(1 for r in results if r['verdict'] == 'PROVEN'),
        "unproven": sum(1 for r in results if r['verdict'] == 'UNPROVEN'),
        "insufficient": sum(1 for r in results if r['verdict'] == 'INSUFFICIENT_EVIDENCE'),
        "average_score": sum(r['overall_score'] for r in results) / len(results) if results else 0,
    },
    "results": results,
}

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n{'='*50}")
print(f"SUMMARY:")
print(f"  PROVEN: {output['summary']['proven']}")
print(f"  UNPROVEN: {output['summary']['unproven']}")
print(f"  INSUFFICIENT: {output['summary']['insufficient']}")
print(f"  Average score: {output['summary']['average_score']:.2f}")
print(f"\nResults saved to: {OUTPUT_PATH}")
