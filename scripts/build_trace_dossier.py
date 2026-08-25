# -*- coding: utf-8 -*-
"""'The Physical Trace' Pattern Dossier — the rare reports that leave something behind: landing
marks, scorched ground, physiological effects, recovered material. The evidentiary holy grail,
and the honest story of how rare and how contested it is. APPENDS to window.UAP_DOSSIERS.

Grounded numbers (verified from sig_meta):
  uap-et-landing-001 (object lands / found on ground)  29,456
  uap-et-ce-002 (Close Encounter 2nd Kind: measurable effect) 19,058
  uap-em-phys-002 (physical ground trace)                 459
  uap-em-phys-001 (physiological effect on witness)       167
  uap-em-mat-001 (physical material recovered)            211
KNOWN = documented; ASSESSED = inference w/ WEP. Run BEFORE generate_dossier_audio.py.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JS = os.path.join(ROOT, "src", "frontend", "uap-dossiers.js")


def load_dossiers():
    import re
    m = re.search(r"window\.UAP_DOSSIERS\s*=\s*(\{.*\});\s*$", open(DOSSIER_JS, encoding="utf-8").read(), re.S)
    if not m: raise SystemExit("run build_nuclear_sentinel_dossier.py first")
    return json.loads(m.group(1))


def main():
    obj = load_dossiers()
    chapters = [
        {"id": "tr-hook", "title": "The evidence that stays behind", "visual": "stats",
         "caption": "Most sightings vanish. A rare few leave a mark you can measure.",
         "narration": (
            "Almost every UAP report is gone the moment it ends — a light in the sky, a memory, a witness "
            "statement. But a small, precious fraction leaves something physical behind: a ring of flattened or "
            "scorched ground, a burn on a witness's skin, a fragment of material. This is the evidentiary holy "
            "grail, because unlike testimony, a physical trace can be taken to a laboratory. "
            "KNOWN: in this corpus, an object landing or found resting on the ground fires 29,456 times, and a "
            "close encounter leaving a measurable physical effect — a Close Encounter of the Second Kind — fires "
            "19,058 times. But the truly hard evidence is far rarer: physical ground traces fire just 459 times, "
            "physiological effects on witnesses 167, and recovered material only 211. ASSESSED, and this is the "
            "honest headline: the physical-trace class is simultaneously the most valuable and the thinnest. "
            "When it exists it can be tested; but it almost never exists, and when material is claimed, the "
            "chain of custody is usually broken. This dossier is about that tension — the highest-value, "
            "lowest-availability evidence in the field."),
         "visualData": {"headline_stat": 29456, "stat_label": "reports where an object lands or is found on the ground (uap-et-landing-001)",
                        "sub_stats": [{"k": "Measurable effect (CE-2)", "v": 19058},
                                      {"k": "Ground trace (phys-002)", "v": 459},
                                      {"k": "Recovered material (mat-001)", "v": 211}]}},
        {"id": "tr-ladder", "title": "The evidence ladder — testimony to material", "visual": "corroboration",
         "caption": "As the evidence gets harder, the number of cases collapses. That is the story.",
         "narration": (
            "Lay the signatures side by side and a pattern jumps out — as the evidence gets physically harder, "
            "the case count collapses. "
            "KNOWN: landings and close encounters number in the tens of thousands. Measurable second-kind "
            "effects, nineteen thousand. But ground traces drop to a few hundred, physiological effects to under "
            "two hundred, recovered material to a couple hundred. ASSESSED: that collapse is itself informative. "
            "It tells you that dramatic, testable physical evidence is genuinely rare — not suppressed into "
            "nonexistence, but simply uncommon, and almost always poorly documented when it appears. ASSESSED, "
            "with MODERATE confidence: the honest reading is that the field is evidence-poor exactly where it "
            "most needs to be evidence-rich. Any single 'recovered material' claim deserves deep skepticism and "
            "a demand for chain of custody and independent lab analysis — because that is precisely the tier "
            "where hoaxes and honest mistakes concentrate, and where extraordinary claims most need "
            "extraordinary documentation."),
         "visualData": {"sources": [
            {"source": "Landing / on ground (landing-001)", "count": 29456},
            {"source": "Measurable effect (CE-2)", "count": 19058},
            {"source": "Ground trace (phys-002)", "count": 459},
            {"source": "Recovered material (mat-001)", "count": 211},
            {"source": "Physiological effect (phys-001)", "count": 167}]}},
        {"id": "tr-ruleout", "title": "How to test a trace honestly", "visual": "checklist",
         "caption": "Provenance, chain of custody, independent labs, and known isotope ratios.",
         "narration": (
            "A physical trace is only as good as its handling, so the rule-out here is a laboratory discipline, "
            "not a field one. "
            "First, provenance: can the sample be tied to the event, or did it appear afterward? Second, chain "
            "of custody: has it been controlled and documented from collection to analysis, or passed through "
            "many hands? Third, independent analysis: has more than one accredited lab examined it blind? "
            "Fourth, the isotope test: extraordinary 'not from Earth' claims must be checked against known "
            "terrestrial isotope ratios — most famous samples turn out to be ordinary industrial slag or metal "
            "with perfectly terrestrial ratios. ASSESSED, stated plainly: the vast majority of recovered-material "
            "claims fail one of these tests, usually chain of custody. That is not a cover-up; it is what "
            "happens when dramatic material is collected by untrained people in uncontrolled conditions. "
            "ASSESSED: a trace with clean provenance, documented custody, and independent labs finding anomalous "
            "isotopes would be ANOMALOUS — HIGH and genuinely important. Almost none clear that bar — and saying "
            "so is the point of an honest tool."),
         "visualData": {"play_steps": [
            {"verb": "PROVENANCE", "action": "Is the sample tied to the event, or did it appear after?", "produces": "RULE-OUT"},
            {"verb": "CUSTODY", "action": "Documented control from collection to lab, or many hands?", "produces": "RULE-OUT"},
            {"verb": "INDEPENDENT LABS", "action": "More than one accredited lab, examined blind?", "produces": "CONFIRM"},
            {"verb": "ISOTOPES", "action": "Check vs known terrestrial ratios — most 'exotic' metal is ordinary slag.", "produces": "RULE-OUT"}],
            "confidence_ladder": [
            {"wep": "ANOMALOUS — HIGH", "when": "Clean provenance + custody + independent labs find anomalous isotopes"},
            {"wep": "ANOMALOUS — MODERATE", "when": "Documented ground trace (soil/plant change) with photos + samples"},
            {"wep": "INSUFFICIENT", "when": "Material with broken custody or unremarkable composition"}]}},
        {"id": "tr-invest", "title": "Run the investigator on a landing / trace case", "visual": "investigator",
         "caption": "Take the play to a real landing or physical-effect record.",
         "narration": (
            "Now test it. Choose a real landing or physical-effect record below and the investigator runs the "
            "field play — the physical claim, whether it was instrumented or lab-tested, whether custody and "
            "provenance hold, and a confidence-rated verdict with the collection gaps. Watch how landing reports "
            "that lack a preserved, tested sample land at MODERATE at best: the event may be real, but without "
            "the material in a lab there is nothing to raise it further. The tool is built to want the sample — "
            "and to say so when it is missing."),
         "visualData": {"investigator": {
            "opening": "A trace you can put in a lab beats a thousand sightings. But it must have provenance, custody, and independent analysis — or it proves nothing.",
            "prosaic_checklist": ["Sample appeared after the event (no provenance)", "Broken chain of custody",
                                   "Single lab / not blind", "Ordinary industrial slag or metal (terrestrial isotopes)",
                                   "Ground 'trace' from ordinary causes (fungus ring, machinery, drought)"]},
            "examples": [
                {"id": "JP-SEED-jal1628-1986", "source": "JP-SEED", "country": "US", "year": 1986,
                 "text": "JAL 1628 — fires CE-2 (measurable effect) + landing signatures; test how a well-witnessed but trace-free case scores."},
                {"id": "RU-SAMIZDAT-0099", "source": "RU-SAMIZDAT", "country": "RU", "year": 1979,
                 "text": "Turgay/Voronezh 1979 — fires landing + close-encounter + credible-witness signatures."}]}},
    ]
    total = 0
    for ch in chapters:
        w = len((ch.get("narration") or "").split()); ch["words"] = w; ch["est_seconds"] = round(w/150.0*60); total += w
    dossier = {"id": "physical-trace", "title": "The Physical Trace",
               "subtitle": "Landings, ground marks, and recovered material — the rarest, most testable evidence",
               "signature": "uap-et-landing-001", "firing_total": 29456, "sources": 2, "countries": 2,
               "narration_words": total, "est_runtime_min": round(total/150.0), "chapters": chapters,
               "landmark_cases": ["JP-SEED-jal1628-1986", "RU-SAMIZDAT-0099"],
               "note": ("Physical-trace class: landing-001=29,456; CE-2=19,058; ground-trace phys-002=459; "
                        "recovered-material mat-001=211; physiological phys-001=167. Honest theme: highest-value, "
                        "lowest-availability evidence; lab discipline (provenance/custody/isotopes) is the rule-out.")}
    obj.setdefault("dossiers", [])
    obj["dossiers"] = [d for d in obj["dossiers"] if d.get("id") != "physical-trace"] + [dossier]
    with open(DOSSIER_JS, "w", encoding="utf-8") as f:
        f.write("// UAP Pattern Dossiers - documentary + play + AI investigator, grounded in the live signal.\n")
        f.write("window.UAP_DOSSIERS = " + json.dumps(obj, ensure_ascii=False) + ";\n")
    print(f"Appended 'The Physical Trace' ({len(chapters)} ch, ~{dossier['est_runtime_min']} min, {total} words). Total: {len(obj['dossiers'])}")


if __name__ == "__main__":
    main()
