#!/usr/bin/env python3
"""Ingest the ufos_uaps claims into the REAL pipeline (Aurora/OpenSearch/Neptune).

Uses the live ingest contract confirmed from src/lambdas/api/ingestion.py:
    POST /case-files            {topic_name, description, search_tier}
    POST /case-files/{id}/ingest {files:[{filename, content_base64}]}

Reads src/data/conspiracy-seed/ufos_uaps/processed_claims.json.

Usage:
    python scripts/_ingest_ufos_uaps.py --limit 25       # validation batch
    python scripts/_ingest_ufos_uaps.py                  # full ingest (all claims)
    python scripts/_ingest_ufos_uaps.py --case-id <id>   # reuse existing case
"""
import argparse
import base64
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CLAIMS = PROJECT_ROOT / "src" / "data" / "conspiracy-seed" / "ufos_uaps" / "processed_claims.json"
BATCH = 25


def _post(path, payload, timeout=60):
    req = urllib.request.Request(
        f"{API}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": (e.read().decode() if e.fp else "")[:300]}
    except Exception as e:
        return {"error": str(e)}


def create_case(topic=None, search_tier="enterprise"):
    # search_tier="enterprise" -> embeddings land in OpenSearch (hybrid search engine).
    # standard would route to Aurora pgvector only. Enterprise is the intended engine.
    return _post("/case-files", {
        "topic_name": topic or "UFO/UAP Sightings (NUFORC full signal set)",
        "description": ("All signature-firing UFO/UAP reports from the full NUFORC 60,632 corpus "
                        "(reports matching >=1 taxonomy signature). Scored against the UFO/UAP typology. "
                        "Feeds the ufos_uaps top-10 conspiracy slot."),
        "search_tier": search_tier,
    })


def claim_to_file(claim, idx):
    # Build a readable text doc from the claim so entity extraction has context
    loc = claim.get("location", {})
    text = (
        f"UFO/UAP SIGHTING REPORT\n"
        f"Shape: {claim.get('shape','')}\n"
        f"Location: {loc.get('city','')}, {loc.get('state','')} "
        f"({loc.get('lat','')}, {loc.get('lng','')})\n"
        f"Year: {claim.get('year','')}\n"
        f"Source: {claim.get('source','')}\n"
        f"Typology: {claim.get('typology','')}\n"
        f"Matched categories: {', '.join(claim.get('matched_categories', []))}\n"
        f"Priority score: {claim.get('priority_score','')}\n\n"
        f"Narrative: {claim.get('claim','')}\n"
    )
    return {
        "filename": f"{claim.get('id', f'uap-{idx:05d}')}.txt",
        "content_base64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Only ingest first N claims (validation)")
    ap.add_argument("--case-id", type=str, default=None, help="Reuse an existing case_id")
    ap.add_argument("--claims-file", type=str, default=None,
                    help="Path to a processed_claims-format JSON (default: ufos_uaps/processed_claims.json)")
    ap.add_argument("--search-tier", type=str, default="enterprise", choices=["standard", "enterprise"],
                    help="enterprise -> OpenSearch (default); standard -> Aurora pgvector")
    ap.add_argument("--topic", type=str, default=None, help="Case topic_name override")
    args = ap.parse_args()

    claims_path = Path(args.claims_file) if args.claims_file else DEFAULT_CLAIMS
    claims = json.loads(claims_path.read_text(encoding="utf-8"))["claims"]
    if args.limit:
        claims = claims[: args.limit]
    print(f"Claims to ingest: {len(claims)}")

    case_id = args.case_id
    if not case_id:
        print(f"Creating case (search_tier={args.search_tier})...")
        resp = create_case(topic=args.topic, search_tier=args.search_tier)
        case_id = resp.get("case_id") or resp.get("case_file", {}).get("case_id")
        if not case_id:
            print(f"  FAILED to create case: {resp}")
            return
        print(f"  case_id = {case_id}")

    files = [claim_to_file(c, i) for i, c in enumerate(claims)]

    ok = err = 0
    last_exec = None
    for i in range(0, len(files), BATCH):
        batch = files[i:i + BATCH]
        r = _post(f"/case-files/{case_id}/ingest", {"files": batch})
        if "error" in r:
            err += 1
            print(f"  batch {i//BATCH+1}: ERROR {r}")
            if err >= 3:
                print("  too many errors, stopping.")
                break
        else:
            ok += 1
            last_exec = r.get("execution_arn")
            print(f"  batch {i//BATCH+1}: OK ({i+len(batch)}/{len(files)}) exec={last_exec}")
        time.sleep(1.0)

    print(f"\nDONE. case_id={case_id} batches_ok={ok} batches_err={err}")
    print(f"Last execution ARN: {last_exec}")
    print(f"Verify with: aws stepfunctions describe-execution --execution-arn {last_exec}")


if __name__ == "__main__":
    main()
