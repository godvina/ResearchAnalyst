#!/usr/bin/env python3
"""
Kiro Best Practices Setup — Run this ONCE in any project.

Creates .kiro/steering/ files and hooks that encode 52+ lessons learned
from production AWS failures. Works on new or existing projects.

Usage:
    python kiro-setup.py

Or copy this script to any project and run it there.
"""
import os
import sys

PLAYBOOK = '''---
inclusion: auto
---

# Kiro Builder Playbook

Follow these rules on every task. Learned from 52+ production failures.

## Before You Build
1. Read project docs (lessons-learned.md, README, steering files) before writing code
2. Test 10 samples before processing 100+ items through any AI model
3. Check IAM permissions before launching any EC2 or cross-service script
4. Show time estimate math: total_items x time_per_item = total_time. Add 50% buffer.

## While You Build
5. EXTEND working code, never REPLACE it
6. Deploy Lambda via S3, never --zip-file fileb://
7. Clean __pycache__ before every Python Lambda deploy
8. Use EC2 for any process over 30 minutes (laptops sleep)
9. Verify actual output within 2 minutes of any launch
10. Never terminate a working process to replace with an improved version

## After You Build
11. Test demo/production case before reporting success
12. Check CloudWatch logs after first deploy
13. Document every failure in docs/lessons-learned.md

## EC2 Rules
- Always install boto3 in userdata: pip3 install boto3 || yum install -y python3-pip && pip3 install boto3
- Never suppress errors with || true on critical installs
- Always self-terminate and upload logs to S3
- Use __.V() not g.V() for Neptune anonymous traversals

## Database Rules
- Never ALTER TABLE ADD COLUMN DEFAULT on large tables in Aurora Serverless
- Never insert one row at a time for bulk loads (batch 100+)
- Use separate tracking tables for batch progress
- Verify row counts after ingestion

## AI/ML Rules
- Run model bake-off before any bulk extraction
- Use constrained prompts listing ONLY the output types you want
- Verify model output JSON structure matches parser DURING testing
- Choose precision over cost
'''

LAUNCH_PROTOCOL = '''---
inclusion: auto
---

# Launch and Verify Protocol

Every time you launch a process (EC2, Lambda, batch job), follow this. No exceptions.

## Pre-Launch
1. Read lessons-learned.md for known issues
2. Calculate time estimate with math
3. Check IAM permissions for every API call
4. Test with 1-2 items locally first

## Post-Launch (MANDATORY)
- T+0: Launch
- T+90s: Check console output or logs
- T+3min: If no output, investigate immediately
- T+5min: Verify metric is changing
- Every hour: Re-check running processes

## Rules
- Never give estimates without showing the math
- Add 50% buffer to all estimates
- Never say "it is running" without verified metric increase
- If process > 30 min, use EC2
- For bulk Aurora inserts, use batch (100+ rows)
- For bulk Bedrock calls, use Batch Inference API
'''

LESSONS_LEARNED = '''# Lessons Learned

Document every issue encountered during development.
Any future session MUST read this file before making changes.

## Template

### Issue N: Title

**Problem**: What happened
**Root cause**: Why it happened
**Fix**: How it was fixed
**Prevention**: How to avoid it next time
**File**: Which files were affected
'''

HOOK = '''{
    "name": "Session Rules Reminder",
    "version": "1.0.0",
    "description": "Reminds the agent to follow best practices on every prompt",
    "when": {
        "type": "promptSubmit"
    },
    "then": {
        "type": "askAgent",
        "prompt": "Follow the rules in .kiro/steering/kiro-builder-playbook.md. Check for running EC2 instances if this is an AWS project. Read docs/lessons-learned.md before making infrastructure changes."
    }
}
'''

def main():
    print("=" * 50)
    print("Kiro Best Practices Setup")
    print("=" * 50)

    # Create directories
    for d in [".kiro/steering", ".kiro/hooks", "docs"]:
        os.makedirs(d, exist_ok=True)

    created = []
    skipped = []

    # Create files (don't overwrite existing)
    files = {
        ".kiro/steering/kiro-builder-playbook.md": PLAYBOOK,
        ".kiro/steering/launch-and-verify-protocol.md": LAUNCH_PROTOCOL,
        "docs/lessons-learned.md": LESSONS_LEARNED,
        ".kiro/hooks/session-rules.json": HOOK,
    }

    for path, content in files.items():
        if os.path.exists(path):
            skipped.append(path)
            print(f"  SKIP (exists): {path}")
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            created.append(path)
            print(f"  CREATED: {path}")

    print()
    print(f"Created {len(created)} files, skipped {len(skipped)} existing files.")
    print()
    print("Best practices are now active in this project.")
    print("The steering files auto-load on every Kiro session.")
    print("The hook reminds the agent to follow rules on every prompt.")
    print()
    print("To use: just start coding. The rules are always in context.")


if __name__ == "__main__":
    main()
