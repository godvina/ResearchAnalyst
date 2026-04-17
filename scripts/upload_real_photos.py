"""Download photos from Wikimedia Commons URLs and upload to S3."""
import io, json, boto3, urllib.request, time

BUCKET = "research-analyst-data-lake-974220725866"
CASE_IDS = [
    "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99",
    "7f05e8d5-4492-4f19-8894-25367606db96",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

with open("data/entity_photos.json") as f:
    data = json.load(f)

s3 = boto3.client("s3", region_name="us-east-1")

for name, info in data["persons"].items():
    url = info.get("url", "")
    if not url:
        print(f"  SKIP {name}: no URL")
        continue
    print(f"Downloading {name}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        resp = urllib.request.urlopen(req, timeout=15)
        img_bytes = resp.read()
        print(f"  Downloaded {len(img_bytes)} bytes")
        # Resize to 200x200
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        side = min(w, h)
        left, top = (w - side) // 2, (h - side) // 2
        img = img.crop((left, top, left + side, top + side)).resize((200, 200), Image.LANCZOS)
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        jpeg_bytes = buf.getvalue()
        # Upload to both cases
        for cid in CASE_IDS:
            key = f"cases/{cid}/face-crops/demo/{name}.jpg"
            s3.put_object(Bucket=BUCKET, Key=key, Body=jpeg_bytes, ContentType="image/jpeg")
            print(f"  Uploaded to {key}")
    except Exception as e:
        print(f"  FAILED {name}: {e}")
    time.sleep(1)

print("\nDone!")
