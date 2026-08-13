"""Ingest conspiracy theory data into the deployed pipeline (Aurora/OpenSearch/Neptune).

Our data is already extracted text (not raw PDFs), so we bypass the batch_loader
and call the ingest API directly. This triggers Step Functions which handles:
- Embedding via Titan
- Storage in Aurora
- Indexing in OpenSearch  
- Graph creation in Neptune

Uses the existing API: POST /case-files/{case_id}/ingest
"""
import boto3
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
PROJECT_ROOT = Path(__file__).parent.parent


def create_case(topic_name, description):
    """Create a new case for conspiracy theories."""
    body = json.dumps({
        'topic_name': topic_name,
        'description': description,
    })
    req = urllib.request.Request(
        f'{API}/case-files',
        data=body.encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        return data.get('case_id', data.get('case_file', {}).get('case_id'))
    except Exception as e:
        print(f"  Create case error: {e}")
        return None


def ingest_documents(case_id, documents):
    """Ingest documents into a case via the API."""
    body = json.dumps({
        'case_id': case_id,
        'documents': documents,
    })
    req = urllib.request.Request(
        f'{API}/case-files/{case_id}/ingest',
        data=body.encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ''
        return {'error': e.code, 'body': error_body[:200]}
    except Exception as e:
        return {'error': str(e)}


def main():
    print("=" * 70)
    print("INGEST CONSPIRACY DATA INTO DEPLOYED PIPELINE")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target: Aurora + OpenSearch + Neptune")
    print()

    # Load our conspiracy claims data
    with open('src/frontend/theory-registry-data.js', 'r', encoding='utf-8') as f:
        content = f.read()
    all_claims = json.loads(content.split('const THEORY_DATA = ')[1].rstrip(';\n'))
    print(f"Total claims to ingest: {len(all_claims)}")

    # Create a case for conspiracy theories
    print("\nStep 1: Creating conspiracy theories case...")
    case_id = create_case(
        'Conspiracy Theory Taxonomy Investigation',
        f'352 claims across 10 conspiracy theories evaluated by Proof Engine. '
        f'Includes: Flat Earth (200 proofs), 9/11, COVID Lab Leak, Moon Landing, '
        f'VAERS, Princess Diana, NWO, RFK Fauci, UFOs, Bermuda Triangle. '
        f'Cross-domain taxonomy scoring with intelligence + scientific standards.'
    )
    
    if not case_id:
        print("  Failed to create case. Trying to find existing...")
        # Check if case already exists
        resp = urllib.request.urlopen(f'{API}/case-files', timeout=10)
        cases = json.loads(resp.read()).get('case_files', [])
        conspiracy_case = [c for c in cases if 'Conspiracy' in c.get('topic_name', '')]
        if conspiracy_case:
            case_id = conspiracy_case[0]['case_id']
            print(f"  Found existing: {case_id}")
        else:
            print("  ERROR: Cannot create or find case")
            return
    else:
        print(f"  Created case: {case_id}")

    # Prepare documents for ingestion (batch into groups of 25)
    print(f"\nStep 2: Preparing {len(all_claims)} documents for ingestion...")
    
    documents = []
    for claim in all_claims:
        doc = {
            'text': f"{claim.get('claim', '')} | Source: {claim.get('source', '')} | "
                   f"Category: {claim.get('category', '')} | Dataset: {claim.get('dataset', '')} | "
                   f"Verdict: {claim.get('verdict', '')} | Score: {claim.get('score', 0)} | "
                   f"Standard: {claim.get('standard', '')}",
            'metadata': {
                'dataset': claim.get('dataset', ''),
                'category': claim.get('category', ''),
                'verdict': claim.get('verdict', ''),
                'score': claim.get('score', 0),
                'source': claim.get('source', ''),
                'claim_id': claim.get('id', ''),
            }
        }
        documents.append(doc)

    # Ingest in batches of 25
    print(f"\nStep 3: Ingesting {len(documents)} documents in batches of 25...")
    batch_size = 25
    success_count = 0
    error_count = 0
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        result = ingest_documents(case_id, batch)
        
        if 'error' in result:
            error_count += 1
            if error_count == 1:
                print(f"  Batch {i//batch_size + 1}: ERROR - {result}")
                # If first batch fails, try alternate endpoint format
                print("  Trying alternate ingest approach...")
                # Try individual document upload
                for doc in batch[:2]:
                    alt_body = json.dumps({'text': doc['text'], 'source': 'conspiracy_taxonomy'})
                    alt_req = urllib.request.Request(
                        f'{API}/case-files/{case_id}/documents',
                        data=alt_body.encode(),
                        headers={'Content-Type': 'application/json'},
                        method='POST'
                    )
                    try:
                        alt_resp = urllib.request.urlopen(alt_req, timeout=10)
                        alt_data = json.loads(alt_resp.read())
                        print(f"    Alt endpoint works: {alt_data}")
                        break
                    except Exception as e2:
                        print(f"    Alt endpoint: {e2}")
            if error_count >= 3:
                print(f"  Too many errors, stopping. Last error: {result}")
                break
        else:
            success_count += 1
            if success_count % 5 == 0:
                print(f"  Batch {i//batch_size + 1}: OK ({i+len(batch)}/{len(documents)} docs)")
        
        time.sleep(1.0)

    print(f"\n{'='*70}")
    print("INGESTION COMPLETE")
    print(f"{'='*70}")
    print(f"  Case ID: {case_id}")
    print(f"  Batches succeeded: {success_count}")
    print(f"  Batches failed: {error_count}")
    print(f"  Documents submitted: {min(success_count * batch_size, len(documents))}")
    print(f"\n  Pipeline will now:")
    print(f"    → Embed via Titan ({len(documents)} docs × $0.0001 = ~${len(documents)*0.0001:.2f})")
    print(f"    → Extract entities via Claude Haiku")
    print(f"    → Store in Aurora (conspiracy schema)")
    print(f"    → Index in OpenSearch (k-NN enabled)")
    print(f"    → Create Neptune graph edges")


if __name__ == '__main__':
    main()
