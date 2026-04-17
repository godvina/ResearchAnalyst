"""Download DOJ Epstein datasets and upload to S3 for pipeline processing.

Phase 1 (test): DataSet 12 (154 files, 114 MB) + first 1000 from DataSet 11
Phase 2: Full DataSet 11 (331K files, 27.5 GB)
Phase 3: DataSet 10 (50K files, 79 GB)
Phase 4: DataSets 1-9 (500K+ files, ~180 GB)

Usage:
    python scripts/download_doj_epstein.py --phase 1          # Test: 1,154 files
    python scripts/download_doj_epstein.py --phase 2          # Full DataSet 11+12
    python scripts/download_doj_epstein.py --phase 3          # DataSet 10
    python scripts/download_doj_epstein.py --phase 4          # DataSets 1-9
    python scripts/download_doj_epstein.py --phase all        # Everything

Dedup: Skips files already in S3 under cases/{case_id}/raw/
"""
import argparse
import io
import os
import sys
import time
import zipfile
from pathlib import Path

import boto3
import requests

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
S3_PREFIX = f"cases/{CASE_ID}/raw/"

# DOJ download URLs with Internet Archive fallbacks
DATASETS = {
    12: [
        "https://www.justice.gov/epstein/files/DataSet%2012.zip",
        "https://archive.org/download/data-set-12_202601/DataSet%2012.zip",
    ],
    11: [
        "https://www.justice.gov/epstein/files/DataSet%2011.zip",
        "https://doj-files.geeken.dev/doj_zips/original_archives/DataSet%2011.zip",
    ],
    10: [
        "https://www.justice.gov/epstein/files/DataSet%2010.zip",
        "https://archive.org/download/data-set-10/DataSet%2010.zip",
        "https://doj-files.geeken.dev/doj_zips/original_archives/DataSet%2010.zip",
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/zip, application/octet-stream, */*",
}

# File extensions to process (skip videos by default)
DOC_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx", ".xls", ".xlsx", ".html", ".htm", ".eml", ".msg"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".wmv", ".mpg", ".mpeg"}

s3 = boto3.client("s3", region_name=REGION)


def get_existing_files():
    """List all files already in S3 for this case."""
    existing = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=S3_PREFIX):
        for obj in page.get("Contents", []):
            filename = obj["Key"].split("/")[-1].lower()
            existing.add(filename)
    print(f"Found {len(existing)} existing files in S3")
    return existing


def download_and_extract(urls, download_dir, max_files=None, include_videos=0):
    """Download a DOJ zip file and extract to local directory.
    
    Args:
        urls: List of download URLs to try (primary + fallbacks)
        download_dir: Local directory to extract to
        max_files: Max number of document files to extract (None = all)
        include_videos: Number of video files to include (0 = none)
    
    Returns:
        List of extracted file paths
    """
    if isinstance(urls, str):
        urls = [urls]
    
    zip_name = urls[0].split("/")[-1].replace("%20", "_")
    zip_path = os.path.join(download_dir, zip_name)
    
    # Download if not already present (or if previous download was bad)
    need_download = True
    if os.path.exists(zip_path):
        # Verify it's actually a zip
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.namelist()  # Quick check
            print(f"Zip already downloaded and valid: {zip_path} ({os.path.getsize(zip_path) / (1024*1024):.1f} MB)")
            need_download = False
        except (zipfile.BadZipFile, Exception):
            print(f"Previous download is corrupt, re-downloading...")
            os.remove(zip_path)
    
    if need_download:
        for url in urls:
            print(f"Downloading {url}...")
            print(f"  Saving to: {zip_path}")
            try:
                resp = requests.get(url, headers=HEADERS, stream=True, timeout=60, allow_redirects=True)
                
                # Check content type — if HTML, the server redirected to a page
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    print(f"  Server returned HTML (not a zip) — trying next URL...")
                    continue
                
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                
                with open(zip_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded * 100 / total
                            mb = downloaded / (1024 * 1024)
                            total_mb = total / (1024 * 1024)
                            sys.stdout.write(f"\r  {mb:.1f}/{total_mb:.1f} MB ({pct:.1f}%)")
                            sys.stdout.flush()
                        else:
                            mb = downloaded / (1024 * 1024)
                            sys.stdout.write(f"\r  {mb:.1f} MB downloaded...")
                            sys.stdout.flush()
                
                print(f"\n  Download complete: {os.path.getsize(zip_path) / (1024*1024):.1f} MB")
                
                # Verify it's a valid zip
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        zf.namelist()
                    break  # Success
                except zipfile.BadZipFile:
                    print(f"  Downloaded file is not a valid zip — trying next URL...")
                    os.remove(zip_path)
                    continue
                    
            except Exception as e:
                print(f"  Download failed: {e}")
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                continue
        
        if not os.path.exists(zip_path):
            print(f"  ERROR: All download URLs failed for {zip_name}")
            return []
    
    # Extract
    print(f"Extracting files...")
    extracted = []
    doc_count = 0
    video_count = 0
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()
        print(f"  Zip contains {len(members)} entries")
        
        for member in members:
            if member.endswith("/"):
                continue  # Skip directories
            
            filename = os.path.basename(member)
            if not filename:
                continue
            
            ext = os.path.splitext(filename)[1].lower()
            
            # Check if it's a document or image
            is_doc = ext in DOC_EXTENSIONS or ext in IMAGE_EXTENSIONS
            is_video = ext in VIDEO_EXTENSIONS
            
            if is_doc:
                if max_files and doc_count >= max_files:
                    continue
                doc_count += 1
            elif is_video:
                if video_count >= include_videos:
                    continue
                video_count += 1
                print(f"  Including video: {filename}")
            else:
                continue  # Skip unknown file types
            
            # Extract to flat directory
            target_path = os.path.join(download_dir, "extracted", filename)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            with zf.open(member) as src, open(target_path, "wb") as dst:
                dst.write(src.read())
            
            extracted.append(target_path)
            
            if len(extracted) % 100 == 0:
                print(f"  Extracted {len(extracted)} files...")
    
    print(f"  Extracted {doc_count} documents + {video_count} videos = {len(extracted)} total")
    return extracted


def upload_to_s3(files, existing_files):
    """Upload files to S3, skipping duplicates.
    
    Args:
        files: List of local file paths
        existing_files: Set of filenames already in S3
    
    Returns:
        (uploaded_count, skipped_count)
    """
    uploaded = 0
    skipped = 0
    
    for filepath in files:
        filename = os.path.basename(filepath)
        
        # Dedup check
        if filename.lower() in existing_files:
            skipped += 1
            continue
        
        s3_key = S3_PREFIX + filename
        file_size = os.path.getsize(filepath)
        
        # Use multipart upload for files > 100 MB
        if file_size > 100 * 1024 * 1024:
            print(f"  Uploading (multipart): {filename} ({file_size / (1024*1024):.1f} MB)")
            s3.upload_file(filepath, BUCKET, s3_key)
        else:
            s3.upload_file(filepath, BUCKET, s3_key)
        
        uploaded += 1
        existing_files.add(filename.lower())
        
        if uploaded % 50 == 0:
            print(f"  Uploaded {uploaded} files (skipped {skipped} duplicates)...")
    
    print(f"  Upload complete: {uploaded} new files, {skipped} skipped (already in S3)")
    return uploaded, skipped


def trigger_pipeline(doc_count):
    """Trigger the ingestion pipeline for the uploaded documents."""
    print(f"\nTo process these {doc_count} documents through the pipeline, run:")
    print(f"  python scripts/load_all_epstein.py")
    print(f"\nOr for a smaller test batch:")
    print(f"  python scripts/load_all_epstein.py --batch-size 50 --max-batches 1")


def main():
    parser = argparse.ArgumentParser(description="Download DOJ Epstein datasets")
    parser.add_argument("--phase", default="1", help="Phase: 1 (test), 2, 3, 4, or all")
    parser.add_argument("--download-dir", default="./epstein_downloads", help="Local download directory")
    parser.add_argument("--include-videos", type=int, default=0, help="Number of video files to include")
    args = parser.parse_args()
    
    download_dir = args.download_dir
    os.makedirs(download_dir, exist_ok=True)
    
    print("=" * 60)
    print("DOJ Epstein Dataset Downloader")
    print(f"Phase: {args.phase}")
    print(f"Download dir: {download_dir}")
    print(f"S3 bucket: {BUCKET}")
    print(f"Case ID: {CASE_ID}")
    print("=" * 60)
    
    # Get existing files for dedup
    existing = get_existing_files()
    
    all_files = []
    
    if args.phase in ("1", "all"):
        print(f"\n--- Phase 1: Test Load ---")
        # DataSet 12 (all 154 files) + first 1000 from DataSet 11
        print("Downloading DataSet 12 (154 files, 114 MB)...")
        files_12 = download_and_extract(DATASETS[12], download_dir, include_videos=args.include_videos)
        all_files.extend(files_12)
        
        print("\nDownloading DataSet 11 (first 1000 files)...")
        files_11 = download_and_extract(DATASETS[11], download_dir, max_files=1000, include_videos=max(0, args.include_videos - 2))
        all_files.extend(files_11)
    
    if args.phase in ("2", "all"):
        print(f"\n--- Phase 2: Full DataSet 11+12 ---")
        files_12 = download_and_extract(DATASETS[12], download_dir)
        all_files.extend(files_12)
        files_11 = download_and_extract(DATASETS[11], download_dir)
        all_files.extend(files_11)
    
    if args.phase in ("3", "all"):
        print(f"\n--- Phase 3: DataSet 10 ---")
        files_10 = download_and_extract(DATASETS[10], download_dir)
        all_files.extend(files_10)
    
    if args.phase == "4" or args.phase == "all":
        print(f"\n--- Phase 4: DataSets 1-9 ---")
        print("DataSets 1-9 URLs need to be added. Check:")
        print("  https://github.com/yung-megafone/Epstein-Files")
        print("  for the complete list of DOJ download links.")
    
    if not all_files:
        print("No files to upload.")
        return
    
    # Upload to S3
    print(f"\n--- Uploading {len(all_files)} files to S3 ---")
    uploaded, skipped = upload_to_s3(all_files, existing)
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"COMPLETE")
    print(f"  Files extracted: {len(all_files)}")
    print(f"  Uploaded to S3: {uploaded}")
    print(f"  Skipped (dedup): {skipped}")
    print(f"{'=' * 60}")
    
    if uploaded > 0:
        trigger_pipeline(uploaded)


if __name__ == "__main__":
    main()
