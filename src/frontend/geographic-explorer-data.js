/**
 * Geographic Explorer — Merged Site Data
 * Generated: 2026-08-03
 * Sources:
 *   - src/data/conspiracy-seed/irish_sacred_sites/irish_ancient_sites.json
 *   - src/data/conspiracy-seed/irish_sacred_sites/irish_ancient_sites_continued.json
 *   - src/data/conspiracy-seed/irish_sacred_sites/tier2_deep_research.json
 *
 * Constants:
 *   GEO_SITES          — array of all sites (merged from files 1 + 2)
 *   GEO_DEEP_RESEARCH  — object keyed by site id (from tier2)
 *   GEO_CROSS_PATTERNS — cross-site patterns + global connections
 *   GEO_REGIONS        — hierarchical region lookup for sidebar
 */

// =============================================================================
// GEO_SITES — All 13 Irish sacred sites merged into a single array
// =============================================================================

const GEO_SITES = [
  {
    id: "irl-001",
    name: "Newgrange (Sí an Bhrú)",
    category: "passage_tombs",
    county: "Meath",
    region: "Boyne Valley",
    coordinates: { lat: 53.6947, lon: -6.4754 },
    age_years: 5200,
    date_built: "3200 BC",
    unesco: true,
    description: "Passage tomb older than Stonehenge and the Giza pyramids. Precisely aligned so winter solstice sunrise penetrates a roofbox and illuminates the inner chamber for 17 minutes.",
    mysteries: [
      "Solar alignment accurate to within 1 degree over 5200 years",
      "200,000 tons of material moved without wheels or metal tools",
      "Quartz facade required transporting stones 80km from Wicklow mountains",
      "Triple-spiral carved art has no known precedent or explanation",
      "Chamber remains completely waterproof after 5200 years",
      "Acoustic resonance at 110Hz matches other ancient sites worldwide"
    ],
    taxonomy_matches: {
      astronomical_correlation: 0.95,
      advanced_technology: 0.85,
      geographic_alignment: 0.80,
      anomalous_artifacts: 0.75,
      lost_knowledge: 0.70
    },
    cross_domain_connections: [
      "Same 110Hz resonance found in Maltese Hypogeum and King's Chamber at Giza",
      "Triple-spiral motif appears in Neolithic Malta and Bronze Age Crete",
      "Solstice alignment parallels Angkor Wat and Karnak Temple"
    ],
    field_notes: "Visit at dawn. Listen for acoustic resonance in the chamber. Photograph the triple-spiral at kerbstone K1 and the roofbox mechanism.",
    ancient_aliens_episode: "Season 7, Episode 3 - Aliens Among Us"
  },
  {
    id: "irl-002",
    name: "Knowth",
    category: "passage_tombs",
    county: "Meath",
    region: "Boyne Valley",
    coordinates: { lat: 53.7014, lon: -6.4908 },
    age_years: 5200,
    date_built: "3200 BC",
    unesco: true,
    description: "Twin-passage tomb with the largest collection of megalithic art in Western Europe. East passage catches equinox sunrise, west passage catches equinox sunset.",
    mysteries: [
      "Over 300 decorated stones — more megalithic art than anywhere in Europe",
      "Dual passage alignment to both equinoxes (sunrise AND sunset)",
      "Lunar calendar carved into kerbstones (18.6-year Metonic cycle)",
      "Engineering of dual passages within same mound without intersection",
      "Some carvings appear to be star maps"
    ],
    taxonomy_matches: {
      astronomical_correlation: 0.95,
      anomalous_artifacts: 0.90,
      advanced_technology: 0.80,
      lost_knowledge: 0.85
    },
    cross_domain_connections: [
      "Lunar calendar tracking parallels Babylonian astronomy",
      "Art motifs match passage tomb art in Gavrinis, Brittany — same culture?",
      "Dual solstice/equinox alignment system mirrors Angkor complex"
    ],
    field_notes: "Study the kerbstone carvings closely — some researchers claim they encode lunar standstill cycles. Compare with Newgrange spiral art.",
    ancient_aliens_episode: null
  },
  {
    id: "irl-003",
    name: "Dowth (Dubhadh)",
    category: "passage_tombs",
    county: "Meath",
    region: "Boyne Valley",
    coordinates: { lat: 53.7033, lon: -6.4500 },
    age_years: 5200,
    date_built: "3200 BC",
    unesco: true,
    description: "Third great passage tomb of the Boyne Valley. Aligned to winter solstice SUNSET (Newgrange catches sunrise). Together they bracket the shortest day.",
    mysteries: [
      "Sunset alignment complements Newgrange sunrise — deliberate system",
      "Underground souterrain tunnel connects to main chamber",
      "Site name means 'darkness' — paired with Newgrange (light)",
      "Less excavated than Newgrange — may contain undiscovered chambers"
    ],
    taxonomy_matches: {
      astronomical_correlation: 0.90,
      geographic_alignment: 0.85
    },
    cross_domain_connections: [],
    field_notes: "Visit at sunset on a clear day. The light/dark pairing with Newgrange suggests a unified cosmological system across the valley.",
    ancient_aliens_episode: null
  },
  {
    id: "irl-004",
    name: "Hill of Tara (Teamhair)",
    category: "hilltop_ceremonial",
    county: "Meath",
    region: "Boyne Valley",
    coordinates: { lat: 53.5789, lon: -6.6117 },
    age_years: 5000,
    date_built: "3000 BC+",
    unesco: false,
    description: "Sacred seat of the High Kings of Ireland. 142 kings reigned here. Contains the Mound of Hostages (passage tomb), Lia Fáil (Stone of Destiny), and concentric ring forts. Described as an entrance to the Otherworld.",
    mysteries: [
      "Lia Fáil (Stone of Destiny) — said to cry out when the rightful king touches it",
      "Line of sight connects Tara to Newgrange, Slane, and Loughcrew — ley line?",
      "Mound of Hostages contains a passage aligned to cross-quarter days (Samhain/Imbolc)",
      "Aerial surveys reveal previously unknown structures beneath surface",
      "Legend of the Tuatha Dé Danann — divine race who ruled from Tara before humans"
    ],
    taxonomy_matches: {
      geographic_alignment: 0.90,
      lost_knowledge: 0.85,
      astronomical_correlation: 0.75
    },
    cross_domain_connections: [
      "Cross-quarter day alignment (Samhain) parallels Celtic calendar used across Europe",
      "Ley line concept mirrors Chinese dragon lines and Australian songlines",
      "Concept of 'divine kings' parallels Sumerian king lists and Egyptian pharaohs"
    ],
    field_notes: "Stand at Lia Fáil. Look north toward Newgrange — you should see the Boyne Valley monuments. Note the ring forts from the air (photos from above reveal patterns invisible from ground).",
    ancient_aliens_episode: null
  },
  {
    id: "irl-005",
    name: "Hill of Slane",
    category: "hilltop_ceremonial",
    county: "Meath",
    region: "Boyne Valley",
    coordinates: { lat: 53.7108, lon: -6.5439 },
    age_years: 5000,
    date_built: "Pre-3000 BC",
    unesco: false,
    description: "Sacred hill with direct line of sight to Hill of Tara (16km). Site where St. Patrick lit the paschal fire in 433 AD, directly challenging the pagan king at Tara. Pre-Christian sacred site claimed by Fir Bolg legends.",
    mysteries: [
      "Direct intervisibility with Tara — fires lit here could be seen at Tara and vice versa",
      "Signal fire communication system between hilltop sites",
      "Pre-Christian burial site predates known history",
      "Patrick deliberately chose this hill to challenge pagan power — why THIS location?"
    ],
    taxonomy_matches: {
      geographic_alignment: 0.85,
      lost_knowledge: 0.70
    },
    cross_domain_connections: [],
    field_notes: "Look toward Tara from the summit. The visual connection between hills suggests a deliberate communication network.",
    ancient_aliens_episode: null
  },
  {
    id: "irl-006",
    name: "Loughcrew Cairns (Sliabh na Caillaí)",
    category: "passage_tombs",
    county: "Meath",
    region: "Boyne Valley",
    coordinates: { lat: 53.7447, lon: -7.1178 },
    age_years: 5500,
    date_built: "3500 BC",
    unesco: false,
    description: "Hilltop complex of 30+ passage tombs spread across four peaks. Cairn T aligned to equinox sunrise. Extensive megalithic art including possible astronomical records. Named 'Mountain of the Hag' — associated with the divine crone Cailleach.",
    mysteries: [
      "Cairn T equinox alignment illuminates backstone carvings at sunrise",
      "30+ cairns on four peaks — why this specific arrangement?",
      "Carved stone inside Cairn T appears to be a sundial or calendar",
      "Older than Newgrange by 300 years — possibly the prototype",
      "Associated with Cailleach (divine hag) — creation goddess who shaped the land"
    ],
    taxonomy_matches: {
      astronomical_correlation: 0.90,
      geographic_alignment: 0.85,
      anomalous_artifacts: 0.75,
      lost_knowledge: 0.80
    },
    cross_domain_connections: [],
    field_notes: "Visit Cairn T at equinox if possible. The light penetration on the carved backstone is dramatic. Less tourist traffic than Newgrange.",
    ancient_aliens_episode: null
  },
  {
    id: "irl-007",
    name: "Poulnabrone Dolmen",
    category: "dolmens_portals",
    county: "Clare",
    region: "The Burren",
    coordinates: { lat: 53.0489, lon: -9.1403 },
    age_years: 5800,
    date_built: "3800 BC",
    unesco: false,
    description: "Iconic portal tomb in the Burren limestone landscape. 33 bodies interred over 600 years. Name means 'hole of sorrows.' Capstone weighs 5 tons, balanced on thin uprights.",
    mysteries: [
      "5-ton capstone balanced precisely on razor-thin uprights for 5800 years",
      "Portal orientation — deliberate alignment or functional?",
      "600 years of continuous use as burial site — multigenerational sacred contract",
      "Burren landscape itself is anomalous — limestone karst with Arctic and Mediterranean plants coexisting",
      "Described as a 'doorway between worlds' by archaeologists"
    ],
    taxonomy_matches: {
      advanced_technology: 0.70,
      anomalous_artifacts: 0.75,
      lost_knowledge: 0.65
    },
    cross_domain_connections: [],
    field_notes: "The Burren landscape around it is as mysterious as the dolmen itself. Photograph the capstone angle — how is it balanced?",
    ancient_aliens_episode: null
  },
  {
    id: "irl-008",
    name: "Skellig Michael",
    category: "monastic_islands",
    county: "Kerry",
    region: "Kerry Coast",
    coordinates: { lat: 51.7717, lon: -10.5386 },
    age_years: 1400,
    date_built: "6th-8th century AD",
    unesco: true,
    description: "Dramatic twin-peaked island 12km off the Kerry coast. Early Christian monastery built on impossible terrain — 600 stone steps carved into rock face. Beehive huts survive intact. Site of extreme ascetic practice.",
    mysteries: [
      "How were building materials transported up 600 vertical feet of exposed rock?",
      "Beehive huts use corbelled construction without mortar — still waterproof after 1400 years",
      "Why choose the most extreme, dangerous location possible for a monastery?",
      "Pre-Christian use suggested by astronomical alignments in the monastery layout",
      "South peak has a hermitage even MORE inaccessible — for what purpose?"
    ],
    taxonomy_matches: {
      advanced_technology: 0.70,
      geographic_alignment: 0.65,
      lost_knowledge: 0.60
    },
    cross_domain_connections: [
      "Extreme isolation parallels Mount Athos, Meteora, Tibetan cliff monasteries",
      "Corbelled construction technique identical to Newgrange chamber (3000 years older)",
      "Michael Line ley line concept — Skellig Michael to Mont St Michel to Monte Sant'Angelo"
    ],
    field_notes: "Weather-dependent boat access. The climb is steep but manageable. Look for the pre-Christian stonework underlying the monastery.",
    ancient_aliens_episode: null
  },
  {
    id: "irl-009",
    name: "Carrowmore Megalithic Complex",
    category: "megalithic_complexes",
    county: "Sligo",
    region: "Sligo / Carrowmore",
    coordinates: { lat: 54.2500, lon: -8.5200 },
    age_years: 5800,
    date_built: "3800 BC",
    unesco: false,
    description: "One of the four major passage tomb complexes in Ireland. 30+ tombs centered around a central monument (Listoghil). Possibly older than Newgrange. All monuments oriented toward Knocknarea (Queen Maeve's cairn).",
    mysteries: [
      "Potentially the oldest megalithic complex in Ireland (some dates 4600 BC)",
      "All satellite tombs oriented toward Knocknarea mountain — deliberate focal point",
      "Central monument Listoghil aligned to Samhain sunrise",
      "Scale suggests large organized society coordinating construction over centuries",
      "Connection to Carrowkeel complex 30km south — paired sites?"
    ],
    taxonomy_matches: {
      geographic_alignment: 0.90,
      astronomical_correlation: 0.80,
      advanced_technology: 0.70
    },
    cross_domain_connections: [],
    field_notes: "Walk the full complex. Note how every tomb 'looks at' Knocknarea. Then drive to Knocknarea and climb to Maeve's cairn for the reverse view.",
    ancient_aliens_episode: null
  },
  {
    id: "irl-010",
    name: "Knocknarea (Queen Maeve's Cairn)",
    category: "hilltop_ceremonial",
    county: "Sligo",
    region: "Sligo / Carrowmore",
    coordinates: { lat: 54.2594, lon: -8.5778 },
    age_years: 5500,
    date_built: "3500 BC",
    unesco: false,
    description: "Massive unopened cairn atop Knocknarea mountain. 40,000 tons of loose stone. Never excavated. Tradition says Queen Maeve is buried standing upright facing her enemies. Focal point for entire Carrowmore complex.",
    mysteries: [
      "40,000 tons of stone carried UP a 327m mountain — immense labor",
      "Never excavated — what's inside remains unknown",
      "Legend says Maeve buried standing, facing north toward Connacht enemies",
      "Visible from the entire Sligo region — ancient landmark/beacon",
      "Unopened passage tomb may predate Maeve legends by 3000+ years"
    ],
    taxonomy_matches: {
      advanced_technology: 0.80,
      lost_knowledge: 0.85,
      geographic_alignment: 0.75
    },
    cross_domain_connections: [],
    field_notes: "Climb the mountain (1 hour). The cairn is massive and unexcavated. Add a stone to the top per tradition. The views connect all the Sligo sites visually.",
    ancient_aliens_episode: null
  },
  {
    id: "irl-011",
    name: "Carrowkeel Passage Tombs",
    category: "passage_tombs",
    county: "Sligo",
    region: "Sligo / Carrowmore",
    coordinates: { lat: 54.0644, lon: -8.3678 },
    age_years: 5400,
    date_built: "3400 BC",
    unesco: false,
    description: "Fourteen passage tombs on Bricklieve Mountains. Cairn G has a roofbox similar to Newgrange — catching summer solstice sunset. Remote and rarely visited.",
    mysteries: [
      "Cairn G roofbox parallels Newgrange (built at same time, 100km apart)",
      "Summer solstice sunset alignment (Newgrange catches winter sunrise — complementary)",
      "Remote mountain location — why build here when valleys are more accessible?",
      "Antler pin deposits suggest ritual use, not just burial",
      "Village of stone huts nearby — who lived here and served the tombs?"
    ],
    taxonomy_matches: {
      astronomical_correlation: 0.90,
      geographic_alignment: 0.80,
      advanced_technology: 0.75
    },
    cross_domain_connections: [
      "Roofbox technology appears independently at Newgrange (100km away) — shared knowledge",
      "Summer/winter solstice pairing mirrors the Dowth/Newgrange sunrise/sunset system",
      "Mountain-top tomb placement parallels Etruscan tumuli and Japanese kofun"
    ],
    field_notes: "Remote site — bring boots. Cairn G is accessible and you can crawl inside. Visit near summer solstice for the light effect.",
    ancient_aliens_episode: null
  },
  {
    id: "irl-012",
    name: "Dún Aonghasa (Dun Aengus)",
    category: "hilltop_ceremonial",
    county: "Galway (Aran Islands)",
    region: "Connemara / Aran Islands",
    coordinates: { lat: 53.1258, lon: -9.7683 },
    age_years: 3100,
    date_built: "1100 BC",
    unesco: false,
    description: "Dramatic cliff-edge stone fort on Inis Mór, Aran Islands. Semi-circular (half the fort eroded into the sea). Chevaux-de-frise stone defenses. Positioned at the edge of the known world — facing the Atlantic.",
    mysteries: [
      "Why build a fort on a cliff edge with no escape route?",
      "Chevaux-de-frise defensive stones — a technique also found in Spain and Scotland",
      "Acoustic properties of the cliff face amplify sound from the sea",
      "Positioned at westernmost point — gateway to the otherworld?",
      "Original full circle may have been complete before cliff erosion"
    ],
    taxonomy_matches: {
      geographic_alignment: 0.75,
      advanced_technology: 0.70,
      lost_knowledge: 0.65
    },
    cross_domain_connections: [],
    field_notes: "Take the ferry to Inis Mór. The walk to the cliff edge is vertigo-inducing. Note the chevaux-de-frise field — unusual defensive technology.",
    ancient_aliens_episode: null
  },
  {
    id: "irl-013",
    name: "Drombeg Stone Circle",
    category: "megalithic_complexes",
    county: "Cork",
    region: "West Cork",
    coordinates: { lat: 51.5647, lon: -9.0886 },
    age_years: 3100,
    date_built: "1100 BC",
    unesco: false,
    description: "Recumbent stone circle aligned to winter solstice sunset. 17 stones originally, 13 surviving. Adjacent fulacht fiadh (ancient cooking/bathing site). Known as 'The Druid's Altar.'",
    mysteries: [
      "Axis aligned precisely to winter solstice sunset over distant hills",
      "Recumbent stone (flat altar stone) faces the setting sun",
      "Human cremation buried at center — sacrifice or honor?",
      "Adjacent fulacht fiadh suggests combined ritual and domestic use",
      "Recumbent circle tradition links Ireland to Aberdeenshire, Scotland — cultural connection"
    ],
    taxonomy_matches: {
      astronomical_correlation: 0.85,
      geographic_alignment: 0.70
    },
    cross_domain_connections: [],
    field_notes: "Visit near winter solstice sunset. The alignment is precise. The nearby fulacht fiadh is worth examining — heated stone technology.",
    ancient_aliens_episode: null
  }
];


