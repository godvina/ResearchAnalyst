"""Epstein 100-doc taxonomy test — score against FULL 6-level taxonomy (crime + conspiracy).

Pull 100 docs from the Epstein 345K case via API, run Broad Scanner to extract
entities/claims/patterns, then score against ALL taxonomy domains simultaneously.

Looking for: anomalies, needles, signatures popping up in unexpected places.
"""
import json
import sys
import time
import urllib.request
import boto3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '7f05e8d5'  # Epstein Main 345K - need to find full ID

# Full 6-level taxonomy domains (crime + conspiracy merged)
ALL_DOMAINS = [
    # Crime typology
    "financial_trail", "organizational_hierarchy", "witness_intimidation",
    "temporal_clustering", "geographic_pattern", "document_concealment",
    # Conspiracy taxonomy (10 universal)
    "evidence_suppression", "institutional_behavior", "witness_reliability",
    "timeline_anomalies", "geographic_clustering", "information_asymmetry",
    "counter_narrative_emergence", "narrative_coherence", "expert_divergence",
    "methodological_red_flags",
]

BROAD_SCANNER_PROMPT = """Analyze this document from the Jeffrey Epstein case files.
Extract ALL relevant patterns matching these taxonomy domains:

CRIME DOMAINS:
- financial_trail: Money flows, accounts, transactions, shell companies
- organizational_hierarchy: Network structure, who reports to whom, chain of command
- witness_intimidation: Threats, pressure, silencing, NDAs, payoffs
- temporal_clustering: Events clustered in time, suspicious timing
- geographic_pattern: Locations, travel patterns, property addresses
- document_concealment: Sealed records, destroyed evidence, redactions

CONSPIRACY DOMAINS:
- evidence_suppression: Hidden/classified/destroyed evidence
- institutional_behavior: Government agency actions, coordinated responses
- witness_reliability: Credibility, recanting, pressure
- timeline_anomalies: Impossible timing, events out of sequence
- information_asymmetry: What's known vs disclosed
- counter_narrative_emergence: Alternative theories
- narrative_coherence: Official story inconsistencies
- expert_divergence: Experts disagreeing with institutions
- methodological_red_flags: Investigation shortcuts, evidence not collected

DOCUMENT:
{doc_text}

Respond JSON:
{{
  "entities": [{{"name": "...", "type": "person|org|location|date|financial", "context": "..."}}],
  "domains_matched": ["domain1", "domain2"],
  "domain_evidence": {{"domain": "specific evidence from doc"}},
  "anomalies": ["anything unusual or unexpected"],
  "cross_domain_signals": ["patterns that span crime AND conspiracy domains"],
  "conspiracy_relevance": "none|low|medium|high"
}}"""


def get_epstein_case_id():
    """Find the full Epstein 345K case ID."""
    resp = urllib.request.urlopen(f'{API}/case-files', timeout=10)
    cases = json.loads(resp.read()).get('case_files', [])
    for c in cases:
        if '345K' in c.get('topic_name', '') or '345K' in c.get('description', ''):
            return c['case_id']
    # Fallback to the combined case
    for c in cases:
        if 'Epstein Combined' in c.get('topic_name', '') and 'DS1-5' in c.get('topic_name', ''):
            return c['case_id']
    for c in cases:
        if 'Epstein' in c.get('topic_name', ''):
            return c['case_id']
    return None


def get_epstein_docs(case_id, limit=100):
    """Pull docs from the Epstein case via API."""
    # Try search with broad query to get docs with content
    queries = ['Epstein', 'financial', 'testimony', 'investigation', 'flight']
    all_docs = []
    seen_ids = set()

    for q in queries:
        body = json.dumps({'query': q, 'top_k': 25})
        req = urllib.request.Request(
            f'{API}/case-files/{case_id}/search',
            data=body.encode(), headers={'Content-Type': 'application/json'}, method='POST'
        )
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read())
            results = data.get('results', [])
            for r in results:
                doc_id = r.get('document_id', '')
                if doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    passage = r.get('passage', r.get('text', r.get('content', '')))
                    if passage and len(passage) > 50:
                        all_docs.append({'id': doc_id, 'text': passage, 'score': float(r.get('relevance_score', 0))})
        except Exception as e:
            continue

        if len(all_docs) >= limit:
            break

    return all_docs[:limit]


def scan_document(doc, bedrock):
    """Run Broad Scanner on an Epstein document."""
    prompt = BROAD_SCANNER_PROMPT.format(doc_text=doc['text'][:3000])
    try:
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }),
            contentType="application/json", accept="application/json"
        )
        result = json.loads(response['body'].read())
        content = result['content'][0]['text']
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {'raw': content[:500], 'error': 'parse'}
    except Exception as e:
        return {'error': str(e)}


