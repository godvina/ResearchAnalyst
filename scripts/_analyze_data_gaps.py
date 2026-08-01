"""Analyze data quality and gaps in the grid investigation data."""
import json
from collections import Counter

with open('src/data/uvg-grid-scored-findings.json') as f:
    scored = json.load(f)
with open('src/data/uvg-grid-research-all-nodes.json') as f:
    research = json.load(f)

print("=== DATA QUALITY ANALYSIS ===")
print(f"Nodes researched: {research['total_researched']}/62")
print(f"Nodes with ANY signature match: {scored['total_with_matches']}/59")
print()

# Confidence distribution
conf = Counter()
sig_counts = Counter()
indicator_freq = Counter()
for r in scored['results']:
    for m in r.get('matches', []):
        conf[m['confidence']] += 1
        sig_counts[m['signature_id']] += 1
        for ind in m.get('matched_indicators', []):
            indicator_freq[ind] += 1

print("Confidence distribution:")
for k, v in conf.most_common():
    print(f"  {k}: {v}")
print()

print("Signature hit counts:")
for k, v in sig_counts.most_common():
    print(f"  {k}: {v}")
print()

print("Most common indicators (top 15):")
for k, v in indicator_freq.most_common(15):
    print(f"  {v:3d}x | {k}")
print()

# What's MISSING
no_match = [r['node_id'] for r in scored['results'] if len(r.get('matches', [])) == 0]
print(f"Nodes with 0 matches: {len(no_match)} nodes")
print(f"  IDs: {no_match}")
print()

# Research quality
statuses = Counter()
for r in research['results']:
    statuses[r['brief']['investigation_status']] += 1
print("Investigation status distribution:")
for k, v in statuses.most_common():
    print(f"  {k}: {v}")
print()

# Ley line specific data?
print("=== LEY LINE SPECIFIC DATA ===")
ley_sigs = ['am-gge-lla-001', 'am-gge-lla-002']
for sig in ley_sigs:
    nodes = [r['node_id'] for r in scored['results'] 
             if any(m['signature_id'] == sig for m in r.get('matches', []))]
    print(f"  {sig}: {len(nodes)} matches — nodes {nodes}")
print()

print("=== WHAT'S NEEDED ===")
print("1. Ley line alignment signatures (lla-001, lla-002) have ZERO matches")
print("   -> Need targeted research on great circle alignments through grid vertices")
print("2. 18 nodes have zero matches -> need deeper research")
print("3. Most indicators are GENERIC (proximity-based)")
print("   -> Need specific cultural, archaeological, measurement-based indicators")
print("4. No construction technique data (cnp-001, cnp-002)")
print("   -> Need research on megalithic techniques, astronomical encodings")
print("5. No Documentary Production data (visual assets, expert contacts)")
print("   -> Need production-focused queries")
