# Pattern Library Sync Strategy

## Problem
Two projects share the same pattern taxonomy system:
- **Research Analyst** (this project) — crime + ancient mysteries
- **RINK Intelligence** (other project) — sports patterns (uses same hierarchy concept)

When signatures are added/modified in one project, the other should be notified and given the option to accept changes.

## Recommended Approach: Shared Git Submodule + PR Workflow

### Architecture
```
github.com/godvina/pattern-library-shared/    ← NEW shared repo
├── crime-taxonomy.json
├── ancient-mysteries-taxonomy.json
├── sports-taxonomy.json (future)
└── CHANGELOG.md

Research Analyst project:
└── src/data/pattern-library/  ← git submodule pointing to shared repo

RINK Intelligence project:
└── src/data/pattern-library/  ← same git submodule
```

### How It Works
1. **Adding new signatures**: Author creates a branch on the shared repo, adds signatures, opens a PR
2. **Human review**: PR shows diff — reviewer sees exactly what changed (new method? new signature? modified vector_text?)
3. **Approval**: Reviewer approves → merged to main
4. **Notification**: Each consuming project gets a Dependabot-style alert: "Submodule has new commits"
5. **Pull**: Developer runs `git submodule update` in each project to accept (or pins to specific commit to delay)

### Simpler Alternative: Kiro Hook + Manual Trigger

If git submodules feel heavy, use a **Kiro userTriggered hook** that:
1. Reads the taxonomy JSON from a shared location (S3 bucket, shared drive, or other project folder)
2. Compares with local copy
3. Shows diff to user
4. On approval, writes the updated file locally

### S3-Based Sync (for deployed environments)
```
s3://pattern-library-shared/
├── crime-taxonomy.json
├── ancient-mysteries-taxonomy.json
└── manifest.json (versions, checksums)

Lambda (on schedule or EventBridge):
1. Compare local Aurora signature count vs S3 manifest
2. If S3 has newer version → queue re-index job
3. Re-index only new/modified signatures (hash comparison)
4. Notify admin via SNS before applying
```

### Human-in-the-Loop Controls
- **Never auto-overwrite** — always queue changes for review
- **Diff view** — show exactly which signatures were added/modified/removed
- **Rollback** — keep last 5 versions in S3 with ability to revert
- **Audit log** — who approved what, when

## Implementation Priority
1. For now: manually copy taxonomy files between projects (low frequency of change)
2. Next: S3 shared bucket with Lambda checker (when deployed to AWS)
3. Future: Git submodule with PR workflow (when team grows)
