"""Process Princess Diana and New World Order conspiracy theories.

Same pipeline: Claims → Baseline → Research → Re-evaluate
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.proof_engine import ProofEngine

OUTPUT_DIR = PROJECT_ROOT / 'src' / 'data'

DIANA_CLAIMS = [
    {"id": "diana-001", "cat": "driver", "claim": "Driver Henri Paul's blood alcohol level was manipulated post-mortem — witnesses say he appeared sober that evening"},
    {"id": "diana-002", "cat": "mi6", "claim": "MI6 had an operational plan to assassinate a foreign leader using a car crash in a tunnel, matching Diana's death exactly (Tomlinson affidavit)"},
    {"id": "diana-003", "cat": "white_fiat", "claim": "A white Fiat Uno made contact with the Mercedes and was never officially identified, despite extensive evidence of paint transfer"},
    {"id": "diana-004", "cat": "paparazzi", "claim": "The paparazzi motorcycle pursuit was deliberately orchestrated to force the car into the tunnel at high speed"},
    {"id": "diana-005", "cat": "cameras", "claim": "All CCTV cameras on the route to and inside the Pont de l'Alma tunnel were non-functional that night — unprecedented for Paris"},
    {"id": "diana-006", "cat": "ambulance", "claim": "The ambulance took over an hour to reach the hospital (normally 5 minutes away), and stopped en route for unexplained reasons"},
    {"id": "diana-007", "cat": "pregnancy", "claim": "Diana was pregnant with Dodi Fayed's child, which the Royal Family found unacceptable — providing motive for elimination"},
    {"id": "diana-008", "cat": "engagement", "claim": "Diana and Dodi were about to announce their engagement, which the establishment considered a threat to the monarchy"},
    {"id": "diana-009", "cat": "landmines", "claim": "Diana's anti-landmine campaign threatened powerful arms industry interests connected to the British establishment"},
    {"id": "diana-010", "cat": "foreknowledge", "claim": "Diana herself wrote a note 10 months before her death predicting she would be killed in a car accident arranged by her ex-husband"},
    {"id": "diana-011", "cat": "embalming", "claim": "Diana's body was embalmed unusually quickly in Paris (before repatriation), potentially destroying evidence of pregnancy"},
    {"id": "diana-012", "cat": "bodyguard", "claim": "Diana's regular security detail was withdrawn shortly before the trip to Paris, leaving her vulnerable"},
]

NWO_CLAIMS = [
    {"id": "nwo-001", "cat": "bilderberg", "claim": "The Bilderberg Group meets annually in secret with heads of state and corporate leaders, making policy decisions outside democratic accountability"},
    {"id": "nwo-002", "cat": "central_banking", "claim": "The Federal Reserve is a private institution owned by banking families, not a government agency, and profits from national debt creation"},
    {"id": "nwo-003", "cat": "world_government", "claim": "Organizations like the WEF, UN, WHO, and IMF are incrementally building a one-world government that supersedes national sovereignty"},
    {"id": "nwo-004", "cat": "great_reset", "claim": "The WEF's 'Great Reset' agenda explicitly calls for restructuring capitalism and society in ways not democratically approved"},
    {"id": "nwo-005", "cat": "surveillance", "claim": "Mass surveillance programs (Five Eyes, PRISM) monitor all global communications, as confirmed by Edward Snowden's revelations"},
    {"id": "nwo-006", "cat": "media_control", "claim": "Six corporations control 90% of US media, enabling coordinated narrative control across supposedly independent outlets"},
    {"id": "nwo-007", "cat": "freemasonry", "claim": "Freemasonry at the highest levels (33rd degree) involves occult practices and members hold disproportionate positions of power in government"},
    {"id": "nwo-008", "cat": "depopulation", "claim": "Multiple elites (Gates, Turner, Rockefeller) have publicly advocated for population reduction, and policies align with this agenda"},
    {"id": "nwo-009", "cat": "financial_control", "claim": "The same banking families (Rothschild, Rockefeller) have controlled both sides of every major war for 200+ years through financing"},
    {"id": "nwo-010", "cat": "bohemian_grove", "claim": "World leaders participate in occult rituals at Bohemian Grove, as documented by infiltrators with video evidence"},
    {"id": "nwo-011", "cat": "operation_mockingbird", "claim": "The CIA's Operation Mockingbird placed agents in major news organizations to control narratives — confirmed by Church Committee hearings"},
    {"id": "nwo-012", "cat": "agenda_2030", "claim": "UN Agenda 2030 and ESG frameworks are mechanisms to transfer sovereignty from nations to unelected global institutions"},
    {"id": "nwo-013", "cat": "mk_ultra", "claim": "The CIA conducted mind control experiments on unwitting citizens (MK-Ultra) — confirmed by declassified documents and congressional hearings"},
    {"id": "nwo-014", "cat": "false_flags", "claim": "Operation Northwoods (1962) proposed US government false flag attacks on American citizens to justify war — document declassified in 1997"},
    {"id": "nwo-015", "cat": "economic_crisis", "claim": "Major economic crashes (2008, etc.) are engineered by central banks to consolidate wealth and justify expanded government control"},
]


def research_claim(claim, bedrock):
    """Deep research a claim — both sides, objective."""
    prompt = f"""You are an objective research analyst. Evaluate this claim FAIRLY.

