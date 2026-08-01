"""Count page_* files to determine which HuggingFace datasets are loaded."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
MAIN = "7f05e8d5-4492-4f19-8894-25367606db96"

page_files = []
doj_files = []
other_files = []

for offset in range(0, 76000, 5000):
    resp = lam.invoke(
        FunctionName=LAMBDA,
        Payload=json.dumps({
            "action": "get_documents_for_extraction",
            "case_id": MAIN,
            "limit": 100,
            "offset": offset,
            "max_text_length": 10,
        }),
    )
    data = json.loads(resp["Payload"].read())
    for d in data.get("docs", []):
        fn = d.get("filename", "")
        if fn.startswith("page_"):
            page_files.append(fn)
        elif fn.startswith("DOJ-"):
            doj_files.append(fn)
        elif fn:
            other_files.append(fn)

print(f"Sampled {len(page_files) + len(doj_files) + len(other_files)} files across 75K docs")
print(f"  page_* (HuggingFace): {len(page_files)}")
print(f"  DOJ-* (DOJ originals): {len(doj_files)}")
print(f"  Other: {len(other_files)}")

if page_files:
    nums = []
    for f in page_files:
        try:
            nums.append(int(f.replace("page_", "").split(".")[0]))
        except:
            pass
    if nums:
        print(f"\n  Page number range: {min(nums)} to {max(nums)}")
        print(f"  Unique pages sampled: {len(set(nums))}")
        print(f"  HuggingFace DS1-8 total: 42,182 pages")
        if max(nums) > 40000:
            print(f"  Coverage: DS1-8 appears FULLY loaded (max page > 40K)")
        else:
            print(f"  Coverage: PARTIAL (max page {max(nums)})")

if other_files:
    print(f"\n  Other file samples: {other_files[:10]}")
