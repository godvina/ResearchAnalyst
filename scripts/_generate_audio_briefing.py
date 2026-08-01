"""Generate an audio briefing from research findings using Bedrock + Polly.

Flow:
1. Load research data (patterns, findings, connections)
2. Use Bedrock to generate a documentary-style narration script
3. Use Amazon Polly to convert each chapter to MP3
4. Upload to S3 for frontend playback

Usage:
    python scripts/_generate_audio_briefing.py
"""
import boto3
import json
import os
import time

REGION = "us-east-1"
S3_BUCKET = "research-analyst-data-lake-974220725866"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")
POLLY_VOICE = "Matthew"  # Neural male voice, good for documentary
BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-6"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
polly = boto3.client("polly", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def load_research_context():
    """Load all research data to build the narration."""
    context = {}
    
    # Research briefs
    path = os.path.join(DATA_DIR, "uvg-grid-research-all-nodes.json")
    with open(path) as f:
        research = json.load(f)
    context["total_nodes"] = research["total_researched"]
    
    # Get top sites
    confirmed = [r for r in research["results"] if r["brief"]["investigation_status"] == "CONFIRMED"]
    probable = [r for r in research["results"] if r["brief"]["investigation_status"] == "PROBABLE"]
    context["confirmed"] = confirmed
    context["probable"] = probable[:5]
    
    # Scored findings
    path2 = os.path.join(DATA_DIR, "uvg-grid-scored-findings.json")
    with open(path2) as f:
        scored = json.load(f)
    context["total_with_matches"] = scored["total_with_matches"]
    
    # Agent chain results
    path3 = os.path.join(DATA_DIR, "agent-chain-results.json")
    if os.path.exists(path3):
        with open(path3) as f:
            chain = json.load(f)
        context["chain_results"] = chain
    
    # Emergent patterns
    path4 = os.path.join(DATA_DIR, "emergent-patterns.json")
    if os.path.exists(path4):
        with open(path4) as f:
            emergent = json.load(f)
        context["emergent_pairs"] = emergent["total_pairs"]
    
    return context


def generate_narration_script(context):
    """Use Bedrock to write a documentary narration script."""
    print("  Generating narration script via Bedrock...")
    
    # Build a summary of findings for the LLM
    confirmed_names = [r["brief"]["codename"] + " (" + r["brief"]["situation"][:100] + ")" 
                       for r in context["confirmed"]]
    
    prompt = f"""You are a documentary narrator for a Discovery Channel episode about ancient mysteries and the UVG global grid.

Write a 7-chapter audio narration script. Each chapter should be 3-5 sentences, spoken naturally as if narrating a documentary. Total script should be about 2000 words.

Use these REAL findings from our AI research:

INVESTIGATION SUMMARY:
- 62 grid vertices analyzed on the Becker-Hagens UVG grid
- {context['total_with_matches']} of 59 researched nodes show evidence of ancient significance
- {len(context['confirmed'])} sites CONFIRMED (Giza, Mohenjo-daro)
- Cross-pattern analysis found connections between distant sites

CONFIRMED SITES:
{json.dumps(confirmed_names, indent=2)[:1000]}

AGENT CHAIN FINDINGS (from automated research):
- Broad Scanner found: Alfred Watkins 1921 ley line theory, Alexander Thom megalithic measurements
- Taxonomy Scanner confirmed: Avebury megaliths, Glastonbury sacred traditions, Stonehenge geometry
- Cross-Pattern Agent found: Teotihuacan ↔ Angkor Wat identical alignment, Easter Island ↔ Callanish same 18.6-year lunar cycle

EMERGENT PATTERNS (AI-detected, not searched for):
- {context.get('emergent_pairs', 128)} unexpected similarity pairs found by OpenSearch
- Southern ocean nodes cluster by shared bathymetric characteristics
- Potential new taxonomy signature: "Oceanic Grid Geometry"

Write the script in this format (return ONLY the JSON, no markdown):
{{
  "title": "The Global Grid: What the AI Found",
  "chapters": [
    {{"chapter": 1, "title": "The Theory", "narration": "full narration text..."}},
    {{"chapter": 2, "title": "The Evidence", "narration": "..."}},
    {{"chapter": 3, "title": "Sacred Sites", "narration": "..."}},
    {{"chapter": 4, "title": "The Connections", "narration": "..."}},
    {{"chapter": 5, "title": "What the AI Discovered", "narration": "..."}},
    {{"chapter": 6, "title": "The Unexplained", "narration": "..."}},
    {{"chapter": 7, "title": "What Comes Next", "narration": "..."}}
  ]
}}

Make it compelling, cite specific measurements and researcher names, and end each chapter with a hook that makes the listener want to hear the next one."""

    from botocore.config import Config
    config = Config(read_timeout=120)
    client = boto3.client("bedrock-runtime", region_name=REGION, config=config)
    
    resp = client.invoke_model(
        modelId=BEDROCK_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        })
    )
    
    body = json.loads(resp["body"].read())
    raw = ""
    for block in body.get("content", []):
        if block.get("type") == "text":
            raw = block["text"]
            break
    
    # Parse JSON
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    
    try:
        return json.loads(text)
    except:
        # Truncation repair
        for trim_to in [text.rfind('}'), text.rfind('"}')]:
            if trim_to <= 0: continue
            candidate = text[:trim_to+1]
            candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
            candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
            try: return json.loads(candidate)
            except: continue
        print("  ERROR: Could not parse script. Saving raw.")
        return {"title": "Research Briefing", "chapters": [{"chapter": 1, "title": "Findings", "narration": raw[:3000]}]}

