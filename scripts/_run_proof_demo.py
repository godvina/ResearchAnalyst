"""Run Proof Engine demo against seed theories with live Bedrock.

Evaluates Ancient Alien theories against the scientific standard,
producing real AI-scored verdicts for each theory.
"""
import json
import os
import sys
import boto3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.services.proof_engine import ProofEngine

# Connect to Bedrock
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
engine = ProofEngine(bedrock_client=bedrock)

# Load seed theories
with open('src/data/conspiracy-seed/ancient_mysteries_theories/ancient_alien_theories.json', 'r') as f:
    data = json.load(f)

theories = data['theories']
print(f"{'='*70}")
print(f"PROOF ENGINE DEMO — {len(theories)} Ancient Mystery Theories")
print(f"Standard: SCIENTIFIC (falsifiable hypothesis, statistical significance,")
print(f"          replication, peer critique, alternative elimination)")
print(f"{'='*70}\n")

results = []

for theory in theories:
    print(f"\n{'─'*70}")
    print(f"THEORY: {theory['title']}")
    print(f"Source: {theory['source']}")
    print(f"{'─'*70}")

    # Build evidence string from for/against
    evidence_parts = []
    evidence_parts.append("EVIDENCE SUPPORTING THE CLAIM:")
    for e in theory.get('current_evidence_for', []):
        evidence_parts.append(f"  + {e}")
    evidence_parts.append("\nEVIDENCE AGAINST THE CLAIM:")
    for e in theory.get('current_evidence_against', []):
        evidence_parts.append(f"  - {e}")
    evidence_parts.append(f"\nTESTABLE PREDICTION: {theory.get('testable_prediction', 'None stated')}")
    evidence = "\n".join(evidence_parts)

    finding_data = {
        "description": theory['claim'],
        "theory_name": "ancient_mysteries",
        "title": theory['title'],
    }

    # Run the proof engine
    verdict = engine.evaluate(
        finding_id=theory['id'],
        finding_data=finding_data,
        evidence=evidence,
        standard_name="scientific",
        tenant_id="ancient_mysteries"
    )

    # Display results
    print(f"\n  Checklist:")
    for item in verdict.checklist_items:
        icon = "✅" if item.score >= 1.0 else ("🟡" if item.score >= 0.5 else "❌")
        critical = " [CRITICAL]" if item.is_critical else ""
        print(f"    {icon} {item.description}{critical} — score: {item.score}")
        if item.justification:
            print(f"       └─ {item.justification[:120]}")

    print(f"\n  Overall Score: {verdict.overall_score:.2f} / 0.70 threshold")
    print(f"  ┌─────────────────────────────────────┐")
    print(f"  │  VERDICT: {verdict.verdict:^25} │")
    print(f"  └─────────────────────────────────────┘")

    if verdict.research_directions:
        print(f"\n  Research Directions:")
        for rd in verdict.research_directions[:3]:
            print(f"    → {rd[:100]}")

    results.append({
        "id": theory['id'],
        "title": theory['title'],
        "verdict": verdict.verdict,
        "score": verdict.overall_score,
        "expected": theory.get('status', 'unknown'),
    })

# Summary
print(f"\n\n{'='*70}")
print(f"SUMMARY — All {len(results)} Theories Evaluated")
print(f"{'='*70}")
print(f"\n{'Theory':<45} {'Verdict':<25} {'Score':<8} {'Expected'}")
print(f"{'─'*45} {'─'*25} {'─'*8} {'─'*20}")
for r in sorted(results, key=lambda x: x['score'], reverse=True):
    print(f"{r['title'][:44]:<45} {r['verdict']:<25} {r['score']:.2f}    {r['expected']}")

proven = sum(1 for r in results if r['verdict'] == 'PROVEN')
unproven = sum(1 for r in results if r['verdict'] == 'UNPROVEN')
insufficient = sum(1 for r in results if r['verdict'] == 'INSUFFICIENT_EVIDENCE')
print(f"\nPROVEN: {proven} | UNPROVEN: {unproven} | INSUFFICIENT: {insufficient}")
