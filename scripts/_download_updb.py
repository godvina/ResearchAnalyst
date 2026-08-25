#!/usr/bin/env python3
"""Download the UPDB postgres dump (Git LFS) from uapublius/updb-importers.

The db/*.sql.gz files are Git LFS pointers. This resolves them via the LFS batch
API and downloads the real gzip bytes to docs/updb/.

Files:
  db/phenomenon.sql.gz       (~108MB) — the sightings/reports table (~318K)
  db/phenomenon_docs.sql.gz  — media/reference docs
"""
import hashlib
import json
import os
import sys
import urllib.request

REPO = "uapublius/updb-importers"
LFS_BATCH_URL = f"https://github.com/{REPO}.git/info/lfs/objects/batch"
POINTERS = {
    "phenomenon.sql.gz": ("5d1f290b4a69d1de6ba9ab29f1188dc9ae8396eb604ad9988ef9b45816ee4fb9", 108562074),
}
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "updb")


def resolve_and_download(name, oid, size):
    body = json.dumps({
        "operation": "download",
        "transfers": ["basic"],
        "objects": [{"oid": oid, "size": size}],
    }).encode()
    req = urllib.request.Request(
        LFS_BATCH_URL, data=body, method="POST",
        headers={
            "Accept": "application/vnd.git-lfs+json",
            "Content-Type": "application/vnd.git-lfs+json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        meta = json.loads(r.read())
    obj = meta["objects"][0]
    if "actions" not in obj or "download" not in obj["actions"]:
        raise SystemExit(f"No download action for {name}: {obj}")
    href = obj["actions"]["download"]["href"]
    headers = obj["actions"]["download"].get("header", {})

    out_path = os.path.join(OUT_DIR, name)
    print(f"Downloading {name} ({size/1e6:.1f} MB)...")
    dreq = urllib.request.Request(href, headers=headers)
    sha = hashlib.sha256()
    with urllib.request.urlopen(dreq, timeout=300) as resp, open(out_path, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            sha.update(chunk)
    got = sha.hexdigest()
    ok = got == oid
    print(f"  saved -> {out_path}  sha256 {'OK' if ok else 'MISMATCH'}")
    if not ok:
        print(f"  expected {oid}\n  got      {got}", file=sys.stderr)
    return out_path, ok


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, (oid, size) in POINTERS.items():
        resolve_and_download(name, oid, size)


if __name__ == "__main__":
    main()
