"""Debug why entity inserts don't affect the NOT EXISTS count."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

# Get a doc that should be "missing entities"
r = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse",
    Payload=json.dumps({"action": "query_aurora_entities", "case_id": CASE_ID, "limit": 1, "offset": 0}))
d = json.loads(r["Payload"].read().decode())
print(f"Aurora entities total: {d.get('total', '?')}")

# Run a custom SQL query to check the actual data
# Use the gremlin_query action but with SQL... wait, that only does Gremlin.
# I need to add a debug SQL action. Let me use the backfill batch with batch_size=1
# and check what document_id it selects

r = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse",
    Payload=json.dumps({"action": "backfill_entities_batch", "case_id": CASE_ID, "batch_size": 1}))
batch = json.loads(r["Payload"].read().decode())
print(f"Batch result: {json.dumps(batch)}")

# The key question: does the entities table have a document_id column that matches documents.document_id?
# Let me check by looking at the entity count for this specific case
r = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse",
    Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}))
count = json.loads(r["Payload"].read().decode())
print(f"Count: has={count.get('has_entities_count')}, missing={count.get('missing_count')}")

# The has_entities_count query is: SELECT COUNT(DISTINCT document_id) FROM entities WHERE case_file_id = %s
# If this returns 40194, it means 40194 unique document_ids have entities
# The missing query is: NOT EXISTS (SELECT 1 FROM entities e WHERE e.document_id = d.document_id)
# If this returns 53811, it means 53811 documents have NO matching entity rows

# This could mean the entities table has document_ids that DON'T match the documents table
# (e.g., from Neptune sync which uses different IDs)
print(f"\nThe 40,194 'has entities' count comes from entities table document_ids")
print(f"The 53,811 'missing' count comes from documents that have NO matching entity")
print(f"These 40,194 entity document_ids may be from Neptune sync, not from the documents table")
print(f"The backfill is inserting new entities but they may have the SAME document_id as existing ones")
print(f"ON CONFLICT DO NOTHING would then silently drop them")
