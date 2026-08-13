"""Debug edge loading — check entity ID coverage."""
import json

entities = json.load(open("scripts/rhowardstone_data/knowledge_graph_entities.json", "r", encoding="utf-8"))
rels = json.load(open("scripts/rhowardstone_data/knowledge_graph_relationships.json", "r", encoding="utf-8"))

# Build ID → name map
id_to_name = {}
for e in entities:
    id_to_name[e["id"]] = e["name"]

print(f"Entities: {len(entities)}")
print(f"Entity ID range: {min(e['id'] for e in entities)} - {max(e['id'] for e in entities)}")
print(f"Relationships: {len(rels)}")
print()

# Check how many rels reference valid entity IDs
valid = 0
invalid_source = 0
invalid_target = 0
for r in rels:
    src = r["source_entity_id"]
    tgt = r["target_entity_id"]
    src_ok = src in id_to_name
    tgt_ok = tgt in id_to_name
    if src_ok and tgt_ok:
        valid += 1
    if not src_ok:
        invalid_source += 1
    if not tgt_ok:
        invalid_target += 1

print(f"Valid (both endpoints exist): {valid}")
print(f"Invalid source: {invalid_source}")
print(f"Invalid target: {invalid_target}")
print()

# Show sample valid edge with resolved names
print("Sample valid edges:")
count = 0
for r in rels:
    src_name = id_to_name.get(r["source_entity_id"])
    tgt_name = id_to_name.get(r["target_entity_id"])
    if src_name and tgt_name:
        print(f"  {src_name} → {tgt_name} ({r['relationship_type']}) weight={r['weight']}")
        count += 1
        if count >= 10:
            break
