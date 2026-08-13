"""Process RFK Jr's "The Real Anthony Fauci" claims.

RFK Jr (now HHS Secretary) published this book with 2,200+ endnotes.
We extract the key testable claims and research them the same way:
- Baseline Proof Engine score
- Deep research (supporting + counter evidence)
- Re-evaluate with research
- Compare: which claims hold up under scrutiny?

This is particularly relevant because:
1. RFK is now in a position of institutional authority (HHS Secretary)
2. The book is densely sourced with citations
3. Many claims have been fact-checked both favorably and unfavorably
4. This tests our engine on claims from someone WITH authority, not against it

Standard: intelligence (institutional patterns, source verification)
"""
import json, sys, time, boto3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.services.proof_engine import ProofEngine

# Key claims from "The Real Anthony Fauci" organized by chapter/theme
RFK_CLAIMS = [
    # === REGULATORY CAPTURE ===
    {"id": "rfk-001", "cat": "regulatory_capture", "claim": "The FDA receives ~45% of its budget from pharmaceutical industry user fees (PDUFA), creating structural conflict of interest in drug/vaccine approval"},
    {"id": "rfk-002", "cat": "regulatory_capture", "claim": "NIAID under Fauci controls $6.1 billion in annual research funding, giving him power to destroy careers of scientists who dissent from his positions"},
    {"id": "rfk-003", "cat": "regulatory_capture", "claim": "Former FDA commissioners and senior staff routinely take positions at pharmaceutical companies they previously regulated (revolving door)"},
    {"id": "rfk-004", "cat": "regulatory_capture", "claim": "NIH scientists including Fauci receive personal royalty payments from drugs they help develop using taxpayer-funded research"},
    # === COVID RESPONSE ===
    {"id": "rfk-005", "cat": "covid_response", "claim": "Hydroxychloroquine and ivermectin were suppressed as early COVID treatments despite evidence of efficacy, because EUA for vaccines required no available treatment"},
    {"id": "rfk-006", "cat": "covid_response", "claim": "The Lancet and NEJM published fraudulent studies (Surgisphere) discrediting HCQ that were later retracted, but only after they influenced policy"},
    {"id": "rfk-007", "cat": "covid_response", "claim": "PCR tests were run at cycle thresholds (Ct>35) that produced up to 90% false positives, artificially inflating case counts"},
    {"id": "rfk-008", "cat": "covid_response", "claim": "Lockdowns caused more deaths (suicide, untreated disease, economic devastation) than they prevented, particularly in developing nations"},
    # === GAIN OF FUNCTION ===
    {"id": "rfk-009", "cat": "gain_of_function", "claim": "Fauci's NIAID funded gain-of-function research on bat coronaviruses at the Wuhan Institute of Virology through EcoHealth Alliance grants"},
    {"id": "rfk-010", "cat": "gain_of_function", "claim": "Fauci denied funding gain-of-function research to Congress (Rand Paul exchange) despite NIH later admitting EcoHealth violated terms"},
    {"id": "rfk-011", "cat": "gain_of_function", "claim": "The 2014 US moratorium on gain-of-function research was circumvented by routing funding through EcoHealth Alliance to foreign labs"},
    # === VACCINE SAFETY ===
    {"id": "rfk-012", "cat": "vaccine_safety", "claim": "No vaccine on the childhood schedule was tested against a true inert placebo in pre-licensure trials — they use other vaccines or adjuvants as 'placebos'"},
    {"id": "rfk-013", "cat": "vaccine_safety", "claim": "The 1986 National Childhood Vaccine Injury Act removed liability from vaccine manufacturers, eliminating their financial incentive for safety"},
    {"id": "rfk-014", "cat": "vaccine_safety", "claim": "VAERS captures only 1-10% of actual vaccine adverse events per the Harvard Pilgrim Healthcare study funded by HHS"},
    {"id": "rfk-015", "cat": "vaccine_safety", "claim": "The CDC's vaccine safety monitoring (VSD) database is not accessible to independent researchers, preventing external verification"},
    # === HIV/AIDS ERA ===
    {"id": "rfk-016", "cat": "hiv_aids", "claim": "AZT (the first AIDS drug Fauci championed) was a failed cancer chemotherapy agent known to be toxic, and its approval was based on a flawed trial"},
    {"id": "rfk-017", "cat": "hiv_aids", "claim": "Fauci suppressed cheaper, less toxic treatment alternatives for AIDS in favor of patented pharmaceuticals"},
    {"id": "rfk-018", "cat": "hiv_aids", "claim": "NIAID conducted unethical drug trials on foster children in New York (Incarnation Children's Center) without proper consent"},
    # === GATES PARTNERSHIP ===
    {"id": "rfk-019", "cat": "gates_pharma", "claim": "In 2000, Gates and Fauci formed a partnership to control global vaccine policy, eventually coordinating $60+ billion in vaccine funding"},
    {"id": "rfk-020", "cat": "gates_pharma", "claim": "The Gates Foundation's funding of WHO, Gavi, and CEPI gives it disproportionate influence over global health policy without democratic accountability"},
    # === CENSORSHIP ===
    {"id": "rfk-021", "cat": "censorship", "claim": "Social media companies coordinated with government health officials to censor vaccine safety concerns and lab leak discussion"},
    {"id": "rfk-022", "cat": "censorship", "claim": "Scientists who published data contradicting official COVID narratives faced career destruction, journal retractions, and public vilification"},
    {"id": "rfk-023", "cat": "censorship", "claim": "The Trusted News Initiative (TNI) was a coordinated media agreement to suppress coverage of vaccine adverse events"},
    # === EVENT 201 / PREPAREDNESS ===
    {"id": "rfk-024", "cat": "preparedness", "claim": "Event 201 (Oct 2019) simulated a coronavirus pandemic weeks before COVID emerged, involving the same institutions that later led the response"},
    {"id": "rfk-025", "cat": "preparedness", "claim": "Multiple pandemic simulation exercises (Crimson Contagion, SPARS, Dark Winter) rehearsed the exact social control measures later deployed for COVID"},
]


