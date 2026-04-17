"""Add top-patterns API Gateway routes and deploy."""
import boto3

client = boto3.client('apigateway', region_name='us-east-1')
API_ID = 'edb025my3i'
LAMBDA_ARN = 'arn:aws:lambda:us-east-1:974220725866:function:ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'
REGION = 'us-east-1'
ACCOUNT = '974220725866'

resources = client.get_resources(restApiId=API_ID, limit=500)['items']
path_to_id = {r['path']: r['id'] for r in resources}
parent_id = path_to_id.get('/case-files/{id}')
print("Parent /case-files/{id}:", parent_id)


def ensure_resource(parent, part):
    for r in resources:
        if r.get('parentId') == parent and r.get('pathPart') == part:
            print(f"  EXISTS: {part} -> {r['id']}")
            return r['id']
    resp = client.create_resource(restApiId=API_ID, parentId=parent, pathPart=part)
    rid = resp['id']
    resources.append({'id': rid, 'parentId': parent, 'pathPart': part})
    print(f"  CREATED: {part} -> {rid}")
    return rid


def add_method(resource_id, method):
    try:
        client.put_method(restApiId=API_ID, resourceId=resource_id,
                          httpMethod=method, authorizationType='NONE')
    except client.exceptions.ConflictException:
        pass
    uri = f'arn:aws:apigateway:{REGION}:lambda:path/2015-03-31/functions/{LAMBDA_ARN}/invocations'
    try:
        client.put_integration(restApiId=API_ID, resourceId=resource_id,
                               httpMethod=method, type='AWS_PROXY',
                               integrationHttpMethod='POST', uri=uri)
    except Exception:
        pass
    stmt_id = f'apigw-{resource_id}-{method}'.replace('/', '-')
    try:
        boto3.client('lambda', region_name=REGION).add_permission(
            FunctionName=LAMBDA_ARN, StatementId=stmt_id,
            Action='lambda:InvokeFunction', Principal='apigateway.amazonaws.com',
            SourceArn=f'arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}/*/{method}/*')
    except Exception:
        pass


print("Adding top-patterns routes...")
tp_id = ensure_resource(parent_id, 'top-patterns')
add_method(tp_id, 'GET')
add_method(tp_id, 'OPTIONS')
print("  OK top-patterns: GET, OPTIONS")

# /case-files/{id}/top-patterns/{patternIndex}
tp_idx = ensure_resource(tp_id, '{patternIndex}')
add_method(tp_idx, 'OPTIONS')

# /case-files/{id}/top-patterns/{patternIndex}/evidence
ev_id = ensure_resource(tp_idx, 'evidence')
add_method(ev_id, 'GET')
add_method(ev_id, 'OPTIONS')
print("  OK top-patterns/{patternIndex}/evidence: GET, OPTIONS")

print("Deploying...")
client.create_deployment(restApiId=API_ID, stageName='v1',
                         description='Add top-patterns routes')
print("DONE - deployed to v1")