CLAIM: "{claim['claim']}"

Research BOTH sides:
1. SUPPORTING EVIDENCE: Specific data, documents, testimony, or confirmed facts that support this
2. COUNTER EVIDENCE: Specific investigations, evidence, or explanations that refute this
3. KEY CONTEXT: What has been officially investigated? What remains unresolved?
4. EVIDENCE STRENGTH: How strong is the supporting evidence? (1-10)

Be OBJECTIVE. Some conspiracy claims are based on confirmed facts (declassified docs, official admissions).
Distinguish between: confirmed facts, reasonable inferences, and speculation.

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
            contentType="application/json",
            accept="application/json"
        )
        result = json.loads(response['body'].read())
        content = result['content'][0]['text']
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {'raw': content[:600], 'evidence_strength': 0}
    except Exception as e:
        return {'error': str(e), 'evidence_strength': 0}


def process_theory(theory_name, claims, engine, bedrock, standard='intelligence'):
    """Full pipeline for one theory."""
    print(f"\n{'='*70}")
    print(f"  {theory_name} ({len(claims)} claims, {standard} standard)")
    print(f"{'='*70}")

    # Baseline
    print(f"  Baseline...")
    baseline = []
    for claim in claims:
        finding_data = {'description': claim['claim'], 'theory_name': theory_name}
        verdict = engine.evaluate(claim['id'], finding_data, f"Claim: {claim['claim']}", standard, 'conspiracy_theories')
        baseline.append({
            'claim_id': claim['id'], 'category': claim['cat'], 'claim': claim['claim'],
            'baseline_verdict': verdict.verdict, 'baseline_score': verdict.overall_score,
        })
        time.sleep(0.5)

    avg_base = sum(r['baseline_score'] for r in baseline) / len(baseline)
    print(f"  Baseline avg: {avg_base:.3f}")

    # Research
    print(f"  Researching...")
    research = {}
    for claim in claims:
        research[claim['id']] = research_claim(claim, bedrock)
        time.sleep(1.0)

    # Enriched
    print(f"  Re-evaluating...")
    enriched = []
    for base in baseline:
        r = research.get(base['claim_id'], {})
        evidence = f"CLAIM: {base['claim']}\nSUPPORTING: {r.get('supporting_evidence','')}\nCOUNTER: {r.get('counter_evidence','')}\nCONTEXT: {r.get('key_context','')}"
        finding_data = {'description': base['claim'], 'theory_name': f"{theory_name} (Researched)"}
        verdict = engine.evaluate(f"{base['claim_id']}-e", finding_data, evidence, standard, 'conspiracy_theories')
        delta = verdict.overall_score - base['baseline_score']
        enriched.append({**base, 'enriched_verdict': verdict.verdict, 'enriched_score': verdict.overall_score,
                        'delta': round(delta, 3), 'research_strength': r.get('evidence_strength', 0)})
        time.sleep(0.5)

    avg_enr = sum(r['enriched_score'] for r in enriched) / len(enriched)
    proven = sum(1 for r in enriched if r['enriched_verdict'] == 'PROVEN')
    improved = sum(1 for r in enriched if r['delta'] > 0)

    print(f"  Results: avg={avg_enr:.3f} (delta {avg_enr-avg_base:+.3f}), proven={proven}, improved={improved}")
    for r in sorted(enriched, key=lambda x: x['enriched_score'], reverse=True)[:5]:
        print(f"    {r['enriched_score']:.2f} [{r['enriched_verdict']:12s}] {r['claim'][:65]}")

    return {'theory': theory_name, 'standard': standard, 'baseline_avg': avg_base,
            'enriched_avg': avg_enr, 'delta': avg_enr - avg_base,
            'proven_enriched': proven, 'improved_count': improved,
            'results': enriched, 'research': research}


def main():
    import boto3

    print("=" * 70)
    print("PROCESSING: PRINCESS DIANA + NEW WORLD ORDER")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    engine = ProofEngine(bedrock_client=bedrock)
    print("Connected to Bedrock\n")

    results = {}
    results['Princess Diana'] = process_theory("Princess Diana Assassination", DIANA_CLAIMS, engine, bedrock, 'intelligence')
    results['New World Order'] = process_theory("New World Order / Illuminati", NWO_CLAIMS, engine, bedrock, 'intelligence')

    # Summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    for name, r in results.items():
        print(f"  {name}: baseline={r['baseline_avg']:.3f} → enriched={r['enriched_avg']:.3f} (delta {r['delta']:+.3f}), proven={r['proven_enriched']}")

    # Save
    out_path = OUTPUT_DIR / 'proof-engine-results-diana-nwo.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'timestamp': datetime.now(timezone.utc).isoformat(), 'results': results}, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
