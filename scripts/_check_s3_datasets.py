"""Check all datasets in S3."""
import boto3

s3 = boto3.client('s3')
bucket = 'research-analyst-data-lake-974220725866'

# Top-level
print("ALL S3 PREFIXES:")
print("=" * 60)
resp = s3.list_objects_v2(Bucket=bucket, Delimiter='/', MaxKeys=200)
for p in resp.get('CommonPrefixes', []):
    prefix = p['Prefix']
    # Count objects in this prefix
    count_resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=5)
    count = count_resp.get('KeyCount', 0)
    print(f"  {prefix:40s} ({count}+ objects)")

# Epstein specific
print("\n\nEPSTEIN-RELATED DATA:")
print("=" * 60)
for prefix in ['epstein/', 'epstein-files/', 'data-lake/epstein', 'case-']:
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter='/', MaxKeys=50)
    prefixes = resp.get('CommonPrefixes', [])
    files = resp.get('Contents', [])
    if prefixes or files:
        print(f"\n  Prefix: {prefix}")
        for p in prefixes[:10]:
            print(f"    {p['Prefix']}")
        for f in files[:5]:
            size_mb = f['Size'] / 1024 / 1024
            print(f"    {f['Key']} ({size_mb:.1f} MB)")
