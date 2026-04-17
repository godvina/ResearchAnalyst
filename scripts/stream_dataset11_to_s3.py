"""Stream DataSet 11 from zip directly to S3 — no local extraction needed.

Downloads the zip to disk (~27.5 GB), then reads each file from the zip
in memory and uploads directly to S3. Extracted files never touch disk.

Disk needed: ~27.5 GB for the zip only (vs ~55 GB with extract).
"""
import io
import os
import sys
import time
import zipfile

import boto3
import requests

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
S3_PREFIX = f"cases/{CASE_ID}/raw/"
DOWNLOAD_DIR = "./epstein_downloads"

URLS_11 = [
    "https://www.justice.gov/epstein/files/DataSet%2011.zip",
    "https://doj-files.geeken.dev/doj_zips/original_archives/DataSet%2011.zip",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/zip, application/octet-stream, */*",
}

DOC_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx", ".xls", ".xlsx", ".html", ".htm", ".eml", ".msg"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".gif", ".bmp"}

s3 = boto3.client("s3", region_name=REGION)


def get_existing_files():
    """List all files already in S3 for dedup."""
    existing = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=S3_PREFIX):
        for obj in page.get("Contents", []):
            filename = obj["Key"].split("/")[-1].lower()
            existing.add(filename)
    print(f"[dedup] Found {len(existing)} existing files in S3")
    return existing


def download_zip(urls, dest_path, max_retries=10):
    """Download zip file with resume support. Retries on timeout."""
    if os.path.exists(dest_path):
        try:
            with zipfile.ZipFile(dest_path, "r") as zf:
                zf.namelist()
            size_gb = os.path.getsize(dest_path) / (1024**3)
            print(f"[download] Zip already exists and valid: {dest_path} ({size_gb:.1f} GB)")
            return True
        except (zipfile.BadZipFile, Exception):
            # Partial file — keep it for resume
            size_mb = os.path.getsize(dest_path) / (1024**2)
            print(f"[download] Partial file found ({size_mb:.0f} MB), will resume...")

    # Find a working URL first
    working_url = None
    for url in urls:
        try:
            resp = requests.head(url, headers=HEADERS, timeout=30, allow_redirects=True)
            if "text/html" not in resp.headers.get("Content-Type", ""):
                working_url = url
                print(f"[download] Using: {url}")
                break
            else:
                print(f"[download] {url} returned HTML, skipping...")
        except Exception as e:
            print(f"[download] {url} failed HEAD: {e}")

    if not working_url:
        print("[download] ERROR: No working URLs found")
        return False

    for attempt in range(1, max_retries + 1):
        try:
            # Check how much we already have
            existing_size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
            req_headers = dict(HEADERS)
            if existing_size > 0:
                req_headers["Range"] = f"bytes={existing_size}-"
                print(f"[download] Resuming from {existing_size / (1024**2):.0f} MB (attempt {attempt}/{max_retries})")

            resp = requests.get(working_url, headers=req_headers, stream=True, timeout=300, allow_redirects=True)

            # If server doesn't support Range, start over
            if existing_size > 0 and resp.status_code == 200:
                print("[download] Server doesn't support resume, starting over...")
                existing_size = 0

            if resp.status_code == 416:  # Range not satisfiable — file is complete
                print("[download] File already fully downloaded")
                break

            total = int(resp.headers.get("Content-Length", 0)) + existing_size
            downloaded = existing_size
            start = time.time()
            mode = "ab" if existing_size > 0 and resp.status_code == 206 else "wb"

            with open(dest_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    elapsed = time.time() - start
                    new_bytes = downloaded - existing_size
                    speed = new_bytes / (1024 * 1024 * max(elapsed, 0.1))
                    if total > 0:
                        pct = downloaded * 100 / total
                        sys.stdout.write(f"\r[download] {downloaded/(1024**2):.0f}/{total/(1024**2):.0f} MB ({pct:.1f}%) — {speed:.1f} MB/s")
                    else:
                        sys.stdout.write(f"\r[download] {downloaded/(1024**2):.0f} MB — {speed:.1f} MB/s")
                    sys.stdout.flush()

            print(f"\n[download] Complete: {os.path.getsize(dest_path) / (1024**3):.1f} GB")

            # Verify
            with zipfile.ZipFile(dest_path, "r") as zf:
                zf.namelist()
            return True

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            print(f"\n[download] Connection lost (attempt {attempt}/{max_retries}): {type(e).__name__}")
            saved = os.path.getsize(dest_path) / (1024**2) if os.path.exists(dest_path) else 0
            print(f"[download] Saved {saved:.0f} MB so far, retrying in 10s...")
            time.sleep(10)
        except Exception as e:
            if "IncompleteRead" in str(e) or "broken" in str(e).lower():
                print(f"\n[download] Connection broken (attempt {attempt}/{max_retries}): {e}")
                saved = os.path.getsize(dest_path) / (1024**2) if os.path.exists(dest_path) else 0
                print(f"[download] Saved {saved:.0f} MB so far, retrying in 10s...")
                time.sleep(10)
            else:
                print(f"\n[download] Unexpected error: {e}")
                break

    # Final check — maybe it completed despite errors
    if os.path.exists(dest_path):
        try:
            with zipfile.ZipFile(dest_path, "r") as zf:
                zf.namelist()
            return True
        except Exception:
            pass

    print("[download] ERROR: Download failed after all retries")
    return False


def stream_zip_to_s3(zip_path, existing_files):
    """Read files from zip in memory and upload directly to S3."""
    uploaded = 0
    skipped_dedup = 0
    skipped_type = 0
    errors = 0
    start = time.time()

    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.namelist() if not m.endswith("/")]
        total = len(members)
        print(f"[stream] Zip contains {total} file entries")

        for i, member in enumerate(members, 1):
            filename = os.path.basename(member)
            if not filename:
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in DOC_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
                skipped_type += 1
                continue

            if filename.lower() in existing_files:
                skipped_dedup += 1
                continue

            try:
                data = zf.read(member)
                s3_key = S3_PREFIX + filename
                s3.put_object(Bucket=BUCKET, Key=s3_key, Body=data)
                existing_files.add(filename.lower())
                uploaded += 1

                if uploaded % 100 == 0:
                    elapsed = time.time() - start
                    rate = uploaded / max(elapsed / 60, 0.01)
                    print(f"[stream] {uploaded} uploaded, {skipped_dedup} dedup, {skipped_type} skipped type "
                          f"({i}/{total} processed, {rate:.0f} files/min)")

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"[stream] Error uploading {filename}: {e}")

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"[DONE] DataSet 11 → S3 complete in {elapsed/60:.1f} minutes")
    print(f"  Uploaded:     {uploaded}")
    print(f"  Skipped dedup: {skipped_dedup}")
    print(f"  Skipped type:  {skipped_type}")
    print(f"  Errors:        {errors}")
    print(f"{'='*60}")
    return uploaded


def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    zip_path = os.path.join(DOWNLOAD_DIR, "DataSet_11.zip")

    print("=" * 60)
    print("DataSet 11 → S3 Streamer (no local extraction)")
    print(f"Bucket: {BUCKET}")
    print(f"Case: {CASE_ID}")
    print("=" * 60)

    existing = get_existing_files()

    if not download_zip(URLS_11, zip_path):
        sys.exit(1)

    uploaded = stream_zip_to_s3(zip_path, existing)

    if uploaded > 0:
        print(f"\nTo process these documents through the pipeline, run:")
        print(f"  python scripts/process_new_epstein_pdfs.py")

    # Optionally delete the zip to reclaim space
    if os.path.exists(zip_path):
        size_gb = os.path.getsize(zip_path) / (1024**3)
        print(f"\nZip file still on disk: {zip_path} ({size_gb:.1f} GB)")
        print(f"Delete it manually when done: del {zip_path}")


if __name__ == "__main__":
    main()
