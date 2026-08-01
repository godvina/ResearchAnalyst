# Feature Note: Research Chat Refinement (Human-in-the-Loop)

## Problem
The concept research agent may not always discover the right things, or may miss important nuances that a human analyst would catch. Currently there's no way for the user to steer the AI's research without modifying code.

## Proposed Feature
Add a chat input box to the Concept Intelligence Briefing panel that lets the user:
1. **Refine the search**: "Also look for the St Michael's Line specifically"
2. **Correct the AI**: "The Becker-Hagens grid is a hypothesis, not established — focus on documented site alignments"
3. **Extend the research**: "What about alignments in South America? I see Nazca and Machu Picchu but what about Tiwanaku?"
4. **Challenge findings**: "This source looks unreliable — find peer-reviewed alternatives"

## Architecture Idea
- Add a text input at the bottom of the Concept Intelligence Briefing panel
- Messages go to a new endpoint: `POST /pattern-library/concept-research/refine`
- The endpoint takes: `{context_key, message, existing_briefing}`
- Sonnet receives the existing concept briefing + user feedback + does targeted follow-up searches
- Updated briefing replaces the current one (and is cached)
- This creates a "conversational research loop" — AI + human analyst working together

## The Ultimate Vision
The concept research should be GOOD ENOUGH that human refinement is rarely needed. But when it is:
- The AI discovers ley lines through research → presents findings
- User says "Add the coordinates for each site on the St Michael's Line"
- AI does follow-up search, geocodes the sites, updates the map layer
- Map now shows the line — sourced from research, verified by human

## Priority
- Complete concept research first (get it working well)
- Add this as augmentation layer after core is solid
- This is essentially "chat with your research" — similar to the existing chatbot.html but scoped to concept research context

## When to Build
After concept research is reliably producing good briefings. Then this becomes the refinement layer that makes it truly interactive, like a research partner rather than a one-shot query.
