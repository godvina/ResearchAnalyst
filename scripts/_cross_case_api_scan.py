"""Cross-case scan via live API — pull all cases and cross-reference with conspiracy findings."""
import urllib.request
import json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'

# Get all cases
resp = urllib.request.urlopen(f'{API}/case-files', timeout=10)
data = json.loads(resp.read())
cases = data.get('case_files', [])

print(f"LIVE CASES IN SYSTEM: {len(cases)}")
print("=" * 60)
for c in cases:
    cid = c.get('case_id', '')[:8]
    topic = c.get('topic_name', '')
    desc = c.get('description', '')[:120]
    print(f"  [{cid}] {topic}")
    print(f"    {desc}")
    print()

# For each case, try to get entities
print("\n" + "=" * 60)
print("ENTITY COUNTS PER CASE")
print("=" * 60)
for c in cases[:10]:
    case_id = c.get('case_id', '')
    try:
        resp = urllib.request.urlopen(f'{API}/case-files/{case_id}/entities', timeout=5)
        entities = json.loads(resp.read())
        ent_list = entities.get('entities', [])
        print(f"  [{c.get('topic_name','')}]: {len(ent_list)} entities")
        if ent_list:
            types = {}
            for e in ent_list:
                t = e.get('entity_type', 'unknown')
                types[t] = types.get(t, 0) + 1
            print(f"    Types: {dict(sorted(types.items(), key=lambda x:-x[1]))}")
    except Exception as e:
        print(f"  [{c.get('topic_name','')}]: {e}")
