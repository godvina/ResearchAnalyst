"""Step D — signature GAP MINER over the whole combined firing corpus.

Runs AFTER every dataset merge (per taxonomy-enrichment-master-loop.md). Finds the
"near-misses": reports that PASS Tier-1 (they look UAP-relevant) but fire 0 or 1
signatures. Those are where the taxonomy is blind. It then clusters the recurring
vocabulary in the near-misses to surface candidate NEW patterns — with a frequency
count and example reports, so we only author signatures the corpus actually supports.

Reuses the pipeline's own loaders + matchers so the result is identical to production.

Output: scripts/signature_gap_report.json + console summary.
"""
import json
import os
import re
from collections import Counter

# reuse the exact production pieces
from ufo_global_updb_pipeline import (
    PROJECT_ROOT, UPDB, load_signatures, score_report_tier1, fire_signatures,
)

# Existing coverage vocabulary — phrases already well-modeled, so we DON'T re-surface them.
ALREADY_COVERED = {
    "triangle", "triangular", "disc", "disk", "saucer", "sphere", "orb", "cigar",
    "hover", "hovering", "hovered", "silent", "no sound", "radar", "pilot", "police",
    "military", "landed", "landing", "occupant", "being", "nuclear", "missile",
    "jellyfish", "plasma", "beam", "recurring", "engine", "instant", "right angle",
    "the", "and", "was", "were", "with", "that", "this", "they", "there", "have",
    "from", "over", "then", "which", "about", "into", "just", "like", "some", "when",
    "what", "very", "could", "would", "seen", "saw", "looked", "appeared", "object",
    "objects", "light", "lights", "sky", "night", "minutes", "seconds", "moving",
    "shape", "shaped", "white", "red", "green", "blue", "bright", "one", "two",
    "for", "not", "had", "his", "her", "him", "our", "out", "who", "all", "are",
    "but", "she", "you", "your", "has", "him", "its", "did", "get", "got", "see",
}

# Candidate uncovered-pattern probes (hypotheses to quantify — NOT yet signatures).
# Each is a family of terms; we count how many near-miss reports contain any of them.
PROBES = {
    "sound_hum_buzz": ["humming", "buzzing", "buzz", "loud hum", "vibrating sound", "whirring", "pulsating sound"],
    "color_shift": ["changed color", "changed colour", "color changed", "colour changed", "shifting colors", "cycled through colors", "pulsating color"],
    "formation_fleet": ["formation", "fleet", "in a row", "evenly spaced", "cluster of", "swarm", "group of objects", "string of"],
    "animal_reaction": ["dogs barking", "animals", "cattle", "livestock", "dog began", "birds", "horses spooked"],
    "time_loss_missing": ["missing time", "lost time", "time loss", "hours later", "could not account", "disorient"],
    "electronic_device": ["phone died", "camera malfunction", "watch stopped", "battery drained", "tv interference", "electronics failed"],
    "physical_aftereffect": ["felt heat", "headache", "nausea", "sunburn", "unable to sleep", "marks on", "nosebleed"],
    "beam_abduction": ["beam of light", "pulled up", "taken aboard", "levitated", "tractor beam", "lifted into"],
    "submerged_water": ["into the ocean", "into the sea", "out of the water", "beneath the surface", "submerged", "off the coast"],
    "repeated_return": ["came back", "returned the next", "same time each", "every night", "appears regularly", "keeps coming"],
    "temperature_silence": ["dead silence", "everything went quiet", "air felt", "cold spot", "sudden cold"],
    "physical_pursuit_car": ["followed my car", "chased us", "paced my car", "followed us home", "kept pace"],
}


def load_all_reports():
    reports = json.load(open(UPDB, encoding="utf-8", errors="replace"))["reports"]
    for rel in [("docs", "spanish-ufo", "spain_airforce_ufo.json"),
                ("docs", "geipan", "geipan_pipeline_records.json"),
                ("docs", "russia-ufo", "russia_ufo.json"),
                ("docs", "ukraine-uap", "ukraine_uap.json"),
                ("docs", "japan-ufo", "japan_uap.json")]:
        p = os.path.join(PROJECT_ROOT, *rel)
        if os.path.exists(p):
            reports += json.load(open(p, encoding="utf-8"))["reports"]
    return reports


def tokens(text):
    return re.findall(r"[a-z']{3,}", text.lower())


def main():
    tax, sigs, meta = load_signatures()
    reports = load_all_reports()
    print(f"Scanning {len(reports)} reports for near-misses…")

    near_texts = []           # descriptions of reports that pass Tier-1 but fire 0-1 sigs
    zero_fire = one_fire = tier1_pass = 0
    for r in reports:
        desc = r.get("description") or ""
        if len(desc) < 60:
            continue
        if not score_report_tier1(desc)["keep"]:
            continue
        tier1_pass += 1
        fired = fire_signatures(desc.lower(), sigs)
        if len(fired) == 0:
            zero_fire += 1
            near_texts.append(desc)
        elif len(fired) == 1:
            one_fire += 1
            near_texts.append(desc)

    print(f"  Tier-1 pass: {tier1_pass} | 0-fire near-miss: {zero_fire} | 1-fire near-miss: {one_fire}")
    print(f"  near-miss pool: {len(near_texts)} reports\n")

    # ---- Probe the near-misses for candidate uncovered patterns ----
    probe_hits = {name: 0 for name in PROBES}
    probe_examples = {name: [] for name in PROBES}
    for desc in near_texts:
        low = desc.lower()
        for name, terms in PROBES.items():
            if any(t in low for t in terms):
                probe_hits[name] += 1
                if len(probe_examples[name]) < 3:
                    probe_examples[name].append(desc[:180])

    # ---- Also surface raw recurring bigrams not in ALREADY_COVERED (discovery) ----
    bigrams = Counter()
    for desc in near_texts[:40000]:   # cap for speed
        ts = [t for t in tokens(desc) if t not in ALREADY_COVERED]
        for i in range(len(ts) - 1):
            bigrams[(ts[i], ts[i+1])] += 1

    ranked_probes = sorted(probe_hits.items(), key=lambda kv: kv[1], reverse=True)
    print("=" * 84)
    print("CANDIDATE UNCOVERED PATTERNS (probe family -> near-miss reports containing it)")
    print("=" * 84)
    for name, n in ranked_probes:
        pct = 100.0 * n / max(1, len(near_texts))
        print(f"  {name:<24} {n:>7} reports ({pct:.1f}% of near-misses)")

    print("\nTop recurring bigrams in near-misses (discovery, uncovered vocab):")
    for (a, b), n in bigrams.most_common(40):
        print(f"  {n:>6}  {a} {b}")

    out = {
        "tier1_pass": tier1_pass, "zero_fire": zero_fire, "one_fire": one_fire,
        "near_miss_pool": len(near_texts),
        "probe_hits": probe_hits,
        "probe_examples": probe_examples,
        "top_bigrams": [{"phrase": f"{a} {b}", "count": n} for (a, b), n in bigrams.most_common(60)],
    }
    json.dump(out, open(os.path.join(PROJECT_ROOT, "scripts", "signature_gap_report.json"), "w",
              encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\nSaved: scripts/signature_gap_report.json")


if __name__ == "__main__":
    main()
