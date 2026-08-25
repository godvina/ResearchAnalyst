#!/usr/bin/env python3
"""One-shot clean indexer for the 25 UFO/UAP signatures into typology-patterns.

Assumes the ufos_uaps domain has ALREADY been cleared from the index (verified 0 docs).
No per-doc dedup — just embed + POST each signature once. Avoids the AOSS
refresh-lag race that duplicated docs when using search+delete per signature.
"""
import hashlib
import json
import os
import boto3
from requests_aws4auth import AWS4Auth
import requests

REGION = "us-east-1"
EP = "https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com"
INDEX = "typology-patterns"
EMBED_MODEL = "amazon.titan-embed-text-v2:0"
TAX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "src", "data", "ufo-uap-taxonomy.json")

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
sess = boto3.Session()
cr = sess.get_credentials()
auth = AWS4Auth(cr.access_key, cr.secret_key, REGION, "aoss", session_token=cr.token)


def embed(text):
    r = bedrock.invoke_model(modelId=EMBED_MODEL, contentType="application/json",
                             accept="application/json",
                             body=json.dumps({"inputText": text[:8000]}))
    return json.loads(r["body"].read())["embedding"]


with open(TAX, encoding="utf-8") as f:
    tax = json.load(f)

domain_id = tax["domain_id"]
n = 0
for typ in tax["typologies"]:
    for method in typ["methods"]:
        for sig in method["signatures"]:
            doc = {
                "pattern_id": sig["signature_id"],
                "description": sig["description"],
                "severity": sig["severity"],
                "typology": typ["typology_id"],
                "method": method["method_id"],
                "domain": domain_id,
                "precedent_case": sig.get("precedent_case", ""),
                "indicators": sig.get("indicators", []),
                "vector_hash": hashlib.md5(sig["vector_text"].encode()).hexdigest(),
                "embedding": embed(sig["vector_text"]),
            }
            resp = requests.post(f"{EP}/{INDEX}/_doc", auth=auth, json=doc, timeout=30)
            ok = resp.status_code < 300
            n += 1 if ok else 0
            print(f"[{n}] {sig['signature_id']} -> {resp.status_code}")

print(f"DONE: indexed {n} UFO signatures")
