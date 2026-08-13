"""Process Voat conspiracy annotation dataset through the Proof Engine.

Source: LOCO (Language of Conspiracy) corpus — Voat annotations
Records: 3,384 total (990 labeled CT=TRUE with structured annotations)
Annotations: Actor, Action, Threat, Pattern, Secrecy (5-dimension conspiracy taxonomy)
Downloaded: 2026-08-02
Source URL: https://zenodo.org/records/3560867

CROSS-DOMAIN SCORING: Per steering rules, we score ALL taxonomy domains
simultaneously (ancient_mysteries + conspiracy_theory + crime). Cross-domain
matches are flagged as highest-value findings.
"""
import csv
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import boto3
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from src.services.proof_engine import ProofEngine

# Paths
DATA_PATH = 'src/data/conspiracy-seed/voat_annotations/voat_annotation.csv'
OUTPUT_PATH = 'src/data/proof-engine-results-voat-annotations.json'
EXTRACTED_PATH = 'src/data/conspiracy-seed/voat_annotations/extracted_theories.json'

# ----- TAXONOMY DOMAIN SIGNATURES (for cross-domain matching) -----
# These are the pattern signatures from all 3 tenant domains.
# In production, these come from OpenSearch k-NN. Here we use keyword matching
# as a proxy since we can't reach VPC-only OpenSearch from local.

TAXONOMY_SIGNATURES = {
    "conspiracy_theory": {
        "evidence_suppression": ["cover up", "suppressed", "hidden", "censored", "silenced", "removed", "deleted", "blocked"],
        "coordinated_actors": ["they", "elites", "government", "deep state", "cabal", "illuminati", "powers that be", "nwo"],
        "pattern_recognition": ["coincidence", "connected", "pattern", "dots", "timing", "planned", "orchestrated"],
        "information_asymmetry": ["they know", "secret", "classified", "hidden truth", "wake up", "sheep", "asleep"],
        "threat_narrative": ["agenda", "control", "destroy", "depopulation", "enslave", "poison", "weapon"],
    },
    "ancient_mysteries": {
        "advanced_technology": ["technology", "precision", "impossible", "engineering", "ancient", "advanced civilization"],
        "geographic_alignment": ["alignment", "ley line", "coordinate", "grid", "geometry", "sacred site"],
        "lost_knowledge": ["lost", "forgotten", "erased", "destroyed", "library", "ancient knowledge"],
        "anomalous_artifacts": ["artifact", "out of place", "anomaly", "unexplained", "mysterious object"],
        "astronomical_correlation": ["stars", "constellation", "solstice", "equinox", "precession", "orion"],
    },
    "crime": {
        "document_concealment": ["shredded", "destroyed evidence", "missing files", "wiped", "bleached"],
        "witness_intimidation": ["threatened", "killed", "silenced", "died mysteriously", "suicide"],
        "financial_trail": ["money", "funding", "offshore", "laundering", "transaction", "payment"],
        "organizational_hierarchy": ["boss", "handler", "network", "ring", "cell", "operation"],
        "temporal_clustering": ["same time", "same day", "coincidence", "timing", "before", "right after"],
    },
}


def score_against_all_domains(text: str) -> dict:
    """Score a document against ALL taxonomy domains simultaneously.
    
    Per steering rules: do NOT filter by domain. Search everything.
    Cross-domain hits are flagged as 'cross_cutting'.
    """
    text_lower = text.lower()
    matches = {}
    
    for domain, signatures in TAXONOMY_SIGNATURES.items():
        for sig_name, keywords in signatures.items():
            hits = [kw for kw in keywords if kw in text_lower]
            if hits:
                key = f"{domain}/{sig_name}"
                matches[key] = {
                    "domain": domain,
                    "signature": sig_name,
                    "keyword_hits": hits,
                    "hit_count": len(hits),
                }
    
    return matches


