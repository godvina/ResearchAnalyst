# -*- coding: utf-8 -*-
"""Build the 'Boyne Valley' Pattern Dossier — Ireland's ancient sky sites (UAP x ancient
sites x mythology), written for reading/listening ON LOCATION. APPENDS a second dossier to
window.UAP_DOSSIERS (keeps Nuclear Sentinel). Grounded in:
  - src/data/conspiracy-seed/irish_sacred_sites/tier2_deep_research.json (measured facts)
  - src/data/archon-crosswalk.json (Tuatha De Danann -> sites mythology)
  - scripts/uap_convergence_results.json (honest lift result near the Boyne Valley)

Documentary voice, Nova-neutral. KNOWN = measured/documented fact; ASSESSED = interpretation;
legend/myth clearly labelled as tradition, never as fact. The UAP chapter reports the HONEST
convergence result (Boyne Valley sits at/below baseline) — no hype.

Run AFTER build_nuclear_sentinel_dossier.py, then run generate_dossier_audio.py.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JS = os.path.join(ROOT, "src", "frontend", "uap-dossiers.js")

# Boyne Valley + related site coords (real)
SITES = {
    "Newgrange":   (53.6947, -6.4754),
    "Knowth":      (53.7014, -6.4908),
    "Dowth":       (53.7036, -6.4525),
    "Hill of Tara":(53.5806, -6.6119),
    "Loughcrew":   (53.7442, -7.1122),
    "Knocknarea":  (54.2586, -8.5744),
    "Carrowmore":  (54.2506, -8.5189),
    "Carrowkeel":  (54.0553, -8.3931),
    "Skellig Michael": (51.7708, -10.5386),
    "Giza":        (29.9792, 31.1344),
}
NON_IE = {"Giza"}


def load_dossiers():
    txt = open(DOSSIER_JS, encoding="utf-8").read()
    import re
    m = re.search(r"window\.UAP_DOSSIERS\s*=\s*(\{.*\});\s*$", txt, re.S)
    if not m:
        raise SystemExit("uap-dossiers.js not in expected shape; run build_nuclear_sentinel_dossier.py first")
    return json.loads(m.group(1))


def sitept(name, label=None):
    lat, lng = SITES[name]
    return {"lat": lat, "lng": lng, "label": label or name, "country": "IE" if name not in NON_IE else "EG"}


# ---- Deep-dive sub-chapters (grounded in tier2_deep_research.json) ----
NEWGRANGE_DEEP = [
    {
        "id": "acoustics",
        "title": "Acoustics & the 110 Hz mind",
        "narration": (
            "Step inside the chamber and clap once, or hum, and you feel it before you understand it — the "
            "stone answers back. "
            "KNOWN: acoustic studies of the Newgrange chamber, including work associated with Princeton's PEAR "
            "laboratory under Professor Robert Jahn and the archaeoacoustician Paul Devereux, measured a "
            "standing resonance in the range of ninety-five to one hundred and twenty hertz, peaking around one "
            "hundred and ten. KNOWN: the same narrow band turns up in other ancient chambers far away — the Hal "
            "Saflieni Hypogeum in Malta, Wayland Smithy in England, Cairn L at Carrowkeel here in Ireland. They "
            "all cluster around the same tone. "
            "KNOWN: an EEG study found that sound at one hundred and ten hertz suppresses activity in the brain's "
            "left hemisphere — the language side — and shifts the listener toward a pre-verbal, receptive state, "
            "the kind associated with meditation and trance. ASSESSED, and offered as hypothesis not fact: some "
            "researchers argue these chambers were not merely tombs but frequency-engineered instruments, tuned "
            "to alter human consciousness. We cannot confirm intent across five thousand years. But the "
            "measurement is real, it repeats across cultures, and standing in it, you understand why the idea "
            "refuses to go away."),
    },
    {
        "id": "engineering",
        "title": "The engineering feat",
        "narration": (
            "Now consider what it took to build the thing you are standing in. "
            "KNOWN: Newgrange contains over two hundred thousand tons of material, the largest stones weighing "
            "around five tons each. KNOWN: the white quartz cobbles of the facade came from the Wicklow "
            "Mountains, roughly seventy kilometres south; the dark granodiorite from the Mourne Mountains, "
            "roughly eighty kilometres north — hauled without wheels or draft animals, across rivers, by people "
            "using timber, rope, and numbers. KNOWN: the roof is a system of overlapping stone slabs cut with "
            "drainage channels, and the chamber has stayed completely dry for over five thousand years — a "
            "waterproofing achievement with no modern equal that does not rely on synthetic materials. "
            "KNOWN: above the door sits the roofbox, an engineered aperture one metre wide and a quarter-metre "
            "high, aligned to a solar azimuth of one hundred and thirty-four point five degrees, and it has held "
            "that winter-solstice alignment accurate to within about one degree over five millennia. ASSESSED: "
            "the facade reconstruction you see, done by O'Kelly in the nineteen-sixties and seventies, is itself "
            "disputed — Cooney and Eriksen argue the quartz was a ground-level platform, not a vertical wall. "
            "Worth knowing as you photograph it: even the modern restoration is a live scholarly argument."),
    },
    {
        "id": "suppression",
        "title": "The argument the establishment resisted",
        "narration": (
            "There is a quieter story here, about how knowledge gets accepted, and it is worth carrying as you "
            "look at the carvings. "
            "KNOWN: in nineteen eighty-three, the researcher Martin Brennan published 'The Stars and the "
            "Stones,' arguing that the carvings at Newgrange and Knowth encoded astronomical records — solstice "
            "and equinox alignments deliberately marked in stone. KNOWN: mainstream archaeology largely "
            "dismissed the astronomical reading at the time as fringe. KNOWN: several of the specific alignments "
            "Brennan pointed to were subsequently verified. "
            "ASSESSED: this is a textbook case of what our platform tags as expert divergence and information "
            "asymmetry — a claim rejected less on evidence than on who was making it and how, then quietly "
            "absorbed once it proved out. The lesson is not that every rejected theory is right; most are not. "
            "It is that the boundary between fringe and accepted is drawn by people, and it moves. Stand at "
            "kerbstone K1, look at the triple spiral, and hold both ideas at once: honest skepticism, and "
            "humility about how often the establishment has had to revise the map."),
    },
]

KNOWTH_DEEP = [
    {
        "id": "lunar-calendar",
        "title": "The lunar calendar written in stone",
        "narration": (
            "Knowth rewards a slower look, because the claim here is extraordinary and specific. "
            "KNOWN: kerbstone fifty-two and others have been interpreted, in peer-reviewed work including a "
            "twenty-eighteen paper in the Journal of Lithic Studies, as encoding astronomical cycles — possibly "
            "the eighteen-point-six-year lunar standstill cycle, the slow swing in how far north and south the "
            "moon rises. KNOWN: an arXiv analysis argues the spirals themselves may encode time — a single "
            "spiral for a month, a double for a year, the triple spiral at Newgrange for some larger cycle we "
            "have not decoded. "
            "ASSESSED: tracking an eighteen-point-six-year cycle is not something you do in one lifetime by "
            "accident. It implies deliberate, multi-generational observation — knowledge handed down and refined "
            "across centuries. That is the part that should stop you. Whether or not every specific reading "
            "holds, the scale of patience required to even attempt it tells you these were not superstitious "
            "primitives. They were astronomers, working in the only permanent medium they had: stone."),
    },
    {
        "id": "moon-map",
        "title": "The oldest map of the moon",
        "narration": (
            "There is one stone at Knowth worth seeking out above the others. "
            "KNOWN: an orthostat in the eastern passage has been interpreted by Professor Philip Stooke of the "
            "University of Western Ontario as a map of the moon — specifically of the lunar maria, the dark "
            "patches visible to the naked eye. If that reading holds, it is the oldest known map of the moon's "
            "surface anywhere on Earth. KNOWN: Knowth as a whole holds over three hundred decorated stones — by "
            "a common estimate about a quarter of all the megalithic art in Western Europe, concentrated in this "
            "one monument. KNOWN: the imagery splits by direction — lunar crescents and arcs dominate the "
            "western kerbstones, solar rayed-circles the eastern, matching the twin passages that face sunset "
            "and sunrise. "
            "ASSESSED: academics divide into four camps — decorative, trance-induced, astronomical, or "
            "territorial — and they have not resolved it. You do not need them to. Walk the western kerb at "
            "dusk, find the crescents, then cross to the eastern rayed circles at the other passage. The "
            "building itself tells you which way to look."),
    },
]


def main():
    obj = load_dossiers()

    chapters = [
        {
            "id": "bv-hook", "title": "Standing in the Bend of the Boyne", "visual": "map",
            "caption": "Older than the Pyramids. Older than Stonehenge. Built to catch the sun.",
            "narration": (
                "You are standing in the Bend of the Boyne — Bru na Boinne — in County Meath, Ireland. "
                "Around you, within a few square miles, are some of the oldest roofed structures on Earth. "
                "KNOWN: Newgrange was built around 3200 BC. That is roughly five hundred years before the "
                "Great Pyramid of Giza, and a thousand years before the first stone was raised at Stonehenge. "
                "These are not piles of rock. They are precision instruments, engineered to catch a single "
                "sunrise, to resonate at a single tone, and to hold their secrets watertight for over five "
                "thousand years. "
                "In this dossier we do three things, honestly. We walk the sites you can actually visit and "
                "tell you what is measurably true about each one. We connect them to the mythology the Irish "
                "attached to them — the Tuatha De Danann, the gods said to have arrived from the sky. And we "
                "ask the harder question this whole platform was built to ask: is there any real pattern "
                "linking these ancient sky-sites to modern reports of unidentified objects — and we will give "
                "you the answer the data actually supports, not the one the tour guides might prefer."),
            "visualData": {"points": [sitept("Newgrange"), sitept("Knowth"), sitept("Dowth"),
                                       sitept("Hill of Tara"), sitept("Loughcrew"), sitept("Knocknarea")]},
        },
        {
            "id": "bv-newgrange", "title": "Newgrange — the Palace of Light", "visual": "graph",
            "explorer_site": "irl-001",
            "caption": "A roofbox that catches the winter solstice sunrise, accurate to 1° over 5,000 years.",
            "narration": (
                "Start with Newgrange itself — Si an Bhru, the palace of the Boyne. "
                "KNOWN: above the entrance is a precisely cut aperture called the roofbox, one metre wide and "
                "a quarter-metre high, aligned to a solar azimuth of 134.5 degrees. For a few minutes at "
                "sunrise on the winter solstice, and only then, a beam of sunlight travels the length of the "
                "nineteen-metre passage and illuminates the inner chamber. That alignment has held accurate "
                "to within about one degree for over five thousand years. "
                "KNOWN: the chamber also resonates. Acoustic studies, including work associated with "
                "Princeton's PEAR laboratory and archaeoacoustician Paul Devereux, measured a standing "
                "resonance around 110 hertz — the same frequency found in ancient chambers in Malta, England, "
                "and Peru. ASSESSED: some researchers argue these chambers were tuned instruments meant to "
                "alter consciousness, not merely tombs. That remains a hypothesis. "
                "In Irish tradition, this is the home of the Dagda, father-god of the Tuatha De Danann, and "
                "of his son Aengus Og, god of youth and love. The river beside you is Boann, the goddess for "
                "whom the Boyne is named — mother of Aengus. Legend, KNOWN as legend; but the people who built "
                "this place pointed it at the sky on purpose."),
            "visualData": {
                "anchor": {"title": "Newgrange (Si an Bhru), Co. Meath — c. 3200 BC", "country": "IE", "year": "3200 BC",
                           "text": "Winter-solstice roofbox aligned to azimuth 134.5 deg; 110 Hz chamber resonance; triple-spiral at kerbstone K1; 200,000+ tons of material, quartz carried ~70km from the Wicklow Mountains."},
                "nodes": [
                    {"id": "Newgrange", "center": True, "kind": "case"},
                    {"id": "Dagda", "kind": "sig"}, {"id": "Aengus Og", "kind": "sig"}, {"id": "Boann", "kind": "sig"},
                    {"id": "Tuatha De Danann", "kind": "sig"},
                    {"id": "Knowth", "kind": "case"}, {"id": "Dowth", "kind": "case"},
                ],
                "links": [
                    {"source": "Newgrange", "target": "Dagda", "w": 5},
                    {"source": "Newgrange", "target": "Aengus Og", "w": 4},
                    {"source": "Newgrange", "target": "Boann", "w": 4},
                    {"source": "Newgrange", "target": "Tuatha De Danann", "w": 3},
                    {"source": "Newgrange", "target": "Knowth", "w": 3},
                    {"source": "Newgrange", "target": "Dowth", "w": 3},
                ],
                "deep": NEWGRANGE_DEEP,
            },
        },
        {
            "id": "bv-knowth", "title": "Knowth — the Book of the Moon", "visual": "stats",
            "explorer_site": "irl-002",
            "caption": "A quarter of all megalithic art in Western Europe — much of it lunar.",
            "narration": (
                "A short walk away is Knowth, and if Newgrange is the palace of the sun, Knowth is the book of "
                "the moon. "
                "KNOWN: Knowth holds over three hundred decorated stones — by one common estimate, around a "
                "quarter of all the megalithic art in Western Europe, in this one place. It has two passages, "
                "not one: the eastern passage aligns to sunrise near the equinoxes, the western to sunset. "
                "KNOWN: kerbstone number fifty-two and others have been interpreted, in peer-reviewed work, as "
                "encoding astronomical cycles — possibly the eighteen-point-six-year lunar standstill cycle. A "
                "stone in the eastern passage has been argued by a planetary scientist to be the world's oldest "
                "map of the moon's surface features. "
                "ASSESSED: academics divide into camps — decorative, trance-induced, astronomical, or "
                "territorial. We do not have to pick a winner to notice the pattern: the western stones lean "
                "lunar, the eastern stones lean solar, matching the twin passages. In tradition Knowth too "
                "belongs to Boann's family and the Tuatha De Danann. When you stand at the kerb, look for the "
                "crescents to the west and the rayed circles to the east. They built the calendar into the wall."),
            "visualData": {"headline_stat": 300, "stat_label": "decorated stones at Knowth (~25% of all in W. Europe)",
                           "sub_stats": [{"k": "Passages (twin)", "v": 2}, {"k": "Lunar standstill cycle (yrs)", "v": 18.6},
                                         {"k": "Built (BC)", "v": 3200}],
                           "deep": KNOWTH_DEEP},
        },
        {
            "id": "bv-dowth", "title": "Dowth — the House of Darkness", "visual": "map",
            "explorer_site": "irl-003",
            "caption": "Newgrange takes the solstice dawn. Dowth takes the dusk.",
            "narration": (
                "A short way east of Newgrange sits the third great Boyne mound, the one most visitors skip — "
                "Dowth, in Irish Dubhadh, the House of Darkness. "
                "KNOWN: where Newgrange is Si an Bhru, the palace of light, catching the winter-solstice "
                "sunrise, Dowth catches the winter-solstice SUNSET. At sunset on the shortest day, light moves "
                "along the left side of its three-metre south passage into a round chamber, and a convex "
                "central stone reflects that light into a dark recess, illuminating decorated stones. So the "
                "two mounds bracket the same day — Newgrange the dawn, Dowth the dusk. "
                "KNOWN: Dowth has two known passages on its south-western side; the northern one runs fourteen "
                "metres to a cruciform chamber with a three-metre corbelled roof. It is less excavated than its "
                "famous siblings and may hold undiscovered chambers. "
                "ASSESSED: the light-and-dark pairing of the names is almost certainly deliberate — Dubhadh, "
                "darkness, set against Si an Bhru, the palace of light, a duality built into the landscape. "
                "Access is limited; the OPW sometimes opens it for the solstice sunset. If you can get in, this "
                "is the quiet one — dusk to Newgrange's dawn."),
            "visualData": {"points": [sitept("Dowth"), sitept("Newgrange")],
                           "anchor": {"title": "Dowth (Dubhadh) — Co. Meath", "country": "IE", "year": "c. 3200 BC",
                                      "text": "Winter-solstice SUNSET alignment; convex reflecting stone lights a dark recess; two passages; less excavated. Paired light/dark with Newgrange."}},
        },
        {
            "id": "bv-tara", "title": "The Hill of Tara — seat of the High Kings", "visual": "stats",
            "explorer_site": "irl-004",
            "caption": "The only Irish passage tomb aligned to the cross-quarter days — and a buried landscape.",
            "narration": (
                "South of the Boyne rises the Hill of Tara, Teamhair — the political and sacred centre of "
                "ancient Ireland, seat of its High Kings for over a thousand years. "
                "KNOWN: the Mound of the Hostages here, a small passage tomb, aligns not to a solstice or an "
                "equinox but to the cross-quarter days — sunrise at Samhain, the first of November, and "
                "Imbolc, the first of February, the days midway between solstice and equinox. It is the only "
                "known passage tomb in Ireland aligned this way, which implies a more sophisticated calendar "
                "than a simple solstice marker. KNOWN: it held the richest collection of human bone and "
                "funerary artefacts of any megalithic tomb in Europe, in use from around three thousand to "
                "seventeen hundred BC — thirteen centuries of continuous use. "
                "KNOWN: aerial and geophysical surveys by the Discovery Programme have revealed enormous "
                "structures still buried beneath the hill — a huge oval enclosure, ring forts, and "
                "processional avenues invisible from the surface. KNOWN: the standing stone here, the Lia Fail, "
                "the Stone of Destiny, was said to cry out for the rightful king — one of several kingship "
                "stones across cultures, alongside Scotland's Stone of Scone. ASSESSED: what you see walking "
                "Tara is a fraction of what is there. Touch the Lia Fail; it still stands."),
            "visualData": {"headline_stat": 1300, "stat_label": "years of continuous use at the Mound of the Hostages (~3000-1700 BC)",
                           "sub_stats": [{"k": "Cross-quarter aligned tombs in Ireland", "v": 1},
                                         {"k": "High Kings inaugurated (tradition)", "v": 142},
                                         {"k": "Buried structures found (survey)", "v": "many"}],
                           "deep": [
                               {"id": "hostages", "title": "The Mound of the Hostages & the cross-quarter sky",
                                "narration": (
                                    "The small mound is easy to walk past, and it is the most calendrically "
                                    "sophisticated thing on the hill. "
                                    "KNOWN: its passage is aligned to sunrise on the cross-quarter days — "
                                    "Samhain in early November and Imbolc in early February — the midpoints "
                                    "between solstice and equinox. Every other aligned passage tomb in Ireland "
                                    "targets a solstice or an equinox; this is the only one that marks the "
                                    "cross-quarters. KNOWN: it was in use for roughly thirteen hundred years and "
                                    "yielded the richest funerary assemblage of any European megalithic tomb, "
                                    "the University College Dublin school of archaeology among those who have "
                                    "studied it. ASSESSED: marking the cross-quarters means the builders were "
                                    "not just catching the obvious extremes of the year but dividing it more "
                                    "finely — a calendar of eight points, not four. That is a step up in "
                                    "astronomical thinking, and it is here, in the smallest monument on the "
                                    "hill of kings.")},
                               {"id": "geophysics", "title": "The landscape beneath your feet",
                                "narration": (
                                    "What makes Tara strange is how much of it is invisible. "
                                    "KNOWN: aerial photography and geophysical survey, notably by Ireland's "
                                    "Discovery Programme and the surveyor Joe Fenwick, have mapped vast "
                                    "structures beneath the turf — a huge enclosure some hundreds of metres "
                                    "across, additional ring forts, and processional avenues, none of it "
                                    "visible to a visitor standing on the grass. ASSESSED: the Tara you walk is "
                                    "a faint surface trace of a monumental ceremonial complex. When you stand "
                                    "by the Lia Fail and it looks like an empty green hill, remember the "
                                    "instruments say otherwise — the hill is full.")},
                           ]},
        },
        {
            "id": "bv-loughcrew", "title": "Loughcrew — the oldest light-show on Earth", "visual": "map",
            "explorer_site": "irl-006",
            "caption": "300 years older than Newgrange. An equinox beam that lights carvings in sequence.",
            "narration": (
                "West of the Boyne, on a ridge of hills, sits Loughcrew — and it may be where the whole thing "
                "began. "
                "KNOWN: Loughcrew was built around three thousand five hundred BC, roughly three hundred years "
                "before Newgrange. KNOWN: at sunrise on the equinoxes, a narrow beam of light enters the "
                "passage of Cairn T and travels across the decorated backstone for about fifty minutes, "
                "illuminating carved sun-symbols one after another in sequence — effectively a five-thousand- "
                "year-old astronomical display. It was first photographed by the researcher Martin Brennan "
                "around nineteen eighty. KNOWN: other cairns in the complex align to the cross-quarter days — "
                "Samhain, Imbolc, Beltane, Lughnasadh — so between them they mark the full Celtic calendar. "
                "ASSESSED: because Loughcrew predates the Boyne mounds, researchers argue it may be the "
                "prototype — the place the builders perfected their astronomy before raising the grander "
                "monuments downriver. If that is right, you are looking at the rough draft of Newgrange, and it "
                "still works. If the cairn is open when you visit, the equinox beam across Cairn T is the "
                "oldest deliberate light-show we know of."),
            "visualData": {"points": [sitept("Loughcrew"), sitept("Newgrange")],
                           "anchor": {"title": "Loughcrew (Cairn T) — Co. Meath", "country": "IE", "year": "c. 3500 BC",
                                      "text": "Equinox sunrise beam crosses the decorated backstone ~50 min, lighting sun-symbols in sequence (Brennan, 1980). Complex marks the full cross-quarter calendar. ~300 yrs older than Newgrange — possible prototype."}},
        },
        {
            "id": "bv-knocknarea", "title": "Knocknarea — the cairn no one has opened", "visual": "stats",
            "explorer_site": "irl-010",
            "caption": "40,000 tons of stone carried up a mountain. Never excavated. Interior unknown.",
            "narration": (
                "Far to the west, in County Sligo, a mountain called Knocknarea carries a mystery the Boyne "
                "sites cannot match: a monument no one has ever opened. "
                "KNOWN: on its 327-metre summit sits a vast cairn — some forty thousand tons of loose "
                "limestone, fifty-five metres wide and ten metres high. It has never been excavated. Its "
                "interior is unknown. KNOWN: archaeologists believe it covers a Neolithic passage tomb older "
                "than three thousand BC, predating by three millennia the legends attached to it. Heritage "
                "Ireland's position is that what is inside should stay there; local tradition holds that "
                "disturbing it would bring catastrophe. There are no published ground-penetrating-radar "
                "results — the site is too remote and the cairn too massive for current non-invasive study. "
                "KNOWN: every passage tomb at Carrowmore, four kilometres away, is oriented toward this "
                "mountain. It was the centre of a ritual landscape. ASSESSED: the real puzzle is the "
                "engineering — thirty to forty thousand tons of stone carried UP a mountain with no road, no "
                "wheel, no draft animals, implying a large, organised society with surplus labour. In legend "
                "it is the grave of Queen Maeve of Connacht, buried upright in her armour, facing her enemies "
                "in Ulster. Tradition, labelled as tradition. But the cairn is real, it is sealed, and no one "
                "alive knows what is inside."),
            "visualData": {"headline_stat": 40000, "stat_label": "tons of stone in the sealed Knocknarea cairn (never excavated)",
                           "sub_stats": [{"k": "Summit height (m)", "v": 327}, {"k": "Cairn width (m)", "v": 55},
                                         {"k": "Carrowmore tombs pointing at it", "v": "all"}]},
        },
        {
            "id": "bv-beyond", "title": "Beyond the Boyne — Carrowmore, Carrowkeel & the Michael Line", "visual": "map",
            "caption": "If you range wider: an older origin, a twin roofbox, and a line across Europe.",
            "narration": (
                "If your trip ranges beyond the Boyne, three more sites are worth knowing, each carrying a "
                "genuine open question. "
                "KNOWN: at Carrowmore in Sligo, controversial radiocarbon dates from cremated bone suggest "
                "construction as early as four thousand six hundred BC — which, if valid, would make it the "
                "oldest megalithic complex in Ireland, over a thousand years older than Newgrange. The dates, "
                "championed by the Swedish archaeologist Goran Burenhult, are challenged by others as possibly "
                "contaminated. ASSESSED: if they hold, Ireland becomes a candidate independent origin point for "
                "megalithic building, not merely a recipient of the idea from the continent. "
                "KNOWN: at Carrowkeel, Cairn G has a roofbox almost identical to Newgrange's — but it catches "
                "the SUMMER-solstice sunset rather than the winter-solstice sunrise. Only two roofboxes are "
                "known in all of Ireland, a hundred kilometres apart, tuned to complementary solar events. "
                "ASSESSED: that implies either the same builders or shared technical knowledge moving across "
                "distance. "
                "KNOWN: far to the south-west, the island monastery of Skellig Michael sits on the so-called "
                "Michael Line — a striking geographic alignment linking Skellig Michael, St Michael's Mount in "
                "Cornwall, Mont Saint-Michel in France, and sanctuaries in Italy and Greece, all on high rocky "
                "peaks, many dedicated to Saint Michael or Apollo. ASSESSED, and stated plainly: the alignment "
                "is real as a line on a map; whether it reflects intent or coincidence is unproven, and it is "
                "exactly the kind of geographic-alignment claim this platform tests rather than assumes. Worth "
                "knowing, not worth believing on faith."),
            "visualData": {"points": [sitept("Carrowmore", "Carrowmore, Sligo"),
                                       sitept("Carrowkeel", "Carrowkeel (Cairn G), Sligo"),
                                       sitept("Skellig Michael", "Skellig Michael, Kerry")],
                           "anchor": {"title": "Carrowmore — the oldest-megalith debate", "country": "IE", "year": "4600-3000 BC?",
                                      "text": "Contested C14 dates (~4600 BC, Burenhult) would predate Newgrange by 1000+ yrs; challenged as contaminated. Satellite tombs orient toward Knocknarea."},
                           "anchor_usovo": {"title": "Carrowkeel Cairn G — the twin roofbox", "country": "IE", "year": "c. 3000 BC",
                                      "text": "Roofbox like Newgrange's but catches SUMMER-solstice sunset (discovered 1997). Only 2 roofboxes in Ireland, 100km apart, complementary events."},
                           "anchor_sdf": {"title": "Skellig Michael & the Michael Line", "country": "IE", "year": "~600 AD monastery",
                                      "text": "On the Skellig Michael -> St Michael's Mount -> Mont St-Michel -> Italy -> Delphi alignment. Corbelled cells use Neolithic technique. Alignment real on a map; intent unproven (ASSESSED)."}},
        },
        {
            "id": "bv-mythology", "title": "The Tuatha Dé Danann — gods from the sky", "visual": "graph",
            "caption": "The mythology the Irish attached to these stones — and its honest status.",
            "narration": (
                "Now the mythology — the part the old Irish attached to these places, and the part you asked "
                "us to keep. "
                "In the medieval texts, the Tuatha De Danann — the people of the goddess Danu — are said to "
                "have arrived in Ireland from the sky, or in some tellings on dark clouds, bringing four "
                "treasures and mastery of arts and magic. When they were finally defeated, they did not leave; "
                "they withdrew into the sidhe, the mounds — into Newgrange, Knowth, and Dowth themselves. The "
                "Dagda, their father-god, holds Newgrange; his son Aengus Og wins it from him in the tales; "
                "Boann, the river goddess, is mother to Aengus and namesake of the Boyne. At Tara reign Nuada "
                "and Lugh; at Knocknarea broods the Morrigan, goddess of war and fate. "
                "ASSESSED, and stated plainly: this is mythology, not history. We label it as tradition, never "
                "as fact. What is genuinely interesting — and testable as a pattern — is the recurring shape "
                "of it: sky-people, associated with light and the heavens, tied to precisely sky-aligned "
                "monuments. That same shape — sky-gods bound to solar architecture — recurs from Egypt to the "
                "Andes. It does not prove anything about the origin of these people. It is a pattern in how "
                "humans have explained the sky, and it is worth seeing clearly for what it is."),
            "visualData": {
                "anchor": {"title": "Tuatha De Danann — the mythology (tradition, not history)", "country": "IE", "year": "myth",
                           "text": "Dagda & Aengus Og -> Newgrange; Boann -> the Boyne (Newgrange/Knowth/Dowth); Nuada & Lugh -> Tara; Morrigan/Medb -> Knocknarea; Brigid -> Loughcrew. Said to have arrived from the sky and withdrawn into the mounds."},
                "nodes": [
                    {"id": "Tuatha De Danann", "center": True, "kind": "case"},
                    {"id": "Dagda", "kind": "sig"}, {"id": "Aengus Og", "kind": "sig"}, {"id": "Boann", "kind": "sig"},
                    {"id": "Nuada", "kind": "sig"}, {"id": "Lugh", "kind": "sig"}, {"id": "Morrigan", "kind": "sig"},
                    {"id": "Newgrange", "kind": "case"}, {"id": "Tara", "kind": "case"}, {"id": "Knocknarea", "kind": "case"},
                ],
                "links": [
                    {"source": "Tuatha De Danann", "target": "Dagda", "w": 4},
                    {"source": "Tuatha De Danann", "target": "Aengus Og", "w": 3},
                    {"source": "Tuatha De Danann", "target": "Boann", "w": 3},
                    {"source": "Tuatha De Danann", "target": "Nuada", "w": 3},
                    {"source": "Tuatha De Danann", "target": "Lugh", "w": 3},
                    {"source": "Tuatha De Danann", "target": "Morrigan", "w": 2},
                    {"source": "Dagda", "target": "Newgrange", "w": 4},
                    {"source": "Nuada", "target": "Tara", "w": 3},
                    {"source": "Morrigan", "target": "Knocknarea", "w": 3},
                ],
            },
        },
        {
            "id": "bv-giza", "title": "Newgrange and Giza — the global thread", "visual": "map",
            "caption": "Two sky-tombs, 500 years and 4,000 km apart, built to the same idea.",
            "narration": (
                "You asked for the global connection — Newgrange and Giza — so here it is, told honestly. "
                "KNOWN: both are monumental stone structures built to engage the sun. Newgrange catches the "
                "winter-solstice sunrise through its roofbox; the Great Pyramid and the wider Giza plateau "
                "carry solar and cardinal alignments that have been studied for centuries. KNOWN: Newgrange is "
                "about five hundred years older. KNOWN: the same roughly 110-hertz acoustic resonance measured "
                "at Newgrange has also been reported in the King's Chamber at Giza and in Malta's Hypogeum — a "
                "recurring acoustic property of these ancient chambers. "
                "KNOWN, from our own analysis: both sites also fall on the latitude band of the Becker-Hagens "
                "world-grid, the geometric model we tested elsewhere in this platform. "
                "ASSESSED: what connects them is not evidence of contact between Neolithic Ireland and dynastic "
                "Egypt — there is none. What connects them is a shared human instinct, appearing independently "
                "across the world: to build in stone, align to the sun, and bind the structure to sky-gods and "
                "the afterlife. That independent convergence is the real pattern. It is more remarkable, not "
                "less, for being something many cultures arrived at on their own."),
            "visualData": {"points": [sitept("Newgrange"), sitept("Giza", "Giza Pyramids, Egypt")]},
        },
        {
            "id": "bv-uap", "title": "The honest question — is there a UAP pattern here?", "visual": "stats",
            "caption": "We ran the numbers. The honest answer matters more than the exciting one.",
            "narration": (
                "This platform exists to detect patterns in unidentified-aerial-phenomena reports, so we owe "
                "you the honest result for these very sites — and it is a lesson in itself. "
                "We tested whether UAP reports actually over-concentrate around the Boyne Valley, using a "
                "confound-controlled method: not a raw count, but a lift ratio comparing report density right "
                "at the sites against a matched baseline of the surrounding region. ASSESSED, and this is the "
                "finding: Newgrange and Knowth sit at or slightly BELOW that baseline — a lift near 0.3 to 0.6, "
                "where 1.0 means no effect. In plain terms, there is no measurable over-concentration of UAP "
                "reports at the Boyne Valley beyond what the local population and reporting activity already "
                "explain. "
                "An earlier, coarser version of this test appeared to show a signal; when we tightened the "
                "method, the signal dissolved. We report that openly, because a tool that only tells you what "
                "you hope to hear is worthless. KNOWN facts: the astronomy, the acoustics, the engineering, the "
                "mythology — all real, all remarkable. ASSESSED: the modern UAP link, at these specific sites, "
                "is not supported by the data. Both of those statements can be true at once, and holding them "
                "together honestly is exactly the point of standing here with clear eyes."),
            "visualData": {"headline_stat": 0.3, "stat_label": "Newgrange UAP lift ratio (1.0 = no effect; below = fewer than baseline)",
                           "sub_stats": [{"k": "Knowth lift", "v": 0.59}, {"k": "Giza lift (small sample)", "v": 4.8},
                                         {"k": "Honest verdict", "v": 0}]},
        },
        {
            "id": "bv-visit", "title": "How to visit — what to look for on the ground", "visual": "checklist",
            "caption": "Your field guide for the Bend of the Boyne.",
            "narration": (
                "Finally, the practical part — how to get the most from actually standing here. "
                "At Newgrange: access to the chamber is by guided tour from the Bru na Boinne Visitor Centre, "
                "and the true winter-solstice illumination is a lottery — but they simulate it on every tour. "
                "Find kerbstone K1 at the entrance and study the triple spiral; stand in the chamber and notice "
                "how sound behaves. At Knowth: you cannot enter the passages, but the kerbstones are the prize "
                "— walk the perimeter and compare the lunar crescents on the west with the solar rayed-circles "
                "on the east. At Dowth: quieter, less managed, aligned to the solstice sunset. At the Hill of "
                "Tara: free to roam — touch the Lia Fail, the standing stone said to cry out for the true king, "
                "and look for the earthworks of a landscape that geophysics shows is far larger than the eye "
                "sees. At Loughcrew, if you make it, the equinox beam in Cairn T is the oldest light-show on "
                "Earth. "
                "Carry two ideas with you. First, KNOWN and ASSESSED are different — enjoy the mythology, but "
                "know which is which. Second, the marvel here needs no aliens: people with no metal and no "
                "wheel tracked the heavens across centuries and wrote it in stone. That is the real wonder of "
                "the Boyne."),
            "visualData": {"play_steps": [
                {"verb": "NEWGRANGE", "action": "Guided tour from Bru na Boinne centre; find kerbstone K1 triple spiral; feel the chamber acoustics.", "produces": "KNOWN"},
                {"verb": "KNOWTH", "action": "Walk the kerb: lunar crescents to the west, solar rayed-circles to the east.", "produces": "KNOWN"},
                {"verb": "DOWTH", "action": "Quieter; winter-solstice SUNSET alignment; the dusk to Newgrange's dawn.", "produces": "KNOWN"},
                {"verb": "TARA", "action": "Free to roam; touch the Lia Fail; look for the buried landscape geophysics revealed.", "produces": "KNOWN"},
                {"verb": "LOUGHCREW", "action": "If open: the equinox sunrise beam across Cairn T — 300 years older than Newgrange.", "produces": "KNOWN"},
            ], "confidence_ladder": [
                {"wep": "Enjoy freely", "when": "The astronomy, engineering, acoustics — all measured and KNOWN"},
                {"wep": "Hold as tradition", "when": "The Tuatha De Danann mythology — real folklore, not history"},
                {"wep": "Set aside", "when": "A UAP link at these sites — not supported by the data"},
            ]},
        },
    ]

    # word counts + est seconds (top-level chapters AND deep sub-chapters)
    total = 0
    for ch in chapters:
        w = len((ch.get("narration") or "").split())
        ch["words"] = w
        ch["est_seconds"] = round(w / 150.0 * 60)
        total += w
        for d in ((ch.get("visualData") or {}).get("deep") or []):
            dw = len((d.get("narration") or "").split())
            d["words"] = dw
            d["est_seconds"] = round(dw / 150.0 * 60)

    dossier = {
        "id": "boyne-valley",
        "title": "The Boyne Valley",
        "subtitle": "Ireland's ancient sky-sites — astronomy, mythology, and an honest look for UAP",
        "signature": "ancient-mysteries",
        "firing_total": 57,   # UAP reports within 60km of the Boyne (from convergence)
        "sources": 1,
        "countries": 2,
        "narration_words": total,
        "est_runtime_min": round(total / 150.0),
        "chapters": chapters,
        "landmark_cases": [],
        "note": ("Field companion for the Boyne Valley. Astronomy/engineering/acoustics are KNOWN "
                 "(documented); mythology is labelled as tradition; the UAP link is reported honestly "
                 "(at/below baseline). Grounded in tier2_deep_research.json + archon-crosswalk.json + "
                 "uap_convergence_results.json."),
    }

    obj.setdefault("dossiers", [])
    obj["dossiers"] = [d for d in obj["dossiers"] if d.get("id") != "boyne-valley"] + [dossier]

    with open(DOSSIER_JS, "w", encoding="utf-8") as f:
        f.write("// UAP Pattern Dossiers - documentary + play + AI investigator, grounded in the live signal.\n")
        f.write("window.UAP_DOSSIERS = " + json.dumps(obj, ensure_ascii=False) + ";\n")
    print(f"Appended dossier 'The Boyne Valley' ({len(chapters)} chapters, ~{dossier['est_runtime_min']} min, "
          f"{total} words). Total dossiers now: {len(obj['dossiers'])}")


if __name__ == "__main__":
    main()
