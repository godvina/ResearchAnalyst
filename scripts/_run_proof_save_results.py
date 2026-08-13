"""Run Proof Engine on all seed theories and save results to JSON."""
import json
import os
import sys
import boto3
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.services.proof_engine import ProofEngine

# Connect to Bedrock
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
engine = ProofEngine(bedrock_client=bedrock)

# Load seed theories
with open('src/data/conspiracy-seed/ancient_mysteries_theories/ancient_alien_theories.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

theories = data['theories']
print(f"Evaluating {len(theories)} theories against SCIENTIFIC standard...")
print(f"Using: Bedrock Claude 3 Haiku")
print()

results = []

for i, theory in enumerate(theories):
    print(f"[{i+1}/{len(theories)}] {theory['title']}...", end=" ", flush=True)

    # Build evidence string
    evidence_parts = ["EVIDENCE SUPPORTING THE CLAIM:"]
    for e in theory.get('current_evidence_for', []):
        evidence_parts.append(f"  + {e}")
    evidence_parts.append("\nEVIDENCE AGAINST THE CLAIM:")
    for e in theory.get('current_evidence_against', []):
        evidence_parts.append(f"  - {e}")
    evidence_parts.append(f"\nTESTABLE PREDICTION: {theory.get('testable_prediction', 'None')}")
    evidence = "\n".join(evidence_parts)

    finding_data = {
        "description": theory['claim'],
        "theory_name": "ancient_mysteries",
        "title": theory['title'],
    }

    # Run proof engine
    verdict = engine.evaluate(
        finding_id=theory['id'],
        finding_data=finding_data,
        evidence=evidence,
        standard_name="scientific",
        tenant_id="ancient_mysteries"
    )

    result = {
        "theory_id": theory['id'],
        "title": theory['title'],
        "source": theory['source'],
        "claim": theory['claim'],
        "testable_prediction": theory.get('testable_prediction', ''),
        "expected_status": theory.get('status', 'unknown'),
        "proof_verdict": verdict.verdict,
        "overall_score": verdict.overall_score,
        "checklist_items": [
            {
                "item": item.description,
                "score": item.score,
                "weight": item.weight,
                "is_critical": item.is_critical,
                "justification": item.justification,
            }
            for item in verdict.checklist_items
        ],
        "research_directions": verdict.research_directions,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    results.append(result)
    print(f"{verdict.verdict} (score: {verdict.overall_score:.2f})")

# Save results
output_path = 'src/data/proof-engine-results-ancient-mysteries.json'
output = {
    "evaluation_run": {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "standard": "scientific",
        "model": "us.anthropic.claude-3-haiku-20240307-v1:0",
        "theories_evaluated": len(results),
    },
    "summary": {
        "proven": sum(1 for r in results if r['proof_verdict'] == 'PROVEN'),
        "unproven": sum(1 for r in results if r['proof_verdict'] == 'UNPROVEN'),
        "insufficient_evidence": sum(1 for r in results if r['proof_verdict'] == 'INSUFFICIENT_EVIDENCE'),
        "average_score": sum(r['overall_score'] for r in results) / len(results) if results else 0,
    },
    "results": sorted(results, key=lambda r: r['overall_score'], reverse=True),
}

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\nResults saved to: {output_path}")
print(f"\nSummary:")
print(f"  PROVEN: {output['summary']['proven']}")
print(f"  UNPROVEN: {output['summary']['unproven']}")
print(f"  INSUFFICIENT: {output['summary']['insufficient_evidence']}")
print(f"  Average score: {output['summary']['average_score']:.2f}")
print(f"\nTop theories by score:")
for r in output['results'][:5]:
    print(f"  {r['overall_score']:.2f} | {r['proof_verdict']:<25} | {r['title']}")
