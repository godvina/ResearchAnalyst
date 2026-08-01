import boto3, json, datetime
ec2 = boto3.client('ec2', region_name='us-east-1')
lam = boto3.client('lambda', region_name='us-east-1')

# EC2 state
r = ec2.describe_instances(InstanceIds=['i-052568e97c7b26874'])
inst = r['Reservations'][0]['Instances'][0]
state = inst['State']['Name']
launch = inst['LaunchTime']
elapsed = (datetime.datetime.now(datetime.timezone.utc) - launch).total_seconds() / 60
print(f"Neptune sync EC2: {state} ({elapsed:.0f} min)")

# Neptune count
r2 = lam.invoke(
    FunctionName='ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq',
    Payload=json.dumps({
        'action': 'gremlin_query',
        'case_id': '7f05e8d5-4492-4f19-8894-25367606db96',
        'query': "g.V().hasLabel('Entity_7f05e8d5-4492-4f19-8894-25367606db96').count()",
        'timeout': 15,
    })
)
d = json.loads(r2['Payload'].read())
print(f"Neptune nodes: {d.get('result', '?')}")
