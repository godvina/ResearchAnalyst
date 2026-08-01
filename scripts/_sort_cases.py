"""Sort antitrust cases by priority then estimated harm, rebuild report."""
import json, re, os

with open('src/frontend/antitrust-cases-data.json', encoding='utf-8') as f:
    data = json.load(f)

def parse_harm(h):
    if not h:
        return 0
    h = h.replace(',', '').replace('+', '')
    m = re.search(r'\$(\d+(?:\.\d+)?)\s*(B|M|T)?', h, re.IGNORECASE)
    if not m:
        return 0
    val = float(m.group(1))
    unit = (m.group(2) or 'M').upper()
    if unit == 'T':
        return val * 1_000_000_000_000
    elif unit == 'B':
        return val * 1_000_000_000
    else:
        return val * 1_000_000

priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
data.sort(key=lambda c: (priority_order.get(c['priority'], 2), -parse_harm(c['harm'])))

print('Top 10 after sort:')
for i, c in enumerate(data[:10]):
    print(f"  {i+1}. [{c['priority']}] {c['harm']:>30s} | {c['title'][:50]}")

with open('src/frontend/antitrust-cases-data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
print(f"\nSaved sorted data ({len(data)} cases)")

# Now rebuild the report HTML with sorted inline data
with open('src/frontend/antitrust-report.html', encoding='utf-8') as f:
    html = f.read()

# Find and replace the inline JSON data
start_marker = 'let cases='
end_marker = ';renderAll();'
start_idx = html.index(start_marker) + len(start_marker)
end_idx = html.index(end_marker, start_idx)
html = html[:start_idx] + json.dumps(data) + html[end_idx:]

with open('src/frontend/antitrust-report.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Updated report HTML with sorted data ({os.path.getsize('src/frontend/antitrust-report.html')} bytes)")