// =============================================================================
// GEO_DEEP_RESEARCH — Deep research per site, keyed by short id
// =============================================================================

const GEO_DEEP_RESEARCH = {
  "irl-001": {
    name: "Newgrange",
    acoustic_research: {
      finding: "Chamber resonates at 95-120 Hz with peak at ~110 Hz",
      source: "Princeton PEAR lab (Prof. Robert Jahn); Paul Devereux archaeoacoustics study",
      paper: "Ancient Architectural Acoustic Resonance Patterns and Regional Brain Activity (ResearchGate)",
      global_pattern: "Same 110Hz resonance found at: Hal Saflieni Hypogeum (Malta), Wayland Smithy (England), Cairn L at Carrowkeel (Ireland). All ancient chambers cluster 95-120Hz.",
      neuroscience: "EEG study showed 110Hz suppresses left-hemisphere language processing, shifting brain into pre-verbal receptive state. Matches meditation/trance states.",
      implication: "Chambers were not just burial sites but frequency-engineered resonance instruments designed to alter consciousness"
    },
    construction_analysis: {
      quartz_source: "White quartz cobbles from Wicklow Mountains, ~70km south. Dark granodiorite from Mourne Mountains, ~80km north. Gabbro from Cooley Mountains.",
      controversy: "O'Kelly's 1962-75 reconstruction of quartz facade is disputed. Cooney (2006) and Eriksen (2006) argue quartz was a ground-level platform, not a vertical wall.",
      weight: "200,000+ tons of material. Largest stones ~5 tons each.",
      waterproofing: "Roof system uses overlapping stone slabs with drainage channels. Chamber completely dry after 5,200 years. No modern equivalent without synthetic materials.",
      roofbox: "Precision aperture above entrance: 1m wide, 0.25m high. Aligned to solar azimuth 134.5° (winter solstice sunrise). Accurate within ~1° over 5 millennia."
    },
    dating_controversy: {
      official: "3200 BC (radiocarbon dating of soil/organic material)",
      challenges: "Some researchers argue the astronomical alignment implies construction over centuries of observation. The 18.6-year lunar standstill cycle at Knowth requires multi-generational tracking.",
      comparison: "500 years older than Giza pyramids. 1000 years older than Stonehenge."
    },
    suppression_patterns: {
      finding: "Knowth and Newgrange carvings interpreted as astronomical records since Brennan (1983) but mainstream archaeology resists astronomical interpretations as 'fringe'",
      academic_gatekeeping: "Martin Brennan's 'The Stars and the Stones' (1983) was dismissed by establishment archaeology despite subsequently verified equinox/solstice alignments",
      taxonomy_match: "information_asymmetry, expert_divergence"
    }
  },

  "irl-002": {
    name: "Knowth",
    lunar_calendar: {
      finding: "Kerbstone K52 interpreted as encoding astronomical cycles — possibly the 18.6-year Metonic/lunar standstill cycle",
      source: "Mythical Ireland research; journal paper: Knowth passage-grave in Ireland: An instrument of precision astronomy? (Journal of Lithic Studies, 2018)",
      arxiv_paper: "Calendrical Interpretation of Spirals in Irish Megalithic Art (arXiv:1903.07393)",
      detail: "Spirals may encode time periods: single spiral = 1 month, double spiral = 1 year, triple spiral at Newgrange = unknown larger cycle",
      lunar_map: "Orthostat in eastern passage interpreted by Prof. P.J. Stooke (UWO Canada) as world's oldest map of lunar maria (surface features visible to naked eye)"
    },
    megalithic_art: {
      scale: "25% of ALL megalithic art in Western Europe is at Knowth. Over 300 decorated stones.",
      types: "Spirals, lozenges, serpentines, crescents, U-motifs, rayed circles",
      western_vs_eastern: "Western kerbstones dominated by lunar imagery (crescents, arcs). Eastern kerbstones show solar imagery (rayed circles). Matches dual passage alignment.",
      interpretation_schools: "Four academic camps: (1) decorative only, (2) entoptic/trance-induced, (3) astronomical/calendrical, (4) territorial/social markers"
    }
  },

  "irl-003": {
    name: "Dowth (Dubhadh — House of Darkness)",
    solstice_mechanism: {
      finding: "South chamber aligned to winter solstice SUNSET. At sunset, light moves along left side of 3m passage into circular chamber. A convex central stone REFLECTS sunlight into a dark recess, illuminating decorated stones.",
      source: "newgrange.com; Mythical Ireland (Anthony Murphy)",
      pairing: "Newgrange catches winter solstice SUNRISE, Dowth catches SUNSET same day. Together they bracket the shortest day — dawn to dusk.",
      public_access: "Limited — OPW sometimes opens for solstice sunset. Permission required otherwise."
    },
    structure: {
      passages: "Two known passages on south-western side. North passage: 14m long, cruciform chamber with 3m corbelled roof. South passage: 3m short, round chamber.",
      undiscovered: "Less excavated than Newgrange/Knowth. May contain additional chambers.",
      name_meaning: "Dubhadh = darkness. Paired with Newgrange (Sí an Bhrú = palace of light). Light/dark duality."
    }
  },

  "irl-004": {
    name: "Hill of Tara (Teamhair)",
    mound_of_hostages: {
      finding: "Passage aligned to CROSS-QUARTER days — sunrise at Samhain (Nov 1) and Imbolc (Feb 1). These are the days midway between equinox and solstice.",
      source: "knowth.com; UCD School of Archaeology",
      significance: "This is the ONLY known passage tomb aligned to cross-quarter days. All others target solstices or equinoxes. Suggests a more sophisticated calendar understanding.",
      contents: "Richest collection of human bone and funerary artefacts from any megalithic tomb in Europe. In use from 3000 BC to 1700 BC (1300 years continuous).",
      academic: "UCD School of Archaeology ongoing research"
    },
    lia_fail: {
      finding: "Standing stone said to 'cry out' when touched by the rightful king. Stone of Destiny associated with inauguration of 142 High Kings.",
      parallel: "Stone of Scone (Scotland), Jacob's Pillow Stone (Bible) — multiple cultures have 'kingship stones' that validate sovereignty",
      current: "Still stands on the hill — you can touch it"
    },
    geophysics: {
      finding: "Aerial and geophysical surveys reveal massive previously unknown structures beneath the surface including a huge banquet hall, additional ring forts, and processional avenues",
      source: "Discovery Programme Ireland; Joe Fenwick aerial survey"
    }
  },

  "irl-005": {
    name: "Hill of Slane",
    signal_network: {
      finding: "Direct intervisibility with Hill of Tara (16km). Fire lit on Slane visible from Tara. Patrick's 433 AD fire was a direct visual challenge to the pagan king Laoghaire at Tara.",
      source: "Heritage Ireland; Mythical Ireland",
      network: "Part of a pre-Christian hilltop signal fire network. Tara → Slane → Ward → Dunsany → Skreen form a communication chain.",
      implication: "This is a TECHNOLOGY — long-distance visual communication predating radio by 5000 years"
    },
    pre_christian: {
      finding: "Burial place of Fir Bolg king Sláine (mythology). Sacred significance predates Christianity by millennia.",
      patrick_choice: "Patrick chose Slane specifically because it was visible from Tara. His fire on the pagan sacred hilltop was an act of symbolic warfare."
    }
  },

  "irl-006": {
    name: "Loughcrew Cairns",
    equinox_mechanism: {
      finding: "At equinox sunrise, a narrow beam enters Cairn T passage (8° south of east to account for declination difference between spring/autumn). Light moves across decorated backstone for ~50 minutes, illuminating specific carvings sequentially.",
      discovered_by: "Martin Brennan (1980) — first to photograph the equinox illumination",
      backstone_carvings: "Sun symbols precisely positioned to be 'activated' by the moving light beam. Effectively a 5,000-year-old astronomical display.",
      cross_quarter: "Other cairns in the complex align to Samhain, Imbolc, Beltane, Lughnasadh — the full Celtic calendar"
    },
    age_significance: {
      date: "3500 BC — 300 years OLDER than Newgrange",
      implication: "Loughcrew may be the prototype. The builders perfected their astronomy here before building the grander Boyne Valley monuments."
    }
  },

  "irl-007": {
    name: "Poulnabrone Dolmen",
    excavation: {
      finding: "33 human remains interred over 600 years (3800-3200 BC). 16 adults, 6 children, plus a later Bronze Age infant. Bodies may have been ritually purified by fire before bone deposition.",
      source: "Ann Lynch excavations 1986/1988; Irish Archaeology",
      health: "Most died before age 30. Arthritis common at early age. One adult had a projectile point embedded in hip.",
      artifacts: "Polished stone axe, bone pendant, quartz crystal, flint tools — grave goods suggesting afterlife beliefs"
    },
    engineering: {
      finding: "Capstone (4m × 2.4m) balanced on two portal stones ~1.8m high. Originally covered by a stone cairn — what remains is the 'skeleton.' Uprights NOT wedged into fissures — held in place by capstone weight alone.",
      source: "Burren Geopark; Heritage Ireland",
      name: "Poll na Brón = 'Hole of the Sorrows' or 'Hole of the Quern Stones'",
      burren_context: "Built on 350-million-year-old limestone pavement. The Burren is itself anomalous — Arctic and Mediterranean plants coexist in this karst landscape."
    }
  },

  "irl-008": {
    name: "Skellig Michael",
    michael_line: {
      finding: "Skellig Michael sits on the 'Apollo/St. Michael Axis' — a geographic alignment connecting: Skellig Michael → St. Michael's Mount (Cornwall) → Mont St Michel (France) → Sacra di San Michele (Italy) → Monte Sant'Angelo (Italy) → Delphi (Greece)",
      source: "Sacred Sites (Martin Gray); Jean Richer alignment research",
      implication: "All sites dedicated to St. Michael/Apollo, all on high rocky peaks, all along a single geographic line. Known 'thousands of years before Christianity.' Ancient pilgrimage/energy line?",
      taxonomy_match: "geographic_alignment: 0.95"
    },
    construction: {
      finding: "6 beehive cells (clocháns) with corbelled stone roofs — same technique as Newgrange (3000 years older). No mortar. Still waterproof after 1400 years.",
      source: "Britannica; Smarthistory; UNESCO",
      access: "600+ steps carved into sheer rock. Monastery at 160m elevation. South peak hermitage even higher — only accessible by climbing near-vertical rock face.",
      question: "Why choose the most extreme, dangerous, isolated location in Ireland for a monastery? Extreme asceticism — or was the location itself sacred BEFORE Christianity?"
    },
    pre_christian: {
      evidence: "No definitive pre-Christian structures found. BUT: corbelled construction technique is Neolithic, not Christian. Location on Michael Line predates Christianity. Island naming pattern (Michael = warrior archangel = protection of sacred high places) consistent with Christianizing existing pagan sites."
    }
  },

  "irl-009": {
    name: "Carrowmore Megalithic Complex",
    dating_controversy: {
      official: "3500-3000 BC for most tombs",
      challenge: "Early C14 dates from cremated bone suggest 4600-4100 BC — which would make it the OLDEST megalithic complex in Ireland, predating Newgrange by 1400 years",
      academic_debate: "Dates challenged by Bergh (1995) and Burenhult. Some samples may be contaminated. If valid, Carrowmore rewrites the origin of Irish megaliths.",
      implication: "If 4600 BC, Irish megaliths are contemporary with earliest Mediterranean ones — challenges diffusionist theory"
    },
    orientation_pattern: {
      finding: "All satellite tombs oriented toward Knocknarea mountain. Central monument (Listoghil) aligned to Samhain sunrise.",
      network: "Paired with Carrowkeel (30km south). Both on elevated ground. Both passage tomb clusters. Ritual territory?"
    },
    oldest_megaliths: {
      finding: "Controversial C14 dates from Tomb 4 suggest construction as early as 4600 BC. If valid, Carrowmore predates ALL other Irish megaliths by 1000+ years.",
      academic_debate: "Dates championed by Prof. Göran Burenhult (Swedish excavations 1977-82). Challenged by Irish archaeologists who argue sample contamination.",
      implication: "If 4600 BC is correct, Irish megaliths are contemporary with earliest Mediterranean ones (Sardinia, Portugal). Challenges the 'diffusion from the continent' theory — maybe Ireland was an INDEPENDENT origin point for megalithic culture."
    },
    focal_orientation: {
      finding: "Every satellite tomb oriented toward Knocknarea mountain (4km away). Central monument Listoghil has no kerb on its Knocknarea-facing side — deliberately open toward the mountain.",
      source: "carrowkeel.com; Burenhult excavation reports"
    },
    listoghil: {
      finding: "Central monument, largest and most complex. Aligned to Samhain sunrise. Contains the only decorated stones in the complex. May be the 'mother tomb' that all others reference.",
      roof: "Massive 70-ton roof slab — one of the largest single stones in any Irish tomb"
    }
  },

  "irl-010": {
    name: "Knocknarea (Queen Maeve's Cairn)",
    unopened_mystery: {
      finding: "40,000 tons of loose limestone, 55m wide, 10m high. NEVER excavated. Interior unknown.",
      why_unopened: "Heritage Ireland states 'what is inside should stay there.' Local tradition holds disturbance would bring catastrophe. Also: massive logistical challenge.",
      probable_contents: "Archaeologists believe it covers a Neolithic passage tomb (3000+ BC) predating the Maeve legends by 3,000 years",
      legend: "Queen Maeve (Medb of Connacht) buried standing upright, facing north toward her enemies in Ulster. Warrior queen of the Táin.",
      radar_survey: "No published ground-penetrating radar results. Site too remote and cairn too massive for non-invasive study with current tech."
    },
    construction_mystery: {
      mountain_transport: "30,000-40,000 tons of stone carried UP a 327m mountain. No road, no wheel tracks. How?",
      labor_estimate: "Would require thousands of people working for years. Implies highly organized society with surplus labor.",
      focal_point: "Every passage tomb at Carrowmore (4km away) is oriented TOWARD Knocknarea. It was the center of a ritual landscape."
    }
  },

  "irl-011": {
    name: "Carrowkeel Passage Tombs",
    roofbox: {
      finding: "Cairn G has a roofbox mechanism virtually identical to Newgrange — a stone slot above the entrance that admits sunlight. But here it catches SUMMER SOLSTICE SUNSET (Newgrange catches winter solstice sunrise).",
      discovered: "1997 by Martin Byrne",
      source: "newgrange.com; carrowkeel.com; Ancient Origins",
      detail: "Sun enters through roofbox at sunset for ~1 month on either side of midsummer. Only 2 known roofboxes in Ireland — Newgrange and Carrowkeel, 100km apart.",
      implication: "Two sites, same rare technology, complementary solar events (winter sunrise vs summer sunset). Either the same builders or shared technical knowledge across distance."
    },
    village: {
      finding: "Cluster of stone hut foundations near the cairns — a Neolithic village. People LIVED here to serve the tombs.",
      source: "carrowkeel.com; trips.ie",
      antler_deposits: "Antler pin deposits in cairns suggest ritual offerings, not just burial"
    },
    remoteness: {
      question: "Why build 14 passage tombs on a remote mountaintop (Bricklieve Mountains) when valleys are more accessible?",
      possible_answer: "Elevation = closer to sky = closer to ancestors/gods. Same logic as Skellig Michael, Tibetan monasteries, Greek mountaintop temples."
    }
  },

  "irl-012": {
    name: "Dún Aonghasa (Dun Aengus)",
    construction_phases: {
      finding: "Built in stages: inner enclosure ~1100-800 BC (Late Bronze Age), outer walls + chevaux-de-frise added 500-200 BC (Iron Age). Occupied continuously into early medieval period.",
      source: "danielkirkpatrick.co.uk; irisharchaeology.org; trips.ie",
      chevaux_de_frise: "Field of thousands of upright limestone spikes planted in ground — anti-cavalry/anti-infantry barrier. Same technique found in Spain (Castros) and Scotland — shared Atlantic military tradition?"
    },
    mystery_stone: {
      finding: "Features a huge rectangular stone slab inside the fort whose function is unknown. Too large to be a simple altar, too flat to be defensive.",
      source: "go-to-ireland.com"
    },
    purpose_debate: {
      fortress: "Three massive walls, chevaux-de-frise, 100m cliff = extreme defense. But against what enemy, on a remote island?",
      ceremonial: "Some scholars argue it was a ritual/ceremonial center, not primarily defensive. Cliff position faces the setting sun — western 'gateway to the otherworld.'",
      acoustic: "Cliff face amplifies sea sound dramatically. Natural amphitheater effect. Ritual use of natural acoustics?"
    }
  }
};


