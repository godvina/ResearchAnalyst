"""Test AOSS access directly using boto3/botocore to isolate the 403 issue."""
import boto3
import json
import botocore.auth
import botocore.awsrequest
from botocore.session import Session as BotocoreSession
from botocore.httpsession import URLLib3Session

ENDPOINT = "https://u260nrrtc0q87ji8iu0k.us-east-1.aoss.amazonaws.com"
REGION = "us-east-1"

session = BotocoreSession()
credentials = session.get_credentials().get_frozen_credentials()

def aoss_request(method, path, body=None):
    url = f"{ENDPOINT}{path}"
    headers = {"Content-Type": "application/json"}
    body_bytes = body.encode("utf-8") if body else b""
    
    req = botocore.awsrequest.AWSRequest(
        method=method, url=url, headers=headers, data=body_bytes,
    )
    signer = botocore.auth.SigV4Auth(credentials, "aoss", REGION)
    signer.add_auth(req)
    
    prepared = req.prepare()
    http = URLLib3Session()
    resp = http.send(prepared)
    
    body_text = resp.content.decode("utf-8") if resp.content else ""
    return resp.status_code, body_text

# Test 1: List indices
print("=== Test 1: GET /_cat/indices ===")
status, body = aoss_request("GET", "/_cat/indices")
print(f"  Status: {status}")
print(f"  Body: {body[:300]}")

# Test 2: Check if index exists
print("\n=== Test 2: HEAD /test-index ===")
status, body = aoss_request("HEAD", "/test-index")
print(f"  Status: {status}")

# Test 3: Create a simple index
print("\n=== Test 3: PUT /test-index ===")
mapping = {
    "settings": {"index": {"knn": True}},
    "mappings": {
        "properties": {
            "text": {"type": "text"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {"name": "hnsw", "engine": "faiss"},
            },
        }
    },
}
status, body = aoss_request("PUT", "/test-index", json.dumps(mapping))
print(f"  Status: {status}")
print(f"  Body: {body[:300]}")

# Test 4: Try creating with the actual case index name
print("\n=== Test 4: PUT /case-test-123 ===")
status, body = aoss_request("PUT", "/case-test-123", json.dumps(mapping))
print(f"  Status: {status}")
print(f"  Body: {body[:300]}")
