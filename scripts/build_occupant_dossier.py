# -*- coding: utf-8 -*-
"""'The Occupant Reports' Pattern Dossier — the most contested class: reports of beings or
occupants associated with a landed or close object. Handled with maximum analytical discipline
(this is where hoax and psychology dominate) but not dismissed, because a real reporting pattern
exists. APPENDS to window.UAP_DOSSIERS.

Grounded numbers (verified from sig_meta):
  uap-et-ce-003 (occupants/beings/humanoid figures observed) 17,438
  uap-et-ce-001 (Close Encounter 1st Kind, object at close range) 80,608
  uap-et-landing-001 (object lands)                          29,456
  uap-wr-cred-002 (multiple independent differing-background witnesses) 1,403
Anchor cases (real): RU-SAMIZDAT-0099 (Voronezh/Turgay 1979), GEIPAN Mende 1998.
KNOWN = documented report; ASSESSED = inference w/ WEP. Run BEFORE generate_dossier_audio.py.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JS = os.path.join(ROOT, "src", "frontend", "uap-dossiers.js")
PTS = {"Voronezh": (51.6720, 39.1843, "RU"), "Mende": (44.5180, 3.5000, "FR")}


def load_dossiers():
    import re
    m = re.search(r"window\.UAP_DOSSIERS\s*=\s*(\{.*\});\s*$", open(DOSSIER_JS, encoding="utf-8").read(), re.S)
    if not m: raise SystemExit("run build_nuclear_sentinel_dossier.py first")
    return json.loads(m.group(1))


def pt(name, label=None):
    lat, lng, cc = PTS[name]; return {"lat": lat, "lng": lng, "label": label or name, "country": cc}


def main():
    obj = load_dossiers()
    chapters = [
        {"id": "oc-hook", "title": "The reports we treat most carefully", "visual": "stats",
         "caption": "The most contested class in the field — and the one that most needs discipline.",
         "narration": (
            "We come now to the most contested class in the entire field, and the one this platform handles with "
            "the most caution: reports of occupants — beings or figures associated with a landed or close "
            "object. This is where hoax, misperception, sleep phenomena, and cultural expectation all crowd in, "
            "and where an honest analyst has to be hardest. We do not dismiss it, because a real and persistent "
            "reporting pattern exists; but we hold it to the highest bar in the library. "
            "KNOWN: in this corpus, reports describing occupants or humanoid figures fire 17,438 times. Close "
            "encounters with an object at close range fire 80,608 times, and landings 29,456. ASSESSED, stated "
            "up front: volume is not veracity. A pattern this size tells us many people sincerely report the "
            "same kind of experience across cultures and decades — which is a fact about the reports, not proof "
            "of their content. This dossier treats occupant reports as a psychological and cultural phenomenon "
            "first, and asks, honestly, what — if anything — survives that scrutiny."),
         "visualData": {"headline_stat": 17438, "stat_label": "reports describing occupants / beings / humanoid figures (uap-et-ce-003)",
                        "sub_stats": [{"k": "Close encounter, object at range (CE-1)", "v": 80608},
                                      {"k": "Object lands (landing-001)", "v": 29456},
                                      {"k": "Multi-witness, mixed backgrounds", "v": 1403}]}},
        {"id": "oc-discipline", "title": "Why this class needs the most discipline", "visual": "corroboration",
         "caption": "Sleep paralysis, cultural scripts, and hoax cluster here more than anywhere.",
         "narration": (
            "Before any occupant report earns attention, it has to pass through the densest thicket of prosaic "
            "explanations in the field. "
            "KNOWN: sleep paralysis with hypnopompic hallucination produces vivid, terrifying 'presence in the "
            "room' experiences that the sufferer genuinely perceives as real — and it is common. KNOWN: the "
            "specific appearance of reported beings has shifted with the culture, from the tall 'Nordic' figures "
            "of the nineteen-fifties to the big-eyed 'grey' that became dominant after it saturated popular "
            "media — a strong sign of cultural scripting. KNOWN: the occupant tier is where deliberate hoaxes "
            "concentrate, because a being is a more sensational story than a light. ASSESSED, with HIGH "
            "confidence: for the great majority of occupant reports, one of these — sleep phenomena, cultural "
            "expectation, or hoax — is the most probable explanation, and the correct verdict is EXPLAINED or "
            "INSUFFICIENT. That is not cynicism; it is where the evidence points. The interesting residue is the "
            "small set that resists all three — daytime, multiple unconnected witnesses of differing "
            "backgrounds, physical traces alongside — and even those we rate no higher than the evidence allows."),
         "visualData": {"sources": [
            {"source": "Object at close range (CE-1)", "count": 80608},
            {"source": "Landing (landing-001)", "count": 29456},
            {"source": "Occupants observed (CE-3)", "count": 17438},
            {"source": "Multi-witness, mixed backgrounds", "count": 1403}]}},
        {"id": "oc-cases", "title": "The cases that resist easy dismissal", "visual": "map",
         "caption": "Daytime, multiple unconnected witnesses — the rare occupant reports that hold up better.",
         "narration": (
            "A very small number of occupant reports resist the easy explanations, and they share features worth "
            "naming. "
            "KNOWN: the 1979 case recorded in the Soviet materials — an object and figures reported near Turgay "
            "and in the wider Voronezh episode — involved military and multiple civilian witnesses and an "
            "associated landing, not a lone sleeper. KNOWN: France's official GEIPAN body holds daytime "
            "occupant reports, such as those from Mende in 1998, with multiple independent witnesses of differing "
            "backgrounds. ASSESSED, carefully: multiple unconnected daytime witnesses defeat sleep paralysis "
            "(which is solitary and nocturnal) and strain the cultural-script explanation (independent people "
            "converging on details). That raises such cases above the noise — but not to proof. ASSESSED, with "
            "MODERATE-to-LOW confidence and the caveats loud: even the best occupant cases rest on human "
            "testimony without physical corroboration, and testimony, however sincere and multiple, is the "
            "weakest evidence class we have. These are the cases worth studying, not the cases that settle "
            "anything."),
         "visualData": {"points": [pt("Voronezh", "Voronezh region, RU — 1979"),
                                    pt("Mende", "Mende, FR — 1998 (GEIPAN)")],
                        "anchor": {"title": "Voronezh / Turgay, USSR — 1979", "country": "RU", "year": "1979",
                                   "id": "RU-SAMIZDAT-0099",
                                   "text": "Object + figures reported by military + civilians, with a landing. Fires CE-3 + landing + credible-witness. Multiple witnesses, not solitary."},
                        "anchor_usovo": {"title": "Mende, France — 1998 (GEIPAN)", "country": "FR", "year": "1998",
                                   "id": "GEIPAN-1998-08-01510",
                                   "text": "Official GEIPAN daytime occupant report; multiple independent witnesses of differing backgrounds. Fires CE-3 + CE-1 + multi-witness."}}},
        {"id": "oc-ruleout", "title": "The occupant rule-out ladder", "visual": "checklist",
         "caption": "Solitary + nocturnal + culturally-scripted = explained. The bar to clear it is high.",
         "narration": (
            "The rule-out for occupant reports is the strictest in the library, and deliberately so. "
            "Was the witness alone, and was it at night or on waking? If so, sleep paralysis with hallucination "
            "is the leading explanation. Do the described beings match the dominant media image of their era? "
            "That points to cultural scripting rather than observation. Is there any independent corroboration at "
            "all — a second unconnected witness, a physical trace, an instrument? Almost never. ASSESSED: only "
            "when a report is daytime, has multiple unconnected witnesses of differing backgrounds, and ideally "
            "carries a physical trace does it clear the prosaic thicket — and even then it rests on testimony "
            "alone. The confidence ceiling for this entire class is therefore lower than any other in the "
            "library: the very best occupant case is ANOMALOUS — MODERATE, never HIGH, because human testimony "
            "without physical corroboration cannot carry a HIGH rating no matter how compelling. Stating that "
            "ceiling out loud is the most important thing this dossier does."),
         "visualData": {"play_steps": [
            {"verb": "SOLITARY/NIGHT?", "action": "Alone, at night or on waking -> sleep paralysis + hallucination.", "produces": "RULE-OUT"},
            {"verb": "CULTURAL SCRIPT?", "action": "Beings match the era's dominant media image -> scripting.", "produces": "RULE-OUT"},
            {"verb": "HOAX MARKERS?", "action": "Sole sensational source, inconsistencies, incentive.", "produces": "RULE-OUT"},
            {"verb": "INDEPENDENT?", "action": "Daytime + multiple unconnected witnesses + a physical trace?", "produces": "CONFIRM"}],
            "confidence_ladder": [
            {"wep": "ANOMALOUS — MODERATE", "when": "Daytime, multiple unconnected witnesses, ideally a trace (ceiling for this class)"},
            {"wep": "INSUFFICIENT", "when": "Testimony only; can't exclude script/hoax"},
            {"wep": "EXPLAINED", "when": "Solitary + nocturnal + era-typical beings (sleep phenomena)"}]}},
        {"id": "oc-invest", "title": "Run the investigator on an occupant case", "visual": "investigator",
         "caption": "Take the play to Voronezh 1979 or the GEIPAN Mende report.",
         "narration": (
            "Finally, test it — and notice the ceiling. Pick a real occupant record below and the investigator "
            "runs the field play: witness count and setting, whether sleep phenomena or cultural scripting fit, "
            "whether anything corroborates the testimony, and a confidence-rated verdict. You will see that even "
            "the strongest occupant cases stop at MODERATE, because the class is capped there by design — "
            "testimony without physical corroboration cannot go higher. That cap is the honest heart of this "
            "whole dossier: take the reports seriously as a phenomenon, study the best of them, and refuse to "
            "overclaim what testimony alone can bear."),
         "visualData": {"investigator": {
            "opening": "This is the class where discipline matters most. Volume is not veracity, and testimony without physical corroboration is capped at MODERATE.",
            "prosaic_checklist": ["Solitary + nocturnal (sleep paralysis / hypnopompic)", "Beings match era's media image (cultural script)",
                                   "Sole sensational source / hoax incentive", "No independent witness or trace",
                                   "Memory shaped by later media / hypnosis"]},
            "examples": [
                {"id": "RU-SAMIZDAT-0099", "source": "RU-SAMIZDAT", "country": "RU", "year": 1979,
                 "text": "Voronezh/Turgay 1979 — object + figures, military + civilian witnesses, landing."},
                {"id": "GEIPAN-1998-08-01510", "source": "GEIPAN", "country": "FR", "year": 1998,
                 "text": "Mende 1998 (GEIPAN) — daytime, multiple independent witnesses of differing backgrounds."}]}},
    ]
    total = 0
    for ch in chapters:
        w = len((ch.get("narration") or "").split()); ch["words"] = w; ch["est_seconds"] = round(w/150.0*60); total += w
    dossier = {"id": "occupant-reports", "title": "The Occupant Reports",
               "subtitle": "The most contested class — handled with maximum discipline, capped by what testimony can bear",
               "signature": "uap-et-ce-003", "firing_total": 17438, "sources": 2, "countries": 2,
               "narration_words": total, "est_runtime_min": round(total/150.0), "chapters": chapters,
               "landmark_cases": ["RU-SAMIZDAT-0099", "GEIPAN-1998-08-01510"],
               "note": ("Occupant class: CE-3=17,438; CE-1=80,608; landing-001=29,456; multi-witness cred-002=1,403. "
                        "Handled with highest discipline: sleep paralysis / cultural scripting / hoax as leading "
                        "explanations; confidence CEILING = ANOMALOUS-MODERATE (testimony w/o physical corroboration).")}
    obj.setdefault("dossiers", [])
    obj["dossiers"] = [d for d in obj["dossiers"] if d.get("id") != "occupant-reports"] + [dossier]
    with open(DOSSIER_JS, "w", encoding="utf-8") as f:
        f.write("// UAP Pattern Dossiers - documentary + play + AI investigator, grounded in the live signal.\n")
        f.write("window.UAP_DOSSIERS = " + json.dumps(obj, ensure_ascii=False) + ";\n")
    print(f"Appended 'The Occupant Reports' ({len(chapters)} ch, ~{dossier['est_runtime_min']} min, {total} words). Total: {len(obj['dossiers'])}")


if __name__ == "__main__":
    main()
