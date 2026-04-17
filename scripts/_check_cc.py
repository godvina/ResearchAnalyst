"""Quick check of Command Center response."""
import urllib.request, json

url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/investigator-analysis?bypass_cache=true"
r = urllib.request.urlopen(url, timeout=30)
d = json.loads(r.read().decode())
cc = d.get("command_center", {})
print(f"Score: {cc.get('viability_score')} / Verdict: {cc.get('verdict')} / Cache: {cc.get('cache_hit')}")
print(f"Reasoning: {cc.get('verdict_reasoning', '')[:200]}")
print()
for ind in cc.get("indicators", []):
    print(f"  {ind['emoji']} {ind['name']}: {ind['score']}/100")
    print(f"    Insight: {ind['insight'][:120]}")
    print(f"    Gap: {ind['gap_note'][:120]}")
    print()
sa = cc.get("strategic_assessment", {})
print(f"BLUF: {sa.get('bluf', '')[:200]}")
threads = cc.get("threat_threads", [])
print(f"\nThreads: {len(threads)}")
for t in threads:
    print(f"  {t.get('title', '')} (confidence: {t.get('confidence', 0)})")
