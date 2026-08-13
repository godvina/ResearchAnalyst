"""Process COVID Lab Leak source documents through the pipeline.

Sources:
1. DEFUSE Proposal (EcoHealth Alliance, 2018) - 5.2 MB
2. House Intelligence Committee COVID Origins Report (Dec 2022) - 313 KB

These are the KEY documents in the lab leak debate.
Standard: intelligence
"""
import json, sys, time, boto3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.services.conspiracy_ingestion_adapters import AdapterRegistry
from src.services.proof_engine import ProofEngine


def main():
    print("=" * 70)
    print("COVID LAB LEAK — PROCESSING SOURCE DOCUMENTS")
    print("=" * 70)

    registry = AdapterRegistry()
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    engine = ProofEngine(bedrock_client=bedrock)
    s3 = boto3.client('s3')
    bucket = 'research-analyst-data-lake-974220725866'

    # Extract documents
    docs = {}
    for fname, label in [('defuse_proposal_2018.pdf', 'DEFUSE'), ('house_intel_covid_origins.pdf', 'House Intel')]:
        path = f'src/data/conspiracy-seed/covid_lab_leak/{fname}'
        recs = registry.ingest_file(path, 'covid_lab_leak')
        if recs:
            docs[label] = recs[0]
            print(f"  {label}: {len(recs[0].content_text)} chars extracted")
            # Upload to S3
            try:
                s3.put_object(Bucket=bucket, Key=recs[0].s3_key, Body=recs[0].to_json().encode('utf-8'), ContentType='application/json')
                print(f"    Uploaded: s3://{bucket}/{recs[0].s3_key}")
            except Exception as e:
                print(f"    S3 upload: {e}")

    # Build combined evidence
    combined_evidence = "\n\n".join([f"[{k}]: {v.content_text[:3000]}" for k, v in docs.items()])

    # COVID claims to evaluate against real documents
    claims = [
        {"id": "covid-d01", "claim": "The DEFUSE proposal explicitly described inserting furin cleavage sites into bat coronaviruses — the exact feature unique to SARS-CoV-2"},
        {"id": "covid-d02", "claim": "EcoHealth Alliance proposed conducting this research at the Wuhan Institute of Virology under BSL-3 conditions (not BSL-4)"},
        {"id": "covid-d03", "claim": "DARPA rejected the DEFUSE proposal citing gain-of-function concerns, but portions of the work may have proceeded with other funding"},
        {"id": "covid-d04", "claim": "The US Intelligence Community assessed the lab leak and natural spillover hypotheses and could not reach consensus"},
        {"id": "covid-d05", "claim": "The furin cleavage site in SARS-CoV-2 has no close match in any known natural sarbecovirus"},
        {"id": "covid-d06", "claim": "WIV researchers were hospitalized with COVID-like illness in November 2019, before the official outbreak timeline"},
        {"id": "covid-d07", "claim": "China blocked international investigators from accessing key WIV data, early samples, and researcher health records"},
        {"id": "covid-d08", "claim": "No intermediate animal host has been identified despite extensive searching over 4+ years"},
        {"id": "covid-d09", "claim": "The Senate HELP Committee concluded the pandemic was 'more likely than not' the result of a research-related incident"},
        {"id": "covid-d10", "claim": "Scientists who publicly dismissed lab leak in the Lancet letter privately acknowledged the possibility in communications"},
    ]

    print(f"\nEvaluating {len(claims)} claims against source documents...")
    results = []
    for claim in claims:
        finding_data = {'description': claim['claim'], 'theory_name': 'COVID Lab Leak (Documents)'}
        evidence = f"CLAIM: {claim['claim']}\n\nSOURCE DOCUMENTS:\n{combined_evidence[:4000]}"
        verdict = engine.evaluate(claim['id'], finding_data, evidence, 'intelligence', 'conspiracy_theories')
        results.append({'claim_id': claim['id'], 'claim': claim['claim'], 'verdict': verdict.verdict, 'score': verdict.overall_score})
        print(f"  {verdict.verdict} ({verdict.overall_score:.2f}) - {claim['claim'][:60]}")
        time.sleep(1.0)

    avg = sum(r['score'] for r in results) / len(results)
    proven = sum(1 for r in results if r['verdict'] == 'PROVEN')
    print(f"\nAverage: {avg:.3f} | Proven: {proven}/{len(results)}")

    output = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'sources': ['DEFUSE Proposal 2018', 'House Intelligence Committee Report 2022'],
        'standard': 'intelligence',
        'results': results,
        'summary': {'avg': avg, 'proven': proven, 'total': len(results)},
    }
    out_path = PROJECT_ROOT / 'src' / 'data' / 'proof-engine-results-covid-documents.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Saved: {out_path}")


if __name__ == '__main__':
    main()
