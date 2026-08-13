"""JFK Assassination — Taxonomy Seed Test with 50 Documents.

This tests our conspiracy taxonomy against REAL declassified documents.
For each document, we:
1. Extract it through the Broad Scanner (entity/claim extraction via Claude)
2. Match against our 10 taxonomy domains
3. Score with cross-domain matching (mandatory)
4. Identify which signatures fire and which domains are hit

This validates the taxonomy is working on real government documents.
"""
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.proof_engine import ProofEngine

OUTPUT_DIR = PROJECT_ROOT / 'src' / 'data'
JFK_CSV = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'jfk_assassination' / 'jfk-files.csv'

csv.field_size_limit(10000000)  # JFK docs are large

TAXONOMY_DOMAINS = [
    "evidence_suppression",
    "institutional_behavior",
    "witness_reliability",
    "timeline_anomalies",
    "geographic_clustering",
    "information_asymmetry",
    "counter_narrative_emergence",
    "narrative_coherence",
    "expert_divergence",
    "methodological_red_flags",
]


BROAD_SCANNER_PROMPT = """You are analyzing a declassified JFK assassination document for conspiracy-relevant patterns.

DOCUMENT (first 3000 chars):
{doc_text}

Analyze this document against these 10 taxonomy domains. For each domain that matches, 
provide specific evidence from the document:

1. evidence_suppression — Redacted text, classified markings, withheld information
2. institutional_behavior — Inter-agency coordination, contradictory statements, cover stories
3. witness_reliability — Witness statements, credibility issues, pressure on witnesses
4. timeline_anomalies — Events out of sequence, suspicious timing, impossible timings
5. geographic_clustering — Multiple events at same location, surveillance patterns
6. information_asymmetry — What's known vs disclosed, selective release patterns
7. counter_narrative_emergence — Alternative theories discussed, contradicting official story
8. narrative_coherence — Internal consistency issues in official account
9. expert_divergence — Experts disagreeing with official conclusions
10. methodological_red_flags — Investigation shortcuts, evidence not collected, scope limitations

Respond in JSON:
{{
  "file_name": "{file_name}",
  "domains_matched": ["domain1", "domain2"],
  "domain_details": {{
    "domain_name": {{"evidence": "specific text/pattern from doc", "confidence": 0.0-1.0}}
  }},
  "key_entities": ["entity1", "entity2"],
  "key_claims": ["claim1", "claim2"],
  "conspiracy_relevance": "low/medium/high",
  "cross_domain_patterns": ["pattern that spans multiple domains"]
}}"""


def load_jfk_sample(n=50):
    """Load first N JFK documents."""
    docs = []
    with open(JFK_CSV, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= n: break
            docs.append({
                'file_name': row.get('file_name', f'doc_{i}'),
                'text': row.get('text', '')[:5000],  # Cap at 5K for Bedrock
                'full_length': len(row.get('text', '')),
            })
    return docs


def scan_document(doc, bedrock):
    """Run Broad Scanner on a single JFK document."""
    prompt = BROAD_SCANNER_PROMPT.format(
        doc_text=doc['text'][:3000],
        file_name=doc['file_name']
    )
    
    try:
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }),
            contentType="application/json",
            accept="application/json"
        )
        result = json.loads(response['body'].read())
        content = result['content'][0]['text']
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {'raw': content[:500], 'error': 'json_parse'}
    except Exception as e:
        return {'error': str(e)}


