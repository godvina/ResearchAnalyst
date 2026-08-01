"""Test the CORRECT AOSS endpoint."""
import hashlib, json
import botocore.auth, botocore.awsrequest
from botocore.session import Session as BotocoreSession
from botocore.httpsession import URLLib3Session

# The CORRECT endpoint (collection hzrvvva3hodw069v9442, not u260nrrtc0q87ji8iu0k)
endpoint = "https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com"

def aoss_req(method, path, body=None):
    session = BotocoreSession()
    creds = session.get_credentials().get_frozen_credentials()
    body_bytes = body.encode() if body else b""
    headers = {"Content-Type": "application/json", "X-Amz-Content-Sha256": hashlib.sha256(body_bytes).hexdigest()}
    url = endpoint + path
    req = botocore.awsrequest.AWSRequest(method=method, url=url, headers=headers, data=body_bytes)
    signer = botocore.auth.SigV4Auth(creds, "aoss", "us-east-1")
    signer.add_auth(req)
    http = URLLib3Session()
    resp = http.send(req.prepare())
    return resp.status_code, resp.content.decode()[:500]

print("=== GET /_cat/indices (correct endpoint) ===")
status, body = aoss_req("GET", "/_cat/indices")
print(f"  Status: {status}")
print(f"  Body: {body[:300]}")

print("\n=== PUT /test-kiro-index ===")
mapping = {"settings": {"index": {"number_of_shards": 1}}, "mappings": {"properties": {"text": {"type": "text"}}}}
status, body = aoss_req("PUT", "/test-kiro-index", json.dumps(mapping))
print(f"  Status: {status}")
print(f"  Body: {body[:300]}")

if status in (200, 201):
    print("\n=== DELETE /test-kiro-index ===")
    status, body = aoss_req("DELETE", "/test-kiro-index")
    print(f"  Status: {status}")
    print("  SUCCESS! AOSS writes work on the correct endpoint!")
