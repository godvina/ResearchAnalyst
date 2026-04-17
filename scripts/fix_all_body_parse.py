"""Fix json.loads body parsing across ALL Lambda handler files."""
import glob
import os

old = 'json.loads(event.get("body") or "{}")'
new = '(json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))'

total_files = 0
total_replaced = 0

for path in glob.glob("src/lambdas/api/*.py"):
    with open(path, "r") as f:
        content = f.read()
    count = content.count(old)
    if count > 0:
        content = content.replace(old, new)
        with open(path, "w") as f:
            f.write(content)
        total_files += 1
        total_replaced += count
        print(f"  {os.path.basename(path)}: {count} replaced")

print(f"\nTotal: {total_replaced} replacements across {total_files} files")
