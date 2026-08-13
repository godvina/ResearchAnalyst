"""Run Proof Engine on Flat Earth — Both Sides.

Evaluates:
1. PRO flat earth claims (should score UNPROVEN against scientific standard)
2. ANTI flat earth rebuttals (should score higher — evidence contradicts FE)

This demonstrates the Proof Engine works correctly on a known-wrong theory.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.proof_engine import ProofEngine


def main():
    import boto3

    print("=" * 70)
    print("FLAT EARTH — DUAL-DIRECTION PROOF ENGINE EVALUATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()

    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    engine = ProofEngine(bedrock_client=bedrock)
    print("Connected to Bedrock")

    # Load the comprehensive dataset
    ds_path = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'flat_earth_evidence' / 'flat_earth_comprehensive_dataset.json'
    with open(ds_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    claims = dataset['structured_claims']
    scraped = dataset['scraped_evidence_pages']

    # Build evidence context from scraped pages
    scraped_evidence = "\n\n".join([
        f"[{p['title']}]: {p['content'][:1000]}"
        for p in scraped[:5]
    ])

    # Also load wiki data
    wiki_path = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'flat_earth_evidence' / 'wiki_tfes_pages.json'
    wiki_evidence = ""
    if wiki_path.exists():
        with open(wiki_path, 'r', encoding='utf-8') as f:
            wiki_pages = json.load(f)
        wiki_evidence = "\n\n".join([f"[FES Wiki - {p['id']}]: {p['content'][:800]}" for p in wiki_pages[:3]])

    print(f"Loaded {len(claims)} structured claims")
    print(f"Scraped evidence: {len(scraped_evidence)} chars")
    print(f"Wiki evidence: {len(wiki_evidence)} chars")

    # DIRECTION 1: Evaluate PRO flat earth claims (as if they're findings to prove)
    print("\n" + "=" * 70)
    print("DIRECTION 1: CAN FLAT EARTH BE PROVEN? (Scientific Standard)")
    print("=" * 70)

    pro_results = []
    for claim in claims:
        print(f"  {claim['title']}...")
        
        # Use their own evidence (pro argument + scraped content)
        pro_evidence = f"""
FLAT EARTH CLAIM: {claim['pro_argument']}

SUPPORTING EVIDENCE FROM FLAT EARTH SOURCES:
{scraped_evidence[:2000]}

{wiki_evidence[:1000]}
"""
        finding_data = {
            'description': claim['pro_argument'],
            'theory_name': f"Flat Earth: {claim['title']}",
        }

        verdict = engine.evaluate(
            finding_id=claim['claim_id'],
            finding_data=finding_data,
            evidence=pro_evidence,
            standard_name='scientific',
            tenant_id='conspiracy_theories'
        )

        pro_results.append({
            'claim_id': claim['claim_id'],
            'title': claim['title'],
            'category': claim['category'],
            'direction': 'PRO_FLAT_EARTH',
            'proof_verdict': verdict.verdict,
            'overall_score': verdict.overall_score,
            'checklist_items': [
                {'item': i.description, 'score': i.score, 'weight': i.weight,
                 'is_critical': i.is_critical, 'justification': i.justification}
                for i in verdict.checklist_items
            ],
            'research_directions': verdict.research_directions,
        })
        print(f"    → {verdict.verdict} ({verdict.overall_score:.2f})")

    # DIRECTION 2: Evaluate the ANTI flat earth position (globe is proven)
    print("\n" + "=" * 70)
    print("DIRECTION 2: IS FLAT EARTH DISPROVEN? (Scientific Standard)")
    print("=" * 70)

    anti_results = []
    for claim in claims:
        print(f"  Rebutting: {claim['title']}...")

        # Use scientific rebuttal evidence
        anti_evidence = f"""
CLAIM BEING TESTED: "{claim['pro_argument']}"

SCIENTIFIC REBUTTAL:
{claim['scientific_rebuttal']}

KEY EVIDENCE THAT DISPROVES THIS CLAIM:
{claim['key_evidence_needed']}

