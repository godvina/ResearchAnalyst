// Archon Crosswalk Data
const ARCHON_CROSSWALK = {
  "version": "1.0.0",
  "created": "2026-08-09",
  "description": "Entity-to-Site crosswalk mapping mythological entities to physical locations. Connects Archon Library entities to Geographic Explorer sites.",
  "tuatha_de_danann_to_irish_sites": {
    "description": "Tuatha D\u00c3\u00a9 Danann deities and their associated Irish sacred sites, derived from the Lebor Gab\u00c3\u00a1la \u00c3\u2030renn and archaeological tradition",
    "mappings": [
      {
        "entity": "Dagda",
        "aliases": [
          "The Dagda",
          "Eochaid Ollathair",
          "Ruad Rofhessa"
        ],
        "type": "deity",
        "role": "Father god, chief of the Tuatha D\u00c3\u00a9 Danann",
        "sites": [
          "irl-001_newgrange"
        ],
        "site_names": [
          "Newgrange (Br\u00c3\u00ba na B\u00c3\u00b3inne)"
        ],
        "evidence": "The Dagda's palace is Br\u00c3\u00ba na B\u00c3\u00b3inne (Newgrange). He was tricked out of it by his son Aengus \u00c3\u201cg.",
        "anunnaki_parallel": "Enki/Ea \u00e2\u20ac\u201d wisdom god, father figure, trickster aspect"
      },
      {
        "entity": "Aengus \u00c3\u201cg",
        "aliases": [
          "\u00c3\u201cengus",
          "Aengus Mac \u00c3\u201cc",
          "Mac ind \u00c3\u201cc"
        ],
        "type": "deity",
        "role": "God of youth, love, and poetry",
        "sites": [
          "irl-001_newgrange"
        ],
        "site_names": [
          "Newgrange (Br\u00c3\u00ba na B\u00c3\u00b3inne)"
        ],
        "evidence": "Tricked the Dagda into giving him Newgrange 'for a day and a night' \u00e2\u20ac\u201d which meant forever, since all time is a day and a night.",
        "anunnaki_parallel": "None direct \u00e2\u20ac\u201d closest is Dumuzi (youth/fertility)"
      },
      {
        "entity": "Nuada",
        "aliases": [
          "Nuada Airgetl\u00c3\u00a1m",
          "Nuada of the Silver Hand"
        ],
        "type": "deity",
        "role": "First king of the Tuatha D\u00c3\u00a9 Danann",
        "sites": [
          "irl-004_hill_of_tara"
        ],
        "site_names": [
          "Hill of Tara (Teamhair)"
        ],
        "evidence": "Nuada was king at Tara. Lost his arm at the First Battle of Mag Tuired, disqualifying him from kingship until Dian C\u00c3\u00a9cht made him a silver arm.",
        "anunnaki_parallel": "Anu \u00e2\u20ac\u201d supreme sky deity, king of the gods"
      },
      {
        "entity": "Lugh",
        "aliases": [
          "Lugh L\u00c3\u00a1mhfhada",
          "Lugh of the Long Arm",
          "Samild\u00c3\u00a1nach"
        ],
        "type": "deity",
        "role": "God of skill, master of all arts",
        "sites": [
          "irl-004_hill_of_tara",
          "irl-011_carrowkeel"
        ],
        "site_names": [
          "Hill of Tara",
          "Carrowkeel"
        ],
        "evidence": "Lugh came to Tara and proved mastery of every skill. Festival of Lughnasadh named for him. Associated with Carrowkeel via summer solstice alignments.",
        "anunnaki_parallel": "Marduk \u00e2\u20ac\u201d young god who becomes supreme through skill/combat"
      },
      {
        "entity": "Brigid",
        "aliases": [
          "Brigit",
          "Br\u00c3\u00adg"
        ],
        "type": "deity",
        "role": "Goddess of healing, poetry, and smithcraft",
        "sites": [
          "irl-006_loughcrew"
        ],
        "site_names": [
          "Loughcrew Cairns"
        ],
        "evidence": "Imbolc (Feb 1) is Brigid's festival. Loughcrew's equinox alignment connects to the seasonal cycle Brigid governs. Kildare is her primary site but not in the 13.",
        "anunnaki_parallel": "Ninhursag/Nintu \u00e2\u20ac\u201d mother goddess, healing"
      },
      {
        "entity": "Morrigan",
        "aliases": [
          "The Morrigan",
          "Morr\u00c3\u00adgu",
          "Badb",
          "Macha",
          "Nemain"
        ],
        "type": "deity",
        "role": "Triple goddess of war, fate, and sovereignty",
        "sites": [
          "irl-010_knocknarea"
        ],
        "site_names": [
          "Knocknarea (Queen Maeve's Cairn)"
        ],
        "evidence": "Knocknarea associated with Queen Medb (Maeve), who is likely a euhemerized form of the sovereignty goddess. The Morrigan appears at Rathcroghan cave nearby.",
        "anunnaki_parallel": "Inanna/Ishtar \u00e2\u20ac\u201d war goddess, sexuality, sovereignty"
      },
      {
        "entity": "Manann\u00c3\u00a1n mac Lir",
        "aliases": [
          "Manann\u00c3\u00a1n"
        ],
        "type": "deity",
        "role": "God of the sea and Otherworld",
        "sites": [
          "irl-008_skellig_michael"
        ],
        "site_names": [
          "Skellig Michael"
        ],
        "evidence": "Skellig Michael sits in Manann\u00c3\u00a1n's domain \u00e2\u20ac\u201d the western ocean, gateway to the Otherworld (T\u00c3\u00adr na n\u00c3\u201cg). Island monasteries were built at liminal sea-places.",
        "anunnaki_parallel": "Enki/Ea \u00e2\u20ac\u201d god of the waters, Abzu (underground ocean)"
      },
      {
        "entity": "Dian C\u00c3\u00a9cht",
        "aliases": [
          "Dian Cecht"
        ],
        "type": "deity",
        "role": "God of healing and medicine",
        "sites": [
          "irl-007_poulnabrone"
        ],
        "site_names": [
          "Poulnabrone Dolmen"
        ],
        "evidence": "Poulnabrone's excavation revealed evidence of medical knowledge (healed fractures in burials). Dian C\u00c3\u00a9cht made Nuada's silver arm \u00e2\u20ac\u201d advanced 'technology'.",
        "anunnaki_parallel": "Enki \u00e2\u20ac\u201d wisdom, healing arts"
      },
      {
        "entity": "Boann",
        "aliases": [
          "B\u00c3\u00b3inn"
        ],
        "type": "deity",
        "role": "Goddess of the River Boyne, mother of Aengus",
        "sites": [
          "irl-001_newgrange",
          "irl-002_knowth",
          "irl-003_dowth"
        ],
        "site_names": [
          "Newgrange",
          "Knowth",
          "Dowth"
        ],
        "evidence": "The entire Br\u00c3\u00ba na B\u00c3\u00b3inne complex (Newgrange, Knowth, Dowth) sits in the bend of the River Boyne \u00e2\u20ac\u201d Boann's river. She created it by approaching Nechtan's well.",
        "anunnaki_parallel": "Tiamat \u00e2\u20ac\u201d primeval water goddess"
      },
      {
        "entity": "Crom Cruach",
        "aliases": [
          "Crom Dubh",
          "Cromm Cr\u00c3\u00baaich"
        ],
        "type": "deity",
        "role": "Pre-Christian idol, possibly harvest/underworld deity",
        "sites": [
          "irl-006_loughcrew"
        ],
        "site_names": [
          "Loughcrew Cairns"
        ],
        "evidence": "Crom Cruach's idol reportedly stood at Mag Sl\u00c3\u00a9cht (Plain of Prostration) in Cavan, near the Loughcrew complex. Associated with Samhain and harvest sacrifice.",
        "anunnaki_parallel": "Enlil \u00e2\u20ac\u201d demanding deity who punishes humanity"
      },
      {
        "entity": "Medb",
        "aliases": [
          "Maeve",
          "Queen Maeve",
          "Medb of Connacht"
        ],
        "type": "hero",
        "role": "Warrior queen of Connacht (euhemerized sovereignty goddess)",
        "sites": [
          "irl-010_knocknarea",
          "irl-009_carrowmore"
        ],
        "site_names": [
          "Knocknarea",
          "Carrowmore"
        ],
        "evidence": "Tradition holds Medb buried standing in the cairn atop Knocknarea, facing her Ulster enemies. All Carrowmore tombs oriented toward Knocknarea.",
        "anunnaki_parallel": "Inanna \u00e2\u20ac\u201d warrior queen archetype"
      },
      {
        "entity": "Tuatha D\u00c3\u00a9 Danann",
        "aliases": [
          "People of the Goddess Danu",
          "Tuatha D\u00c3\u00a9"
        ],
        "type": "group",
        "role": "The gods of pre-Christian Ireland, arrived with four treasures",
        "sites": [
          "irl-001_newgrange",
          "irl-002_knowth",
          "irl-003_dowth",
          "irl-004_hill_of_tara",
          "irl-011_carrowkeel"
        ],
        "site_names": [
          "Newgrange",
          "Knowth",
          "Dowth",
          "Hill of Tara",
          "Carrowkeel"
        ],
        "evidence": "After defeat by the Milesians, the Tuatha retreated underground into the s\u00c3\u00addhe (fairy mounds) \u00e2\u20ac\u201d which ARE the passage tombs. Each deity took a mound as their dwelling.",
        "anunnaki_parallel": "Anunnaki \u00e2\u20ac\u201d 'the gods' who came from elsewhere, retreated underground"
      }
    ]
  },
  "anunnaki_to_mesopotamian_sites": {
    "description": "Sumerian/Akkadian deities and their cult centers",
    "mappings": [
      {
        "entity": "Anu",
        "sites": [
          "uruk_eanna"
        ],
        "site_names": [
          "Uruk (Eanna Temple)"
        ],
        "role": "Supreme sky god",
        "irish_parallel": "Nuada (king of gods at Tara)"
      },
      {
        "entity": "Enlil",
        "sites": [
          "nippur_ekur"
        ],
        "site_names": [
          "Nippur (Ekur Temple)"
        ],
        "role": "Storm god, authority, decides fates",
        "irish_parallel": "Crom Cruach (demanding authority deity)"
      },
      {
        "entity": "Enki",
        "aliases": [
          "Ea",
          "Nudimmud"
        ],
        "sites": [
          "eridu_eabzu"
        ],
        "site_names": [
          "Eridu (E-abzu Temple)"
        ],
        "role": "God of wisdom, water, and magic",
        "irish_parallel": "Dagda (wisdom, father figure, trickster)"
      },
      {
        "entity": "Inanna",
        "aliases": [
          "Ishtar"
        ],
        "sites": [
          "uruk_eanna"
        ],
        "site_names": [
          "Uruk (Eanna Temple)"
        ],
        "role": "Goddess of love, war, and sovereignty",
        "irish_parallel": "Morrigan / Medb (war, sovereignty)"
      },
      {
        "entity": "Marduk",
        "sites": [
          "babylon_esagila"
        ],
        "site_names": [
          "Babylon (Esagila Temple)"
        ],
        "role": "Chief god of Babylon, slayer of Tiamat",
        "irish_parallel": "Lugh (young god rises to supremacy through skill)"
      },
      {
        "entity": "Ninhursag",
        "aliases": [
          "Nintu",
          "Mami",
          "Belet-ili"
        ],
        "sites": [
          "kish",
          "tell_al_ubaid"
        ],
        "site_names": [
          "Kish",
          "Tell al-'Ubaid"
        ],
        "role": "Mother goddess, birth goddess",
        "irish_parallel": "Brigid (healing, creation)"
      }
    ]
  },
  "cross_cultural_entity_crosswalk": {
    "description": "Direct entity equivalences across traditions (from archon-build-plan.md)",
    "mappings": [
      {
        "sumerian": "Anu",
        "hebrew": "El/Yahweh",
        "greek": "Zeus/Ouranos",
        "irish": "Dagda/Nuada",
        "hindu": "Brahma",
        "role": "Supreme sky deity"
      },
      {
        "sumerian": "Enlil",
        "hebrew": null,
        "greek": "Zeus (storm)",
        "irish": null,
        "hindu": "Indra",
        "role": "Storm/authority god"
      },
      {
        "sumerian": "Enki (Ea)",
        "hebrew": null,
        "greek": "Prometheus/Poseidon",
        "irish": "Dian C\u00c3\u00a9cht",
        "hindu": "Vishnu",
        "role": "Wisdom, humanity's protector"
      },
      {
        "sumerian": "Ninhursag",
        "hebrew": "Eve (creation)",
        "greek": "Gaia",
        "irish": "Danu",
        "hindu": "Parvati",
        "role": "Mother goddess"
      },
      {
        "sumerian": "Utnapishtim",
        "hebrew": "Noah",
        "greek": "Deucalion",
        "irish": "Fintan",
        "hindu": "Manu",
        "role": "Flood survivor"
      },
      {
        "sumerian": "Anunnaki",
        "hebrew": "Elohim/Nephilim",
        "greek": "Titans/Olympians",
        "irish": "Tuatha D\u00c3\u00a9 Danann",
        "hindu": "Devas",
        "role": "The gods who came from elsewhere"
      },
      {
        "sumerian": "Gilgamesh",
        "hebrew": "Nimrod",
        "greek": "Heracles",
        "irish": "C\u00c3\u00ba Chulainn",
        "hindu": "Arjuna",
        "role": "Semi-divine hero"
      },
      {
        "sumerian": "Inanna/Ishtar",
        "hebrew": null,
        "greek": "Aphrodite/Athena",
        "irish": "Brigid/Morrigan",
        "hindu": "Durga/Lakshmi",
        "role": "War/love goddess"
      },
      {
        "sumerian": "Semjaza (Enochic)",
        "hebrew": "Satan/Samael",
        "greek": "Prometheus",
        "irish": null,
        "hindu": "Ravana",
        "role": "Rebel who brings forbidden knowledge"
      },
      {
        "sumerian": "Nephilim/Giants",
        "hebrew": "Nephilim",
        "greek": "Giants/Titans",
        "irish": "Fomorians",
        "hindu": "Asuras/Rakshasas",
        "role": "Monstrous offspring / enemies of gods"
      }
    ]
  },
  "pattern_site_scores": {
    "description": "Which Archon cross-cultural patterns are most relevant to each Irish site",
    "scores": [
      {
        "site": "irl-001_newgrange",
        "patterns": [
          "arch-004_underground_retreat",
          "arch-006_solar_alignment",
          "arch-007_divine_kingship"
        ],
        "evidence": "Passage tomb = underground dwelling of Dagda/Aengus. Winter solstice roofbox = astronomical precision. Royal inauguration connections."
      },
      {
        "site": "irl-002_knowth",
        "patterns": [
          "arch-006_solar_alignment",
          "arch-005_pre_flood_civilization"
        ],
        "evidence": "Equinox alignment, lunar calendar encoding on kerbstones, oldest lunar map."
      },
      {
        "site": "irl-003_dowth",
        "patterns": [
          "arch-004_underground_retreat",
          "arch-006_solar_alignment"
        ],
        "evidence": "Winter solstice sunset alignment (complementary to Newgrange sunrise). Underground chambers."
      },
      {
        "site": "irl-004_hill_of_tara",
        "patterns": [
          "arch-007_divine_kingship",
          "arch-004_underground_retreat"
        ],
        "evidence": "Seat of High Kings, Lia F\u00c3\u00a1il (Stone of Destiny), Mound of the Hostages passage tomb."
      },
      {
        "site": "irl-006_loughcrew",
        "patterns": [
          "arch-006_solar_alignment"
        ],
        "evidence": "Equinox light mechanism illuminates decorated backstone in Cairn T."
      },
      {
        "site": "irl-008_skellig_michael",
        "patterns": [
          "arch-004_underground_retreat"
        ],
        "evidence": "Island at edge of known world, Michael Line alignment, liminal gateway site."
      },
      {
        "site": "irl-009_carrowmore",
        "patterns": [
          "arch-005_pre_flood_civilization",
          "arch-006_solar_alignment"
        ],
        "evidence": "If 4600 BCE dates valid, oldest megaliths in Ireland. All tombs oriented toward Knocknarea. Samhain alignment."
      },
      {
        "site": "irl-010_knocknarea",
        "patterns": [
          "arch-004_underground_retreat",
          "arch-007_divine_kingship"
        ],
        "evidence": "Unopened cairn (hidden contents), warrior queen burial, focal point of ritual landscape."
      },
      {
        "site": "irl-011_carrowkeel",
        "patterns": [
          "arch-006_solar_alignment",
          "arch-004_underground_retreat"
        ],
        "evidence": "Roofbox similar to Newgrange (summer solstice), 110Hz resonance in chambers."
      }
    ]
  }
};
