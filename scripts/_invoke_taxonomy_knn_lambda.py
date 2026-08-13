"""Invoke Lambda to run taxonomy k-NN search against Epstein embeddings in OpenSearch.

Strategy:
1. Embed our new taxonomy signatures (16 domains) using Titan Embed locally
2. Invoke the existing Lambda (which has OpenSearch access) with those vectors
3. Lambda searches the Epstein index for k-NN matches against each signature
4. Returns which Epstein docs match which conspiracy/crime taxonomy patterns

This uses the EXISTING deployed infrastructure — no new Lambda needed.
We invoke the search Lambda that's already wired to OpenSearch.
"""
import boto3
import json
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')

# Our full taxonomy signatures to search with
TAXONOMY_SIGNATURES = [
    # Crime domains
    {"domain": "crime", "name": "financial_trail", "text": "money laundering shell company offshore account wire transfer suspicious transaction layering placement integration"},
    {"domain": "crime", "name": "organizational_hierarchy", "text": "chain of command recruitment structure network associate lieutenant boss leader organization rank"},
    {"domain": "crime", "name": "witness_intimidation", "text": "threat silence NDA payoff bribe coerce pressure witness recant fear retaliation"},
    {"domain": "crime", "name": "temporal_clustering", "text": "events clustered same time period suspicious timing coordinated dates sequence pattern"},
    {"domain": "crime", "name": "geographic_pattern", "text": "location travel pattern property address island residence frequent visits movement tracking"},
    {"domain": "crime", "name": "document_concealment", "text": "sealed record destroyed evidence shredded redacted classified hidden document disposal"},
    # Conspiracy domains
    {"domain": "conspiracy", "name": "evidence_suppression", "text": "classified withheld suppressed FOIA denied sealed records destroyed evidence blocked access"},
    {"domain": "conspiracy", "name": "institutional_behavior", "text": "government agency coordinated response contradicted official statement institutional failure coverup"},
    {"domain": "conspiracy", "name": "witness_reliability", "text": "witness credibility recanting pressure intimidated inconsistent testimony changed story death"},
    {"domain": "conspiracy", "name": "timeline_anomalies", "text": "impossible timing before after retroactive predated sequence violated expected order"},
    {"domain": "conspiracy", "name": "information_asymmetry", "text": "known but not disclosed insider knowledge selective release delayed years later FOIA"},
    {"domain": "conspiracy", "name": "counter_narrative", "text": "alternative theory researchers argue disputed official story challenged contradicts"},
    {"domain": "conspiracy", "name": "narrative_coherence", "text": "contradiction inconsistent doesn't explain impossible official account changed story"},
    {"domain": "conspiracy", "name": "expert_divergence", "text": "expert disagrees whistleblower dissent professional risk credentials challenged mainstream"},
    {"domain": "conspiracy", "name": "methodological_red_flags", "text": "scope limited not investigated predetermined conclusion shortcuts evidence not collected"},
    {"domain": "conspiracy", "name": "regulatory_capture", "text": "revolving door industry funding conflict interest captured regulator oversight failure"},
]


def embed_signatures():
    """Embed all taxonomy signatures using Titan Embed v2."""
    print("Embedding taxonomy signatures...")
    embedded = []
    for sig in TAXONOMY_SIGNATURES:
        response = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": sig['text'], "dimensions": 1024, "normalize": True}),
            contentType="application/json", accept="application/json"
        )
        vector = json.loads(response['body'].read())['embedding']
        embedded.append({**sig, 'vector': vector})
        time.sleep(0.3)
    print(f"  Embedded {len(embedded)} signatures")
    return embedded


def find_search_lambda():
    """Find the deployed Lambda function that can search OpenSearch."""
    print("Finding search Lambda...")
    paginator = lambda_client.get_paginator('list_functions')
    
    search_lambdas = []
    for page in paginator.paginate():
        for fn in page['Functions']:
            name = fn['FunctionName']
            if any(kw in name.lower() for kw in ['search', 'semantic', 'opensearch', 'query']):
                search_lambdas.append(name)
    
    print(f"  Found {len(search_lambdas)} potential search Lambdas:")
    for name in search_lambdas[:10]:
        print(f"    {name}")
    
    return search_lambdas


