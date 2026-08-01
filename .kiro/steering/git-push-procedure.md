# Git Push Procedure

When the user says "push to git", "commit and push", or "sync to repos", follow this procedure.

## Remotes

This project has two git remotes:

1. **origin** (GitLab): `git@ssh.gitlab.aws.dev:agentic-ai-demos/agentic-ai-demo-investigative-intelligence.git`
   - Push via SSH (requires `mwinit -f` to be run first in an external terminal)
   - Command: `$env:GIT_SSH_COMMAND = "ssh -o StrictHostKeyChecking=no"; git push origin main`

2. **github** (GitHub): `https://github.com/godvina/ResearchAnalyst`
   - Push via GitHub Contents API (git SSH is blocked by corporate firewall)
   - Command: `$env:GITHUB_TOKEN = "<token>"; python scripts/push_to_github.py`
   - The token must be set as env var — never hardcode it
   - Ask the user for the token if not available

## Push Steps

1. Stage changed files: `git add -A` (but review what's staged first)
2. Commit: `git commit -m "description of changes"`
3. Push to GitLab: `$env:GIT_SSH_COMMAND = "ssh -o StrictHostKeyChecking=no"; git push origin main`
4. Push to GitHub: `$env:GITHUB_TOKEN = "<ask user>"; python scripts/push_to_github.py`

## Prerequisites

- User must run `mwinit -f` in an external PowerShell window before GitLab push
- SSH key must exist at `~/.ssh/id_ecdsa` (one-time: `ssh-keygen -t ecdsa -b 256`)
- GitHub token must be provided by user (never stored in code)

## Important

- Always clean `__pycache__` before committing
- Never commit `scripts/set_brave_key.py` (contains real API key)
- The `.gitignore` excludes pip packages, data files, deploy zips, and credential files
- Update `deploy-package/` with fresh `cdk synth` output before major pushes
