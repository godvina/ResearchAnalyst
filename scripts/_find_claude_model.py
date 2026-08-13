"""Find available Claude models and inference profiles."""
import boto3

bedrock = boto3.client('bedrock', region_name='us-east-1')

# List inference profiles
print("=== Inference Profiles (Claude/Sonnet) ===")
try:
    profiles = bedrock.list_inference_profiles()
    for p in profiles.get('inferenceProfileSummaries', []):
        pid = p.get('inferenceProfileId', '')
        if 'claude' in pid.lower() or 'sonnet' in pid.lower() or 'anthropic' in pid.lower():
            print(f"  {pid}")
except Exception as e:
    print(f"  Error listing profiles: {e}")

# List foundation models
print("\n=== Foundation Models (Anthropic) ===")
try:
    r = bedrock.list_foundation_models(byProvider='Anthropic')
    for m in r['modelSummaries']:
        if 'sonnet' in m['modelId'].lower() or 'haiku' in m['modelId'].lower():
            print(f"  {m['modelId']}: {m['modelName']}")
except Exception as e:
    print(f"  Error: {e}")
