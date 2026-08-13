"""Cross-Dataset Convergence Scan.

Finds patterns that repeat ACROSS different conspiracy theories.
This is the highest-value finding type — when the SAME structural pattern
appears in JFK, COVID, 9/11, RFK, and NWO independently.

Uses keyword + semantic overlap to identify cross-cutting claims.
"""
import json, sys, os
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_all_claims():
    """Load all processed claims from all datasets."""
    with open('src/frontend/theory-registry-data.js', 'r', encoding='utf-8') as f:
        content = f.read()
    return json.loads(content.split('const THEORY_DATA = ')[1].rstrip(';\n'))


def extract_themes(claim_text):
    """Extract thematic keywords from a claim."""
    text = claim_text.lower()
    themes = set()
    
    # Evidence suppression patterns
    if any(w in text for w in ['suppress', 'censor', 'withheld', 'classified', 'redact', 'hidden', 'blocked']):
        themes.add('EVIDENCE_SUPPRESSION')
    # Institutional coverup
    if any(w in text for w in ['cover', 'destroy', 'obstruct', 'refused', 'denied access']):
        themes.add('INSTITUTIONAL_COVERUP')
    # Funding/financial
    if any(w in text for w in ['fund', 'money', 'billion', 'payment', 'profit', 'financial', 'budget']):
        themes.add('FINANCIAL_MOTIVE')
    # Expert silencing
    if any(w in text for w in ['career', 'fired', 'retract', 'vilif', 'dissent', 'whistleblower', 'silence']):
        themes.add('EXPERT_SILENCING')
    # Regulatory capture
    if any(w in text for w in ['revolving door', 'conflict of interest', 'industry', 'regulator', 'fda', 'cdc']):
        themes.add('REGULATORY_CAPTURE')
    # Foreknowledge
    if any(w in text for w in ['foreknowledge', 'advance warning', 'predicted', 'simulation', 'before', 'prior']):
        themes.add('FOREKNOWLEDGE')
    # Media coordination
    if any(w in text for w in ['media', 'narrative', 'coordinated', 'talking points', 'corporation']):
        themes.add('MEDIA_COORDINATION')
    # Government lies
    if any(w in text for w in ['lied', 'denied', 'contradicted', 'false statement', 'congress']):
        themes.add('OFFICIAL_DECEPTION')
    # Investigation failure
    if any(w in text for w in ['underfunded', 'investigation', 'commission', 'not examined', 'ignored']):
        themes.add('INVESTIGATION_FAILURE')
    # Surveillance/control
    if any(w in text for w in ['surveillance', 'monitor', 'control', 'track', 'prism', 'nsa']):
        themes.add('SURVEILLANCE_CONTROL')
    # Pharmaceutical
    if any(w in text for w in ['pharma', 'vaccine', 'drug', 'trial', 'fda', 'adverse', 'safety']):
        themes.add('PHARMACEUTICAL')
    # Secret coordination
    if any(w in text for w in ['secret', 'bilderberg', 'bohemian', 'freemason', 'illuminate']):
        themes.add('SECRET_COORDINATION')
    
    return themes


def find_cross_dataset_patterns(claims):
    """Find themes that appear across multiple datasets."""
    theme_claims = defaultdict(list)
    
    for claim in claims:
        themes = extract_themes(claim.get('claim', '') + ' ' + claim.get('title', ''))
        for theme in themes:
            theme_claims[theme].append({
                'dataset': claim.get('dataset', ''),
                'claim': claim.get('claim', claim.get('title', '')),
                'score': claim.get('score', 0),
                'verdict': claim.get('verdict', ''),
            })
    
    # Find themes spanning 3+ datasets
    cross_cutting = {}
    for theme, items in theme_claims.items():
        datasets = set(i['dataset'] for i in items)
        if len(datasets) >= 3:
            cross_cutting[theme] = {
                'datasets': sorted(datasets),
                'dataset_count': len(datasets),
                'claim_count': len(items),
                'avg_score': sum(i['score'] for i in items) / len(items) if items else 0,
                'top_claims': sorted(items, key=lambda x: x['score'], reverse=True)[:5],
            }
    
    return cross_cutting


def main():
    claims = load_all_claims()
    print(f"Loaded {len(claims)} claims across {len(set(c.get('dataset','') for c in claims))} datasets\n")
    
    cross = find_cross_dataset_patterns(claims)
    
    print("=" * 70)
    print("CROSS-DATASET CONVERGENCE PATTERNS")
    print("(Themes appearing in 3+ independent conspiracy theories)")
    print("=" * 70)
    
    for theme, data in sorted(cross.items(), key=lambda x: -x[1]['dataset_count']):
        print(f"\n{'='*60}")
        print(f"  {theme} — spans {data['dataset_count']} datasets, {data['claim_count']} claims")
        print(f"  Datasets: {', '.join(data['datasets'])}")
        print(f"  Average confidence: {data['avg_score']*100:.0f}%")
        print(f"  Top claims:")
        for c in data['top_claims'][:3]:
            print(f"    [{c['dataset']:20s}] {c['score']*100:.0f}% — {c['claim'][:80]}")
    
    # Most interesting: themes with HIGH scores across MANY datasets
    print(f"\n\n{'='*70}")
    print("🔥 MOST INTERESTING: High confidence + Multiple datasets")
    print("{'='*70}")
    hot = sorted(cross.items(), key=lambda x: x[1]['avg_score'] * x[1]['dataset_count'], reverse=True)
    for theme, data in hot[:5]:
        print(f"\n  🔥 {theme}")
        print(f"     Spans: {data['dataset_count']} theories | Confidence: {data['avg_score']*100:.0f}% | Claims: {data['claim_count']}")
        print(f"     WHY THIS MATTERS: The same pattern independently appears in:")
        for c in data['top_claims'][:4]:
            print(f"       • [{c['dataset']}] {c['claim'][:70]}")
    
    # Save
    output = {
        'scan_type': 'cross_dataset_convergence',
        'total_claims': len(claims),
        'total_datasets': len(set(c.get('dataset','') for c in claims)),
        'patterns_found': len(cross),
        'patterns': {k: {**v, 'top_claims': v['top_claims'][:5]} for k, v in cross.items()},
    }
    with open('src/data/cross-dataset-convergence-scan.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n\nSaved: src/data/cross-dataset-convergence-scan.json")


if __name__ == '__main__':
    main()
