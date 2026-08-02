"""Merge intro briefing + deep-dive episodes into the inline audio data file."""
import json
import re

# Read current inline audio (has overview episodes)
with open('src/data/_inline_audio_v2.js', 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'var INLINE_AUDIO_V2\s*=\s*(\{[\s\S]*\})\s*;?\s*$', content)
audio_data = json.loads(match.group(1))

# Read the original intro briefing
with open('src/data/audio-briefing-script.json', 'r', encoding='utf-8') as f:
    briefing = json.load(f)
with open('src/data/audio-briefing-manifest.json', 'r', encoding='utf-8') as f:
    manifest_briefing = json.load(f)

# Read deep dives (narration text)
with open('src/data/deep-dive-episodes.json', 'r', encoding='utf-8') as f:
    deep_data = json.load(f)

# Read audio manifest (has deep dive URLs)
with open('src/data/audio-manifest-v2.json', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Build URL lookup from manifest deep dives
dd_url_map = {}  # chapter_id -> url
for dd in manifest.get('deep_dives', []):
    for ch in dd.get('chapters', []):
        cid = ch.get('chapter_id', '')
        url = ch.get('url', '')
        duration = ch.get('duration_estimate_s', 240)
        dd_url_map[cid] = {'url': url, 'duration': duration}

print(f"Deep dive URLs in manifest: {len(dd_url_map)}")

# Build intro episode from briefing
base_url = manifest_briefing.get('chapter_base_url',
    'https://research-analyst-data-lake-974220725866.s3.us-east-1.amazonaws.com/audio/')
intro_chapters = []
for ch in briefing['chapters']:
    s3_key = f"briefing-chapter-{ch['chapter']:02d}.mp3"
    url = base_url + s3_key
    intro_chapters.append({
        "id": f"1.{ch['chapter']}",
        "title": ch['title'],
        "url": url,
        "duration": 120,
        "narration": ch['narration'],
        "cues": []
    })

intro_episode = {
    "id": "ep1",
    "title": "The Global Grid: What the AI Found",
    "subtitle": "Introduction",
    "type": "intro",
    "chapters": intro_chapters
}

# Get the existing overview episodes (strip any deep dives already merged)
overview_episodes = [ep for ep in audio_data['episodes'] if ep.get('type') != 'deep-dive']
# Also strip the intro if it was already added
overview_episodes = [ep for ep in overview_episodes if ep['id'] != 'ep1']

# Merge deep dive URLs into deep_data chapters
for dd in deep_data['deep_dives']:
    for ch in dd['chapters']:
        cid = ch.get('id', '')
        if cid in dd_url_map:
            ch['url'] = dd_url_map[cid]['url']
            ch['duration'] = dd_url_map[cid]['duration']
        else:
            # Try matching by chapter_id pattern
            # deep-dive chapters use ids like "2.2.1", manifest uses same
            ch['url'] = ''
            ch['duration'] = ch.get('estimated_seconds', 240)

# Interleave deep dives after their parent overviews
new_episodes = [intro_episode]

for ep in overview_episodes:
    new_episodes.append(ep)
    ep_num = ep['id'].replace('ep', '')
    for dd in deep_data['deep_dives']:
        dd_ep_num = dd['id'].replace('deep-', '').split('.')[0]
        if dd_ep_num == ep_num:
            dd_entry = dict(dd)
            dd_entry['type'] = 'deep-dive'
            new_episodes.append(dd_entry)

audio_data['episodes'] = new_episodes

print(f"\nTotal episodes: {len(new_episodes)}")
total_chapters = 0
missing_urls = 0
for ep in new_episodes:
    t = ep.get('type', 'overview')
    chs = len(ep['chapters'])
    total_chapters += chs
    no_url = sum(1 for ch in ep['chapters'] if not ch.get('url'))
    status = f" ({no_url} missing URLs)" if no_url else ""
    print(f"  [{ep['id']}] {ep['title']} ({t}, {chs} ch){status}")
    missing_urls += no_url
print(f"\nTotal chapters: {total_chapters}, Missing URLs: {missing_urls}")

# Write
output = 'var INLINE_AUDIO_V2 = ' + json.dumps(audio_data, ensure_ascii=False) + ';'
with open('src/data/_inline_audio_v2.js', 'w', encoding='utf-8') as f:
    f.write(output)

print("\nDone.")
