"""VAERS Full Pipeline — Same approach as Flat Earth 200 Proofs.

1. Extract key claims/patterns from VAERS data (2021 COVID year)
2. Run baseline Proof Engine (intelligence standard)
3. Deep research each claim (find supporting + opposing evidence)
4. Re-run Proof Engine with enriched evidence
5. Compare: Did research move the needle?

VAERS data: 2.6 GB total, 114 files, 1990-2023
Focus: 2021 (COVID vaccines, biggest year - 632 MB)

CROSS-DOMAIN SCORING: Mandatory per steering doc.
Standard: intelligence (not scientific — this is about reporting patterns, not causation)
"""
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.proof_engine import ProofEngine

OUTPUT_DIR = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'vaers'
VAERS_DATA = OUTPUT_DIR / '2021VAERSDATA.csv'


def analyze_vaers_data():
    """Analyze the 2021 VAERS data and extract key statistical patterns."""
    print("  Loading 2021 VAERS data (COVID year)...")
    
    total = 0
    deaths = 0
    hospitalizations = 0
    er_visits = 0
    disabled = 0
    life_threat = 0
    onset_days = []
    age_groups = Counter()
    symptoms_common = Counter()
    
    with open(VAERS_DATA, 'r', encoding='latin-1', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if row.get('DIED') == 'Y': deaths += 1
            if row.get('HOSPITAL') == 'Y': hospitalizations += 1
            if row.get('ER_VISIT') == 'Y' or row.get('ER_ED_VISIT') == 'Y': er_visits += 1
            if row.get('DISABLE') == 'Y': disabled += 1
            if row.get('L_THREAT') == 'Y': life_threat += 1
            
            # Onset timing
            try:
                numdays = row.get('NUMDAYS', '')
                if numdays and numdays.strip():
                    days = int(float(numdays))
                    if 0 <= days <= 365:
                        onset_days.append(days)
            except (ValueError, TypeError):
                pass
            
            # Age groups
            try:
                age = float(row.get('AGE_YRS', 0) or 0)
                if age < 18: age_groups['<18'] += 1
                elif age < 40: age_groups['18-39'] += 1
                elif age < 60: age_groups['40-59'] += 1
                elif age < 80: age_groups['60-79'] += 1
                else: age_groups['80+'] += 1
            except (ValueError, TypeError):
                pass
            
            # Common symptom keywords
            sym = (row.get('SYMPTOM_TEXT', '') or '').lower()
            for kw in ['myocarditis', 'pericarditis', 'stroke', 'clot', 'thrombosis',
                       'anaphylaxis', 'bell', 'palsy', 'guillain', 'seizure', 'death',
                       'cardiac', 'heart attack', 'pulmonary embolism']:
                if kw in sym:
                    symptoms_common[kw] += 1
    
    # Onset timing analysis
    onset_0_1 = sum(1 for d in onset_days if d <= 1)
    onset_2_7 = sum(1 for d in onset_days if 2 <= d <= 7)
    onset_8_30 = sum(1 for d in onset_days if 8 <= d <= 30)
    onset_31_plus = sum(1 for d in onset_days if d > 30)
    
    stats = {
        'total_reports': total,
        'deaths': deaths,
        'hospitalizations': hospitalizations,
        'er_visits': er_visits,
        'disabled': disabled,
        'life_threatening': life_threat,
        'onset_timing': {
            '0-1 days': onset_0_1,
            '2-7 days': onset_2_7,
            '8-30 days': onset_8_30,
            '31+ days': onset_31_plus,
        },
        'age_distribution': dict(age_groups.most_common()),
        'serious_symptoms': dict(symptoms_common.most_common(15)),
        'death_rate_per_report': round(deaths / total * 100, 3) if total else 0,
    }
    
    print(f"  Total 2021 reports: {total:,}")
    print(f"  Deaths: {deaths:,} ({stats['death_rate_per_report']}%)")
    print(f"  Hospitalizations: {hospitalizations:,}")
    print(f"  Life-threatening: {life_threat:,}")
    print(f"  Top symptoms: {list(symptoms_common.most_common(5))}")
    
    return stats


def generate_vaers_claims(stats):
    """Generate testable claims from VAERS data patterns.
    
    These are the claims conspiracy theorists make about vaccines
    based on VAERS data. We evaluate them OBJECTIVELY.
    """
    claims = [
        {
            'claim_id': 'vaers-001',
            'category': 'reporting_volume',
            'claim': f'COVID vaccines generated {stats["total_reports"]:,} adverse event reports in 2021 alone — more than all other vaccines combined in the prior 30 years of VAERS',
            'data_point': stats['total_reports'],
        },
        {
            'claim_id': 'vaers-002',
            'category': 'mortality',
            'claim': f'VAERS recorded {stats["deaths"]:,} deaths following COVID vaccination in 2021, an unprecedented number for any vaccine in the system history',
            'data_point': stats['deaths'],
        },
        {
            'claim_id': 'vaers-003',
            'category': 'temporal_clustering',
            'claim': f'{stats["onset_timing"]["0-1 days"]:,} adverse events occurred within 0-1 days of vaccination, suggesting a causal temporal relationship',
            'data_point': stats['onset_timing']['0-1 days'],
        },
        {
            'claim_id': 'vaers-004',
            'category': 'myocarditis',
            'claim': f'VAERS recorded {stats["serious_symptoms"].get("myocarditis", 0):,} reports of myocarditis and {stats["serious_symptoms"].get("pericarditis", 0):,} pericarditis cases — conditions rare in the general population but clustered post-vaccination',
            'data_point': stats['serious_symptoms'].get('myocarditis', 0),
        },
        {
            'claim_id': 'vaers-005',
            'category': 'thrombosis',
            'claim': f'VAERS recorded {stats["serious_symptoms"].get("thrombosis", 0) + stats["serious_symptoms"].get("clot", 0):,} reports involving blood clots or thrombosis following COVID vaccination',
            'data_point': stats['serious_symptoms'].get('thrombosis', 0),
        },
        {
            'claim_id': 'vaers-006',
            'category': 'underreporting',
            'claim': 'VAERS captures only 1-10% of actual adverse events (per Harvard Pilgrim study), meaning the true number of adverse events could be 10-100x higher than reported',
            'data_point': None,
        },
        {
            'claim_id': 'vaers-007',
            'category': 'neurological',
            'claim': f'VAERS recorded {stats["serious_symptoms"].get("guillain", 0) + stats["serious_symptoms"].get("bell", 0) + stats["serious_symptoms"].get("palsy", 0):,} reports of neurological events (Guillain-Barré, Bell\'s palsy) following vaccination',
            'data_point': stats['serious_symptoms'].get('guillain', 0),
        },
        {
            'claim_id': 'vaers-008',
            'category': 'cardiac',
            'claim': f'VAERS recorded {stats["serious_symptoms"].get("cardiac", 0) + stats["serious_symptoms"].get("heart attack", 0):,} cardiac events including heart attacks following COVID vaccination',
            'data_point': stats['serious_symptoms'].get('cardiac', 0),
        },
        {
            'claim_id': 'vaers-009',
            'category': 'suppression',
            'claim': 'Healthcare workers report institutional pressure not to file VAERS reports, and reports have been deleted or altered after submission',
            'data_point': None,
        },
        {
            'claim_id': 'vaers-010',
            'category': 'risk_benefit',
            'claim': f'For young healthy adults (18-39), the {stats["age_distribution"].get("18-39", 0):,} adverse events reported may represent a risk that exceeds the COVID risk for that age group',
            'data_point': stats['age_distribution'].get('18-39', 0),
        },
        {
            'claim_id': 'vaers-011',
            'category': 'regulatory_failure',
            'claim': 'The CDC/FDA safety signal detection system failed to act on signals visible in VAERS data that independent researchers identified months earlier',
            'data_point': None,
        },
        {
            'claim_id': 'vaers-012',
            'category': 'informed_consent',
            'claim': 'The true rate of serious adverse events was not disclosed to vaccine recipients, violating informed consent principles',
            'data_point': None,
        },
    ]
    return claims


def research_vaers_claim(claim, bedrock):
    """Deep research a VAERS claim — find evidence both sides."""
    prompt = f"""You are an objective research analyst evaluating a claim about vaccine adverse events.

CLAIM: "{claim['claim']}"

Research this OBJECTIVELY. Present:
1. SUPPORTING EVIDENCE: What data, studies, or observations support this claim?
2. COUNTER EVIDENCE: What data, studies, or context argues against this interpretation?
3. KEY CONTEXT: What's the baseline rate? What does correlation vs causation analysis show?
4. DEFINITIVE TEST: What analysis would settle this claim?

Be FAIR — VAERS data IS real government data. Acknowledge what it shows while also noting its limitations.

Respond in JSON:
{{
  "supporting_evidence": "specific data/studies supporting the claim",
  "counter_evidence": "specific data/studies/context arguing against",
  "key_context": "baseline rates, correlation vs causation factors",
  "definitive_test": "what would prove or disprove this",
  "evidence_strength": <1-10>
}}"""
    
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
            return {'raw': content[:500], 'evidence_strength': 0}
    except Exception as e:
        return {'error': str(e), 'evidence_strength': 0}


def main():
    import boto3
    
    print("=" * 70)
    print("VAERS FULL PIPELINE — ANALYZE → CLAIMS → RESEARCH → PROOF ENGINE")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Standard: intelligence (threshold 0.65)")
    print(f"Data: 2021 VAERS (COVID vaccines)")
    print()
    
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    engine = ProofEngine(bedrock_client=bedrock)
    print("Connected to Bedrock\n")
    
    # STEP 1: Analyze VAERS data
    print("STEP 1: Analyzing 2021 VAERS data...")
    stats = analyze_vaers_data()
    print()
    
    # STEP 2: Generate claims
    print("STEP 2: Generating testable claims from data patterns...")
    claims = generate_vaers_claims(stats)
    print(f"  Generated {len(claims)} claims\n")
    
    # STEP 3: Baseline Proof Engine
    print("STEP 3: Running baseline Proof Engine (intelligence standard)...")
    baseline_results = []
    for i, claim in enumerate(claims):
        finding_data = {'description': claim['claim'], 'theory_name': 'VAERS Adverse Events'}
        evidence = f"VAERS 2021 data shows: {claim['claim']}\nData point: {claim.get('data_point', 'N/A')}"
        
        verdict = engine.evaluate(
            finding_id=claim['claim_id'],
            finding_data=finding_data,
            evidence=evidence,
            standard_name='intelligence',
            tenant_id='conspiracy_theories'
        )
        baseline_results.append({
            'claim_id': claim['claim_id'],
            'category': claim['category'],
            'claim': claim['claim'],
            'baseline_verdict': verdict.verdict,
            'baseline_score': verdict.overall_score,
        })
        print(f"  [{i+1:2d}/{len(claims)}] {verdict.verdict} ({verdict.overall_score:.2f}) - {claim['category']}")
        time.sleep(0.8)
    
    avg_baseline = sum(r['baseline_score'] for r in baseline_results) / len(baseline_results)
    print(f"\n  Baseline avg: {avg_baseline:.3f}\n")
    
    # STEP 4: Deep research
    print("STEP 4: Deep research on each claim...")
    research_data = {}
    for i, claim in enumerate(claims):
        research = research_vaers_claim(claim, bedrock)
        research_data[claim['claim_id']] = research
        strength = research.get('evidence_strength', 0)
        print(f"  [{i+1:2d}/{len(claims)}] Strength: {strength}/10 - {claim['category']}")
        time.sleep(1.0)
    
    # STEP 5: Re-run with enriched evidence
    print("\nSTEP 5: Re-running Proof Engine with research evidence...")
    enriched_results = []
    for i, base in enumerate(baseline_results):
        research = research_data.get(base['claim_id'], {})
        supporting = research.get('supporting_evidence', '')
        counter = research.get('counter_evidence', '')
        context = research.get('key_context', '')
        
        enriched_evidence = f"""CLAIM: {base['claim']}

SUPPORTING EVIDENCE: {supporting}
COUNTER EVIDENCE: {counter}
KEY CONTEXT: {context}

VAERS 2021 statistics: {json.dumps(stats, indent=2)[:500]}"""
        
        finding_data = {'description': base['claim'], 'theory_name': 'VAERS (Researched)'}
        verdict = engine.evaluate(
            finding_id=f"{base['claim_id']}-enriched",
            finding_data=finding_data,
            evidence=enriched_evidence,
            standard_name='intelligence',
            tenant_id='conspiracy_theories'
        )
        
        delta = verdict.overall_score - base['baseline_score']
        enriched_results.append({
            **base,
            'enriched_verdict': verdict.verdict,
            'enriched_score': verdict.overall_score,
            'delta': round(delta, 3),
            'research_strength': research.get('evidence_strength', 0),
        })
        time.sleep(0.8)
    
    avg_enriched = sum(r['enriched_score'] for r in enriched_results) / len(enriched_results)
    
    # RESULTS
    print("\n" + "=" * 70)
    print("RESULTS: VAERS CLAIMS — DID RESEARCH MOVE THE NEEDLE?")
    print("=" * 70)
    print(f"\n  BASELINE avg: {avg_baseline:.3f}")
    print(f"  ENRICHED avg: {avg_enriched:.3f}")
    print(f"  DELTA: {avg_enriched - avg_baseline:+.3f}")
    
    improved = [r for r in enriched_results if r['delta'] > 0]
    print(f"\n  Improved: {len(improved)}/{len(enriched_results)}")
    
    print(f"\n  PER-CLAIM RESULTS:")
    for r in sorted(enriched_results, key=lambda x: x['enriched_score'], reverse=True):
        d = f"+{r['delta']:.2f}" if r['delta'] > 0 else f"{r['delta']:.2f}"
        print(f"    {r['baseline_score']:.2f} → {r['enriched_score']:.2f} ({d}) [{r['enriched_verdict']:12s}] {r['category']}")
    
    # Save
    output = {
        'pipeline_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'standard': 'intelligence',
            'data_source': '2021VAERSDATA.csv (632 MB, COVID vaccines)',
            'total_reports_analyzed': stats['total_reports'],
        },
        'vaers_statistics': stats,
        'claims': claims,
        'research': research_data,
        'results': enriched_results,
        'summary': {
            'baseline_avg': avg_baseline,
            'enriched_avg': avg_enriched,
            'delta': avg_enriched - avg_baseline,
            'improved': len(improved),
        },
    }
    
    out_path = PROJECT_ROOT / 'src' / 'data' / 'proof-engine-results-vaers-full.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
