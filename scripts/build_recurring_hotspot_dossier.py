# -*- coding: utf-8 -*-
"""Build the 'Recurring Hotspot' Pattern Dossier — fixed locations that generate repeated,
recurring reports over years or decades. APPENDS to window.UAP_DOSSIERS.

Grounded numbers (verified from src/frontend/uap-command-data.js sig_meta):
  uap-et-hotspot-001 (fixed location, recurring reports) fires 63,537 reports
Anchor cases (real, in uap-case-store.js):
  NO-HESSDALEN-wave-1984      — Hessdalen valley wave, 1984
  NO-HESSDALEN-eml-hypothesis — Hessdalen EM-light hypothesis, 2007
  IT-CUN-national             — Italy national recurring reporting
  JP-SEED-sdf-nuclear-watch   — JASDF recurring watch (hotspot + strat)

Hessdalen is the headline because it is the one hotspot with a permanent scientific
instrument station (Project Hessdalen / EMBLA). Documentary voice, Nova-neutral.
Run BEFORE generate_dossier_audio.py.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JS = os.path.join(ROOT, "src", "frontend", "uap-dossiers.js")

PTS = {
    "Hessdalen":  (62.7833, 11.1917, "NO"),
    "Rome":       (41.9028, 12.4964, "IT"),
    "Sedona":     (34.8697, -111.7610, "US"),
    "Senganmori": (37.5000, 140.5000, "JP"),
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
            "id": "hs-hook", "title": "Some places keep producing lights", "visual": "stats",
            "caption": "Not a one-off. The same patch of sky, reporting the same thing, for decades.",
            "narration": (
                "Most UAP reports are scattered — one place, one night, one witness. But a distinct pattern in "
                "the data is the opposite of scattered: a fixed location that produces the same kind of report "
                "again and again, across years and sometimes decades. We call it a recurring hotspot, and it is "
                "one of the most analytically useful patterns we have — because a place that keeps performing "
                "can be studied on purpose, rather than chased after the fact. "
                "KNOWN: the recurring-hotspot signature fires 63,537 times across this corpus. ASSESSED, with "
                "HIGH confidence for the clustering and LOW-to-MODERATE for any single cause: recurrence is a "
                "double-edged clue. It can point to something genuinely unusual about a location — or to a "
                "purely earthly driver: a nearby airport, a military range, a geological or atmospheric quirk, "
                "or simply a local reporting culture that primes people to look up. This dossier takes the most "
                "famous hotspots and asks, for each, which of those it really is."),
            "visualData": {"headline_stat": 63537, "stat_label": "reports fire the recurring-hotspot signature (uap-et-hotspot-001)",
                           "sub_stats": [{"k": "Headline site", "v": "Hessdalen"},
                                         {"k": "Has permanent instruments", "v": "Yes (EMBLA)"},
                                         {"k": "Severity rating", "v": "moderate"}]},
        },
        {
            "id": "hs-hessdalen", "title": "Hessdalen — the hotspot science actually studies", "visual": "map",
            "caption": "A Norwegian valley with a permanent automated station watching the sky since 1984.",
            "narration": (
                "The headline hotspot, and the anchor of this dossier, is the Hessdalen valley in central "
                "Norway — because it is the one place where science set up shop and stayed. "
                "KNOWN: beginning in 1981 and peaking around 1984, residents of this sparsely populated valley "
                "reported frequent luminous phenomena — floating, pulsing, and sometimes fast-moving lights, "
                "often low over the terrain, at a rate of many sightings per week at the peak. KNOWN: rather "
                "than argue about anecdotes, researchers built Project Hessdalen and later the automated EMBLA "
                "station, instrumenting the valley with cameras, magnetometers, radar, and spectrometers. It is "
                "one of the only UAP hotspots on Earth under continuous scientific measurement. "
                "ASSESSED: the leading hypothesis from that instrumented work is not exotic — it is that at "
                "least some of the Hessdalen lights are a natural plasma or electromagnetic phenomenon, "
                "possibly linked to the valley's unusual geology and mineral content, effectively a poorly "
                "understood but natural 'earth light.' That is a genuinely exciting scientific answer, and an "
                "honest one. Hessdalen is the model: take a hotspot seriously enough to measure it, and you "
                "often find something real — just not always what the folklore promised."),
            "visualData": {"points": [pt("Hessdalen", "Hessdalen valley, Norway — instrumented since 1984")],
                           "anchor": {"title": "Hessdalen valley — Norway, 1984 wave", "country": "NO", "year": "1984",
                                      "id": "NO-HESSDALEN-wave-1984",
                                      "text": "Frequent luminous phenomena, many sightings/week at peak; low over terrain. Fires hover + slow + radar + hotspot signatures."},
                           "anchor_usovo": {"title": "Hessdalen EM/plasma hypothesis — 2007", "country": "NO", "year": "2007",
                                      "id": "NO-HESSDALEN-eml-hypothesis",
                                      "text": "Project Hessdalen / EMBLA instrumented study: leading ASSESSED explanation is a natural plasma/EM 'earth light' tied to valley geology. Fires formation + radar + hotspot."}},
        },
        {
            "id": "hs-others", "title": "The other hotspots — and what each really is", "visual": "process",
            "caption": "Sedona, Senganmori, and national reporting clusters — mixed causes, honestly labelled.",
            "narration": (
                "Hessdalen is the well-studied case; the others show how varied the causes can be, and why you "
                "must judge each hotspot on its own evidence rather than lumping them together. "
                "KNOWN: Sedona, Arizona, is a long-running American hotspot — but it sits in a landscape of "
                "heavy tourism, a strong new-age reporting culture, and busy military training airspace nearby, "
                "all of which inflate reports independent of anything unusual overhead. KNOWN: Senganmori and "
                "the wider Fukushima region of Japan carry a centuries-old folklore of strange mountain lights, "
                "and appear in the Japanese reporting record. KNOWN: some national bodies, like Italy's, show "
                "hotspot-style clustering that is partly an artefact of where a country concentrates its "
                "official reporting. "
                "ASSESSED: put together, 'hotspot' is not one phenomenon but a category with at least three "
                "distinct drivers — a genuine local physical effect (Hessdalen's best candidate), a "
                "reporting-culture amplifier (Sedona), and an infrastructure or airspace confound (bases and "
                "airports). The analytical discipline is to decompose a hotspot into these before claiming any "
                "of it is anomalous. Recurrence tells you where to look; it does not tell you what you will "
                "find."),
            "visualData": {"steps": [
                {"label": "Hessdalen (NO)", "detail": "Instrumented; best candidate for a genuine natural plasma/EM effect"},
                {"label": "Sedona (US)", "detail": "Reporting-culture + tourism + nearby military airspace amplifier"},
                {"label": "Senganmori / Fukushima (JP)", "detail": "Centuries-old mountain-light folklore + modern reports"},
                {"label": "National clusters (e.g. IT)", "detail": "Partly an artefact of where official reporting concentrates"},
            ]},
        },
        {
            "id": "hs-ruleout", "title": "Decomposing a hotspot", "visual": "checklist",
            "caption": "Airport, range, geology, reporting culture — subtract them before you claim anomaly.",
            "narration": (
                "Because 'recurring' is so easy to over-read, the hotspot pattern demands the most disciplined "
                "rule-out of any in this library. Before a location earns the word anomalous, you subtract the "
                "ordinary drivers of recurrence one by one. "
                "Is there a nearby airport, flight corridor, or military training range that would naturally "
                "put lights and craft over this spot on a schedule? Is there a geological or atmospheric quirk "
                "— mineral-rich faulting, temperature inversions, a valley that traps and reflects light? Is "
                "there a reporting-culture amplifier — tourism, a famous prior sighting, an active local group "
                "— that raises the count without raising the underlying rate? And crucially: is the location "
                "instrumented, or are we relying entirely on eyes? "
                "ASSESSED: only after those subtractions does the residue matter. Hessdalen is compelling "
                "precisely because it survived instrumentation — the lights kept appearing on cameras and "
                "magnetometers, not just in testimony. The honest verdict for most hotspots is EXPLAINED or "
                "INSUFFICIENT once the confounds are removed; the rare few, like Hessdalen, reach ANOMALOUS — "
                "MODERATE and, more importantly, become real scientific targets rather than campfire stories."),
            "visualData": {"play_steps": [
                {"verb": "AIRSPACE", "action": "Nearby airport / corridor / military range that schedules lights overhead?", "produces": "RULE-OUT"},
                {"verb": "GEOLOGY/ATMO", "action": "Mineral faulting, inversions, light-trapping valley (Hessdalen candidate)?", "produces": "RULE-OUT"},
                {"verb": "REPORTING CULTURE", "action": "Tourism / famous prior case / active local group inflating counts?", "produces": "RULE-OUT"},
                {"verb": "INSTRUMENTED?", "action": "Cameras/magnetometers/radar present, or eyes-only? Instruments raise the floor.", "produces": "CONFIRM"},
            ], "confidence_ladder": [
                {"wep": "ANOMALOUS — MODERATE", "when": "Effect persists on instruments after confounds removed (Hessdalen)"},
                {"wep": "INSUFFICIENT", "when": "Recurrence real but eyes-only; confounds not excluded"},
                {"wep": "EXPLAINED", "when": "Airport/range/reporting-culture fully accounts for the cluster"},
            ]},
        },
        {
            "id": "hs-invest", "title": "Run the investigator on a hotspot case", "visual": "investigator",
            "caption": "Take the play to Hessdalen and the recurring-watch records.",
            "narration": (
                "Finally, test it. Choose one of the real hotspot records below and the investigator runs the "
                "field play against that exact case — checking whether the location is genuinely producing "
                "something, whether instruments back it, whether an airspace or reporting confound explains it, "
                "and ending on a confidence-rated verdict with the collection gaps that would raise it. "
                "Watch how Hessdalen, with its permanent instrument station, behaves differently from an "
                "eyes-only cluster. The presence or absence of a sensor is what separates a scientific target "
                "from a story — and the investigator is built to make that difference visible rather than "
                "assumed."),
            "visualData": {"investigator": {
                "opening": "Recurrence tells you where to point an instrument. It does not, by itself, tell you what is there.",
                "prosaic_checklist": ["Nearby airport / flight corridor", "Military training range on a schedule",
                                       "Geological / atmospheric light effect", "Tourism + reporting-culture amplifier",
                                       "Eyes-only, no instrumentation"]},
                "examples": [
                    {"id": "NO-HESSDALEN-wave-1984", "source": "NO-HESSDALEN", "country": "NO", "year": 1984,
                     "text": "Hessdalen valley wave — many sightings/week; later instrumented by Project Hessdalen."},
                    {"id": "NO-HESSDALEN-eml-hypothesis", "source": "NO-HESSDALEN", "country": "NO", "year": 2007,
                     "text": "Hessdalen EMBLA study — leading explanation a natural plasma/EM earth-light."},
                    {"id": "IT-CUN-national", "source": "IT-CUN", "country": "IT", "year": 2000,
                     "text": "Italy national recurring reporting cluster — fires hotspot + radar + mass-sighting."},
                    {"id": "JP-SEED-sdf-nuclear-watch", "source": "JP-SEED", "country": "JP", "year": 2000,
                     "text": "JASDF recurring watch — fires hotspot + strategic-weapons signatures."},
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
        "id": "recurring-hotspot",
        "title": "The Recurring Hotspot",
        "subtitle": "Fixed locations that keep producing reports — and how to tell a real effect from a confound",
        "signature": "uap-et-hotspot-001",
        "firing_total": 63537,
        "sources": 3,
        "countries": 3,
        "narration_words": total,
        "est_runtime_min": round(total / 150.0),
        "chapters": chapters,
        "landmark_cases": ["NO-HESSDALEN-wave-1984", "NO-HESSDALEN-eml-hypothesis", "IT-CUN-national", "JP-SEED-sdf-nuclear-watch"],
        "note": ("Recurring-hotspot signature (uap-et-hotspot-001 = 63,537 fires). Hessdalen headline (only "
                 "hotspot under permanent instruments; ASSESSED natural plasma/EM). Others decomposed honestly "
                 "into airspace / geology / reporting-culture confounds. KNOWN documented; ASSESSED w/ WEP."),
    }

    obj.setdefault("dossiers", [])
    obj["dossiers"] = [d for d in obj["dossiers"] if d.get("id") != "recurring-hotspot"] + [dossier]

    with open(DOSSIER_JS, "w", encoding="utf-8") as f:
        f.write("// UAP Pattern Dossiers - documentary + play + AI investigator, grounded in the live signal.\n")
        f.write("window.UAP_DOSSIERS = " + json.dumps(obj, ensure_ascii=False) + ";\n")
    print(f"Appended dossier 'The Recurring Hotspot' ({len(chapters)} chapters, ~{dossier['est_runtime_min']} min, "
          f"{total} words). Total dossiers now: {len(obj['dossiers'])}")


if __name__ == "__main__":
    main()
