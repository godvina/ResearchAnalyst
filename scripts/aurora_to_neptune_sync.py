"""Sync entities from Aurora to Neptune graph nodes via Gremlin."""
import boto3
import json
import time
import sys

LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
lam = boto3.client("lambda", region_name="us-east-1")

case_id = sys.argv[1] if len(sys.argv) > 1 else "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
label = "Entity_" + case_id

# Step 1: Get unique entity types from Aurora
print(f"Syncing Aurora entities to Neptune for {case_id}...")

# Use a custom query to get distinct entities
resp = lam.invoke(
    FunctionName=LAMBDA_NAME,
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query",
        "query": f"g.V().hasLabel('{label}').count()",
    }),
)
result = json.loads(resp["Payload"].read().decode())
print(f"Current Neptune nodes: {result}")

# Step 2: Get entities from Aurora that need to be in Neptune
# We'll query Aurora for distinct (canonical_name, entity_type) pairs
# and create Neptune nodes for each
resp = lam.invoke(
    FunctionName=LAMBDA_NAME,
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "query_aurora_entities",
        "case_id": case_id,
        "limit": 5000,
    }),
)
result = json.loads(resp["Payload"].read().decode())

if "entities" not in result:
    # Action doesn't exist yet - use gremlin to check what we have
    print(f"query_aurora_entities not available: {str(result)[:200]}")
    print("Using direct entity insert approach instead...")
    
    # Get entity types we know exist
    entity_types = ["person", "organization", "location", "date", "financial_amount", "event"]
    
    for etype in entity_types:
        # Query Neptune for existing entities of this type
        q = f"g.V().hasLabel('{label}').has('entity_type','{etype}').count()"
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "gremlin_query", "query": q}),
        )
        r = json.loads(resp["Payload"].read().decode())
        print(f"  Neptune {etype}: {r.get('result', '?')}")
    
    print("\nTo fully sync Aurora → Neptune, run the Step Functions pipeline")
    print("or use: python scripts/sync_neptune_to_aurora.py --case-id " + case_id)
else:
    entities = result["entities"]
    print(f"Got {len(entities)} entities from Aurora")
    
    created = 0
    for ent in entities:
        name = ent.get("name", "").replace("'", "\\'")
        etype = ent.get("type", "unknown")
        if not name or len(name) < 2:
            continue
        
        q = (f"g.addV('{label}')"
             f".property('canonical_name','{name}')"
             f".property('entity_type','{etype}')"
             f".property('confidence',0.9)"
             f".property('occurrence_count',1)"
             f".property('case_file_id','{case_id}')")
        
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "gremlin_query", "query": q}),
        )
        r = json.loads(resp["Payload"].read().decode())
        if "error" not in r:
            created += 1
        
        if created % 100 == 0 and created > 0:
            print(f"  Created {created} nodes...")
        time.sleep(0.1)
    
    print(f"Done: {created} nodes created in Neptune")
