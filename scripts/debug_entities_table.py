"""Debug the entities table to understand why inserts are silently dropped."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

# First, get a document that's "missing entities"
r = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse",
    Payload=json.dumps({"action": "backfill_entities_batch", "case_id": CASE_ID, "batch_size": 1}))
batch = json.loads(r["Payload"].read().decode())
print(f"Batch: {json.dumps(batch)}")

# Now add a custom debug action to check the table
# Use the query_aurora_entities action to check entity count per document
r2 = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse",
    Payload=json.dumps({"action": "query_aurora_entities", "case_id": CASE_ID, "limit": 5, "offset": 0}))
d2 = json.loads(r2["Payload"].read().decode())
print(f"\nAurora entities total distinct: {d2.get('total', '?')}")
if "entities" in d2:
    for e in d2["entities"][:5]:
        print(f"  {e['name']} ({e['type']}): {e['count']}")

# The key question: are the entities being inserted with document_id or not?
# The ON CONFLICT DO NOTHING needs a unique constraint to conflict on.
# If there's no unique constraint, ON CONFLICT DO NOTHING does nothing (no conflict possible).
# But if there IS a unique constraint on (case_file_id, canonical_name, entity_type),
# then inserting the same entity name for the same case would conflict even for different documents.

print("\nThe issue is likely:")
print("1. ON CONFLICT DO NOTHING has no conflict target specified")
print("2. There's a unique constraint on (case_file_id, canonical_name, entity_type)")
print("3. The same entity names are being extracted for different documents")
print("4. The first insert succeeds, subsequent inserts for the same entity name are dropped")
print("5. But the NOT EXISTS checks document_id, not entity name")
print("\nFix: Change ON CONFLICT DO NOTHING to specify the conflict target,")
print("or remove ON CONFLICT and use INSERT ... WHERE NOT EXISTS instead")