def synthesize_audio(chapter_text, chapter_num, title):
    """Convert text to MP3 using Amazon Polly Neural voice."""
    print(f"  Chapter {chapter_num}: '{title}' ({len(chapter_text)} chars)")
    
    # Add SSML for better pacing
    ssml = f'<speak><prosody rate="95%"><p>{chapter_text}</p></prosody></speak>'
    
    try:
        response = polly.synthesize_speech(
            Text=ssml,
            TextType='ssml',
            OutputFormat='mp3',
            VoiceId=POLLY_VOICE,
            Engine='neural'
        )
        
        audio_stream = response['AudioStream'].read()
        return audio_stream
    except Exception as e:
        print(f"    Polly error: {e}")
        # Fallback to standard engine if neural not available for this voice
        try:
            response = polly.synthesize_speech(
                Text=chapter_text,
                TextType='text',
                OutputFormat='mp3',
                VoiceId=POLLY_VOICE,
                Engine='standard'
            )
            return response['AudioStream'].read()
        except Exception as e2:
            print(f"    Fallback also failed: {e2}")
            return None


def main():
    print("=" * 60)
    print("  AUDIO BRIEFING GENERATOR")
    print("  Bedrock (script) → Polly (audio) → S3 (storage)")
    print("=" * 60)
    print()
    
    # Load research context
    print("[1/4] Loading research data...")
    context = load_research_context()
    print(f"  Nodes: {context['total_nodes']} | Matches: {context['total_with_matches']} | Confirmed: {len(context['confirmed'])}")
    print()
    
    # Generate narration script
    print("[2/4] Generating documentary script via Bedrock...")
    script = generate_narration_script(context)
    print(f"  Title: {script['title']}")
    print(f"  Chapters: {len(script['chapters'])}")
    
    # Save script
    script_path = os.path.join(DATA_DIR, "audio-briefing-script.json")
    with open(script_path, "w") as f:
        json.dump(script, f, indent=2)
    print(f"  Script saved: {script_path}")
    print()
    
    # Synthesize audio for each chapter
    print("[3/4] Converting to audio via Amazon Polly...")
    audio_files = []
    all_audio = b''
    
    for ch in script["chapters"]:
        audio = synthesize_audio(ch["narration"], ch["chapter"], ch["title"])
        if audio:
            # Save individual chapter
            key = f"audio/briefing-chapter-{ch['chapter']:02d}.mp3"
            s3.put_object(Bucket=S3_BUCKET, Key=key, Body=audio, ContentType='audio/mpeg')
            audio_files.append({"chapter": ch["chapter"], "title": ch["title"], "s3_key": key, "size_kb": len(audio) // 1024})
            all_audio += audio
            print(f"    ✓ {len(audio) // 1024}KB")
        time.sleep(0.5)
    
    # Save combined full briefing
    if all_audio:
        combined_key = "audio/briefing-full.mp3"
        s3.put_object(Bucket=S3_BUCKET, Key=combined_key, Body=all_audio, ContentType='audio/mpeg')
        print(f"\n  Combined MP3: {len(all_audio) // 1024}KB → s3://{S3_BUCKET}/{combined_key}")
    
    # Save manifest for frontend
    print()
    print("[4/4] Saving manifest...")
    manifest = {
        "title": script["title"],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "voice": POLLY_VOICE,
        "total_chapters": len(audio_files),
        "total_size_kb": len(all_audio) // 1024,
        "chapters": audio_files,
        "full_briefing_url": f"https://{S3_BUCKET}.s3.{REGION}.amazonaws.com/audio/briefing-full.mp3",
        "chapter_base_url": f"https://{S3_BUCKET}.s3.{REGION}.amazonaws.com/audio/"
    }
    
    manifest_path = os.path.join(DATA_DIR, "audio-briefing-manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    # Upload manifest to S3 for API
    s3.put_object(Bucket=S3_BUCKET, Key="pattern-library/audio-briefing-manifest.json",
                  Body=json.dumps(manifest, indent=2), ContentType='application/json')
    
    print(f"  Manifest saved: {manifest_path}")
    print()
    print("=" * 60)
    print(f"  DONE! {len(audio_files)} chapters generated")
    print(f"  Total audio: {len(all_audio) // 1024}KB")
    print(f"  Listen: {manifest['full_briefing_url']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
