"""Build combined audio data file with URLs + narration + cue sheets."""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

# Read source data
manifest = json.load(open(os.path.join(DATA_DIR, "audio-manifest-v2.json")))
script = json.load(open(os.path.join(DATA_DIR, "expanded-documentary-script.json")))
deep = json.load(open(os.path.join(DATA_DIR, "deep-dive-episodes.json")))

# Map chapter IDs to manifest entries (URLs)
manifest_map = {}
for ep in manifest.get("episodes", []):
    for ch in ep.get("chapters", []):
        manifest_map[ch["chapter_id"]] = ch
for dd in manifest.get("deep_dives", []):
    for ch in dd.get("chapters", []):
        manifest_map[ch["chapter_id"]] = ch

# Site coordinates for cue sheet generation
SITE_COORDS = {
    "giza": {"lat": 29.979, "lng": 31.134, "label": "Great Pyramid of Giza"},
    "sedona": {"lat": 34.87, "lng": -111.76, "label": "Sedona Vortexes"},
    "mohenjo": {"lat": 27.324, "lng": 68.138, "label": "Mohenjo-daro"},
    "angkor": {"lat": 13.412, "lng": 103.866, "label": "Angkor Wat"},
    "easter": {"lat": -27.116, "lng": -109.349, "label": "Easter Island"},
    "nazca": {"lat": -14.692, "lng": -75.130, "label": "Nazca Lines"},
    "stonehenge": {"lat": 51.179, "lng": -1.826, "label": "Stonehenge"},
    "teotihuacan": {"lat": 19.692, "lng": -98.844, "label": "Teotihuacan"},
    "persepolis": {"lat": 29.935, "lng": 52.891, "label": "Persepolis"},
    "tiwanaku": {"lat": -16.555, "lng": -68.673, "label": "Tiwanaku"},
}

def generate_cues_from_narration(narration, chapter_id):
    """Auto-generate map cues by finding site mentions in narration text."""
    cues = []
    text_lower = narration.lower()
    words = narration.split()
    total_duration = len(words) / 2.5  # estimated seconds

    for site_key, coords in SITE_COORDS.items():
        # Find position of site mention in text (as fraction of total)
        pos = text_lower.find(site_key)
        if pos >= 0:
            # Estimate timestamp based on character position
            fraction = pos / max(len(narration), 1)
            timestamp = int(fraction * total_duration)
            cues.append({
                "time": timestamp,
                "action": "highlight_site",
                "target": {"lat": coords["lat"], "lng": coords["lng"], "zoom": 5},
                "label": coords["label"]
            })

    # Sort by time
    cues.sort(key=lambda c: c["time"])
    return cues


# Build combined output
audio_data = {
    "title": "The Grid — AI Documentary Series",
    "subtitle": "An AI-Powered Investigation of Earth's Hidden Geometry",
    "episodes": [],
    "deep_dives": []
}

# Episodes
for ep in script.get("episodes", []):
    ep_data = {"id": ep["id"], "title": ep["title"], "subtitle": ep.get("subtitle", ""), "chapters": []}
    for ch in ep.get("chapters", []):
        m = manifest_map.get(ch["id"], {})
        cues = generate_cues_from_narration(ch.get("narration", ""), ch["id"])
        ep_data["chapters"].append({
            "id": ch["id"],
            "title": ch["title"],
            "url": m.get("url", ""),
            "duration": ch.get("estimated_seconds", 60),
            "narration": ch.get("narration", ""),
            "cues": cues,
        })
    audio_data["episodes"].append(ep_data)

# Deep dives
for dd in deep.get("deep_dives", []):
    dd_data = {"id": dd["id"], "title": dd["title"], "subtitle": dd.get("subtitle", ""),
               "parent": dd.get("parent_chapter", ""), "chapters": []}
    for ch in dd.get("chapters", []):
        m = manifest_map.get(ch["id"], {})
        cues = generate_cues_from_narration(ch.get("narration", ""), ch["id"])
        dd_data["chapters"].append({
            "id": ch["id"],
            "title": ch["title"],
            "url": m.get("url", ""),
            "duration": ch.get("estimated_seconds", 240),
            "narration": ch.get("narration", ""),
            "cues": cues,
        })
    audio_data["deep_dives"].append(dd_data)

# Save
output_path = os.path.join(DATA_DIR, "audio-combined-v2.json")
with open(output_path, "w") as f:
    json.dump(audio_data, f, indent=2)

# Stats
total_eps = len(audio_data["episodes"])
total_ep_ch = sum(len(e["chapters"]) for e in audio_data["episodes"])
total_dd = len(audio_data["deep_dives"])
total_dd_ch = sum(len(d["chapters"]) for d in audio_data["deep_dives"])
total_cues = sum(len(c["cues"]) for e in audio_data["episodes"] for c in e["chapters"])
total_cues += sum(len(c["cues"]) for d in audio_data["deep_dives"] for c in d["chapters"])

print(f"Episodes: {total_eps} with {total_ep_ch} chapters")
print(f"Deep dives: {total_dd} with {total_dd_ch} chapters")
print(f"Total map cues generated: {total_cues}")
print(f"Saved: {output_path}")
