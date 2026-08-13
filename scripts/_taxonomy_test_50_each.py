"""Taxonomy Validation Test — 50 records from each source.

Tests whether the universal conspiracy taxonomy correctly identifies
cross-domain patterns across all available datasets. Uses 50 records
per source to validate taxonomy coverage before full processing.

Per steering rules: scores against ALL taxonomy domains simultaneously.
"""
import csv
import json
import os
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cross-domain taxonomy signatures (all 3 domains)
TAXONOMY_SIGNATURES = {
    "conspiracy_theory": {
        "evidence_suppression": ["cover up", "suppressed", "hidden", "censored", "silenced", "classified", "redacted", "withheld"],
        "institutional_behavior": ["government", "agency", "official", "denied", "contradicted", "coordinated"],
        "witness_reliability": ["witness", "testimony", "recanted", "credible", "inconsistent", "corroborated"],
        "timeline_anomalies": ["before", "after", "timing", "retroactive", "impossible", "predated", "sequence"],
        "geographic_clustering": ["cluster", "concentrated", "same location", "multiple sites", "pattern"],
        "information_asymmetry": ["knew", "secret", "classified", "disclosed", "revealed", "delayed"],
        "counter_narrative": ["alternative", "theory", "disputed", "mainstream", "official story"],
        "narrative_coherence": ["contradiction", "inconsistent", "doesn't explain", "impossible", "logical"],
        "expert_divergence": ["expert", "scientist", "professor", "disagrees", "whistleblower", "dissent"],
        "methodological_red_flags": ["investigation", "scope", "not examined", "limited", "predetermined", "flawed"],
    },
    "ancient_mysteries": {
        "advanced_technology": ["technology", "precision", "engineering", "impossible", "advanced", "sophisticated"],
        "geographic_alignment": ["alignment", "ley line", "coordinate", "grid", "geometry", "sacred"],
        "lost_knowledge": ["lost", "ancient", "forgotten", "erased", "civilization", "destroyed"],
        "anomalous_artifacts": ["artifact", "anomaly", "unexplained", "mysterious", "out of place"],
        "astronomical_correlation": ["stars", "constellation", "solstice", "equinox", "precession", "orion", "alignment"],
    },
    "crime": {
        "document_concealment": ["shredded", "destroyed", "missing files", "wiped", "deleted", "removed"],
        "witness_intimidation": ["threatened", "killed", "silenced", "died mysteriously", "suicide", "accident"],
        "financial_trail": ["money", "funding", "offshore", "transaction", "payment", "laundering", "billion"],
        "organizational_hierarchy": ["boss", "network", "ring", "operation", "organization", "group"],
        "temporal_clustering": ["same time", "same day", "coincidence", "timing", "before", "right after", "immediately"],
    },
}


def score_text(text: str) -> dict:
    """Score a single text against ALL taxonomy domains."""
    text_lower = text.lower() if text else ""
    matches = {}
    for domain, sigs in TAXONOMY_SIGNATURES.items():
        for sig_name, keywords in sigs.items():
            hits = [kw for kw in keywords if kw in text_lower]
            if hits:
                key = f"{domain}/{sig_name}"
                matches[key] = {
                    "domain": domain,
                    "signature": sig_name,
                    "hits": hits,
                    "count": len(hits),
                }
    return matches


def load_bermuda_sample(n=50):
    """Load n records from NTSB Bermuda Triangle data."""
    path = 'src/data/conspiracy-seed/bermuda_triangle/ntsb_bermuda_accidents.json'
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    records = []
    for acc in data['accidents'][:n]:
        text = f"Aviation accident: {acc.get('ev_city', '')} {acc.get('ev_country', '')} on {acc.get('ev_date', '')}. " \
               f"Highest injury: {acc.get('ev_highest_injury', '')}. Weather: {acc.get('wx_cond_basic', '')}. " \
               f"Location: lat {acc.get('dec_latitude', '')}, lon {acc.get('dec_longitude', '')}"
        records.append({"source": "bermuda_ntsb", "text": text, "id": acc.get('ev_id', '')})
    return records


def load_ufo_sample(n=50):
    """Load n records from UFO sightings."""
    path = 'src/data/conspiracy-seed/ufo_sightings/ufo_sightings.csv'
    records = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= n:
                break
            text = f"UFO sighting: {row.get('Data.Shape', '')} shaped object in {row.get('Location.City', '')}, {row.get('Location.State', '')}. " \
                   f"Duration: {row.get('Data.Encounter duration', '')} seconds. " \
                   f"Description: {row.get('Data.Description excerpt', '')}"
            records.append({"source": "ufo_nuforc", "text": text, "id": f"ufo_{i}"})
    return records