def main():
    print("=" * 70)
    print("EPSTEIN 100-DOC TAXONOMY TEST — CRIME + CONSPIRACY MERGED")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Taxonomy: {len(ALL_DOMAINS)} domains (6 crime + 10 conspiracy)")
    print()

    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

    # Get case
    print("Finding Epstein case...")
    case_id = get_epstein_case_id()
    if not case_id:
        print("  ERROR: No Epstein case found")
        return
    print(f"  Case ID: {case_id}")

    # Pull docs
    print("\nPulling documents from Epstein case...")
    docs = get_epstein_docs(case_id, 100)
    print(f"  Got {len(docs)} documents with content")

    if not docs:
        print("  No documents retrieved. Check API.")
        return

    # Scan each doc
    print(f"\nScanning {len(docs)} docs through Broad Scanner...")
    results = []
    domain_hits = {d: 0 for d in ALL_DOMAINS}
    all_entities = []
    all_anomalies = []
    cross_signals = []
    high_relevance = 0

    for i, doc in enumerate(docs):
        scan = scan_document(doc, bedrock)
        results.append(scan)

        if scan.get('error'):
            continue

        # Track domain hits
        for d in scan.get('domains_matched', []):
            if d in domain_hits:
                domain_hits[d] += 1

        # Track entities
        for e in scan.get('entities', []):
            all_entities.append(e)

        # Track anomalies
        for a in scan.get('anomalies', []):
            if a:
                all_anomalies.append({'doc_id': doc['id'], 'anomaly': a})

        # Track cross-domain signals (THE NEEDLES)
        for s in scan.get('cross_domain_signals', []):
            if s:
                cross_signals.append({'doc_id': doc['id'], 'signal': s})

        if scan.get('conspiracy_relevance') == 'high':
            high_relevance += 1

        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(docs)} scanned...")
        time.sleep(1.2)

    # ANALYSIS
    print(f"\n{'='*70}")
    print("RESULTS: EPSTEIN × FULL TAXONOMY")
    print(f"{'='*70}")
    print(f"  Documents scanned: {len(docs)}")
    print(f"  High conspiracy relevance: {high_relevance}/{len(docs)}")
    print(f"  Total entities extracted: {len(all_entities)}")
    print(f"  Anomalies found: {len(all_anomalies)}")
    print(f"  Cross-domain signals: {len(cross_signals)}")

    print(f"\n  DOMAIN HIT RATES:")
    for domain, count in sorted(domain_hits.items(), key=lambda x: -x[1]):
        if count > 0:
            pct = count / len(docs) * 100
            bar = '█' * int(pct / 5)
            print(f"    {domain:30s} {count:3d} ({pct:4.1f}%) {bar}")

    # Entity analysis - find repeated names
    print(f"\n  TOP ENTITIES (appearing multiple times):")
    entity_counts = {}
    for e in all_entities:
        name = e.get('name', '')
        if name and len(name) > 2:
            entity_counts[name] = entity_counts.get(name, 0) + 1
    for name, count in sorted(entity_counts.items(), key=lambda x: -x[1])[:15]:
        etype = next((e.get('type', '') for e in all_entities if e.get('name') == name), '')
        print(f"    {count:3d}x  [{etype:10s}] {name}")

    # ANOMALIES - the interesting stuff
    if all_anomalies:
        print(f"\n  🔥 ANOMALIES DETECTED:")
        for a in all_anomalies[:10]:
            print(f"    • {a['anomaly'][:100]}")

    # CROSS-DOMAIN SIGNALS - the needles
    if cross_signals:
        print(f"\n  ⚡ CROSS-DOMAIN SIGNALS (crime + conspiracy overlap):")
        for s in cross_signals[:10]:
            print(f"    • {s['signal'][:100]}")

    # Save
    output = {
        'test_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'case_id': case_id,
            'docs_scanned': len(docs),
            'taxonomy_domains': len(ALL_DOMAINS),
        },
        'domain_hits': domain_hits,
        'top_entities': sorted(entity_counts.items(), key=lambda x: -x[1])[:30],
        'anomalies': all_anomalies[:20],
        'cross_domain_signals': cross_signals[:20],
        'high_relevance_count': high_relevance,
    }
    out_path = PROJECT_ROOT / 'src' / 'data' / 'epstein-taxonomy-cross-scan-results.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
