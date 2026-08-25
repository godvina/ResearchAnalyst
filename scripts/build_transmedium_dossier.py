# -*- coding: utf-8 -*-
"""'The Transmedium Problem' Pattern Dossier — objects that cross between air, water, and space
without the transition that physics expects. APPENDS to window.UAP_DOSSIERS.

Grounded numbers (verified from src/frontend/uap-command-data.js sig_meta):
  uap-fk-tm-001 (enters/exits water)                 6,994
  uap-fk-tm-002 (on/at the water surface)           28,009
  uap-fk-tm-003 (USO tracked/observed submerged)    26,849
Anchor cases (real, in uap-case-store.js): coastal GEIPAN reports firing tm signatures.
KNOWN = documented; ASSESSED = inference w/ WEP. Run BEFORE generate_dossier_audio.py.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JS = os.path.join(ROOT, "src", "frontend", "uap-dossiers.js")
PTS = {"Plouhinec": (47.9869, -4.4831, "FR"), "Douai": (50.3714, 3.0800, "FR"),
       "Nimitz": (32.6, -119.5, "US")}


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
        {"id": "tm-hook", "title": "The medium is the problem", "visual": "stats",
         "caption": "Air, water, space — one object, no transition. That is the hard part.",
         "narration": (
            "Most flying-object reports stay in one medium: they are seen in the air, and they leave through "
            "the air. A smaller but persistent class does something far stranger — it crosses between air and "
            "water, or is tracked beneath the sea, with none of the splash, shockwave, or slowdown that "
            "physics demands at the boundary. This is the transmedium problem, and it is one of the harder "
            "things in the whole corpus to explain away. "
            "KNOWN: in this dataset, objects entering or exiting water fire 6,994 times; objects on or at the "
            "water surface, 28,009 times; and unidentified submerged objects — USOs — tracked underwater, "
            "26,849 times. ASSESSED, with MODERATE confidence: a normal aircraft cannot enter the sea without "
            "destroying itself; a submarine cannot leap into the air; and neither moves cleanly between the two "
            "at speed. The transmedium reports describe exactly that clean crossing. That does not prove an "
            "exotic craft — but it is the specific behaviour that conventional explanations struggle with most, "
            "which is why it sits near the centre of the modern military interest."),
         "visualData": {"headline_stat": 26849, "stat_label": "reports of unidentified SUBMERGED objects tracked underwater (uap-fk-tm-003)",
                        "sub_stats": [{"k": "On/at water surface (tm-002)", "v": 28009},
                                      {"k": "Enter/exit water (tm-001)", "v": 6994},
                                      {"k": "Physics problem", "v": "boundary"}]}},
        {"id": "tm-why", "title": "Why the boundary matters", "visual": "corroboration",
         "caption": "The air-water interface is a wall for our machines. Not, apparently, for these.",
         "narration": (
            "To see why transmedium behaviour is such a strong flag, think about the boundary itself. "
            "KNOWN: water is roughly eight hundred times denser than air. Hitting it at speed is, for any of our "
            "vehicles, a violent event — aircraft break up, and even purpose-built craft slow dramatically. A "
            "submarine surfaces slowly and deliberately; it does not breach and fly. ASSESSED, with MODERATE "
            "confidence: an object that passes from air to water, or water to air, at speed and intact is doing "
            "something our engineering cannot. That is the whole point of tracking this signature — it isolates "
            "the reports that break the medium barrier, which is a physical constraint, not a matter of witness "
            "opinion. "
            "KNOWN: the three transmedium signatures stack into a coherent picture — surface sightings the most "
            "common, submerged tracking almost as frequent, and the rarer, hardest cases where the crossing "
            "itself is witnessed. ASSESSED: taken together they describe an object at home in a medium that is "
            "hostile to everything we build. Worth watching; not yet explained."),
         "visualData": {"sources": [
            {"source": "On/at water surface (tm-002)", "count": 28009},
            {"source": "Submerged / USO (tm-003)", "count": 26849},
            {"source": "Enter/exit water (tm-001)", "count": 6994},
            {"source": "Radar-confirmed (em-rv-001)", "count": 8136}]}},
        {"id": "tm-cases", "title": "USOs and coastal crossings", "visual": "map",
         "caption": "Coastlines and naval ranges are where transmedium reports concentrate.",
         "narration": (
            "Transmedium reports cluster where people watch the sea — coastlines, naval exercise areas, and "
            "fishing grounds. "
            "KNOWN: the corpus holds numerous coastal European reports, such as those logged by France's "
            "official GEIPAN body, of objects seen entering or moving at the water's surface. KNOWN, from the "
            "public record beyond this corpus: the United States Navy's own encounters off the eastern seaboard "
            "and southern California — the events behind the 2021 government UAP assessment — included objects "
            "that operators described dropping toward or into the water. ASSESSED: the honest position is that "
            "many individual reports have prosaic candidates — a diving bird, a breaching whale, a boat wake, a "
            "sensor artefact at the horizon. But the volume, and the specific descriptions of clean entry "
            "without impact, are not all dismissable that way. ASSESSED, with MODERATE confidence: the "
            "transmedium class is real as a reporting pattern; its cause is unresolved, and it is precisely the "
            "class that warrants instrumented ocean sensors rather than more eyewitness accounts."),
         "visualData": {"points": [pt("Plouhinec", "Plouhinec, FR — coastal report"),
                                    pt("Douai", "Douai, FR"), pt("Nimitz", "US Navy range, off S. California")],
                        "anchor": {"title": "Coastal / naval transmedium reports", "country": "FR/US", "year": "various",
                                   "text": "GEIPAN coastal surface/entry reports + US Navy off-coast encounters (2004-2015, behind the 2021 ODNI assessment). Fire fk-tm-001/002/003."}}},
        {"id": "tm-ruleout", "title": "What transmedium must survive", "visual": "checklist",
         "caption": "Birds, whales, wakes, submarines, and horizon mirage.",
         "narration": (
            "Because water plays tricks on the eye, transmedium reports demand a hard rule-out. "
            "A diving seabird or a breaching whale can look, from distance, like an object entering the water. "
            "A boat wake or a submarine's sail can read as a surface object. A temperature gradient over the sea "
            "bends light, producing horizon mirages that float and distort. Sonar can misread thermoclines and "
            "biological layers as solid returns. ASSESSED: each of these kills a subset of reports — and should. "
            "What survives is the narrow set where the object is large, structured, moves under power against "
            "wind or current, and crosses the boundary at speed without impact — ideally with a sensor, not just "
            "an eye. ASSESSED, with the discipline stated plainly: a single coastal light dropping toward the sea "
            "is INSUFFICIENT; a radar-or-sonar-confirmed object crossing the interface at speed is ANOMALOUS — "
            "and only the rare, instrumented case reaches HIGH. The medium barrier is the strongest part of the "
            "claim; the sensor is what turns it from a story into data."),
         "visualData": {"play_steps": [
            {"verb": "SEABIRD/WHALE", "action": "Diving bird or breaching whale mimics entry — check size + structure.", "produces": "RULE-OUT"},
            {"verb": "WAKE/SUB", "action": "Boat wake or submarine sail reads as surface object.", "produces": "RULE-OUT"},
            {"verb": "MIRAGE", "action": "Horizon temperature gradient floats/distorts distant objects.", "produces": "RULE-OUT"},
            {"verb": "SONAR ARTEFACT", "action": "Thermoclines/biologics misread as solid submerged returns.", "produces": "RULE-OUT"},
            {"verb": "CLEAN CROSSING", "action": "Structured object crossing air-water at speed, no impact, sensor-tracked.", "produces": "CONFIRM"}],
            "confidence_ladder": [
            {"wep": "ANOMALOUS — HIGH", "when": "Radar/sonar-confirmed crossing at speed, no prosaic fit"},
            {"wep": "ANOMALOUS — MODERATE", "when": "Credible witness to a clean crossing, no instrument"},
            {"wep": "INSUFFICIENT", "when": "Single coastal light toward the sea; prosaic candidates open"}]}},
        {"id": "tm-invest", "title": "Run the investigator on a transmedium case", "visual": "investigator",
         "caption": "Take the play to a real coastal / water-crossing record.",
         "narration": (
            "Now test it. Pick a real transmedium record below and the investigator runs the field play against "
            "that exact case — the medium-crossing behaviour, whether an instrument backs it, whether a bird, "
            "wake, or mirage explains it, and a confidence-rated verdict with the collection gaps that would "
            "raise it. Watch how the honest verdict usually lands at MODERATE: the behaviour is striking, but "
            "the sea offers many prosaic candidates, and few reports carry the sonar or radar that would settle "
            "it. That restraint is the tool working as intended."),
         "visualData": {"investigator": {
            "opening": "Water is 800x denser than air. An object crossing that boundary intact is the hard part — and the sea is full of look-alikes.",
            "prosaic_checklist": ["Diving seabird / breaching whale", "Boat wake or submarine sail",
                                   "Horizon mirage (temperature gradient)", "Sonar thermocline/biologic artefact",
                                   "Distant boat or aircraft near the waterline"]},
            "examples": [
                {"id": "GEIPAN-2023-01-51422", "source": "GEIPAN", "country": "FR", "year": 2023,
                 "text": "Plouhinec (coastal Brittany) — object report firing transmedium surface/entry signatures."},
                {"id": "BE-SOBEPS-1990-f16", "source": "BE-SOBEPS", "country": "BE", "year": 1990,
                 "text": "Belgian F-16 intercept — fires the transmedium signature among others; test how it scores."}]}},
    ]
    total = 0
    for ch in chapters:
        w = len((ch.get("narration") or "").split()); ch["words"] = w; ch["est_seconds"] = round(w/150.0*60); total += w
    dossier = {"id": "transmedium", "title": "The Transmedium Problem",
               "subtitle": "Objects that cross air, water, and space without the transition physics expects",
               "signature": "uap-fk-tm-003", "firing_total": 26849, "sources": 3, "countries": 2,
               "narration_words": total, "est_runtime_min": round(total/150.0), "chapters": chapters,
               "landmark_cases": ["GEIPAN-2023-01-51422", "BE-SOBEPS-1990-f16"],
               "note": ("Transmedium/USO class: fk-tm-001=6,994; fk-tm-002=28,009; fk-tm-003=26,849. KNOWN "
                        "documented; ASSESSED w/ WEP; prosaic sea look-alikes stated (birds/whales/wake/mirage/sonar).")}
    obj.setdefault("dossiers", [])
    obj["dossiers"] = [d for d in obj["dossiers"] if d.get("id") != "transmedium"] + [dossier]
    with open(DOSSIER_JS, "w", encoding="utf-8") as f:
        f.write("// UAP Pattern Dossiers - documentary + play + AI investigator, grounded in the live signal.\n")
        f.write("window.UAP_DOSSIERS = " + json.dumps(obj, ensure_ascii=False) + ";\n")
    print(f"Appended 'The Transmedium Problem' ({len(chapters)} ch, ~{dossier['est_runtime_min']} min, {total} words). Total: {len(obj['dossiers'])}")


if __name__ == "__main__":
    main()
