"""Download individual DOJ Epstein video files and upload to S3.

The DOJ Epstein library has video files accessible by changing .pdf to .mp4/.mov.
This script downloads specific known video files directly (no ZIP needed).

Usage:
    python scripts/download_doj_videos.py                    # Download all 6 + upload to S3
    python scripts/download_doj_videos.py --download-only    # Download locally only
    python scripts/download_doj_videos.py --list             # Just list the videos

Source: https://kaburbank.substack.com/p/how-to-view-video-files-in-the-doj
"""
import argparse
import os
import sys
import time

import boto3
import requests

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
COMBINED_CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
S3_PREFIX = f"cases/{CASE_ID}/raw/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "video/mp4, video/quicktime, application/octet-stream, */*",
    "Referer": "https://www.justice.gov/epstein/search",
}

# Known video files from DOJ Epstein library (Dataset 10)
# DOJ blocked direct access (age-verify gate) as of Feb 2026.
# Primary source: Wayback Machine cached copies from Jan 31, 2026.
# Fallback: direct DOJ URL (in case they re-enable access).
VIDEOS = [
    {
        "urls": [
            "https://web.archive.org/web/20260131081447/https://www.justice.gov/epstein/files/DataSet%2010/EFTA01648768.mp4",
            "https://www.justice.gov/epstein/files/DataSet%2010/EFTA01648768.mp4",
        ],
        "filename": "EFTA01648768.mp4",
        "description": "DNA paternity test kit on surface with Epstein paperwork",
        "dataset": 10,
    },
    {
        "urls": [
            "https://web.archive.org/web/20260131/https://www.justice.gov/epstein/files/DataSet%2010/EFTA01688320.mp4",
            "https://www.justice.gov/epstein/files/DataSet%2010/EFTA01688320.mp4",
        ],
        "filename": "EFTA01688320.mp4",
        "description": "Epstein talking on camera",
        "dataset": 10,
    },
    {
        "urls": [
            "https://web.archive.org/web/20260131/https://www.justice.gov/epstein/files/DataSet%2010/EFTA01688321.mp4",
            "https://www.justice.gov/epstein/files/DataSet%2010/EFTA01688321.mp4",
        ],
        "filename": "EFTA01688321.mp4",
        "description": "Ghislaine Maxwell deposition footage (April 22, 2016)",
        "dataset": 10,
    },
    {
        "urls": [
            "https://web.archive.org/web/20260131081215/https://www.justice.gov/epstein/files/DataSet%2010/EFTA01621046.mov",
            "https://www.justice.gov/epstein/files/DataSet%2010/EFTA01621046.mov",
        ],
        "filename": "EFTA01621046.mov",
        "description": "Jack Lang and Jeffrey Epstein at the Louvre",
        "dataset": 10,
    },
    {
        "urls": [
            "https://web.archive.org/web/20260131081213/https://www.justice.gov/epstein/files/DataSet%2010/EFTA01621029.mov",
            "https://www.justice.gov/epstein/files/DataSet%2010/EFTA01621029.mov",
        ],
        "filename": "EFTA01621029.mov",
        "description": "Newspaper headline about Cosby circled in pen",
        "dataset": 10,
    },
    {
        "urls": [
            "https://web.archive.org/web/20260213044614/https://www.justice.gov/epstein/files/DataSet%2010/EFTA01619633.mov",
            "https://www.justice.gov/epstein/files/DataSet%2010/EFTA01619633.mov",
        ],
        "filename": "EFTA01619633.mov",
        "description": "Spiritual/mindfulness advisor clip",
        "dataset": 10,
    },
]

s3 = boto3.client("s3", region_name=REGION)


def download_video(video, download_dir):
    """Download a single video file, trying multiple URLs."""
    filepath = os.path.join(download_dir, video["filename"])

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"  Already downloaded: {video['filename']} ({size_mb:.1f} MB)")
        return filepath

    print(f"  Downloading: {video['filename']}")
    print(f"    {video['description']}")

    urls = video.get("urls", [video.get("url", "")])

    for i, url in enumerate(urls):
        source = "Wayback Machine" if "archive.org" in url else "DOJ direct"
        print(f"    Trying [{source}]: {url[:90]}...")

        try:
            resp = requests.get(url, headers=HEADERS, stream=True, timeout=180,
                                allow_redirects=True)

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type:
                print(f"    SKIP: Got HTML response ({source})")
                continue

            if resp.status_code != 200:
                print(f"    SKIP: HTTP {resp.status_code}")
                continue

            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=512 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 / total
                        mb = downloaded / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        sys.stdout.write(f"\r    {mb:.1f}/{total_mb:.1f} MB ({pct:.0f}%)")
                    else:
                        mb = downloaded / (1024 * 1024)
                        sys.stdout.write(f"\r    {mb:.1f} MB...")
                    sys.stdout.flush()

            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if size_mb < 0.001:
                print(f"\n    SKIP: Empty file from {source}")
                os.remove(filepath)
                continue

            print(f"\n    OK: {size_mb:.1f} MB from {source}")
            return filepath

        except Exception as e:
            print(f"    SKIP: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            continue

    print(f"    FAILED: All URLs exhausted for {video['filename']}")
    return None


def upload_to_s3(filepath, filename, case_id):
    """Upload a video file to S3 for a given case."""
    s3_key = f"cases/{case_id}/raw/{filename}"

    # Check if already exists
    try:
        s3.head_object(Bucket=BUCKET, Key=s3_key)
        print(f"    Already in S3: s3://{BUCKET}/{s3_key}")
        return True
    except s3.exceptions.ClientError:
        pass

    file_size = os.path.getsize(filepath)
    size_mb = file_size / (1024 * 1024)
    print(f"    Uploading to S3: {filename} ({size_mb:.1f} MB) -> {case_id[:8]}...")

    s3.upload_file(filepath, BUCKET, s3_key)
    print(f"    OK: s3://{BUCKET}/{s3_key}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Download DOJ Epstein video files")
    parser.add_argument("--download-only", action="store_true", help="Download locally, don't upload to S3")
    parser.add_argument("--list", action="store_true", help="Just list the videos")
    parser.add_argument("--download-dir", default="./epstein_downloads/videos", help="Local download dir")
    parser.add_argument("--both-cases", action="store_true", default=True,
                        help="Upload to both main and combined case (default: True)")
    args = parser.parse_args()

    if args.list:
        print(f"Known DOJ Epstein video files ({len(VIDEOS)} total):\n")
        for i, v in enumerate(VIDEOS, 1):
            print(f"  {i}. {v['filename']} (Dataset {v['dataset']})")
            print(f"     {v['description']}")
            for url in v.get("urls", []):
                src = "Wayback" if "archive.org" in url else "DOJ"
                print(f"     [{src}] {url}")
            print()
        return

    download_dir = args.download_dir
    os.makedirs(download_dir, exist_ok=True)

    print("=" * 60)
    print("DOJ Epstein Video Downloader")
    print(f"Videos to download: {len(VIDEOS)}")
    print(f"Download dir: {download_dir}")
    if not args.download_only:
        print(f"S3 bucket: {BUCKET}")
        print(f"Main case: {CASE_ID}")
        print(f"Combined case: {COMBINED_CASE_ID}")
    print("=" * 60)

    downloaded = []
    failed = []

    for i, video in enumerate(VIDEOS, 1):
        print(f"\n[{i}/{len(VIDEOS)}] {video['filename']}")
        filepath = download_video(video, download_dir)
        if filepath:
            downloaded.append((filepath, video["filename"]))
        else:
            failed.append(video["filename"])

    print(f"\n{'=' * 60}")
    print(f"Download complete: {len(downloaded)} OK, {len(failed)} failed")

    if failed:
        print(f"Failed: {', '.join(failed)}")

    if not args.download_only and downloaded:
        print(f"\n--- Uploading to S3 ---")
        uploaded = 0
        for filepath, filename in downloaded:
            # Upload to main case
            ok1 = upload_to_s3(filepath, filename, CASE_ID)
            # Upload to combined case
            ok2 = upload_to_s3(filepath, filename, COMBINED_CASE_ID)
            if ok1 or ok2:
                uploaded += 1

        print(f"\nUploaded {uploaded} videos to S3 (both cases)")
        print(f"\nTo process through the pipeline, trigger ingestion for these files.")
        print(f"The pipeline's rekognition_handler already supports video via")
        print(f"_process_video() and _process_video_faces_only().")

    # Summary
    total_size = sum(os.path.getsize(fp) for fp, _ in downloaded) if downloaded else 0
    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"  Downloaded: {len(downloaded)} videos")
    print(f"  Total size: {total_size / (1024*1024):.1f} MB")
    print(f"  Failed: {len(failed)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
