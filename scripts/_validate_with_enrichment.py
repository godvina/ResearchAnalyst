"""Validate taxonomy with Broad Scanner enrichment step.

The correct pipeline is: Raw Data → Broad Scanner (enrich) → Taxonomy Scanner (match)
Not: Raw Data → Taxonomy Scanner directly

This script simulates the full pipeline:
1. Load raw UFO records
2. Run Broad Scanner enrichment via Claude (extract conspiracy-relevant indicators)
3. Embed enriched text
4. Match against signature embeddings
5. Report match rates

This is the architecturally correct validation approach.
"""
import json
import os
import sys
import csv
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def cosine_similarity(vec_a, vec_b):
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = sum(a * a for a in vec_a) ** 0.5
    mag_b = sum(b * b for b in vec_b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


BROAD_SCANNER_PROMPT = """Analyze this UFO/UAP sighting report and extract conspiracy-relevant behavioral patterns.

For each pattern you find, classify it into one of these domains:
- evidence_suppression: Reports suppressed, witnesses silenced, documents classified
- institutional_behavior: Government/military response patterns, coordinated denials
- witness_reliability: Multiple witnesses, credentialed observers, consistency
- timeline_anomalies: Temporal clustering, impossible timing, recurring events
- geographic_clustering: Hotspot areas, correlation with military/nuclear sites
- information_asymmetry: What's known vs disclosed, radar vs official statements
- expert_divergence: Pilots/scientists disagreeing with official explanations
- narrative_coherence: Consistent craft descriptions across cases, structural patterns
- methodological_red_flags: Premature case closure, evidence not collected
- counter_narrative: Physical traces, independent analysis contradicting official story

SIGHTING REPORT:
{report}

Respond in JSON:
{{
  "enriched_summary": "2-3 sentence summary emphasizing conspiracy-relevant patterns",
  "domains_matched": ["domain1", "domain2"],
  "indicators": ["specific pattern 1", "specific pattern 2"],
  "conspiracy_relevance": "low/medium/high"
}}"""


def enrich_via_broad_scanner(records, bedrock, max_records=20):
    """Enrich raw records through Broad Scanner (Claude)."""
    enriched = []

    for i, record in enumerate(records[:max_records]):
        try:
            prompt = BROAD_SCANNER_PROMPT.format(report=record[:1500])
            response = bedrock.invoke_model(
                modelId="us.anthropic.claude-3-haiku-20240307-v1:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                }),
                contentType="application/json", accept="application/json"
            )
            result = json.loads(response['body'].read())
            content = result['content'][0]['text']

            # Parse JSON response
            try:
                parsed = json.loads(content)
                enriched_text = parsed.get('enriched_summary', '')
                indicators = parsed.get('indicators', [])
                domains = parsed.get('domains_matched', [])
                relevance = parsed.get('conspiracy_relevance', 'low')

                # Build enriched text for embedding
                full_enriched = f"{enriched_text} Domains: {', '.join(domains)}. Indicators: {', '.join(indicators)}"
                enriched.append({
                    'original': record[:500],
                    'enriched_text': full_enriched,
                    'domains': domains,
                    'indicators': indicators,
                    'relevance': relevance,
                })
            except json.JSONDecodeError:
                # Use raw Claude response as enriched text
                enriched.append({
                    'original': record[:500],
                    'enriched_text': content[:500],
                    'domains': [],
                    'indicators': [],
                    'relevance': 'unknown',
                })

        except Exception as e:
            print(f"  Enrichment failed for record {i}: {e}")
            continue

        if (i + 1) % 10 == 0:
            print(f"  Enriched {i+1}/{min(len(records), max_records)} records")

    return enriched


def main():
    import boto3

    print("=" * 70)
    print("TAXONOMY VALIDATION WITH BROAD SCANNER ENRICHMENT")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("Pipeline: Raw Data → Broad Scanner (Claude) → Embed → Match Signatures")
    print()

    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    print("Connected to Bedrock")

    # Load signatures and embed them
    sig_path = PROJECT_ROOT / 'src' / 'data' / 'taxonomy-expansion-ufo-vaers.json'
    with open(sig_path, 'r', encoding='utf-8') as f:
        expansion = json.load(f)

    all_sigs = expansion['ufo_signatures']['new_signatures'] + expansion['vaers_signatures']['new_signatures']
    print(f"Embedding {len(all_sigs)} signatures...")

    sig_embeddings = []
    for sig in all_sigs:
        resp = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": sig['vector_text'], "dimensions": 1024, "normalize": True}),
            contentType="application/json", accept="application/json"
        )
        emb = json.loads(resp['body'].read())['embedding']
        sig_embeddings.append({**sig, 'embedding': emb})

    print(f"  Done: {len(sig_embeddings)} signatures embedded")

    # Load UFO raw data
    print("\nLoading UFO sighting records...")
    ufo_texts = []
    ufo_dir = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'ufo_sightings'
    if ufo_dir.exists():
        for f in os.listdir(ufo_dir):
            fpath = ufo_dir / f
            if f.endswith('.json'):
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    for item in data[:60]:
                        ufo_texts.append(json.dumps(item, ensure_ascii=False)[:2000])
                elif isinstance(data, dict):
                    for key in ['records', 'data', 'results', 'sightings', 'theories']:
                        if key in data and isinstance(data[key], list):
                            for item in data[key][:60]:
                                ufo_texts.append(json.dumps(item, ensure_ascii=False)[:2000])
                            break
            elif f.endswith('.csv'):
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    reader = csv.DictReader(fh)
                    for i, row in enumerate(reader):
                        if i >= 60: break
                        parts = [f"{k}: {v}" for k, v in row.items() if v and len(str(v)) > 10]
                        if parts:
                            ufo_texts.append('\n'.join(parts[:8]))

    print(f"  Loaded {len(ufo_texts)} UFO records")

    # STEP 1: Broad Scanner Enrichment
    print(f"\nRunning Broad Scanner enrichment (Claude Haiku)...")
    enriched_records = enrich_via_broad_scanner(ufo_texts, bedrock, max_records=20)
    print(f"  Enriched: {len(enriched_records)} records")

    # Show relevance distribution
    relevance_counts = {}
    for r in enriched_records:
        rel = r.get('relevance', 'unknown')
        relevance_counts[rel] = relevance_counts.get(rel, 0) + 1
    print(f"  Relevance: {relevance_counts}")

    # STEP 2: Embed enriched text and match against signatures
    print(f"\nMatching enriched records against {len(sig_embeddings)} signatures...")
    threshold = 0.50  # More generous after enrichment aligns domains

    matched = 0
    cross_cutting = 0
    all_scores = []
    match_details = []

    for rec in enriched_records:
        enriched_text = rec['enriched_text']
        if not enriched_text:
            continue

        # Embed enriched text
        resp = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": enriched_text[:2000], "dimensions": 1024, "normalize": True}),
            contentType="application/json", accept="application/json"
        )
        doc_emb = json.loads(resp['body'].read())['embedding']

        # Match against ALL signatures (cross-domain mandatory)
        doc_matches = []
        for sig in sig_embeddings:
            sim = cosine_similarity(doc_emb, sig['embedding'])
            all_scores.append(sim)
            if sim >= threshold:
                doc_matches.append((sig['context_key'], sim))

        if doc_matches:
            matched += 1
            domains_hit = set()
            for ctx_key, score in doc_matches:
                # Determine domain from signature mappings
                for sig in sig_embeddings:
                    if sig['context_key'] == ctx_key:
                        for dm in sig.get('domain_mappings', []):
                            domains_hit.add(dm)
            if len(domains_hit) > 1:
                cross_cutting += 1

            match_details.append({
                'enriched_preview': enriched_text[:200],
                'matches': [(k, f"{s:.3f}") for k, s in sorted(doc_matches, key=lambda x: -x[1])[:3]],
                'domains': list(domains_hit),
            })

    total = len(enriched_records)
    match_rate = (matched / total * 100) if total else 0

    # Score statistics
    all_scores.sort(reverse=True)
    print(f"\n  Score distribution ({len(all_scores)} comparisons):")
    print(f"    Max: {all_scores[0]:.4f}")
    print(f"    Top 10: {[f'{s:.3f}' for s in all_scores[:10]]}")
    print(f"    Mean: {sum(all_scores)/len(all_scores):.4f}")

    # Results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"  UFO records tested: {total}")
    print(f"  Matched (threshold {threshold}): {matched} ({match_rate:.1f}%)")
    print(f"  Cross-cutting: {cross_cutting} ({cross_cutting/total*100:.0f}%)")
    print(f"  Previous (raw, no enrichment): 16%")
    print(f"  Improvement: +{match_rate - 16:.1f}%")

    if match_rate >= 50:
        print(f"\n  ✓ TARGET MET: >= 50% match rate with enrichment pipeline")
    else:
        print(f"\n  ✗ Below 50% target. May need:")
        print(f"    - More signatures or broader vector_text")
        print(f"    - Lower threshold (current top scores suggest {all_scores[int(total*0.5)]:.3f})")
        print(f"    - Richer enrichment prompt")

    # Show sample matches
    if match_details:
        print(f"\n  Sample matches:")
        for md in match_details[:3]:
            print(f"    {md['enriched_preview'][:100]}...")
            print(f"    → {md['matches'][:2]} | Domains: {md['domains']}")
            print()

    # Save results
    output = {
        'test_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'pipeline': 'raw → broad_scanner → embed → taxonomy_match',
            'threshold': threshold,
            'signatures': len(sig_embeddings),
            'records_tested': total,
            'enrichment_model': 'us.anthropic.claude-3-haiku-20240307-v1:0',
            'embedding_model': 'amazon.titan-embed-text-v2:0',
        },
        'results': {
            'ufo_nuforc': {
                'total': total,
                'matched': matched,
                'match_rate': match_rate,
                'cross_cutting': cross_cutting,
                'previous_rate': 16.0,
                'improvement': match_rate - 16.0,
            }
        },
        'enrichment_analysis': {
            'relevance_distribution': relevance_counts,
            'enriched_records_sample': enriched_records[:5],
        },
        'match_details': match_details[:10],
    }

    out_path = PROJECT_ROOT / 'src' / 'data' / 'taxonomy-validation-expanded-results.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
