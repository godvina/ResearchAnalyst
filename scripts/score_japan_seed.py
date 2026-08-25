"""Score the Japan documented-precedent seed against the LIVE signature matcher
(same fire_signatures the global pipeline uses). Shows per case what fires now vs
expected, to drive Japanese keyword additions and any new signature (master-loop:
only add a signature the data supports)."""
import json
import os
from ufo_global_updb_pipeline import load_signatures, fire_signatures, score_report_tier1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "src", "data", "conspiracy-seed", "japan_uap", "japan_seed.json")


def main():
    tax, sigs, meta = load_signatures()
    d = json.load(open(SEED, encoding="utf-8"))
    print("=" * 84)
    print("JAPAN SEED — signature coverage vs the live matcher")
    print("=" * 84)
    allf = set()
    for c in d["cases"]:
        blob = c["description"].lower()
        t1 = score_report_tier1(c["description"])
        fired = set(fire_signatures(blob, sigs))
        allf |= fired
        exp = set(c.get("expected_signatures", []))
        print(f"\n{c['id']}  ({c['city']}, {c['country']} {c['date']})")
        print(f"  Tier-1 keep={t1['keep']}")
        print(f"  FIRED now : {sorted(fired) or '(none)'}")
        print(f"  expected  : {sorted(exp)}")
        missed = exp - fired
        if missed:
            print(f"  MISSED    : {sorted(missed)}  <- keyword/needle gap")
        print(f"  gap note  : {c.get('notes_for_gap','')}")
    print("\n" + "-" * 84)
    print(f"Union fired across Japan seed: {len(allf)} -> {sorted(allf)}")


if __name__ == "__main__":
    main()
