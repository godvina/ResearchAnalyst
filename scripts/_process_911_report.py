"""Process 9/11 Commission Report through the full pipeline.

Following the data-processing-rules.md steering doc:
1. Extract PDF via adapter
2. Upload to S3 (triggers Lambda pipeline)
3. Run Proof Engine on 9/11 conspiracy claims with real document evidence
4. Save results

Source: 9/11 Commission Report (585 pages, 7.2 MB PDF)
Standard: intelligence
"""
import json
import sys
import time
import boto3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.conspiracy_ingestion_adapters import AdapterRegistry
from src.services.proof_engine import ProofEngine


def main():
    print("=" * 70)
    print("9/11 COMMISSION REPORT — FULL PIPELINE PROCESSING")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()

    # Step 1: Extract PDF
    print("Step 1: Extracting PDF...")
    registry = AdapterRegistry()
    records = registry.ingest_file(
        str(PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'nine_eleven' / '911_commission_report.pdf'),
        'nine_eleven'
    )
    if not records:
        print("  ERROR: No records extracted")
        return
    
    doc = records[0]
    print(f"  Extracted: {len(doc.content_text)} chars, {doc.metadata.get('page_count', '?')} pages")

    # Step 2: Upload to S3 (triggers existing Lambda pipeline)
    print("\nStep 2: Uploading to S3...")
    try:
        s3 = boto3.client('s3')
        bucket = 'research-analyst-data-lake-974220725866'
        key = doc.s3_key
        
        # Upload the normalized JSON
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=doc.to_json().encode('utf-8'),
            ContentType='application/json'
        )
        print(f"  Uploaded: s3://{bucket}/{key}")
        print("  ✓ This triggers the deployed Lambda pipeline (Broad Scanner → Taxonomy Scanner → Neptune)")
    except Exception as e:
        print(f"  S3 upload failed: {e}")
        print("  Continuing with local processing...")

    # Step 3: Run Proof Engine on 9/11 claims with document evidence
    print("\nStep 3: Running Proof Engine with document evidence...")
    
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    engine = ProofEngine(bedrock_client=bedrock)
    
    # Key 9/11 claims to evaluate against the actual report
    claims = [
        {"id": "911-r01", "cat": "commission", "claim": "The 9/11 Commission was underfunded and had significant conflicts of interest among its members"},
        {"id": "911-r02", "cat": "intelligence", "claim": "Multiple intelligence agencies had specific advance warnings about the 9/11 attacks that were not acted upon"},
        {"id": "911-r03", "cat": "saudi", "claim": "Saudi government officials provided financial and logistical support to the 9/11 hijackers"},
        {"id": "911-r04", "cat": "fbi", "claim": "FBI field agents identified the hijackers before 9/11 but headquarters blocked their investigations"},
        {"id": "911-r05", "cat": "norad", "claim": "NORAD's response on 9/11 was abnormally slow and confused, inconsistent with standard intercept procedures"},
        {"id": "911-r06", "cat": "cia_oswald", "claim": "The CIA withheld information about hijackers al-Mihdhar and al-Hazmi from the FBI before 9/11"},
        {"id": "911-r07", "cat": "bush_admin", "claim": "The Bush administration downgraded terrorism as a priority compared to the Clinton administration in early 2001"},
        {"id": "911-r08", "cat": "pdb", "claim": "The August 6 2001 Presidential Daily Briefing explicitly warned 'Bin Laden Determined to Strike in US'"},
        {"id": "911-r09", "cat": "financing", "claim": "The financing of the 9/11 attacks was never fully traced and the Commission stated the question of funding was 'of little practical significance'"},
        {"id": "911-r10", "cat": "obstruction", "claim": "Key government officials destroyed or withheld documents and recordings relevant to the 9/11 investigation"},
    ]
    
    # Use actual commission report text as evidence
    report_text = doc.content_text[:4000]  # First 4K chars for context
    
    results = []
    for claim in claims:
        print(f"  Evaluating: {claim['cat']}...")
        
        evidence = f"""9/11 COMMISSION REPORT (585 pages, official US government document):
{report_text}

CLAIM BEING EVALUATED: {claim['claim']}

Note: The 9/11 Commission Report itself documents many failures and gaps.
The question is whether these constitute evidence of the specific claim above."""
        
        finding_data = {'description': claim['claim'], 'theory_name': '9/11 (Commission Report Evidence)'}
        verdict = engine.evaluate(claim['id'], finding_data, evidence, 'intelligence', 'conspiracy_theories')
        
        results.append({
            'claim_id': claim['id'],
            'category': claim['cat'],
            'claim': claim['claim'],
            'verdict': verdict.verdict,
            'score': verdict.overall_score,
            'checklist': [{'item': i.description, 'score': i.score, 'justification': i.justification} for i in verdict.checklist_items],
            'research_directions': verdict.research_directions,
        })
        print(f"    {verdict.verdict} ({verdict.overall_score:.2f})")
        time.sleep(1.0)
    
    # Summary
    print(f"\n{'='*70}")
    print("RESULTS: 9/11 Claims vs Commission Report")
    print(f"{'='*70}")
    avg = sum(r['score'] for r in results) / len(results)
    proven = sum(1 for r in results if r['verdict'] == 'PROVEN')
    print(f"  Average score: {avg:.3f}")
    print(f"  Proven: {proven}/{len(results)}")
    for r in sorted(results, key=lambda x: x['score'], reverse=True):
        print(f"    {r['score']:.2f} [{r['verdict']:15s}] {r['claim'][:70]}")
    
    # Save
    output = {
        'pipeline_run': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': '9/11 Commission Report (585 pages)',
            'standard': 'intelligence',
            's3_key': doc.s3_key,
        },
        'document_stats': {
            'pages': doc.metadata.get('page_count', 0),
            'chars_extracted': len(doc.content_text),
        },
        'results': results,
    }
    
    out_path = PROJECT_ROOT / 'src' / 'data' / 'proof-engine-results-911-commission-report.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
