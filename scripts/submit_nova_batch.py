import boto3
b = boto3.client('bedrock', region_name='us-east-1')
try:
    r = b.create_model_invocation_job(
        jobName='entity-extract-nova-v3',
        modelId='amazon.nova-lite-v1:0',
        roleArn='arn:aws:iam::974220725866:role/BedrockBatchInferenceRole',
        inputDataConfig={'s3InputDataConfig': {'s3Uri': 's3://research-analyst-data-lake-974220725866/batch-inference/entity-extraction/7f05e8d5-4492-4f19-8894-25367606db96/input/'}},
        outputDataConfig={'s3OutputDataConfig': {'s3Uri': 's3://research-analyst-data-lake-974220725866/batch-inference/entity-extraction/7f05e8d5-4492-4f19-8894-25367606db96/output-v3/'}},
    )
    print('SUCCESS! Job ARN:', r['jobArn'])
except Exception as e:
    print('ERROR:', e)
