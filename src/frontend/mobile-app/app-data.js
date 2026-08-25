// Ancient Mysteries Field Companion — All Data (works offline)
const APP_DATA = {
  sites: [
    {
      name: "Newgrange (Brú na Bóinne)",
      deity: "The Dagda & Aengus Óg",
      date: "3200 BCE",
      tagline: "Winter solstice alignment, 110Hz acoustic resonance, dwelling of the father god",
      audio: "audio/brief_dagda.mp3",
      what_to_look_for: "The roofbox above the entrance — a precision aperture 1m wide × 0.25m high aligned to winter solstice sunrise at azimuth 134.5°. Light penetrates 19m to the back chamber for exactly 17 minutes on Dec 21. Also: the white quartz facade (controversial reconstruction), the 97 kerbstones with spiral art, and the dry chamber roof (no leak in 5,200 years).",
      facts: [
        "500 years older than the Great Pyramid of Giza",
        "1000 years older than Stonehenge",
        "200,000+ tons of material transported without the wheel",
        "Chamber resonates at 95-120 Hz with peak at 110 Hz (same as Hal Saflieni Hypogeum in Malta)",
        "Dagda's palace — he was tricked out of it by his son Aengus who asked for it 'for a day and a night' (which means forever)",
        "After defeat by the Milesians, the Tuatha Dé Danann retreated INTO these mounds"
      ],
      deity_description: "The Dagda — 'The Good God.' Chief of the Tuatha Dé Danann. Father of Brigid, Aengus, and others. Owns a cauldron that never empties, a club that kills with one end and resurrects with the other, and a harp that controls the seasons. His Sumerian parallel is Enki — both are wisdom-trickster-father gods whose dwelling is the most sacred site in their land.",
      global_parallels: [
        {site: "Eridu (E-abzu Temple)", country: "Iraq", parallel_deity: "Enki/Ea", shared_pattern: "Oldest sacred site in region, wisdom-father god's dwelling"},
        {site: "Giza Pyramids", country: "Egypt", parallel_deity: "Osiris (Orion alignment)", shared_pattern: "Stellar/solar alignment, impossibly precise construction"},
        {site: "Göbekli Tepe", country: "Turkey", parallel_deity: "Unknown (pre-dates all known mythology)", shared_pattern: "Predates agriculture, astronomical alignment, voluntarily buried"},
        {site: "Angkor Wat", country: "Cambodia", parallel_deity: "Vishnu", shared_pattern: "Solar equinox alignment, massive construction, sacred geography"}
      ],
      dialogue: {
        entity_a: "Dagda",
        entity_b: "Odin",
        premise: "Both father-gods with magical artifacts, wisdom, and shape-shifting",
        lines: [
          {speaker: "Dagda", text: "I hear you gave an eye for wisdom, Allfather. I merely had to outwit my own son."},
          {speaker: "Odin", text: "An eye at Mímir's well, nine days on the World Tree. What price did you pay?"},
          {speaker: "Dagda", text: "I built a fortress with my own hands while enslaved by Bres. My cauldron never empties, my club kills and resurrects. What does your spear do?"},
          {speaker: "Odin", text: "Gungnir never misses. But tell me — you too retreated underground? We went to Valhalla above. You went below."},
          {speaker: "Dagda", text: "Below, above — what difference? My mound at Brú na Bóinne catches the solstice sun. Your Valhalla catches the souls of the slain. Both are beyond the reach of mortals."},
          {speaker: "Odin", text: "Your people were defeated and chose the underground. Mine face Ragnarök. Both endings. Both also beginnings."}
        ]
      },
      insight: "You're standing inside a structure that was ancient when the pyramids were new. The 110Hz resonance is not accidental — the same frequency appears in Malta's Hypogeum and multiple other Neolithic chambers worldwide. This frequency suppresses language processing in the left brain hemisphere, inducing trance states. These weren't just tombs. They were engineered spaces for altered consciousness."
    },
    {
      name: "Knowth",
      deity: "Lunar calendar encoders",
      date: "3200 BCE",
      tagline: "Dual equinox passages, possible oldest lunar map, 25% of all megalithic art in Western Europe",
      audio: "audio/brief_aengus_og.mp3",
      what_to_look_for: "The eastern and western passages — one aligns to equinox sunrise, the other to equinox sunset (complementary pair). Kerbstone K52 may encode the 18.6-year lunar standstill cycle. Over 300 decorated stones — 25% of ALL megalithic art in Western Europe is at this one site.",
      facts: [
        "Over 300 decorated stones (largest collection of megalithic art in Europe)",
        "Dual passage: east = equinox sunrise, west = equinox sunset",
        "Kerbstone K52 interpreted as encoding astronomical cycles",
        "Prof. Stooke (UWO Canada) identified one orthostat as world's oldest map of lunar surface features",
        "Four academic camps disagree on what the art means: decorative, trance-induced, astronomical, or territorial"
      ],
      deity_description: "Knowth is associated with astronomical knowledge rather than a single deity. The sophistication of its art suggests a priestly/scholarly class encoding celestial observations into stone — a library in spiral form.",
      global_parallels: [
        {site: "Giza Pyramids", country: "Egypt", parallel_deity: "Thoth (wisdom, astronomy)", shared_pattern: "Encoded astronomical knowledge in stone architecture"},
        {site: "Angkor Wat", country: "Cambodia", parallel_deity: "Hindu astronomers", shared_pattern: "Equinox alignment, massive stone library"},
        {site: "Chichén Itzá", country: "Mexico", parallel_deity: "Kukulkan", shared_pattern: "Equinox light phenomenon on stone surface"}
      ],
      dialogue: null,
      insight: "If the spiral art encodes astronomical cycles, then Neolithic Ireland had a system of recording knowledge in stone that predates writing by 2000 years. The question isn't whether they could observe the sky — it's how they transmitted precise knowledge across generations without writing. Oral tradition alone cannot maintain the precision needed for an 18.6-year cycle."
    },
    {
      name: "Hill of Tara (Teamhair)",
      deity: "Nuada & Lugh",
      date: "~3000 BCE onwards",
      tagline: "Seat of the High Kings, Stone of Destiny (Lia Fáil), where Lugh proved mastery of all arts",
      audio: "audio/brief_nuada.mp3",
      what_to_look_for: "The Lia Fáil (Stone of Destiny) — said to cry out beneath every rightful king. The Mound of the Hostages (passage tomb, oldest structure). The banqueting hall outline. This was the political AND spiritual center of Ireland for 3000+ years.",
      facts: [
        "Lia Fáil (Stone of Fal) — one of the Four Treasures brought from the Northern Islands",
        "Mound of the Hostages: passage tomb aligned to Samhain/Imbolc cross-quarter days",
        "Site of the Feis Temro (Festival of Tara) — kingship inauguration",
        "Lugh arrived here and proved mastery of every art to gain entry",
        "Nuada ruled from here until losing his hand disqualified him"
      ],
      deity_description: "Nuada Airgetlám (Silver Hand) — first king of the TDD, lost his arm in battle, replaced with silver prosthetic by Dian Cécht. Gave way to Lugh Samildánach (Master of All Arts) who arrived and proved superiority in every skill. Nuada parallels Anu (supreme sky deity) — legitimate authority. Lugh parallels Marduk — the young god who rises through demonstrated excellence.",
      global_parallels: [
        {site: "Uruk (Eanna Temple)", country: "Iraq", parallel_deity: "Anu — supreme sky god's throne", shared_pattern: "Seat of divine kingship, political-spiritual center"},
        {site: "Babylon (Esagila)", country: "Iraq", parallel_deity: "Marduk — young god takes throne", shared_pattern: "New god proves superiority to claim rule"},
        {site: "Memphis", country: "Egypt", parallel_deity: "Pharaoh as living Horus", shared_pattern: "Divine kingship, god-king rules from sacred site"},
        {site: "Olympus", country: "Greece", parallel_deity: "Zeus overthrows Kronos", shared_pattern: "Younger god displaces older, takes the throne"}
      ],
      dialogue: {
        entity_a: "Lugh",
        entity_b: "Zeus",
        premise: "Both master-of-all-arts / supreme young gods who overthrow older order",
        lines: [
          {speaker: "Lugh", text: "When I came to Tara, the doorkeeper asked my art. I named every one. He said they had a smith, a harper, a champion. I asked: do you have ONE who masters ALL?"},
          {speaker: "Zeus", text: "I didn't need to prove arts. I freed my siblings from our father's belly and won a ten-year war."},
          {speaker: "Lugh", text: "Crude. I killed my grandfather Balor with a sling stone through his evil eye. Precision over force."},
          {speaker: "Zeus", text: "Your grandfather had ONE destructive eye. My father Kronos swallowed gods whole. Scale differs."},
          {speaker: "Lugh", text: "Yet we both took the throne from an older generation that had to fall. Why does every tradition tell this same story?"},
          {speaker: "Zeus", text: "Perhaps because it IS the story. The young must replace the old. The question is whether it happened once, in a place both our peoples remember."}
        ]
      },
      insight: "The 'young god overthrows old order' pattern appears in Ireland (Lugh/Nuada), Greece (Zeus/Kronos), Babylon (Marduk/Anu), and Norse (Odin/Ymir). These four cultures had NO contact. Either this is a universal psychological pattern (every generation displaces the last), or it encodes a shared memory of an actual power transition in deep prehistory."
    },
    {
      name: "Knocknarea (Queen Maeve's Cairn)",
      deity: "Morrigan / Medb",
      date: "~3000 BCE (cairn), Iron Age (Medb legends)",
      tagline: "40,000 tons of stone, NEVER excavated, warrior queen buried standing facing her enemies",
      audio: "audio/brief_medb.mp3",
      what_to_look_for: "The massive cairn visible from everywhere in Sligo. 55m wide, 10m high. Never opened. Tradition says disturbing it brings catastrophe. Every passage tomb at Carrowmore (visible below) is oriented TOWARD this cairn — it was the focal point of the entire ritual landscape.",
      facts: [
        "40,000 tons of loose limestone — NEVER excavated",
        "No published ground-penetrating radar results",
        "Legend: Queen Maeve buried standing, facing north toward Ulster enemies",
        "Probably covers a Neolithic passage tomb predating Maeve legends by 3000 years",
        "Every tomb at Carrowmore (4km away) is oriented toward Knocknarea"
      ],
      deity_description: "The Morrigan / Medb — triple war-sovereignty goddess. Medb of Connacht is likely a euhemerized form of the sovereignty goddess. She is the land itself — whoever 'marries' her rules Ireland. Her parallel is Inanna/Ishtar — both war goddesses who embody sovereignty, both choose who lives, who dies, who rules.",
      global_parallels: [
        {site: "Uruk", country: "Iraq", parallel_deity: "Inanna/Ishtar — war-sovereignty goddess", shared_pattern: "Warrior queen archetype, land = goddess"},
        {site: "Knossos", country: "Greece", parallel_deity: "Goddess worship, labyrinth", shared_pattern: "Unopened/sealed sacred space, feminine power"},
        {site: "Xibalba (concept)", country: "Mexico", parallel_deity: "Underworld lords", shared_pattern: "Sealed realm, forbidden to enter, power within"}
      ],
      dialogue: {
        entity_a: "Morrigan",
        entity_b: "Inanna",
        premise: "Both war/sovereignty goddesses who descend to underworld / realm of the dead",
        lines: [
          {speaker: "Morrigan", text: "I appear as crow over the battlefield. I choose who falls. The land is mine to give."},
          {speaker: "Inanna", text: "I descended through seven gates, stripped at each one, died and hung on a hook. But I returned. Did you?"},
          {speaker: "Morrigan", text: "I didn't need to die. I mated with the Dagda at the ford before battle — that IS the descent. Sex and death in one act."},
          {speaker: "Inanna", text: "My husband Dumuzi I gave to the underworld as my replacement. Someone must always go down."},
          {speaker: "Morrigan", text: "On the cairn above Sligo, they say my warrior form still stands. Facing north. Forty thousand tons of stone and no one dares to look inside."},
          {speaker: "Inanna", text: "The ways of the underworld are perfect. They may not be questioned."}
        ]
      },
      insight: "This cairn has never been opened in the archaeological record. Whatever is inside — passage tomb, burial chamber, nothing — has been sealed for 5000 years under 40,000 tons of stone that someone carried UP a 327m mountain. The labor investment alone implies enormous significance. The ritual landscape of Carrowmore below is entirely organized around this point. Something here mattered more than anything else in Neolithic Sligo."
    },
    {
      name: "Skellig Michael",
      deity: "Manannán mac Lir",
      date: "6th-8th century CE (monastery), site much older",
      tagline: "Island at the edge of the world, Michael Line alignment, gateway to the Otherworld",
      audio: "audio/brief_manannan_mac_lir.mp3",
      what_to_look_for: "The impossible stairway (600 steps cut into rock). The beehive huts (corbelled stone, no mortar, still waterproof). The location itself — 12km off the coast, visible only in clear weather. This is where the known world ends and the Otherworld begins.",
      facts: [
        "12km off Kerry coast, Atlantic Ocean",
        "Part of the 'Michael Line' — a ley line running Skellig → St Michael's Mount (England) → Mont Saint-Michel (France) → Sacra di San Michele (Italy) → more",
        "All Michael Line sites are: islands or coastal promontories, dedicated to the archangel Michael, built on pre-Christian sacred sites",
        "Manannán's domain — the western ocean, gateway to Tír na nÓg (Land of the Young)",
        "Used as Ahch-To in Star Wars: The Last Jedi (Luke's exile island)"
      ],
      deity_description: "Manannán mac Lir — god of the sea and the Otherworld. He controls the boundary between worlds. Skellig sits in his waters, a liminal place at the threshold. His parallel is Enki of Eridu — also god of the waters, also guardian of the Abzu (underground ocean), also master of the boundary between realms.",
      global_parallels: [
        {site: "Eridu", country: "Iraq", parallel_deity: "Enki — god of the Abzu (underground waters)", shared_pattern: "Water deity, boundary guardian, liminal sacred site"},
        {site: "Mont Saint-Michel", country: "France", parallel_deity: "Archangel Michael", shared_pattern: "Island monastery, Michael Line, pre-Christian sacred site"},
        {site: "Mount Athos", country: "Greece", parallel_deity: "Monastic tradition", shared_pattern: "Remote peninsula monastery, edge-of-world sacred geography"},
        {site: "Potala Palace", country: "Tibet", parallel_deity: "Buddhist sacred mountain", shared_pattern: "Elevated sacred site, spiritual gateway, extreme isolation"}
      ],
      dialogue: null,
      insight: "The Michael Line connects sacred sites across Europe in a suspiciously straight line from Ireland to Israel. Each site: (a) is on a coastal promontory or island, (b) was sacred BEFORE Christianity, (c) was re-dedicated to the archangel Michael (slayer of the dragon/serpent). The pre-Christian layer at each site suggests the line predates its Christian naming. What was being marked?"
    },
    {
      name: "Loughcrew Cairns",
      deity: "Brigid / Crom Cruach",
      date: "~3300 BCE",
      tagline: "Equinox light mechanism, 360° hilltop views, Cairn T backstone illumination",
      audio: "audio/brief_brigid.mp3",
      what_to_look_for: "Cairn T — on the equinox (March 21 / Sept 23), sunlight enters the passage and illuminates the carved backstone for ~50 minutes. The carvings include sun symbols, radial patterns. The hilltop location gives 360° views — visible from/to Tara, Knowth, Dowth.",
      facts: [
        "Equinox sunrise illuminates carved backstone in Cairn T",
        "Hilltop cairn complex with 360° views of surrounding landscape",
        "Intervisible with Tara, Brú na Bóinne sites — part of a network",
        "Crom Cruach's idol reportedly stood nearby at Mag Slécht",
        "Brigid's festival Imbolc (Feb 1) marks seasonal transition — Loughcrew's equinox connects to her seasonal governance"
      ],
      deity_description: "Brigid — daughter of the Dagda. Triple goddess of healing, poetry, and smithcraft. Her festival Imbolc marks spring's return. Loughcrew's equinox alignment connects to the seasonal cycle she governs. Also associated with Crom Cruach — a pre-Christian harvest deity whose idol stood nearby.",
      global_parallels: [
        {site: "Chichén Itzá (El Castillo)", country: "Mexico", parallel_deity: "Kukulkan — feathered serpent appears at equinox", shared_pattern: "Equinox light phenomenon on sacred structure"},
        {site: "Mnajdra Temple", country: "Malta", parallel_deity: "Neolithic goddess cult", shared_pattern: "Equinox alignment, megalithic temple, prehistoric astronomy"},
        {site: "Karnak Temple", country: "Egypt", parallel_deity: "Amun-Ra", shared_pattern: "Solar alignment illuminates inner sanctum on specific dates"}
      ],
      dialogue: null,
      insight: "Three sites on three continents — Loughcrew (Ireland), Chichén Itzá (Mexico), Mnajdra (Malta) — all produce a specific light event on the equinox. Zero cultural contact between them. Either all three independently figured out equinox alignment and decided to engineer it into stone, or there's a shared knowledge tradition older than any of these structures."
    },
    {
      name: "Carrowmore & Carrowkeel",
      deity: "Tuatha Dé Danann (collective)",
      date: "Possibly 4600 BCE (disputed)",
      tagline: "Potentially the OLDEST megalithic complex in Ireland, oriented toward Knocknarea",
      audio: "audio/brief_tuatha_de_danann.mp3",
      what_to_look_for: "At Carrowmore: the central monument Listoghil aligned to Samhain sunrise. All satellite tombs oriented toward Knocknarea. At Carrowkeel: roofbox similar to Newgrange (summer solstice), 110Hz chamber resonance. If the early C14 dates (4600 BCE) are valid, these predate Newgrange by 1400 years.",
      facts: [
        "Early C14 dates suggest 4600-4100 BCE — would make these the OLDEST megaliths in Ireland",
        "If valid, contemporary with earliest Mediterranean megalithic (challenges diffusionist theory)",
        "All satellite tombs oriented toward Knocknarea mountain",
        "Central monument Listoghil aligned to Samhain (Nov 1) sunrise",
        "Carrowkeel has a roofbox similar to Newgrange — summer solstice alignment",
        "110Hz resonance detected in Carrowkeel chambers (same as Newgrange)"
      ],
      deity_description: "The Tuatha Dé Danann collectively — 'The People of the Goddess Danu.' They arrived from the Northern Islands with four treasures, defeated the Fir Bolg and Fomorians, then retreated underground into the sídhe (passage tombs) after defeat by the Milesians. These ARE the underground places they retreated into.",
      global_parallels: [
        {site: "Göbekli Tepe", country: "Turkey", parallel_deity: "Unknown builders", shared_pattern: "Oldest megalithic site in region, predates agriculture, voluntarily buried/sealed"},
        {site: "Carnac", country: "France", parallel_deity: "Unknown", shared_pattern: "Massive megalithic complex, aligned stones, prehistoric astronomy"},
        {site: "Hal Saflieni Hypogeum", country: "Malta", parallel_deity: "Neolithic goddess", shared_pattern: "Underground chambers, 110Hz resonance, ritual function"}
      ],
      dialogue: null,
      insight: "If the 4600 BCE dates hold up, Ireland's megalithic tradition is independent of — and possibly older than — anything in the Mediterranean or Middle East. This demolishes the 'diffusion from the East' theory and suggests either (a) independent invention of megalithic construction, or (b) a source tradition older than both. The 110Hz resonance appearing in both Ireland AND Malta is the smoking gun for a shared engineering specification."
    },
    {
      name: "Dowth (Dubhadh — Darkness)",
      deity: "Boann (River Boyne goddess)",
      date: "~3200 BCE",
      tagline: "Winter solstice SUNSET alignment (complementary to Newgrange sunrise)",
      audio: "audio/brief_boann.mp3",
      what_to_look_for: "Dowth's passage captures winter solstice SUNSET — making it the evening counterpart to Newgrange's sunrise alignment. Together they mark the full solstice day. The name means 'darkness' (Dubhadh). Less reconstructed than Newgrange — more authentic but harder to access.",
      facts: [
        "Winter solstice sunset illuminates the chamber (opposite of Newgrange's sunrise)",
        "Part of the Brú na Bóinne complex with Newgrange and Knowth",
        "Name means 'darkness' — complementary to Newgrange's light",
        "Less reconstructed than Newgrange — shows original state better",
        "Boann (goddess of the River Boyne) created the river by approaching Nechtan's forbidden well"
      ],
      deity_description: "Boann — goddess of the River Boyne. She created the river by approaching Nechtan's forbidden well (pursuit of forbidden knowledge). The waters rose and chased her, taking her arm, leg, and eye. The river formed in her wake. Her parallel is Tiamat (primeval water goddess) — both are feminine water that shapes the landscape.",
      global_parallels: [
        {site: "Giza (sunset alignment)", country: "Egypt", parallel_deity: "Ra — setting sun entering Duat", shared_pattern: "Sunset/death alignment complementing sunrise/rebirth"},
        {site: "Newgrange (sunrise)", country: "Ireland", parallel_deity: "Dagda/Aengus", shared_pattern: "Sunrise-sunset pair marking complete solar cycle"}
      ],
      dialogue: null,
      insight: "Newgrange captures the moment of rebirth (sunrise). Dowth captures the moment of death (sunset). Together they mark the full cycle — death and resurrection on the shortest day. This mirrors the Osiris/Ra cycle in Egypt exactly: Ra dies each evening (enters the Duat), is reborn each morning. Two cultures, same astronomical theology, same architectural solution."
    }
  ],

  patterns: [
    {name: "Divine Creation of Humans", description: "Gods create humans from clay/earth/corn to serve as laborers or worshippers", verdict: "UNIVERSAL", cultures: 13, entities: 36},
    {name: "Catastrophic Flood", description: "Divine council destroys humanity via flood; one righteous person is warned and survives", verdict: "UNIVERSAL", cultures: 11, entities: 28},
    {name: "Divine/Human Interbreeding", description: "Gods mate with humans producing semi-divine offspring (heroes, giants)", verdict: "UNIVERSAL", cultures: 15, entities: 154},
    {name: "Underground Retreat", description: "Gods/divine beings retreat underground, remain present but hidden", verdict: "UNIVERSAL", cultures: 12, entities: 37},
    {name: "Pre-Flood Civilization", description: "Advanced civilization existed before the catastrophe, fragments of knowledge survived", verdict: "UNIVERSAL", cultures: 8, entities: 10},
    {name: "Solar/Astronomical Alignment", description: "Ancient structures demonstrate astronomical knowledge requiring advanced observation", verdict: "REGIONAL", cultures: 4, entities: 8},
    {name: "Divine Kingship", description: "Rulers claim divine descent, kingship 'descends from heaven'", verdict: "UNIVERSAL", cultures: 12, entities: 36}
  ],

  crosswalk: [
    {role: "Supreme sky deity / king of gods", sumerian: "Anu", irish: "Nuada/Dagda", greek: "Zeus/Ouranos", hebrew: "El/Yahweh", hindu: "Brahma", norse: "Odin"},
    {role: "Wisdom god, humanity's protector", sumerian: "Enki (Ea)", irish: "Dian Cécht", greek: "Prometheus", hebrew: null, hindu: "Vishnu", norse: null},
    {role: "Mother goddess / earth", sumerian: "Ninhursag", irish: "Danu/Brigid", greek: "Gaia", hebrew: "Eve", hindu: "Parvati", norse: "Frigg"},
    {role: "Flood survivor", sumerian: "Utnapishtim", irish: "Fintan", greek: "Deucalion", hebrew: "Noah", hindu: "Manu", norse: "Lif/Lifthrasir"},
    {role: "The gods (collective)", sumerian: "Anunnaki", irish: "Tuatha Dé Danann", greek: "Olympians/Titans", hebrew: "Elohim", hindu: "Devas", norse: "Aesir"},
    {role: "Semi-divine hero", sumerian: "Gilgamesh", irish: "Cú Chulainn", greek: "Heracles", hebrew: "Nephilim", hindu: "Arjuna", norse: "Sigurd"},
    {role: "War/sovereignty goddess", sumerian: "Inanna/Ishtar", irish: "Morrigan/Medb", greek: "Athena/Aphrodite", hebrew: null, hindu: "Durga", norse: "Freya"},
    {role: "Forbidden knowledge bringer", sumerian: "Enki (warns Atrahasis)", irish: null, greek: "Prometheus (steals fire)", hebrew: "Watchers/Azazel", hindu: null, norse: "Odin (runes)"},
    {role: "Rebel/trickster who causes catastrophe", sumerian: null, irish: "Bres (half-blood tyrant)", greek: "Kronos", hebrew: "Satan/Serpent", hindu: "Ravana", norse: "Loki"},
    {role: "Giants / enemies of gods", sumerian: "Kingu", irish: "Fomorians (Balor)", greek: "Titans/Giants", hebrew: "Nephilim", hindu: "Asuras", norse: "Jotnar"}
  ]
};