def research_claim(claim, bedrock):
    """Deep research — both sides, objective. Note: RFK cites 2,200 sources."""
    prompt = f"""You are an objective research analyst. RFK Jr (current HHS Secretary) made this claim in his book "The Real Anthony Fauci" (2021, 2,200+ endnotes).

CLAIM: "{claim['claim']}"

Research this OBJECTIVELY:
1. SUPPORTING EVIDENCE: What documentation, studies, government records, or confirmed facts support this claim? RFK cites specific sources — what do they show?
2. COUNTER EVIDENCE: What fact-checks, official responses, or contradicting evidence exists?
3. KEY CONTEXT: What's confirmed vs speculative? Has anything changed since publication (2021)?
4. EVIDENCE STRENGTH: How well-sourced is this specific claim? (1-10)

Note: Some of RFK's claims have been subsequently confirmed (e.g., NIH admitted EcoHealth violations, FOIA confirmed royalty payments, Surgisphere papers were retracted). Be fair to both sides.

Respond in JSON:
{{"supporting_evidence": "...", "counter_evidence": "...", "key_context": "...", "evidence_strength": <1-10>}}"""

    try:
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}]
            }),
            contentType="application/json", accept="application/json"
        )
        result = json.loads(response['body'].read())
        content = result['content'][0]['text']
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {'raw': content[:600], 'evidence_strength': 0}
    except Exception as e:
        return {'error': str(e), 'evidence_strength': 0}


