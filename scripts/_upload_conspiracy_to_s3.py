"""Upload all conspiracy findings to S3 for indexing alongside Epstein/SNAP/etc.

This triggers the existing Lambda pipeline which indexes into OpenSearch,
enabling cross-case k-NN search across ALL datasets.
"""
import boto3
import json
import os
from datetime import datetime, timezone

s3 = boto3.client('s3')
BUCKET = 'research-analyst-data-lake-974220725866'
PREFIX = 'data-lake/conspiracy-theories'

# Check current state
print("Checking S3 access...")
try:
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=f'{PREFIX}/', MaxKeys=10)
    existing = resp.get('Contents', [])
    print(f"  Existing files: {len(existing)}")
    for obj in existing[:5]:
        print(f"    {obj['Key']} ({obj['Size']//1024} KB)")
except Exception as e:
    print(f"  Error: {e}")
    exit(1)

# Load all our processed claims
print("\nLoading processed claims...")
with open('src/frontend/theory-registry-data.js', 'r', encoding='utf-8') as f:
    content = f.read()
claims = json.loads(content.split('const THEORY_DATA = ')[1].rstrip(';\n'))
print(f"  Total claims: {len(claims)}")

# Group by dataset
datasets = {}
for c in claims:
    ds = c.get('dataset', 'unknown')
    if ds not in datasets:
        datasets[ds] = []
    datasets[ds].append(c)

print(f"  Datasets: {len(datasets)}")

# Upload each dataset as a JSON file to S3
print("\nUploading to S3...")
uploaded = 0
for ds_name, ds_claims in datasets.items():
    # Create a document for each dataset with all its claims
    doc = {
        'dataset_name': ds_name,
        'upload_timestamp': datetime.now(timezone.utc).isoformat(),
        'claim_count': len(ds_claims),
        'claims': ds_claims,
        'cross_domain_scoring': True,
        'tenant_id': 'conspiracy_theories',
    }
    
    key = f"{PREFIX}/{ds_name}/processed_claims.json"
    body = json.dumps(doc, ensure_ascii=False)
    
    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=body.encode('utf-8'),
            ContentType='application/json',
            Metadata={
                'dataset': ds_name,
                'claim_count': str(len(ds_claims)),
                'tenant': 'conspiracy_theories',
            }
        )
        uploaded += 1
        print(f"  ✓ {key} ({len(body)//1024} KB, {len(ds_claims)} claims)")
    except Exception as e:
        print(f"  ✗ {ds_name}: {e}")

# Also upload the cross-dataset convergence scan
convergence_path = 'src/data/cross-dataset-convergence-scan.json'
if os.path.exists(convergence_path):
    with open(convergence_path, 'r', encoding='utf-8') as f:
        convergence = f.read()
    s3.put_object(
        Bucket=BUCKET,
        Key=f"{PREFIX}/_cross_dataset_convergence.json",
        Body=convergence.encode('utf-8'),
        ContentType='application/json',
    )
    print(f"  ✓ Cross-dataset convergence scan uploaded")
    uploaded += 1

# Upload individual proof engine result files
result_files = [f for f in os.listdir('src/data') if f.startswith('proof-engine-results')]
for fname in result_files:
    fpath = os.path.join('src/data', fname)
    theory = fname.replace('proof-engine-results-', '').replace('.json', '')
    key = f"{PREFIX}/{theory}/proof_engine_results.json"
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            body = f.read()
        s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode('utf-8'), ContentType='application/json')
        uploaded += 1
        print(f"  ✓ {key} ({len(body)//1024} KB)")
    except Exception as e:
        print(f"  ✗ {fname}: {e}")

print(f"\n{'='*60}")
print(f"UPLOAD COMPLETE: {uploaded} files to s3://{BUCKET}/{PREFIX}/")
print(f"This triggers the existing Lambda pipeline for OpenSearch indexing.")
print(f"Cross-case k-NN search will now find conspiracy claims alongside Epstein, SNAP, etc.")
