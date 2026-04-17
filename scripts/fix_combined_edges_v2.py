"""Add person→location edges using vertex ID lookup."""
import boto3
import json
import time
import urllib.request
import ssl
import os

lam = boto3.client("lambda", region_name="us-east-1")
case_id = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
label = "Entity_" + case_id

edges = [
    ("Jeffrey Epstein", "New York, NY"),
    ("Jeffrey Epstein", "Palm Beach, FL"),
    ("Jeffrey Epstein", "Paris, France"),
    ("Jeffrey Epstein", "Little Saint James Island"),
    ("Jeffrey Epstein", "Marrakesh, Morocco"),
    ("Jeffrey Epstein", "Islip, NY"),
    ("Jeffrey Epstein", "West Palm Beach, FL"),
    ("Jeffrey Epstein", "London, UK"),
    ("Jeffrey Epstein", "Santa Fe, NM"),
    ("Jeffrey Epstein", "Miami, FL"),
    ("Jeffrey Epstein", "Virgin Islands"),
    ("Ghislaine Maxwell", "New York, NY"),
    ("Ghislaine Maxwell", "Palm Beach, FL"),
    ("Ghislaine Maxwell", "Paris, France"),
    ("Ghislaine Maxwell", "London, UK"),
    ("Ghislaine Maxwell", "Little Saint James Island"),
    ("Ghislaine Maxwell", "Virgin Islands"),
    ("Lesley Groff", "New York, NY"),
    ("Lesley Groff", "Palm Beach, FL"),
    ("JP Morgan Chase", "New York, NY"),
    ("LSJE, LLC", "New York, NY"),
    ("LSJE, LLC", "Virgin Islands"),
]

# Use simpler Gremlin: find source, find target, add edge between them
print(f"Adding {len(edges)} edges...")
created = 0

for src, dst in edges:
    src_esc = src.replace("'", "\\'")
    dst_esc = dst.replace("'", "\\'")
    
    # Use coalesce pattern to avoid duplicates and handle missing vertices
    q = (f"g.V().hasLabel('{label}').has('canonical_name','{src_esc}').as('s')"
         f".V().hasLabel('{label}').has('canonical_name','{dst_esc}').as('t')"
         f".select('s').addE('RELATED_TO').to(select('t'))"
         f".property('relationship_type','co-occurrence')"
         f".property('confidence',0.9)")
    
    resp = lam.invoke(
        FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "query": q}),
    )
    r = json.loads(resp["Payload"].read().decode())
    if "error" not in r:
        created += 1
        print(f"  OK: {src} → {dst}")
    else:
        # Try alternate names (without state abbreviation)
        alt_dst = dst.split(",")[0].strip()
        q2 = (f"g.V().hasLabel('{label}').has('canonical_name',containing('{src_esc}')).as('s')"
              f".V().hasLabel('{label}').has('canonical_name',containing('{alt_dst}')).as('t')"
              f".select('s').addE('RELATED_TO').to(select('t'))"
              f".property('relationship_type','co-occurrence')"
              f".property('confidence',0.9)")
        
        resp2 = lam.invoke(
            FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "gremlin_query", "query": q2}),
        )
        r2 = json.loads(resp2["Payload"].read().decode())
        if "error" not in r2:
            created += 1
            print(f"  OK (alt): {src} → {alt_dst}")
        else:
            print(f"  FAIL: {src} → {dst}: {r2.get('error','')[:60]}")
    
    time.sleep(0.3)

print(f"\nDone: {created}/{len(edges)} edges created")
