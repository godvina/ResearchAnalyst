"""Rebuild the theory-registry-data.js with ALL results including flat earth 200."""
import json
import os

base = 'src/data'
all_theories = []

def get_verdict(r):
    return r.get('proof_verdict') or r.get('verdict') or r.get('enriched_verdict') or r.get('baseline_verdict') or 'UNKNOWN'

def get_score(r):
    return r.get('overall_score') or r.get('score') or r.get('enriched_score') or r.get('baseline_score') or 0

# Ancient Mysteries
with open(os.path.join(base, 'proof-engine-results-ancient-mysteries.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
for r in data.get('results', []):
    all_theories.append({'id': r['theory_id'], 'title': r['title'], 'source': r.get('source',''),
        'claim': r.get('claim',''), 'prediction': r.get('testable_prediction',''),
        'verdict': get_verdict(r), 'score': get_score(r),
        'standard': 'scientific', 'dataset': 'ancient_mysteries', 'checklist': [], 'research_directions': r.get('research_directions',[])})

# Bermuda
with open(os.path.join(base, 'proof-engine-results-bermuda-triangle.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
v = data.get('verdict', {})
all_theories.append({'id': 'bermuda-001', 'title': 'Bermuda Triangle Anomalous Danger',
    'source': 'NTSB 218 accidents', 'claim': 'Bermuda Triangle has anomalous accident rate',
    'prediction': '', 'verdict': v.get('verdict','UNPROVEN'), 'score': v.get('overall_score', 0.80),
    'standard': 'scientific', 'dataset': 'bermuda_triangle', 'checklist': [], 'research_directions': []})

# Flat Earth (original 8)
with open(os.path.join(base, 'proof-engine-results-flat-earth.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
for r in data.get('results', []):
    all_theories.append({'id': r.get('theory_id',''), 'title': r.get('title',''),
        'source': 'Flat Earth (original 8)', 'claim': r.get('claim',''), 'prediction': '',
        'verdict': get_verdict(r), 'score': get_score(r),
        'standard': 'scientific', 'dataset': 'flat_earth', 'checklist': [], 'research_directions': []})

# Flat Earth 200 PROOFS (the big one!)
with open('src/data/conspiracy-seed/flat_earth_evidence/dubay_200_full_pipeline_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
for r in data.get('results', []):
    all_theories.append({'id': r.get('claim_id',''), 'title': f"FE#{r.get('number',0)}: {r.get('claim','')[:60]}",
        'source': 'Eric Dubay 200 Proofs', 'claim': r.get('claim',''), 'prediction': '',
        'verdict': r.get('enriched_verdict',''), 'score': r.get('enriched_score', 0),
        'standard': 'scientific', 'dataset': 'flat_earth_200', 'checklist': [], 'research_directions': [],
        'baseline_score': r.get('baseline_score', 0), 'delta': r.get('delta', 0),
        'category': r.get('category', 'uncategorized')})

# UFO
with open(os.path.join(base, 'proof-engine-results-ufo-sightings.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
for r in data.get('results', []):
    all_theories.append({'id': r.get('theory_id',''), 'title': r.get('title',''),
        'source': 'NUFORC 60K sightings', 'claim': r.get('claim',''), 'prediction': '',
        'verdict': get_verdict(r), 'score': get_score(r),
        'standard': 'intelligence', 'dataset': 'ufo_sightings', 'checklist': [], 'research_directions': []})

# Voat
with open(os.path.join(base, 'proof-engine-results-voat-conspiracy.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
for r in data.get('proof_engine_results', []):
    all_theories.append({'id': r.get('theory_id',''), 'title': r.get('title',''),
        'source': r.get('source',''), 'claim': r.get('claim',''), 'prediction': '',
        'verdict': get_verdict(r), 'score': get_score(r),
        'standard': 'intelligence', 'dataset': 'voat_conspiracy', 'checklist': [], 'research_directions': []})

# VAERS (if done)
vaers_path = os.path.join(base, 'proof-engine-results-vaers-full.json')
if os.path.exists(vaers_path):
    with open(vaers_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for r in data.get('results', []):
        all_theories.append({'id': r.get('claim_id',''), 'title': f"VAERS: {r.get('category','')}",
            'source': 'VAERS 2021 (768K reports)', 'claim': r.get('claim',''), 'prediction': '',
            'verdict': r.get('enriched_verdict', r.get('baseline_verdict','')), 'score': r.get('enriched_score', r.get('baseline_score', 0)),
            'standard': 'intelligence', 'dataset': 'vaers', 'checklist': [], 'research_directions': [],
            'delta': r.get('delta', 0)})

# 9/11 + COVID + Moon (if done)
trio_path = os.path.join(base, 'proof-engine-results-911-covid-moon.json')
if os.path.exists(trio_path):
    with open(trio_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for theory_name, theory_data in data.get('results', {}).items():
        for r in theory_data.get('results', []):
            ds = 'nine_eleven' if '9/11' in theory_name else 'covid_lab_leak' if 'COVID' in theory_name else 'moon_landing'
            all_theories.append({'id': r.get('claim_id',''), 'title': r.get('claim','')[:70],
                'source': theory_name, 'claim': r.get('claim',''), 'prediction': '',
                'verdict': r.get('enriched_verdict', r.get('baseline_verdict','')), 'score': r.get('enriched_score', r.get('baseline_score', 0)),
                'standard': 'intelligence', 'dataset': ds, 'checklist': [], 'research_directions': [],
                'delta': r.get('delta', 0)})

# Diana + NWO (if done)
diana_path = os.path.join(base, 'proof-engine-results-diana-nwo.json')
if os.path.exists(diana_path):
    with open(diana_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for theory_name, theory_data in data.get('results', {}).items():
        for r in theory_data.get('results', []):
            ds = 'princess_diana' if 'Diana' in theory_name else 'new_world_order'
            all_theories.append({'id': r.get('claim_id',''), 'title': r.get('claim','')[:70],
                'source': theory_name, 'claim': r.get('claim',''), 'prediction': '',
                'verdict': r.get('enriched_verdict', r.get('baseline_verdict','')), 'score': r.get('enriched_score', r.get('baseline_score', 0)),
                'standard': 'intelligence', 'dataset': ds, 'checklist': [], 'research_directions': [],
                'delta': r.get('delta', 0)})

print(f'Total theories for frontend: {len(all_theories)}')
verdicts = {}
datasets = {}
for t in all_theories:
    v = t['verdict']
    verdicts[v] = verdicts.get(v, 0) + 1
    d = t['dataset']
    datasets[d] = datasets.get(d, 0) + 1
    # Ensure category exists
    if 'category' not in t:
        t['category'] = ''
print(f'Verdicts: {json.dumps(verdicts)}')
print(f'Datasets: {json.dumps(datasets)}')

# Print category coverage
cats_by_ds = {}
for t in all_theories:
    ds = t['dataset']
    cat = t.get('category', '')
    if cat:
        if ds not in cats_by_ds: cats_by_ds[ds] = set()
        cats_by_ds[ds].add(cat)
for ds, cats in cats_by_ds.items():
    print(f'  {ds}: {len(cats)} categories - {list(cats)[:5]}')

with open('src/frontend/theory-registry-data.js', 'w', encoding='utf-8') as f:
    f.write('// Auto-generated — all proof engine results\n')
    f.write('// Includes: flat earth 200 proofs, VAERS, 9/11, COVID, Moon, Diana, NWO\n')
    f.write('const THEORY_DATA = ')
    json.dump(all_theories, f, ensure_ascii=False)
    f.write(';\n')

print('Saved: src/frontend/theory-registry-data.js')

# RFK Fauci (if done)
rfk_path = os.path.join(base, 'proof-engine-results-rfk-fauci.json')
if os.path.exists(rfk_path):
    with open(rfk_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for r in data.get('results', []):
        all_theories.append({'id': r.get('id',''), 'title': r.get('claim','')[:70],
            'source': 'RFK Jr - The Real Anthony Fauci (2021)', 'claim': r.get('claim',''), 'prediction': '',
            'verdict': r.get('enriched_verdict', r.get('baseline_verdict','')), 'score': r.get('enriched_score', r.get('baseline_score', 0)),
            'standard': 'intelligence', 'dataset': 'rfk_fauci', 'checklist': [], 'research_directions': [],
            'delta': r.get('delta', 0), 'category': r.get('cat', '')})

# 9/11 Commission Report (if done)
report_path = os.path.join(base, 'proof-engine-results-911-commission-report.json')
if os.path.exists(report_path):
    with open(report_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for r in data.get('results', []):
        all_theories.append({'id': r.get('claim_id',''), 'title': r.get('claim','')[:70],
            'source': '9/11 Commission Report (585 pages)', 'claim': r.get('claim',''), 'prediction': '',
            'verdict': r.get('verdict',''), 'score': r.get('score', 0),
            'standard': 'intelligence', 'dataset': 'nine_eleven_report', 'checklist': [], 'research_directions': [],
            'category': r.get('category', '')})

# COVID Documents (if done)
covid_doc_path = os.path.join(base, 'proof-engine-results-covid-documents.json')
if os.path.exists(covid_doc_path):
    with open(covid_doc_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for r in data.get('results', []):
        all_theories.append({'id': r.get('claim_id',''), 'title': r.get('claim','')[:70],
            'source': 'DEFUSE Proposal + House Intel Report', 'claim': r.get('claim',''), 'prediction': '',
            'verdict': r.get('verdict',''), 'score': r.get('score', 0),
            'standard': 'intelligence', 'dataset': 'covid_documents', 'checklist': [], 'research_directions': [],
            'category': ''})
