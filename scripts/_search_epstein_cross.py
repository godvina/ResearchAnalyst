"""Search Epstein case for conspiracy-relevant patterns via API."""
import urllib.request
import json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'

# Get Epstein case ID
resp = urllib.request.urlopen(f'{API}/case-files', timeout=10)
cases = json.loads(resp.read()).get('case_files', [])
epstein_cases = [c for c in cases if 'Epstein' in c.get('topic_name', '') and 'Combined' in c.get('topic_name', '')]

if not epstein_cases:
    print("No Epstein cases found")
    exit()

case = epstein_cases[0]
case_id = case['case_id']
print(f"Searching: {case['topic_name']}")
print(f"Case ID: {case_id}")
print(f"Description: {case['description'][:200]}")
print()

# Search for our cross-cutting conspiracy patterns
queries = [
    'evidence suppression documents destroyed',
    'financial transactions offshore accounts',
    'witness intimidation threats silence',
    'intelligence agency CIA FBI connection',
    'cover up obstruction investigation',
    'powerful individuals politicians names',
    'blackmail leverage control',
    'institutional failure oversight',
]

print("CROSS-CASE PATTERN SEARCH: Conspiracy themes → Epstein documents")
print("=" * 60)

for q in queries:
    body = json.dumps({'query': q, 'top_k': 3})
    req = urllib.request.Request(
        f'{API}/case-files/{case_id}/search',
        data=body.encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        results = data.get('results', [])
        print(f"\n  [{q[:40]}]: {len(results)} matches")
        for r in results[:2]:
            # Get text content from result
            text = ''
            score = r.get('score', 0)
            for key in ['text', 'content', 'snippet', 'body', 'summary', 'description']:
                if key in r and isinstance(r[key], str) and len(r[key]) > 20:
                    text = r[key][:200]
                    break
            if not text:
                # Show all keys
                text = str({k: str(v)[:50] for k, v in r.items() if v})[:200]
            print(f"    [{score:.2f}] {text}")
    except Exception as e:
        print(f"  [{q[:40]}]: ERROR {str(e)[:60]}")