// =============================================================================
// GEO_CROSS_PATTERNS — Cross-site patterns and global connections
// =============================================================================

const GEO_CROSS_PATTERNS = {
  cross_site_patterns: {
    acoustic_network: "110Hz resonance documented at Newgrange, suggested at Carrowkeel Cairn G, and at passage tombs in Brittany (same culture). Was this a design specification?",
    roofbox_technology: "Only two sites in Ireland have roofbox mechanisms: Newgrange (winter solstice) and Carrowkeel Cairn G (summer solstice). 100km apart, complementary alignments.",
    sequential_building: "Loughcrew (3500 BC) → Newgrange/Knowth/Dowth (3200 BC) → Hill of Tara (3000 BC) — a 500-year construction program moving south to north",
    intervisibility_network: "Tara → Slane → Newgrange → Dowth form a visual communication chain. Signal fires at one could be seen from all others.",
    celtic_calendar_system: "Different sites mark different calendar points: Newgrange (winter solstice), Knowth (equinoxes), Loughcrew (equinoxes + cross-quarters), Carrowkeel (summer solstice), Drombeg (winter solstice sunset). Together they form a COMPLETE astronomical calendar distributed across the landscape."
  },
  global_connections: {
    "110Hz_sites": [
      "Newgrange (Ireland)",
      "Hal Saflieni Hypogeum (Malta)",
      "Wayland Smithy (England)",
      "Chavín de Huántar (Peru)"
    ],
    solstice_alignments: [
      "Newgrange (Ireland)",
      "Karnak Temple (Egypt)",
      "Angkor Wat (Cambodia)",
      "Machu Picchu (Peru)"
    ],
    corbelled_construction: [
      "Newgrange (Ireland, 3200 BC)",
      "Treasury of Atreus (Greece, 1250 BC)",
      "Skellig Michael (Ireland, 600 AD)"
    ],
    passage_tomb_tradition: [
      "Brú na Bóinne (Ireland)",
      "Gavrinis (Brittany)",
      "Maeshowe (Orkney)",
      "Los Millares (Spain)"
    ]
  }
};

// =============================================================================
// GEO_REGIONS — Hierarchical region lookup for sidebar navigation
// =============================================================================

const GEO_REGIONS = {
  "Ireland": {
    "Boyne Valley": ["irl-001", "irl-002", "irl-003", "irl-004", "irl-005", "irl-006"],
    "Sligo / Carrowmore": ["irl-009", "irl-010", "irl-011"],
    "The Burren": ["irl-007"],
    "Kerry Coast": ["irl-008"],
    "Connemara / Aran Islands": ["irl-012"],
    "West Cork": ["irl-013"]
  }
};
