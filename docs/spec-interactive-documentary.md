# Interactive Documentary — Requirements & Design

## Vision Statement

A **living documentary** that narrates research findings while simultaneously animating the investigation dashboard, discovering new evidence in real-time, and adapting to the viewer's interests. Unlike traditional documentaries which are pre-recorded and static, this system generates content dynamically, responds to viewer engagement, and triggers live research during playback.

**Target experience**: Running on a treadmill wearing Meta glasses, listening to AI-narrated research findings while seeing the global grid animate, sites highlight, and new discoveries pop up in real-time.

---

## Requirements

### R1: Timestamp-Synced Map Animation
**Priority: P0 (build now)**

As audio plays, the geographic map and network graph animate in sync:
- Each chapter has a cue sheet mapping timestamps to node IDs and actions
- Map zooms to relevant location when narrator mentions it
- Nodes pulse/highlight when discussed
- Network graph below shows the relevant connections for current topic
- Sidebar displays contextual cards matching the current narration

**Acceptance Criteria:**
- Map animates within 0.5s of narrator mentioning a site
- At least 3 map transitions per chapter
- Network graph updates per chapter (shows relevant pattern)
- Smooth transitions (pan/zoom, not jump cuts)

### R2: Live Research Triggers
**Priority: P1 (next session)**

Background agents search for new evidence during playback:
- One Tavily search per chapter on the current topic
- If new information found (post our research date), display "🆕 New Finding" card
- Card shows title, source, date, and one-line summary
- User can tap/click to pause and explore, or dismiss and continue
- New findings are cached to Aurora for future briefings

**Acceptance Criteria:**
- Search completes within 5s of chapter start (background, non-blocking)
- Only shows "new" if published after our last research date
- Maximum 1 popup per chapter (not overwhelming)
- Popup auto-dismisses after 10s if not interacted with

### R3: Progressive Revelation (Multi-Listen)
**Priority: P2 (future)**

Each time the user listens, content adapts based on previous engagement:
- First listen: Overview (the 7 chapters we have today)
- Second listen: Goes deeper on patterns where user paused or replayed
- Third listen: Focuses on unexplained gaps and suggests field research
- Tracks which chapters were replayed, skipped, or paused

**Acceptance Criteria:**
- System remembers at least 3 listening sessions
- Content of chapters 2+ changes based on engagement signals
- Never repeats the same narration verbatim in subsequent listens
- User can reset to "fresh listen" mode

### R4: Branching Narratives
**Priority: P2 (future)**

Voice or gesture commands allow viewer to steer the documentary:
- "Tell me more about this" → generates and plays a deep-dive segment
- "Skip this" → jumps to next chapter
- "Go deeper on the connection" → triggers cross-pattern agent + narrates result
- "What's new here?" → triggers live Tavily search + narrates finding

**Acceptance Criteria:**
- Voice recognition via Web Speech API (no external service)
- Response generated and narrated within 15s of command
- At least 3 branching commands supported
- Can resume main narrative after branch

### R5: Spatial Computing (Meta Glasses / WebXR)
**Priority: P3 (future — requires hardware)**

3D immersive experience for AR/VR headsets:
- Globe rendered in 3D space (user looks around it)
- Spatial audio (narration about Giza comes from the direction of Egypt)
- Gesture-based interaction (pinch a node to expand its brief)
- Nodes float in space showing network relationships
- Walking on treadmill = traveling along a ley line

**Acceptance Criteria:**
- WebXR compatible (works in Meta Quest browser)
- Maintains 72fps minimum for comfort
- Spatial audio positioning accurate to ±15°
- Gesture recognition for pinch, point, and grab

### R6: Collaborative Listening
**Priority: P3 (future — multi-tenant)**

Multiple researchers listen simultaneously:
- Shared session where multiple users hear the same briefing
- When one user bookmarks/flags a finding, others are notified
- "Research party" mode — distributed team investigating together
- Chat/voice overlay for discussion

**Acceptance Criteria:**
- WebSocket-based real-time sync between 2-10 listeners
- Bookmark notifications appear within 1s across all connected users
- Audio stays synchronized (±0.5s drift maximum)

### R7: Context-Aware Triggers (GPS)
**Priority: P3 (future — mobile)**

If user is physically near a grid vertex or known site:
- Detect GPS proximity to any of the 62 vertices
- Automatically narrate information about the nearest node
- "You're 50km from Vertex 17 — the Sedona Vortex. Here's what we know..."
- Trigger field research recommendations for that specific location

**Acceptance Criteria:**
- GPS detection within 100km radius of any vertex
- Narration triggers automatically (opt-in) when entering radius
- Works in mobile browser (navigator.geolocation)
- Battery-efficient (checks position every 60s, not continuously)

### R8: Personalization Engine
**Priority: P2 (future)**

AI learns from engagement patterns to personalize future briefings:
- Tracks: pause points, replay segments, skip patterns, branch choices
- Builds interest profile: "This user is interested in megalithic construction, less interested in ocean nodes"
- Next briefing emphasizes their interests, introduces ONE new topic per session
- "Based on your listening history, you might find this connection interesting..."

