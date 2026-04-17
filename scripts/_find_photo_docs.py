"""Search EFTA documents for key persons and photo references."""
import boto3

s3 = boto3.client('s3', region_name='us-east-1')
bucket = 'research-analyst-data-lake-974220725866'
case_id = '7f05e8d5-4492-4f19-8894-25367606db96'

targets = ['Jeffrey Epstein', 'Ghislaine Maxwell', 'Prince Andrew', 'Bill Clinton',
           'Alan Dershowitz', 'Les Wexner', 'Ehud Barak', 'Jean-Luc Brunel',
           'Sarah Kellen', 'Nadia Marcinkova', 'Donald Trump', 'Leon Black']

photo_keywords = ['photo', 'photograph', 'image', 'picture', 'mugshot', 'booking', 'portrait', 'headshot', 'depicted']
results = {}

paginator = s3.get_paginator('list_objects_v2')
count = 0
for page in paginator.paginate(Bucket=bucket, Prefix=f'cases/{case_id}/raw/EFTA'):
    for obj in page.get('Contents', []):
        if obj['Size'] < 50 or obj['Size'] > 50000:
            continue
        count += 1
        if count > 500:
            break
        try:
            body = s3.get_object(Bucket=bucket, Key=obj['Key'])['Body'].read().decode('utf-8', errors='ignore')
            text_lower = body.lower()
            for person in targets:
                if person.lower() in text_lower:
                    fname = obj['Key'].rsplit('/', 1)[-1]
                    bates = fname.replace('.txt', '')
                    if person not in results:
                        results[person] = []
                    has_photo_ref = any(kw in text_lower for kw in photo_keywords)
                    results[person].append({
                        'bates': bates, 'size': obj['Size'],
                        'has_photo_ref': has_photo_ref,
                        'snippet': body[:150].strip()
                    })
        except Exception:
            pass
    if count > 500:
        break

print(f"\nScanned {count} EFTA documents\n")
for person in targets:
    docs = results.get(person, [])
    photo_docs = [d for d in docs if d['has_photo_ref']]
    print(f"{person}: {len(docs)} docs, {len(photo_docs)} with photo refs")
    show = photo_docs[:3] if photo_docs else docs[:2]
    for d in show:
        tag = " [PHOTO]" if d['has_photo_ref'] else ""
        print(f"  {d['bates']} ({d['size']}b){tag}: {d['snippet'][:80]}...")
    print()
