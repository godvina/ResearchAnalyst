"""Check what Irish/Celtic ancient mystery data we have."""
import json

data = json.load(open(
    "src/data/conspiracy-seed/ancient_mysteries_theories/ancient_alien_theories.json",
    "r", encoding="utf-8"))

theories = data.get("theories", [])
print(f"Total ancient mystery theories: {len(theories)}")

# Search for Irish/Celtic references
irish_keywords = ["ireland", "irish", "newgrange", "tara", "celtic", "druid",
                  "boyne", "knowth", "dowth", "skellig", "aran", "dingle",
                  "brú na bóinne", "tuatha", "ogham", "ley line", "megalith"]

irish_theories = []
for t in theories:
    text = json.dumps(t).lower()
    matches = [kw for kw in irish_keywords if kw in text]
    if matches:
        irish_theories.append((t, matches))

print(f"\nIrish/Celtic related theories: {len(irish_theories)}")
for t, matches in irish_theories:
    print(f"\n  [{t['id']}] {t['title']}")
    print(f"    Matches: {matches}")
    print(f"    Claim: {t.get('claim', '')[:150]}")
    evidence = t.get("current_evidence_for", [])
    if evidence:
        print(f"    Evidence for: {evidence[:2]}")

# Also check which theories mention astronomical alignment or geographic patterns
# (which would apply to Irish sites)
alignment_theories = []
for t in theories:
    text = json.dumps(t).lower()
    if any(kw in text for kw in ["alignment", "solstice", "equinox", "astronomical",
                                  "passage", "chamber", "spiral", "carved"]):
        alignment_theories.append(t)

print(f"\nTheories with alignment/astronomical patterns: {len(alignment_theories)}")
for t in alignment_theories[:5]:
    print(f"  - {t['title']}")