**Acceptance Criteria:**
- Profile built from minimum 3 listening sessions
- Content ranking adjusts demonstrably after 5 sessions
- User can view and edit their interest profile
- "Surprise me" mode ignores personalization for serendipity

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (browser / WebXR)                 │
├─────────────────────────────────────────────────────────────┤
│  Audio Player │ Map Animation │ Network Graph │ Popup Cards  │
│       ↕              ↕              ↕              ↕         │
│              CUE SHEET ENGINE (JavaScript)                    │
│     Reads timestamps → triggers map/graph/card actions       │
├─────────────────────────────────────────────────────────────┤
│                        API GATEWAY                            │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│  Audio   │  Cue     │  Live    │ Research │  Personalization │
│  (Polly) │  Sheet   │  Search  │  Data    │  (Aurora)        │
│          │  (S3)    │  (Tavily)│  (S3/OS) │                  │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│                    BEDROCK (narration generation)             │
│                    POLLY (text-to-speech)                     │
│                    TAVILY (live web search)                   │
│                    OPENSEARCH (pattern detection)             │
│                    AURORA (cache + personalization)           │
└─────────────────────────────────────────────────────────────┘
```

### Cue Sheet Format

```json
{
  "version": "1.0",
  "total_duration_seconds": 420,
  "chapters": [
    {
      "chapter": 1,
      "title": "The Theory",
      "start_time": 0,
      "end_time": 60,
      "cues": [
        {"time": 5, "action": "zoom", "target": {"lat": 20, "lng": 20, "zoom": 2}, "label": "Global view"},
        {"time": 15, "action": "highlight_nodes", "nodes": [1, 12, 25, 35, 47], "color": "#ecc94b"},
        {"time": 30, "action": "focus_pattern", "pattern": "sacred"},
        {"time": 45, "action": "show_card", "card": {"title": "62 Vertices", "text": "The Becker-Hagens grid..."}}
      ],
      "live_search_query": "UVG grid Becker Hagens new research 2026"
    }
  ]
}
```

### Cue Actions (supported):
- `zoom` — pan/zoom map to coordinates
- `highlight_nodes` — pulse specific node IDs
- `highlight_site` — highlight a known site by name
- `focus_pattern` — activate pattern focus mode
- `show_network` — show network graph for pattern
- `show_card` — display info card in sidebar
- `show_finding` — display new finding popup
- `clear` — reset to default view

### Audio Generation Pipeline

```
Research data
  → Bedrock generates narration script + cue sheet simultaneously
  → Polly converts narration to MP3 (with SSML marks for timing)
  → S3 stores: audio files + cue sheet JSON + manifest
  → Frontend loads manifest → plays audio → reads cue sheet → animates
```

### Live Search Integration

```
Chapter starts playing
  → Frontend fires background fetch to /grid/live-search?topic={chapter_topic}
  → Lambda runs Tavily search (1 call)
  → Compares result dates against our research_date
  → If newer: returns {new_finding: true, title, source, date, summary}
  → Frontend shows "🆕" popup at appropriate moment
  → Finding cached to Aurora for future reference
```

---

## Implementation Phases

### Phase 1 (TODAY): Timestamp-Synced Animation
- Generate cue sheet alongside audio
- Frontend reads cues and animates map/graph
- No live search yet — just pre-computed animations
- Estimated: 45 minutes

**BUILT (2026-08-01):**
- Cue sheet with 25 cues across 7 chapters (inline in HTML)
- Cue engine polls every 500ms, checks audio.currentTime against cue timestamps
- Supported actions: zoom, highlight_site (gold ring + label popup), focus_pattern
- Two modes: "Play All" (absolute time, full MP3) and individual chapter (offset time)
- Chapter buttons for jumping between sections
- Progress scrubber, ⏪/⏩ seek, speed control (0.75x-2x)
- CC captions with highlighted current word (inline script data)

**What the user should see:**
- Click "▶ All" → audio starts → at ~10s into Ch3 (Sacred Sites), map activates sacred pattern focus
- At ~25s into Ch3: map zooms to Sedona with gold ring + "Sedona Vortexes" label
- At ~45s into Ch3: map zooms to Lake Baikal
- Ch4 (Connections): map zooms to Giza, then Angkor Wat, then Easter Island sequentially
- Ch5: activates submerged pattern; Ch6: activates tectonic pattern
- Ch7: zooms to Nazca Lines, then Mohenjo-daro
- Between chapters: returns to global view

**Known limitations:**
- Timing is approximate (based on Polly's speech rate, not word-level timestamps)
- No SSML marks from Polly (would need to use SpeechMarkTypes for precise sync)
- Network graph doesn't auto-show during audio (only on manual pattern click)

### Phase 2 (NEXT SESSION): Live Research Triggers
- Add Tavily background search per chapter
- "New finding" popup UI
- Cache findings to Aurora
- Estimated: 2 hours

### Phase 3 (FUTURE): Branching + Personalization
- Voice command integration (Web Speech API)
- Engagement tracking (pause/replay/skip signals)
- Personalized briefing generation
- Estimated: 1-2 days

### Phase 4 (FUTURE): Spatial Computing
- WebXR prototype for Meta Quest
- Spatial audio positioning
- Gesture-based interaction
- Estimated: 1 week (with WebXR experience)

---

## Cost Impact

| Component | Per Briefing | Monthly (daily use) |
|-----------|-------------|---------------------|
| Bedrock (script + cue gen) | ~$0.05 | ~$1.50 |
| Polly (7 chapters audio) | ~$0.08 | ~$2.40 |
| Tavily (7 live searches) | 7 credits | 210 credits/month |
| S3 (audio storage) | ~3MB | ~90MB/month |
| **Total** | **~$0.13** | **~$4/month** |

Essentially free to run daily.

---

## Success Metrics

1. **Engagement**: User listens to >80% of briefing (vs skipping)
2. **Discovery**: Live search finds "new" information in >30% of chapters
3. **Return**: User generates 2+ briefings per week
4. **Action**: User clicks through to investigate a finding after listening in >50% of sessions