def main():
    print("=" * 70)
    print("RFK Jr 'THE REAL ANTHONY FAUCI' — CLAIMS PIPELINE")
    print("=" * 70)
    print(f"Claims: {len(RFK_CLAIMS)} | Standard: intelligence")
    print(f"Source: Book with 2,200+ endnotes by current HHS Secretary")
    print()

    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    engine = ProofEngine(bedrock_client=bedrock)
    print("Connected to Bedrock\n")

    # Baseline
    print("Baseline evaluation...")
    baseline = []
    for claim in RFK_CLAIMS:
        finding_data = {'description': claim['claim'], 'theory_name': 'RFK - Real Anthony Fauci'}
        verdict = engine.evaluate(claim['id'], finding_data, f"Claim: {claim['claim']}", 'intelligence', 'conspiracy_theories')
        baseline.append({**claim, 'baseline_verdict': verdict.verdict, 'baseline_score': verdict.overall_score})
        time.sleep(0.5)

    avg_base = sum(r['baseline_score'] for r in baseline) / len(baseline)
    print(f"  Baseline avg: {avg_base:.3f}\n")

    # Research
    print("Deep research (both sides, checking RFK's sources)...")
    research = {}
    for i, claim in enumerate(RFK_CLAIMS):
        research[claim['id']] = research_claim(claim, bedrock)
        if (i+1) % 5 == 0:
            print(f"  {i+1}/{len(RFK_CLAIMS)} researched")
        time.sleep(1.0)

    # Enriched
    print("\nRe-evaluating with research...")
    enriched = []
    for base in baseline:
        r = research.get(base['id'], {})
        evidence = f"CLAIM: {base['claim']}\nSUPPORTING: {r.get('supporting_evidence','')}\nCOUNTER: {r.get('counter_evidence','')}\nCONTEXT: {r.get('key_context','')}"
        finding_data = {'description': base['claim'], 'theory_name': 'RFK Fauci (Researched)'}
        verdict = engine.evaluate(f"{base['id']}-e", finding_data, evidence, 'intelligence', 'conspiracy_theories')
        delta = verdict.overall_score - base['baseline_score']
        enriched.append({**base, 'enriched_verdict': verdict.verdict, 'enriched_score': verdict.overall_score,
                        'delta': round(delta, 3), 'research_strength': r.get('evidence_strength', 0)})
        time.sleep(0.5)

    # Results
    avg_enr = sum(r['enriched_score'] for r in enriched) / len(enriched)
    proven = sum(1 for r in enriched if r['enriched_verdict'] == 'PROVEN')
    improved = sum(1 for r in enriched if r['delta'] > 0)

    print(f"\n{'='*70}")
    print("RESULTS: RFK's Claims — Did Research Confirm Them?")
    print(f"{'='*70}")
    print(f"  Baseline: {avg_base:.3f} → Enriched: {avg_enr:.3f} (delta {avg_enr-avg_base:+.3f})")
    print(f"  Proven: {proven}/{len(enriched)} | Improved: {improved}/{len(enriched)}")
    print(f"\n  BY CATEGORY:")
    cats = {}
    for r in enriched:
        cat = r['cat']
        if cat not in cats: cats[cat] = []
        cats[cat].append(r)
    for cat, items in sorted(cats.items(), key=lambda x: -sum(i['enriched_score'] for i in x[1])/len(x[1])):
        avg = sum(i['enriched_score'] for i in items) / len(items)
        p = sum(1 for i in items if i['enriched_verdict'] == 'PROVEN')
        print(f"    {cat:20s}: avg {avg:.2f}, proven {p}/{len(items)}")

    print(f"\n  TOP CLAIMS (highest after research):")
    for r in sorted(enriched, key=lambda x: x['enriched_score'], reverse=True)[:10]:
        print(f"    {r['enriched_score']:.2f} [{r['enriched_verdict']:12s}] {r['claim'][:70]}")

    # Save
    output = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'RFK Jr "The Real Anthony Fauci" (2021, 2200+ endnotes)',
        'standard': 'intelligence', 'claims': len(RFK_CLAIMS),
        'summary': {'baseline': avg_base, 'enriched': avg_enr, 'proven': proven, 'improved': improved},
        'results': enriched, 'research': research,
    }
    out_path = PROJECT_ROOT / 'src' / 'data' / 'proof-engine-results-rfk-fauci.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