def main():
    import boto3
    
    print("=" * 70)
    print("JFK ASSASSINATION — TAXONOMY SEED TEST (50 DOCUMENTS)")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Source: Seungjun/jfk-files HuggingFace (2,522 OCR'd declassified docs)")
    print(f"Test: 50 docs through Broad Scanner → Taxonomy Domain Matching")
    print(f"Cross-domain scoring: ENABLED (mandatory)")
    print()
    
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    print("Connected to Bedrock\n")
    
    # Load 50 docs
    print("Loading 50 JFK documents...")
    docs = load_jfk_sample(50)
    print(f"  Loaded {len(docs)} docs, avg length: {sum(d['full_length'] for d in docs)//len(docs)} chars\n")
    
    # Scan each document
    print("Running Broad Scanner on each document...")
    scan_results = []
    domain_hits = {d: 0 for d in TAXONOMY_DOMAINS}
    cross_domain_count = 0
    high_relevance = 0
    
    for i, doc in enumerate(docs):
        result = scan_document(doc, bedrock)
        scan_results.append(result)
        
        # Track domain hits
        domains = result.get('domains_matched', [])
        for d in domains:
            if d in domain_hits:
                domain_hits[d] += 1
        
        if len(domains) >= 3:
            cross_domain_count += 1
        
        relevance = result.get('conspiracy_relevance', 'low')
        if relevance == 'high':
            high_relevance += 1
        
        if (i + 1) % 10 == 0:
            print(f"  Scanned {i+1}/50 docs...")
        
        time.sleep(1.0)
    
    # Analysis
    total_scanned = len([r for r in scan_results if not r.get('error')])
    match_rate = sum(1 for r in scan_results if r.get('domains_matched')) / len(scan_results) * 100
    
    print(f"\n{'='*70}")
    print("TAXONOMY TEST RESULTS")
    print(f"{'='*70}")
    print(f"  Documents scanned: {total_scanned}/50")
    print(f"  Match rate (at least 1 domain): {match_rate:.1f}%")
    print(f"  Cross-domain hits (3+ domains): {cross_domain_count}/50")
    print(f"  High conspiracy relevance: {high_relevance}/50")
    print(f"\n  DOMAIN HIT RATES:")
    for domain, count in sorted(domain_hits.items(), key=lambda x: -x[1]):
        pct = count / total_scanned * 100 if total_scanned else 0
        bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
        print(f"    {domain:30s} {count:3d} ({pct:5.1f}%) {bar}")
    
    # Coverage assessment
    covered = sum(1 for c in domain_hits.values() if c >= 3)
    gaps = [d for d, c in domain_hits.items() if c < 3]
    print(f"\n  TAXONOMY COVERAGE:")
    print(f"    Domains with 3+ hits: {covered}/10")
    print(f"    Gaps (< 3 hits): {gaps if gaps else 'NONE'}")
    print(f"    Overall coverage: {covered/10*100:.0f}%")
    
    # Also run JFK-specific claims through Proof Engine
    print(f"\n  Running Proof Engine on JFK conspiracy claims...")
    engine = ProofEngine(bedrock_client=bedrock)
    
    jfk_claims = [
        {"id": "jfk-001", "claim": "Lee Harvey Oswald did not act alone — multiple shooters were involved based on acoustic evidence and wound trajectories"},
        {"id": "jfk-002", "claim": "The CIA had foreknowledge of the assassination and withheld information from the Warren Commission"},
        {"id": "jfk-003", "claim": "Jack Ruby's murder of Oswald was orchestrated to silence him, not a spontaneous act of grief"},
        {"id": "jfk-004", "claim": "The 'magic bullet' theory (single bullet causing 7 wounds) violates basic physics and was fabricated to support the lone gunman narrative"},
        {"id": "jfk-005", "claim": "Multiple witnesses reported shots from the grassy knoll, and their testimony was suppressed or altered"},
        {"id": "jfk-006", "claim": "Oswald's connections to both CIA and Soviet intelligence suggest he was a pawn in a larger operation"},
        {"id": "jfk-007", "claim": "The Zapruder film shows Kennedy's head moving backward (toward the shooter), inconsistent with a shot from behind"},
        {"id": "jfk-008", "claim": "Key witnesses died under suspicious circumstances in the years following the assassination at a statistically improbable rate"},
    ]
    
    jfk_proof_results = []
    # Build evidence from scanned docs
    doc_evidence = "\n".join([
        f"[{r.get('file_name','doc')}] Domains: {r.get('domains_matched',[])} Relevance: {r.get('conspiracy_relevance','?')}"
        for r in scan_results[:20] if not r.get('error')
    ])
    
    for claim in jfk_claims:
        finding_data = {'description': claim['claim'], 'theory_name': 'JFK Assassination'}
        evidence = f"CLAIM: {claim['claim']}\n\nDECLASSIFIED DOCUMENT ANALYSIS (50 docs scanned):\n{doc_evidence[:2000]}"
        verdict = engine.evaluate(claim['id'], finding_data, evidence, 'intelligence', 'conspiracy_theories')
        jfk_proof_results.append({
            'claim_id': claim['id'], 'claim': claim['claim'],
            'verdict': verdict.verdict, 'score': verdict.overall_score,
        })
        print(f"    {verdict.verdict} ({verdict.overall_score:.2f}) - {claim['claim'][:60]}")
        time.sleep(0.8)
    
    # Save everything
    output = {
        'test_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'documents_scanned': total_scanned,
            'source': 'Seungjun/jfk-files (HuggingFace, 103 MB, 2522 docs)',
            'match_rate': match_rate,
            'cross_domain_rate': cross_domain_count / 50 * 100,
        },
        'domain_hits': domain_hits,
        'coverage': {'covered': covered, 'gaps': gaps, 'pct': covered / 10 * 100},
        'scan_results': scan_results,
        'proof_engine_results': jfk_proof_results,
    }
    
    out_path = OUTPUT_DIR / 'proof-engine-results-jfk-taxonomy-test.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
