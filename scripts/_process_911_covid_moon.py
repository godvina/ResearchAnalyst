"""Process 9/11, COVID Lab Leak, and Moon Landing conspiracies.

Same pipeline as flat earth and VAERS:
1. Define key claims for each theory
2. Run baseline Proof Engine
3. Deep research each claim (both sides, objective)
4. Re-run with enriched evidence
5. Compare: Did research move the needle?

Three theories in one script to be efficient with Bedrock calls.
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


# ============================================================
# 9/11 CONSPIRACY CLAIMS
# ============================================================
NINE_ELEVEN_CLAIMS = [
    {"id": "911-001", "cat": "controlled_demolition", "claim": "World Trade Center Building 7 collapsed at free-fall speed into its own footprint without being hit by a plane, consistent with controlled demolition"},
    {"id": "911-002", "cat": "controlled_demolition", "claim": "The Twin Towers collapsed at near free-fall speed, which is impossible from fire alone without pre-placed explosives removing structural resistance"},
    {"id": "911-003", "cat": "controlled_demolition", "claim": "Molten steel was found in the WTC rubble weeks after collapse, at temperatures that jet fuel fires cannot achieve"},
    {"id": "911-004", "cat": "controlled_demolition", "claim": "Nano-thermite residue was found in WTC dust samples by independent researchers (Harrit et al. 2009 peer-reviewed paper)"},
    {"id": "911-005", "cat": "pentagon", "claim": "The hole in the Pentagon was too small for a Boeing 757, and no identifiable large aircraft debris was visible in initial photos"},
    {"id": "911-006", "cat": "pentagon", "claim": "The flight path of Flight 77 required an impossible 270-degree descending spiral turn by an inexperienced pilot"},
    {"id": "911-007", "cat": "flight93", "claim": "Flight 93 debris was scattered over 8 miles, inconsistent with a crash and consistent with being shot down"},
    {"id": "911-008", "cat": "foreknowledge", "claim": "Put options on American Airlines and United Airlines stock surged abnormally in the days before 9/11, suggesting insider trading based on foreknowledge"},
    {"id": "911-009", "cat": "foreknowledge", "claim": "Multiple intelligence agencies had specific advance warnings that were ignored or suppressed, suggesting deliberate stand-down"},
    {"id": "911-010", "cat": "cover_up", "claim": "The 9/11 Commission was underfunded, had conflicts of interest, and key witnesses were not called or testimony was classified"},
    {"id": "911-011", "cat": "cover_up", "claim": "WTC steel evidence was rapidly shipped to China for recycling before forensic investigation could be completed"},
    {"id": "911-012", "cat": "physics", "claim": "Firefighters and first responders reported hearing sequential explosions before and during the collapses"},
    {"id": "911-013", "cat": "motive", "claim": "The Project for a New American Century (PNAC) document called for a 'new Pearl Harbor' event one year before 9/11 to justify military expansion"},
    {"id": "911-014", "cat": "saudi_connection", "claim": "28 pages of the 9/11 Commission Report regarding Saudi government involvement were classified for 15 years"},
    {"id": "911-015", "cat": "physics", "claim": "The seismic recordings from 9/11 show large energy spikes before the towers collapsed, consistent with explosions at the base"},
]

# ============================================================
# COVID LAB LEAK CLAIMS
# ============================================================
COVID_LAB_LEAK_CLAIMS = [
    {"id": "covid-001", "cat": "origin", "claim": "SARS-CoV-2 originated from the Wuhan Institute of Virology (WIV) which was conducting gain-of-function research on bat coronaviruses"},
    {"id": "covid-002", "cat": "furin_cleavage", "claim": "The furin cleavage site in SARS-CoV-2 is unique among known sarbecoviruses and suggests engineered insertion rather than natural evolution"},
    {"id": "covid-003", "cat": "database", "claim": "The WIV took its virus database offline in September 2019 (months before the outbreak was acknowledged) and has refused to share the data"},
    {"id": "covid-004", "cat": "sick_researchers", "claim": "Three WIV researchers were hospitalized with COVID-like symptoms in November 2019, before the official outbreak timeline"},
    {"id": "covid-005", "cat": "gain_of_function", "claim": "NIH-funded EcoHealth Alliance grants to WIV specifically funded gain-of-function research on bat coronaviruses, despite denials"},
    {"id": "covid-006", "cat": "cover_up", "claim": "Scientists who publicly dismissed the lab leak theory in early 2020 (Lancet letter) privately expressed concerns about engineering markers"},
    {"id": "covid-007", "cat": "no_intermediate", "claim": "No intermediate animal host has been identified after 4+ years of searching, unlike SARS-1 (identified in months) and MERS"},
    {"id": "covid-008", "cat": "proximity", "claim": "The outbreak began within miles of the WIV BSL-4 lab, which was the world's leading center for bat coronavirus research"},
    {"id": "covid-009", "cat": "genetic_evidence", "claim": "The virus shows no evidence of serial passage in animals (adaptation mutations) expected from natural spillover"},
    {"id": "covid-010", "cat": "suppression", "claim": "Social media platforms censored lab leak discussion as 'misinformation' in 2020-2021, then reversed course when the theory gained mainstream credibility"},
    {"id": "covid-011", "cat": "defuse_proposal", "claim": "EcoHealth Alliance's DEFUSE proposal (2018) described inserting furin cleavage sites into bat coronaviruses — the exact feature found in SARS-CoV-2"},
    {"id": "covid-012", "cat": "investigation_blocked", "claim": "China blocked WHO investigators from accessing WIV records, raw data, and early patient samples"},
]

# ============================================================
# MOON LANDING CONSPIRACY CLAIMS
# ============================================================
MOON_LANDING_CLAIMS = [
    {"id": "moon-001", "cat": "photography", "claim": "Photos from the lunar surface show no stars in the sky, which should be visible without atmospheric interference"},
    {"id": "moon-002", "cat": "photography", "claim": "Shadows in lunar photos point in multiple directions, suggesting artificial studio lighting rather than a single sun source"},
    {"id": "moon-003", "cat": "photography", "claim": "The crosshairs on lunar photos appear behind objects in some images, suggesting compositing or post-processing"},
    {"id": "moon-004", "cat": "flag", "claim": "The American flag appears to wave in the vacuum of space where there is no atmosphere to create wind"},
    {"id": "moon-005", "cat": "radiation", "claim": "The Van Allen radiation belts would deliver lethal radiation doses to astronauts, making transit impossible with 1960s shielding technology"},
    {"id": "moon-006", "cat": "technology", "claim": "NASA claims to have lost the original Apollo telemetry tapes and the technology to return to the moon, which is suspicious for humanity's greatest achievement"},
    {"id": "moon-007", "cat": "footage", "claim": "The lunar module descent footage shows no blast crater or significant dust disturbance from the 10,000-pound-thrust engine"},
    {"id": "moon-008", "cat": "footage", "claim": "Slow-motion analysis of astronaut movements shows they match Earth gravity at half-speed, consistent with studio filming"},
    {"id": "moon-009", "cat": "whistleblower", "claim": "Multiple NASA employees and contractors have made deathbed or whistleblower statements suggesting the landings were faked"},
    {"id": "moon-010", "cat": "political_motive", "claim": "The US had overwhelming political motivation to fake the landings to win the Space Race, and the technology gap between 1969 and subsequent decades suggests it wasn't real"},
    {"id": "moon-011", "cat": "radiation", "claim": "The lunar surface temperatures (250°F in sun, -280°F in shade) would have killed astronauts and destroyed film, yet photos show no thermal distortion"},
    {"id": "moon-012", "cat": "kubrick", "claim": "Stanley Kubrick was contracted by NASA to film the moon landings, based on the advanced filmmaking technology shown in 2001: A Space Odyssey (1968)"},
]


def research_claim(claim, bedrock):
    """Deep research a claim — find evidence both sides, objective."""
    prompt = f"""You are an objective research analyst. Evaluate this claim FAIRLY.

