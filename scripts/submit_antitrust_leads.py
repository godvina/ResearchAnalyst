"""Submit 5 real DOJ antitrust cases as pre-case leads and run the full pipeline.

This script:
1. Submits 5 real DOJ antitrust cases as pre-case leads via the API
2. Triggers AI classification for each lead
3. Triggers OSINT data gathering
4. Triggers prosecution readiness assessment
5. Prints a summary report with go/no-go recommendations

Uses the deployed Lambda directly (not HTTP) for reliability.
"""

import json
import time
import boto3
import sys

# --- Configuration ---
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"

lambda_client = boto3.client("lambda", region_name=REGION)


def invoke_api(method, path, body=None):
    """Invoke the Lambda as if it were an API Gateway request."""
    event = {
        "httpMethod": method,
        "path": path,
        "pathParameters": {},
        "queryStringParameters": {},
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body) if body else None,
    }
    response = lambda_client.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(event),
    )
    payload = json.loads(response["Payload"].read())
    status = payload.get("statusCode", 0)
    resp_body = payload.get("body", "{}")
    if isinstance(resp_body, str):
        try:
            resp_body = json.loads(resp_body)
        except json.JSONDecodeError:
            pass
    return status, resp_body


# --- 5 Real DOJ Antitrust Cases ---
ANTITRUST_CASES = [
    {
        "title": "Big Four Beef Packers Price-Fixing Investigation",
        "summary": (
            "DOJ and USDA investigation into Tyson Foods, JBS USA, Cargill, and "
            "National Beef Packing for alleged price-fixing and collusion in the US "
            "cattle and beef industries. Federal officials allege coordinated suppression "
            "of cattle prices paid to ranchers while inflating consumer beef prices. "
            "The four companies control approximately 85% of US beef processing capacity."
        ),
        "source_type": "referral",
        "source_content": {
            "subjects": ["Tyson Foods", "JBS USA", "Cargill", "National Beef Packing"],
            "industry": "beef_processing",
            "market_share": "85% of US beef processing",
            "alleged_conduct": "price-fixing, bid suppression at cattle auctions",
            "affected_parties": "US cattle ranchers, consumers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$10B+ over 5 years",
            "source_url": "https://www.justice.gov/atr",
            "referral_agency": "USDA",
        },
        "priority": "critical",
    },
    {
        "title": "LIBOR Rate Manipulation - Banking Cartel",
        "summary": (
            "Seven major banks manipulated the London Interbank Offered Rate (LIBOR) "
            "by submitting intentionally high or low rates to benefit trading positions. "
            "Banks paid over $3 billion in fines, multiple subsidiaries pled guilty, "
            "and 16 individuals were convicted. Affected trillions in financial instruments."
        ),
        "source_type": "referral",
        "source_content": {
            "subjects": [
                "Barclays", "Deutsche Bank", "UBS", "Rabobank",
                "Royal Bank of Scotland", "Citicorp", "JPMorgan Chase",
            ],
            "industry": "banking_financial_services",
            "alleged_conduct": "rate manipulation, fraud, wire fraud",
            "affected_instruments": "LIBOR-linked derivatives, mortgages, student loans",
            "geographic_scope": "global",
            "estimated_harm": "$300B+ in affected instruments",
            "fines_paid": "$3B+",
            "convictions": "16 individuals, 7 corporate guilty pleas",
            "source_url": "https://www.justice.gov/atr/new-york-office",
        },
        "priority": "critical",
    },
    {
        "title": "Real Estate Agent Commission Price-Fixing (NAR)",
        "summary": (
            "National Association of Realtors and major brokerages accused of conspiring "
            "to inflate real estate agent commissions at 5-6% through mandatory buyer-broker "
            "commission rules in MLS systems. Resulted in $1.8B settlement by NAR and "
            "major structural reforms to how commissions are set and disclosed."
        ),
        "source_type": "news",
        "source_content": {
            "subjects": [
                "National Association of Realtors", "Keller Williams",
                "RE/MAX", "Anywhere Real Estate", "HomeServices of America",
            ],
            "industry": "real_estate",
            "alleged_conduct": "price-fixing of broker commissions via MLS rules",
            "mechanism": "mandatory buyer-broker commission sharing in MLS",
            "affected_parties": "home sellers, home buyers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$30B+ annually in inflated commissions",
            "settlement_amount": "$1.8B (NAR) + $250M (others)",
            "source_url": "https://www.justice.gov/atr",
        },
        "priority": "high",
    },
    {
        "title": "Generic Pharmaceutical Price-Fixing Conspiracy",
        "summary": (
            "DOJ investigation into widespread price-fixing among generic drug manufacturers. "
            "Over 40 states filed suit alleging that 20+ generic drug companies conspired to "
            "fix prices, rig bids, and allocate markets for over 300 generic drugs. "
            "Teva Pharmaceuticals, Sandoz, Mylan, and others implicated. Multiple executives "
            "have pled guilty to criminal charges."
        ),
        "source_type": "referral",
        "source_content": {
            "subjects": [
                "Teva Pharmaceuticals", "Sandoz", "Mylan", "Heritage Pharmaceuticals",
                "Aurobindo Pharma", "Rising Pharmaceuticals",
            ],
            "industry": "pharmaceuticals",
            "alleged_conduct": "price-fixing, market allocation, bid rigging",
            "mechanism": "coordinated price increases via industry conferences and calls",
            "affected_parties": "patients, insurers, government health programs",
            "geographic_scope": "nationwide",
            "estimated_harm": "$5B+ in overcharges",
            "drugs_affected": "300+ generic medications",
            "source_url": "https://www.justice.gov/atr",
            "referral_agency": "HHS-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "South Korean Auto Parts Bid-Rigging Cartel",
        "summary": (
            "DOJ prosecution of executives from South Korean and Japanese auto parts "
            "manufacturers who rigged bids and fixed prices for components sold to "
            "US automakers including GM, Ford, Chrysler, Toyota, and Honda. "
            "Over $2.9 billion in fines collected from 50+ companies. "
            "48 individuals charged, with many serving prison sentences."
        ),
        "source_type": "referral",
        "source_content": {
            "subjects": [
                "Denso Corporation", "Yazaki Corporation", "Furukawa Electric",
                "Hyundai Mobis", "Mando Corporation", "SL Corporation",
            ],
            "industry": "automotive_parts",
            "alleged_conduct": "bid rigging, price fixing for auto parts",
            "mechanism": "pre-arranged bid winners at industry meetings",
            "affected_parties": "US automakers, car buyers",
            "geographic_scope": "US, Japan, South Korea",
            "estimated_harm": "$5B+ in overcharges to automakers",
            "fines_collected": "$2.9B from 50+ companies",
            "individuals_charged": 48,
            "source_url": "https://www.justice.gov/atr",
        },
        "priority": "high",
    },
]


def main():
    print("=" * 70)
    print("DOJ ANTITRUST PRE-CASE INTELLIGENCE — AUTOMATED TRAWL & ASSESS")
    print("=" * 70)
    print()

    results = []

    for i, case in enumerate(ANTITRUST_CASES, 1):
        print(f"\n{'─' * 70}")
        print(f"CASE {i}/5: {case['title']}")
        print(f"{'─' * 70}")

        # Step 1: Submit lead
        print(f"  [1/4] Submitting lead...")
        status, body = invoke_api("POST", "/pre-case/leads", case)
        if status != 200 and status != 201:
            print(f"  ❌ FAILED to submit lead: {status} — {body}")
            results.append({"title": case["title"], "error": f"submit failed: {status}"})
            continue

        lead_id = body.get("lead_id") or body.get("data", {}).get("lead_id")
        if not lead_id:
            print(f"  ❌ No lead_id in response: {body}")
            results.append({"title": case["title"], "error": "no lead_id"})
            continue
        print(f"  ✓ Lead created: {lead_id}")

        # Step 2: Classify
        print(f"  [2/4] Classifying case type...")
        status, body = invoke_api("POST", f"/pre-case/leads/{lead_id}/classify")
        if status == 200:
            classification = body.get("data", body)
            case_type = classification.get("case_type", "unknown")
            confidence = classification.get("confidence", 0)
            print(f"  ✓ Classified: {case_type} (confidence: {confidence}%)")
        else:
            case_type = "unknown"
            confidence = 0
            print(f"  ⚠ Classification returned {status}: {str(body)[:100]}")

        # Step 3: Gather OSINT
        print(f"  [3/4] Gathering OSINT data...")
        status, body = invoke_api("POST", f"/pre-case/leads/{lead_id}/gather")
        if status == 200:
            gather_data = body.get("data", body)
            sources_ok = gather_data.get("sources_succeeded", [])
            sources_fail = gather_data.get("sources_failed", [])
            records = gather_data.get("records_gathered", 0)
            print(f"  ✓ OSINT gathered: {records} records from {len(sources_ok)} sources")
            if sources_fail:
                print(f"    (failed sources: {', '.join(sources_fail)})")
        else:
            records = 0
            print(f"  ⚠ OSINT gathering returned {status}: {str(body)[:100]}")

        # Step 4: Assess prosecution readiness
        print(f"  [4/4] Assessing prosecution readiness...")
        status, body = invoke_api("POST", f"/pre-case/leads/{lead_id}/assess")
        if status == 200:
            assessment = body.get("data", body)
            score = assessment.get("score", 0)
            recommendation = assessment.get("recommendation", "unknown")
            print(f"  ✓ Assessment complete: Score={score}/100, Recommendation={recommendation}")
        else:
            score = 0
            recommendation = "error"
            print(f"  ⚠ Assessment returned {status}: {str(body)[:100]}")

        results.append({
            "title": case["title"],
            "lead_id": lead_id,
            "case_type": case_type,
            "confidence": confidence,
            "osint_records": records,
            "score": score,
            "recommendation": recommendation,
            "priority": case["priority"],
        })

        # Brief pause between cases to avoid throttling
        time.sleep(1)

    # --- Summary Report ---
    print(f"\n\n{'=' * 70}")
    print("PROSECUTION READINESS SUMMARY REPORT")
    print(f"{'=' * 70}\n")

    print(f"{'Case':<50} {'Type':<22} {'Score':<8} {'Recommendation':<20}")
    print(f"{'─' * 50} {'─' * 22} {'─' * 8} {'─' * 20}")

    for r in results:
        if "error" in r:
            print(f"{r['title'][:50]:<50} {'ERROR':<22} {'—':<8} {r['error']:<20}")
        else:
            emoji = "🟢" if r["recommendation"] == "open_investigation" else (
                "🟡" if r["recommendation"] == "need_more_evidence" else "🔴"
            )
            print(
                f"{r['title'][:50]:<50} "
                f"{r['case_type'][:22]:<22} "
                f"{r['score']:<8} "
                f"{emoji} {r['recommendation']:<20}"
            )

    # Go/No-Go summary
    open_cases = [r for r in results if r.get("recommendation") == "open_investigation"]
    need_more = [r for r in results if r.get("recommendation") == "need_more_evidence"]
    insufficient = [r for r in results if r.get("recommendation") == "insufficient_basis"]

    print(f"\n{'─' * 70}")
    print(f"GO (Open Investigation):     {len(open_cases)} cases")
    print(f"CONDITIONAL (Need Evidence): {len(need_more)} cases")
    print(f"NO-GO (Insufficient):        {len(insufficient)} cases")
    print(f"{'─' * 70}")

    if open_cases:
        print("\n🟢 RECOMMENDED FOR IMMEDIATE INVESTIGATION:")
        for r in open_cases:
            print(f"   • {r['title']} (Score: {r['score']}/100)")

    print("\nDone. All leads are now in the Pre-Case Intelligence dashboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
