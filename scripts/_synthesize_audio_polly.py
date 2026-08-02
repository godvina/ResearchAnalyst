"""Synthesize documentary narration via Amazon Polly (Neural voice).

Reads expanded-documentary-script.json and deep-dive-episodes.json,
generates MP3 audio for each chapter via Polly Neural (Matthew voice),
uploads to S3, and produces a manifest with presigned URLs.

Usage:
    python scripts/_synthesize_audio_polly.py [--deep-dives] [--overview]

Cost: ~$4 per 1 million characters (Neural). Our 13K words ≈ ~75K chars ≈ $0.30 total.
"""
import boto3
import json
import os
import sys
import time

REGION = "us-east-1"
S3_BUCKET = "research-analyst-data-lake-974220725866"
S3_PREFIX = "audio/documentary-v2/"
VOICE_ID = "Matthew"  # Neural male voice
ENGINE = "neural"
OUTPUT_FORMAT = "mp3"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

polly = boto3.client("polly", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def synthesize_chapter(chapter_id, title, text):
    """Synthesize one chapter to MP3 via Polly, upload to S3, return metadata."""
    # Clean text for Polly
    clean_text = text.replace("&", "and").replace("<", "").replace(">", "")
    
    # Polly SynthesizeSpeech SSML limit is 3000 chars. Split if needed.
    chunks = []
    if len(clean_text) > 2800:
        # Split on sentence boundaries
        sentences = clean_text.replace(". ", ".|").split("|")
        current_chunk = ""
        for sent in sentences:
            if len(current_chunk) + len(sent) > 2700:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sent
            else:
                current_chunk += sent
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
    else:
        chunks = [clean_text]

    try:
        audio_parts = []
        for chunk in chunks:
            ssml = (
                '<speak>'
                '<prosody rate="95%">'
                f'{chunk}'
                '</prosody>'
                '</speak>'
            )
            response = polly.synthesize_speech(
                Text=ssml,
                TextType="ssml",
                OutputFormat=OUTPUT_FORMAT,
                VoiceId=VOICE_ID,
                Engine=ENGINE,
            )
            audio_parts.append(response["AudioStream"].read())
            time.sleep(0.3)

        # Concatenate audio chunks
        audio_data = b"".join(audio_parts)
        audio_size = len(audio_data)

        # Upload to S3
        s3_key = f"{S3_PREFIX}{chapter_id}.mp3"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=audio_data,
            ContentType="audio/mpeg",
        )

        # Generate presigned URL (7 days)
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=604800,
        )

        return {
            "chapter_id": chapter_id,
            "title": title,
            "s3_key": s3_key,
            "url": presigned_url,
            "size_bytes": audio_size,
            "duration_estimate_s": len(text.split()) / 2.5,
            "chunks_used": len(chunks),
        }
    except Exception as e:
        print(f"    ERROR: {e}")
        return None


def main():
    do_overview = "--overview" in sys.argv or len(sys.argv) == 1
    do_deep = "--deep-dives" in sys.argv or len(sys.argv) == 1

    manifest = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "episodes": [], "deep_dives": []}
    total_chars = 0
    total_files = 0

    # --- OVERVIEW EPISODES ---
    if do_overview:
        overview_path = os.path.join(DATA_DIR, "expanded-documentary-script.json")
        if os.path.exists(overview_path):
            with open(overview_path) as f:
                overview = json.load(f)

            print("=" * 60)
            print("  SYNTHESIZING OVERVIEW EPISODES")
            print("=" * 60)

            for ep in overview.get("episodes", []):
                print(f"\n  Episode: {ep['title']}")
                ep_manifest = {"id": ep["id"], "title": ep["title"], "chapters": []}

                for ch in ep.get("chapters", []):
                    print(f"    [{ch['id']}] {ch['title']}...", end=" ")
                    result = synthesize_chapter(ch["id"], ch["title"], ch["narration"])
                    if result:
                        ep_manifest["chapters"].append(result)
                        total_chars += len(ch["narration"])
                        total_files += 1
                        print(f"OK ({result['size_bytes']//1024}KB)")
                    else:
                        print("FAILED")
                    time.sleep(0.5)  # Rate limit

                manifest["episodes"].append(ep_manifest)

    # --- DEEP DIVE EPISODES ---
    if do_deep:
        deep_path = os.path.join(DATA_DIR, "deep-dive-episodes.json")
        if os.path.exists(deep_path):
            with open(deep_path) as f:
                deep = json.load(f)

            print("\n" + "=" * 60)
            print("  SYNTHESIZING DEEP DIVE EPISODES")
            print("=" * 60)

            for dd in deep.get("deep_dives", []):
                print(f"\n  Deep Dive: {dd['title']}")
                dd_manifest = {"id": dd["id"], "title": dd["title"], "chapters": []}

                for ch in dd.get("chapters", []):
                    print(f"    [{ch['id']}] {ch['title']}...", end=" ")
                    result = synthesize_chapter(ch["id"], ch["title"], ch["narration"])
                    if result:
                        dd_manifest["chapters"].append(result)
                        total_chars += len(ch["narration"])
                        total_files += 1
                        print(f"OK ({result['size_bytes']//1024}KB)")
                    else:
                        print("FAILED")
                    time.sleep(0.5)

                manifest["deep_dives"].append(dd_manifest)

    # Save manifest
    manifest_path = os.path.join(DATA_DIR, "audio-manifest-v2.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  COMPLETE")
    print(f"  Files: {total_files}")
    print(f"  Characters: {total_chars:,}")
    print(f"  Est. cost: ${total_chars * 4 / 1_000_000:.2f} (Polly Neural)")
    print(f"  Manifest: {manifest_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
