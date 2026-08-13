"""
Sync Pattern Library to Finding Fentanyl project.

Copies the master pattern library taxonomy and reference docs from Research Analyst
to the Finding Fentanyl shared/ folder so both projects access the same data.

Run this after any pattern library updates:
    python scripts/sync_pattern_library.py
"""
import shutil
import os
from pathlib import Path

# Paths
RESEARCH_ANALYST = Path(__file__).parent.parent
FINDING_FENTANYL = RESEARCH_ANALYST.parent / "Finding Fentanyl"

# Source files to sync
FILES_TO_SYNC = [
    ("src/data/pattern-library-taxonomy.json", "shared/pattern-library-taxonomy.json"),
    ("docs/PATTERN-LIBRARY-TAXONOMY-REFERENCE.md", "shared/PATTERN-LIBRARY-TAXONOMY-REFERENCE.md"),
    ("src/frontend/succession-cultural-profiles.js", "shared/succession-cultural-profiles.js"),
    ("src/frontend/succession-comp-data.js", "shared/succession-comp-data.js"),
]

def sync():
    if not FINDING_FENTANYL.exists():
        print(f"ERROR: Finding Fentanyl not found at {FINDING_FENTANYL}")
        return

    shared_dir = FINDING_FENTANYL / "shared"
    shared_dir.mkdir(exist_ok=True)

    synced = 0
    for src_rel, dst_rel in FILES_TO_SYNC:
        src = RESEARCH_ANALYST / src_rel
        dst = FINDING_FENTANYL / dst_rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  ✓ {src_rel} → {dst_rel} ({src.stat().st_size // 1024}KB)")
            synced += 1
        else:
            print(f"  ✗ {src_rel} — source not found")

    print(f"\nSynced {synced}/{len(FILES_TO_SYNC)} files to Finding Fentanyl")

if __name__ == "__main__":
    print("Syncing Pattern Library → Finding Fentanyl...")
    print(f"  Source: {RESEARCH_ANALYST}")
    print(f"  Target: {FINDING_FENTANYL}")
    print()
    sync()
