"""Search ALL cases with taxonomy patterns via API.

Uses the working API endpoint to search each case with our taxonomy signatures.
This is the cross-ALL-datasets search.
"""
import json
import urllib.request
import time
from datetime import datetime, timezone
from pathlib import Path

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
PROJECT_ROOT = Path(__file__).parent.parent

TAXONOMY_QUERIES = [
    ("financial_trail", "shell company offshore account wire transfer money laundering suspicious transaction"),
    ("witness_intimidation", "threat silence NDA payoff coerce pressure witness recant intimidation"),
    ("evidence_suppression", "classified withheld destroyed sealed records blocked FOIA suppressed evidence"),
    ("institutional_behavior", "government agency coordinated cover contradicted official failure oversight"),
    ("regulatory_capture", "revolving door industry funding conflict interest regulator captured oversight"),
    ("foreknowledge", "advance warning predicted knew before simulation foreknowledge prior intelligence"),
    ("geographic_pattern", "island property travel flight location address residence frequent visit"),
    ("organizational_hierarchy", "network associate lieutenant boss structure recruitment chain command"),
]


def get_all_cases():
    resp = urllib.request.urlopen(f'{API}/case-files', timeout=10)
    return json.loads(resp.read()).get('case_files', [])


def search_case(case_id, query, top_k=5):
    body = json.dumps({'query': query, 'top_k': top_k})
    req = urllib.request.Request(
        f'{API}/case-files/{case_id}/search',
        data=body.encode(), headers={'Content-Type': 'application/json'}, method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data.get('results', [])
    except:
        return []


def main():
    print("=" * 70)
    print("CROSS-ALL-CASES TAXONOMY SEARCH")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    cases = get_all_cases()
    # Filter to real cases (skip test/empty)
    real_cases = [c for c in cases if len(c.get('description', '')) > 20 and 'Test' not in c.get('topic_name', '')]
    print(f"Cases to search: {len(real_cases)}")
    for c in real_cases:
        print(f"  • {c['topic_name']}")
    print()

    # Search each taxonomy pattern across ALL cases
    all_results = {}
    for pattern_name, query in TAXONOMY_QUERIES:
        print(f"\nPattern: {pattern_name}")
        pattern_hits = []

        for case in real_cases:
            case_id = case['case_id']
            case_name = case['topic_name']
            results = search_case(case_id, query, top_k=3)

            if results:
                for r in results:
                    score = float(r.get('relevance_score', 0))
                    passage = r.get('passage', '')[:150]
                    if score > 0.25:  # Only meaningful matches
                        pattern_hits.append({
                            'case': case_name,
                            'score': score,
                            'passage': passage,
                        })

            time.sleep(0.3)

        # Sort by score
        pattern_hits.sort(key=lambda x: -x['score'])
        all_results[pattern_name] = pattern_hits

        if pattern_hits:
            print(f"  {len(pattern_hits)} hits across {len(set(h['case'] for h in pattern_hits))} cases:")
            for h in pattern_hits[:5]:
                print(f"    [{h['score']:.3f}] {h['case'][:25]:25s} | {h['passage'][:80]}")
        else:
            print("  No significant matches")

    # Cross-case convergence
    print(f"\n\n{'='*70}")
    print("CROSS-CASE CONVERGENCE: Patterns appearing in 3+ cases")
    print(f"{'='*70}")
    for pattern, hits in sorted(all_results.items(), key=lambda x: -len(set(h['case'] for h in x[1]))):
        case_names = set(h['case'] for h in hits)
        if len(case_names) >= 2:
            avg_score = sum(h['score'] for h in hits) / len(hits) if hits else 0
            print(f"\n  {pattern}: {len(case_names)} cases, avg score {avg_score:.3f}")
            for case in sorted(case_names):
                best = max((h for h in hits if h['case'] == case), key=lambda x: x['score'])
                print(f"    [{best['score']:.3f}] {case}")

    # Save
    output = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'cases_searched': len(real_cases),
        'patterns_searched': len(TAXONOMY_QUERIES),
        'results': {k: v[:10] for k, v in all_results.items()},
    }
    out_path = PROJECT_ROOT / 'src' / 'data' / 'cross-all-cases-taxonomy-search.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
