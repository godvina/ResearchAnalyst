---
inclusion: manual
---

# New Project Setup Guide

**Trigger**: When the user says "new project", "starting fresh", "bootstrap", or "what do I need from you"

## What This Does

When you're starting a new Kiro project or a new session, just say:

> "bootstrap" or "new project setup"

And Kiro will:
1. Copy the universal steering files to the new project
2. Generate a session context transfer with all current state
3. List all running AWS processes that need monitoring
4. Summarize what's in progress and what's next

## Files to Copy to Any New Project

These two files encode 52+ lessons from production failures and work on ANY AWS project:

1. `.kiro/steering/kiro-builder-playbook.md` — master operating rules
2. `.kiro/steering/launch-and-verify-protocol.md` — EC2/process launch rules

## For This Specific Project (Investigative Intelligence Platform)

Additional files needed:
3. `.kiro/steering/entity-extraction-rules.md` — extraction pipeline rules
4. `docs/lessons-learned.md` — all 52+ issues with fixes
5. `docs/master-entity-taxonomy.md` — 40 entity types across 10 tiers
6. `docs/new-session-bootstrap.md` — copy-paste block for new sessions

## Quick Reference

Just type any of these in chat:
- **"bootstrap"** — load all context for this project
- **"status"** — check all running processes
- **"what's next"** — see the current task queue
- **"new project"** — get the files you need for a fresh project
