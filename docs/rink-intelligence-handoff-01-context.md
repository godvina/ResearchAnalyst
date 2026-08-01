# Rink Intelligence — Handoff Doc 1: Project Context & Vision

Paste this whole file as your FIRST message in the new Kiro workspace
(`Art of Possible Demos/Rink-Intelligence`).

## The Idea

Art of the Possible demo showing AWS pattern-finding (Neptune graph +
OpenSearch + Bedrock) applied to NHL hockey data instead of law enforcement
case data. Same architecture pattern as the "Research Analyst" investigative
intelligence platform, completely different domain — public, low-sensitivity
data that's easy to demo without any redaction/fictionalization concerns.

## What We're Building

1. **Assist-chain network graph (Neptune)** — for every goal, build a
   weighted graph of players: `scorer <- assist1 <- assist2`. Aggregate
   across a season to find "who feeds whom" patterns per team/player.
2. **Pattern search over goals (OpenSearch)** — index every goal with
   situational metadata (strength state, zone, shot type, time remaining,
   off a takeaway/giveaway, empty net, etc.) so you can query things like
   "show me all 5v5 game-winning goals scored within 90 seconds of a
   takeaway in the defensive zone."
3. **Rink geospatial visualization** — NOT a lat/lng map. A custom
   SVG/Canvas rink diagram (rink coordinate space is x: -100 to 100 ft,
   y: -42.5 to 42.5 ft) showing shot/goal heatmaps and a stylized animated
   reconstruction of the assist chain's event locations leading to a goal.

## IMPORTANT Data Reality (confirmed via research before starting)

- The free NHL API (`api-web.nhle.com`) has NO "pass" event and NO live
  player-tracking/puck-tracking data (that's proprietary NHL Edge tracking,
  sold via Sportlogiq/Stathletes — not available free).
- What IS available per goal: scorer + up to 2 credited assists
  (`assist1PlayerId`, `assist2PlayerId`), each with period/time. This gives
  a real 2-3 hop assist chain — genuinely demoable in Neptune — but it is
  NOT a full possession/passing sequence of every touch in the minute
  before the goal.
- Other events (`shot-on-goal`, `missed-shot`, `blocked-shot`, `hit`,
  `giveaway`, `takeaway`, `faceoff`) DO have x/y rink coordinates. These
  are real and usable for the geospatial heatmap and for building a
  stylized (not literal) animated reconstruction.
- Framing for the demo audience: "Here's what 3 AWS services find in
  publicly available structured event data — no proprietary tracking feed
  required." Don't oversell it as a literal replay.

## Why This Is a Good/Unique Demo

- Visual, universally relatable audience (vs. law enforcement case data).
- Most public hockey analytics content is shot charts / Corsi-Fenwick
  stats. An assist-network graph in Neptune + OpenSearch situational
  pattern search over goals is a less common combination — good
  differentiator for "Art of the Possible."
- Reuses a proven architecture (see Handoff Doc 2) so infra stand-up should
  be much faster than the first time.

## Recommended Phased Build

1. **Ingestion** — pull schedule → game IDs → play-by-play JSON per game →
   raw JSON to S3. Start small: 1-2 seasons, a handful of marquee teams.
2. **Local data shape check FIRST** — before touching AWS, write one
   script that pulls play-by-play for ~10 games and dumps parsed goal
   events (scorer, assists, locations, situational metadata) to a local
   JSON file. Confirms the data is rich enough before investing in infra.
3. **Neptune** — parse goals into vertices/edges, build the assist-chain
   graph, weighted by frequency across a season.
4. **OpenSearch** — index goal events with full situational metadata.
5. **Rink geospatial** — Canvas/SVG rink diagram, shot/goal heatmaps,
   animated assist-chain reconstruction (stylized, not literal replay).

## Key NHL API Endpoints (confirmed working, no auth required)

Base URL: `https://api-web.nhle.com/`

- `/v1/schedule/{date}` — games on a given date (YYYY-MM-DD)
- `/v1/club-schedule-season/{team}/{season}` — full season schedule for a
  team (season format YYYYYYYY, e.g. `20242025`; team = 3-letter code e.g.
  `TOR`, `BOS`)
- `/v1/gamecenter/{game-id}/play-by-play` — full play-by-play for a game,
  includes every event with type, period, time, players involved, and
  x/y location where applicable. THIS IS THE MAIN DATA SOURCE.
- `/v1/gamecenter/{game-id}/boxscore` — boxscore summary
- `/v1/gamecenter/{game-id}/landing` — game landing page data (summary,
  scoring plays with assist info in a friendlier shape than raw PBP)
- `/v1/roster/{team}/{season}` — team roster for a season
- `/v1/season` — list of all season IDs (use to know date range available)

Unofficial but well-maintained reference (community-documented, matches
what we tested): https://github.com/Zmalski/NHL-API-Reference

No API key needed. Be a good citizen: cache aggressively to S3, don't
hammer the API — this is undocumented/unofficial and could rate-limit or
change without notice.

## What NOT to do

- Don't put this in the Research Analyst workspace/repo — different data
  domain, different audience, keep them separated (see Handoff Doc 2 for
  what to reuse vs. rebuild).
- Don't build a literal video-game-style replay — the tracking data to do
  that legitimately isn't in the free API. Build a stylized reconstruction
  instead and say so in the demo narration.
- Don't try to pull all 32 teams x 10 seasons on day one. Start with 1-2
  teams, 1-2 seasons, prove the pipeline, then scale ingestion.
