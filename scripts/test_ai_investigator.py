"""Test the AI Investigator API."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

# Test 1: Get suspects and AI questions
print("=== Get Suspects + AI Questions ===")
r = lam.invoke(
    FunctionName=LAMBDA,
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "ai_investigator",
        "case_id": CASE_ID,
        "investigator_action": "get_suspects",
    }),
)
d = json.loads(r["Payload"].read().decode())
if "error" in d:
    print(f"ERROR: {d['error']}")
else:
    suspects = d.get("suspects", [])
    questions = d.get("questions", [])
    print(f"Total persons: {d.get('total_persons', '?')}")
    print(f"\nAI Questions ({len(questions)}):")
    for q in questions:
        print(f"  {q.get('icon', '?')} [{q.get('category', '?')}] {q.get('question', '?')}")
    print(f"\nTop Suspects ({len(suspects)}):")
    for s in suspects[:15]:
        print(f"  {s['name']}: {s['connections']} connections")

# Test 2: Analyze a specific suspect
if suspects:
    top_suspect = suspects[0]["name"]
    print(f"\n=== Analyze Suspect: {top_suspect} ===")
    r2 = lam.invoke(
        FunctionName=LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "ai_investigator",
            "case_id": CASE_ID,
            "investigator_action": "analyze_suspect",
            "suspect_name": top_suspect,
        }),
    )
    d2 = json.loads(r2["Payload"].read().decode())
    if "error" in d2:
        print(f"ERROR: {d2['error']}")
    else:
        print(f"Connections: {len(d2.get('connections', []))}")
        print(f"\nAI Analysis:\n{d2.get('analysis', '?')[:800]}")
        print(f"\nFollow-up Questions:")
        for fq in d2.get("follow_up_questions", []):
            print(f"  → {fq}")
