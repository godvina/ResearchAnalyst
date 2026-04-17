"""Check if the document download route exists in API Gateway."""
import boto3

apigw = boto3.client("apigateway", region_name="us-east-1")
resources = apigw.get_resources(restApiId="edb025my3i", limit=200)["items"]

matches = [r for r in resources if "download" in r.get("path", "")]
print(f"Found {len(matches)} download routes:")
for r in matches:
    methods = list(r.get("resourceMethods", {}).keys())
    print(f"  {r['path']}  methods={methods}  id={r['id']}")

# Also check the case_files Lambda dispatch to see what resource path it expects
print("\nAll /case-files/{id}/documents paths:")
for r in resources:
    if "documents" in r.get("path", ""):
        methods = list(r.get("resourceMethods", {}).keys())
        print(f"  {r['path']}  methods={methods}")
