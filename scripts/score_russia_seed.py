"""Score the Russia/Soviet documented-precedent seed against the LIVE signature matcher
(the same fire_signatures the global pipeline uses). Shows, per case: what fires now,
what we expected, and the gap. This drives which NEW signatures to author (master-loop:
only add a signature the data supports)."""
import json
import os
from ufo_global_updb_pipeline import load_signatures, fire_signatures, score_report_tier1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "src", "data", "conspiracy-seed", "russia_soviet_uap", "russia_seed.json")


def main():
    tax, sigs, meta = load_signatures()
    d = json.load(open(SEED, encoding="utf-8"))
    print("=" * 84)
    print("RUSSIA/SOVIET SEED — signature coverage vs the live matcher")
    print("=" * 84)
    all_fired = set()
    for c in d["cases"]:
        blob = c["description"].lower()
        t1 = score_report_tier1(c["description"])
        fired = fire_signatures(blob, sigs)
        all_fired.update(fired)
        exp = set(c.get("expected_signatures", []))
        got = set(fired)
        print(f"\n{c['id']}  ({c['city']}, {c['country']} {c['date']})")
        print(f"  Tier-1 keep={t1['keep']}  keyword_hits={t1.get('total_hits','?')}")
        print(f"  FIRED now : {sorted(got) or '(none)'}")
        print(f"  expected  : {sorted(exp)}")
        missed = exp - got
        if missed:
            print(f"  MISSED    : {sorted(missed)}  <- keyword/needle gap")
        print(f"  gap note  : {c.get('notes_for_gap','')}")
    print("\n" + "-" * 84)
    print(f"Union of signatures fired across seed: {len(all_fired)} -> {sorted(all_fired)}")
    print("Candidate NEW signatures suggested by the seed (not in current taxonomy):")
    print("  * plasma/amorphous 'jellyfish' morphology + light-beam emission (Petrozavodsk)")
    print("  * strategic-weapons / nuclear-missile system activation-interference (Usovo 1982)")
    print("  * recovered-material / metallurgical anomaly from a downed object (Dalnegorsk)")
    print("  * military engagement / interception-with-force (Siberia 1987)")


if __name__ == "__main__":
    main()
