import boto3
s3 = boto3.client('s3', region_name='us-east-1')
r = s3.list_objects_v2(Bucket='research-analyst-data-lake-974220725866', Prefix='cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/raw/', MaxKeys=200)
exts = {}
for o in r.get('Contents', []):
    k = o['Key']
    ext = k.rsplit('.', 1)[-1].lower() if '.' in k.split('/')[-1] else 'no_ext'
    exts[ext] = exts.get(ext, 0) + 1
print(f"Sampled {sum(exts.values())} files, IsTruncated={r.get('IsTruncated')}")
for e, c in sorted(exts.items(), key=lambda x: -x[1]):
    img = ' <-- IMAGE' if e in ('jpg','jpeg','png','tiff','tif','gif','bmp') else ''
    print(f"  .{e}: {c}{img}")
