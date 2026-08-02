# Lessons Learned: Audio-Map Sync System

## Issue (2026-08-01 Session 3)

Audio playback was not triggering map animations (zoom to site, gold highlight ring, PIP photo overlay) despite the cue engine code being intact.

## Root Cause

The `INLINE_AUDIO_V2` variable embedded in `grid-globe.html` did NOT include `cues` arrays in its chapter objects. It only had `title`, `url`, and `duration`. The cues existed in `src/data/audio-combined-v2.json` but the inline copy was stale.

The cue engine checks `window._v2Cues` which gets populated from `ch.cues || []`. With no cues in the inline data, it was always an empty array → no cues ever fired.

## How the Cue System Works

```
1. playV2Chapter(idx) loads a chapter:
   - Sets window._v2Cues = chapter.cues (array of {time, action, target, label})
   - Sets window._v2CuesFired = {} (reset)
   - Calls startCueEngine() → setInterval(processCues, 500ms)

2. processCues() (overridden) checks every 500ms:
   - Reads audio.currentTime
   - For each cue where currentTime >= cue.time and not fired:
     - Marks as fired
     - Calls executeCue(cue)

3. executeCue() handles:
   - 'zoom' → map.flyTo(target coords)
   - 'highlight_site' → gold ring + popup label + flyTo + PIP photo
   - 'focus_pattern' → focus the map on a pattern
```

## Key Architecture Details

- **Data source**: `src/data/audio-combined-v2.json` — the canonical source with cues
- **Inline copy**: `var INLINE_AUDIO_V2` in `grid-globe.html` — must be regenerated when JSON changes
- **Cue times**: RELATIVE to each chapter's MP3 start (not absolute to episode)
- **focusLayer**: Must be added to map before adding markers (`if (!map.hasLayer(focusLayer)) focusLayer.addTo(map)`)
- **HTML onended**: REMOVED from `<audio>` element — JS handler (`audio.onended`) takes priority now

## How to Regenerate Inline Data

When `audio-combined-v2.json` changes (e.g., new cues added, URLs refreshed):

```powershell
# PowerShell — regenerate inline and update HTML
$json = Get-Content "src\data\audio-combined-v2.json" -Raw | ConvertFrom-Json
$compact = $json | ConvertTo-Json -Depth 10 -Compress
$newLine = "var INLINE_AUDIO_V2 = " + $compact + ";"

$lines = Get-Content "src\frontend\grid-globe.html"
$newLines = @()
foreach ($line in $lines) {
    if ($line -match '^var INLINE_AUDIO_V2 = ') { $newLines += $newLine }
    else { $newLines += $line }
}
$newLines | Set-Content "src\frontend\grid-globe.html" -Encoding UTF8
```

## Cue Data Format (in audio-combined-v2.json)

Each chapter can have a `cues` array:
```json
{
  "id": "2.1",
  "title": "Giza — The Confirmed Node",
  "url": "https://...",
  "duration": 72,
  "narration": "There are places on this Earth...",
  "cues": [
    {
      "time": 9,
      "action": "highlight_site",
      "target": {"lat": 29.979, "lng": 31.134, "zoom": 5},
      "label": "Great Pyramid of Giza"
    }
  ]
}
```

## Prevention

1. **Always regenerate inline data** after modifying `audio-combined-v2.json`
2. **Never remove the HTML `<audio>` onended attribute** without updating the inline handler
3. **Test cue firing** by checking browser console for `CUE FIRED:` log messages
4. **Verify inline data has cues** before shipping: search for `"action":"highlight_site"` in HTML
5. **Brace balance check** after every edit: count `{` vs `}` — must be equal
