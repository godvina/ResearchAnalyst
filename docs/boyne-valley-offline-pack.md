# Boyne Valley Dossier — Offline / Phone Pack (for the Ireland trip)

Goal: open the documentary on your phone with **no cell service** and listen to the narrated
audio. Everything below is a static file — no server, no internet needed once downloaded
(with one small caveat about the maps, noted at the end).

## The URL to use now (with service)
http://127.0.0.1:8000/uap-command-center.html  → click **📕 Pattern Dossiers** → **🗿 The Boyne Valley**
→ press **▶ Play episode (auto-advance)**.

## What to download before you go (copy these onto the phone, keep the folder structure)

From `src/frontend/`:

```
uap-command-center.html          ← the page
config.js
uts-integrity.js
uap-command-data.js
uap-case-store.js
uap-geo.js
uap-convergence.js
uap-leyline-convergence.js
uap-dossiers.js                  ← the documentary text + chapter data
uap-investigator.js
common.css
audio/dossiers/                  ← the narrated MP3s (grab the WHOLE folder — 34 files)
   # Boyne Valley (the 8 you most want for Ireland):
   boyne-valley_bv-hook.mp3
   boyne-valley_bv-newgrange.mp3
   boyne-valley_bv-knowth.mp3
   boyne-valley_bv-cluster.mp3
   boyne-valley_bv-mythology.mp3
   boyne-valley_bv-giza.mp3
   boyne-valley_bv-uap.mp3
   boyne-valley_bv-visit.mp3
   # The other 4 dossiers travel free — copy the whole folder and you get them all:
   nuclear-sentinel_*.mp3     (9 clips)
   silent-triangle_*.mp3      (6 clips)
   radar-visual_*.mp3         (6 clips)
   recurring-hotspot_*.mp3    (5 clips)
   manifest.json
vendor/                          ← Leaflet + D3 libraries (now LOCAL, no internet)
   leaflet.js
   leaflet.css
   leaflet.markercluster.js
   MarkerCluster.css
   MarkerCluster.Default.css
   d3.v7.min.js
   images/marker-icon.png
   images/marker-shadow.png
```

Keep them in the SAME relative layout (i.e. the `audio/dossiers/` and `vendor/` folders sit
next to `uap-command-center.html`). All audio, script, and library paths are **relative**, so
it just works from a folder with no internet.

## How to open it on the phone offline
- Put the folder in your phone's Files app (iOS Files / Android Files), or a cloud folder you
  pre-sync so it's cached locally.
- Tap `uap-command-center.html` → it opens in the browser with no network.
- Go to Pattern Dossiers → Boyne Valley → play each chapter, or "Play episode" to auto-advance.

## The 8 Boyne Valley chapters (~11 min total narrated)
1. Standing in the Bend of the Boyne (map)
2. Newgrange — the Palace of Light (mythology network)
3. Knowth — the Book of the Moon (stats)
4. The wider ritual landscape — Dowth, Tara, Loughcrew (build sequence)
5. The Tuatha Dé Danann — gods from the sky (mythology network)
6. Newgrange and Giza — the global thread (map)
7. The honest question — is there a UAP pattern here? (the real lift result)
8. How to visit — what to look for on the ground (field checklist)

## Also travelling in the pack (5 dossiers total, pick from the picker)
When you open **📕 Pattern Dossiers** you now get a picker with all five:
- 🗿 **The Boyne Valley** — the one for Ireland (above)
- ☢️ **The Nuclear Sentinel** — UAP over strategic/nuclear sites (9 ch, ~13 min)
- 🔺 **The Silent Triangle** — the large silent triangular craft (6 ch, ~7 min)
- 📡 **The Radar-Visual Encounter** — trained observer + instrument agree (6 ch, ~7 min)
- 📍 **The Recurring Hotspot** — Hessdalen and fixed-location clusters (5 ch, ~6 min)

Each has a live **AI investigator** chapter: tap a real case and it runs the 5-step play and
returns a KNOWN/ASSESSED, WEP-rated verdict. (The investigator needs the page's scripts, all of
which are in the download list above — it runs fully offline.)

## Two ways in, now connected
- **The documentary** (`uap-command-center.html` → 📕 Pattern Dossiers → The Boyne Valley): 12
  chapters, ~17 min, per-site deep dives, narrated. **100% offline** — audio, text, and the
  dossier's own maps (self-contained inline SVG drawn from coordinates, no tiles).
- **The map explorer** (`geographic-explorer.html`): tap an Irish site → info panel → a
  **🎬 Watch the documentary chapter** button jumps straight to that site's narrated chapter.
  Sites with a chapter show a **🎧** badge. From a chapter, **📍 See this site on the map** jumps back.

## Offline status — honest
- **Dossier documentary: 100% offline.** Audio, all text, every dossier visual (inline-SVG maps,
  D3 networks). Leaflet + D3 are local in `vendor/`.
- **Map Explorer: mostly offline, ONE caveat.** Its scripts and data are local, and the
  site→chapter hand-off works offline. BUT the Explorer's main Leaflet map uses **OpenStreetMap
  tiles that need signal** — with no service, the map background will be blank while the pins/panels
  still work. For the actual on-location documentary, use the dossier (fully offline); use the
  Explorer map when you have signal.

*Generated 2026-08-22. Rebuild audio: `python scripts/build_boyne_valley_dossier.py; python scripts/generate_dossier_audio.py`.*
