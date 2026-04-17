"""Test AOSS connectivity from Lambda by invoking a test function."""
import boto3
import json
import base64

REGION = "us-east-1"
lam = boto3.client("lambda", region_name=REGION)

# Create a simple test payload that the embed handler can use
# We'll invoke the embed Lambda directly with a minimal test
test_code = """
import socket
import ssl
import urllib.request
import os
import json

def test_connectivity():
    endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
    results = {}
    
    # Test 1: DNS resolution
    try:
        host = endpoint.replace("https://", "").rstrip("/")
        addrs = socket.getaddrinfo(host, 443)
        results["dns_ipv4"] = [a[4][0] for a in addrs if a[0] == socket.AF_INET]
        results["dns_ipv6"] = [a[4][0] for a in addrs if a[0] == socket.AF_INET6]
    except Exception as e:
        results["dns_error"] = str(e)
    
    # Test 2: TCP connection to IPv4
    if results.get("dns_ipv4"):
        ip = results["dns_ipv4"][0]
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, 443))
            results["tcp_ipv4"] = f"Connected to {ip}:443"
            s.close()
        except Exception as e:
            results["tcp_ipv4_error"] = str(e)
    
    # Test 3: HTTPS request
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(f"{endpoint}/_cat/indices", method="GET")
        req.add_header("Host", host)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            results["https"] = f"Status {resp.status}"
    except Exception as e:
        results["https_error"] = str(e)
    
    return results

print(json.dumps(test_connectivity(), indent=2))
"""

# We can't run arbitrary code in Lambda, but we can check the Lambda's env
# Let's just invoke the embed Lambda with a minimal event to see the error
print("Testing AOSS connectivity from Lambda...")
print("Invoking embed Lambda with a test event...")

# Actually, let's just check if the Lambda can resolve DNS
# by looking at the CloudWatch logs from the last execution
logs = boto3.client("logs", region_name=REGION)
log_group = "/aws/lambda/ResearchAnalystStack-IngestionEmbedLambdaE92F3BC0-wYlIRbksk1Jz"

try:
    streams = logs.describe_log_streams(
        logGroupName=log_group,
        orderBy="LastEventTime",
        descending=True,
        limit=3,
    )["logStreams"]
    
    for stream in streams[:1]:
        events = logs.get_log_events(
            logGroupName=log_group,
            logStreamName=stream["logStreamName"],
            limit=50,
        )["events"]
        print(f"\nLog stream: {stream['logStreamName']}")
        for event in events:
            msg = event["message"].strip()
            if msg and not msg.startswith("INIT_START") and not msg.startswith("END"):
                print(f"  {msg[:200]}")
except Exception as e:
    print(f"Could not read logs: {e}")
