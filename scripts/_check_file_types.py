"""Check file types in the case raw/ folder."""
import boto3
s3 = boto3.client('s3', region_name='us-east-1')
bucket = 'research-analyst-data-lake-974220725866'
case_id = 'ed0b6c27-3b6b-4255-b9d0-efe8f4383a99'
prefix = f'cases/{case_id}/raw/'

exts = {}
total = 0
paginator = s3.get_paginator('list_objects_v2')
for page in paginator.paginate(Bucket=bucket, Prefix=prefix, PaginationConfig={'MaxItems': 2000}):
    for obj in page.get('Contents', []):
        key = obj['Key']
        ext = key.rsplit('.', 1)[-1].lower() if '.' in key else 'no_ext'
        exts[ext] = exts.get(ext, 0) + 1
        total += 1

print(f'Total files: {total}')
print('File types:')
for ext, count in sorted(exts.items(), key=lambda x: -x[1]):
    is_image = ext in ('jpg', 'jpeg', 'png', 'tiff', 'tif', 'gif', 'bmp')
    marker = ' <-- IMAGE' if is_image else ''
    print(f'  .{ext}: {count}{marker}')
