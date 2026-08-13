"""Show Epstein × Panama Papers results."""
import json

with open('src/data/epstein-x-panama-papers-matches.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Epstein entities searched: {data['epstein_entities_count']}")
print(f"ICIJ entities database: {data['icij_entities_count']:,}")
print(f"EXACT matches: {data['exact_count']}")
print(f"PARTIAL matches: {data['partial_count']}")
print()

exact = [m for m in data['matches'] if m['match_type'] == 'exact']
partial = [m for m in data['matches'] if m['match_type'] == 'partial']

if exact:
    print("EXACT MATCHES (same name in Epstein docs AND offshore records):")
    print("=" * 70)
    for m in exact[:20]:
        print(f"  {m['epstein_name']:35s} → {m['icij_name']}")
        print(f"    Type: {m['icij_type']} | Jurisdiction: {m['jurisdiction']} | Source: {m['source']}")
        print()

if partial:
    print("\nPARTIAL MATCHES (investigate further):")
    print("=" * 70)
    for m in partial[:20]:
        print(f"  {m['epstein_name']:35s} ~ {m['icij_name']}")
        print(f"    Type: {m['icij_type']} | Jurisdiction: {m['jurisdiction']}")
        print()

# Also show Epstein entity sample
print("\nSample Epstein entities extracted:")
for e in data.get('epstein_entity_sample', [])[:20]:
    print(f"  {e}")
