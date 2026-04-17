"""Clean up OCR noise entities from Aurora."""
import boto3
import json

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

lam = boto3.client("lambda", region_name="us-east-1")

cleanup_queries = [
    # Generic OCR noise entities
    f"DELETE FROM entities WHERE case_file_id = '{CASE_ID}' AND canonical_name IN ('Doctor''s Name', 'Name', 'Relationship', 'Doctor', 'Address', 'Phone Number', 'Email', 'Date', 'Number', 'Unknown', 'N/A', 'None', 'null', '', 'EFTA', 'USG DUROCK', 'Document', 'Page', 'Case', 'File')",
    # Single character entities
    f"DELETE FROM entities WHERE case_file_id = '{CASE_ID}' AND LENGTH(canonical_name) <= 2",
    # Entities that are just numbers or phone-like patterns
    f"DELETE FROM entities WHERE case_file_id = '{CASE_ID}' AND canonical_name ~ '^[0-9\\-\\.\\s\\(\\)]+$'",
    # Entities with placeholder patterns
    f"DELETE FROM entities WHERE case_file_id = '{CASE_ID}' AND (canonical_name ILIKE '%xxx%' OR canonical_name ILIKE '%000-000%' OR canonical_name ILIKE 'page %' OR canonical_name ILIKE '1-800%')",
]

total_deleted = 0
for i, q in enumerate(cleanup_queries):
    try:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "admin_sql", "sql": q}),
        )
        body = json.loads(resp["Payload"].read().decode())
        rows = body.get("rows_affected", body.get("rowcount", "?"))
        print(f"  Query {i+1}: {rows} rows deleted")
        if isinstance(rows, int):
            total_deleted += rows
    except Exception as e:
        print(f"  Query {i+1} failed: {e}")

print(f"\n  Total deleted: {total_deleted}")

# Refresh stats
resp = lam.invoke(
    FunctionName=LAMBDA_NAME,
    InvocationType="RequestResponse",
    Payload=json.dumps({"action": "refresh_case_stats", "case_id": CASE_ID}),
)
stats = json.loads(resp["Payload"].read().decode())
print(f"  Stats: docs={stats.get('document_count','?')}, entities={stats.get('entity_count','?')}, rels={stats.get('relationship_count','?')}")
