"""Show top 25 findings from Pass 1 research, priority ranked."""
import json

with open(r"src\data\uvg-grid-research-all-nodes.json", encoding="utf-8") as f:
    data = json.load(f)

results = data.get("results", [])
status_rank = {"CONFIRMED": 0, "PROBABLE": 1, "INCONCLUSIVE": 2, "NEGATIVE": 3}

ranked = []
for r in results:
    brief = r.get("brief", {})
    if brief.get("error"):
        continue
    status = brief.get("investigation_status", "INCONCLUSIVE")
    for key in status_rank:
        if key in str(status).upper():
            status = key
            break
    ranked.append({
        "node_id": r["node_id"],
        "lat": r["lat"],
        "lng": r["lng"],
        "classification": r["classification"],
        "status": status,
        "codename": brief.get("codename", "?"),
        "smoking_gun": brief.get("smoking_gun", ""),
        "situation": brief.get("situation", "")[:200],
    })

ranked.sort(key=lambda x: status_rank.get(x["status"], 99))

confirmed = [r for r in ranked if r["status"] == "CONFIRMED"]
probable = [r for r in ranked if r["status"] == "PROBABLE"]
inconclusive = [r for r in ranked if r["status"] == "INCONCLUSIVE"]

print(f"PASS 1 FINDINGS — PRIORITY RANKED")
print(f"Total nodes: {len(ranked)}")
print(f"  CONFIRMED:    {len(confirmed)}")
print(f"  PROBABLE:     {len(probable)}")
print(f"  INCONCLUSIVE: {len(inconclusive)}")
print()
print("=" * 80)

for i, r in enumerate(ranked[:25], 1):
    gun = r["smoking_gun"]
    if "No definitive" in gun:
        gun = ""
    print(f"{i:>2}. [{r['status']:>12}] Node {r['node_id']:>2} | {r['codename']}")
    print(f"    {r['lat']:.2f}, {r['lng']:.2f} | {r['classification']}")
    if gun:
        print(f"    KEY: {gun[:140]}")
    else:
        print(f"    {r['situation'][:140]}")
    print()
