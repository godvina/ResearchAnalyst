import boto3
b = boto3.client('bedrock', region_name='us-east-1')

# First list models that support batch inference
models = b.list_foundation_models()
batch_models = [m for m in models['modelSummaries'] 
                if 'BATCH' in str(m.get('inferenceTypesSupported', []))]
print("Models supporting batch inference in us-east-1:")
for m in batch_models:
    if any(x in m['modelId'].lower() for x in ['claude', 'haiku', 'sonnet', 'titan', 'nova']):
        print(f"  {m['modelId']} - {m.get('modelLifecycle',{}).get('status','active')}")

# Try submitting with Claude 3 Sonnet (non-legacy, commonly available)
print("\nTrying to submit with available models...")
candidates = [
    'anthropic.claude-3-haiku-20240307-v1:0',
    'anthropic.claude-3-5-haiku-20241022-v1:0', 
    'anthropic.claude-3-sonnet-20240229-v1:0',
    'anthropic.claude-3-5-sonnet-20241022-v2:0',
    'anthropic.claude-3-5-sonnet-20240620-v1:0',
    'amazon.nova-lite-v1:0',
    'amazon.nova-micro-v1:0',
]
for model_id in candidates:
    try:
        r = b.create_model_invocation_job(
            jobName=f'entity-extract-{model_id.split(".")[1][:10]}',
            modelId=model_id,
            roleArn='arn:aws:iam::974220725866:role/BedrockBatchInferenceRole',
            inputDataConfig={'s3InputDataConfig': {'s3Uri': 's3://research-analyst-data-lake-974220725866/batch-inference/entity-extraction/7f05e8d5-4492-4f19-8894-25367606db96/input/'}},
            outputDataConfig={'s3OutputDataConfig': {'s3Uri': 's3://research-analyst-data-lake-974220725866/batch-inference/entity-extraction/7f05e8d5-4492-4f19-8894-25367606db96/output/'}},
        )
        print(f'SUCCESS with {model_id}! Job ARN: {r["jobArn"]}')
        break
    except Exception as e:
        err = str(e)[:120]
        print(f'  {model_id}: {err}')
