"""Process UFO/NUFORC sightings dataset through the Proof Engine.

Source: NUFORC (National UFO Reporting Center) via CORGIS dataset
Records: 60,632 US sightings (1910-2014)
Fields: Location (city/state/lat/lng), Shape, Duration, Description, Dates
Downloaded: 2026-08-02
Source URL: https://corgis-edu.github.io/corgis/csv/ufo_sightings/

CROSS-DOMAIN SCORING: Per steering rules, we score ALL taxonomy domains
simultaneously (ancient_mysteries + conspiracy_theory + crime). Cross-domain
matches reveal structural patterns across subject areas.

APPROACH: With 60K records, we don't run Proof Engine on each one.
Instead we:
1. Cluster by geographic region and temporal patterns
2. Identify statistical anomalies (geographic clustering, temporal spikes)
3. Build testable theories from the data patterns
4. Run Proof Engine on the meta-theories
"""
import csv
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from collections import defaultdict
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import boto3
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from src.services.proof_engine import ProofEngine

DATA_PATH = 'src/data/conspiracy-seed/ufo_sightings/ufo_sightings.csv'
OUTPUT_PATH = 'src/data/proof-engine-results-ufo-sightings.json'
ANALYSIS_PATH = 'src/data/conspiracy-seed/ufo_sightings/ufo_analysis.json'

# Cross-domain taxonomy signatures (same as voat processor)
TAXONOMY_SIGNATURES = {
    "conspiracy_theory": {
        "evidence_suppression": ["cover up", "suppressed", "hidden", "censored", "silenced", "military", "classified"],
        "coordinated_actors": ["government", "military", "air force", "nasa", "fbi", "cia"],
        "pattern_recognition": ["same", "identical", "formation", "pattern", "multiple", "group"],
        "information_asymmetry": ["reported", "witness", "no explanation", "unexplained", "unknown"],
        "threat_narrative": ["chased", "followed", "beam", "abducted", "paralyzed", "frightened"],
    },
    "ancient_mysteries": {
        "advanced_technology": ["technology", "advanced", "impossible", "craft", "propulsion", "silent"],
        "geographic_alignment": ["formation", "triangle", "grid", "pattern", "hover", "stationary"],
        "anomalous_artifacts": ["object", "craft", "metallic", "glowing", "pulsating"],
        "astronomical_correlation": ["stars", "moon", "planet", "constellation", "orbit"],
    },
    "crime": {
        "temporal_clustering": ["same time", "same night", "multiple witnesses", "several reports"],
        "witness_intimidation": ["afraid", "scared", "threatened", "told not to", "men in black"],
        "organizational_hierarchy": ["military", "base", "installation", "restricted"],
    },
}


def score_text_cross_domain(text: str) -> dict:
    """Score text against ALL taxonomy domains simultaneously."""
    text_lower = text.lower()
    matches = {}
    for domain, sigs in TAXONOMY_SIGNATURES.items():
        for sig_name, keywords in sigs.items():
            hits = [kw for kw in keywords if kw in text_lower]
            if hits:
                key = f"{domain}/{sig_name}"
                matches[key] = {"domain": domain, "signature": sig_name, "hits": hits, "count": len(hits)}
    return matches


