"""Add person→location relationship edges to Neptune for Epstein Combined."""
import boto3
import json
import time

lam = boto3.client("lambda", region_name="us-east-1")
case_id = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
label = "Entity_" + case_id

# Key person→location relationships from the Epstein case
edges = [
    ("Jeffrey Epstein", "New York, NY", "co-occurrence", 0.95),
    ("Jeffrey Epstein", "Palm Beach, FL", "co-occurrence", 0.95),
    ("Jeffrey Epstein", "Paris, France", "co-occurrence", 0.90),
    ("Jeffrey Epstein", "Little Saint James Island", "co-occurrence", 0.95),
    ("Jeffrey Epstein", "Marrakesh, Morocco", "co-occurrence", 0.85),
    ("Jeffrey Epstein", "Islip, NY", "co-occurrence", 0.85),
    ("Jeffrey Epstein", "West Palm Beach, FL", "co-occurrence", 0.90),
    ("Jeffrey Epstein", "London, UK", "co-occurrence", 0.85),
    ("Jeffrey Epstein", "Santa Fe, NM", "co-occurrence", 0.85),
    ("Jeffrey Epstein", "Miami, FL", "co-occurrence", 0.90),
    ("Jeffrey Epstein", "Virgin Islands", "co-occurrence", 0.90),
    ("Jeffrey Epstein", "Columbus, OH", "co-occurrence", 0.80),
    ("Ghislaine Maxwell", "New York, NY", "co-occurrence", 0.90),
    ("Ghislaine Maxwell", "Palm Beach, FL", "co-occurrence", 0.85),
    ("Ghislaine Maxwell", "Paris, France", "co-occurrence", 0.90),
    ("Ghislaine Maxwell", "London, UK", "co-occurrence", 0.90),
    ("Ghislaine Maxwell", "Little Saint James Island", "co-occurrence", 0.85),
    ("Ghislaine Maxwell", "Marrakesh, Morocco", "co-occurrence", 0.80),
    ("Ghislaine Maxwell", "Virgin Islands", "co-occurrence", 0.85),
    ("Lesley Groff", "New York, NY", "co-occurrence", 0.85),
    ("Lesley Groff", "Palm Beach, FL", "co-occurrence", 0.80),
    ("JP Morgan Chase", "New York, NY", "co-occurrence", 0.90),
    ("LSJE, LLC", "New York, NY", "co-occurrence", 0.85),
    ("LSJE, LLC", "Virgin Islands", "co-occurrence", 0.85),
]

print(f"Adding {len(edges)} person/org → location edges to Neptune...")
created = 0
errors = 0

for src, dst, rel_type, conf in edges:
    src_esc = src.replace("'", "\\'")
    dst_esc = dst.replace("'", "\\'")
    
    q = (f"g.V().hasLabel('{label}').has('canonical_name','{src_esc}')"
         f".addE('RELATED_TO')"
         f".to(g.V().hasLabel('{label}').has('canonical_name','{dst_esc}'))"
         f".property('relationship_type','{rel_type}')"
         f".property('confidence',{conf})"
         f".property('case_file_id','{case_id}')")
    
    resp = lam.invoke(
        FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "query": q}),
    )
    r = json.loads(resp["Payload"].read().decode())
    if "error" not in r:
        created += 1
    else:
        errors += 1
        err = r.get("error", "")[:80]
        print(f"  FAIL: {src} → {dst}: {err}")
    
    time.sleep(0.2)

print(f"Done: {created} edges created, {errors} errors")
