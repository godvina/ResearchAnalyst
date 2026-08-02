# Feature Note: Interactive Intelligence Discovery Loop (v2)

## Concept

The intelligence brief panel becomes a living, interactive document where:
- Highlighted findings are CLICKABLE — each links to a deeper investigation
- Clicking auto-generates a new brief on that sub-topic (Bedrock or cache)
- The UI transitions from "visual mode" (map/graph) to "deep dive mode" (full-screen reading)
- OpenSearch vector search surfaces related patterns the user didn't ask for

## User Flow

```
1. User sees node brief with highlighted "needles" (interesting findings)
   "This site shares SPIRIT_DWELLING with [5 other sites →]"
                                          ^^^^^^^^^^^^^^^^ clickable

2. User clicks → system generates intelligence brief on that sub-topic
   - Checks cache first (Aurora ai_level_summaries)
   - If miss: calls Bedrock with context from scored findings + vector search
   - Displays: full brief with sources, citations, web links

3. UI expands to "deep dive mode":
   - Map/graph minimizes (20% width left column)
   - Reading panel takes 80% width
   - Text is larger, more readable
   - Visuals auto-generate based on content (timeline, comparison table, etc.)

4. "Did you know?" section pulls from OpenSearch:
   - k-NN similarity finds related findings user didn't search for
   - "Hey, this pattern also appears at [3 other sites] — investigate?"
   - Each suggestion is itself clickable → recursive discovery

5. Sources linked:
   - Researcher citations → Google Scholar link
   - Web results from Tavily → actual URLs
   - "Learn more" → external documentation
```

## Components Needed (all exist)

| Component | Current State | What to Add |
|-----------|--------------|-------------|
| Scored findings | Working | Add "clickable" flag to key indicators |
| Bedrock briefs | Working (level_summary.py) | New prompt template for sub-topic briefs |
| OpenSearch k-NN | Working (emergent patterns) | Query for "related to THIS finding" |
| Tavily web search | Working (agent chain) | Store URLs in scored data for citation links |
| Aurora cache | Working (summary_cache_manager) | Cache generated sub-topic briefs |
| Frontend sidebar | Working | Add "deep dive mode" CSS + layout toggle |

## Design Principles

1. **Never dead-end** — every insight has a "go deeper" action
2. **Skip what bores you** — overview stays concise, depth is opt-in
3. **Always cite sources** — every claim links to a researcher/URL
4. **Surprise the user** — "Did you know?" surfaces connections they didn't ask for
5. **Adapt the UI** — visual mode for exploration, reading mode for comprehension

## Priority: HIGH (for v2 / next session)

This transforms the static intelligence brief into a Wikipedia-like exploration tool
where every fact is a doorway to more investigation.
