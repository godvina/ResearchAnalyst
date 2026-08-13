"""Inspect the downloaded rhowardstone data formats."""
import json

# Check extracted_entities_filtered.json structure
data = json.load(open("scripts/rhowardstone_data/extracted_entities_filtered.json", "r", encoding="utf-8"))
print(f"Type: {type(data).__name__}")
if isinstance(data, dict):
    print(f"Keys: {list(data.keys())}")
    for k, v in data.items():
        if isinstance(v, list):
            print(f"  {k}: list of {len(v)}")
            if v:
                print(f"    Sample: {v[0]}")
        elif isinstance(v, dict):
            print(f"  {k}: dict with {len(v)} keys")
            sample_keys = list(v.keys())[:3]
            for sk in sample_keys:
                print(f"    {sk}: {v[sk]}")
        else:
            print(f"  {k}: {v}")
elif isinstance(data, list):
    print(f"Length: {len(data)}")
    if data:
        print(f"First item type: {type(data[0]).__name__}")
        print(f"First item: {data[0]}")

print("\n\n--- Knowledge Graph Entities ---")
kg = json.load(open("scripts/rhowardstone_data/knowledge_graph_entities.json", "r", encoding="utf-8"))
print(f"Type: {type(kg).__name__}, Length: {len(kg)}")
if isinstance(kg, list) and kg:
    print(f"First: {json.dumps(kg[0], indent=2)[:300]}")
elif isinstance(kg, dict):
    print(f"Keys: {list(kg.keys())[:10]}")
    # Check first value
    first_key = list(kg.keys())[0]
    print(f"First value ({first_key}): {kg[first_key]}")

print("\n\n--- Knowledge Graph Relationships ---")
rels = json.load(open("scripts/rhowardstone_data/knowledge_graph_relationships.json", "r", encoding="utf-8"))
print(f"Type: {type(rels).__name__}, Length: {len(rels)}")
if isinstance(rels, list) and rels:
    print(f"First: {json.dumps(rels[0], indent=2)[:300]}")
elif isinstance(rels, dict):
    print(f"Keys: {list(rels.keys())[:10]}")
    first_key = list(rels.keys())[0]
    print(f"First value ({first_key}): {json.dumps(rels[first_key], indent=2)[:200]}")
