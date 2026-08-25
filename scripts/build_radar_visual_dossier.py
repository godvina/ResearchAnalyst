# -*- coding: utf-8 -*-
"""Build the 'Radar-Visual Pilot Encounter' Pattern Dossier — the cases where a trained aerial
observer sees something AND an instrument records it. The highest-evidence class in the corpus.
APPENDS to window.UAP_DOSSIERS (keeps existing dossiers).

Grounded numbers (verified from src/frontend/uap-command-data.js sig_meta):
  uap-em-rv-001 (object confirmed on radar)                fires 8,136 reports
  uap-em-rv-002 (aircraft paced/escorted by object)        fires 27,125 reports
  uap-em-rv-003 (ground/military radar tracks unknown)     fires 7,253 reports
  uap-wr-cred-001 (primary witness is trained observer)    fires 12,632 reports
Anchor cases (real, in uap-case-store.js):
  JP-SEED-jal1628-1986   — JAL flight 1628 over Alaska, 1986 (radar + crew)
  CL-CEFAA-helicopter-2014 — Chilean Navy helicopter IR footage, 2014 (em-rv-001/002)
  BE-SOBEPS-1990-f16     — Belgian F-16 radar intercept, 1990

Documentary voice, Nova-neutral. KNOWN vs ASSESSED w/ WEP.
Run BEFORE generate_dossier_audio.py.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JS = os.path.join(ROOT, "src", "frontend", "uap-dossiers.js")

PTS = {
    "Anchorage":     (61.1743, -149.9963, "US"),
    "Santiago":      (-33.4489, -71.0000, "CL"),
    "Petit-Rechain": (50.6167, 5.8667, "BE"),
    "Nimitz":        (32.6, -119.5, "US"),   # off Southern California (2004 Nimitz encounter area)
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
            "id": "rv-hook", "title": "When the instrument agrees with the eye", "visual": "stats",
            "caption": "A trained observer sees it. A sensor records it. That is the strongest class of case.",
            "narration": (
                "Most UAP reports rest on a single human eye, and a single eye can be honestly wrong. But there "
                "is a class of case that rises above the rest — the radar-visual encounter, where a trained "
                "aerial observer sees an object and, at the same moment, an instrument independently records it. "
                "When the eye and the sensor agree, the two most common failure modes of UAP data — "
                "misperception and hoax — both get much harder. "
                "KNOWN: in this corpus, an object confirmed on radar fires 8,136 times; an aircraft being paced "
                "or escorted by an unknown object fires 27,125 times; ground or military radar tracking an "
                "unknown fires 7,253 times; and a trained aerial observer as the primary witness fires 12,632 "
                "times. ASSESSED, with HIGH confidence: this is the evidentiary top of the pyramid. It is also "
                "the class most cited in official assessments, because it is the class that governments can "
                "least easily dismiss. This dossier walks the strongest of these encounters, honestly."),
            "visualData": {"headline_stat": 27125, "stat_label": "reports where an aircraft is paced/escorted by an unknown object (uap-em-rv-002)",
                           "sub_stats": [{"k": "Object confirmed on radar (rv-001)", "v": 8136},
                                         {"k": "Ground/military radar track (rv-003)", "v": 7253},
                                         {"k": "Trained observer as witness (wr-cred)", "v": 12632}]},
        },
        {
            "id": "rv-why", "title": "Why radar-visual outranks everything else", "visual": "corroboration",
            "caption": "Two independent collection channels agreeing on one object.",
            "narration": (
                "To see why this class matters, think in terms of collection channels. A visual report is one "
                "channel — the human eye. A radar or infrared return is a second, physically independent "
                "channel — it does not care what the witness expected to see. When both channels register the "
                "same object, in the same place, at the same time, you have crossed from testimony into "
                "corroborated observation. "
                "KNOWN: the strongest cases stack even more channels — a visual sighting, an airborne radar "
                "lock, a separate ground-radar track, and sometimes infrared video, all on one target. Each "
                "added channel multiplies the difficulty of a mundane explanation. ASSESSED, with HIGH "
                "confidence: a single misperception cannot fool a radar; a radar glitch cannot look like a "
                "structured craft to a pilot; a hoax cannot easily forge four systems at once. This is the "
                "multi-vector logic the whole platform is built on — and radar-visual cases are where the UAP "
                "corpus comes closest to satisfying it."),
            "visualData": {"sources": [
                {"source": "Aircraft paced by object (rv-002)", "count": 27125},
                {"source": "Trained observer (wr-cred-001)", "count": 12632},
                {"source": "Object confirmed on radar (rv-001)", "count": 8136},
                {"source": "Ground/military radar (rv-003)", "count": 7253},
            ]},
        },
        {
            "id": "rv-jal", "title": "JAL 1628 — the cargo jet over Alaska", "visual": "map",
            "caption": "17 November 1986: a Japan Airlines crew and radar track objects for ~50 minutes.",
            "narration": (
                "The classic radar-visual case, and the one that anchors this dossier, is Japan Airlines flight "
                "1628. "
                "KNOWN: on the 17th of November 1986, a JAL cargo 747 flying over Alaska, near Anchorage, "
                "reported being paced for roughly fifty minutes by unidentified objects — first two smaller "
                "craft, then a very large one the captain described as enormous. KNOWN: the crew were "
                "professional aircrew, and both the aircraft and, at points, ground radar at Anchorage centre "
                "reported returns in the vicinity. The Federal Aviation Administration investigated; a senior "
                "FAA official held a press conference and released the case files. "
                "ASSESSED, and stated with balance: the radar picture was genuinely ambiguous — some returns "
                "were later argued to be weather or split radar targets, and the giant object was never "
                "unambiguously locked on radar. But the core is strong: a credible professional crew, a "
                "prolonged encounter, an official investigation, and at least partial instrumented "
                "corroboration. Under our field play this is an ANOMALOUS — MODERATE-to-HIGH case: not "
                "explained, well-witnessed, partially instrumented. It is a model of the class."),
            "visualData": {"points": [pt("Anchorage", "JAL 1628 — near Anchorage, Alaska, 1986")],
                           "anchor": {"title": "JAL flight 1628 — Alaska, 17 Nov 1986", "country": "US", "year": "1986",
                                      "id": "JP-SEED-jal1628-1986",
                                      "text": "JAL cargo 747 paced ~50 min by unknown objects near Anchorage; professional crew; FAA investigation; partial radar corroboration. Fires formation + em-rv-002 + close-encounter signatures."}},
        },
        {
            "id": "rv-chile", "title": "The Chilean Navy footage — instrument first", "visual": "map",
            "caption": "2014: a Navy helicopter's IR camera films an object that vents a plume, in front of witnesses.",
            "narration": (
                "Where JAL 1628 started with the eye, the Chilean Navy case started with the instrument. "
                "KNOWN: in November 2014, the crew of a Chilean Navy helicopter off the coast near Santiago "
                "filmed an unidentified object for about nine minutes on a forward-looking infrared camera, "
                "while in contact with two ground radar stations that could not identify it and confirmed no "
                "known traffic in the area. KNOWN: the footage shows the object apparently venting a plume or "
                "discharge twice. KNOWN: the case was investigated by Chile's official government UAP body, the "
                "CEFAA, which studied it for two years with a technical committee before releasing it publicly. "
                "ASSESSED: skeptical analysts have argued the object is a distant aircraft with its contrail "
                "flattened by the infrared optics — a serious, non-trivial explanation that this dossier will "
                "not wave away. But the case remains a strong template regardless: professional operators, an "
                "instrument as the primary sensor, negative radar identification, and a formal government "
                "investigation. That is the procedure working, whatever the final answer."),
            "visualData": {"points": [pt("Santiago", "Chilean Navy IR encounter — off Santiago, 2014")],
                           "anchor": {"title": "Chilean Navy (CEFAA) IR footage — 2014", "country": "CL", "year": "2014",
                                      "id": "CL-CEFAA-helicopter-2014",
                                      "text": "Navy helicopter FLIR films unidentified object ~9 min; 2 ground radars cannot ID; object appears to vent plume; CEFAA 2-year investigation. Fires em-rv-001 + em-rv-002."},
                           "anchor_usovo": {"title": "Belgian F-16 radar intercept — 1990", "country": "BE", "year": "1990",
                                      "id": "BE-SOBEPS-1990-f16",
                                      "text": "For contrast: airborne F-16 radar locks on targets that reportedly break lock with sharp accelerations. Fires em-rv-001/002/003."}},
        },
        {
            "id": "rv-ruleout", "title": "What radar-visual must survive", "visual": "checklist",
            "caption": "Radar angels, temperature inversions, IR parallax, and split targets.",
            "narration": (
                "Instruments are harder to fool than eyes, but they are not infallible, and an honest analyst "
                "attacks the sensor as hard as the witness. Radar can produce 'angels' — returns from birds, "
                "insects, or clear-air turbulence. A temperature inversion can bend both radar and light, "
                "putting a distant object where it is not, or mirroring a real one. Infrared cameras compress "
                "depth, so a far-off jet and its contrail can read as a strange nearby object — the core of the "
                "skeptical case against the Chilean footage. Ground and air radar can also 'split' a single "
                "return into phantom extras. "
                "ASSESSED: the way through is convergence. A case where the visual, the airborne radar, and a "
                "separate ground radar all independently agree is very hard to explain with any single sensor "
                "artefact, because each artefact afflicts one channel, not all at once. So the correct verdict "
                "scales with the number of independent channels that agree: one channel is INSUFFICIENT; a "
                "credible visual plus one instrument is ANOMALOUS — MODERATE; a visual plus two independent "
                "instrumented tracks, with no prosaic fit, is ANOMALOUS — HIGH. The instruments do not prove "
                "the exotic; they raise the floor of what must be explained."),
            "visualData": {"play_steps": [
                {"verb": "RADAR ANGELS", "action": "Birds/insects/clear-air returns — check for a coincident visual + persistence.", "produces": "RULE-OUT"},
                {"verb": "INVERSION", "action": "Temperature layer bends radar + light — check atmospheric profile.", "produces": "RULE-OUT"},
                {"verb": "IR PARALLAX", "action": "Infrared flattens depth; distant jet + contrail can mimic an object (Chile debate).", "produces": "RULE-OUT"},
                {"verb": "SPLIT TARGET", "action": "One return read as several — cross-check independent radar heads.", "produces": "RULE-OUT"},
                {"verb": "CONVERGE", "action": "Visual + airborne radar + ground radar agreeing defeats single-sensor artefacts.", "produces": "CONFIRM"},
            ], "confidence_ladder": [
                {"wep": "ANOMALOUS — HIGH", "when": "Visual + 2 independent instrumented tracks, no prosaic fit"},
                {"wep": "ANOMALOUS — MODERATE", "when": "Credible visual + one instrument (JAL 1628, Chile)"},
                {"wep": "INSUFFICIENT", "when": "Single channel, or a live prosaic explanation on the table"},
            ]},
        },
        {
            "id": "rv-invest", "title": "Run the investigator on a radar-visual case", "visual": "investigator",
            "caption": "Take the play to JAL 1628, the Chilean footage, or the Belgian F-16.",
            "narration": (
                "Now put it to work. Pick one of the real radar-visual records below and the investigator runs "
                "the field play against that exact case — testing the witness quality, the instrumented "
                "corroboration, and whether a sensor artefact or prosaic cause is on the table, then closing on "
                "a confidence-rated verdict with the collection gaps that would raise it. "
                "Notice how these cases behave: strong on witness and corroboration, but almost always carrying "
                "a live prosaic counter-argument that keeps the honest verdict at MODERATE rather than HIGH. "
                "That restraint is the feature, not the bug. The strongest thing this tool can do is tell you "
                "when the evidence is good but not yet conclusive."),
            "visualData": {"investigator": {
                "opening": "The eye can be fooled and so can one sensor. Two independent instruments agreeing is what moves the needle.",
                "prosaic_checklist": ["Radar angels (birds/insects/clear air)", "Temperature inversion bending radar+light",
                                       "Infrared parallax (distant jet + contrail)", "Split/phantom radar target",
                                       "Ordinary aircraft misjudged for range/size"]},
                "examples": [
                    {"id": "JP-SEED-jal1628-1986", "source": "JP-SEED", "country": "US", "year": 1986,
                     "text": "JAL 1628 over Alaska — cargo 747 crew + radar, ~50 min encounter, FAA investigation."},
                    {"id": "CL-CEFAA-helicopter-2014", "source": "CL-CEFAA", "country": "CL", "year": 2014,
                     "text": "Chilean Navy helicopter FLIR footage; 2 radars cannot ID; CEFAA 2-year study."},
                    {"id": "BE-SOBEPS-1990-f16", "source": "BE-SOBEPS", "country": "BE", "year": 1990,
                     "text": "Belgian F-16 radar intercept — airborne locks that reportedly break with sharp accelerations."},
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
        "id": "radar-visual",
        "title": "The Radar-Visual Encounter",
        "subtitle": "When a trained observer and an instrument record the same object — the highest-evidence class",
        "signature": "uap-em-rv-002",
        "firing_total": 27125,
        "sources": 3,
        "countries": 3,
        "narration_words": total,
        "est_runtime_min": round(total / 150.0),
        "chapters": chapters,
        "landmark_cases": ["JP-SEED-jal1628-1986", "CL-CEFAA-helicopter-2014", "BE-SOBEPS-1990-f16"],
        "note": ("Radar-visual class: em-rv-001=8,136; em-rv-002=27,125; em-rv-003=7,253; wr-cred-001=12,632. "
                 "KNOWN documented; ASSESSED w/ WEP; skeptical explanations stated (IR parallax for Chile, "
                 "split radar for JAL). Anchors JAL 1628 (1986), Chilean Navy CEFAA (2014), Belgian F-16 (1990)."),
    }

    obj.setdefault("dossiers", [])
    obj["dossiers"] = [d for d in obj["dossiers"] if d.get("id") != "radar-visual"] + [dossier]

    with open(DOSSIER_JS, "w", encoding="utf-8") as f:
        f.write("// UAP Pattern Dossiers - documentary + play + AI investigator, grounded in the live signal.\n")
        f.write("window.UAP_DOSSIERS = " + json.dumps(obj, ensure_ascii=False) + ";\n")
    print(f"Appended dossier 'The Radar-Visual Encounter' ({len(chapters)} chapters, ~{dossier['est_runtime_min']} min, "
          f"{total} words). Total dossiers now: {len(obj['dossiers'])}")


if __name__ == "__main__":
    main()
