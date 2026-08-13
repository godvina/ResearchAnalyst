"""Cross-reference Epstein entities against Panama/Pandora Papers (ICIJ).

This is the real needle-finding operation:
1. Pull ALL Epstein entities from the API (both 345K case and Combined)
2. Download ICIJ entities database (321 MB, already in S3)
3. Cross-match: do any Epstein names appear in offshore shell companies?

Zero Bedrock cost — pure entity name matching.
"""
import boto3
import json
import urllib.request
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
BUCKET = 'research-analyst-data-lake-974220725866'

s3 = boto3.client('s3')


def get_epstein_entities():
    """Pull entities from ALL Epstein cases via API search."""
    print("  Pulling Epstein entities via API...")
    
    # Get all case IDs
    resp = urllib.request.urlopen(f'{API}/case-files', timeout=10)
    cases = json.loads(resp.read()).get('case_files', [])
    epstein_cases = [c for c in cases if 'Epstein' in c.get('topic_name', '')]
    print(f"  Found {len(epstein_cases)} Epstein cases")
    
    all_entities = set()
    all_entity_details = []
    
    # Search across all Epstein cases for entity-rich results
    search_queries = [
        'Epstein', 'Maxwell', 'flight', 'island', 'foundation',
        'bank', 'company', 'financial', 'attorney', 'testimony',
        'witness', 'victim', 'associate', 'travel', 'property',
        'trust', 'corporation', 'offshore', 'account', 'payment',
    ]
    
    for case in epstein_cases:
        case_id = case['case_id']
        case_name = case['topic_name']
        
        for query in search_queries:
            body = json.dumps({'query': query, 'top_k': 20})
            req = urllib.request.Request(
                f'{API}/case-files/{case_id}/search',
                data=body.encode(), headers={'Content-Type': 'application/json'}, method='POST'
            )
            try:
                resp = urllib.request.urlopen(req, timeout=10)
                data = json.loads(resp.read())
                results = data.get('results', [])
                for r in results:
                    passage = r.get('passage', r.get('text', ''))
                    if passage:
                        # Extract names from passages (simple approach - look for capitalized words)
                        words = passage.split()
                        for i in range(len(words) - 1):
                            if words[i][0:1].isupper() and words[i+1][0:1].isupper():
                                name = f"{words[i]} {words[i+1]}"
                                # Clean
                                name = name.strip('.,;:()"\'')
                                if len(name) > 4 and len(name) < 50 and ' ' in name:
                                    all_entities.add(name)
                                    all_entity_details.append({
                                        'name': name, 'case': case_name, 'context': passage[:100]
                                    })
            except:
                continue
        
        print(f"    {case_name}: {len(all_entities)} unique entities so far")
    
    return all_entities, all_entity_details


def load_icij_entities():
    """Load ICIJ (Panama/Pandora Papers) entities from S3."""
    print("  Downloading ICIJ entities from S3 (321 MB)...")
    print("  This may take a minute...")
    
    # Stream the JSONL file
    obj = s3.get_object(Bucket=BUCKET, Key='hsi-cases/icij-reference/entities.jsonl')
    body = obj['Body']
    
    icij_entities = {}  # name → details
    icij_names_lower = {}  # lowercase name → original name
    count = 0
    
    # Read line by line (JSONL format)
    buffer = ''
    for chunk in body.iter_chunks(chunk_size=1024*1024):  # 1MB chunks
        buffer += chunk.decode('utf-8', errors='replace')
        lines = buffer.split('\n')
        buffer = lines[-1]  # Keep incomplete last line
        
        for line in lines[:-1]:
            if not line.strip():
                continue
            try:
                entity = json.loads(line)
                name = entity.get('name', entity.get('entity_name', ''))
                if name and len(name) > 2:
                    icij_entities[name] = {
                        'type': entity.get('type', entity.get('entity_type', '')),
                        'jurisdiction': entity.get('jurisdiction', entity.get('country', '')),
                        'source': entity.get('source', entity.get('dataset', '')),
                    }
                    icij_names_lower[name.lower()] = name
                    count += 1
            except json.JSONDecodeError:
                continue
        
        if count % 100000 == 0 and count > 0:
            print(f"    Loaded {count:,} ICIJ entities...")
    
    print(f"  Total ICIJ entities loaded: {count:,}")
    return icij_entities, icij_names_lower


