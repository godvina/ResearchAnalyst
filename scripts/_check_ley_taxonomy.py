"""Check what ley line / grid taxonomy exists."""
import json

with open(r"src\data\ancient-mysteries-taxonomy.json", encoding="utf-8") as f:
    data = json.load(f)

print("Domain:", data.get("domain_id"), "-", data.get("name"))
print()

for typology in data.get("typologies", []):
    tid = typology.get("typology_id", "")
    tname = typology.get("name", "")
    methods = typology.get("methods", [])
    
    # Show all typologies to find grid/energy/ley
    total_sigs = sum(len(m.get("signatures", [])) for m in methods)
    print(f"  {tid}: {tname} ({len(methods)} methods, {total_sigs} signatures)")
    
    if "grid" in tid.lower() or "energy" in tid.lower() or "earth" in tid.lower():
        print("    ^^^ THIS IS THE GRID/LEY LINES TYPOLOGY ^^^")
        for method in methods:
            mid = method.get("method_id", "")
            mname = method.get("name", "")
            sigs = method.get("signatures", [])
            print(f"    METHOD: {mid} - {mname} ({len(sigs)} signatures)")
            for sig in sigs:
                print(f"      {sig['signature_id']}: {sig['description'][:80]}")
