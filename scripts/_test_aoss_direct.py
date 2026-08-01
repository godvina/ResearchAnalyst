"""Direct AOSS test from local machine to check if we can list indexes and create one."""
import hashlib, json, boto3
import botocore.auth, botocore.awsrequest
from botocore.session import Session as BotocoreSession
from botocore.httpsession import URLLib3Session

endpoint = "https://u260nrrtc0q87ji8iu0k.us-east-1.aoss.amazonaws.com"
region = "us-east-1"

def aoss_request(method, path, body=None):
    body_bytes = body.encode() if body else b""
    headers = {"Content-Type": "application/json", "X-Amz-Content-Sha256": hashlib.sha256(body_bytes).hexdigest()}
    url = f"{endpoint}{path}"
    session = BotocoreSession()
    creds = session.get_credentials().get_frozen_credentials()
    req = botocore.awsrequest.AWSRequest(method=method, url=url, headers=headers, data=body_bytes)
    signer = botocore.auth.SigV4Auth(creds, "aoss", region)
    signer.add_auth(req)
    http = URLLib3Session()
    resp = http.send(req.prepare())
    return resp.status_code, resp.content.decode()[:500]

# Test 1: List indexes
print("=== GET /_cat/indices ===")
status, body = aoss_request("GET", "/_cat/indices")
print(f"  Status: {status}")
print(f"  Body: {body[:300]}")

# Test 2: Try to create a simple test index
print("\n=== PUT /test-kiro-index ===")
mapping = {"settings": {"index": {"number_of_shards": 1}}, "mappings": {"properties": {"text": {"type": "text"}}}}
status, body = aoss_request("PUT", "/test-kiro-index", json.dumps(mapping))
print(f"  Status: {status}")
print(f"  Body: {body[:300]}")

# Test 3: If create worked, delete it
if status in (200, 201):
    print("\n=== DELETE /test-kiro-index ===")
    status, body = aoss_request("DELETE", "/test-kiro-index")
    print(f"  Status: {status}")
