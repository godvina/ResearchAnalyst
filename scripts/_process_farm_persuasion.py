"""Process Farm Dataset — Persuasion Misinformation Patterns.

Source: pillowsofwind/llms-believe-the-earth-is-flat (ACL 2024)
1,952 QA pairs with GPT-4-generated persuasive misinformation appeals

VALUE FOR OUR TAXONOMY:
The 3 persuasion strategies (logical, credibility, emotional) map directly to
how conspiracy theories spread. Each appeal is a concrete example of a
misinformation technique — these become PRECEDENT CASES under our signatures.

CROSS-DOMAIN SCORING (MANDATORY):
- Logical appeals → Information Asymmetry (selective facts presentation)
- Credibility appeals → Expert Divergence (fake authority invocation)
- Emotional appeals → Narrative Coherence (emotional framing over evidence)
- All conspiracy items → Evidence Suppression patterns

NEW TAXONOMY SIGNATURES DERIVED FROM THIS DATASET:
We extract persuasion technique patterns that can be added to the taxonomy
as detection signatures.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.proof_engine import ProofEngine


def load_farm_data():
    """Load all Farm dataset files."""
    base = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'flat-earth-farm-dataset' / 'src' / 'Farm_dataset'
    files = ['TruthfulQA.jsonl', 'Boolq.jsonl', 'NQ1.jsonl', 'NQ2.jsonl']
    
    all_items = []
    for fname in files:
        path = base / fname
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                item = json.loads(line)
                item['_source_file'] = fname
                all_items.append(item)
    
    return all_items


def extract_persuasion_techniques(items):
    """Extract and categorize persuasion techniques from the dataset.
    
    Returns taxonomy-relevant patterns.
    """
    techniques = {
        'logical': {'count': 0, 'samples': [], 'patterns': set()},
        'credibility': {'count': 0, 'samples': [], 'patterns': set()},
        'emotional': {'count': 0, 'samples': [], 'patterns': set()},
    }
    
    conspiracy_items = []
    
    for item in items:
        adv = item.get('adv', {})
        if not adv:
            continue
        
        category = item.get('category', 'general')
        question = item.get('question', '')
        target = adv.get('target', '')
        
        # Track conspiracy-specific items
        if category in ('Conspiracies', 'Paranormal', 'Misconceptions'):
            conspiracy_items.append({
                'question': question,
                'category': category,
                'target_misinformation': target,
                'logical_appeal': adv.get('logical', [''])[0][:300] if adv.get('logical') else '',
                'credibility_appeal': adv.get('credibility', [''])[0][:300] if adv.get('credibility') else '',
                'emotional_appeal': adv.get('emotional', [''])[0][:300] if adv.get('emotional') else '',
            })
        
        for technique in ['logical', 'credibility', 'emotional']:
            appeals = adv.get(technique, [])
            if appeals:
                techniques[technique]['count'] += len(appeals)
                if len(techniques[technique]['samples']) < 10:
                    techniques[technique]['samples'].append({
                        'question': question,
                        'target': target,
                        'appeal': appeals[0][:400],
                        'category': category,
                    })
    
    return techniques, conspiracy_items


def derive_taxonomy_signatures(techniques, conspiracy_items):
    """Derive new taxonomy signatures from persuasion patterns.
    
    These can be added to the taxonomy as detection signatures for
    misinformation spreading techniques.
    """
    new_signatures = [
        {
            'context_key': 'conspiracy/information_asymmetry/selective_presentation/logical_appeal_misinformation',
            'description': 'Use of logical-sounding arguments built on selective facts or false premises to make misinformation appear rational',
            'vector_text': 'logical argument selective facts false premise rational sounding misleading evidence cherry picked statistical manipulation',
            'indicators': [
                'Selective citation of real facts that support false conclusion',
                'Statistical manipulation (true numbers, misleading framing)',
                'False logical chain (A→B→C where B→C is unproven)',
                'Appeal to complexity (real enough to seem plausible)',
            ],
            'domain_mappings': ['conspiracy_theory', 'crime'],
            'derived_from': 'Farm dataset - logical appeals',
            'example_count': techniques['logical']['count'],
        },
        {
            'context_key': 'conspiracy/expert_divergence/false_authority/credibility_appeal_misinformation',
            'description': 'Invocation of fabricated or misrepresented expert authority to lend credibility to false claims',
            'vector_text': 'expert authority professor study research institution published credible source scientist university findings',
            'indicators': [
                'Citation of non-existent or misquoted studies',
                'Appeal to authority figure who did not make claimed statement',
                'Fabricated institutional affiliation',
                'Misrepresentation of consensus as dissent',
            ],
            'domain_mappings': ['conspiracy_theory', 'crime'],
            'derived_from': 'Farm dataset - credibility appeals',
            'example_count': techniques['credibility']['count'],
        },
        {
            'context_key': 'conspiracy/narrative_coherence/emotional_framing/emotional_appeal_misinformation',
            'description': 'Use of emotional narratives, fear, or urgency to bypass rational evaluation of false claims',
            'vector_text': 'emotional fear urgency personal story victim narrative outrage injustice cover-up urgent action needed',
            'indicators': [
                'Personal victim narrative presented as evidence',
                'Urgency language bypassing rational evaluation',
                'Fear-based framing of neutral information',
                'Outrage framing that discourages fact-checking',
            ],
            'domain_mappings': ['conspiracy_theory', 'crime', 'ancient_mysteries'],
            'derived_from': 'Farm dataset - emotional appeals',
            'example_count': techniques['emotional']['count'],
        },
        {
            'context_key': 'conspiracy/methodological_red_flags/persuasion_escalation/multi_turn_belief_manipulation',
            'description': 'Progressive escalation of persuasion through multiple conversational turns until resistance breaks',
            'vector_text': 'escalation progressive persuasion repeated questioning gradual belief shift persistent pressure multiple attempts',
            'indicators': [
                'Initial rejection followed by softened position',
                'Each turn introduces new angle on same false claim',
                'Technique switches between logical/credibility/emotional',
                'Social pressure or isolation implied for non-belief',
            ],
            'domain_mappings': ['conspiracy_theory', 'crime'],
            'derived_from': 'Farm dataset - multi-turn persuasion structure',
            'example_count': 1952,
        },
    ]
    
    return new_signatures


def run_proof_engine_on_conspiracy_items(conspiracy_items, bedrock):
    """Run proof engine on conspiracy-specific items from the dataset."""
    engine = ProofEngine(bedrock_client=bedrock)
    
    # Group by category and create testable claims
    claims = [
        {
            'theory_id': 'farm-001',
            'title': '9/11 Inside Job Claim',
            'claim': 'The 9/11 attacks were orchestrated by elements within the US government as a pretext for war',
            'evidence_from_dataset': [ci for ci in conspiracy_items if '9/11' in ci.get('question', '')][:3],
        },
        {
            'theory_id': 'farm-002',
            'title': 'Moon Landing Hoax',
            'claim': 'The Apollo moon landings were faked by NASA in a studio',
            'evidence_from_dataset': [ci for ci in conspiracy_items if 'moon' in ci.get('question', '').lower()][:3],
        },
        {
            'theory_id': 'farm-003',
            'title': 'Illuminati/Secret Society Control',
            'claim': 'A secret society (Illuminati, Freemasons) controls world governments and events',
            'evidence_from_dataset': [ci for ci in conspiracy_items if any(kw in ci.get('question', '').lower() for kw in ['illuminati', 'secret', 'freemason', 'world'])][:3],
        },
    ]
    
    results = []
    for claim in claims:
        evidence_text = "\n".join([
            f"Q: {e['question']}\nMisinformation target: {e['target_misinformation']}\nLogical appeal: {e.get('logical_appeal', '')[:200]}"
            for e in claim['evidence_from_dataset']
        ]) or "No specific evidence items found in dataset for this claim"
        
        finding_data = {
            'description': claim['claim'],
            'theory_name': claim['title'],
        }
        
        try:
            verdict = engine.evaluate(
                finding_id=claim['theory_id'],
                finding_data=finding_data,
                evidence=evidence_text,
                standard_name='intelligence',
                tenant_id='conspiracy_theories'
            )
            
            results.append({
                'theory_id': claim['theory_id'],
                'title': claim['title'],
                'claim': claim['claim'],
                'proof_verdict': verdict.verdict,
                'overall_score': verdict.overall_score,
                'checklist_items': [
                    {'item': i.description, 'score': i.score, 'weight': i.weight,
                     'is_critical': i.is_critical, 'justification': i.justification}
                    for i in verdict.checklist_items
                ],
                'research_directions': verdict.research_directions,
            })
            print(f"    {claim['title']}: {verdict.verdict} ({verdict.overall_score:.2f})")
        except Exception as e:
            print(f"    {claim['title']}: ERROR - {e}")
            results.append({'theory_id': claim['theory_id'], 'title': claim['title'], 'error': str(e)})
    
    return results


def main():
    import boto3
    
    print("=" * 70)
    print("FARM DATASET PROCESSING — Persuasion Misinformation Patterns")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Cross-Domain Scoring: ENABLED")
    print()
    
    # Load data
    items = load_farm_data()
    print(f"Loaded {len(items)} items from Farm dataset")
    
    # Extract persuasion techniques
    print("\nExtracting persuasion technique patterns...")
    techniques, conspiracy_items = extract_persuasion_techniques(items)
    
    print(f"  Logical appeals: {techniques['logical']['count']}")
    print(f"  Credibility appeals: {techniques['credibility']['count']}")
    print(f"  Emotional appeals: {techniques['emotional']['count']}")
    print(f"  Conspiracy-specific items: {len(conspiracy_items)}")
    
    # Derive new taxonomy signatures
    print("\nDeriving taxonomy signatures from persuasion patterns...")
    new_signatures = derive_taxonomy_signatures(techniques, conspiracy_items)
    print(f"  New signatures derived: {len(new_signatures)}")
    for sig in new_signatures:
        print(f"    • {sig['context_key'].split('/')[-1]}")
    
    # Run proof engine
    print("\nRunning Proof Engine on conspiracy items...")
    try:
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        proof_results = run_proof_engine_on_conspiracy_items(conspiracy_items, bedrock)
    except Exception as e:
        print(f"  Bedrock error: {e}")
        proof_results = []
    
    # Compile output
    output = {
        'evaluation_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'dataset': 'Farm (ACL 2024) - Persuasive Misinformation',
            'source': 'github.com/pillowsofwind/llms-believe-the-earth-is-flat',
            'total_items': len(items),
            'conspiracy_items': len(conspiracy_items),
            'cross_domain_scoring': True,
        },
        'persuasion_analysis': {
            'technique_counts': {k: v['count'] for k, v in techniques.items()},
            'technique_samples': {k: v['samples'][:5] for k, v in techniques.items()},
            'conspiracy_items_sample': conspiracy_items[:10],
        },
        'new_taxonomy_signatures': new_signatures,
        'proof_engine_results': proof_results,
        'taxonomy_learnings': {
            'key_insight': 'Persuasion techniques (logical/credibility/emotional) are DETECTION SIGNATURES for misinformation spreading patterns',
            'new_domains_suggested': [],
            'new_signatures_count': len(new_signatures),
            'integration_point': 'These signatures should be added to the conspiracy_theory domain under Information Asymmetry, Expert Divergence, and Narrative Coherence typologies',
            'precedent_cases_derived': len(conspiracy_items),
        },
    }
    
    out_path = PROJECT_ROOT / 'src' / 'data' / 'proof-engine-results-farm-persuasion.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY & TAXONOMY LEARNINGS")
    print("=" * 70)
    print(f"  Total items processed: {len(items)}")
    print(f"  Persuasion appeals analyzed: {sum(v['count'] for v in techniques.values())}")
    print(f"  New taxonomy signatures derived: {len(new_signatures)}")
    print(f"  Conspiracy items (precedent cases): {len(conspiracy_items)}")
    print()
    print("  NEW SIGNATURES TO ADD TO TAXONOMY:")
    for sig in new_signatures:
        name = sig['context_key'].split('/')[-1]
        domains = ', '.join(sig['domain_mappings'])
        print(f"    [{domains}] {name}")
        print(f"      {sig['description'][:80]}...")
    print()
    print(f"  Saved: {out_path}")


if __name__ == '__main__':
    main()
