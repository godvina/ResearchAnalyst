"""Debug typology findings - invoke Lambda with enhanced error context."""
import boto3
import json
import time

client = boto3.client('lambda', region_name='us-east-1')
logs_client = boto3.client('logs', region_name='us-east-1')
FUNCTION = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'
LOG_GROUP = '/aws/lambda/ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'

# Invoke the findings endpoint for Epstein Combined (ed0b6c27) which has 15,670 entities
case_id = 'ed0b6c27-1a2b-3c4d-5e6f-7a8b9c0d1e2f'
category = 'recruitment_grooming'

print(f"Testing: case={case_id[:8]}, category={category}")
print(f"This case has 15,670 entities per the case_files table.\n")

event = {
    'httpMethod': 'GET',
    'path': f'/case-files/{case_id}/typology/{category}/findings',
    'pathParameters': {'id': case_id},
    'queryStringParameters': {},
    'headers': {'content-type': 'application/json'}
}

# Invoke
start = time.time()
r = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event).encode(), LogType='Tail')
elapsed = time.time() - start

resp = json.loads(r['Payload'].read())
status = resp.get('statusCode', '?')
body = json.loads(resp.get('body', '{}'))

print(f"Status: {status} ({elapsed:.1f}s)")
print(f"Situations: {len(body.get('situations', []))}")

if body.get('error'):
    print(f"Error: {body['error']}")

# Decode the log tail
import base64
log_tail = r.get('LogResult', '')
if log_tail:
    decoded = base64.b64decode(log_tail).decode('utf-8', errors='replace')
    print(f"\n=== Lambda Log Tail ===")
    # Look for warning/error lines
    for line in decoded.split('\n'):
        if any(k in line.lower() for k in ['error', 'warning', 'failed', 'exception', 'entities', 'typology']):
            print(f"  {line.strip()}")
    # Also print last 10 lines
    print(f"\n=== Last 10 lines ===")
    lines = [l for l in decoded.split('\n') if l.strip()]
    for line in lines[-10:]:
        print(f"  {line.strip()[:150]}")