def analyze_ufo_data(csv_path: str) -> dict:
    """Analyze UFO sightings for statistical patterns and anomalies."""
    print("  Reading CSV...")
    
    records = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row.get('Location.Coordinates.Latitude ', '0').strip())
                lng = float(row.get('Location.Coordinates.Longitude ', '0').strip())
            except (ValueError, TypeError):
                lat, lng = 0.0, 0.0
            
            try:
                year = int(row.get('Dates.Sighted.Year', '0'))
            except ValueError:
                year = 0
            
            records.append({
                'city': row.get('Location.City', ''),
                'state': row.get('Location.State', ''),
                'lat': lat,
                'lng': lng,
                'shape': row.get('Data.Shape', 'unknown'),
                'duration': row.get('Data.Encounter duration', ''),
                'description': row.get('Data.Description excerpt', ''),
                'year': year,
                'month': int(row.get('Dates.Sighted.Month', '0') or 0),
            })
    
    print(f"  Loaded {len(records)} records")
    
    # Geographic clustering (10-degree grid cells)
    geo_clusters = defaultdict(list)
    for r in records:
        if r['lat'] != 0 and r['lng'] != 0:
            cell = (round(r['lat'] / 2) * 2, round(r['lng'] / 2) * 2)
            geo_clusters[cell].append(r)
    
    # Temporal analysis
    yearly = defaultdict(int)
    monthly = defaultdict(int)
    for r in records:
        if r['year'] > 0:
            yearly[r['year']] += 1
        if r['month'] > 0:
            monthly[r['month']] += 1
    
    # Shape distribution
    shapes = defaultdict(int)
    for r in records:
        shapes[r['shape']] += 1
    
    # Find hotspots (cells with 500+ sightings)
    hotspots = [(cell, len(recs)) for cell, recs in geo_clusters.items() if len(recs) >= 500]
    hotspots.sort(key=lambda x: -x[1])
    
    # Temporal spikes (years with 2x the average)
    if yearly:
        avg_yearly = sum(yearly.values()) / len(yearly)
        spike_years = [(y, c) for y, c in yearly.items() if c > avg_yearly * 2 and y > 1950]
        spike_years.sort(key=lambda x: -x[1])
    else:
        avg_yearly = 0
        spike_years = []
    
    # Bermuda Triangle overlap
    bermuda_sightings = [r for r in records if 18 <= r['lat'] <= 33 and -80 <= r['lng'] <= -64]
    
    # Cross-domain scoring on description samples
    print("  Running cross-domain scoring on sample descriptions...")
    cross_domain_totals = defaultdict(int)
    sample_size = min(1000, len(records))
    step = max(1, len(records) // sample_size)
    for i in range(0, len(records), step):
        desc = records[i].get('description', '')
        if desc:
            matches = score_text_cross_domain(desc)
            for key, match in matches.items():
                cross_domain_totals[key] += match['count']
    
    analysis = {
        "total_records": len(records),
        "geographic": {
            "total_geo_cells": len(geo_clusters),
            "hotspots": [{"lat": h[0][0], "lng": h[0][1], "count": h[1]} for h in hotspots[:15]],
            "bermuda_triangle_sightings": len(bermuda_sightings),
        },
        "temporal": {
            "year_range": f"{min(yearly.keys())}-{max(yearly.keys())}" if yearly else "N/A",
            "average_per_year": round(avg_yearly, 1),
            "spike_years": [{"year": y, "count": c, "multiplier": round(c/avg_yearly, 1)} for y, c in spike_years[:10]],
            "monthly_distribution": dict(monthly),
        },
        "shapes": dict(sorted(shapes.items(), key=lambda x: -x[1])[:15]),
        "cross_domain_matches": dict(sorted(cross_domain_totals.items(), key=lambda x: -x[1])[:20]),
    }
    
    return analysis, records


def build_theories(analysis: dict, records: list) -> list:
    """Build testable meta-theories from statistical patterns in the data."""
    theories = []
    
    # Theory 1: Geographic clustering suggests non-random distribution
    hotspots = analysis['geographic']['hotspots']
    if hotspots:
        theories.append({
            'id': str(uuid.uuid4()),
            'title': 'UFO Geographic Clustering Anomaly',
            'claim': f"UFO sightings are non-randomly distributed, with {len(hotspots)} geographic hotspots containing disproportionate concentrations ({hotspots[0]['count']}+ sightings in single grid cells)",
            'evidence_for': [
                f"Top hotspot: lat {hotspots[0]['lat']}, lng {hotspots[0]['lng']} with {hotspots[0]['count']} sightings",
                f"{len(hotspots)} cells exceed 500 sightings (out of {analysis['geographic']['total_geo_cells']} cells)",
                "Clustering could indicate: (a) real phenomenon, (b) military installations, (c) population density",
            ],
            'evidence_against': [
                "Population density naturally creates clustering in any report-based dataset",
                "Light pollution near cities makes aerial phenomena more visible",
                "Reporting bias: urban areas have better internet access for filing reports",
            ],
            'cross_domain': ['ancient_mysteries/geographic_alignment', 'conspiracy_theory/pattern_recognition'],
        })
    
    # Theory 2: Temporal spikes correlate with media events
    spikes = analysis['temporal']['spike_years']
    if spikes:
        theories.append({
            'id': str(uuid.uuid4()),
            'title': 'UFO Temporal Spike Correlation',
            'claim': f"UFO reports spike dramatically in specific years ({spikes[0]['year']}: {spikes[0]['count']} reports, {spikes[0]['multiplier']}x average), suggesting social/media influence rather than physical phenomena",
            'evidence_for': [
                f"Year {spikes[0]['year']} had {spikes[0]['multiplier']}x the average reporting rate",
                f"{len(spikes)} years exceed 2x the long-term average",
                "Spikes often coincide with popular UFO media (Independence Day 1996, X-Files 1993-2002)",
            ],
            'evidence_against': [
                "Media attention could FOLLOW increased sightings rather than cause them",
                "Improved reporting infrastructure in later years naturally increases counts",
                "Some years with major media have no corresponding spike",
            ],
            'cross_domain': ['conspiracy_theory/pattern_recognition', 'crime/temporal_clustering'],
        })
    
    # Theory 3: Triangle shapes suggest structured craft
    triangle_count = analysis['shapes'].get('triangle', 0)
    total = analysis['total_records']
    if triangle_count > 0:
        theories.append({
            'id': str(uuid.uuid4()),
            'title': 'Triangle Craft Structural Consistency',
            'claim': f"Triangle-shaped sightings ({triangle_count}/{total}, {triangle_count/total*100:.1f}%) suggest a consistent craft type rather than random misidentification",
            'evidence_for': [
                f"{triangle_count} independent reports describe triangular shape",
                "Triangle reports span decades (not a single event)",
                "Multiple witnesses often describe identical characteristics (dark, silent, lights at vertices)",
            ],
            'evidence_against': [
                "B-2 Spirit stealth bomber is triangular and has been operational since 1989",
                "TR-3B and other military black projects match many triangle descriptions",
                "Human cognitive bias toward geometric shapes in ambiguous stimuli",
            ],
            'cross_domain': ['ancient_mysteries/advanced_technology', 'conspiracy_theory/coordinated_actors'],
        })
    
    # Theory 4: Bermuda Triangle overlap
    bermuda = analysis['geographic']['bermuda_triangle_sightings']
    if bermuda > 0:
        theories.append({
            'id': str(uuid.uuid4()),
            'title': 'UFO-Bermuda Triangle Intersection',
            'claim': f"UFO sightings in the Bermuda Triangle region ({bermuda} records) suggest a connection between unexplained aerial and maritime phenomena in this area",
            'evidence_for': [
                f"{bermuda} UFO sightings fall within Bermuda Triangle coordinates (18-33N, 64-80W)",
                "Region has historical reports of electromagnetic anomalies",
                "Multiple phenomenon types (UFO + missing vessels) in same geographic zone",
            ],
            'evidence_against': [
                "Bermuda Triangle is one of the world's busiest air/sea corridors — high traffic = more reports",
                "218 NTSB aviation accidents in the same area suggest normal accident rates",
                "Coast Guard statistics show no anomalous loss rates vs comparable regions",
            ],
            'cross_domain': ['ancient_mysteries/geographic_alignment', 'conspiracy_theory/pattern_recognition', 'crime/temporal_clustering'],
        })
    
    # Theory 5: Description patterns suggest coordinated reporting
    cross_matches = analysis['cross_domain_matches']
    if cross_matches:
        top_conspiracy = sum(v for k, v in cross_matches.items() if 'conspiracy_theory' in k)
        top_ancient = sum(v for k, v in cross_matches.items() if 'ancient_mysteries' in k)
        theories.append({
            'id': str(uuid.uuid4()),
            'title': 'Cross-Domain Narrative Pattern in UFO Reports',
            'claim': f"UFO sighting descriptions contain structural patterns matching both conspiracy ({top_conspiracy} hits) and ancient mysteries ({top_ancient} hits) taxonomy signatures, suggesting shared narrative frameworks",
            'evidence_for': [
                f"Conspiracy theory signatures found in {top_conspiracy} description samples",
                f"Ancient mysteries signatures found in {top_ancient} description samples",
                "Government/military references appear across decades of reports",
                "Description language follows recognizable narrative templates",
            ],
            'evidence_against': [
                "Shared vocabulary doesn't prove coordinated narrative — could reflect genuine observations",
                "Military/government keywords expected when reporting near military airspace",
                "Keyword matching is imprecise — context determines meaning",
            ],
            'cross_domain': list(set(k.split('/')[0] for k in list(cross_matches.keys())[:5])),
        })
    
    return theories


def run_proof_engine(theories: list) -> list:
    """Run theories through Proof Engine with intelligence standard."""
    if HAS_BOTO:
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        engine = ProofEngine(bedrock_client=bedrock)
        print("Connected to Bedrock (Claude 3 Haiku)")
    else:
        engine = ProofEngine(bedrock_client=None)
        print("Running WITHOUT Bedrock")
    
    results = []
    
    for i, theory in enumerate(theories):
        print(f"[{i+1}/{len(theories)}] {theory['title']}...", end=" ", flush=True)
        
        evidence_parts = ["EVIDENCE SUPPORTING:"]
        for e in theory.get('evidence_for', []):
            evidence_parts.append(f"  + {e}")
        evidence_parts.append("\nEVIDENCE AGAINST:")
        for e in theory.get('evidence_against', []):
            evidence_parts.append(f"  - {e}")
        evidence_parts.append(f"\nCROSS-DOMAIN SIGNATURES: {', '.join(theory.get('cross_domain', []))}")
        evidence = "\n".join(evidence_parts)
        
        finding_data = {
            "description": theory['claim'],
            "theory_name": "ufo_sightings",
            "title": theory['title'],
        }
        
        verdict = engine.evaluate(
            finding_id=theory['id'],
            finding_data=finding_data,
            evidence=evidence,
            standard_name="intelligence",
            tenant_id="conspiracy_theories"
        )
        
        domains_hit = list(set(theory.get('cross_domain', [])))
        is_cross_cutting = len(set(d.split('/')[0] if '/' in d else d for d in domains_hit)) >= 2
        
        results.append({
            "theory_id": theory['id'],
            "title": theory['title'],
            "claim": theory['claim'],
            "is_cross_cutting": is_cross_cutting,
            "domains_matched": domains_hit,
            "verdict": verdict.verdict,
            "overall_score": verdict.overall_score,
            "checklist_items": [
                {"item": item.description, "score": item.score, "justification": item.justification[:200]}
                for item in verdict.checklist_items
            ],
            "research_directions": verdict.research_directions,
        })
        
        tag = "[CROSS-CUTTING]" if is_cross_cutting else ""
        print(f"{verdict.verdict} (score: {verdict.overall_score:.2f}) {tag}")
    
    return results


def main():
    print("=" * 60)
    print("UFO SIGHTINGS (NUFORC) PROCESSING")
    print("=" * 60)
    print(f"Source: {DATA_PATH}")
    print(f"Standard: INTELLIGENCE")
    print(f"Cross-domain scoring: ALL domains")
    print()
    
    # Step 1: Analyze
    print("[Step 1] Analyzing 60K+ sighting records...")
    analysis, records = analyze_ufo_data(DATA_PATH)
    
    print(f"  Records: {analysis['total_records']}")
    print(f"  Hotspots (500+ sightings): {len(analysis['geographic']['hotspots'])}")
    print(f"  Bermuda Triangle overlap: {analysis['geographic']['bermuda_triangle_sightings']}")
    print(f"  Temporal spikes: {len(analysis['temporal']['spike_years'])}")
    print()
    
    # Step 2: Build theories
    print("[Step 2] Building testable meta-theories from data patterns...")
    theories = build_theories(analysis, records)
    print(f"  Generated {len(theories)} theories")
    print()
    
    # Save analysis
    with open(ANALYSIS_PATH, 'w', encoding='utf-8') as f:
        json.dump({
            "source": "NUFORC UFO Sightings via CORGIS",
            "source_url": "https://corgis-edu.github.io/corgis/csv/ufo_sightings/",
            "download_date": "2026-08-02",
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis": analysis,
            "theories": theories,
        }, f, indent=2, ensure_ascii=False)
    print(f"  Analysis saved: {ANALYSIS_PATH}")
    print()
    
    # Step 3: Proof Engine
    print("[Step 3] Running Proof Engine...")
    print()
    results = run_proof_engine(theories)
    
    # Step 4: Save
    output = {
        "evaluation_run": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "standard": "intelligence",
            "model": "us.anthropic.claude-3-haiku-20240307-v1:0",
            "source_dataset": "ufo_sightings.csv (NUFORC/CORGIS)",
            "source_url": "https://corgis-edu.github.io/corgis/csv/ufo_sightings/",
            "total_records": analysis['total_records'],
            "theories_evaluated": len(results),
            "cross_domain_scoring": True,
        },
        "data_analysis_summary": {
            "total_sightings": analysis['total_records'],
            "year_range": analysis['temporal']['year_range'],
            "top_shapes": dict(list(analysis['shapes'].items())[:5]),
            "hotspot_count": len(analysis['geographic']['hotspots']),
            "bermuda_overlap": analysis['geographic']['bermuda_triangle_sightings'],
            "temporal_spikes": len(analysis['temporal']['spike_years']),
        },
        "summary": {
            "proven": sum(1 for r in results if r['verdict'] == 'PROVEN'),
            "unproven": sum(1 for r in results if r['verdict'] == 'UNPROVEN'),
            "insufficient": sum(1 for r in results if r['verdict'] == 'INSUFFICIENT_EVIDENCE'),
            "average_score": round(sum(r['overall_score'] for r in results) / len(results), 3) if results else 0,
            "cross_cutting_theories": sum(1 for r in results if r['is_cross_cutting']),
        },
        "cross_domain_analysis": {
            "top_cross_domain_signatures": dict(list(analysis['cross_domain_matches'].items())[:10]),
        },
        "results": results,
    }
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Sightings analyzed: {analysis['total_records']}")
    print(f"  Theories evaluated: {len(results)}")
    print(f"  PROVEN: {output['summary']['proven']}")
    print(f"  UNPROVEN: {output['summary']['unproven']}")
    print(f"  INSUFFICIENT_EVIDENCE: {output['summary']['insufficient']}")
    print(f"  Average score: {output['summary']['average_score']:.3f}")
    print(f"  Cross-cutting: {output['summary']['cross_cutting_theories']}")
    print()
    print(f"Results saved to: {OUTPUT_PATH}")


if __name__ == '__main__':
    main()
