"""Ingestion Ledger — view and update the audit trail for all data loads.

Usage:
    python scripts/ledger.py                  # print summary
    python scripts/ledger.py --detail         # print full detail per load
    python scripts/ledger.py --record         # record a new load entry (called by phase scripts)
"""
import argparse
import json
import os

LEDGER_FILE = os.path.join(os.path.dirname(__file__), "ingestion_ledger.json")


def load_ledger():
    with open(LEDGER_FILE) as f:
        return json.load(f)


def save_ledger(data):
    with open(LEDGER_FILE, "w") as f:
        json.dump(data, f, indent=2)


def print_summary():
    ledger = load_ledger()
    cases = ledger.get("cases", {})

    print("=" * 90)
    print("INGESTION LEDGER — Summary")
    print("=" * 90)

    print(f"\n{'Case':<30} {'Role':<18} {'Loads':>5} {'S3 Docs':>8} {'Pipeline':>10}")
    print("-" * 90)

    for cid, info in cases.items():
        name = info.get("name", "?")
        role = info.get("role", "")
        num_loads = len(info.get("loads", []))
        s3_total = info.get("running_total_s3_docs", 0)
        pipeline_total = sum(
            l.get("docs_sent_to_pipeline", 0) for l in info.get("loads", [])
        )
        print(f"{name:<30} {role:<18} {num_loads:>5} {s3_total:>8} {pipeline_total:>10}")

    # Pending loads
    pending = []
    for cid, info in cases.items():
        for p in info.get("pending_loads", []):
            pending.append((info["name"], p))

    if pending:
        print(f"\nPENDING LOADS:")
        for name, p in pending:
            est = p.get("estimated_docs", "?")
            src = p.get("source", "?")
            print(f"  {name} <- {src} (~{est} docs)")

    # V2 cleanup
    v2 = ledger.get("fragmented_v2_cases", {})
    if v2:
        print(f"\nFRAGMENTED V2 CASES: {v2.get('count', 0)} cases, "
              f"{v2.get('total_docs', 0)} docs total — {v2.get('status', '?')}")

    # Buckets
    buckets = ledger.get("s3_buckets", {})
    if buckets:
        print(f"\nS3 BUCKETS:")
        for key, b in buckets.items():
            print(f"  [{key}] {b['name']}")
            print(f"         {b['contents']}")

    print()


def print_detail():
    ledger = load_ledger()
    cases = ledger.get("cases", {})

    print("=" * 90)
    print("INGESTION LEDGER — Full Detail")
    print("=" * 90)

    for cid, info in cases.items():
        name = info.get("name", "?")
        print(f"\n{'─' * 90}")
        print(f"CASE: {name}")
        print(f"  ID:   {cid}")
        print(f"  Role: {info.get('role', '')}")
        print(f"  S3 Total: {info.get('running_total_s3_docs', 0)} docs")

        for i, load in enumerate(info.get("loads", []), 1):
            lid = load.get("load_id", f"load_{i}")
            print(f"\n  Load #{i}: {lid}")
            print(f"    Timestamp:    {load.get('timestamp', '?')}")
            print(f"    Source:       {load.get('source', '?')}")
            if load.get("source_bucket"):
                print(f"    Bucket:       {load['source_bucket']}")
            print(f"    Source files:  {load.get('source_files_total', '?')}")
            print(f"    Blanks skip:  {load.get('blanks_skipped', '?')}")
            print(f"    Docs sent:    {load.get('docs_sent_to_pipeline', '?')}")
            sfn = load.get("sfn_executions", "?")
            ok = load.get("sfn_succeeded", "?")
            fail = load.get("sfn_failed", "?")
            print(f"    SFN:          {sfn} total, {ok} succeeded, {fail} failed")
            print(f"    S3 after:     {load.get('s3_docs_after', '?')}")
            if load.get("notes"):
                print(f"    Notes:        {load['notes']}")

        for p in info.get("pending_loads", []):
            print(f"\n  PENDING: {p.get('load_id', '?')}")
            print(f"    Source:       {p.get('source', '?')}")
            print(f"    Est. files:   {p.get('source_files_total', '?')}")
            print(f"    Est. blanks:  {p.get('estimated_blanks', '?')}")
            print(f"    Est. docs:    {p.get('estimated_docs', '?')}")


def record_load(case_id, load_data):
    """Append a load record to a case in the ledger."""
    ledger = load_ledger()
    cases = ledger.setdefault("cases", {})
    if case_id not in cases:
        cases[case_id] = {"name": load_data.get("case_name", "Unknown"), "loads": []}
    case = cases[case_id]
    case["loads"].append(load_data)
    # Update running total
    case["running_total_s3_docs"] = sum(
        l.get("s3_docs_after", l.get("docs_sent_to_pipeline", 0))
        for l in case["loads"]
    )
    # Remove from pending if matched
    pending = case.get("pending_loads", [])
    case["pending_loads"] = [
        p for p in pending if p.get("load_id") != load_data.get("load_id")
    ]
    save_ledger(ledger)


def main():
    parser = argparse.ArgumentParser(description="Ingestion Ledger")
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args()

    if args.detail:
        print_detail()
    else:
        print_summary()


if __name__ == "__main__":
    main()
