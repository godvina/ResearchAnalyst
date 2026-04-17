"""DataSet 11 → S3 streamer v2.

Downloads to a different filename to avoid the locked file,
downloads in 2 GB chunks with resume, streams files to S3 from zip.
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
ZIP_PATH = os.path.join(DOWNLOAD_DIR, "DataSet_11_v2.zip")

URL = "https://doj-files.geeken.dev/doj_zips/original_archives/DataSet%2011.zip"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

DOC_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx", ".xls", ".xlsx", ".html", ".htm", ".eml", ".msg"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".gif", ".bmp"}

s3 = boto3.client("s3", region_name=REGION)


CHUNK_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB download chunks


def get_existing_s3_files():
    existing = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=S3_PREFIX):
        for obj in page.get("Contents", []):
            existing.add(obj["Key"].split("/")[-1].lower())
    print(f"[dedup] {len(existing)} files already in S3")
    return existing


def get_remote_size(url):
    """Get total file size via HEAD request."""
    resp = requests.head(url, headers=HEADERS, timeout=30, allow_redirects=True)
    return int(resp.headers.get("Content-Length", 0))


def download_chunk(url, dest, start, end, attempt=1):
    """Download a byte range to file. Returns bytes written."""
    range_hdr = f"bytes={start}-{end}"
    print(f"[download] Chunk {start/(1024**3):.1f}-{end/(1024**3):.1f} GB (attempt {attempt})")
    
    resp = requests.get(
        url, headers={**HEADERS, "Range": range_hdr},
        stream=True, timeout=300, allow_redirects=True,
    )
    
    written = 0
    with open(dest, "r+b" if os.path.exists(dest) and start > 0 else "wb") as f:
        f.seek(start)
        for data in resp.iter_content(chunk_size=4 * 1024 * 1024):
            f.write(data)
            written += len(data)
            total_on_disk = start + written
            sys.stdout.write(f"\r[download] {total_on_disk/(1024**2):.0f} MB ({total_on_disk*100/(end+1):.1f}%) — {written/(1024**2):.0f} MB this chunk")
            sys.stdout.flush()
    
    print()
    return written


def download_in_chunks(url, dest, total_size):
    """Download file in 2 GB chunks with retry per chunk."""
    # Check existing progress
    existing_size = os.path.getsize(dest) if os.path.exists(dest) else 0
    if existing_size >= total_size:
        print(f"[download] Already complete: {existing_size/(1024**3):.1f} GB")
        return True
    
    if existing_size > 0:
        print(f"[download] Resuming from {existing_size/(1024**2):.0f} MB")
    
    pos = existing_size
    while pos < total_size:
        chunk_end = min(pos + CHUNK_SIZE - 1, total_size - 1)
        
        for attempt in range(1, 6):
            try:
                download_chunk(url, dest, pos, chunk_end, attempt)
                pos = chunk_end + 1
                pct = pos * 100 / total_size
                print(f"[download] Progress: {pos/(1024**3):.1f}/{total_size/(1024**3):.1f} GB ({pct:.0f}%)")
                break
            except Exception as e:
                print(f"\n[download] Chunk failed (attempt {attempt}/5): {type(e).__name__}: {e}")
                if attempt < 5:
                    time.sleep(10 * attempt)
                else:
                    print("[download] ERROR: Chunk failed after 5 retries")
                    return False
    
    # Verify
    final_size = os.path.getsize(dest)
    print(f"[download] Complete: {final_size/(1024**3):.1f} GB")
    try:
        with zipfile.ZipFile(dest, "r") as zf:
            count = len(zf.namelist())
            print(f"[download] Valid zip with {count} entries")
        return True
    except Exception as e:
        print(f"[download] WARNING: Zip validation failed: {e}")
        return False


def stream_to_s3(zip_path, existing):
    """Stream files from zip directly to S3."""
    uploaded = 0
    skipped_dedup = 0
    skipped_type = 0
    errors = 0
    start = time.time()

    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.namelist() if not m.endswith("/")]
        total = len(members)
        print(f"[stream] {total} files in zip")

        for i, member in enumerate(members, 1):
            filename = os.path.basename(member)
            if not filename:
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in DOC_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
                skipped_type += 1
                continue

            if filename.lower() in existing:
                skipped_dedup += 1
                continue

            try:
                data = zf.read(member)
                s3.put_object(Bucket=BUCKET, Key=S3_PREFIX + filename, Body=data)
                existing.add(filename.lower())
                uploaded += 1

                if uploaded % 200 == 0:
                    elapsed = time.time() - start
                    rate = uploaded / max(elapsed / 60, 0.01)
                    print(f"[stream] {uploaded} uploaded, {skipped_dedup} dedup, "
                          f"{i}/{total} processed, {rate:.0f} files/min")
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"[stream] Error: {filename}: {e}")

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"DONE — {elapsed/60:.1f} minutes")
    print(f"  Uploaded: {uploaded}")
    print(f"  Dedup skipped: {skipped_dedup}")
    print(f"  Type skipped: {skipped_type}")
    print(f"  Errors: {errors}")
    print(f"{'='*60}")
    return uploaded


def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    print("=" * 60)
    print("DataSet 11 → S3 (chunked download, v2)")
    print(f"Downloading to: {ZIP_PATH}")
    print("=" * 60)

    existing = get_existing_s3_files()

    print("[download] Getting file size...")
    total_size = get_remote_size(URL)
    if total_size == 0:
        print("[download] ERROR: Could not determine file size")
        sys.exit(1)
    print(f"[download] Total: {total_size/(1024**3):.1f} GB")
    num_chunks = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"[download] Will download in {num_chunks} chunks of ~2 GB each")

    if not download_in_chunks(URL, ZIP_PATH, total_size):
        print("Download failed. Run again to resume.")
        sys.exit(1)

    uploaded = stream_to_s3(ZIP_PATH, existing)

    if uploaded > 0:
        print(f"\nNext: python scripts/process_new_epstein_pdfs.py")


if __name__ == "__main__":
    main()
