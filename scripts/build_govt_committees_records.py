"""Normalize the government-UAP-committees documented seed into pipeline records.

Six official government bodies (Belgium SOBEPS/BAF, Chile CEFAA, Brazil CENIMAR/Operacao
Prato, Argentina CEFAe, Peru DIFAA, Uruguay CRIDOVNI). Each case keeps its committee as
`source` (BE-SOBEPS, CL-CEFAA, BR-CENIMAR, AR-CEFAe, PE-DIFAA, UY-CRIDOVNI) and real coords.
Documented-case pattern, same as Russia/Japan seeds — public, source-cited historical events.

Input:  src/data/conspiracy-seed/govt_committees/govt_committees_seed.json
Output: docs/govt-committees/govt_committees.json
"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "src", "data", "conspiracy-seed", "govt_committees", "govt_committees_seed.json")
OUT_DIR = os.path.join(ROOT, "docs", "govt-committees")


def main():
    d = json.load(open(SEED, encoding="utf-8"))
    recs = []
    for c in d["cases"]:
        recs.append({
            "id": c["id"], "source": c["source"], "date": c.get("date", ""),
            "description": c["description"], "city": c.get("city", ""),
            "district": "", "country": c.get("country", ""),
            "lat": c.get("lat"), "lng": c.get("lng"),
            "source_url": c.get("source_url", ""),
        })
    doc = {
        "source": "Official government UAP committees (BE/CL/BR/AR/PE/UY), documented public cases",
        "licence": "summaries of public historical events with source links",
        "count": len(recs), "reports": recs,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(doc, open(os.path.join(OUT_DIR, "govt_committees.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"Built {len(recs)} govt-committee records -> docs/govt-committees/govt_committees.json")
    print("  by source:", dict(Counter(r["source"] for r in recs)))


if __name__ == "__main__":
    main()