CLAIM: "{claim['claim']}"

Research BOTH sides:
1. SUPPORTING EVIDENCE: Specific data, studies, documents, observations that support this
2. COUNTER EVIDENCE: Specific data, studies, investigations that refute this
3. KEY CONTEXT: What's the full picture? What are investigators on record saying?
4. EVIDENCE STRENGTH: How strong is the supporting evidence? (1-10)

Be OBJECTIVE. Acknowledge legitimate questions even in conspiracy theories.
Some conspiracy claims have turned out to be partially or fully correct (e.g., NSA mass surveillance).

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
    """Process a single conspiracy theory through the full pipeline."""
    print(f"\n{'='*70}")
    print(f"  PROCESSING: {theory_name} ({len(claims)} claims)")
    print(f"{'='*70}")

    # Baseline
    print(f"  Baseline evaluation ({standard} standard)...")
    baseline = []
    for i, claim in enumerate(claims):
        finding_data = {'description': claim['claim'], 'theory_name': theory_name}
        evidence = f"Claim: {claim['claim']}"
        verdict = engine.evaluate(claim['id'], finding_data, evidence, standard, 'conspiracy_theories')
        baseline.append({
            'claim_id': claim['id'], 'category': claim['cat'], 'claim': claim['claim'],
            'baseline_verdict': verdict.verdict, 'baseline_score': verdict.overall_score,
        })
        time.sleep(0.5)
    
    avg_base = sum(r['baseline_score'] for r in baseline) / len(baseline)
    proven_base = sum(1 for r in baseline if r['baseline_verdict'] == 'PROVEN')
    print(f"  Baseline: avg={avg_base:.3f}, proven={proven_base}/{len(claims)}")

    # Research
    print(f"  Deep research (both sides)...")
    research = {}
    for i, claim in enumerate(claims):
        r = research_claim(claim, bedrock)
        research[claim['id']] = r
        time.sleep(1.0)
    
    # Enriched evaluation
    print(f"  Re-evaluating with research evidence...")
    enriched = []
    for base in baseline:
        r = research.get(base['claim_id'], {})
        supporting = r.get('supporting_evidence', '')
        counter = r.get('counter_evidence', '')
        context = r.get('key_context', '')
        
        enriched_evidence = f"CLAIM: {base['claim']}\n\nSUPPORTING: {supporting}\nCOUNTER: {counter}\nCONTEXT: {context}"
        finding_data = {'description': base['claim'], 'theory_name': f"{theory_name} (Researched)"}
        verdict = engine.evaluate(f"{base['claim_id']}-e", finding_data, enriched_evidence, standard, 'conspiracy_theories')
        
        delta = verdict.overall_score - base['baseline_score']
        enriched.append({
            **base, 'enriched_verdict': verdict.verdict, 'enriched_score': verdict.overall_score,
            'delta': round(delta, 3), 'research_strength': r.get('evidence_strength', 0),
        })
        time.sleep(0.5)
    
    avg_enr = sum(r['enriched_score'] for r in enriched) / len(enriched)
    proven_enr = sum(1 for r in enriched if r['enriched_verdict'] == 'PROVEN')
    improved = sum(1 for r in enriched if r['delta'] > 0)
    
    print(f"  Enriched: avg={avg_enr:.3f}, proven={proven_enr}/{len(claims)}, improved={improved}")
    print(f"  Delta: {avg_enr - avg_base:+.3f}")
    
    # Top claims
    for r in sorted(enriched, key=lambda x: x['enriched_score'], reverse=True)[:5]:
        d = f"+{r['delta']:.2f}" if r['delta'] >= 0 else f"{r['delta']:.2f}"
        print(f"    {r['enriched_score']:.2f} ({d}) [{r['enriched_verdict']:12s}] {r['claim'][:60]}")
    
    return {
        'theory': theory_name,
        'standard': standard,
        'claims_count': len(claims),
        'baseline_avg': avg_base,
        'enriched_avg': avg_enr,
        'delta': avg_enr - avg_base,
        'proven_baseline': proven_base,
        'proven_enriched': proven_enr,
        'improved_count': improved,
        'results': enriched,
        'research': research,
    }


