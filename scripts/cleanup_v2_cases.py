"""Cleanup: Delete the 14 fragmented "Epstein Files v2" cases from the sidebar.

Lists all cases, identifies the v2 fragments, and deletes them.
The Epstein Main (7f05e8d5) and Epstein Combined cases are preserved.

Usage:
    python scripts/cleanup_v2_cases.py --dry-run   # list what would be deleted
    python scripts/cleanup_v2_cases.py --confirm    # actually delete them
"""
import argparse
import json
import urllib.request

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

# Cases to NEVER delete
PROTECTED_CASE_IDS = [
    "7f05e8d5",  # Epstein Main (Original) — partial match is fine
]


def list_cases():
    url = f"{API_URL}/case-files"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
    return result.get("case_files", result.get("cases", []))


def delete_case(case_id):
    url = f"{API_URL}/case-files/{case_id}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True
    except Exception as e:
        print(f"  ERROR deleting {case_id}: {str(e)[:200]}")
        return False


def is_v2_fragment(case):
    """Identify the fragmented v2 cases by name pattern."""
    name = (case.get("topic_name") or case.get("name") or "").lower()
    case_id = case.get("case_id", "")

    # Protect specific cases
    for protected in PROTECTED_CASE_IDS:
        if protected in case_id:
            return False

    # Match v2 fragment patterns
    if "epstein files v2" in name:
        return True
    if "epstein" in name and ("batch" in name or "v2" in name):
        return True

    return False


def main():
    parser = argparse.ArgumentParser(description="Delete fragmented Epstein v2 cases")
    parser.add_argument("--confirm", action="store_true", help="Actually delete")
    parser.add_argument("--dry-run", action="store_true", help="Just list what would be deleted")
    args = parser.parse_args()

    print("=" * 60)
    print("Cleanup: Delete Fragmented Epstein v2 Cases")
    print("=" * 60)

    print("\nListing all cases...")
    cases = list_cases()
    print(f"  Found {len(cases)} total cases")

    v2_cases = [c for c in cases if is_v2_fragment(c)]
    keep_cases = [c for c in cases if not is_v2_fragment(c)]

    print(f"\nCases to DELETE ({len(v2_cases)}):")
    for c in v2_cases:
        name = c.get("topic_name") or c.get("name", "?")
        cid = c.get("case_id", "?")
        doc_count = c.get("document_count", "?")
        print(f"  - {cid[:8]}... {name} ({doc_count} docs)")

    print(f"\nCases to KEEP ({len(keep_cases)}):")
    for c in keep_cases:
        name = c.get("topic_name") or c.get("name", "?")
        cid = c.get("case_id", "?")
        doc_count = c.get("document_count", "?")
        print(f"  + {cid[:8]}... {name} ({doc_count} docs)")

    if args.dry_run:
        print(f"\n[DRY RUN] Would delete {len(v2_cases)} cases.")
        return

    if not args.confirm:
        print("\nRun with --confirm to delete, or --dry-run to preview.")
        return

    if not v2_cases:
        print("\nNo v2 cases found to delete.")
        return

    print(f"\nDeleting {len(v2_cases)} cases...")
    deleted = 0
    for c in v2_cases:
        cid = c.get("case_id")
        name = c.get("topic_name") or c.get("name", "?")
        if delete_case(cid):
            print(f"  Deleted: {cid[:8]}... {name}")
            deleted += 1

    print(f"\n{'=' * 60}")
    print(f"CLEANUP COMPLETE — {deleted}/{len(v2_cases)} cases deleted")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