def load_voat_sample(n=50):
    """Load n conspiracy-labeled records from Voat annotations."""
    path = 'src/data/conspiracy-seed/voat_annotations/voat_annotation.csv'
    records = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['overall_ct'] == 'TRUE' and len(records) < n:
                text = row.get('body', '')
                records.append({"source": "voat_conspiracy", "text": text, "id": row.get('comment_id', '')})
    return records


def load_flat_earth_sample(n=50):
    """Load flat earth theories."""
    path = 'src/data/conspiracy-seed/flat_earth/flat_earth_theories.json'
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    records = []
    for t in data['theories'][:n]:
        text = f"{t['title']}: {t['claim']}. Evidence for: {'; '.join(t.get('evidence_for', [])[:3])}. Evidence against: {'; '.join(t.get('evidence_against', [])[:3])}"
        records.append({"source": "flat_earth", "text": text, "id": t['id']})
    return records


def load_ancient_mysteries_sample(n=50):
    """Load ancient mystery theories."""
    path = 'src/data/conspiracy-seed/ancient_mysteries_theories/ancient_alien_theories.json'
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    records = []
    for t in data['theories'][:n]:
        text = f"{t['title']}: {t['claim']}. Evidence for: {'; '.join(t.get('current_evidence_for', [])[:3])}. Evidence against: {'; '.join(t.get('current_evidence_against', [])[:3])}"
        records.append({"source": "ancient_mysteries", "text": text, "id": t['id']})
    return records


def load_vaers_sample(n=50):
    """Load n records from VAERS adverse event database."""
    zip_path = 'docs/AllVAERSDataCSVS.zip'
    if not os.path.exists(zip_path):
        return []
    
    records = []
    with zipfile.ZipFile(zip_path, 'r') as z:
        # Use the most recent year's data file
        data_files = sorted([f for f in z.namelist() if 'DATA' in f and f.endswith('.csv')], reverse=True)
        if not data_files:
            return []
        
        latest_file = data_files[0]
        print(f"  VAERS: reading from {latest_file}")
        
        with z.open(latest_file) as f:
            import io
            content = f.read().decode('latin-1')  # VAERS uses latin-1 encoding
            reader = csv.DictReader(io.StringIO(content))
            
            for i, row in enumerate(reader):
                if i >= n:
                    break
                text = f"VAERS Report: {row.get('VAX_TYPE', '')} vaccine. " \
                       f"Symptoms: {row.get('SYMPTOM_TEXT', '')[:500]}. " \
                       f"Age: {row.get('AGE_YRS', '')}. Sex: {row.get('SEX', '')}. " \
                       f"Died: {row.get('DIED', '')}. Hospitalized: {row.get('HOSPITAL', '')}"
                records.append({"source": "vaers", "text": text, "id": row.get('VAERS_ID', f'vaers_{i}')})
    
    return records


