import boto3
j = boto3.client('bedrock', region_name='us-east-1').get_model_invocation_job(
    jobIdentifier='arn:aws:bedrock:us-east-1:974220725866:model-invocation-job/ldhi23bwhsje')
print(j['status'], j.get('message', 'ok'))
