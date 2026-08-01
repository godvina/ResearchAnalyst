"""
SAM.gov OSINT Trawler - Fetches entity data for all ATR cases.

Queries the SAM.gov Entity Management API for each subject company,
saves structured results to data/osint/sam_gov_results.json.

Usage:
    python scripts/fetch_sam_gov.py

The output JSON is consumed by the antitrust-report.html drill-down modal
to show real OSINT source data when clicking on "SAM.gov" in the OSINT section.

API Docs: https://open.gsa.gov/api/entity-api/
Rate limit: ~10 req/sec (public tier)
"""

import json
import os
import sys
import time
import requests
from pathlib import Path

# --- Configuration ---
SAM_API_KEY = os.environ.get('SAM_API_KEY', 'SAM-aacbd729-cc35-41f6-a4ef-1cdcddee68a9')
SAM_BASE_URL = 'https://api.sam.gov/entity-information/v3/entities'
OUTPUT_DIR = Path('data/osint')
OUTPUT_FILE = OUTPUT_DIR / 'sam_gov_results.json'
PROGRESS_FILE = OUTPUT_DIR / 'sam_gov_progress.json'
RATE_LIMIT_DELAY = 3.0  # seconds between requests (very conservative for SAM.gov public tier)


# --- Top 10 procurement cases for demo (most likely to have SAM.gov registrations) ---
CASES = [
    {"title": "Military Base Fuel Supply Bid-Rigging (Fort Bragg)", "category": "procurement_collusion", "subjects": ["Petroleum Traders Corp", "TransMontaigne Partners", "Global Industries"], "industry": "military_fuel_supply"},
    {"title": "Federal IT Services Contract Bid-Rigging (GSA Schedule)", "category": "procurement_collusion", "subjects": ["Unison Technologies", "DLT Solutions", "Carahsoft Technology", "Mythics Inc"], "industry": "federal_IT_services"},
    {"title": "Navy Ship Repair Bid-Rigging (Norfolk Naval Shipyard)", "category": "procurement_collusion", "subjects": ["BAE Systems Ship Repair", "Metro Machine Corp"], "industry": "naval_ship_repair"},
    {"title": "VA Hospital Medical Supply Bid-Rigging", "category": "procurement_collusion", "subjects": ["Medline Industries", "Owens & Minor", "Cardinal Health Distribution", "McKesson Medical-Surgical"], "industry": "medical_supplies"},
    {"title": "FEMA Disaster Relief Supply Bid-Rigging", "category": "procurement_collusion", "subjects": ["Fluor Enterprises", "Clean Harbors"], "industry": "disaster_relief_supplies"},
    {"title": "Highway Construction Bid-Rigging (North Carolina DOT)", "category": "procurement_collusion", "subjects": ["Blythe Construction", "Barnhill Contracting"], "industry": "highway_construction"},
    {"title": "Airport Construction Bid-Rigging (Atlanta)", "category": "procurement_collusion", "subjects": ["Holder Construction", "Hensel Phelps", "McCarthy Building Companies"], "industry": "airport_construction"},
    {"title": "EPA Superfund Cleanup Bid-Rigging", "category": "procurement_collusion", "subjects": ["Clean Harbors", "US Ecology"], "industry": "environmental_remediation"},
    {"title": "Coast Guard Vessel Maintenance Bid-Rigging", "category": "procurement_collusion", "subjects": ["Vigor Industrial", "Bollinger Shipyards"], "industry": "coast_guard_maintenance"},
    {"title": "Lockheed Martin/Aerojet Rocketdyne Merger", "category": "merger_review", "subjects": ["Lockheed Martin", "Aerojet Rocketdyne"], "industry": "defense"},
]