def extract_theories_from_voat(csv_path: str) -> list:
    """Extract conspiracy-labeled posts and structure as theories for the Proof Engine.
    
    Groups by subverse and dominant conspiracy dimension to create
    testable 'meta-theories' that can be evaluated.
    """
    posts_by_subverse = defaultdict(list)
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['overall_ct'] != 'TRUE':
                continue
            
            # Count annotation dimensions
            dims = []
            if row['Actor'] == 'TRUE':
                dims.append('Actor')
            if row['Action'] == 'TRUE':
                dims.append('Action')
            if row['Threat'] == 'TRUE':
                dims.append('Threat')
            if row['Pattern'] == 'TRUE':
                dims.append('Pattern')
            if row['Secrecy'] == 'TRUE':
                dims.append('Secrecy')
            
            posts_by_subverse[row.get('subverse', 'unknown')].append({
                'body': row.get('body', ''),
                'dimensions': dims,
                'dimension_count': len(dims),
                'actor_span': row.get('Actor_span', 'NA'),
                'action_span': row.get('Action_span', 'NA'),
                'pattern_span': row.get('Pattern_span', 'NA'),
                'secrecy_span': row.get('Secrecy_span', 'NA'),
                'threat_span': row.get('Threat_span', 'NA'),
                'date': row.get('date', ''),
                'upvotes': int(row.get('upvotes', 0) or 0),
            })
    
    # Build meta-theories from each subverse cluster
    theories = []
    
    for subverse, posts in posts_by_subverse.items():
        if not posts:
            continue
        
        # Sort by dimension richness (most annotated = strongest signal)
        rich_posts = sorted(posts, key=lambda p: p['dimension_count'], reverse=True)
        
        # Take top 10 richest posts as evidence corpus
        evidence_posts = rich_posts[:10]
        
        # Build the meta-theory from this cluster
        dominant_dims = defaultdict(int)
        for p in posts:
            for d in p['dimensions']:
                dominant_dims[d] += 1
        
        top_dim = max(dominant_dims.items(), key=lambda x: x[1])[0] if dominant_dims else 'Pattern'
        
        # Cross-domain scoring for all posts in this subverse
        cross_domain_hits = defaultdict(int)
        for p in evidence_posts:
            matches = score_against_all_domains(p['body'])
            for key, match in matches.items():
                cross_domain_hits[key] += match['hit_count']
        
        # Determine if cross-cutting
        domains_hit = set()
        for key in cross_domain_hits:
            domain = key.split('/')[0]
            domains_hit.add(domain)
        
        is_cross_cutting = len(domains_hit) >= 2
        
        theory = {
            'id': str(uuid.uuid4()),
            'title': f"Voat/{subverse} Conspiracy Narrative Cluster",
            'claim': f"Posts in v/{subverse} exhibit coordinated conspiracy thinking with dominant {top_dim} dimension ({len(posts)} posts, {sum(p['dimension_count'] for p in posts)/len(posts):.1f} avg dimensions)",
            'subverse': subverse,
            'total_posts': len(posts),
            'ct_dimension_breakdown': dict(dominant_dims),
            'dominant_dimension': top_dim,
            'avg_dimensions_per_post': round(sum(p['dimension_count'] for p in posts) / len(posts), 2),
            'multi_dimension_posts': sum(1 for p in posts if p['dimension_count'] >= 2),
            'evidence_samples': [p['body'][:300] for p in evidence_posts[:5]],
            'cross_domain_matches': dict(cross_domain_hits),
            'domains_matched': list(domains_hit),
            'is_cross_cutting': is_cross_cutting,
        }
        theories.append(theory)
    
    return theories


def run_proof_engine(theories: list, use_bedrock: bool = True) -> list:
    """Run all extracted theories through the Proof Engine with intelligence standard."""
    
    if use_bedrock and HAS_BOTO:
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        engine = ProofEngine(bedrock_client=bedrock)
        print("Connected to Bedrock (Claude 3 Haiku)")
    else:
        engine = ProofEngine(bedrock_client=None)
        print("Running WITHOUT Bedrock (scores will be 0.0)")
    
    results = []
    
    for i, theory in enumerate(theories):
        print(f"[{i+1}/{len(theories)}] {theory['title']}...", end=" ", flush=True)
        
        # Build evidence text
        evidence_parts = [
            f"SUBVERSE: v/{theory['subverse']}",
            f"TOTAL POSTS: {theory['total_posts']}",
            f"DOMINANT DIMENSION: {theory['dominant_dimension']}",
            f"AVERAGE DIMENSIONS PER POST: {theory['avg_dimensions_per_post']}",
            f"MULTI-DIMENSION POSTS: {theory['multi_dimension_posts']}",
            "",
            "CROSS-DOMAIN TAXONOMY MATCHES:",
        ]
        for sig, count in sorted(theory['cross_domain_matches'].items(), key=lambda x: -x[1])[:10]:
            evidence_parts.append(f"  {sig}: {count} hits")
        
        evidence_parts.append("")
        evidence_parts.append("SAMPLE POSTS:")
        for j, sample in enumerate(theory['evidence_samples']):
            evidence_parts.append(f"  [{j+1}] {sample}")
        
        evidence = "\n".join(evidence_parts)
        
        finding_data = {
            "description": theory['claim'],
            "theory_name": f"voat_{theory['subverse'].lower()}",
            "title": theory['title'],
        }
        
        # Use intelligence standard for conspiracy theories (per steering)
        verdict = engine.evaluate(
            finding_id=theory['id'],
            finding_data=finding_data,
            evidence=evidence,
            standard_name="intelligence",
            tenant_id="conspiracy_theories"
        )
        
        results.append({
            "theory_id": theory['id'],
            "title": theory['title'],
            "subverse": theory['subverse'],
            "claim": theory['claim'],
            "total_posts": theory['total_posts'],
            "dominant_dimension": theory['dominant_dimension'],
            "avg_dimensions": theory['avg_dimensions_per_post'],
            "is_cross_cutting": theory['is_cross_cutting'],
            "domains_matched": theory['domains_matched'],
            "cross_domain_top_hits": dict(sorted(
                theory['cross_domain_matches'].items(), key=lambda x: -x[1]
            )[:5]),
            "verdict": verdict.verdict,
            "overall_score": verdict.overall_score,
            "checklist_items": [
                {"item": item.description, "score": item.score, "justification": item.justification[:200]}
                for item in verdict.checklist_items
            ],
            "research_directions": verdict.research_directions,
        })
        print(f"{verdict.verdict} (score: {verdict.overall_score:.2f}) {'[CROSS-CUTTING]' if theory['is_cross_cutting'] else ''}")
    
    return results


