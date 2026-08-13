"""Run Documentary Methodology Evaluation.

Evaluates all theories against the 'journalistic' standard which implements
the Documentary Research Stack (Hook → Established Facts → Anomaly → Pattern → Implication).

This is the investigative journalist taxonomy layer that sits alongside the
scientific/intelligence proof standards — it evaluates whether a theory is
DOCUMENTARY-READY (has enough structured evidence for a compelling investigation)
rather than whether it's scientifically proven.

The journalistic checklist items map directly to the Documentary Research Format
(docs/best-practices-documentary-research-format.md):
  1. Hook identified → Layer 1: THE HOOK
  2. Established facts documented → Layer 2: THE ESTABLISHED FACTS  
  3. Anomaly is measurable → Layer 3: THE ANOMALY
  4. Pattern demonstrated → Layer 4: THE PATTERN
  5. Implication stated → Layer 5: THE IMPLICATION
  6. Three-source rule → Documentary Credibility Framework
  7. Counter-argument addressed → The "Skeptic Paragraph"
  8. Expert sources identified → The "Expert Talking Head" Rule
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.proof_engine import ProofEngine


def load_theories():
    """Load all theories from ancient mysteries results."""
    path = PROJECT_ROOT / 'src' / 'data' / 'proof-engine-results-ancient-mysteries.json'
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['results']


def main():
    import boto3

    print("=" * 70)
    print("DOCUMENTARY METHODOLOGY EVALUATION")
    print("Standard: journalistic (Hook → Facts → Anomaly → Pattern → Implication)")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()

    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    engine = ProofEngine(bedrock_client=bedrock)
    print("Connected to Bedrock (Claude 3 Haiku)")

    # Load theories
    theories = load_theories()
    print(f"Evaluating {len(theories)} theories against documentary standard\n")

    results = []
    for theory in theories:
        title = theory['title']
        print(f"  Evaluating: {title}...")

        # Build evidence context from what we know
        evidence_parts = [
            f"Claim: {theory.get('claim', '')}",
            f"Testable prediction: {theory.get('testable_prediction', '')}",
            f"Source: {theory.get('source', '')}",
        ]
        # Add checklist justifications from scientific evaluation as evidence
        for item in theory.get('checklist_items', []):
            if item.get('justification'):
                evidence_parts.append(f"Scientific evaluation: {item['justification']}")
        # Add research directions
        for rd in theory.get('research_directions', []):
            evidence_parts.append(f"Research direction: {rd}")

        evidence = "\n".join(evidence_parts)

        finding_data = {
            'description': theory.get('claim', title),
            'theory_name': title,
        }

        verdict = engine.evaluate(
            finding_id=theory['theory_id'],
            finding_data=finding_data,
            evidence=evidence,
            standard_name='journalistic',
            tenant_id='ancient_mysteries'
        )

        result = {
            'theory_id': theory['theory_id'],
            'title': title,
            'source': theory.get('source', ''),
            'scientific_verdict': theory.get('proof_verdict', ''),
            'scientific_score': theory.get('overall_score', 0),
            'documentary_verdict': verdict.verdict,
            'documentary_score': verdict.overall_score,
            'documentary_checklist': [
                {
                    'item': item.description,
                    'score': item.score,
                    'weight': item.weight,
                    'is_critical': item.is_critical,
                    'justification': item.justification,
                }
                for item in verdict.checklist_items
            ],
            'documentary_research_directions': verdict.research_directions,
        }
        results.append(result)

        status = "✓" if verdict.verdict == "PROVEN" else "△" if verdict.verdict == "INSUFFICIENT_EVIDENCE" else "✗"
        print(f"    {status} {verdict.verdict} ({verdict.overall_score:.2f})")

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS: Scientific vs Documentary Assessment")
    print("=" * 70)
    print(f"{'Theory':<45} {'Scientific':<15} {'Documentary':<15}")
    print("-" * 75)
    for r in sorted(results, key=lambda x: x['documentary_score'], reverse=True):
        t = r['title'][:44]
        sci = f"{r['scientific_score']:.2f} {r['scientific_verdict'][:4]}"
        doc = f"{r['documentary_score']:.2f} {r['documentary_verdict'][:4]}"
        print(f"  {t:<43} {sci:<13} {doc:<13}")

    # Save
    output = {
        'evaluation_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'standard': 'journalistic',
            'model': 'us.anthropic.claude-3-haiku-20240307-v1:0',
            'description': 'Documentary methodology evaluation (Hook/Facts/Anomaly/Pattern/Implication)',
            'theories_evaluated': len(results),
        },
        'summary': {
            'documentary_ready': sum(1 for r in results if r['documentary_verdict'] == 'PROVEN'),
            'needs_work': sum(1 for r in results if r['documentary_verdict'] == 'INSUFFICIENT_EVIDENCE'),
            'not_ready': sum(1 for r in results if r['documentary_verdict'] == 'UNPROVEN'),
        },
        'results': results,
    }

    out_path = PROJECT_ROOT / 'src' / 'data' / 'proof-engine-results-documentary-methodology.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}")

    # Key insight
    print("\n" + "=" * 70)
    print("KEY INSIGHT: Scientific proof ≠ Documentary readiness")
    print("=" * 70)
    print("A theory can be UNPROVEN scientifically but still be")
    print("DOCUMENTARY-READY (has hook, anomaly, pattern, experts on both sides).")
    print("This is exactly what makes it good television/investigation material.")


if __name__ == '__main__':
    main()
