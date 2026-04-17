"""Test fetching Nikity data via HuggingFace dataset viewer REST API."""
import json
import urllib.request

url = "https://datasets-server.huggingface.co/rows?dataset=Nikity/Epstein-Files&config=default&split=train&offset=0&length=5"
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode())

rows = data.get("rows", [])
print(f"Got {len(rows)} rows")
for r in rows:
    row = r.get("row", {})
    ds_id = row.get("dataset_id")
    doc_id = row.get("doc_id")
    ft = row.get("file_type")
    text = row.get("text_content") or ""
    print(f"  ds={ds_id}, doc={doc_id}, type={ft}, text_len={len(text)}")