def main():
    import boto3
    
    print("=" * 70)
    print("PROCESSING 3 THEORIES: 9/11 + COVID LAB LEAK + MOON LANDING")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Pipeline: Claims → Baseline → Research → Re-evaluate")
    print()
    
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    engine = ProofEngine(bedrock_client=bedrock)
    print("Connected to Bedrock\n")
    
    theories = [
        ("9/11 Conspiracy Theories", NINE_ELEVEN_CLAIMS, "intelligence"),
        ("COVID-19 Lab Leak Theory", COVID_LAB_LEAK_CLAIMS, "intelligence"),
        ("Moon Landing Hoax", MOON_LANDING_CLAIMS, "scientific"),
    ]
    
    all_results = {}
    for theory_name, claims, standard in theories:
        result = process_theory(theory_name, claims, engine, bedrock, standard)
        all_results[theory_name] = result
    
    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY — ALL 3 THEORIES")
    print("=" * 70)
    for name, r in all_results.items():
        print(f"\n  {name}:")
        print(f"    Claims: {r['claims_count']} | Standard: {r['standard']}")
        print(f"    Baseline: {r['baseline_avg']:.3f} | Enriched: {r['enriched_avg']:.3f} | Delta: {r['delta']:+.3f}")
        print(f"    Proven (before→after): {r['proven_baseline']} → {r['proven_enriched']}")
        print(f"    Improved by research: {r['improved_count']}/{r['claims_count']}")
    
    # Save
    output = {
        'pipeline_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'theories': [t[0] for t in theories],
            'total_claims': sum(len(t[1]) for t in theories),
        },
        'results': {k: {**v, 'research': {kid: {kk: vv for kk, vv in rv.items() if kk != 'raw'} 
                        for kid, rv in v['research'].items()}} for k, v in all_results.items()},
    }
    
    out_path = OUTPUT_DIR / 'proof-engine-results-911-covid-moon.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
