---
inclusion: auto
---

# Session Continuity Protocol — Research Analyst

A repeatable process so work, data, and decisions persist across sessions and are
never lost or forgotten. Follow this every session.

## At the START of a session
1. Read `.kiro/steering/data-assets-registry.md` to know what data already exists.
2. Skim the latest `docs/session-summary-*.md` if the task continues prior work.

## When we ACQUIRE or PROCESS data (download, generate, tier-filter, embed, load)
Do ALL of these in the same turn:
1. Record it in `data-assets-registry.md` (path, count, fields, coverage, script).
2. State the exact absolute path in chat so it is in the transcript.
3. Never re-download without first confirming absence via the registry + a recursive
   search of this workspace AND sibling workspaces.

## Before saying "I can't find X"
1. `file_search`/`grep` are scoped to the current workspace root. If they return
   nothing, WIDEN: recursive `Get-ChildItem` across
   `c:\Users\eyreaws\Documents\Sales\2026\Art of Possible Demos\` before concluding.
2. Check the registry — the thing you're looking for may already be documented.

## At the END of a meaningful chunk of work
1. Write/append a `docs/session-summary-YYYY-MM-DD.md`: what was built, files changed,
   data touched, decisions made, and what's next.
2. Update the registry if data changed.

## Never do
- Never propose re-downloading data that the registry says we have.
- Never claim data is missing based on a workspace-scoped search alone.
- Never lose track of a large dataset we processed — it goes in the registry immediately.