def run_taxonomy_test():
    """Run 50 records from each source through taxonomy scoring."""
    print("=" * 70)
    print("TAXONOMY VALIDATION TEST — 50 Records Per Source")
    print("=" * 70)
    print("Testing whether the universal taxonomy identifies patterns across ALL datasets")
    print("Scoring against ALL taxonomy domains simultaneously (per steering rules)")
    print()
    
    # Load samples
    print("Loading samples (50 per source)...")
    all_records = []
    
    bermuda = load_bermuda_sample(50)
    print(f"  Bermuda Triangle (NTSB): {len(bermuda)} records")
    all_records.extend(bermuda)
    
    ufo = load_ufo_sample(50)
    print(f"  UFO Sightings (NUFORC): {len(ufo)} records")
    all_records.extend(ufo)
    
    voat = load_voat_sample(50)
    print(f"  Voat Conspiracy Posts: {len(voat)} records")
    all_records.extend(voat)
    
    flat_earth = load_flat_earth_sample(50)
    print(f"  Flat Earth Theories: {len(flat_earth)} records")
    all_records.extend(flat_earth)
    
    ancient = load_ancient_mysteries_sample(50)
    print(f"  Ancient Mysteries: {len(ancient)} records")
    all_records.extend(ancient)
    
    vaers = load_vaers_sample(50)
    print(f"  VAERS Vaccine Reports: {len(vaers)} records")
    all_records.extend(vaers)
    
    print(f"\n  TOTAL: {len(all_records)} records across {len(set(r['source'] for r in all_records))} sources")
    print()
    
    # Score all records
    print("Scoring against taxonomy (all domains)...")
    source_stats = defaultdict(lambda: {
        "total": 0,
        "matched": 0,
        "unmatched": 0,
        "domain_hits": defaultdict(int),
        "signature_hits": defaultdict(int),
        "cross_cutting": 0,
    })
    
    for record in all_records:
        source = record['source']
        source_stats[source]['total'] += 1
        
        matches = score_text(record['text'])
        
        if matches:
            source_stats[source]['matched'] += 1
            domains_hit = set()
            for key, match in matches.items():
                source_stats[source]['domain_hits'][match['domain']] += 1
                source_stats[source]['signature_hits'][key] += 1
                domains_hit.add(match['domain'])
            
            if len(domains_hit) >= 2:
                source_stats[source]['cross_cutting'] += 1
        else:
            source_stats[source]['unmatched'] += 1
    
    # Print results
    print()
    print("=" * 70)
    print("TAXONOMY COVERAGE RESULTS")
    print("=" * 70)
    
    overall_matched = 0
    overall_total = 0
    overall_cross = 0
    
    for source, stats in sorted(source_stats.items()):
        total = stats['total']
        matched = stats['matched']
        unmatched = stats['unmatched']
        cross = stats['cross_cutting']
        match_rate = matched / total * 100 if total > 0 else 0
        
        overall_matched += matched
        overall_total += total
        overall_cross += cross
        
        print(f"\n  [{source}] ({total} records)")
        print(f"    Match rate: {matched}/{total} ({match_rate:.0f}%)")
        print(f"    Cross-cutting (2+ domains): {cross} ({cross/total*100:.0f}%)")
        print(f"    Domain breakdown:")
        for domain, count in sorted(stats['domain_hits'].items(), key=lambda x: -x[1]):
            print(f"      {domain}: {count} hits")
        print(f"    Top signatures:")
        for sig, count in sorted(stats['signature_hits'].items(), key=lambda x: -x[1])[:5]:
            print(f"      {sig}: {count}")
    
    # Overall summary
    overall_match_rate = overall_matched / overall_total * 100 if overall_total > 0 else 0
    print(f"\n{'='*70}")
    print(f"OVERALL TAXONOMY HEALTH")
    print(f"{'='*70}")
    print(f"  Total records tested: {overall_total}")
    print(f"  Records with taxonomy matches: {overall_matched} ({overall_match_rate:.0f}%)")
    print(f"  Cross-cutting (match 2+ domains): {overall_cross} ({overall_cross/overall_total*100:.0f}%)")
    print(f"  Unmatched records: {overall_total - overall_matched}")
    
    # Taxonomy health assessment
    print(f"\n  TAXONOMY HEALTH ASSESSMENT:")
    if overall_match_rate >= 80:
        print(f"  ✅ EXCELLENT — taxonomy covers {overall_match_rate:.0f}% of diverse data")
    elif overall_match_rate >= 60:
        print(f"  🟡 GOOD — taxonomy covers {overall_match_rate:.0f}% but gaps exist")
    elif overall_match_rate >= 40:
        print(f"  ⚠️ FAIR — taxonomy covers {overall_match_rate:.0f}%, needs expansion")
    else:
        print(f"  ❌ POOR — taxonomy only covers {overall_match_rate:.0f}%, major gaps")
    
    # Identify gaps
    low_match_sources = [s for s, stats in source_stats.items() if stats['matched']/stats['total'] < 0.5]
    if low_match_sources:
        print(f"\n  GAPS IDENTIFIED (sources with <50% match rate):")
        for s in low_match_sources:
            stats = source_stats[s]
            print(f"    - {s}: {stats['matched']}/{stats['total']} ({stats['matched']/stats['total']*100:.0f}%)")
            print(f"      → Taxonomy may need expansion for this data type")
    
    # Save results
    output = {
        "test_run": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "records_per_source": 50,
            "total_records": overall_total,
            "sources_tested": len(source_stats),
        },
        "overall": {
            "match_rate": round(overall_match_rate, 1),
            "cross_cutting_rate": round(overall_cross / overall_total * 100, 1),
            "health": "excellent" if overall_match_rate >= 80 else "good" if overall_match_rate >= 60 else "fair" if overall_match_rate >= 40 else "poor",
        },
        "per_source": {
            source: {
                "total": stats["total"],
                "matched": stats["matched"],
                "match_rate": round(stats["matched"] / stats["total"] * 100, 1),
                "cross_cutting": stats["cross_cutting"],
                "top_domains": dict(sorted(stats["domain_hits"].items(), key=lambda x: -x[1])),
                "top_signatures": dict(sorted(stats["signature_hits"].items(), key=lambda x: -x[1])[:10]),
            }
            for source, stats in source_stats.items()
        },
        "gaps": low_match_sources,
    }
    
    output_path = 'src/data/taxonomy-validation-test-results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n  Results saved to: {output_path}")


if __name__ == '__main__':
    run_taxonomy_test()
