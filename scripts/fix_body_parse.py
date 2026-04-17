"""Replace all json.loads body parsing with _parse_body helper."""
path = "src/lambdas/api/investigator_analysis.py"
with open(path, "r") as f:
    content = f.read()
old = 'json.loads(event.get("body") or "{}")'
new = "_parse_body(event)"
count = content.count(old)
print(f"Found {count} instances to replace")
content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print(f"Replaced {count} instances")
