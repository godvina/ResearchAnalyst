"""Check AWS credentials and Bedrock access."""
import boto3

# Check identity
sts = boto3.client('sts')
identity = sts.get_caller_identity()
print(f"Account: {identity['Account']}")
print(f"ARN: {identity['Arn']}")

# Check Bedrock access
try:
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    # Quick test: embed a short text
    import json
    response = bedrock.invoke_model(
        modelId='amazon.titan-embed-text-v2:0',
        body=json.dumps({"inputText": "test embedding"}),
        contentType='application/json',
        accept='application/json'
    )
    result = json.loads(response['body'].read())
    embedding = result.get('embedding', [])
    print(f"Bedrock Titan Embed: OK ({len(embedding)} dimensions)")
except Exception as e:
    print(f"Bedrock error: {e}")

# Check Claude access
try:
    response = bedrock.invoke_model(
        modelId='anthropic.claude-sonnet-4-20250514-v1:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 50,
            "messages": [{"role": "user", "content": "Say 'hello' and nothing else."}]
        }),
        contentType='application/json',
        accept='application/json'
    )
    result = json.loads(response['body'].read())
    text = result['content'][0]['text']
    print(f"Bedrock Claude Sonnet 4: OK (response: {text})")
except Exception as e:
    print(f"Claude error: {e}")
