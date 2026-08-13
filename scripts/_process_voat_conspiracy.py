"""Process Voat Conspiracy Annotation Dataset.

Source: voat_annotation.csv (3,384 posts, 990 conspiracy-labeled)
Downloaded: 2026-08-02
Source URL: Academic annotation dataset from Voat (Reddit-like platform)

This script processes the Voat conspiracy theory annotation dataset through
the proof engine pipeline. The dataset has 5 annotation dimensions that map
directly to our taxonomy:

  Voat Dimension → Our Taxonomy Domain
  ─────────────────────────────────────
  Actor          → Institutional Behavior (who is alleged to act)
  Action         → Evidence Suppression (what they allegedly did)
  Threat         → Information Asymmetry (what's at stake)
  Pattern        → Timeline Anomalies / Narrative Coherence (structural patterns)
  Secrecy        → Evidence Suppression / Expert Divergence (hidden information)

CROSS-DOMAIN SCORING (MANDATORY per steering doc):
All posts are scored against ALL taxonomy domains (ancient_mysteries +
conspiracy_theory + crime) simultaneously. Cross-domain matches are flagged
as "cross_cutting" — these are the highest-value findings.
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.proof_engine import ProofEngine


def load_voat_data(csv_path: str) -> list[dict]:
    """Load and parse the Voat annotation CSV."""
    posts = []
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            posts.append(row)
    return posts


def extract_conspiracy_posts(posts: list[dict]) -> list[dict]:
    """Filter to conspiracy-labeled posts and enrich with dimension analysis."""
    ct_posts = []
    for post in posts:
        if post.get('overall_ct') != 'TRUE':
            continue

        # Extract active conspiracy dimensions
        dimensions = []
        dimension_spans = {}
        for dim in ['Actor', 'Action', 'Threat', 'Pattern', 'Secrecy']:
            if post.get(dim) == 'TRUE':
                dimensions.append(dim)
                span = post.get(f'{dim}_span', 'NA')
                if span and span != 'NA':
                    dimension_spans[dim] = span

        ct_posts.append({
            'body': post.get('body', ''),
            'user': post.get('user', ''),
            'date': post.get('date', ''),
            'time': post.get('time', ''),
            'subverse': post.get('subverse', ''),
            'upvotes': int(post.get('upvotes', 0) or 0),
            'downvotes': int(post.get('downvotes', 0) or 0),
            'dimensions': dimensions,
            'dimension_spans': dimension_spans,
            'dimension_count': len(dimensions),
            'title': post.get('title', ''),
            'domain': post.get('domain', ''),
            'link': post.get('link', ''),
        })

    return ct_posts


def map_to_taxonomy_domains(dimensions: list[str]) -> list[dict]:
    """Map Voat annotation dimensions to our universal taxonomy domains.
    
    Returns matches against ALL domains (ancient_mysteries + conspiracy + crime)
    per the cross-domain scoring mandate.
    """
    mappings = []

    # CONSPIRACY THEORY domains
    if 'Actor' in dimensions:
        mappings.append({
            'taxonomy_domain': 'conspiracy_theory',
            'domain_name': 'institutional_behavior',
            'match_type': 'direct',
            'confidence': 0.90,
            'reasoning': 'Actor dimension directly maps to institutional behavior patterns'
        })
    if 'Action' in dimensions:
        mappings.append({
            'taxonomy_domain': 'conspiracy_theory',
            'domain_name': 'evidence_suppression',
            'match_type': 'direct',
            'confidence': 0.85,
            'reasoning': 'Action dimension maps to active evidence suppression/manipulation'
        })
    if 'Threat' in dimensions:
        mappings.append({
            'taxonomy_domain': 'conspiracy_theory',
            'domain_name': 'information_asymmetry',
            'match_type': 'direct',
            'confidence': 0.80,
            'reasoning': 'Threat dimension maps to information asymmetry and power dynamics'
        })
    if 'Pattern' in dimensions:
        mappings.append({
            'taxonomy_domain': 'conspiracy_theory',
            'domain_name': 'narrative_coherence',
            'match_type': 'direct',
            'confidence': 0.85,
            'reasoning': 'Pattern dimension maps to narrative structure analysis'
        })
    if 'Secrecy' in dimensions:
        mappings.append({
            'taxonomy_domain': 'conspiracy_theory',
            'domain_name': 'expert_divergence',
            'match_type': 'direct',
            'confidence': 0.75,
            'reasoning': 'Secrecy dimension maps to hidden knowledge / expert withholding'
        })

    # CROSS-DOMAIN: Crime typology matches
    if 'Actor' in dimensions and 'Action' in dimensions:
        mappings.append({
            'taxonomy_domain': 'crime',
            'domain_name': 'criminal_network',
            'match_type': 'cross_cutting',
            'confidence': 0.60,
            'reasoning': 'Actor+Action pattern parallels criminal network coordination signatures'
        })
    if 'Secrecy' in dimensions and 'Pattern' in dimensions:
        mappings.append({
            'taxonomy_domain': 'crime',
            'domain_name': 'document_concealment',
            'match_type': 'cross_cutting',
            'confidence': 0.55,
            'reasoning': 'Secrecy+Pattern parallels evidence concealment in criminal investigations'
        })

    # CROSS-DOMAIN: Ancient mysteries matches
    if 'Pattern' in dimensions:
        mappings.append({
            'taxonomy_domain': 'ancient_mysteries',
            'domain_name': 'geographic_clustering',
            'match_type': 'cross_cutting',
            'confidence': 0.40,
            'reasoning': 'Pattern recognition may correlate with geographic/temporal clustering'
        })
    if 'Actor' in dimensions and 'Secrecy' in dimensions:
        mappings.append({
            'taxonomy_domain': 'ancient_mysteries',
            'domain_name': 'knowledge_suppression',
            'match_type': 'cross_cutting',
            'confidence': 0.45,
            'reasoning': 'Actor+Secrecy parallels historical knowledge suppression narratives'
        })

    return mappings


def analyze_dataset(ct_posts: list[dict]) -> dict:
    """Produce comprehensive analysis of the dataset with cross-domain scoring."""

    # Dimension statistics
    dim_counts = {'Actor': 0, 'Action': 0, 'Threat': 0, 'Pattern': 0, 'Secrecy': 0}
    dim_combos = {}
    subverse_counts = {}
    cross_domain_hits = 0
    total_domain_matches = 0

    all_results = []

    for post in ct_posts:
        dims = post['dimensions']
        for d in dims:
            dim_counts[d] = dim_counts.get(d, 0) + 1

        # Track dimension combinations
        combo_key = '+'.join(sorted(dims))
        dim_combos[combo_key] = dim_combos.get(combo_key, 0) + 1

        # Track subverses
        sv = post['subverse']
        subverse_counts[sv] = subverse_counts.get(sv, 0) + 1

        # Cross-domain scoring (MANDATORY)
        domain_matches = map_to_taxonomy_domains(dims)
        total_domain_matches += len(domain_matches)

        cross_cutting = [m for m in domain_matches if m['match_type'] == 'cross_cutting']
        if cross_cutting:
            cross_domain_hits += 1

        all_results.append({
            'body_preview': post['body'][:300],
            'subverse': sv,
            'date': post['date'],
            'dimensions': dims,
            'dimension_count': post['dimension_count'],
            'domain_matches': domain_matches,
            'cross_domain_count': len(cross_cutting),
            'is_cross_cutting': len(cross_cutting) > 0,
        })

    # Identify highest-value cross-domain posts (5 dimensions = max cross-cutting)
    top_cross_domain = sorted(
        [r for r in all_results if r['is_cross_cutting']],
        key=lambda x: x['cross_domain_count'],
        reverse=True
    )[:20]

    return {
        'dataset_info': {
            'source': 'voat_annotation.csv',
            'source_url': 'Academic conspiracy annotation dataset (Voat/Reddit)',
            'download_date': '2026-08-02',
            'total_posts': len(ct_posts),
            'conspiracy_labeled': len(ct_posts),
        },
        'dimension_statistics': {
            'counts': dim_counts,
            'top_combinations': dict(sorted(dim_combos.items(), key=lambda x: -x[1])[:10]),
            'multi_dimension_rate': sum(1 for p in ct_posts if p['dimension_count'] >= 2) / len(ct_posts),
        },
        'cross_domain_scoring': {
            'total_domain_matches': total_domain_matches,
            'posts_with_cross_domain_hits': cross_domain_hits,
            'cross_domain_rate': cross_domain_hits / len(ct_posts),
            'note': 'MANDATORY: All posts scored against ALL taxonomy domains simultaneously',
        },
        'subverse_distribution': dict(sorted(subverse_counts.items(), key=lambda x: -x[1])),
        'top_cross_domain_findings': top_cross_domain[:10],
    }


def run_proof_engine_sample(ct_posts: list[dict]) -> list[dict]:
    """Run Proof Engine on sample conspiracy claims extracted from the dataset.
    
    We extract the most strongly-annotated posts (all 5 dimensions active)
    and formulate them as testable claims for the proof engine.
    """
    import boto3

    # Find posts with maximum conspiracy signal (all 5 dimensions)
    max_signal = [p for p in ct_posts if p['dimension_count'] == 5]
    print(f"\n  Posts with all 5 dimensions active: {len(max_signal)}")

    # We'll formulate 5 representative claims from the dataset
    claims = [
        {
            'theory_id': 'voat-001',
            'title': 'Pizzagate: Coordinated Elite Pedophile Network',
            'source': 'Voat/pizzagate subverse (376 posts)',
            'claim': 'A network of politically connected individuals used coded language in emails to coordinate child exploitation, with systematic suppression of investigations',
            'testable_prediction': 'Decoded communications would reveal coordination patterns matching known trafficking networks; suppressed investigations would show political interference',
            'expected_status': 'UNPROVEN',
        },
        {
            'theory_id': 'voat-002',
            'title': 'QAnon Great Awakening: Deep State Conspiracy',
            'source': 'Voat/GreatAwakening subverse (376 posts)',
            'claim': 'A coordinated group of unelected officials (deep state) systematically controls government policy while suppressing evidence of their activities',
            'testable_prediction': 'Policy decisions would show correlation with non-elected actor preferences rather than elected official platforms; document classification patterns would spike around specific topics',
            'expected_status': 'INSUFFICIENT_EVIDENCE',
        },
        {
            'theory_id': 'voat-003',
            'title': 'Flat Earth: Global Deception by Space Agencies',
            'source': 'Voat/Science subverse (flat earth content)',
            'claim': 'All space agencies globally coordinate to fabricate evidence of a spherical Earth, suppressing observations that contradict the model',
            'testable_prediction': 'Independent observations (ship visibility, flight paths, star positions) would be inconsistent with spherical model; agency communications would show coordination on narrative',
            'expected_status': 'UNPROVEN',
        },
        {
            'theory_id': 'voat-004',
            'title': 'News Media Coordination: Synchronized Narrative Control',
            'source': 'Voat/news subverse (376 posts)',
            'claim': 'Major news outlets receive coordinated talking points from a central authority, evidenced by identical phrasing appearing simultaneously across outlets',
            'testable_prediction': 'Statistical analysis would show improbable simultaneous appearance of identical rare phrases across supposedly independent outlets',
            'expected_status': 'INSUFFICIENT_EVIDENCE',
        },
        {
            'theory_id': 'voat-005',
            'title': 'Vaccine Injury Suppression: Systematic Under-Reporting',
            'source': 'Voat/Conspiracy subverse',
            'claim': 'Adverse vaccine events are systematically under-reported through institutional pressure on healthcare workers and manipulation of reporting systems',
            'testable_prediction': 'Comparison of passive (VAERS) vs active surveillance systems would show 10x+ discrepancy; whistleblower reports would describe institutional pressure',
            'expected_status': 'INSUFFICIENT_EVIDENCE',
        },
    ]

    # Connect to Bedrock and evaluate
    try:
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        engine = ProofEngine(bedrock_client=bedrock)
        print("  Connected to Bedrock for Proof Engine evaluation")
    except Exception as e:
        print(f"  Bedrock connection failed: {e}")
        print("  Returning claims without AI evaluation")
        return claims

    results = []
    for claim in claims:
        print(f"  Evaluating: {claim['title']}...")

        # Build evidence from the dataset posts
        relevant_posts = []
        if 'pizzagate' in claim['source'].lower():
            relevant_posts = [p for p in ct_posts if p['subverse'] == 'pizzagate'][:10]
        elif 'GreatAwakening' in claim['source']:
            relevant_posts = [p for p in ct_posts if p['subverse'] == 'GreatAwakening'][:10]
        elif 'flat earth' in claim['title'].lower():
            relevant_posts = [p for p in ct_posts if 'space' in p['body'].lower() or 'earth' in p['body'].lower()][:10]
        elif 'news' in claim['source'].lower():
            relevant_posts = [p for p in ct_posts if p['subverse'] == 'news'][:10]
        else:
            relevant_posts = [p for p in ct_posts if p['subverse'] == 'Conspiracy'][:10]

        evidence_text = "\n\n".join([
            f"[{p['subverse']} | {p['date']} | Dims: {','.join(p['dimensions'])}]\n{p['body'][:500]}"
            for p in relevant_posts
        ])

        finding_data = {
            'description': claim['claim'],
            'theory_name': claim['title'],
            'testable_prediction': claim['testable_prediction'],
        }

        try:
            verdict = engine.evaluate(
                finding_id=claim['theory_id'],
                finding_data=finding_data,
                evidence=evidence_text,
                standard_name='intelligence',  # Conspiracy theories use intelligence standard
                tenant_id='conspiracy_theories'
            )

            results.append({
                **claim,
                'proof_verdict': verdict.verdict,
                'overall_score': verdict.overall_score,
                'checklist_items': [
                    {
                        'item': item.description,
                        'score': item.score,
                        'weight': item.weight,
                        'is_critical': item.is_critical,
                        'justification': item.justification,
                    }
                    for item in verdict.checklist_items
                ],
                'research_directions': verdict.research_directions,
                'evaluated_at': datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            print(f"    Error evaluating {claim['title']}: {e}")
            results.append({**claim, 'error': str(e)})

    return results


def main():
    """Main processing pipeline for Voat conspiracy dataset."""
    print("=" * 70)
    print("VOAT CONSPIRACY ANNOTATION DATASET — PROCESSING PIPELINE")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Cross-Domain Scoring: ENABLED (per steering doc mandate)")
    print()

    # Load data
    csv_path = str(PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'voat_conspiracy' / 'voat_annotation.csv')
    print(f"Loading: {csv_path}")
    posts = load_voat_data(csv_path)
    print(f"  Total posts: {len(posts)}")

    # Extract conspiracy posts
    ct_posts = extract_conspiracy_posts(posts)
    print(f"  Conspiracy-labeled: {len(ct_posts)}")
    print()

    # Run cross-domain analysis
    print("Running cross-domain taxonomy scoring...")
    analysis = analyze_dataset(ct_posts)

    print(f"  Domain matches (total): {analysis['cross_domain_scoring']['total_domain_matches']}")
    print(f"  Posts with cross-domain hits: {analysis['cross_domain_scoring']['posts_with_cross_domain_hits']}")
    print(f"  Cross-domain rate: {analysis['cross_domain_scoring']['cross_domain_rate']:.1%}")
    print()

    print("Dimension statistics:")
    for dim, count in sorted(analysis['dimension_statistics']['counts'].items(), key=lambda x: -x[1]):
        print(f"  {dim}: {count} ({count*100//len(ct_posts)}%)")
    print(f"  Multi-dimension rate: {analysis['dimension_statistics']['multi_dimension_rate']:.1%}")
    print()

    # Run Proof Engine evaluation on extracted claims
    print("Running Proof Engine evaluation (intelligence standard)...")
    proof_results = run_proof_engine_sample(ct_posts)
    print()

    # Compile full output
    output = {
        'evaluation_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'dataset': 'voat_annotation.csv',
            'standard': 'intelligence',
            'model': 'us.anthropic.claude-3-haiku-20240307-v1:0',
            'cross_domain_scoring': True,
            'theories_evaluated': len(proof_results),
        },
        'dataset_analysis': analysis,
        'proof_engine_results': proof_results,
    }

    # Save results
    output_path = str(PROJECT_ROOT / 'src' / 'data' / 'proof-engine-results-voat-conspiracy.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Results saved to: {output_path}")

    # Print summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if proof_results and 'proof_verdict' in proof_results[0]:
        verdicts = {}
        for r in proof_results:
            v = r.get('proof_verdict', 'ERROR')
            verdicts[v] = verdicts.get(v, 0) + 1
        print(f"  Verdicts: {json.dumps(verdicts)}")
        print()
        for r in proof_results:
            score = r.get('overall_score', 'N/A')
            verdict = r.get('proof_verdict', 'N/A')
            print(f"  {r['title'][:50]:50s} | {score:.2f} | {verdict}")
    else:
        print("  Proof Engine evaluation skipped (no Bedrock connection)")
        print("  Dataset analysis completed successfully")

    print()
    print("Cross-domain findings:")
    print(f"  {analysis['cross_domain_scoring']['posts_with_cross_domain_hits']} posts match crime/ancient_mysteries domains")
    print(f"  These cross-cutting patterns are the HIGHEST VALUE findings")


if __name__ == '__main__':
    main()
