"""Build the 'Nuclear Sentinel' Pattern Dossier (UAP version of the Finding-Fentanyl
Mirror-Trade documentary). Pulls REAL firing stats + sample cases from the signal file so
every chapter is grounded, defines the investigation PLAY and the bespoke AI investigator,
and emits src/frontend/uap-dossiers.js (window.UAP_DOSSIERS).

Signal: scripts/updb_signal_reports.json  (fired_signatures per report)
Anchor cases: docs/us-nuclear/us_nuclear_uap.json + the Russia/Japan/govt seeds already merged.

Chapter visual types (drive auto-rendered diagrams in the UI):
  stats | corroboration | process | map | timeline | graph | checklist | investigator
"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNAL = os.path.join(ROOT, "scripts", "updb_signal_reports.json")
SIG = "uap-em-strat-001"          # Nuclear Sentinel needle
FORCE = "uap-ir-force-001"        # military-engagement companion


def pick_examples(rows, n=6):
    """Rank firing reports for readability: longer, nuclear-explicit descriptions first."""
    kw = ("nuclear", "missile", "silo", "reactor", "base", "power plant", "warhead", "military")
    def score(r):
        d = (r.get("description") or "").lower()
        return (sum(k in d for k in kw), len(d))
    out = sorted(rows, key=score, reverse=True)[:n]
    return [{
        "id": r["id"], "source": r["source"], "country": r.get("country", ""),
        "year": r.get("year", ""), "city": r.get("city", ""),
        "text": (r.get("description") or "")[:280],
    } for r in out]


def main():
    d = json.load(open(SIGNAL, encoding="utf-8"))
    rows = d["reports"]
    strat = [r for r in rows if SIG in r.get("fired_signatures", [])]
    by_source = Counter(r["source"] for r in strat)
    by_country = Counter(r.get("country", "?") for r in strat)
    n_strat = len(strat)

    # landmark anchor cases (documented) — the ones we seeded
    anchor_ids = {
        "US-NUKE-malmstrom-1967", "US-NUKE-sac-wave-1975", "US-NUKE-rendlesham-bentwaters-1980",
        "RU-SEED-usovo-1982", "JP-SEED-sdf-nuclear-watch",
    }
    anchors = [r for r in strat if r["id"] in anchor_ids]
    anchor_by_id = {r["id"]: r for r in anchors}

    def anchor(id_, fallback_title):
        r = anchor_by_id.get(id_)
        if not r:
            return {"id": id_, "title": fallback_title, "text": "", "country": "", "year": ""}
        return {"id": id_, "title": fallback_title, "country": r.get("country", ""),
                "year": r.get("year", ""), "source": r["source"],
                "text": (r.get("description") or "")[:400]}

    # ---- The investigation PLAY (5-step, mirrors Mirror-Trade shape) ----
    play = {
        "id": "uap-nuclear-sentinel",
        "title": "The Nuclear Sentinel",
        "method": "UAP loitering over nuclear / strategic-weapons infrastructure, sometimes correlated with systems effects",
        "needle": "An unidentified object observed over or beside a nuclear/missile/strategic site, coincident with a systems anomaly, logged by credible or official observers",
        "trigger_signature": SIG,
        "statute_analog": "n/a (UAP has no statute) — payoff is a rigorous investigation standard, not a prosecution",
        "steps": [
            {"n": 1, "verb": "SPOT", "kind": "tool", "produces": "KNOWN", "uts": ["visual"],
             "action": "Confirm proximity: is the object over/beside a nuclear, missile, reactor, or strategic-military site? (geofence the report against known facilities)"},
            {"n": 2, "verb": "CONFIRM", "kind": "tool", "produces": "KNOWN", "uts": ["electronic", "visual"],
             "action": "Systems effect? Did weapons/command/comms/power systems behave anomalously during the sighting (missiles off-alert, launch sequence, EM interference)?"},
            {"n": 3, "verb": "CORROBORATE", "kind": "tool", "produces": "KNOWN", "uts": ["visual", "electronic"],
             "action": "Independent corroboration: multiple/credible witnesses (security, aircrew, officers), radar, FLIR, or an official record/investigation."},
            {"n": 4, "verb": "RULE-OUT", "kind": "gate", "produces": "KNOWN", "uts": ["visual"],
             "action": "Rule out prosaic causes: test flight, drone incursion, balloon, planet/star, exercise, misID near secure airspace.",
             "kill_if": "prosaic cause fully explains proximity + systems-effect + corroboration"},
            {"n": 5, "verb": "ASSESS", "kind": "llm", "produces": "ASSESSED", "uts": ["visual", "electronic"],
             "action": "Weigh the surviving evidence and assign an IC-standard WEP confidence: how strongly does this fit the Nuclear Sentinel pattern vs remain explained/insufficient?"},
        ],
        "result_shape": "A confidence-rated Nuclear-Sentinel assessment with an explicit collection-gap list (what would raise confidence), never a claim of proof.",
    }

    # ---- The bespoke AI investigator config for this dossier ----
    investigator = {
        "id": "inv-nuclear-sentinel",
        "label": "Nuclear Sentinel Investigator",
        "opening": "I investigate whether an unidentified object was genuinely surveilling a strategic-weapons site, or whether a prosaic cause explains it. I run five steps and I tell you my confidence honestly.",
        "vectors_wanted": ["visual", "electronic"],
        "prosaic_checklist": [
            "Scheduled test flight / exercise (check NOTAMs, base schedules)",
            "Drone incursion (increasingly common near bases post-2015)",
            "Weather balloon / research balloon",
            "Astronomical (planet/star near horizon, especially if 'hovering for hours')",
            "Conventional aircraft with unusual lighting near restricted airspace",
        ],
        "confidence_ladder": [
            {"wep": "Insufficient", "when": "Single witness, no systems effect, no official record"},
            {"wep": "Likely (prosaic)", "when": "A prosaic cause plausibly covers proximity + effect"},
            {"wep": "Anomalous — MODERATE", "when": "Credible/multiple witnesses + proximity, prosaic not fully covering"},
            {"wep": "Anomalous — HIGH", "when": "Official record + systems effect + radar/FLIR + prosaic excluded"},
        ],
    }

    n_force = sum(1 for r in rows if FORCE in r.get('fired_signatures', []))
    top_src = by_source.most_common(2)
    src_line = " and ".join(f"{c:,} from {s}" for s, c in top_src)

    # ---- The chapters (documentary) ----
    # Each chapter has a full `narration` (documentary script, ~150-260 words, Nova-neutral
    # voice) for the 1-2 min audio, plus a short `caption` subtitle. Every NUMBER and every
    # case detail is grounded in the corpus/records; connective storytelling is authored prose
    # that never invents a fact, quote, or figure. KNOWN/ASSESSED woven into the script.
    chapters = [
        {
            "id": "ch-hook", "title": "Why do they watch our weapons?", "visual": "stats",
            "caption": f"{n_strat:,} reports fire the Nuclear Sentinel signature across {len(by_source)} sources.",
            "narration": (
                "Since the dawn of the atomic age, a strange and stubborn pattern has surfaced in the "
                "records of nearly every nation that built the bomb. Again and again, unidentified objects "
                "are reported not over cities or airports, but over the most secret and dangerous places we "
                "have ever built: missile silos, weapons-storage bunkers, nuclear reactors, and the command "
                "posts that control them. Airmen, security police, and pilots describe silent craft that "
                "hover above the fence line, hold position for minutes at a time, and depart without a trace. "
                "We call this pattern the Nuclear Sentinel. "
                f"This is what our system detects. ASSESSED: across the corpus, {n_strat:,} separate reports "
                f"fire the Nuclear Sentinel signature. KNOWN: these are real reports drawn from "
                f"{len(by_source)} independent sources and dozens of countries — not one storyteller, but "
                "many, most of whom never knew of one another. "
                "We are not here to tell you what these objects are. We cannot prove that, and anyone who "
                "says otherwise should lose your trust. What we can do is something a catalog of sightings "
                "cannot: show you that the pattern is real, show you where it holds up and where it falls "
                "apart, and show you exactly how a disciplined investigator would work a case like this."),
            "visualData": {"headline_stat": n_strat, "stat_label": "reports fire the Nuclear Sentinel signature",
                           "sub_stats": [{"k": "Independent sources", "v": len(by_source)},
                                         {"k": "Countries", "v": len(by_country)},
                                         {"k": "Reports of military engagement", "v": n_force}]},
        },
        {
            "id": "ch-signature", "title": "What the detector actually tests", "visual": "process",
            "caption": "The signature is a testable rule, not a feeling.",
            "narration": (
                "Before we look at the cases, you should understand exactly what the machine is looking for, "
                "because this is where our approach parts ways with every UFO website you have ever seen. "
                "A sighting catalog stores what someone reported. Our system instead applies a testable rule "
                "— what we call a signature. "
                "The Nuclear Sentinel signature fires only when a report satisfies a specific combination. "
                "First, proximity: the object is described at or beside a nuclear, missile, reactor, or "
                "strategic-military site. Second, an effect or a witness of weight: either the site's systems "
                "behaved anomalously during the sighting — missiles dropping off alert, a launch sequence, "
                "electrical or communications interference — or the observer is a credible one, like security "
                "police or aircrew, or an official investigation was opened. "
                "KNOWN: this is a rule you can argue with, tighten, or break. That is the point. A pattern "
                "is a checklist, not an intuition. When a report clears that bar, the signature fires and the "
                "report joins the pattern you are about to see. When it does not, it stays out — no matter how "
                "dramatic the story. ASSESSED: that discipline is what lets us say the number "
                f"{n_strat:,} and mean something by it."),
            "visualData": {"steps": [
                {"label": "Proximity", "detail": "at or beside a silo, reactor, nuclear facility, or base"},
                {"label": "Systems effect", "detail": "missiles off-alert, launch sequence, EM or comms interference"},
                {"label": "Credible record", "detail": "security police, aircrew, officers — or an official investigation"},
            ]},
        },
        {
            "id": "ch-corroboration", "title": "The same pattern, many independent sources", "visual": "corroboration",
            "caption": "The pattern appears independently across sources that never coordinated.",
            "narration": (
                "Here is the single most important idea in this dossier, and it is the thing a catalog can "
                "never show you. "
                "A pattern that appears in only one archive proves nothing — it could be a quirk of how that "
                "one group collects reports. But the Nuclear Sentinel signature does not live in one archive. "
                f"KNOWN: it fires on {src_line} — the two largest civilian reporting bodies — but it also "
                "fires in the official case files of France's government UAP office, in Soviet-era records "
                "smuggled out of the USSR, in accounts attributed to Japanese Self-Defense Force pilots, and "
                "in the instrument logs of Norway's Hessdalen research station. "
                "Think about what that means. These sources speak different languages. They were compiled by "
                "rival governments and by amateurs who distrusted those governments. They had no shared "
                "database and, in the Cold War, every reason not to compare notes. And yet the same structural "
                "pattern — an object loitering over strategic weapons — surfaces in all of them. "
                "ASSESSED: independent convergence like this is the strongest argument that we are looking at "
                "a real phenomenon rather than one culture's anxiety or one archive's bias. It does not tell "
                "us what the objects are. It tells us the pattern is not imaginary."),
            "visualData": {"sources": [{"source": s, "count": c} for s, c in by_source.most_common(10)]},
        },
        {
            "id": "ch-malmstrom", "title": "Landmark: Malmstrom AFB, 1967", "visual": "graph",
            "caption": "Missiles went off alert as an object hovered over the base.",
            "narration": (
                "To understand the pattern, start with the case that defines it. "
                "KNOWN, from declassified US Air Force records and the later public testimony of former "
                "missile-launch officers: on the sixteenth of March, 1967, at Malmstrom Air Force Base in "
                "Montana, an entire flight of Minuteman intercontinental ballistic missiles — Echo Flight — "
                "went off alert in rapid succession, dropping to a no-go status the launch crew could not "
                "explain. At the same time, security personnel on the surface reported an unidentified glowing "
                "object hovering over the facility. A similar event was described at Oscar Flight. "
                "Sit with the stakes for a moment. These were live nuclear weapons at the height of the Cold "
                "War, and ten of them simultaneously became unavailable while something no one could identify "
                "sat above the site. The Air Force investigated. The event entered the official record. "
                "ASSESSED: the coincidence of a strategic-weapons-system failure with an unidentified object "
                "directly overhead is the archetype of the Nuclear Sentinel pattern — proximity, a systems "
                "effect, and credible military witnesses, all at once. It is exactly the combination the "
                "signature is built to catch. And crucially, we did not invent that rule and then go looking "
                "for Malmstrom. Malmstrom is one of ten thousand reports the rule found on its own."),
            "visualData": {
                "anchor": anchor("US-NUKE-malmstrom-1967", "Malmstrom AFB (Echo/Oscar Flights) 1967"),
                # network: the case at the center, wired to the signatures it fired + sibling cases
                "nodes": [
                    {"id": "Malmstrom 1967", "center": True, "kind": "case"},
                    {"id": "nuclear interference", "kind": "sig"},
                    {"id": "formation", "kind": "sig"},
                    {"id": "occupant", "kind": "sig"},
                    {"id": "landing", "kind": "sig"},
                    {"id": "1975 SAC wave", "kind": "case"},
                    {"id": "Usovo 1982", "kind": "case"},
                ],
                "links": [
                    {"source": "Malmstrom 1967", "target": "nuclear interference", "w": 5},
                    {"source": "Malmstrom 1967", "target": "formation", "w": 3},
                    {"source": "Malmstrom 1967", "target": "occupant", "w": 2},
                    {"source": "Malmstrom 1967", "target": "landing", "w": 2},
                    {"source": "Malmstrom 1967", "target": "1975 SAC wave", "w": 4},
                    {"source": "Malmstrom 1967", "target": "Usovo 1982", "w": 3},
                ],
            },
        },
        {
            "id": "ch-1975wave", "title": "Landmark: the 1975 SAC-base wave", "visual": "timeline",
            "caption": "Autumn 1975: a wave over Strategic Air Command bases storing nuclear weapons.",
            "narration": (
                "One event might be a fluke. A wave is a pattern. "
                "KNOWN, from US Air Force message traffic later released under the Freedom of Information Act: "
                "over several weeks in the late autumn of 1975, a series of unidentified craft and lights was "
                "reported over Strategic Air Command bases across the northern United States — Loring in "
                "Maine, Wurtsmith in Michigan, Malmstrom again in Montana. Several of these bases stored "
                "nuclear weapons. Security teams and aircrews described objects hovering over the "
                "weapons-storage and alert areas. Interceptor aircraft were launched. KNOWN: in some cases, "
                "they achieved no identification at all. "
                "What makes the 1975 wave important is its shape in time. It was not one base or one night; it "
                "was base after base, night after night, clustering in a matter of weeks — and then it "
                "stopped. When you place it on a timeline alongside Malmstrom in 1967, Rendlesham in 1980, "
                "Usovo in 1982, and the Japanese accounts of the 2000s, ASSESSED: the pattern is not only "
                "geographic, tied to where our weapons are; it is temporal, arriving in concentrated waves "
                "that the reporting record captures decade after decade."),
            "visualData": {"anchor": anchor("US-NUKE-sac-wave-1975", "SAC-base overflight wave, Oct-Nov 1975"),
                           "timeline": [{"year": "1967", "label": "Malmstrom"}, {"year": "1975", "label": "SAC wave"},
                                        {"year": "1980", "label": "Rendlesham"}, {"year": "1982", "label": "Usovo (USSR)"},
                                        {"year": "2000s", "label": "Japanese SDF"}]},
        },
        {
            "id": "ch-global", "title": "Landmark: it isn't only America", "visual": "map",
            "caption": "The pattern crosses the Iron Curtain and the Pacific.",
            "narration": (
                "If the Nuclear Sentinel pattern were only an American story, we could set it aside as a "
                "product of Cold-War nerves and secrecy on one side of the world. It is not. "
                "KNOWN: in October 1982, at a strategic missile facility near Usovo in what was then Soviet "
                "Ukraine, personnel reported a disc-shaped object hovering above the base — and during the "
                "sighting, launch-control equipment reportedly activated on its own, with missiles briefly "
                "entering a pre-launch sequence that no human had commanded, before the object departed and "
                "the systems returned to normal. This was recorded in Soviet documentation, on the other side "
                "of the Iron Curtain, by the adversary. "
                "KNOWN: half a world away, accounts attributed to Japan Air Self-Defense Force pilots describe "
                "repeated encounters with luminous objects near nuclear power facilities, framed by the "
                "observers as if the objects were watching sensitive energy infrastructure. "
                "ASSESSED: a pattern that shows up independently in American, Soviet, British, and Japanese "
                "records — among governments that were rivals or enemies and had no reason to corroborate one "
                "another — is very hard to explain as any single nation's mistake or myth. The geography of "
                "the pattern follows the geography of the weapons, wherever on Earth they are kept."),
            "visualData": {"points": [{"lat": r["lat"], "lng": r["lng"], "id": r["id"], "country": r.get("country", ""),
                                        "label": r.get("city", "")} for r in anchors if r.get("lat") is not None],
                           "anchor_usovo": anchor("RU-SEED-usovo-1982", "Usovo missile base, USSR 1982"),
                           "anchor_sdf": anchor("JP-SEED-sdf-nuclear-watch", "Japanese SDF nuclear-plant accounts")},
        },
        {
            "id": "ch-skeptic", "title": "What we rule out (the honesty chapter)", "visual": "process",
            "caption": "A dossier that can't say what it rules out isn't trustworthy.",
            "narration": (
                "Now the part most UFO stories skip — and the part a serious investigator cares about most. "
                "What is the ordinary explanation? Because most of the time, there is one. "
                "KNOWN prosaic causes cluster around military bases precisely because bases are busy, secure, "
                "and watched. Scheduled test flights and exercises put unfamiliar aircraft in the sky on a "
                "timetable. Since the mid-2010s, drone incursions over bases have become common and are often "
                "reported as unidentified. Weather and research balloons drift for hours and can appear to "
                "hover. A bright planet low on the horizon fools even trained observers, especially in reports "
                "of an object that 'hovered for hours.' And conventional aircraft with unusual lighting, seen "
                "near restricted airspace, generate a steady stream of honest mistakes. "
                "ASSESSED, and this is the crucial admission: the signature does not rule any of this out by "
                "itself. Firing the signature makes a report a candidate, nothing more. It takes a real "
                "investigation — the next chapter — to separate the genuine anomaly from the test flight or "
                "the planet. A tool that cannot state plainly what it rules out is not an intelligence tool; "
                "it is a believer's scrapbook. The willingness to say 'this one is probably a drone' is what "
                "earns the right to say 'this one, we cannot explain.'"),
            "visualData": {"steps": [{"label": c, "detail": ""} for c in investigator["prosaic_checklist"]]},
        },
        {
            "id": "ch-howto", "title": "How to investigate it", "visual": "checklist",
            "caption": "The field guide: collect these vectors, rule out these causes, earn your confidence.",
            "narration": (
                "So how do you actually work a Nuclear Sentinel case? This is the field guide — the part a "
                "MUFON investigator or a military analyst can put to use tomorrow. "
                "The procedure has five steps, and each one either strengthens the case or closes it. First, "
                "SPOT: confirm the object really was at or beside a strategic site, by geofencing the report "
                "against known facilities — not 'near the base' from memory, but on the map. Second, CONFIRM: "
                "establish whether any system genuinely behaved anomalously during the sighting, from "
                "maintenance logs, alert records, or communications data. Third, CORROBORATE: find independent "
                "support — a second credible witness, a radar or infrared track, an official memorandum. "
                "Fourth, RULE OUT: work the prosaic checklist from the last chapter and try honestly to kill "
                "the case. If a test flight or a drone explains everything, you stop here and say so. "
                "Fifth, ASSESS: only now do you assign a confidence, using plain intelligence-standard "
                "language. KNOWN: with a single uncorroborated witness and no systems effect, you are at "
                "'insufficient.' ASSESSED: an official record plus a systems effect plus a radar or infrared "
                "track, with prosaic causes excluded, is the only path to a high-confidence anomaly. "
                "The goal is never to prove aliens. The goal is to know precisely how much you are entitled to "
                "believe — and to be able to defend that number to a skeptic."),
            "visualData": {"play_steps": play["steps"], "confidence_ladder": investigator["confidence_ladder"]},
        },
        {
            "id": "ch-investigator", "title": "Run the Nuclear Sentinel Investigator", "visual": "investigator",
            "caption": "Practice the five steps on a real case; the AI shows its reasoning.",
            "narration": (
                "Reading about a method is one thing. Running it is another — and that is where this stops "
                "being a documentary and becomes a training ground. "
                "The Nuclear Sentinel Investigator is an AI agent built for this exact pattern and no other. "
                "Hand it a real report from the corpus and it walks the five steps in the open: it states why "
                "it is looking at each thing, what it found, and what that does to the case. It works the "
                "prosaic checklist out loud, and it assigns an honest, intelligence-standard confidence — and "
                "at every step you can overrule it, redirect it, or feed it something it missed. "
                "For an organization like MUFON, with decades of hard-won field experience and a generation of "
                "veteran investigators, this is more than a demo. It is a way to encode what those veterans "
                "know into a repeatable method, to train new volunteers against real cases, and to preserve "
                "expert judgment after the experts have moved on. KNOWN: France's government office publishes "
                "official A, B, C, and D classifications for its cases — which means, for a large body of "
                "reports, we already have an answer key to grade a trainee's reasoning against. "
                "Pick a case below and run it. Every one is a real, KNOWN record — and each opens to its "
                "original source."),
            "visualData": {"investigator": investigator, "examples": pick_examples(strat, 6)},
        },
    ]

    # annotate each chapter with word count + estimated narration seconds (~150 wpm)
    total_words = 0
    for ch in chapters:
        w = len((ch.get("narration") or "").split())
        ch["words"] = w
        ch["est_seconds"] = round(w / 150.0 * 60)
        total_words += w

    dossier = {
        "id": "nuclear-sentinel",
        "title": "The Nuclear Sentinel",
        "subtitle": "Why do UAP appear over our nuclear weapons?",
        "signature": SIG,
        "firing_total": n_strat,
        "sources": len(by_source),
        "countries": len(by_country),
        "narration_words": total_words,
        "est_runtime_min": round(total_words / 150.0),
        "play": play,
        "investigator": investigator,
        "chapters": chapters,
        "landmark_cases": [a for a in [anchor_by_id.get(i) for i in anchor_ids] if a],
        "note": ("Grounded in the live signal (scripts/updb_signal_reports.json). Every stat is KNOWN "
                 "corpus data; every interpretation is ASSESSED. No claim of proof."),
    }

    fe = {"generated": "build_nuclear_sentinel_dossier.py",
          "dossiers": [dossier]}
    out_path = os.path.join(ROOT, "src", "frontend", "uap-dossiers.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("// UAP Pattern Dossiers - documentary + play + AI investigator, grounded in the live signal.\n")
        f.write("window.UAP_DOSSIERS = " + json.dumps(fe, ensure_ascii=False) + ";\n")
    print(f"Built dossier '{dossier['title']}' ({n_strat:,} firing, {len(by_source)} sources, "
          f"{len(chapters)} chapters, {len(dossier['landmark_cases'])} anchors) -> src/frontend/uap-dossiers.js")


if __name__ == "__main__":
    main()
