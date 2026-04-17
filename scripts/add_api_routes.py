"""Add missing API Gateway routes for all new modules."""
import boto3
import time

client = boto3.client('apigateway', region_name='us-east-1')
API_ID = 'edb025my3i'
LAMBDA_ARN = 'arn:aws:lambda:us-east-1:974220725866:function:ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'
REGION = 'us-east-1'
ACCOUNT = '974220725866'

# Get all existing resources
resources = client.get_resources(restApiId=API_ID, limit=500)['items']
path_to_id = {r['path']: r['id'] for r in resources}
print(f"Existing routes: {len(path_to_id)}")

# Find parent: /case-files/{id}
parent_id = path_to_id.get('/case-files/{id}')
root_id = path_to_id.get('/')
if not parent_id:
    print("ERROR: /case-files/{id} not found")
    exit(1)

def ensure_resource(parent, part):
    """Create resource if it doesn't exist, return resource ID."""
    # Check if already exists
    for r in resources:
        if r.get('parentId') == parent and r.get('pathPart') == part:
            print(f"  EXISTS: {part} -> {r['id']}")
            return r['id']
    resp = client.create_resource(restApiId=API_ID, parentId=parent, pathPart=part)
    rid = resp['id']
    resources.append({'id': rid, 'parentId': parent, 'pathPart': part, 'path': f'.../{part}'})
    print(f"  CREATED: {part} -> {rid}")
    return rid

def add_method(resource_id, method):
    """Add method + Lambda proxy integration."""
    try:
        client.put_method(restApiId=API_ID, resourceId=resource_id,
                         httpMethod=method, authorizationType='NONE')
    except client.exceptions.ConflictException:
        pass  # Method already exists
    uri = f'arn:aws:apigateway:{REGION}:lambda:path/2015-03-31/functions/{LAMBDA_ARN}/invocations'
    try:
        client.put_integration(restApiId=API_ID, resourceId=resource_id,
                              httpMethod=method, type='AWS_PROXY',
                              integrationHttpMethod='POST', uri=uri)
    except Exception:
        pass
    # Add Lambda permission
    stmt_id = f'apigw-{resource_id}-{method}'.replace('/', '-')
    try:
        boto3.client('lambda', region_name=REGION).add_permission(
            FunctionName=LAMBDA_ARN, StatementId=stmt_id,
            Action='lambda:InvokeFunction', Principal='apigateway.amazonaws.com',
            SourceArn=f'arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}/*/{method}/*')
    except Exception:
        pass  # Permission may already exist

def add_options(resource_id):
    """Add OPTIONS method with Lambda proxy for CORS."""
    add_method(resource_id, 'OPTIONS')

# === INVESTIGATOR AI ROUTES ===
print("\n--- Investigator AI Routes ---")
for part, methods in [
    ('investigative-leads', ['GET']),
    ('evidence-triage', ['GET']),
    ('ai-hypotheses', ['GET']),
    ('subpoena-recommendations', ['GET']),
    ('session-briefing', ['GET']),
    ('question-answer', ['POST']),
]:
    rid = ensure_resource(parent_id, part)
    for m in methods:
        add_method(rid, m)
    add_options(rid)
    print(f"  OK {part}: {', '.join(methods)}")

# === NETWORK DISCOVERY ROUTES ===
print("\n--- Network Discovery Routes ---")
for part, methods in [
    ('network-analysis', ['POST', 'GET']),
    ('persons-of-interest', ['GET']),
    ('sub-cases', ['POST']),
    ('network-patterns', ['GET']),
]:
    rid = ensure_resource(parent_id, part)
    for m in methods:
        add_method(rid, m)
    add_options(rid)
    print(f"  OK {part}: {', '.join(methods)}")

# persons-of-interest/{pid}
poi_id = path_to_id.get('/case-files/{id}/persons-of-interest')
if not poi_id:
    poi_id = ensure_resource(parent_id, 'persons-of-interest')
pid_id = ensure_resource(poi_id, '{pid}')
add_method(pid_id, 'GET')
add_options(pid_id)
print("  OK persons-of-interest/{pid}: GET")

# === PROSECUTOR ROUTES ===
print("\n--- Prosecutor Routes ---")
for part, methods in [
    ('element-assessment', ['POST', 'GET']),
    ('precedent-analysis', ['POST', 'GET']),
    ('case-weaknesses', ['POST', 'GET']),
    ('charging-memo', ['POST', 'GET']),
    ('decisions', ['GET']),
]:
    rid = ensure_resource(parent_id, part)
    for m in methods:
        add_method(rid, m)
    add_options(rid)
    print(f"  OK {part}: {', '.join(methods)}")

