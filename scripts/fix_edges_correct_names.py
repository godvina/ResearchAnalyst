"""Add edges using the EXACT node names from Neptune."""
import boto3
import json
import time

lam = boto3.client("lambda", region_name="us-east-1")
case_id = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
label = "Entity_" + case_id

# Use exact names from Neptune (from the patterns query output)
edges = [
    ("Jeffrey Epstein", "New York"),
    ("Jeffrey Epstein", "Paris"),
    ("Jeffrey Epstein", "PARIS"),
    ("Jeffrey Epstein", "Washington"),
    ("Jeffrey Epstein", "Canada"),
    ("Jeffrey Epstein", "NY"),
    ("Jeffrey Epstein", "DC"),
    ("Ghislaine Maxwell", "New York"),
    ("Ghislaine Maxwell", "Paris"),
    ("Ghislaine Maxwell", "PARIS"),
    ("Ghislaine Maxwell", "London"),
    ("Ghislaine Maxwell", "Washington"),
    ("Lesley Groff", "New York"),
    ("Lesley Groff", "NY"),
    ("JP Morgan Chase", "New York"),
    ("LSJE, LLC", "New York"),
    ("LSJE, LLC", "NY"),
]

print(f"Adding {len(edges)} edges with correct Neptune names...")
created = 0

for src, dst in edges:
    src_esc = src.replace("'", "\\'")
    dst_esc = dst.replace("'", "\\'")
    
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
        print(f"  FAIL: {src} → {dst}: {r.get('error','')[:60]}")
    time.sleep(0.2)

print(f"\nDone: {created}/{len(edges)} edges")