The scientific consensus, supported by independent measurements from thousands of observers, GPS satellites, ISS observations, multiple space agencies, and amateur astronomers, confirms the Earth is an oblate spheroid.
"""
        finding_data = {
            'description': f"The flat earth claim '{claim['title']}' is DISPROVEN by scientific evidence",
            'theory_name': f"Globe Rebuttal: {claim['title']}",
        }

        verdict = engine.evaluate(
            finding_id=f"{claim['claim_id']}-anti",
            finding_data=finding_data,
            evidence=anti_evidence,
            standard_name='scientific',
            tenant_id='conspiracy_theories'
        )

        anti_results.append({
            'claim_id': f"{claim['claim_id']}-anti",
            'title': f"REBUTTAL: {claim['title']}",
            'category': claim['category'],
            'direction': 'ANTI_FLAT_EARTH',
            'proof_verdict': verdict.verdict,
            'overall_score': verdict.overall_score,
            'checklist_items': [
                {'item': i.description, 'score': i.score, 'weight': i.weight,
                 'is_critical': i.is_critical, 'justification': i.justification}
                for i in verdict.checklist_items
            ],
            'research_directions': verdict.research_directions,
        })
        print(f"    → {verdict.verdict} ({verdict.overall_score:.2f})")

    # Compile and save
    output = {
        'evaluation_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'standard': 'scientific',
            'model': 'us.anthropic.claude-3-haiku-20240307-v1:0',
            'claims_evaluated': len(claims),
            'directions': ['PRO_FLAT_EARTH', 'ANTI_FLAT_EARTH'],
            'data_sources': ['flattruths.com', 'wiki.tfes.org', 'r/flatearth', 'structured rebuttals'],
        },
        'summary': {
            'pro_flat_earth': {
                'proven': sum(1 for r in pro_results if r['proof_verdict'] == 'PROVEN'),
                'unproven': sum(1 for r in pro_results if r['proof_verdict'] == 'UNPROVEN'),
                'insufficient': sum(1 for r in pro_results if r['proof_verdict'] == 'INSUFFICIENT_EVIDENCE'),
                'avg_score': sum(r['overall_score'] for r in pro_results) / len(pro_results) if pro_results else 0,
            },
            'anti_flat_earth': {
                'proven': sum(1 for r in anti_results if r['proof_verdict'] == 'PROVEN'),
                'unproven': sum(1 for r in anti_results if r['proof_verdict'] == 'UNPROVEN'),
                'insufficient': sum(1 for r in anti_results if r['proof_verdict'] == 'INSUFFICIENT_EVIDENCE'),
                'avg_score': sum(r['overall_score'] for r in anti_results) / len(anti_results) if anti_results else 0,
            },
            'engine_working_correctly': 'YES' if (
                sum(r['overall_score'] for r in anti_results) > sum(r['overall_score'] for r in pro_results)
            ) else 'NEEDS REVIEW',
        },
        'pro_results': pro_results,
        'anti_results': anti_results,
    }

    out_path = PROJECT_ROOT / 'src' / 'data' / 'proof-engine-results-flat-earth-dual.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL RESULTS — PROOF ENGINE VALIDATION")
    print("=" * 70)
    s = output['summary']
    print(f"\n  PRO Flat Earth (trying to prove it's flat):")
    print(f"    Proven: {s['pro_flat_earth']['proven']} | Unproven: {s['pro_flat_earth']['unproven']} | Insufficient: {s['pro_flat_earth']['insufficient']}")
    print(f"    Average score: {s['pro_flat_earth']['avg_score']:.2f}")
    print(f"\n  ANTI Flat Earth (proving it's a globe):")
    print(f"    Proven: {s['anti_flat_earth']['proven']} | Unproven: {s['anti_flat_earth']['unproven']} | Insufficient: {s['anti_flat_earth']['insufficient']}")
    print(f"    Average score: {s['anti_flat_earth']['avg_score']:.2f}")
    print(f"\n  ENGINE VALIDATION: {s['engine_working_correctly']}")
    print(f"  (Anti scores should be HIGHER than Pro scores)")
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
