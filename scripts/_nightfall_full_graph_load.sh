#!/bin/bash
# EC2 Userdata — FULL Neptune Graph Load for Operation Nightfall
# Step 1: Drop old vertices
# Step 2: Load ALL entities (no type filtering, junk filter only)
# Step 3: Load ALL edges (MIN_OCCURRENCE = 1)
set -e
exec > >(tee /var/log/nightfall-full-load.log) 2>&1

BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="0b24a307-a674-41b6-8d22-581c4a4aa566"
CASE_LABEL="Entity_${CASE_ID}"
NEPTUNE="neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com"
REGION="us-east-1"

echo "=========================================="
echo "FULL NEPTUNE GRAPH LOAD: Operation Nightfall"
echo "Case: $CASE_ID"
echo "Time: $(date)"
echo "=========================================="

# Install deps
yum install -y python3-pip 2>&1 || true
pip3 install boto3 2>&1 || true

# ── STEP 1: DROP all existing vertices ──
echo ""
echo "=== STEP 1: DROP all vertices with label $CASE_LABEL ==="
python3 -c "
import json, ssl, urllib.request, time

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
try:
    r = gremlin(f\"g.V().hasLabel('{LABEL}').count()\")
    count = r['result']['data']['@value'][0]['@value']
except:
    count = 'unknown'
print(f'  Vertices before drop: {count}')

# Drop in batches
batch = 0
while True:
    batch += 1
    gremlin(f\"g.V().hasLabel('{LABEL}').limit(1000).drop()\", timeout=120)
    time.sleep(0.5)
    try:
        r2 = gremlin(f\"g.V().hasLabel('{LABEL}').count()\")
        remaining = r2['result']['data']['@value'][0]['@value']
    except:
        remaining = 0
    print(f'  Batch {batch}: remaining={remaining}')
    if remaining == 0 or batch > 30:
        break

print(f'  DROP COMPLETE. Remaining: {remaining}')
"

# ── STEP 2: Load ALL vertices ──
echo ""
echo "=== STEP 2: Load ALL entities from Aurora (no type filter, junk filter only) ==="
aws s3 cp s3://$BUCKET/deploy/ec2_neptune_resync.py /tmp/ec2_neptune_resync.py
cd /tmp
export CASE_ID=$CASE_ID
python3 ec2_neptune_resync.py --case-id $CASE_ID 2>&1

# ── STEP 3: Load ALL edges ──
echo ""
echo "=== STEP 3: Load ALL edges (MIN_OCCURRENCE=1) ==="
aws s3 cp s3://$BUCKET/deploy/neptune_edge_sync.py /tmp/neptune_edge_sync.py
python3 neptune_edge_sync.py --case-id $CASE_ID 2>&1

# Upload full log
aws s3 cp /var/log/nightfall-full-load.log s3://$BUCKET/logs/neptune-resync/nightfall_full_load_$(date +%Y%m%d_%H%M%S).txt

echo ""
echo "=========================================="
echo "FULL GRAPH LOAD COMPLETE"
echo "Time: $(date)"
echo "=========================================="
echo "NOTE: Manually terminate this instance."
