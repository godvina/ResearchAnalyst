"""Test the get_documents_for_extraction Lambda action."""
import boto3
import json
import time

time.sleep(10)  # Wait for Lambda update

lam = boto3.client("lambda", region_name="us-east-1")
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps({
        "action": "get_documents_for_extraction",
        "case_id": "7f05e8d5-4492-4f19-8894-25367606db96",
        "limit": 3,
        "offset": 0,
    }),
)
data = json.loads(resp["Payload"].read())
total = data.get("total", "error")
docs = data.get("docs", [])
print(f"Total documents with text (>= 50 chars): {total}")
for d in docs:
    text = d.get("raw_text", "")
    did = d.get("document_id", "?")[:12]
    fname = d.get("filename", "?")[:40]
    print(f"  {did}  {fname:40s}  {len(text):6d} chars")
    print(f"    Preview: {text[:120]}...")
if "error" in data:
    print(f"Error: {data['error']}")