def invoke_search(lambda_name, case_id, vector, top_k=10):
    """Invoke the search Lambda with a vector query."""
    payload = {
        "body": json.dumps({
            "case_id": case_id,
            "embedding": vector,
            "top_k": top_k,
            "mode": "semantic",
        }),
        "httpMethod": "POST",
        "path": f"/case-files/{case_id}/search",
    }
    
    try:
        response = lambda_client.invoke(
            FunctionName=lambda_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload).encode(),
        )
        result = json.loads(response['Payload'].read())
        if isinstance(result, dict) and 'body' in result:
            return json.loads(result['body'])
        return result
    except Exception as e:
        return {'error': str(e)}


def main():
    print("=" * 70)
    print("TAXONOMY k-NN SEARCH VIA LAMBDA — Epstein × New Taxonomy")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Cost: ~$0.002 (16 Titan embeddings only)")
    print()
    
    # Step 1: Embed signatures
    signatures = embed_signatures()
    
    # Step 2: Find the Lambda
    lambdas = find_search_lambda()
    
    if not lambdas:
        print("\n  No search Lambda found. Listing all Lambdas...")
        paginator = lambda_client.get_paginator('list_functions')
        all_lambdas = []
        for page in paginator.paginate():
            for fn in page['Functions']:
                all_lambdas.append(fn['FunctionName'])
        
        # Look for anything research-analyst related
        ra_lambdas = [l for l in all_lambdas if 'research' in l.lower() or 'analyst' in l.lower() or 'investigat' in l.lower()]
        print(f"  Research Analyst Lambdas: {len(ra_lambdas)}")
        for l in ra_lambdas[:20]:
            print(f"    {l}")
        
        # Also check all lambdas
        print(f"\n  All Lambdas ({len(all_lambdas)} total):")
        for l in sorted(all_lambdas)[:30]:
            print(f"    {l}")
        
        # Save signatures for manual Lambda invoke
        sig_path = PROJECT_ROOT / 'src' / 'data' / 'taxonomy-signature-vectors-for-lambda.json'
        with open(sig_path, 'w', encoding='utf-8') as f:
            json.dump(signatures, f)
        print(f"\n  Saved signature vectors: {sig_path}")
        print("  These can be used to manually invoke the search Lambda")
        return
    
    # Step 3: Run k-NN search for each signature against Epstein
    # Use the Epstein Combined case
    epstein_case_id = 'ed0b6c27-3b6b-4255-b9d0-efe8f4383a99'
    search_lambda = lambdas[0]
    
    print(f"\n  Using Lambda: {search_lambda}")
    print(f"  Searching case: {epstein_case_id}")
    print(f"  Signatures: {len(signatures)}")
    
    results = {}
    for sig in signatures:
        print(f"  Searching: {sig['domain']}/{sig['name']}...")
        result = invoke_search(search_lambda, epstein_case_id, sig['vector'])
        
        hits = result.get('results', result.get('hits', []))
        results[f"{sig['domain']}/{sig['name']}"] = {
            'hit_count': len(hits),
            'top_hits': hits[:3],
        }
        
        if hits:
            print(f"    → {len(hits)} matches")
        time.sleep(0.5)
    
    # Summary
    print(f"\n{'='*70}")
    print("RESULTS: Which taxonomy patterns match Epstein docs?")
    print(f"{'='*70}")
    for sig_key, data in sorted(results.items(), key=lambda x: -x[1]['hit_count']):
        if data['hit_count'] > 0:
            print(f"  {data['hit_count']:3d} hits — {sig_key}")
    
    # Save
    out_path = PROJECT_ROOT / 'src' / 'data' / 'epstein-taxonomy-knn-via-lambda.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'timestamp': datetime.now(timezone.utc).isoformat(), 'results': results}, f, indent=2)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
