"""One-shot demo setup script.

Run this after cdk deploy to:
1. Create the Ancient Aliens case file
2. Trigger ingestion of all 238 transcripts (batched to avoid payload limits)
3. Create the Crop Circles sub-case

Usage:
    python scripts/setup_demo.py
"""
import base64
import json
import os
import time

import requests

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
TRANSCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "transcripts")
BATCH_SIZE = 10  # files per ingestion request to stay under API Gateway/Lambda payload limits


def create_case_file(topic, description):
    resp = requests.post(f"{API}/case-files", json={"topic_name": topic, "description": description})
    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"  Created: {data.get('case_id')}")
        return data.get("case_id")
    print(f"  Error {resp.status_code}: {resp.text[:200]}")
    return None


def ingest_transcripts(case_id, transcript_dir):
    all_files = []
    for fn in sorted(os.listdir(transcript_dir)):
        if fn.endswith(".txt"):
            with open(os.path.join(transcript_dir, fn), "rb") as f:
                content = f.read()
            all_files.append({
                "filename": fn,
                "content_base64": base64.b64encode(content).decode("utf-8"),
            })

    total = len(all_files)
    print(f"  Found {total} transcripts, ingesting in batches of {BATCH_SIZE}...")

    total_success = 0
    total_failed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = all_files[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} files)... ", end="", flush=True)

        try:
            resp = requests.post(
                f"{API}/case-files/{case_id}/ingest",
                json={"files": batch},
                timeout=300,
            )
            if resp.status_code == 200:
                data = resp.json()
                s = data.get("successful", 0)
                f_ = data.get("failed", 0)
                total_success += s
                total_failed += f_
                print(f"OK ({s} succeeded, {f_} failed)")
            elif resp.status_code == 504:
                # Lambda is still running, just API Gateway timed out
                print(f"Accepted (processing in background)")
                total_success += len(batch)
            else:
                total_failed += len(batch)
                print(f"Error {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as e:
            total_failed += len(batch)
            print(f"Request error: {e}")

        # Brief pause between batches to avoid throttling
        if i + BATCH_SIZE < total:
            time.sleep(2)

    print(f"\n  Ingestion complete: {total_success} succeeded, {total_failed} failed out of {total}")
    return total_failed == 0


def main():
    print("=== Research Analyst Platform — Demo Setup ===\n")

    # Step 1: Create main Ancient Aliens case
    print("1. Creating Ancient Aliens case file...")
    case_id = create_case_file(
        "Ancient Aliens Investigation",
        "Comprehensive analysis of Ancient Aliens TV series transcripts (all seasons, 238 episodes). "
        "Extracting entities, relationships, and hidden patterns covering "
        "ancient astronaut theory, mysterious locations, unexplained structures, and alleged "
        "extraterrestrial contact throughout human history."
    )
    if not case_id:
        print("Failed to create case file. Check API is running.")
        return

    # Step 2: Ingest transcripts
    print(f"\n2. Ingesting transcripts into case {case_id}...")
    success = ingest_transcripts(case_id, TRANSCRIPTS_DIR)

    if not success:
        print("Ingestion failed. Check Lambda logs.")
        return

    # Step 3: Create Crop Circles sub-case
    print("\n3. Creating Crop Circles sub-case...")
    resp = requests.post(f"{API}/case-files/{case_id}/drill-down", json={
        "topic_name": "Crop Circles Deep Dive",
        "description": "Focused investigation into crop circle phenomena as discussed in Ancient Aliens. "
                       "Analyzing geometric patterns, locations (primarily UK), alleged extraterrestrial "
                       "connections, and scientific explanations. Cross-referencing with other mysterious "
                       "location patterns found in the main case.",
        "entity_names": ["crop circles", "Wiltshire", "England", "geometric patterns", "sacred geometry"],
    })
    if resp.status_code in (200, 201):
        sub_case = resp.json()
        print(f"  Created sub-case: {sub_case.get('case_id')}")
    else:
        print(f"  Error {resp.status_code}: {resp.text[:200]}")

    print(f"\n=== Setup Complete ===")
    print(f"Main case ID: {case_id}")
    print(f"Open Streamlit at http://localhost:8501 to explore the data.")


if __name__ == "__main__":
    main()
