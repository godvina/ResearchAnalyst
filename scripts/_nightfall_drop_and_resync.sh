#!/bin/bash
# EC2 Userdata — Drop Neptune subgraph then re-sync for Operation Nightfall
# This DROPS all old vertices first, then loads fresh from Aurora
set -e
exec > >(tee /var/log/nightfall-drop-resync.log) 2>&1

BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="0b24a307-a674-41b6-8d22-581c4a4aa566"
CASE_LABEL="Entity_${CASE_ID}"
NEPTUNE="neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com"
REGION="us-east-1"

echo "=== Neptune DROP + Re-Sync: Operation Nightfall ==="
echo "Case: $CASE_ID"
echo "Label: $CASE_LABEL"
echo "Time: $(date)"

# Install deps
yum install -y python3-pip 2>&1 || true
pip3 install boto3 2>&1 || true

# Step 1: DROP all vertices with this case label from Neptune
echo ""
echo "=== STEP 1: Dropping all vertices with label $CASE_LABEL ==="
python3 -c "
import json, ssl, urllib.request

NEPTUNE = '$NEPTUNE'
LABEL = '$CASE_LABEL'

def gremlin(query, timeout=120):
    url = f'https://{NEPTUNE}:8182/gremlin'
    data = json.dumps({'gremlin': query}).encode()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return json.loads(resp.read())

# Count before
r = gremlin(f\"g.V().hasLabel('{LABEL}').count()\")
count = r.get('result', {}).get('data', {}).get('@value', [{}])[0].get('@value', 0) if isinstance(r.get('result', {}).get('data', {}), dict) else 0
try:
    count = r['result']['data']['@value'][0]['@value']
except:
    try:
        count = r['result']['data'][0]
    except:
        count = 'unknown'
print(f'  Vertices before drop: {count}')

# Drop in batches of 1000 to avoid timeout
batch = 0
while True:
    batch += 1
    r = gremlin(f\"g.V().hasLabel('{LABEL}').limit(1000).drop()\", timeout=120)
    # Check if any vertices remain
    r2 = gremlin(f\"g.V().hasLabel('{LABEL}').count()\")
    try:
        remaining = r2['result']['data']['@value'][0]['@value']
    except:
        try:
            remaining = r2['result']['data'][0]
        except:
            remaining = 0
    print(f'  Batch {batch}: dropped up to 1000, remaining: {remaining}')
    if remaining == 0 or batch > 20:
        break

print(f'  Drop complete. Vertices remaining: {remaining}')
"

echo ""
echo "=== STEP 2: Re-syncing clean entities from Aurora ==="

# Download and run the re-sync script
aws s3 cp s3://$BUCKET/deploy/ec2_neptune_resync.py /tmp/ec2_neptune_resync.py

cd /tmp
export CASE_ID=$CASE_ID
python3 ec2_neptune_resync.py --case-id $CASE_ID 2>&1 | tee -a /var/log/nightfall-drop-resync.log

# Upload log to S3
aws s3 cp /var/log/nightfall-drop-resync.log s3://$BUCKET/logs/neptune-resync/nightfall_drop_resync_$(date +%Y%m%d_%H%M%S).txt

echo ""
echo "=== DROP + Re-Sync Complete ==="
echo "NOTE: Manually terminate this instance."
