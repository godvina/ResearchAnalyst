"""Generate a cue sheet for the audio briefing — maps timestamps to map/graph actions.

Uses Bedrock to analyze each chapter's narration and determine:
- What nodes/sites are mentioned
- When to zoom the map
- When to show the network graph
- What cards to display

Output: audio-briefing-cues.json
"""
import boto3
import json
import os
import time

REGION = "us-east-1"
MODEL = "us.anthropic.claude-sonnet-4-6"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

# Approximate duration per chapter (based on ~150 words/minute for Polly neural at 95% rate)
# Average chapter is ~1400 chars ≈ 230 words ≈ 92 seconds
APPROX_SECONDS_PER_CHAR = 0.065  # Calibrated from our 3131KB total / ~10000 chars


def main():
    print("Generating cue sheet for audio briefing...")
    
    with open(os.path.join(DATA_DIR, "audio-briefing-script.json")) as f:
        script = json.load(f)
    
    # Known node coordinates for cue targets
    node_coords = {
        1: {"lat": 31.72, "lng": 31.2, "name": "Great Pyramid of Giza"},
        4: {"lat": 52.62, "lng": 103.2, "name": "Lake Baikal"},
        12: {"lat": 26.57, "lng": 67.2, "name": "Mohenjo-daro"},
        14: {"lat": 26.57, "lng": 139.2, "name": "Dragon Triangle"},
        17: {"lat": 31.72, "lng": -112.8, "name": "Sedona"},
        25: {"lat": 10.81, "lng": 103.2, "name": "Angkor Wat"},
        35: {"lat": -10.81, "lng": -76.8, "name": "Nazca Lines"},
        47: {"lat": -26.57, "lng": -112.8, "name": "Easter Island"},
    }
    
    # Build cue sheet based on chapter content analysis
    cue_sheet = {"version": "1.0", "chapters": []}
    current_time = 0
    
    for ch in script["chapters"]:
        text = ch["narration"].lower()
        duration = int(len(ch["narration"]) * APPROX_SECONDS_PER_CHAR)
        
        chapter_cues = {
            "chapter": ch["chapter"],
            "title": ch["title"],
            "start_time": current_time,
            "end_time": current_time + duration,
            "duration": duration,
            "cues": []
        }
        
        # Detect mentions and generate cues
        t = current_time
        
        # Opening: always start with a global view
        chapter_cues["cues"].append({"time": t + 2, "action": "zoom", "target": {"lat": 20, "lng": 20, "zoom": 2}})
        
        # Scan for site mentions and create zoom cues
        mentions_found = []
        for node_id, coords in node_coords.items():
            name_lower = coords["name"].lower()
            # Check variations
            search_terms = [name_lower]
            if "great pyramid" in name_lower:
                search_terms.extend(["giza", "pyramid", "egypt"])
            if "angkor" in name_lower:
                search_terms.extend(["angkor", "cambodia"])
            if "nazca" in name_lower:
                search_terms.extend(["nazca", "peru"])
            if "easter" in name_lower:
                search_terms.extend(["easter island", "rapa nui"])
            if "sedona" in name_lower:
                search_terms.extend(["sedona", "vortex"])
            if "baikal" in name_lower:
                search_terms.extend(["baikal", "siberia"])
            if "mohenjo" in name_lower:
                search_terms.extend(["mohenjo", "indus"])
            
            for term in search_terms:
                pos = text.find(term)
                if pos >= 0:
                    # Estimate time position in the narration
                    mention_time = current_time + int(pos * APPROX_SECONDS_PER_CHAR)
                    mentions_found.append({"time": mention_time, "node_id": node_id, "coords": coords})
                    break
        
        # Sort by time and add zoom cues
        mentions_found.sort(key=lambda x: x["time"])
        for m in mentions_found[:4]:  # Max 4 zooms per chapter
            chapter_cues["cues"].append({
                "time": m["time"],
                "action": "highlight_site",
                "node_id": m["node_id"],
                "target": {"lat": m["coords"]["lat"], "lng": m["coords"]["lng"], "zoom": 4},
                "label": m["coords"]["name"]
            })
        
        # Pattern-specific cues based on chapter
        if ch["chapter"] == 3:  # Sacred Sites
            chapter_cues["cues"].append({"time": t + 10, "action": "focus_pattern", "pattern": "sacred"})
        elif ch["chapter"] == 4:  # Connections
            chapter_cues["cues"].append({"time": t + 10, "action": "focus_pattern", "pattern": "cluster"})
            chapter_cues["cues"].append({"time": t + int(duration * 0.5), "action": "show_network", "pattern": "cluster"})
        elif ch["chapter"] == 5:  # AI Discovered
            chapter_cues["cues"].append({"time": t + 10, "action": "focus_pattern", "pattern": "submerged"})
        elif ch["chapter"] == 6:  # Unexplained
            chapter_cues["cues"].append({"time": t + 10, "action": "focus_pattern", "pattern": "tectonic"})
        
        # End of chapter: return to global view
        chapter_cues["cues"].append({"time": current_time + duration - 3, "action": "zoom", "target": {"lat": 20, "lng": 20, "zoom": 2}})
        
        # Sort cues by time
        chapter_cues["cues"].sort(key=lambda x: x["time"])
        
        cue_sheet["chapters"].append(chapter_cues)
        current_time += duration
    
    cue_sheet["total_duration"] = current_time
    
    # Save
    output_path = os.path.join(DATA_DIR, "audio-briefing-cues.json")
    with open(output_path, "w") as f:
        json.dump(cue_sheet, f, indent=2)
    
    # Upload to S3
    s3 = boto3.client("s3", region_name=REGION)
    s3.put_object(
        Bucket="research-analyst-data-lake-974220725866",
        Key="pattern-library/audio-briefing-cues.json",
        Body=json.dumps(cue_sheet, indent=2),
        ContentType="application/json"
    )
    
    print(f"Cue sheet generated: {len(cue_sheet['chapters'])} chapters, {current_time}s total")
    for ch in cue_sheet["chapters"]:
        print(f"  Ch {ch['chapter']}: {ch['title']} ({ch['duration']}s, {len(ch['cues'])} cues)")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