def query_sam_entity(entity_name: str, retries: int = 3) -> dict:
    """Query SAM.gov Entity Management API for a single entity."""
    params = {
        'api_key': SAM_API_KEY,
        'legalBusinessName': entity_name,
        'registrationStatus': 'A',
        'includeSections': 'entityRegistration,coreData',
    }
    try:
        resp = requests.get(SAM_BASE_URL, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            total = data.get('totalRecords', 0)
            entities = data.get('entityData', [])
            return {
                'query': entity_name,
                'total_records': total,
                'status': 'found' if total > 0 else 'not_found',
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'entities': [summarize_entity(e) for e in entities[:5]],
            }
        elif resp.status_code == 429:
            if retries > 0:
                wait = 5 * (4 - retries)  # 5s, 10s, 15s backoff
                print(f"  Rate limited. Waiting {wait}s... ({retries} retries left)")
                time.sleep(wait)
                return query_sam_entity(entity_name, retries - 1)
            else:
                return {
                    'query': entity_name,
                    'total_records': 0,
                    'status': 'rate_limited',
                    'error': 'Rate limited after 3 retries',
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'entities': [],
                }
        else:
            return {
                'query': entity_name,
                'total_records': 0,
                'status': 'error',
                'error': f'HTTP {resp.status_code}: {resp.text[:200]}',
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'entities': [],
            }
    except Exception as e:
        return {
            'query': entity_name,
            'total_records': 0,
            'status': 'error',
            'error': str(e),
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'entities': [],
        }


def summarize_entity(entity: dict) -> dict:
    """Extract key fields from a SAM.gov entity record."""
    reg = entity.get('entityRegistration', {})
    core = entity.get('coreData', {})
    phys_addr = core.get('physicalAddress', {})
    return {
        'ueiSAM': reg.get('ueiSAM', ''),
        'legalBusinessName': reg.get('legalBusinessName', ''),
        'dbaName': reg.get('dbaName', ''),
        'registrationStatus': reg.get('registrationStatus', ''),
        'registrationDate': reg.get('registrationDate', ''),
        'expirationDate': reg.get('expirationDate', ''),
        'cageCode': reg.get('cageCode', ''),
        'city': phys_addr.get('city', ''),
        'state': phys_addr.get('stateOrProvinceCode', ''),
        'country': phys_addr.get('countryCode', ''),
        'entityType': core.get('entityInformation', {}).get('entityStructureDesc', ''),
    }


def load_progress() -> dict:
    """Load previously fetched results to allow resuming."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_progress(results: dict):
    """Save progress incrementally."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(results, f, indent=2)


def main():
    print("=" * 60)
    print("SAM.gov OSINT Trawler - Antitrust Case Portfolio")
    print("=" * 60)
    print(f"API Key: {SAM_API_KEY[:12]}...{SAM_API_KEY[-4:]}")
    print(f"Cases: {len(CASES)}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    all_results = load_progress()
    total_subjects = sum(len(c['subjects']) for c in CASES)
    print(f"Subjects to query: {total_subjects}")
    print(f"Already fetched: {sum(len(v.get('subjects', {})) for v in all_results.values())}")
    print()

    fetched = 0
    skipped = 0

    for case_idx, case in enumerate(CASES):
        print(f"[{case_idx+1}/{len(CASES)}] {case['title']}")
        case_key = case['title']

        if case_key not in all_results:
            all_results[case_key] = {
                'case_title': case['title'],
                'category': case['category'],
                'industry': case['industry'],
                'subjects': {},
            }

        for subject in case['subjects']:
            if subject in all_results[case_key].get('subjects', {}):
                skipped += 1
                print(f"  → {subject} (cached)")
                continue

            print(f"  → Querying: {subject}...", end=' ')
            result = query_sam_entity(subject)
            all_results[case_key]['subjects'][subject] = result
            fetched += 1

            status_icon = 'Y' if result['status'] == 'found' else 'N' if result['status'] == 'not_found' else '!'
            print(f"[{status_icon}] ({result['total_records']} records)")

            time.sleep(RATE_LIMIT_DELAY)

            if fetched % 10 == 0:
                save_progress(all_results)

    # Final save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_results, f, indent=2)
    save_progress(all_results)

    print()
    print("=" * 60)
    print("COMPLETE")
    print(f"  Fetched: {fetched}")
    print(f"  Skipped (cached): {skipped}")
    print(f"  Output: {OUTPUT_FILE}")

    found_count = sum(
        1 for case_data in all_results.values()
        for subj_data in case_data.get('subjects', {}).values()
        if subj_data.get('status') == 'found'
    )
    print(f"  Found in SAM.gov: {found_count}")
    print(f"  Not found: {total_subjects - found_count}")
    print("=" * 60)


if __name__ == '__main__':
    main()
