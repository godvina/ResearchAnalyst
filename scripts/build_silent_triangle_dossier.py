# -*- coding: utf-8 -*-
"""Build the 'Silent Triangle' Pattern Dossier — the large, silent, low-and-slow triangular
craft, one of the most consistent morphologies in the corpus. APPENDS to window.UAP_DOSSIERS
(keeps Nuclear Sentinel + Boyne Valley).

Grounded numbers (from src/frontend/uap-command-data.js sig_meta, verified):
  uap-cm-tri-001 (large silent triangle, 3 vertex lights) fires 58,027 reports
  uap-cm-tri-002 (matte black triangle, no nav lights)   fires 57,950 reports
  uap-cm-formation-001 (formation/fleet)                 fires 112,030 reports
Anchor cases (real, in uap-case-store.js):
  BE-SOBEPS-1990-eupen  — Belgian wave, Eupen 1989 (fires tri-001 + formation)
  BE-SOBEPS-1990-f16    — Belgian wave, Petit-Rechain / F-16 intercept 1990

Documentary voice, Nova-neutral. KNOWN = documented; ASSESSED = inference w/ WEP.
Run BEFORE generate_dossier_audio.py.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JS = os.path.join(ROOT, "src", "frontend", "uap-dossiers.js")

PTS = {
    "Eupen":         (50.6280, 6.0378, "BE"),
    "Petit-Rechain": (50.6167, 5.8667, "BE"),
    "Phoenix":       (33.4484, -112.0740, "US"),
    "Lubbock":       (33.5779, -101.8552, "US"),
}


def load_dossiers():
    import re
    txt = open(DOSSIER_JS, encoding="utf-8").read()
    m = re.search(r"window\.UAP_DOSSIERS\s*=\s*(\{.*\});\s*$", txt, re.S)
    if not m:
        raise SystemExit("uap-dossiers.js not in expected shape; run build_nuclear_sentinel_dossier.py first")
    return json.loads(m.group(1))


def pt(name, label=None):
    lat, lng, cc = PTS[name]
    return {"lat": lat, "lng": lng, "label": label or name, "country": cc}


def main():
    obj = load_dossiers()

    chapters = [
        {
            "id": "st-hook", "title": "The thing that should not be able to fly", "visual": "stats",
            "caption": "Bigger than a jetliner. Silent. Hanging still in the air.",
            "narration": (
                "There is one shape that comes back, again and again, in reports from people who otherwise "
                "have nothing in common — no shared country, decade, or language. A triangle. Not a distant "
                "light: a solid, structured object, often described as larger than a commercial airliner, with "
                "a light at each of its three corners, moving slowly or hanging completely still, and — the "
                "detail witnesses fix on — making no sound at all. "
                "KNOWN: in this corpus of over three hundred thousand reports, the large-silent-triangle "
                "signature fires 58,027 times, and a closely related matte-black-triangle signature fires "
                "another 57,950. That is not a fringe of the data. It is one of its largest single structures. "
                "ASSESSED: the consistency is the interesting part. A silent object the size of a building, "
                "holding a dead hover, is hard to reconcile with conventional lift and propulsion — which is "
                "exactly why the triangle sits at the centre of the modern debate. This dossier walks the "
                "pattern honestly: what recurs, where it is strongest, the two cases that anchor it, and the "
                "prosaic explanations it must survive."),
            "visualData": {"headline_stat": 58027, "stat_label": "reports fire the large silent-triangle signature (uap-cm-tri-001)",
                           "sub_stats": [{"k": "Matte black-triangle (tri-002)", "v": 57950},
                                         {"k": "Formation / fleet signature", "v": 112030},
                                         {"k": "Severity rating", "v": "HIGH"}]},
        },
        {
            "id": "st-shape", "title": "Anatomy of the pattern", "visual": "corroboration",
            "caption": "How the triangle-family signatures fire across the corpus.",
            "narration": (
                "What turns a shape into a signature is the cluster of features that keep arriving together. "
                "KNOWN, from the signature definition and the reports that fire it: a triangular or delta "
                "outline; a distinct light at each of the three vertices; near-total silence; slow drift or a "
                "motionless hover; and an estimated size larger than a commercial aircraft. "
                "A second, darker variant adds its own tell: a matte-black body that blots out the stars "
                "behind it, showing none of the red-and-green navigation lights or anti-collision strobes that "
                "aviation law requires of every real aircraft. "
                "ASSESSED, with HIGH confidence for the co-occurrence and MODERATE for the cause: when several "
                "of these features appear in one account, prosaic explanations get harder. A blimp is silent "
                "but cannot hover crisply against wind; a formation of aircraft is not one solid body that "
                "occludes stars; a drone is not the size of an airliner. The signature is built to reward the "
                "combination, not any single trait — because any one trait alone is easy to explain away."),
            "visualData": {"sources": [
                {"source": "Large silent-triangle (tri-001)", "count": 58027},
                {"source": "Matte black-triangle (tri-002)", "count": 57950},
                {"source": "Formation / fleet (formation-001)", "count": 112030},
                {"source": "Radar-confirmed (em-rv-001)", "count": 8136},
                {"source": "Official response (ir-off-001)", "count": 3545},
            ]},
        },
        {
            "id": "st-belgium", "title": "The Belgian Wave — the best-documented case", "visual": "map",
            "caption": "1989–90: thousands of reports, a national police log, and an F-16 scramble.",
            "narration": (
                "If the triangle has a flagship case, it is the Belgian wave of 1989 and 1990 — and it anchors "
                "this dossier because it is unusually well documented. "
                "KNOWN: beginning in November 1989 around Eupen, near the German border, Belgian gendarmes and "
                "hundreds of civilians reported large triangular craft with corner lights moving slowly and "
                "silently at low altitude. The reports were logged by police, not just enthusiasts. KNOWN: the "
                "civilian study group SOBEPS investigated systematically, and in March 1990 the Belgian Air "
                "Force scrambled two F-16 interceptors after ground and air radar reported unknown targets. "
                "KNOWN: the pilots reported radar locks that broke, with targets showing accelerations that "
                "the recorded data could not cleanly resolve. "
                "ASSESSED: the Belgian wave is not proof of anything exotic — some radar returns were later "
                "argued to be atmospheric, and the single most famous photograph is now widely regarded as a "
                "hoax. But strip away the disputed image and a hard core remains: many independent witnesses, "
                "an official military response, and instrumented radar involvement, all around one recurring "
                "shape. That combination — the multiplicity, the officials, the sensors — is why it remains "
                "the reference case for the triangle."),
            "visualData": {"points": [pt("Eupen", "Eupen, BE — 1989 triangle reports"),
                                       pt("Petit-Rechain", "Petit-Rechain, BE — 1990 F-16 intercept")],
                           "anchor": {"title": "Belgian wave — Eupen 1989", "country": "BE", "year": "1989",
                                      "id": "BE-SOBEPS-1990-eupen",
                                      "text": "Gendarme + civilian triangle reports around Eupen; fires uap-cm-tri-001 + formation. Investigated by SOBEPS."},
                           "anchor_usovo": {"title": "Belgian wave — F-16 intercept 1990", "country": "BE", "year": "1990",
                                      "id": "BE-SOBEPS-1990-f16",
                                      "text": "March 1990 Belgian Air Force F-16 scramble; ground + airborne radar targets; radar locks reportedly broken. Fires em-rv-001/002/003 + formation."}},
        },
        {
            "id": "st-phoenix", "title": "The Phoenix Lights — a nation looks up", "visual": "timeline",
            "caption": "13 March 1997: thousands across Arizona see a silent V pass overhead.",
            "narration": (
                "Eight years later, on the evening of the 13th of March 1997, the pattern played out over a "
                "major American city. "
                "KNOWN: thousands of people across Arizona, from Henderson through Phoenix and down toward "
                "Tucson, reported a large, silent, V-shaped or triangular formation of lights passing slowly "
                "overhead. Witnesses included the state's then-Governor, Fife Symington, who years later said "
                "publicly he had seen it himself and considered it unexplained. "
                "KNOWN, and reported here honestly: two things happened that night. A slow-moving formation "
                "was seen earlier in the evening; and a separate, later set of lights over the Phoenix area was "
                "subsequently attributed by the military to flares dropped during an exercise at the Barry "
                "Goldwater Range. ASSESSED: the flare explanation plausibly covers the later, stationary lights "
                "— but many witnesses maintain it does not fit the earlier, structured object that moved in "
                "formation across the sky. We hold both: a documented prosaic cause for part of the night, and "
                "a residual, credibly-witnessed triangle for the rest. That is the honest shape of the Phoenix "
                "Lights."),
            "visualData": {"anchor": {"title": "Phoenix Lights — Arizona, 13 March 1997", "country": "US", "year": "1997",
                                      "text": "Mass silent V/triangle formation across Arizona; later stationary lights attributed to military flares; earlier structured object remains disputed."},
                           "timeline": [
                               {"year": 1951, "label": "Lubbock Lights (TX) — early photographed V-formation"},
                               {"year": 1989, "label": "Belgian wave begins (Eupen) — triangle reports"},
                               {"year": 1990, "label": "Belgian F-16 intercept; radar involvement"},
                               {"year": 1997, "label": "Phoenix Lights — mass silent formation over Arizona"},
                               {"year": 2021, "label": "ODNI UAP report — shape/behaviour reports formalised"},
                           ]},
        },
        {
            "id": "st-ruleout", "title": "What the triangle must survive", "visual": "checklist",
            "caption": "Blimps, drones, aircraft formations, and one honest photo-hoax.",
            "narration": (
                "A good pattern is defined as much by what it excludes as by what it includes, so here are the "
                "prosaic causes the triangle has to survive — and where each one bites. "
                "A blimp or airship is large and can be quiet, but it drifts with the wind and cannot hold a "
                "crisp hover or make sharp turns. A formation of conventional aircraft can look triangular from "
                "below, but it is several bodies with regulation navigation lights and engine noise, not one "
                "silent solid that blots out the stars. Modern drones are silent and can hover, but not at the "
                "size of an airliner. Stealth aircraft like the B-2 are large and dark, but they are not silent "
                "at low level and do not hover. And in the Belgian case specifically, the most-circulated "
                "photograph is now widely judged a hoax. "
                "ASSESSED: none of these individually explains the full triangle signature — the combination of "
                "great size, true silence, dead hover, and star-occlusion. But absence of a prosaic match is "
                "not presence of the exotic. The correct verdict for most single triangle reports is ANOMALOUS "
                "— MODERATE at best: consistent with the pattern, short of proof. The cases that climb higher "
                "are the ones like Belgium, where multiplicity and instruments back the shape."),
            "visualData": {"play_steps": [
                {"verb": "BLIMP/AIRSHIP", "action": "Large + quiet, but drifts with wind; no crisp hover or sharp turn.", "produces": "RULE-OUT"},
                {"verb": "AIRCRAFT FORMATION", "action": "Several bodies with nav lights + engine noise; not one silent solid.", "produces": "RULE-OUT"},
                {"verb": "DRONE", "action": "Silent + hovers, but not airliner-sized.", "produces": "RULE-OUT"},
                {"verb": "STEALTH (B-2)", "action": "Large + dark, but audible at low level; does not hover.", "produces": "RULE-OUT"},
                {"verb": "PHOTO-HOAX", "action": "The famous Petit-Rechain photo is widely judged fake — set it aside; the witness+radar core remains.", "produces": "RULE-OUT"},
            ], "confidence_ladder": [
                {"wep": "ANOMALOUS — HIGH", "when": "Multiplicity + radar/official response (e.g. Belgian wave core)"},
                {"wep": "ANOMALOUS — MODERATE", "when": "Full shape reported by a credible witness, no instruments"},
                {"wep": "INSUFFICIENT", "when": "Single distant light, few features, night-only"},
            ]},
        },
        {
            "id": "st-invest", "title": "Run the investigator on a triangle case", "visual": "investigator",
            "caption": "Take the play to a real firing record and see the verdict.",
            "narration": (
                "You have the pattern; now test it the way an analyst would. Pick one of the real triangle "
                "cases below and the investigator runs the field play against that exact record — checking the "
                "shape and feature-cluster, whether there is corroboration or instrumentation, whether a "
                "prosaic cause is stated, and it ends on a confidence-rated verdict with the collection gaps "
                "that would raise it. "
                "Watch how the Belgian wave, with its official response and radar involvement, behaves "
                "differently from a lone night-time light. Same procedure, honestly applied, different result — "
                "which is the whole point. The tool is not here to believe; it is here to sort."),
            "visualData": {"investigator": {
                "opening": "A triangle is a strong shape and a weak proof. Corroboration and instruments are what move it.",
                "prosaic_checklist": ["Blimp / airship drifting with wind", "Aircraft formation with nav lights",
                                       "Large drone", "Stealth aircraft at altitude", "Hoaxed photograph"]},
                "examples": [
                    {"id": "BE-SOBEPS-1990-eupen", "source": "BE-SOBEPS", "country": "BE", "year": 1989,
                     "text": "Belgian wave — Eupen triangle reports (gendarme + civilian), fires tri-001 + formation."},
                    {"id": "BE-SOBEPS-1990-f16", "source": "BE-SOBEPS", "country": "BE", "year": 1990,
                     "text": "Belgian wave — F-16 intercept, ground + air radar targets."},
                ]},
        },
    ]

    total = 0
    for ch in chapters:
        w = len((ch.get("narration") or "").split())
        ch["words"] = w
        ch["est_seconds"] = round(w / 150.0 * 60)
        total += w

    dossier = {
        "id": "silent-triangle",
        "title": "The Silent Triangle",
        "subtitle": "The large, silent, low-and-slow triangular craft — the corpus's most consistent shape",
        "signature": "uap-cm-tri-001",
        "firing_total": 58027,
        "sources": 2,
        "countries": 2,
        "narration_words": total,
        "est_runtime_min": round(total / 150.0),
        "chapters": chapters,
        "landmark_cases": ["BE-SOBEPS-1990-eupen", "BE-SOBEPS-1990-f16"],
        "note": ("The triangle morphology (uap-cm-tri-001 = 58,027 fires; tri-002 = 57,950; formation = "
                 "112,030). KNOWN documented; ASSESSED w/ WEP. Anchors: Belgian wave (Eupen 1989, F-16 1990) "
                 "+ Phoenix Lights 1997 (flare caveat stated honestly)."),
    }

    obj.setdefault("dossiers", [])
    obj["dossiers"] = [d for d in obj["dossiers"] if d.get("id") != "silent-triangle"] + [dossier]

    with open(DOSSIER_JS, "w", encoding="utf-8") as f:
        f.write("// UAP Pattern Dossiers - documentary + play + AI investigator, grounded in the live signal.\n")
        f.write("window.UAP_DOSSIERS = " + json.dumps(obj, ensure_ascii=False) + ";\n")
    print(f"Appended dossier 'The Silent Triangle' ({len(chapters)} chapters, ~{dossier['est_runtime_min']} min, "
          f"{total} words). Total dossiers now: {len(obj['dossiers'])}")


if __name__ == "__main__":
    main()
