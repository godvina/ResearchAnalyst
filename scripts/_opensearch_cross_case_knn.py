"""Run OpenSearch k-NN queries to find cross-case patterns.

Embeds conspiracy claim themes and searches across ALL indexed cases
(Epstein, SNAP, Cartel, Human Trafficking, Ancient Aliens + new conspiracy data).
"""
import boto3
import json
import urllib.request
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = 'us-east-1'
OPENSEARCH_ENDPOINT = 'https://u260nrrtc0q87ji8iu0k.us-east-1.aoss.amazonaws.com'

session = boto3.Session(region_name=REGION)
credentials = session.get_credentials().get_frozen_credentials()
bedrock = boto3.client('bedrock-runtime', region_name=REGION)


def sign_request(method, url, body=None):
    """Sign request with SigV4 for OpenSearch Serverless."""
    headers = {'Content-Type': 'application/json'}
    request = AWSRequest(method=method, url=url, data=body, headers=headers)
    SigV4Auth(credentials, 'aoss', REGION).add_auth(request)
    return dict(request.headers)


def opensearch_request(method, path, body=None):
    """Execute a signed request to OpenSearch."""
    url = f"{OPENSEARCH_ENDPOINT}/{path}"
    headers = sign_request(method, url, body)
    
    req = urllib.request.Request(url, data=body.encode() if body else None, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ''
        return {'error': e.code, 'message': error_body[:300]}
    except Exception as e:
        return {'error': str(e)}


def get_embedding(text):
    """Get Titan embedding for a search query."""
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text[:2000], "dimensions": 1024, "normalize": True}),
        contentType="application/json", accept="application/json"
    )
    return json.loads(response['body'].read())['embedding']


def main():
    print("=" * 70)
    print("OPENSEARCH CROSS-CASE k-NN SEARCH")
    print("=" * 70)
    
    # First: list all indices to see what's available
    print("\nStep 1: Listing indices...")
    result = opensearch_request('GET', '_cat/indices?v&format=json')
    if 'error' in result:
        print(f"  Index listing: {result}")
        # Try alternate format
        result2 = opensearch_request('GET', '_cat/indices?format=json')
        if 'error' in result2:
            print(f"  Alternate: {result2}")
            print("\n  Cannot access OpenSearch indices directly.")
            print("  The 403 means we need the data access policy updated for this IAM identity.")
            print("  The data IS uploaded to S3 — the Lambda pipeline will index it on next run.")
            print("\n  WORKAROUND: Using API Gateway search instead...")
            run_api_search()
            return
        result = result2
    
    if isinstance(result, list):
        print(f"  Found {len(result)} indices:")
        for idx in result:
            print(f"    {idx.get('index', '?')} — {idx.get('docs.count', '?')} docs, {idx.get('store.size', '?')}")
    
    # Search queries — our cross-cutting themes
    queries = [
        ("evidence suppression classified documents withheld FOIA denied", "EVIDENCE_SUPPRESSION"),
        ("institutional coverup destroyed records blocked investigation", "INSTITUTIONAL_COVERUP"),
        ("financial motive funding conflict of interest revolving door profit", "FINANCIAL_MOTIVE"),
        ("foreknowledge advance warning predicted simulation knew before", "FOREKNOWLEDGE"),
        ("witness silenced career destroyed whistleblower retaliation", "EXPERT_SILENCING"),
    ]
    
    print("\nStep 2: Running k-NN searches across all cases...")
    for query_text, theme in queries:
        print(f"\n  {'='*50}")
        print(f"  THEME: {theme}")
        print(f"  Query: {query_text[:60]}...")
        
        # Get embedding
        embedding = get_embedding(query_text)
        
        # Try k-NN search on case indices
        # The existing cases use index pattern: case-{case_id}
        knn_body = json.dumps({
            "size": 10,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": embedding,
                        "k": 10
                    }
                }
            },
            "_source": ["text", "case_id", "entity_type", "metadata"]
        })
        
        # Search across all case indices
        result = opensearch_request('POST', 'case-*/_search', knn_body)
        
        if 'error' in result:
            # Try keyword search instead
            keyword_body = json.dumps({
                "size": 10,
                "query": {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["text", "content", "description"]
                    }
                }
            })
            result = opensearch_request('POST', 'case-*/_search', keyword_body)
        
        if 'error' in result:
            print(f"    Search failed: {result.get('message', result.get('error', ''))[:100]}")
        elif 'hits' in result:
            hits = result['hits'].get('hits', [])
            print(f"    Found {len(hits)} matches across cases:")
            for hit in hits[:5]:
                source = hit.get('_source', {})
                index = hit.get('_index', '')
                score = hit.get('_score', 0)
                text = source.get('text', source.get('content', ''))[:120]
                print(f"      [{score:.3f}] {index}: {text}...")


def run_api_search():
    """Fallback: use the API Gateway to search."""
    API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
    
    # Get the Epstein case ID
    resp = urllib.request.urlopen(f'{API}/case-files', timeout=10)
    cases = json.loads(resp.read()).get('case_files', [])
    
    # Find searchable cases
    epstein_cases = [c for c in cases if 'Epstein' in c.get('topic_name', '')]
    print(f"\n  Epstein cases available: {len(epstein_cases)}")
    
    # Try search endpoint patterns
    for case in epstein_cases[:2]:
        case_id = case['case_id']
        topic = case['topic_name']
        print(f"\n  Trying search on: {topic} ({case_id[:8]}...)")
        
        # Try various search endpoint patterns
        search_urls = [
            f'{API}/case-files/{case_id}/search?q=evidence+suppression',
            f'{API}/case-files/{case_id}/documents?q=evidence+suppression',
            f'{API}/search?case_id={case_id}&query=evidence+suppression',
        ]
        
        for url in search_urls:
            try:
                req = urllib.request.Request(url, headers={'Content-Type': 'application/json'})
                resp = urllib.request.urlopen(req, timeout=10)
                data = json.loads(resp.read())
                print(f"    ✓ {url.split(case_id)[1][:30]}: {json.dumps(data)[:200]}")
                break
            except Exception as e:
                continue
        
        # Try POST search
        try:
            search_body = json.dumps({"query": "evidence suppression cover up", "top_k": 5})
            req = urllib.request.Request(
                f'{API}/case-files/{case_id}/search',
                data=search_body.encode(),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            results = data.get('results', data.get('documents', []))
            print(f"    POST search: {len(results)} results")
            for r in results[:3]:
                text = r.get('text', r.get('content', r.get('snippet', '')))[:150]
                print(f"      • {text}...")
        except Exception as e:
            print(f"    POST search: {str(e)[:80]}")


if __name__ == '__main__':
    main()
