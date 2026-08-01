"""Check table schemas then populate prosecution readiness."""
import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

def run_sql(sql):
    body = json.dumps({'sql': sql}).encode()
    req = urllib.request.Request(API + '/admin/run-migration', data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode())

# Check schemas
print("=== case_ips_results columns ===")
r = run_sql("SELECT column_name FROM information_schema.columns WHERE table_name='case_ips_results' ORDER BY ordinal_position")
print([row[0] for row in r.get('rows', [])])

print("\n=== command_center_cache columns ===")
r2 = run_sql("SELECT column_name FROM information_schema.columns WHERE table_name='command_center_cache' ORDER BY ordinal_position")
print([row[0] for row in r2.get('rows', [])])
