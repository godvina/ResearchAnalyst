"""Quick check of Tier 3 results."""
import json

data = json.load(open("scripts/epstein_tier3_entities.json", "r", encoding="utf-8"))
print(f"Docs: {data['documents_processed']}")
print(f"Entities: {data['total_entities']}")
print(f"Relationships: {data['total_relationships']}")
print(f"Red flags: {data['total_red_flags']}")
print()
print("Top 20 entities:")
for name, count in list(data["top_entities"].items())[:20]:
    print(f"  {name}: {count}")
print()
print("Top 10 red flags:")
for f in data["red_flags"][:10]:
    print(f"  * {f}")