# /statutes
print("\n--- Statutes Routes ---")
stat_id = ensure_resource(root_id, 'statutes')
add_method(stat_id, 'GET')
add_options(stat_id)
stat_by_id = ensure_resource(stat_id, '{id}')
add_method(stat_by_id, 'GET')
add_options(stat_by_id)
print("  OK statutes: GET, statutes/{id}: GET")

# /decisions/{id}/confirm and /decisions/{id}/override
print("\n--- Decision Workflow Routes ---")
dec_id = ensure_resource(root_id, 'decisions')
dec_by_id = ensure_resource(dec_id, '{id}')
confirm_id = ensure_resource(dec_by_id, 'confirm')
add_method(confirm_id, 'POST')
add_options(confirm_id)
override_id = ensure_resource(dec_by_id, 'override')
add_method(override_id, 'POST')
add_options(override_id)
print("  OK decisions/{id}/confirm: POST")
print("  OK decisions/{id}/override: POST")

# === DOCUMENT ASSEMBLY ROUTES ===
print("\n--- Document Assembly Routes ---")
docs_id = path_to_id.get('/case-files/{id}/documents')
if not docs_id:
    docs_id = ensure_resource(parent_id, 'documents')
gen_id = ensure_resource(docs_id, 'generate')
add_method(gen_id, 'POST')
add_options(gen_id)
add_method(docs_id, 'GET')
print("  OK documents/generate: POST")

# documents/{doc_id}
doc_by_id_path = '/case-files/{id}/documents/{docId}'
doc_by_id = path_to_id.get(doc_by_id_path)
if doc_by_id:
    add_method(doc_by_id, 'GET')
    signoff_id = ensure_resource(doc_by_id, 'sign-off')
    add_method(signoff_id, 'POST')
    add_options(signoff_id)
    export_id = ensure_resource(doc_by_id, 'export')
    add_method(export_id, 'GET')
    add_options(export_id)
    print("  OK documents/{docId}: GET, sign-off: POST, export: GET")

# /case-files/{id}/discovery
disc_id = ensure_resource(parent_id, 'discovery')
add_method(disc_id, 'GET')
add_options(disc_id)
produce_id = ensure_resource(disc_id, 'produce')
add_method(produce_id, 'POST')
add_options(produce_id)
print("  OK discovery: GET, discovery/produce: POST")

# === TRAWLER / ALERT ROUTES ===
print("\n--- Trawler / Alert Routes ---")
# /case-files/{id}/trawl — POST
trawl_id = ensure_resource(parent_id, 'trawl')
add_method(trawl_id, 'POST')
add_options(trawl_id)
print("  OK trawl: POST")

# /case-files/{id}/trawl/history — GET
history_id = ensure_resource(trawl_id, 'history')
add_method(history_id, 'GET')
add_options(history_id)
print("  OK trawl/history: GET")

# /case-files/{id}/trawl-config — PUT, GET
trawl_config_id = ensure_resource(parent_id, 'trawl-config')
add_method(trawl_config_id, 'PUT')
add_method(trawl_config_id, 'GET')
add_options(trawl_config_id)
print("  OK trawl-config: PUT, GET")

# /case-files/{id}/alerts — GET
alerts_id = ensure_resource(parent_id, 'alerts')
add_method(alerts_id, 'GET')
add_options(alerts_id)
print("  OK alerts: GET")

# /case-files/{id}/alerts/{alert_id} — PATCH
alert_by_id = ensure_resource(alerts_id, '{alert_id}')
add_method(alert_by_id, 'PATCH')
add_options(alert_by_id)
print("  OK alerts/{alert_id}: PATCH")

# /case-files/{id}/alerts/{alert_id}/investigate — POST
investigate_id = ensure_resource(alert_by_id, 'investigate')
add_method(investigate_id, 'POST')
add_options(investigate_id)
print("  OK alerts/{alert_id}/investigate: POST")

# === DEPLOY ===
print("\n--- Deploying API ---")
try:
    client.create_deployment(restApiId=API_ID, stageName='v1',
                            description='Add all missing routes for new modules')
    print("OK Deployed to v1 stage")
except Exception as e:
    print(f"Deploy error: {e}")

print("\nDone. All routes added.")