def cross_reference(epstein_entities, icij_entities, icij_names_lower):
    """Find Epstein entities that appear in Panama/Pandora Papers."""
    print("\n  Cross-referencing...")
    
    matches = []
    
    for name in epstein_entities:
        name_lower = name.lower()
        
        # Exact match
        if name_lower in icij_names_lower:
            icij_name = icij_names_lower[name_lower]
            icij_detail = icij_entities.get(icij_name, {})
            matches.append({
                'epstein_name': name,
                'icij_name': icij_name,
                'match_type': 'exact',
                'icij_type': icij_detail.get('type', ''),
                'jurisdiction': icij_detail.get('jurisdiction', ''),
                'source': icij_detail.get('source', ''),
            })
        
        # Partial match (last name)
        parts = name.split()
        if len(parts) >= 2:
            last_name = parts[-1].lower()
            if len(last_name) > 4:  # Avoid common short names
                for icij_lower, icij_orig in icij_names_lower.items():
                    if last_name in icij_lower and icij_lower != name_lower:
                        if len(icij_lower) < 50:  # Avoid matching against huge strings
                            # Check if first name also partially matches
                            first = parts[0].lower()
                            if first[:3] in icij_lower:
                                icij_detail = icij_entities.get(icij_orig, {})
                                matches.append({
                                    'epstein_name': name,
                                    'icij_name': icij_orig,
                                    'match_type': 'partial',
                                    'icij_type': icij_detail.get('type', ''),
                                    'jurisdiction': icij_detail.get('jurisdiction', ''),
                                    'source': icij_detail.get('source', ''),
                                })
                                break  # One partial match per entity
    
    return matches


def main():
    print("=" * 70)
    print("EPSTEIN × PANAMA/PANDORA PAPERS — ENTITY CROSS-REFERENCE")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Cost: $0 (pure entity matching, no Bedrock)")
    print()
    
    # Step 1: Get Epstein entities
    print("STEP 1: Extracting Epstein entities from API...")
    epstein_entities, entity_details = get_epstein_entities()
    print(f"  Unique Epstein entities: {len(epstein_entities)}")
    
    # Step 2: Load ICIJ data
    print("\nSTEP 2: Loading ICIJ entities (Panama/Pandora Papers)...")
    icij_entities, icij_names_lower = load_icij_entities()
    
    # Step 3: Cross-reference
    print("\nSTEP 3: Cross-referencing Epstein × ICIJ...")
    matches = cross_reference(epstein_entities, icij_entities, icij_names_lower)
    
    # Results
    print(f"\n{'='*70}")
    print("RESULTS: EPSTEIN × PANAMA/PANDORA PAPERS MATCHES")
    print(f"{'='*70}")
    print(f"  Epstein entities searched: {len(epstein_entities)}")
    print(f"  ICIJ entities searched against: {len(icij_entities):,}")
    print(f"  MATCHES FOUND: {len(matches)}")
    
    exact = [m for m in matches if m['match_type'] == 'exact']
    partial = [m for m in matches if m['match_type'] == 'partial']
    print(f"    Exact matches: {len(exact)}")
    print(f"    Partial matches: {len(partial)}")
    
    if exact:
        print(f"\n  🔥 EXACT MATCHES (Epstein name in offshore records):")
        for m in exact[:20]:
            print(f"    {m['epstein_name']:30s} → [{m['icij_type']:10s}] {m['icij_name']} ({m['jurisdiction']})")
    
    if partial:
        print(f"\n  ⚡ PARTIAL MATCHES (investigate further):")
        for m in partial[:20]:
            print(f"    {m['epstein_name']:30s} ~ {m['icij_name']} [{m['icij_type']}] ({m['jurisdiction']})")
    
    # Save
    output = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'epstein_entities_count': len(epstein_entities),
        'icij_entities_count': len(icij_entities),
        'matches': matches,
        'exact_count': len(exact),
        'partial_count': len(partial),
        'epstein_entity_sample': list(epstein_entities)[:50],
    }
    out_path = PROJECT_ROOT / 'src' / 'data' / 'epstein-x-panama-papers-matches.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == '__main__':
    main()