def main():
    print("=" * 60)
    print("VOAT CONSPIRACY ANNOTATION PROCESSING")
    print("=" * 60)
    print(f"Source: {DATA_PATH}")
    print(f"Standard: INTELLIGENCE (per steering: conspiracy -> intelligence)")
    print(f"Cross-domain scoring: ALL domains (per steering rules)")
    print()
    
    # Step 1: Extract and cluster
    print("[Step 1] Extracting conspiracy-labeled posts and clustering...")
    theories = extract_theories_from_voat(DATA_PATH)
    print(f"  Extracted {len(theories)} meta-theories from {sum(t['total_posts'] for t in theories)} posts")
    print()
    
    # Show cross-domain summary
    cross_cutting = [t for t in theories if t['is_cross_cutting']]
    print(f"  Cross-cutting theories (match 2+ domains): {len(cross_cutting)}/{len(theories)}")
    for t in cross_cutting:
        print(f"    - {t['subverse']}: matches {t['domains_matched']}")
    print()
    
    # Save extracted theories
    with open(EXTRACTED_PATH, 'w', encoding='utf-8') as f:
        json.dump({
            "source": "Voat LOCO conspiracy annotations",
            "source_url": "https://zenodo.org/records/3560867",
            "download_date": "2026-08-02",
            "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_ct_posts": sum(t['total_posts'] for t in theories),
            "theories": theories,
        }, f, indent=2, ensure_ascii=False)
    print(f"  Saved extracted theories: {EXTRACTED_PATH}")
    print()
    
    # Step 2: Run Proof Engine
    print("[Step 2] Running Proof Engine (intelligence standard)...")
    print()
    results = run_proof_engine(theories, use_bedrock=HAS_BOTO)
    
    # Step 3: Save results
    output = {
        "evaluation_run": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "standard": "intelligence",
            "model": "us.anthropic.claude-3-haiku-20240307-v1:0",
            "source_dataset": "voat_annotation.csv (LOCO corpus)",
            "source_url": "https://zenodo.org/records/3560867",
            "total_posts_processed": sum(t['total_posts'] for t in theories),
            "theories_evaluated": len(results),
            "cross_domain_scoring": True,
        },
        "summary": {
            "proven": sum(1 for r in results if r['verdict'] == 'PROVEN'),
            "unproven": sum(1 for r in results if r['verdict'] == 'UNPROVEN'),
            "insufficient": sum(1 for r in results if r['verdict'] == 'INSUFFICIENT_EVIDENCE'),
            "average_score": round(sum(r['overall_score'] for r in results) / len(results), 3) if results else 0,
            "cross_cutting_theories": sum(1 for r in results if r['is_cross_cutting']),
        },
        "cross_domain_analysis": {
            "description": "Matches found across multiple taxonomy domains (highest value findings)",
            "theories_matching_ancient_mysteries": sum(
                1 for r in results if 'ancient_mysteries' in r.get('domains_matched', [])
            ),
            "theories_matching_crime": sum(
                1 for r in results if 'crime' in r.get('domains_matched', [])
            ),
            "theories_matching_conspiracy": sum(
                1 for r in results if 'conspiracy_theory' in r.get('domains_matched', [])
            ),
        },
        "results": results,
    }
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total posts processed: {output['evaluation_run']['total_posts_processed']}")
    print(f"  Meta-theories evaluated: {len(results)}")
    print(f"  PROVEN: {output['summary']['proven']}")
    print(f"  UNPROVEN: {output['summary']['unproven']}")
    print(f"  INSUFFICIENT_EVIDENCE: {output['summary']['insufficient']}")
    print(f"  Average score: {output['summary']['average_score']:.3f}")
    print(f"  Cross-cutting: {output['summary']['cross_cutting_theories']}")
    print()
    print("CROSS-DOMAIN ANALYSIS:")
    print(f"  Theories matching ancient_mysteries signatures: {output['cross_domain_analysis']['theories_matching_ancient_mysteries']}")
    print(f"  Theories matching crime signatures: {output['cross_domain_analysis']['theories_matching_crime']}")
    print(f"  Theories matching conspiracy signatures: {output['cross_domain_analysis']['theories_matching_conspiracy']}")
    print()
    print(f"Results saved to: {OUTPUT_PATH}")
    print(f"Extracted theories saved to: {EXTRACTED_PATH}")


if __name__ == '__main__':
    main()
