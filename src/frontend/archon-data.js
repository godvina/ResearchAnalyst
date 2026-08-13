// Archon Library v2.3.0 - 2026-08-09
// 266 entities, 188 rels, 7 patterns
// 13 traditions + deep Irish mythology (Cath Maige Tuired)

const ARCHON_DATA = {
  "name": "Archon Library",
  "version": "2.3.0",
  "description": "Cross-cultural mythology and ancient text analysis. Entities, relationships, and pattern signatures from Sumerian, Babylonian, Hebrew, and comparative traditions.",
  "last_updated": "2026-08-09",
  "sources_processed": [
    "Enuma_Elish_Creation_Epic.pdf",
    "Epic_of_Gilgamesh_Kovacs.pdf",
    "Epic_of_Gilgamesh_Sandars.pdf",
    "Atra-Hasis_Epic.txt",
    "Book_of_Enoch_Charles_1917.txt",
    "Lebor_Gabala_Index_Extracts.txt",
    "Sumerian_King_List.txt",
    "Popol_Vuh_Spence_1908.txt",
    "Descent_of_Inanna_Kramer.txt",
    "Matsya_Purana_Flood.txt",
    "Prose_Edda_Gylfaginning.txt",
    "Genesis_1-11_Primeval_History.txt",
    "Book_of_Giants_DSS.txt",
    "Greek_Theogony_Hesiod.txt",
    "Mahabharata_Vimana_Weapons.txt",
    "Egyptian_Pyramid_Texts.txt",
    "Zoroastrian_Bundahishn.txt",
    "Chinese_Pangu_Nuwa_Creation.txt",
    "Cath_Maige_Tuired_Second_Battle.txt"
  ],
  "entities": [
    {
      "name": "Apsu",
      "type": "deity",
      "culture": "Babylonian",
      "description": "The primeval freshwater ocean that existed before the creation of the cosmos.",
      "aliases": []
    },
    {
      "name": "Tiamat",
      "type": "deity",
      "culture": "Babylonian",
      "description": "The primeval saltwater ocean that existed before the creation of the cosmos, also the mother of the gods.",
      "aliases": [
        "Ummu-Hubur"
      ]
    },
    {
      "name": "Lahmu",
      "type": "deity",
      "culture": "Babylonian",
      "description": "One of the first pair of gods to be created.",
      "aliases": []
    },
    {
      "name": "Lahamu",
      "type": "deity",
      "culture": "Babylonian",
      "description": "One of the first pair of gods to be created.",
      "aliases": []
    },
    {
      "name": "Ansar",
      "type": "deity",
      "culture": "Babylonian",
      "description": "A primordial deity, one of the first generation of gods.",
      "aliases": []
    },
    {
      "name": "Kisar",
      "type": "deity",
      "culture": "Babylonian",
      "description": "A primordial deity, one of the first generation of gods.",
      "aliases": []
    },
    {
      "name": "Anu",
      "type": "deity",
      "culture": "Babylonian",
      "description": "The sky god, ruler of the heavens.",
      "aliases": []
    },
    {
      "name": "Nudimmud",
      "type": "deity",
      "culture": "Babylonian",
      "description": "Another name for the god Ea, the god of wisdom and fresh water.",
      "aliases": [
        "Ea"
      ]
    },
    {
      "name": "Mummu",
      "type": "deity",
      "culture": "Babylonian",
      "description": "The minister and vizier of Apsu.",
      "aliases": []
    },
    {
      "name": "Kingu",
      "type": "deity",
      "culture": "Babylonian",
      "description": "One of Tiamat's sons, whom she exalted and made the leader of her forces against the other gods.",
      "aliases": []
    },
    {
      "name": "Anunnaki",
      "type": "group",
      "culture": "Babylonian",
      "description": "The group of major Mesopotamian deities.",
      "aliases": []
    },
    {
      "name": "Gaga",
      "type": "deity",
      "culture": "Babylonian",
      "description": "Ansar's minister, sent to deliver a message to Lahmu and Lahamu.",
      "aliases": []
    },
    {
      "name": "Marduk",
      "type": "deity",
      "culture": "Babylonian",
      "description": "The god who is destined to become the champion and avenger of the other gods against Tiamat.",
      "aliases": []
    },
    {
      "name": "Upsukkinaku",
      "type": "location",
      "culture": "Babylonian",
      "description": "The assembly hall of the gods.",
      "aliases": []
    },
    {
      "name": "Gilgamesh",
      "type": "hero",
      "culture": "Mesopotamian",
      "description": "The king of Uruk, a demigod with superhuman strength and wisdom.",
      "aliases": []
    },
    {
      "name": "Enkidu",
      "type": "hero",
      "culture": "Mesopotamian",
      "description": "A wild man created by the gods to be Gilgamesh's equal and companion.",
      "aliases": []
    },
    {
      "name": "Uruk",
      "type": "location",
      "culture": "Mesopotamian",
      "description": "The great city where Gilgamesh rules as king.",
      "aliases": []
    },
    {
      "name": "Ishtar",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "The goddess of love and war.",
      "aliases": []
    },
    {
      "name": "Aruru",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "The goddess of creation who made Enkidu.",
      "aliases": []
    },
    {
      "name": "Ninurta",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "The god of war, whose virtues were present in Enkidu.",
      "aliases": []
    },
    {
      "name": "Samugan",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "The god of cattle, whose appearance Enkidu shared.",
      "aliases": []
    },
    {
      "name": "Nisaba",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "The goddess of corn, whose hair Enkidu's resembled.",
      "aliases": []
    },
    {
      "name": "Ninsun",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "Gilgamesh's mother, a wise goddess.",
      "aliases": []
    },
    {
      "name": "Shamash",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "The glorious sun god who endowed Gilgamesh with beauty.",
      "aliases": []
    },
    {
      "name": "Adad",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "The god of the storm who endowed Gilgamesh with courage.",
      "aliases": []
    },
    {
      "name": "Enlil",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "One of the chief gods who gave Gilgamesh deep understanding.",
      "aliases": []
    },
    {
      "name": "Ea",
      "type": "deity",
      "culture": "Mesopotamian",
      "description": "The wise god who gave Gilgamesh deep understanding.",
      "aliases": []
    },
    {
      "name": "Enki/Ea",
      "type": "deity",
      "culture": "Akkadian",
      "description": "Wisdom god",
      "aliases": []
    },
    {
      "name": "Nintu/Mami/Belet-ili",
      "type": "deity",
      "culture": "Akkadian",
      "description": "Birth goddess",
      "aliases": [
        "Mami",
        "Belet-kala-ili"
      ]
    },
    {
      "name": "Anunna",
      "type": "divine beings",
      "culture": "Akkadian",
      "description": "The great gods",
      "aliases": []
    },
    {
      "name": "Igigi",
      "type": "divine beings",
      "culture": "Akkadian",
      "description": "The lower gods who revolted",
      "aliases": []
    },
    {
      "name": "Atrahasis",
      "type": "hero",
      "culture": "Akkadian",
      "description": "Flood survivor, described as 'exceedingly wise'",
      "aliases": []
    },
    {
      "name": "Aw-ilu",
      "type": "deity",
      "culture": "Akkadian",
      "description": "God who was slaughtered, whose blood was used to create humans",
      "aliases": []
    },
    {
      "name": "Anzu",
      "type": "creature",
      "culture": "Akkadian",
      "description": "Mythical bird",
      "aliases": []
    },
    {
      "name": "Tigris",
      "type": "location",
      "culture": "Akkadian",
      "description": "River",
      "aliases": []
    },
    {
      "name": "Euphrates",
      "type": "location",
      "culture": "Akkadian",
      "description": "River",
      "aliases": []
    },
    {
      "name": "Ekur",
      "type": "location",
      "culture": "Akkadian",
      "description": "Enlil's temple",
      "aliases": []
    },
    {
      "name": "Semjaza",
      "type": "angel",
      "culture": "Hebrew",
      "description": "Leader of the 200 fallen Watchers who descended to Mount Hermon",
      "aliases": [
        "Semjazaz",
        "Shemyaza"
      ]
    },
    {
      "name": "Arakiba",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Rameel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Kokabiel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Tamiel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Ramiel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Danel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Ezequeel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Baraqijal",
      "type": "angel",
      "culture": "Hebrew",
      "aliases": []
    },
    {
      "name": "Asael",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Armaros",
      "type": "angel",
      "culture": "Hebrew",
      "aliases": []
    },
    {
      "name": "Batarel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Ananel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Zaqiel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Samsapeel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Satarel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Turel",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Jomjael",
      "type": "angel",
      "culture": "Hebrew"
    },
    {
      "name": "Sariel",
      "type": "angel",
      "culture": "Hebrew",
      "aliases": []
    },
    {
      "name": "Azazel",
      "type": "angel",
      "culture": "Hebrew",
      "description": "Taught humans forbidden knowledge"
    },
    {
      "name": "Kokabel",
      "type": "angel",
      "culture": "Hebrew",
      "description": "Taught the constellations"
    },
    {
      "name": "Ezeqeel",
      "type": "angel",
      "culture": "Hebrew",
      "description": "Taught the knowledge of the clouds"
    },
    {
      "name": "Araqiel",
      "type": "angel",
      "culture": "Hebrew",
      "description": "Taught the signs of the earth"
    },
    {
      "name": "Shamsiel",
      "type": "angel",
      "culture": "Hebrew",
      "description": "Taught the signs of the sun"
    },
    {
      "name": "Michael",
      "type": "archangel",
      "culture": "Hebrew"
    },
    {
      "name": "Uriel",
      "type": "archangel",
      "culture": "Hebrew"
    },
    {
      "name": "Raphael",
      "type": "archangel",
      "culture": "Hebrew"
    },
    {
      "name": "Gabriel",
      "type": "archangel",
      "culture": "Hebrew"
    },
    {
      "name": "Noah",
      "type": "human",
      "culture": "Hebrew"
    },
    {
      "name": "Lamech",
      "type": "human",
      "culture": "Hebrew"
    },
    {
      "name": "Methuselah",
      "type": "human",
      "culture": "Hebrew"
    },
    {
      "name": "Mount Hermon",
      "type": "location",
      "culture": "Hebrew"
    },
    {
      "name": "Dudael",
      "type": "location",
      "culture": "Hebrew"
    },
    {
      "name": "Watchers",
      "type": "group",
      "culture": "Hebrew",
      "description": "200 angels who descended to Earth and took human wives"
    },
    {
      "name": "Lord of Spirits",
      "type": "divine",
      "culture": "Hebrew"
    },
    {
      "name": "Head of Days",
      "type": "divine",
      "culture": "Hebrew"
    },
    {
      "name": "Son of Man",
      "type": "divine",
      "culture": "Hebrew"
    },
    {
      "name": "Nephilim",
      "type": "group",
      "culture": "Hebrew",
      "description": "Giants born from the union of the Watchers and human women"
    },
    {
      "name": "Dagda",
      "type": "deity",
      "culture": "Irish",
      "description": "Chief of the Tuatha De Danann, father god, associated with Brug na Boinne (Newgrange)",
      "aliases": [
        "the Great Good Father",
        "In Dagda Mor",
        "Eochu Ollathair"
      ]
    },
    {
      "name": "Lugh",
      "type": "deity",
      "culture": "Irish",
      "description": "A hero-god of the Tuatha Dé Danann"
    },
    {
      "name": "Nuada",
      "type": "deity",
      "culture": "Irish",
      "description": "King of the Tuatha Dé Danann"
    },
    {
      "name": "Brigid",
      "type": "deity",
      "culture": "Irish",
      "description": "Daughter of the Dagda, goddess of poetry, healing, and smithcraft"
    },
    {
      "name": "Morrigan",
      "type": "deity",
      "culture": "Irish",
      "description": "Goddess of war, fate, and sovereignty",
      "aliases": []
    },
    {
      "name": "Dian Cecht",
      "type": "deity",
      "culture": "Irish",
      "description": "God of healing",
      "aliases": []
    },
    {
      "name": "Manannán",
      "type": "deity",
      "culture": "Irish",
      "description": "God of the sea"
    },
    {
      "name": "Ogma",
      "type": "deity",
      "culture": "Irish",
      "description": "God of eloquence and writing",
      "aliases": []
    },
    {
      "name": "Balor",
      "type": "deity",
      "culture": "Irish",
      "description": "Leader of the Fomorians",
      "aliases": []
    },
    {
      "name": "Bres",
      "type": "deity",
      "culture": "Irish",
      "description": "A king of the Tuatha Dé Danann"
    },
    {
      "name": "Tuatha Dé Danann",
      "type": "group",
      "culture": "Irish",
      "description": "The gods and goddesses of Irish mythology"
    },
    {
      "name": "Fomorians",
      "type": "group",
      "culture": "Irish",
      "description": "Mythical semi-divine beings who were enemies of the Tuatha Dé Danann"
    },
    {
      "name": "Brug na Boinne",
      "type": "location",
      "culture": "Irish",
      "description": "A sacred site associated with the Dagda and the Tuatha Dé Danann"
    },
    {
      "name": "Alulim",
      "type": "deity",
      "culture": "Sumerian",
      "description": "First king of Eridu, ruled for 28,800 years",
      "aliases": []
    },
    {
      "name": "Alalgar",
      "type": "deity",
      "culture": "Sumerian",
      "description": "Second king of Eridu, ruled for 36,000 years",
      "aliases": []
    },
    {
      "name": "Enmen-lu-ana",
      "type": "deity",
      "culture": "Sumerian",
      "description": "King of Bad-tibira, ruled for 43,200 years",
      "aliases": []
    },
    {
      "name": "Enmen-gal-ana",
      "type": "deity",
      "culture": "Sumerian",
      "description": "King of Bad-tibira, ruled for 28,800 years",
      "aliases": []
    },
    {
      "name": "Dumuzi",
      "type": "deity",
      "culture": "Sumerian",
      "description": "The shepherd king of Bad-tibira, ruled for 36,000 years",
      "aliases": []
    },
    {
      "name": "En-sipad-zid-ana",
      "type": "deity",
      "culture": "Sumerian",
      "description": "King of Larak, ruled for 28,800 years",
      "aliases": []
    },
    {
      "name": "Enmen-dur-ana",
      "type": "deity",
      "culture": "Sumerian",
      "description": "King of Sippar, ruled for 21,000 years",
      "aliases": []
    },
    {
      "name": "Ubara-Tutu",
      "type": "deity",
      "culture": "Sumerian",
      "description": "King of Shuruppak, ruled for 18,600 years",
      "aliases": []
    },
    {
      "name": "Etana",
      "type": "deity",
      "culture": "Sumerian",
      "description": "Shepherd king of Kish who ascended to heaven, ruled for 1,500 years",
      "aliases": []
    },
    {
      "name": "Enmen-baragesi",
      "type": "deity",
      "culture": "Sumerian",
      "description": "King of Kish who destroyed Elam's weapons, ruled for 900 years",
      "aliases": []
    },
    {
      "name": "Agga",
      "type": "deity",
      "culture": "Sumerian",
      "description": "Son of Enmen-baragesi, king of Kish, ruled for 625 years",
      "aliases": []
    },
    {
      "name": "Mes-ki'ag-gaser",
      "type": "deity",
      "culture": "Sumerian",
      "description": "Lord and king of Uruk, son of the sun god Utu, ruled for 324 years",
      "aliases": []
    },
    {
      "name": "Enmerkar",
      "type": "deity",
      "culture": "Sumerian",
      "description": "King of Uruk, son of Mes-ki'ag-gaser, ruled for 420 years",
      "aliases": []
    },
    {
      "name": "Lugal-banda",
      "type": "deity",
      "culture": "Sumerian",
      "description": "The shepherd king of Uruk, ruled for 1,200 years",
      "aliases": []
    },
    {
      "name": "Hurakan",
      "type": "deity",
      "culture": "Kiché (Maya)",
      "description": "The mighty wind, the Heart of Heaven, creator god",
      "aliases": []
    },
    {
      "name": "Gucumatz",
      "type": "deity",
      "culture": "Kiché (Maya)",
      "description": "The Feathered Serpent, creator god",
      "aliases": []
    },
    {
      "name": "Xpiyacoc",
      "type": "deity",
      "culture": "Kiché (Maya)",
      "description": "Father god, creator",
      "aliases": []
    },
    {
      "name": "Xmucane",
      "type": "deity",
      "culture": "Kiché (Maya)",
      "description": "Mother goddess, creator",
      "aliases": []
    },
    {
      "name": "Tepeu",
      "type": "deity",
      "culture": "Kiché (Maya)",
      "description": "King/creator god",
      "aliases": []
    },
    {
      "name": "Hun-Ahpu",
      "type": "hero",
      "culture": "Kiché (Maya)",
      "description": "The Master, Magician, hero twin",
      "aliases": []
    },
    {
      "name": "Xbalanque",
      "type": "hero",
      "culture": "Kiché (Maya)",
      "description": "Little Tiger, hero twin",
      "aliases": []
    },
    {
      "name": "Vukub-Cakix",
      "type": "titan",
      "culture": "Kiché (Maya)",
      "description": "Seven-fires, arrogant titan",
      "aliases": []
    },
    {
      "name": "Zipacna",
      "type": "titan",
      "culture": "Kiché (Maya)",
      "description": "Mountain-maker, titan son of Vukub-Cakix",
      "aliases": []
    },
    {
      "name": "Cabrakan",
      "type": "titan",
      "culture": "Kiché (Maya)",
      "description": "Earthquake, titan son of Vukub-Cakix",
      "aliases": []
    },
    {
      "name": "Hun-Came",
      "type": "underworld lord",
      "culture": "Kiché (Maya)",
      "description": "Ruler of the Underworld (Xibalba)",
      "aliases": []
    },
    {
      "name": "Vukub-Came",
      "type": "underworld lord",
      "culture": "Kiché (Maya)",
      "description": "Ruler of the Underworld (Xibalba)",
      "aliases": []
    },
    {
      "name": "Camazotz",
      "type": "underworld lord",
      "culture": "Kiché (Maya)",
      "description": "Ruler of Bats in the Underworld",
      "aliases": []
    },
    {
      "name": "Balam-Quitze",
      "type": "first man",
      "culture": "Kiché (Maya)",
      "description": "Tiger with the Sweet Smile, one of the first four men",
      "aliases": []
    },
    {
      "name": "Balam-Agab",
      "type": "first man",
      "culture": "Kiché (Maya)",
      "description": "Tiger of the Night, one of the first four men",
      "aliases": []
    },
    {
      "name": "Mahucutah",
      "type": "first man",
      "culture": "Kiché (Maya)",
      "description": "The Distinguished Name, one of the first four men",
      "aliases": []
    },
    {
      "name": "Iqi-Balam",
      "type": "first man",
      "culture": "Kiché (Maya)",
      "description": "Tiger of the Moon, one of the first four men",
      "aliases": []
    },
    {
      "name": "Tohil",
      "type": "tribal god",
      "culture": "Kiché (Maya)",
      "description": "The creator of fire, given to Balam-Quitze",
      "aliases": []
    },
    {
      "name": "Avilix",
      "type": "tribal god",
      "culture": "Kiché (Maya)",
      "description": "Given to Balam-Agab",
      "aliases": []
    },
    {
      "name": "Hacavitz",
      "type": "tribal god",
      "culture": "Kiché (Maya)",
      "description": "Given to Mahucutah",
      "aliases": []
    },
    {
      "name": "Xquiq",
      "type": "virgin",
      "culture": "Kiché (Maya)",
      "description": "Blood, virgin mother of the hero twins",
      "aliases": []
    },
    {
      "name": "Hunhun-Ahpu",
      "type": "father",
      "culture": "Kiché (Maya)",
      "description": "Father of the hero twins",
      "aliases": []
    },
    {
      "name": "400 youths",
      "type": "group",
      "culture": "Kiché (Maya)",
      "description": "Slain by Zipacna, became the stars",
      "aliases": []
    },
    {
      "name": "Inanna",
      "type": "deity",
      "culture": "Sumerian",
      "description": "Queen of Heaven",
      "aliases": []
    },
    {
      "name": "Ereshkigal",
      "type": "deity",
      "culture": "Sumerian",
      "description": "Queen of the Underworld",
      "aliases": []
    },
    {
      "name": "Enki",
      "type": "deity",
      "culture": "Sumerian",
      "description": "God of Wisdom",
      "aliases": []
    },
    {
      "name": "Nanna",
      "type": "deity",
      "culture": "Sumerian",
      "description": "Refused to help Inanna",
      "aliases": []
    },
    {
      "name": "Utu",
      "type": "deity",
      "culture": "Sumerian",
      "description": "God of Justice, helped Dumuzi",
      "aliases": []
    },
    {
      "name": "Ninshubur",
      "type": "servant",
      "culture": "Sumerian",
      "description": "Faithful servant/sukkal of Inanna",
      "aliases": []
    },
    {
      "name": "Neti",
      "type": "servant",
      "culture": "Sumerian",
      "description": "Gatekeeper of the Underworld",
      "aliases": []
    },
    {
      "name": "Shara",
      "type": "offspring",
      "culture": "Sumerian",
      "description": "Son of Inanna",
      "aliases": []
    },
    {
      "name": "Lulal",
      "type": "offspring",
      "culture": "Sumerian",
      "description": "Son of Inanna",
      "aliases": []
    },
    {
      "name": "Kurgarra",
      "type": "creature",
      "culture": "Sumerian",
      "description": "Neither male nor female, created by Enki from dirt",
      "aliases": []
    },
    {
      "name": "Galatur",
      "type": "creature",
      "culture": "Sumerian",
      "description": "Neither male nor female, created by Enki from dirt",
      "aliases": []
    },
    {
      "name": "Galla",
      "type": "demon",
      "culture": "Sumerian",
      "description": "Demons of the Underworld, know no food, drink, love",
      "aliases": []
    },
    {
      "name": "Annuna",
      "type": "group",
      "culture": "Sumerian",
      "description": "Judges of the Underworld",
      "aliases": []
    },
    {
      "name": "Vishnu",
      "type": "deity",
      "culture": "Hindu/Indian",
      "description": "Supreme preserver god, takes Matsya avatar",
      "aliases": []
    },
    {
      "name": "Brahma",
      "type": "deity",
      "culture": "Hindu/Indian",
      "description": "Creator, whose Vedas were stolen",
      "aliases": []
    },
    {
      "name": "Matsya",
      "type": "avatar",
      "culture": "Hindu/Indian",
      "description": "The divine fish - Vishnu's first incarnation",
      "aliases": []
    },
    {
      "name": "Manu/Satyavrata/Vaivasvata",
      "type": "human",
      "culture": "Hindu/Indian",
      "description": "7th Manu, flood survivor, progenitor of humanity",
      "aliases": []
    },
    {
      "name": "Ila/Shraddha",
      "type": "human",
      "culture": "Hindu/Indian",
      "description": "First woman post-flood",
      "aliases": []
    },
    {
      "name": "Saptarishi",
      "type": "sage",
      "culture": "Hindu/Indian",
      "description": "Seven Great Sages who survive on the ship",
      "aliases": []
    },
    {
      "name": "Hayagriva",
      "type": "demon",
      "culture": "Hindu/Indian",
      "description": "Horse-headed demon who stole the Vedas",
      "aliases": []
    },
    {
      "name": "Vasuki",
      "type": "creature",
      "culture": "Hindu/Indian",
      "description": "Cosmic serpent, used as rope to tie ship to fish's horn",
      "aliases": []
    },
    {
      "name": "Odin",
      "type": "deity",
      "culture": "Norse/Scandinavian",
      "description": "Allfather, wisdom, war, death, poetry, runes — hung on Yggdrasil 9 days to gain knowledge of runes",
      "aliases": []
    },
    {
      "name": "Thor",
      "type": "deity",
      "culture": "Norse/Scandinavian",
      "description": "thunder, strength, protector of Midgard",
      "aliases": []
    },
    {
      "name": "Loki",
      "type": "deity",
      "culture": "Norse/Scandinavian",
      "description": "trickster, shape-shifter, father of monsters — Fenrir wolf, Jormungandr serpent, Hel",
      "aliases": []
    },
    {
      "name": "Freya",
      "type": "deity",
      "culture": "Norse/Scandinavian",
      "description": "love, fertility, war, magic/seidr",
      "aliases": []
    },
    {
      "name": "Baldur",
      "type": "deity",
      "culture": "Norse/Scandinavian",
      "description": "beauty, light, beloved of all — killed by Loki's trickery",
      "aliases": []
    },
    {
      "name": "Tyr",
      "type": "deity",
      "culture": "Norse/Scandinavian",
      "description": "law, justice, sacrificed hand to bind Fenrir",
      "aliases": []
    },
    {
      "name": "Heimdall",
      "type": "deity",
      "culture": "Norse/Scandinavian",
      "description": "watchman of gods, blows Gjallarhorn at Ragnarok",
      "aliases": []
    },
    {
      "name": "Ymir",
      "type": "giant",
      "culture": "Norse/Scandinavian",
      "description": "first being, killed to make the world",
      "aliases": []
    },
    {
      "name": "Surtr",
      "type": "giant",
      "culture": "Norse/Scandinavian",
      "description": "fire giant who destroys the world at Ragnarok",
      "aliases": []
    },
    {
      "name": "Thrym",
      "type": "giant",
      "culture": "Norse/Scandinavian",
      "description": "stole Thor's hammer",
      "aliases": []
    },
    {
      "name": "Fenrir",
      "type": "monster",
      "culture": "Norse/Scandinavian",
      "description": "great wolf that breaks free at Ragnarok",
      "aliases": []
    },
    {
      "name": "Jormungandr",
      "type": "monster",
      "culture": "Norse/Scandinavian",
      "description": "world serpent that rises from the ocean, flooding the land",
      "aliases": []
    },
    {
      "name": "Hel",
      "type": "monster",
      "culture": "Norse/Scandinavian",
      "description": "death goddess",
      "aliases": []
    },
    {
      "name": "Ask",
      "type": "human",
      "culture": "Norse/Scandinavian",
      "description": "first man, created from an ash tree",
      "aliases": []
    },
    {
      "name": "Embla",
      "type": "human",
      "culture": "Norse/Scandinavian",
      "description": "first woman, created from an elm tree",
      "aliases": []
    },
    {
      "name": "Lif",
      "type": "human",
      "culture": "Norse/Scandinavian",
      "description": "one of the two humans who survive Ragnarok, hidden in Yggdrasil",
      "aliases": []
    },
    {
      "name": "Lifthrasir",
      "type": "human",
      "culture": "Norse/Scandinavian",
      "description": "one of the two humans who survive Ragnarok, hidden in Yggdrasil",
      "aliases": []
    },
    {
      "name": "Audhumla",
      "type": "cosmic",
      "culture": "Norse/Scandinavian",
      "description": "primeval cow that nourished Ymir",
      "aliases": []
    },
    {
      "name": "Buri",
      "type": "cosmic",
      "culture": "Norse/Scandinavian",
      "description": "first of the gods, revealed by Audhumla",
      "aliases": []
    },
    {
      "name": "Yggdrasil",
      "type": "cosmic",
      "culture": "Norse/Scandinavian",
      "description": "the great ash tree that structures the cosmos",
      "aliases": []
    },
    {
      "name": "God",
      "type": "divine",
      "culture": "Hebrew/Israelite",
      "description": "Creator of heaven and earth",
      "aliases": [
        "Elohim",
        "Yahweh/LORD God"
      ]
    },
    {
      "name": "Adam",
      "type": "human",
      "culture": "Hebrew/Israelite",
      "description": "First man created from dust",
      "aliases": []
    },
    {
      "name": "Eve",
      "type": "human",
      "culture": "Hebrew/Israelite",
      "description": "First woman, created from Adam's rib",
      "aliases": []
    },
    {
      "name": "Cain",
      "type": "human",
      "culture": "Hebrew/Israelite",
      "description": "Son of Adam and Eve, murdered Abel",
      "aliases": []
    },
    {
      "name": "Abel",
      "type": "human",
      "culture": "Hebrew/Israelite",
      "description": "Son of Adam and Eve, killed by Cain",
      "aliases": []
    },
    {
      "name": "Shem",
      "type": "human",
      "culture": "Hebrew/Israelite",
      "description": "One of Noah's sons, ancestor of Semitic peoples",
      "aliases": []
    },
    {
      "name": "Ham",
      "type": "human",
      "culture": "Hebrew/Israelite",
      "description": "One of Noah's sons, ancestor of Hamitic peoples",
      "aliases": []
    },
    {
      "name": "Japheth",
      "type": "human",
      "culture": "Hebrew/Israelite",
      "description": "One of Noah's sons, ancestor of Japhetic peoples",
      "aliases": []
    },
    {
      "name": "Nimrod",
      "type": "human",
      "culture": "Hebrew/Israelite",
      "description": "Mighty hunter and builder of cities",
      "aliases": []
    },
    {
      "name": "Ohya",
      "type": "human",
      "culture": "Jewish Aramaic",
      "description": "Prominent giant, son of Semjaza"
    },
    {
      "name": "Hahya",
      "type": "human",
      "culture": "Jewish Aramaic",
      "description": "Giant, son of Semjaza, brother of Ohya"
    },
    {
      "name": "Mahaway",
      "type": "human",
      "culture": "Jewish Aramaic",
      "description": "Messenger giant who flew to Enoch"
    },
    {
      "name": "Hobabish",
      "type": "human",
      "culture": "Jewish Aramaic",
      "description": "One of the named giants"
    },
    {
      "name": "Baraq'el",
      "type": "human",
      "culture": "Jewish Aramaic",
      "description": "Named after the Watcher Baraqiel"
    },
    {
      "name": "Baraqiel",
      "type": "human",
      "culture": "Jewish Aramaic",
      "description": "One of the Watchers"
    },
    {
      "name": "Enoch",
      "type": "human",
      "culture": "Jewish Aramaic",
      "description": "Scribe, interpreter of dreams"
    },
    {
      "name": "Zeus",
      "type": "deity",
      "culture": "Greek",
      "description": "King of the Olympian gods",
      "aliases": []
    },
    {
      "name": "Kronos",
      "type": "deity",
      "culture": "Greek",
      "description": "Titan who ruled before Zeus"
    },
    {
      "name": "Gaia",
      "type": "deity",
      "culture": "Greek",
      "description": "Primordial goddess of the Earth"
    },
    {
      "name": "Ouranos",
      "type": "deity",
      "culture": "Greek",
      "description": "Primordial god of the Sky"
    },
    {
      "name": "Titans",
      "type": "group",
      "culture": "Greek",
      "description": "Twelve children of Gaia and Ouranos"
    },
    {
      "name": "Cyclopes",
      "type": "group",
      "culture": "Greek",
      "description": "One-eyed giants"
    },
    {
      "name": "Hecatoncheires",
      "type": "group",
      "culture": "Greek",
      "description": "Hundred-handed giants"
    },
    {
      "name": "Prometheus",
      "type": "deity",
      "culture": "Greek",
      "description": "Titan who gave fire to humans"
    },
    {
      "name": "Pandora",
      "type": "character",
      "culture": "Greek",
      "description": "First woman, created by Zeus"
    },
    {
      "name": "Deucalion",
      "type": "character",
      "culture": "Greek",
      "description": "Survivor of the great flood"
    },
    {
      "name": "Pyrrha",
      "type": "character",
      "culture": "Greek",
      "description": "Wife of Deucalion"
    },
    {
      "name": "Giants",
      "type": "group",
      "culture": "Greek",
      "description": "Born from Ouranos' blood"
    },
    {
      "name": "Heracles",
      "type": "deity",
      "culture": "Greek",
      "description": "Demigod hero"
    },
    {
      "name": "Aphrodite",
      "type": "deity",
      "culture": "Greek",
      "description": "Goddess of love and beauty"
    },
    {
      "name": "Athena",
      "type": "deity",
      "culture": "Greek",
      "description": "Goddess of wisdom and war"
    },
    {
      "name": "Pushpaka Vimana",
      "type": "vehicle",
      "culture": "Hindu/Indian",
      "description": "A flying palace/chariot originally belonging to Kubera"
    },
    {
      "name": "Arjuna's chariot",
      "type": "vehicle",
      "culture": "Hindu/Indian",
      "description": "Provided by Indra, drawn by celestial horses"
    },
    {
      "name": "Krishna's chariot Jaitra",
      "type": "vehicle",
      "culture": "Hindu/Indian",
      "description": "Divine chariot used by Krishna"
    },
    {
      "name": "Surya's chariot",
      "type": "vehicle",
      "culture": "Hindu/Indian",
      "description": "Chariot of the sun god, drawn by seven horses"
    },
    {
      "name": "Brahmastra",
      "type": "weapon",
      "culture": "Hindu/Indian",
      "description": "Brahma's weapon, a powerful incandescent projectile"
    },
    {
      "name": "Pasupatastra",
      "type": "weapon",
      "culture": "Hindu/Indian",
      "description": "Shiva's weapon, capable of destroying all creation"
    },
    {
      "name": "Narayanastra",
      "type": "weapon",
      "culture": "Hindu/Indian",
      "description": "Vishnu's weapon, releases millions of missiles"
    },
    {
      "name": "Varunastra",
      "type": "weapon",
      "culture": "Hindu/Indian",
      "description": "Varuna's weapon, controls water and creates floods"
    },
    {
      "name": "Vayavyastra",
      "type": "weapon",
      "culture": "Hindu/Indian",
      "description": "Vayu's weapon, creates hurricanes and tornados"
    },
    {
      "name": "Agneyastra",
      "type": "weapon",
      "culture": "Hindu/Indian",
      "description": "Agni's weapon, generates unquenchable fire"
    },
    {
      "name": "Yudhishthira",
      "type": "hero",
      "culture": "Hindu/Indian",
      "description": "Son of Dharma, the god of justice"
    },
    {
      "name": "Bhima",
      "type": "hero",
      "culture": "Hindu/Indian",
      "description": "Son of Vayu, the wind god"
    },
    {
      "name": "Arjuna",
      "type": "hero",
      "culture": "Hindu/Indian",
      "description": "Son of Indra, the king of gods"
    },
    {
      "name": "Nakula and Sahadeva",
      "type": "heroes",
      "culture": "Hindu/Indian",
      "description": "Sons of the Ashvin twins, divine physicians"
    },
    {
      "name": "Krishna",
      "type": "avatar",
      "culture": "Hindu/Indian",
      "description": "8th avatar of Vishnu incarnated as a human prince"
    },
    {
      "name": "Nun",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Primeval waters"
    },
    {
      "name": "Atum",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Self-created creator god"
    },
    {
      "name": "Shu",
      "type": "deity",
      "culture": "Egyptian",
      "description": "God of air"
    },
    {
      "name": "Tefnut",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Goddess of moisture"
    },
    {
      "name": "Geb",
      "type": "deity",
      "culture": "Egyptian",
      "description": "God of earth"
    },
    {
      "name": "Nut",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Goddess of sky"
    },
    {
      "name": "Osiris",
      "type": "deity",
      "culture": "Egyptian",
      "description": "God of the dead"
    },
    {
      "name": "Isis",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Goddess of magic"
    },
    {
      "name": "Set",
      "type": "deity",
      "culture": "Egyptian",
      "description": "God of chaos"
    },
    {
      "name": "Nephthys",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Goddess of death"
    },
    {
      "name": "Horus",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Falcon-headed god"
    },
    {
      "name": "Anubis",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Jackal-headed god of embalming"
    },
    {
      "name": "Thoth",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Ibis-headed god of wisdom"
    },
    {
      "name": "Ma'at",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Goddess of truth and justice"
    },
    {
      "name": "Hathor",
      "type": "deity",
      "culture": "Egyptian",
      "description": "Cow-headed goddess of love and sky"
    },
    {
      "name": "Ahura Mazda",
      "type": "deity",
      "culture": "Persian/Zoroastrian",
      "description": "Wise Lord, supreme creator god",
      "aliases": []
    },
    {
      "name": "Angra Mainyu",
      "type": "deity",
      "culture": "Persian/Zoroastrian",
      "description": "Destructive Spirit, evil",
      "aliases": [
        "Ahriman"
      ]
    },
    {
      "name": "Gayomart",
      "type": "primordial",
      "culture": "Persian/Zoroastrian",
      "description": "First Man, shining, white, tall as a tree",
      "aliases": []
    },
    {
      "name": "Gavaevodata",
      "type": "primordial",
      "culture": "Persian/Zoroastrian",
      "description": "Primeval Bull",
      "aliases": []
    },
    {
      "name": "Mashya",
      "type": "primordial",
      "culture": "Persian/Zoroastrian",
      "description": "First human couple with Mashyana",
      "aliases": []
    },
    {
      "name": "Mashyana",
      "type": "primordial",
      "culture": "Persian/Zoroastrian",
      "description": "First human couple with Mashya",
      "aliases": []
    },
    {
      "name": "Yima",
      "type": "king",
      "culture": "Persian/Zoroastrian",
      "description": "First mortal king, ruled during Golden Age",
      "aliases": [
        "Jamshid"
      ]
    },
    {
      "name": "Saoshyant",
      "type": "savior",
      "culture": "Persian/Zoroastrian",
      "description": "Final savior, born of virgin, raises dead",
      "aliases": []
    },
    {
      "name": "Amesha Spentas",
      "type": "divine",
      "culture": "Persian/Zoroastrian",
      "description": "Holy Immortals, including Vohu Manah, Asha Vahishta, Armaiti, Khshathra Vairya, Haurvatat, Ameretat",
      "aliases": []
    },
    {
      "name": "Asha",
      "type": "concept",
      "culture": "Persian/Zoroastrian",
      "description": "Truth/Cosmic Order",
      "aliases": []
    },
    {
      "name": "Druj",
      "type": "concept",
      "culture": "Persian/Zoroastrian",
      "description": "The Lie",
      "aliases": []
    },
    {
      "name": "Vara",
      "type": "location",
      "culture": "Persian/Zoroastrian",
      "description": "Underground enclosure/fortress",
      "aliases": []
    },
    {
      "name": "Pangu",
      "type": "deity",
      "culture": "Chinese",
      "description": "First Being who created the world from cosmic egg",
      "aliases": []
    },
    {
      "name": "Nüwa",
      "type": "deity",
      "culture": "Chinese",
      "description": "Female deity, creator of humans from clay",
      "aliases": []
    },
    {
      "name": "Gong Gong",
      "type": "deity",
      "culture": "Chinese",
      "description": "Water god, destroyed sky pillar causing flood",
      "aliases": []
    },
    {
      "name": "Zhurong",
      "type": "deity",
      "culture": "Chinese",
      "description": "Fire god",
      "aliases": []
    },
    {
      "name": "Fuxi",
      "type": "deity",
      "culture": "Chinese",
      "description": "Nüwa's brother/husband, invented writing and technology",
      "aliases": []
    },
    {
      "name": "Huangdi",
      "type": "human",
      "culture": "Chinese",
      "description": "Legendary ancestor, civilizer, ascended to heaven",
      "aliases": [
        "Yellow Emperor"
      ]
    },
    {
      "name": "Gun",
      "type": "human",
      "culture": "Chinese",
      "description": "Tried to stop flood, failed and was executed",
      "aliases": []
    },
    {
      "name": "Yu",
      "type": "human",
      "culture": "Chinese",
      "description": "Channeled flood waters, became first Xia emperor",
      "aliases": []
    },
    {
      "name": "Chi You",
      "type": "monster",
      "culture": "Chinese",
      "description": "Monstrous rebel defeated by Huangdi",
      "aliases": []
    },
    {
      "name": "Xiangliu",
      "type": "monster",
      "culture": "Chinese",
      "description": "Nine-headed serpent",
      "aliases": []
    },
    {
      "name": "Yin/Yang",
      "type": "concept",
      "culture": "Chinese",
      "description": "Dual forces",
      "aliases": []
    },
    {
      "name": "Wu Xing",
      "type": "concept",
      "culture": "Chinese",
      "description": "Five elements",
      "aliases": []
    },
    {
      "name": "Lug",
      "type": "deity",
      "culture": "Irish",
      "description": "Master of all arts, kills Balor",
      "aliases": [
        "Lugh",
        "Samildanach"
      ]
    },
    {
      "name": "Nuadu Airgetlam",
      "type": "deity",
      "culture": "Irish",
      "description": "First king of TDD, lost and regained hand"
    },
    {
      "name": "Goibniu",
      "type": "deity",
      "culture": "Irish",
      "description": "Smith, forges unbreakable weapons"
    },
    {
      "name": "Bres mac Elathan",
      "type": "deity",
      "culture": "Irish",
      "description": "Half-Fomorian, tyrannical king"
    },
    {
      "name": "Cian",
      "type": "deity",
      "culture": "Irish",
      "description": "Father of Lug"
    },
    {
      "name": "Ethne",
      "type": "deity",
      "culture": "Irish",
      "description": "Mother of Lug, daughter of Balor"
    },
    {
      "name": "Tailtiu",
      "type": "deity",
      "culture": "Irish",
      "description": "Foster mother of Lug"
    },
    {
      "name": "Miach",
      "type": "deity",
      "culture": "Irish",
      "description": "Son of Dian Cecht, heals Nuadu's hand"
    },
    {
      "name": "Airmed",
      "type": "deity",
      "culture": "Irish",
      "description": "Daughter of Dian Cecht, grows herbs from Miach's grave"
    },
    {
      "name": "Elatha",
      "type": "deity",
      "culture": "Irish",
      "description": "Fomorian king, father of Bres and Ogma"
    },
    {
      "name": "Eriu",
      "type": "deity",
      "culture": "Irish",
      "description": "Mother of Bres, daughter of TDD"
    },
    {
      "name": "Coirpre",
      "type": "deity",
      "culture": "Irish",
      "description": "Poet, composes first satire against Bres"
    },
    {
      "name": "Net",
      "type": "deity",
      "culture": "Irish",
      "description": "Grandfather of Balor"
    },
    {
      "name": "Macha",
      "type": "deity",
      "culture": "Irish",
      "description": "Killed by Balor in battle"
    },
    {
      "name": "Mac Oc",
      "type": "deity",
      "culture": "Irish",
      "description": "Son of Dagda, tricks him out of Brú na Bóinne"
    }
  ],
  "relationships": [
    {
      "source": "Apsu",
      "target": "Tiamat",
      "type": "parent_of",
      "context": "Apsu and Tiamat are the primeval freshwater and saltwater oceans that existed before the creation of the cosmos."
    },
    {
      "source": "Tiamat",
      "target": "Lahmu",
      "type": "parent_of",
      "context": "Tiamat is the mother of the gods, including Lahmu and Lahamu."
    },
    {
      "source": "Tiamat",
      "target": "Lahamu",
      "type": "parent_of",
      "context": "Tiamat is the mother of the gods, including Lahmu and Lahamu."
    },
    {
      "source": "Ansar",
      "target": "Kisar",
      "type": "sibling_of",
      "context": "Ansar and Kisar are primordial deities, the first generation of gods."
    },
    {
      "source": "Ansar",
      "target": "Ea",
      "type": "parent_of",
      "context": "Ea (also known as Nudimmud) is the son of Ansar."
    },
    {
      "source": "Tiamat",
      "target": "Kingu",
      "type": "exalted",
      "context": "Tiamat exalted Kingu and made him the leader of her forces against the other gods."
    },
    {
      "source": "Ansar",
      "target": "Gaga",
      "type": "servant",
      "context": "Gaga is Ansar's minister, sent to deliver a message."
    },
    {
      "source": "Marduk",
      "target": "Tiamat",
      "type": "battles",
      "context": "Marduk is destined to become the champion and avenger of the gods against Tiamat."
    },
    {
      "source": "Gilgamesh",
      "target": "Uruk",
      "type": "rules_over",
      "context": "Gilgamesh is the king of Uruk."
    },
    {
      "source": "Anu",
      "target": "Uruk",
      "type": "rules_over",
      "context": "Anu is the god of the firmament, to whom the temple of Eanna in Uruk is dedicated."
    },
    {
      "source": "Ishtar",
      "target": "Uruk",
      "type": "rules_over",
      "context": "Ishtar is the goddess of love, to whom the temple of Eanna in Uruk is also dedicated."
    },
    {
      "source": "Aruru",
      "target": "Enkidu",
      "type": "created",
      "context": "Aruru created Enkidu to be Gilgamesh's equal."
    },
    {
      "source": "Ninurta",
      "target": "Enkidu",
      "type": "possesses",
      "context": "Enkidu has the virtues of the god of war, Ninurta."
    },
    {
      "source": "Samugan",
      "target": "Enkidu",
      "type": "possesses",
      "context": "Enkidu's body is covered in matted hair like the god of cattle, Samugan."
    },
    {
      "source": "Nisaba",
      "target": "Enkidu",
      "type": "possesses",
      "context": "Enkidu's hair waves like the hair of the goddess of corn, Nisaba."
    },
    {
      "source": "Ninsun",
      "target": "Gilgamesh",
      "type": "parent_of",
      "context": "Ninsun is Gilgamesh's mother."
    },
    {
      "source": "Shamash",
      "target": "Gilgamesh",
      "type": "gave",
      "context": "Shamash the sun god endowed Gilgamesh with beauty."
    },
    {
      "source": "Adad",
      "target": "Gilgamesh",
      "type": "gave",
      "context": "Adad the storm god endowed Gilgamesh with courage."
    },
    {
      "source": "Enlil",
      "target": "Gilgamesh",
      "type": "gave",
      "context": "Enlil was one of the chief gods who gave Gilgamesh deep understanding."
    },
    {
      "source": "Ea",
      "target": "Gilgamesh",
      "type": "gave",
      "context": "Ea the wise god gave Gilgamesh deep understanding."
    },
    {
      "source": "Anunna",
      "target": "Igigi",
      "type": "rules_over",
      "context": "The Anunna-gods burdened the Igigi-gods with forced labor"
    },
    {
      "source": "Ea",
      "target": "Nintu",
      "type": "proposes",
      "context": "Ea proposes that Nintu create a human to relieve the gods' forced labor"
    },
    {
      "source": "Nintu",
      "target": "Enki",
      "type": "defers_to",
      "context": "Nintu says the task of creating humans is Enki's"
    },
    {
      "source": "Enki",
      "target": "Aw-ilu",
      "type": "sacrifices",
      "context": "Enki has the god Aw-ilu slaughtered, and his flesh and blood used to create humans"
    },
    {
      "source": "Enki",
      "target": "Atrahasis",
      "type": "warns",
      "context": "Enki warns Atrahasis in a dream about the coming flood"
    },
    {
      "source": "Enlil",
      "target": "Humans",
      "type": "punishes",
      "context": "Enlil decides to extinguish mankind by a Great Flood"
    },
    {
      "source": "Enki",
      "target": "Nintu",
      "type": "proposes",
      "context": "Enki proposes measures to Nintu to limit human population after the flood"
    },
    {
      "source": "Semjaza",
      "target": "Watchers",
      "type": "leads",
      "context": "Led 200 angels to descend to Earth"
    },
    {
      "source": "Azazel",
      "target": "humans",
      "type": "taught",
      "context": "Taught humans forbidden knowledge"
    },
    {
      "source": "Armaros",
      "target": "humans",
      "type": "taught",
      "context": "Taught the resolving of enchantments"
    },
    {
      "source": "Baraqijal",
      "target": "humans",
      "type": "taught",
      "context": "Taught astrology"
    },
    {
      "source": "Kokabel",
      "target": "humans",
      "type": "taught",
      "context": "Taught the constellations"
    },
    {
      "source": "Ezeqeel",
      "target": "humans",
      "type": "taught",
      "context": "Taught the knowledge of the clouds"
    },
    {
      "source": "Araqiel",
      "target": "humans",
      "type": "taught",
      "context": "Taught the signs of the earth"
    },
    {
      "source": "Shamsiel",
      "target": "humans",
      "type": "taught",
      "context": "Taught the signs of the sun"
    },
    {
      "source": "Sariel",
      "target": "humans",
      "type": "taught",
      "context": "Taught the course of the moon"
    },
    {
      "source": "Michael",
      "target": "humans",
      "type": "observed",
      "context": "Observed the lawlessness on Earth"
    },
    {
      "source": "Uriel",
      "target": "Noah",
      "type": "instructed",
      "context": "Instructed Noah about the coming flood"
    },
    {
      "source": "Raphael",
      "target": "Azazel",
      "type": "bound",
      "context": "Bound Azazel and cast him into Dudael"
    },
    {
      "source": "Watchers",
      "target": "humans",
      "type": "mated with",
      "context": "Took human wives and produced the Nephilim giants"
    },
    {
      "source": "Dagda",
      "target": "Brigid",
      "type": "parent_of",
      "context": "Brigid was the daughter of the Dagda"
    },
    {
      "source": "Dagda",
      "target": "Brug na Boinne",
      "type": "associated_with",
      "context": "The Brug na Boinne was persistently associated with the Dagda and his family"
    },
    {
      "source": "Dagda",
      "target": "Fomorians",
      "type": "fought_against",
      "context": "The Dagda fought against the Fomorians in the Second Battle of Mag Tuired"
    },
    {
      "source": "Lugh",
      "target": "Dagda",
      "type": "succeeded",
      "context": "Lugh succeeded the Dagda as king of the Tuatha Dé Danann"
    },
    {
      "source": "Nuada",
      "target": "Dian Cecht",
      "type": "cured_by",
      "context": "Dian Cecht cured Nuada's wounded arm"
    },
    {
      "source": "Morrigan",
      "target": "Dagda",
      "type": "associated_with",
      "context": "The Morrigan is associated with the Dagda in Irish mythology"
    },
    {
      "source": "Manannán",
      "target": "Tuatha Dé Danann",
      "type": "associated_with",
      "context": "Manannán is a figure associated with the Tuatha Dé Danann"
    },
    {
      "source": "Ogma",
      "target": "Delbaeth",
      "type": "parent_of",
      "context": "Delbaeth was the son of Ogma"
    },
    {
      "source": "Balor",
      "target": "Lugh",
      "type": "grandfather_of",
      "context": "Lugh was the grandson of Balor"
    },
    {
      "source": "Bres",
      "target": "Tuatha Dé Danann",
      "type": "king_of",
      "context": "Bres was a king of the Tuatha Dé Danann"
    },
    {
      "source": "Alulim",
      "target": "Eridu",
      "type": "ruled",
      "context": "First king of Eridu"
    },
    {
      "source": "Alalgar",
      "target": "Eridu",
      "type": "ruled",
      "context": "Second king of Eridu"
    },
    {
      "source": "Enmen-lu-ana",
      "target": "Bad-tibira",
      "type": "ruled",
      "context": "King of Bad-tibira"
    },
    {
      "source": "Enmen-gal-ana",
      "target": "Bad-tibira",
      "type": "ruled",
      "context": "King of Bad-tibira"
    },
    {
      "source": "Dumuzi",
      "target": "Bad-tibira",
      "type": "ruled",
      "context": "The shepherd king of Bad-tibira"
    },
    {
      "source": "En-sipad-zid-ana",
      "target": "Larak",
      "type": "ruled",
      "context": "King of Larak"
    },
    {
      "source": "Enmen-dur-ana",
      "target": "Sippar",
      "type": "ruled",
      "context": "King of Sippar"
    },
    {
      "source": "Ubara-Tutu",
      "target": "Shuruppak",
      "type": "ruled",
      "context": "King of Shuruppak"
    },
    {
      "source": "Etana",
      "target": "Kish",
      "type": "ruled",
      "context": "Shepherd king of Kish who ascended to heaven"
    },
    {
      "source": "Enmen-baragesi",
      "target": "Kish",
      "type": "ruled",
      "context": "King of Kish who destroyed Elam's weapons"
    },
    {
      "source": "Agga",
      "target": "Kish",
      "type": "ruled",
      "context": "King of Kish, son of Enmen-baragesi"
    },
    {
      "source": "Mes-ki'ag-gaser",
      "target": "Uruk",
      "type": "ruled",
      "context": "Lord and king of Uruk, son of the sun god Utu"
    },
    {
      "source": "Enmerkar",
      "target": "Uruk",
      "type": "ruled",
      "context": "King of Uruk, son of Mes-ki'ag-gaser"
    },
    {
      "source": "Lugal-banda",
      "target": "Uruk",
      "type": "ruled",
      "context": "The shepherd king of Uruk"
    },
    {
      "source": "Gilgamesh",
      "target": "Kulaba",
      "type": "ruled",
      "context": "Lord of Kulaba, whose father was an invisible being"
    },
    {
      "source": "Hurakan",
      "target": "Gucumatz",
      "type": "creator",
      "context": "Deliberated and created the world"
    },
    {
      "source": "Hurakan",
      "target": "Xpiyacoc",
      "type": "creator",
      "context": "Deliberated and created the world"
    },
    {
      "source": "Hurakan",
      "target": "Xmucane",
      "type": "creator",
      "context": "Deliberated and created the world"
    },
    {
      "source": "Hurakan",
      "target": "Tepeu",
      "type": "creator",
      "context": "Deliberated and created the world"
    },
    {
      "source": "Hun-Ahpu",
      "target": "Xbalanque",
      "type": "twin",
      "context": "Hero twins who defeated the titans"
    },
    {
      "source": "Vukub-Cakix",
      "target": "Zipacna",
      "type": "parent",
      "context": "Vukub-Cakix was the father of Zipacna and Cabrakan"
    },
    {
      "source": "Vukub-Cakix",
      "target": "Cabrakan",
      "type": "parent",
      "context": "Vukub-Cakix was the father of Zipacna and Cabrakan"
    },
    {
      "source": "Hun-Came",
      "target": "Vukub-Came",
      "type": "ruler",
      "context": "Co-rulers of the Underworld (Xibalba)"
    },
    {
      "source": "Balam-Quitze",
      "target": "Tohil",
      "type": "patron",
      "context": "Tohil was the tribal god given to Balam-Quitze"
    },
    {
      "source": "Balam-Agab",
      "target": "Avilix",
      "type": "patron",
      "context": "Avilix was the tribal god given to Balam-Agab"
    },
    {
      "source": "Mahucutah",
      "target": "Hacavitz",
      "type": "patron",
      "context": "Hacavitz was the tribal god given to Mahucutah"
    },
    {
      "source": "Xquiq",
      "target": "Hunhun-Ahpu",
      "type": "mother",
      "context": "Xquiq was impregnated by Hunhun-Ahpu and bore the hero twins"
    },
    {
      "source": "400 youths",
      "target": "stars",
      "type": "transformation",
      "context": "The 400 youths slain by Zipacna became the stars in the sky"
    },
    {
      "source": "Inanna",
      "target": "Ereshkigal",
      "type": "sibling",
      "context": "Inanna visits her sister Ereshkigal in the Underworld"
    },
    {
      "source": "Inanna",
      "target": "Ninshubur",
      "type": "servant",
      "context": "Ninshubur is the faithful servant/sukkal of Inanna"
    },
    {
      "source": "Inanna",
      "target": "Shara",
      "type": "parent",
      "context": "Shara is the son of Inanna"
    },
    {
      "source": "Inanna",
      "target": "Lulal",
      "type": "parent",
      "context": "Lulal is the son of Inanna"
    },
    {
      "source": "Inanna",
      "target": "Dumuzi",
      "type": "spouse",
      "context": "Dumuzi is the husband of Inanna"
    },
    {
      "source": "Enki",
      "target": "Kurgarra",
      "type": "creator",
      "context": "Enki fashioned the Kurgarra from dirt"
    },
    {
      "source": "Enki",
      "target": "Galatur",
      "type": "creator",
      "context": "Enki fashioned the Galatur from dirt"
    },
    {
      "source": "Enlil",
      "target": "Inanna",
      "type": "refusal",
      "context": "Enlil refused to help Inanna"
    },
    {
      "source": "Nanna",
      "target": "Inanna",
      "type": "refusal",
      "context": "Nanna refused to help Inanna"
    },
    {
      "source": "Utu",
      "target": "Dumuzi",
      "type": "help",
      "context": "Utu helped Dumuzi"
    },
    {
      "source": "Galla",
      "target": "Inanna",
      "type": "pursuit",
      "context": "The Galla demons pursued Inanna after she left the Underworld"
    },
    {
      "source": "Vishnu",
      "target": "Matsya",
      "type": "avatar",
      "context": "Vishnu takes the Matsya avatar"
    },
    {
      "source": "Vishnu",
      "target": "Manu/Satyavrata/Vaivasvata",
      "type": "warns",
      "context": "Vishnu warns Manu about the impending flood"
    },
    {
      "source": "Manu/Satyavrata/Vaivasvata",
      "target": "Saptarishi",
      "type": "collects",
      "context": "Manu collects the Seven Great Sages to board the ship"
    },
    {
      "source": "Hayagriva",
      "target": "Vedas",
      "type": "steals",
      "context": "Hayagriva steals the Vedas and hides them in the cosmic ocean"
    },
    {
      "source": "Vishnu",
      "target": "Vedas",
      "type": "recovers",
      "context": "Vishnu recovers the Vedas from the cosmic ocean"
    },
    {
      "source": "Manu/Satyavrata/Vaivasvata",
      "target": "Ila/Shraddha",
      "type": "progenitors",
      "context": "Manu and Ila/Shraddha become the progenitors of all humanity"
    },
    {
      "source": "Matsya",
      "target": "Ship",
      "type": "guides",
      "context": "Vishnu-as-Matsya guides the ship through the cosmic waters"
    },
    {
      "source": "Vasuki",
      "target": "Ship",
      "type": "ties",
      "context": "Vasuki is used as a rope to tie the ship to Matsya's horn"
    },
    {
      "source": "Odin",
      "target": "Vili",
      "type": "brother",
      "context": "Odin, Vili, and Ve killed Ymir and created the world"
    },
    {
      "source": "Odin",
      "target": "Ve",
      "type": "brother",
      "context": "Odin, Vili, and Ve killed Ymir and created the world"
    },
    {
      "source": "Odin",
      "target": "Ask",
      "type": "creator",
      "context": "Odin, Vili, and Ve created the first humans, Ask and Embla"
    },
    {
      "source": "Odin",
      "target": "Embla",
      "type": "creator",
      "context": "Odin, Vili, and Ve created the first humans, Ask and Embla"
    },
    {
      "source": "Loki",
      "target": "Fenrir",
      "type": "father",
      "context": "Loki is the father of the monsters Fenrir, Jormungandr, and Hel"
    },
    {
      "source": "Loki",
      "target": "Jormungandr",
      "type": "father",
      "context": "Loki is the father of the monsters Fenrir, Jormungandr, and Hel"
    },
    {
      "source": "Loki",
      "target": "Hel",
      "type": "father",
      "context": "Loki is the father of the monsters Fenrir, Jormungandr, and Hel"
    },
    {
      "source": "Ymir",
      "target": "world",
      "type": "creator",
      "context": "Ymir's body was used to create the world"
    },
    {
      "source": "Audhumla",
      "target": "Ymir",
      "type": "nourisher",
      "context": "Audhumla, the primeval cow, nourished Ymir"
    },
    {
      "source": "Audhumla",
      "target": "Buri",
      "type": "revealer",
      "context": "Audhumla revealed Buri, the first of the gods"
    },
    {
      "source": "God",
      "target": "Adam",
      "type": "created",
      "context": "Formed from dust of the ground"
    },
    {
      "source": "God",
      "target": "Eve",
      "type": "created",
      "context": "Formed from Adam's rib"
    },
    {
      "source": "Cain",
      "target": "Abel",
      "type": "killed",
      "context": "Cain murdered Abel"
    },
    {
      "source": "God",
      "target": "Noah",
      "type": "instructed",
      "context": "Told Noah to build the Ark"
    },
    {
      "source": "God",
      "target": "Humanity",
      "type": "destroyed",
      "context": "Destroyed humanity with the Flood"
    },
    {
      "source": "Noah",
      "target": "Animals",
      "type": "saved",
      "context": "Noah saved pairs of animals in the Ark"
    },
    {
      "source": "God",
      "target": "Noah",
      "type": "made covenant",
      "context": "God made a covenant with Noah after the Flood"
    },
    {
      "source": "Sons of God",
      "target": "Daughters of men",
      "type": "mated",
      "context": "Produced the Nephilim"
    },
    {
      "source": "Tubal-cain",
      "target": "Humans",
      "type": "taught",
      "context": "Taught metalworking to humans"
    },
    {
      "source": "Nimrod",
      "target": "Cities",
      "type": "built",
      "context": "Built cities like Babel, Erech, Accad, and Nineveh"
    },
    {
      "source": "Semjaza",
      "target": "Ohya",
      "type": "father",
      "context": "Ohya was the son of Semjaza"
    },
    {
      "source": "Semjaza",
      "target": "Hahya",
      "type": "father",
      "context": "Hahya was the son of Semjaza"
    },
    {
      "source": "Ohya",
      "target": "Hahya",
      "type": "sibling",
      "context": "Ohya and Hahya were brothers"
    },
    {
      "source": "Mahaway",
      "target": "Enoch",
      "type": "messenger",
      "context": "Mahaway flew to Enoch to interpret dreams"
    },
    {
      "source": "Baraq'el",
      "target": "Baraqiel",
      "type": "named after",
      "context": "Baraq'el was named after the Watcher Baraqiel"
    },
    {
      "source": "Gilgamesh",
      "target": "Nephilim",
      "type": "member",
      "context": "Gilgamesh appeared as one of the giants"
    },
    {
      "source": "Watchers",
      "target": "Giants",
      "type": "fathers",
      "context": "The Watchers were the fathers of the Giants"
    },
    {
      "source": "Giants",
      "target": "Monsters",
      "type": "offspring",
      "context": "The Giants produced animal-human hybrid Monsters"
    },
    {
      "source": "Ohya",
      "target": "Flood",
      "type": "dreamed",
      "context": "Ohya had a dream about the coming Flood"
    },
    {
      "source": "Hahya",
      "target": "Flood",
      "type": "dreamed",
      "context": "Hahya had a dream about the coming Flood"
    },
    {
      "source": "Zeus",
      "target": "Kronos",
      "type": "overthrew",
      "context": "Led Titanomachy against his father"
    },
    {
      "source": "Kronos",
      "target": "Ouranos",
      "type": "overthrew",
      "context": "Castrated Ouranos"
    },
    {
      "source": "Gaia",
      "target": "Ouranos",
      "type": "produced",
      "context": "Together they produced the Titans"
    },
    {
      "source": "Prometheus",
      "target": "Humans",
      "type": "created",
      "context": "Fashioned humans from clay"
    },
    {
      "source": "Prometheus",
      "target": "Fire",
      "type": "stole",
      "context": "Gave fire to humanity"
    },
    {
      "source": "Zeus",
      "target": "Prometheus",
      "type": "punished",
      "context": "Chained him to a rock for stealing fire"
    },
    {
      "source": "Zeus",
      "target": "Pandora",
      "type": "created",
      "context": "As punishment for humanity"
    },
    {
      "source": "Deucalion",
      "target": "Pyrrha",
      "type": "married",
      "context": "Survived the great flood together"
    },
    {
      "source": "Heracles",
      "target": "Giants",
      "type": "defeated",
      "context": "Helped the gods defeat the Giants"
    },
    {
      "source": "Zeus",
      "target": "Humanity",
      "type": "destroyed",
      "context": "Sent the great flood to destroy humanity"
    },
    {
      "source": "Pushpaka Vimana",
      "target": "Kubera",
      "type": "belonged to",
      "context": "Originally belonging to the god of wealth"
    },
    {
      "source": "Pushpaka Vimana",
      "target": "Ravana",
      "type": "stolen by",
      "context": "Stolen by Ravana in the Ramayana"
    },
    {
      "source": "Arjuna's chariot",
      "target": "Indra",
      "type": "provided by",
      "context": "Provided by the king of gods"
    },
    {
      "source": "Brahmastra",
      "target": "Brahma",
      "type": "associated with",
      "context": "Brahma's powerful weapon"
    },
    {
      "source": "Pasupatastra",
      "target": "Shiva",
      "type": "associated with",
      "context": "Shiva's weapon, capable of destroying all creation"
    },
    {
      "source": "Narayanastra",
      "target": "Vishnu",
      "type": "associated with",
      "context": "Vishnu's weapon, releases millions of missiles"
    },
    {
      "source": "Varunastra",
      "target": "Varuna",
      "type": "associated with",
      "context": "Varuna's weapon, controls water and creates floods"
    },
    {
      "source": "Vayavyastra",
      "target": "Vayu",
      "type": "associated with",
      "context": "Vayu's weapon, creates hurricanes and tornados"
    },
    {
      "source": "Agneyastra",
      "target": "Agni",
      "type": "associated with",
      "context": "Agni's weapon, generates unquenchable fire"
    },
    {
      "source": "Yudhishthira",
      "target": "Dharma",
      "type": "son of",
      "context": "Son of the god of justice"
    },
    {
      "source": "Atum",
      "target": "Shu",
      "type": "created",
      "context": "Atum created Shu and Tefnut"
    },
    {
      "source": "Shu",
      "target": "Geb",
      "type": "created",
      "context": "Shu and Tefnut created Geb and Nut"
    },
    {
      "source": "Geb",
      "target": "Osiris",
      "type": "created",
      "context": "Geb and Nut created Osiris, Isis, Set, and Nephthys"
    },
    {
      "source": "Osiris",
      "target": "Set",
      "type": "killed",
      "context": "Set killed Osiris"
    },
    {
      "source": "Isis",
      "target": "Osiris",
      "type": "resurrected",
      "context": "Isis resurrected Osiris"
    },
    {
      "source": "Horus",
      "target": "Set",
      "type": "defeated",
      "context": "Horus defeated Set"
    },
    {
      "source": "Anubis",
      "target": "Osiris",
      "type": "judged",
      "context": "Anubis judged the deceased in the underworld"
    },
    {
      "source": "Ma'at",
      "target": "Osiris",
      "type": "judged",
      "context": "The heart was weighed against the feather of Ma'at"
    },
    {
      "source": "Ra",
      "target": "Apophis",
      "type": "battled",
      "context": "Ra battled the chaos serpent Apophis"
    },
    {
      "source": "Pharaoh",
      "target": "Ra",
      "type": "incarnated",
      "context": "The pharaoh was the living incarnation of Horus, son of Ra"
    },
    {
      "source": "Ahura Mazda",
      "target": "World",
      "type": "created",
      "context": "In six stages"
    },
    {
      "source": "Angra Mainyu",
      "target": "World",
      "type": "attacked",
      "context": "Burst through sky, polluted water, cracked earth, withered plants, killed Bull and Gayomart"
    },
    {
      "source": "Gayomart",
      "target": "Mashya",
      "type": "seed",
      "context": "Gayomart's seed grew into first human couple"
    },
    {
      "source": "Mashya",
      "target": "Angra Mainyu",
      "type": "deceived",
      "context": "Declared Angra Mainyu as creator, first lie/sin"
    },
    {
      "source": "Yima",
      "target": "Vara",
      "type": "built",
      "context": "Underground enclosure to survive terrible winter"
    },
    {
      "source": "Ahura Mazda",
      "target": "Fravashis",
      "type": "consulted",
      "context": "Before creation, asked if they wanted to incarnate and fight Angra Mainyu"
    },
    {
      "source": "Saoshyant",
      "target": "World",
      "type": "purify",
      "context": "With molten metal, at end of time"
    },
    {
      "source": "Angra Mainyu",
      "target": "World",
      "type": "destroyed",
      "context": "At end of time, by Saoshyant"
    },
    {
      "source": "Pangu",
      "target": "World",
      "type": "created",
      "context": "His body became earth, sky, rivers"
    },
    {
      "source": "Nüwa",
      "target": "Humans",
      "type": "created",
      "context": "Molded humans from clay"
    },
    {
      "source": "Gong Gong",
      "target": "Sky Pillar",
      "type": "destroyed",
      "context": "Broke pillar, causing flood"
    },
    {
      "source": "Nüwa",
      "target": "Sky Pillar",
      "type": "repaired",
      "context": "Patched hole in sky"
    },
    {
      "source": "Huangdi",
      "target": "Heaven",
      "type": "ascended",
      "context": "Ascended to heaven on a dragon"
    },
    {
      "source": "Huangdi",
      "target": "Knowledge",
      "type": "possessed",
      "context": "Had knowledge of technology and civilization"
    },
    {
      "source": "Gun",
      "target": "Flood",
      "type": "tried to stop",
      "context": "Stole 'breathing earth' but failed"
    },
    {
      "source": "Yu",
      "target": "Flood",
      "type": "channeled",
      "context": "Worked for 13 years to channel the waters"
    },
    {
      "source": "Lug",
      "target": "Balor",
      "type": "kills",
      "context": "Sling stone through the Evil Eye"
    },
    {
      "source": "Lug",
      "target": "Cian",
      "type": "son of",
      "context": "Son of Cian (son of Dian Cecht)"
    },
    {
      "source": "Lug",
      "target": "Ethne",
      "type": "son of",
      "context": "Son of Ethne (daughter of Balor)"
    },
    {
      "source": "Lug",
      "target": "Tailtiu",
      "type": "foster son of",
      "context": "Foster son of Tailtiu"
    },
    {
      "source": "Dagda",
      "target": "Morrigan",
      "type": "mates with",
      "context": "Mates with the Morrigan at the Ford of the Unshin before battle"
    },
    {
      "source": "Dagda",
      "target": "Mac Oc",
      "type": "father of",
      "context": "Father of Mac Oc (Aengus Óg) who tricks him out of Brú na Bóinne"
    },
    {
      "source": "Dian Cecht",
      "target": "Miach",
      "type": "father of",
      "context": "Father of Miach"
    },
    {
      "source": "Dian Cecht",
      "target": "Airmed",
      "type": "father of",
      "context": "Father of Airmed"
    },
    {
      "source": "Dian Cecht",
      "target": "Cian",
      "type": "father of",
      "context": "Father of Cian"
    },
    {
      "source": "Bres",
      "target": "Elatha",
      "type": "son of",
      "context": "Son of Elatha (Fomorian) and Eriu (TDD)"
    },
    {
      "source": "Nuadu",
      "target": "Lug",
      "type": "gives kingship to",
      "context": "Gives kingship to Lug"
    },
    {
      "source": "Goibniu",
      "target": "Luchta",
      "type": "part of trinity with",
      "context": "With Luchta (carpenter) and Credne (brazier) = trinity of craftsmen"
    },
    {
      "source": "Goibniu",
      "target": "Credne",
      "type": "part of trinity with",
      "context": "With Luchta (carpenter) and Credne (brazier) = trinity of craftsmen"
    },
    {
      "source": "Ogma",
      "target": "Indech mac De Domnann",
      "type": "kills",
      "context": "Kills Indech mac De Domnann in single combat"
    },
    {
      "source": "Balor",
      "target": "Lug",
      "type": "killed by",
      "context": "Killed by Lug: sling stone carries eye through back of head"
    }
  ],
  "key_events": [
    {
      "event": "Tiamat's Rebellion",
      "participants": [
        "Tiamat",
        "Apsu",
        "Mummu"
      ],
      "description": "Tiamat, the primordial saltwater ocean, conceives a hatred for the other gods and plans to destroy them. She arms herself and her son Kingu to lead her forces against the gods.",
      "significance": "This sets up the central conflict of the epic, the cosmic battle between Tiamat and the gods led by Marduk."
    },
    {
      "event": "Ansar Summons Marduk",
      "participants": [
        "Ansar",
        "Ea",
        "Marduk"
      ],
      "description": "Ansar, one of the primordial deities, summons his son Marduk and appoints him as the champion to defeat Tiamat and her forces.",
      "significance": "This establishes Marduk as the destined hero who will save the gods and create the cosmos from the chaos of Tiamat."
    },
    {
      "event": "Gaga Delivers Ansar's Message",
      "participants": [
        "Ansar",
        "Gaga",
        "Lahmu",
        "Lahamu"
      ],
      "description": "Ansar sends his minister Gaga to deliver a message to the gods Lahmu and Lahamu, informing them of Tiamat's rebellion and the need for Marduk to be appointed as the avenger.",
      "significance": "This sets the stage for the gods to gather and formally appoint Marduk as their champion against Tiamat."
    },
    {
      "event": "Gilgamesh's tyrannical rule",
      "participants": [
        "Gilgamesh",
        "people of Uruk"
      ],
      "description": "The people of Uruk lament Gilgamesh's tyrannical rule, as he abuses his power and takes their sons and daughters.",
      "significance": "This establishes Gilgamesh as a flawed hero who needs to be balanced and challenged."
    },
    {
      "event": "Creation of Enkidu",
      "participants": [
        "Aruru",
        "Enkidu"
      ],
      "description": "The goddess Aruru creates Enkidu, a wild man, to be Gilgamesh's equal and companion.",
      "significance": "Enkidu's creation sets up the central conflict and relationship of the epic."
    },
    {
      "event": "Enkidu's transformation",
      "participants": [
        "Enkidu",
        "harlot",
        "shepherds"
      ],
      "description": "Enkidu is civilized by a harlot, who teaches him the ways of human society and leads him to Uruk to challenge Gilgamesh.",
      "significance": "Enkidu's transformation from a wild man to a civilized being sets the stage for his encounter with Gilgamesh."
    },
    {
      "event": "Enkidu's challenge to Gilgamesh",
      "participants": [
        "Enkidu",
        "Gilgamesh"
      ],
      "description": "Enkidu enters Uruk and challenges Gilgamesh, declaring that he has come to change the old order.",
      "significance": "This confrontation between the two heroes sets up the central conflict and relationship of the epic."
    },
    {
      "event": "Revolt of the Lower Gods",
      "participants": [
        "Igigi",
        "Enlil"
      ],
      "description": "The Igigi-gods, burdened with forced labor, revolt against Enlil and attack his dwelling",
      "significance": "This revolt leads to the creation of humans to replace the Igigi and perform the gods' labor"
    },
    {
      "event": "Creation of Humans",
      "participants": [
        "Ea",
        "Nintu",
        "Aw-ilu"
      ],
      "description": "Ea proposes that Nintu create a human being from clay mixed with the flesh and blood of the slaughtered god Aw-ilu",
      "significance": "Humans are created specifically to bear the 'yoke' and 'drudgery of the gods', replacing the Igigi laborers"
    },
    {
      "event": "The Great Flood",
      "participants": [
        "Enlil",
        "Atrahasis",
        "Enki",
        "Adad",
        "Anzu"
      ],
      "description": "Enlil decides to destroy humanity with a great flood, but Enki warns the flood survivor Atrahasis in a dream. Atrahasis builds an ark, and the flood is unleashed with Adad's storms and Anzu's talons rending the sky.",
      "significance": "The flood serves as divine punishment for human overpopulation and noise, but Atrahasis is saved to restart humanity"
    },
    {
      "event": "Post-Flood Regulations",
      "participants": [
        "Enki",
        "Nintu"
      ],
      "description": "Enki proposes to Nintu measures to limit human population after the flood, including death, infertility, and celibacy",
      "significance": "These regulations establish a new order for humanity, with population control measures imposed by the gods"
    },
    {
      "event": "Fall of the Watchers",
      "participants": [
        "Semjaza",
        "Watchers"
      ],
      "description": "200 angels descended to Mount Hermon and took human wives",
      "significance": "Origin of evil and the Nephilim giants"
    },
    {
      "event": "Second Battle of Mag Tuired",
      "participants": [
        "Dagda",
        "Lugh",
        "Balor"
      ],
      "description": "The Tuatha Dé Danann defeat the Fomorians",
      "significance": "Establishes the Tuatha Dé Danann's rule in Ireland"
    },
    {
      "event": "Death of the Dagda",
      "participants": [
        "Dagda"
      ],
      "description": "The Dagda dies from a mortal wound inflicted by Cethlenn",
      "significance": "Marks the end of the Dagda's reign as king of the Tuatha Dé Danann"
    },
    {
      "event": "Healing of Nuada",
      "participants": [
        "Nuada",
        "Dian Cecht"
      ],
      "description": "Dian Cecht heals Nuada's wounded arm, restoring him as king",
      "significance": "Allows Nuada to continue ruling the Tuatha Dé Danann"
    },
    {
      "event": "Birth of Lugh",
      "participants": [
        "Lugh",
        "Balor"
      ],
      "description": "Lugh is born to Balor's daughter, a version of the Perseus myth",
      "significance": "Lugh's birth sets the stage for his eventual defeat of Balor"
    },
    {
      "event": "Reign of the Dagda",
      "participants": [
        "Dagda"
      ],
      "description": "The Dagda reigns as king of the Tuatha Dé Danann for 80 years",
      "significance": "Establishes the Dagda as a central figure in Irish mythology"
    },
    {
      "event": "Kingship descended from heaven",
      "participants": [],
      "description": "The kingship was believed to have descended from heaven to various Sumerian cities",
      "significance": "Indicates the divine mandate and sacred nature of Sumerian kingship"
    },
    {
      "event": "The Flood",
      "participants": [],
      "description": "The Flood is described as a clear dividing line in Sumerian history, separating the pre-flood and post-flood eras",
      "significance": "The Flood is a major mythological event that reset civilization, similar to the biblical Flood"
    },
    {
      "event": "Etana ascended to heaven",
      "participants": [
        "Etana"
      ],
      "description": "Etana, the shepherd king of Kish, is described as ascending to heaven",
      "significance": "This motif of a mortal ascending to heaven is found in other ancient Near Eastern traditions, such as Enoch in the Bible"
    },
    {
      "event": "Gilgamesh's father was an invisible being",
      "participants": [
        "Gilgamesh"
      ],
      "description": "Gilgamesh, the lord of Kulaba, is described as having an invisible or phantom-like father",
      "significance": "This suggests a divine or supernatural parentage for Gilgamesh, similar to the concept of divine-human hybrids (Nephilim) in other ancient traditions"
    },
    {
      "event": "Creation of the world",
      "participants": [
        "Hurakan",
        "Gucumatz",
        "Xpiyacoc",
        "Xmucane",
        "Tepeu"
      ],
      "description": "The creator gods deliberated and brought forth the earth and animals, but not yet man.",
      "significance": "Establishes the Kiché creation myth and the pantheon of creator deities."
    },
    {
      "event": "Destruction of the wooden men",
      "participants": [
        "Hurakan",
        "wooden men"
      ],
      "description": "The wooden men created by the gods displeased them, so Hurakan caused a great flood to destroy them.",
      "significance": "Demonstrates the theme of failed creations being destroyed, a common motif in creation myths."
    },
    {
      "event": "Defeat of the titans",
      "participants": [
        "Hun-Ahpu",
        "Xbalanque",
        "Vukub-Cakix",
        "Zipacna",
        "Cabrakan"
      ],
      "description": "The hero twins Hun-Ahpu and Xbalanque defeated the arrogant titans Vukub-Cakix, Zipacna, and Cabrakan.",
      "significance": "Establishes the hero twins as the champions who overcome the destructive forces of the titans."
    },
    {
      "event": "Descent to the Underworld",
      "participants": [
        "Hun-Ahpu",
        "Xbalanque",
        "Hun-Came",
        "Vukub-Came",
        "Camazotz"
      ],
      "description": "The hero twins underwent ordeals in the Underworld (Xibalba) and defeated the Underworld lords.",
      "significance": "Demonstrates the theme of the hero twins' journey to the Underworld and their triumph over the forces of death, a common motif in mythology."
    },
    {
      "event": "Creation of the first men",
      "participants": [
        "Creator and Former",
        "Balam-Quitze",
        "Balam-Agab",
        "Mahucutah",
        "Iqi-Balam"
      ],
      "description": "The Creator and Former made the first four perfect men from maize, and then created their wives.",
      "significance": "Establishes the Kiché origin of humanity, with the first men created from maize, a common theme in Mesoamerican mythology."
    },
    {
      "event": "Inanna's Descent to the Underworld",
      "participants": [
        "Inanna",
        "Ereshkigal"
      ],
      "description": "Inanna, Queen of Heaven, descends to the Underworld (kur) to visit her sister Ereshkigal. She passes through 7 gates, losing one of her 7 divine garments/objects (me) at each gate. Stripped naked, she is killed by Ereshkigal and hung on a hook.",
      "significance": "This descent and stripping of power/identity is a key theme in the myth, paralleling similar motifs in other cultures."
    },
    {
      "event": "Inanna's Resurrection",
      "participants": [
        "Inanna",
        "Ninshubur",
        "Enki",
        "Kurgarra",
        "Galatur"
      ],
      "description": "After 3 days, Inanna's servant Ninshubur seeks help from the gods. Enki creates two beings, the Kurgarra and Galatur, from dirt. They retrieve Inanna's corpse and sprinkle her with the food and water of life, reviving her.",
      "significance": "Inanna's death and resurrection is a key motif, paralleling similar dying and reviving deity figures in other mythologies."
    },
    {
      "event": "Substitution of Dumuzi",
      "participants": [
        "Inanna",
        "Dumuzi"
      ],
      "description": "Inanna must provide a substitute to take her place in the Underworld. She chooses her husband Dumuzi, the shepherd, who did not mourn for her.",
      "significance": "The requirement of a substitute is a common theme in mythology, seen in the scapegoat ritual and the Christian concept of Christ as a substitute for humanity."
    },
    {
      "event": "Vishnu warns Manu about the impending flood",
      "participants": [
        "Vishnu",
        "Manu/Satyavrata/Vaivasvata"
      ],
      "description": "Vishnu appears to Manu as a small fish and warns him about the upcoming great deluge, instructing him to build a ship and gather the necessary supplies.",
      "significance": "This event sets the stage for the flood narrative and Manu's role as the survivor and progenitor of humanity."
    },
    {
      "event": "Manu collects the Saptarishi, seeds, and animals onto the ship",
      "participants": [
        "Manu/Satyavrata/Vaivasvata",
        "Saptarishi"
      ],
      "description": "Manu gathers the Seven Great Sages, seeds of all plants, and pairs of all animals onto the ship as instructed by Vishnu.",
      "significance": "This ensures the preservation of life on Earth during the flood, allowing for the recreation of the world after the waters recede."
    },
    {
      "event": "The great flood (pralaya) submerges the three worlds",
      "participants": [
        "Manu/Satyavrata/Vaivasvata",
        "Saptarishi"
      ],
      "description": "The cosmic flood, or pralaya, submerges the three worlds, destroying all life except for those on the ship guided by Matsya.",
      "significance": "This event represents the destruction of the old world and the preparation for the recreation of life on Earth."
    },
    {
      "event": "Vishnu recovers the stolen Vedas from the demon Hayagriva",
      "participants": [
        "Vishnu",
        "Hayagriva"
      ],
      "description": "While the flood is in progress, Vishnu descends into the cosmic ocean and recovers the Vedas, which had been stolen by the demon Hayagriva.",
      "significance": "The preservation of the sacred knowledge of the Vedas ensures the continuity of Hindu tradition and culture after the flood."
    },
    {
      "event": "Manu and Ila/Shraddha become the progenitors of humanity",
      "participants": [
        "Manu/Satyavrata/Vaivasvata",
        "Ila/Shraddha"
      ],
      "description": "After the flood, Manu performs a sacrifice, and from the sacrifice a woman named Ila/Shraddha appears. Together, Manu and Ila/Shraddha become the progenitors of all humanity.",
      "significance": "This event represents the recreation of life on Earth and the continuation of the human lineage after the great flood."
    },
    {
      "event": "Creation of the world",
      "participants": [
        "Odin",
        "Vili",
        "Ve"
      ],
      "description": "Odin, Vili, and Ve killed Ymir and used his body to create the world: his flesh = earth, his blood = seas, his bones = mountains, his skull = sky, his brains = clouds, his eyebrows = Midgard",
      "significance": "The creation of the world from the body of the primordial being Ymir is a common motif in mythology, seen in traditions like Enuma Elish and Chinese mythology."
    },
    {
      "event": "Creation of the first humans",
      "participants": [
        "Odin",
        "Vili",
        "Ve"
      ],
      "description": "Odin, Vili, and Ve created the first humans, Ask and Embla, from an ash tree and an elm tree. Odin gave them breath/spirit, Vili gave them understanding/movement, and Ve gave them form/speech/senses.",
      "significance": "The creation of the first humans from natural materials is a recurring theme in mythology, seen in traditions like the creation of Adam from dust in the Bible and the creation of humans from clay in Mesopotamian myths."
    },
    {
      "event": "Ragnarok",
      "participants": [
        "Odin",
        "Thor",
        "Loki",
        "Heimdall",
        "Fenrir",
        "Jormungandr",
        "Surtr"
      ],
      "description": "Fimbulwinter, the great wolf Fenrir breaking free, Jormungandr rising from the ocean, Loki leading the armies of the dead against Asgard, and the fire giant Surtr advancing with a flaming sword. Odin is swallowed by Fenrir, Thor kills Jormungandr but dies from its venom, Heimdall and Loki kill each other, and Surtr engulfs everything in fire, causing the earth to sink into the sea.",
      "significance": "Ragnarok, the apocalyptic destruction of the world, is a central event in Norse mythology that parallels the Great Flood and other catastrophic events in other mythological traditions. The subsequent renewal of the world is also a common theme."
    },
    {
      "event": "The Creation",
      "participants": [
        "God"
      ],
      "description": "God creates heaven, earth, and all life in 6 days",
      "significance": "Establishes God as creator of the universe"
    },
    {
      "event": "The Flood",
      "participants": [
        "God",
        "Noah"
      ],
      "description": "God destroys earth with flood, Noah survives in ark",
      "significance": "Divine reset of humanity"
    },
    {
      "event": "The Tower of Babel",
      "participants": [
        "Humans",
        "God"
      ],
      "description": "Humans build a tower to reach heaven, God confuses their language",
      "significance": "Limits human ambition and technological advancement"
    },
    {
      "event": "The Nephilim",
      "participants": [
        "Sons of God",
        "Daughters of men"
      ],
      "description": "Supernatural beings mate with humans, producing giants",
      "significance": "Demonstrates divine/human interbreeding"
    },
    {
      "event": "The Expulsion from Eden",
      "participants": [
        "Adam",
        "Eve",
        "God"
      ],
      "description": "Adam and Eve are expelled from the Garden of Eden",
      "significance": "Humans lose access to the divine realm"
    },
    {
      "event": "The Flood",
      "participants": [
        "God",
        "Noah"
      ],
      "description": "God destroys earth with flood, Noah survives",
      "significance": "Divine reset of humanity"
    },
    {
      "event": "Giants' Dreams of Flood",
      "participants": [
        "Ohya",
        "Hahya"
      ],
      "description": "Giants receive visions of the coming Flood",
      "significance": "Foreshadows the Flood's destruction"
    },
    {
      "event": "Mahaway's Flight to Enoch",
      "participants": [
        "Mahaway",
        "Enoch"
      ],
      "description": "Messenger giant flies to Enoch for dream interpretation",
      "significance": "Giants seek Enoch's divine knowledge"
    },
    {
      "event": "Enoch Confirms Destruction",
      "participants": [
        "Enoch",
        "Giants"
      ],
      "description": "Enoch tells giants their judgment is sealed",
      "significance": "Giants cannot prevent their doom"
    },
    {
      "event": "Giants' Corruption and Violence",
      "participants": [
        "Giants"
      ],
      "description": "Giants fill earth with violence and abominations",
      "significance": "Triggers divine judgment"
    },
    {
      "event": "Titanomachy",
      "participants": [
        "Zeus",
        "Kronos"
      ],
      "description": "Olympians defeat Titans",
      "significance": "New divine order established"
    },
    {
      "event": "Prometheus steals fire",
      "participants": [
        "Prometheus",
        "Humans"
      ],
      "description": "Prometheus gives fire to humanity",
      "significance": "Humans gain forbidden knowledge"
    },
    {
      "event": "Deucalion's Flood",
      "participants": [
        "Zeus",
        "Deucalion",
        "Pyrrha"
      ],
      "description": "Zeus destroys humanity, Deucalion and Pyrrha survive",
      "significance": "New humans created from stones"
    },
    {
      "event": "Gigantomachy",
      "participants": [
        "Olympian gods",
        "Giants"
      ],
      "description": "Gods defeat the Giants",
      "significance": "Olympian order solidified"
    },
    {
      "event": "Creation of Pandora",
      "participants": [
        "Zeus",
        "Pandora"
      ],
      "description": "Zeus creates Pandora as punishment for humanity",
      "significance": "Introduces evils into the world"
    },
    {
      "event": "Kurukshetra War",
      "participants": [
        "Pandavas",
        "Kauravas"
      ],
      "description": "Great war between two royal families",
      "significance": "Devastated the landscape, marked the end of Dvapara Yuga"
    },
    {
      "event": "Use of divine weapons",
      "participants": [
        "Pandavas",
        "Kauravas"
      ],
      "description": "Weapons of mass destruction used in the war",
      "significance": "Caused widespread destruction and loss of life"
    },
    {
      "event": "Dwarka submerged",
      "participants": [
        "Krishna"
      ],
      "description": "Krishna's city of Dwarka now underwater",
      "significance": "Parallels other submerged ancient civilizations"
    },
    {
      "event": "Divine/human interbreeding",
      "participants": [
        "Pandava heroes",
        "gods"
      ],
      "description": "Heroes fathered by gods through mantras",
      "significance": "Reflects themes of divine kingship and demigods"
    },
    {
      "event": "Brahmastra usage restrictions",
      "participants": [
        "Mahabharata text"
      ],
      "description": "Brahmastra should never be used on civilians",
      "significance": "Reflects divine laws of war"
    },
    {
      "event": "Creation from Primeval Waters",
      "participants": [
        "Nun",
        "Atum"
      ],
      "description": "Atum arose from the primeval waters of Nun"
    },
    {
      "event": "Osiris Myth",
      "participants": [
        "Osiris",
        "Set",
        "Isis",
        "Horus"
      ],
      "description": "Osiris was killed by Set, resurrected by Isis, and avenged by Horus"
    },
    {
      "event": "Underworld Journey",
      "participants": [
        "Ba",
        "Anubis",
        "Ma'at"
      ],
      "description": "The soul travels through the underworld, judged by Anubis and Ma'at"
    },
    {
      "event": "Stellar Alignment",
      "participants": [
        "Pharaoh",
        "Orion",
        "Sirius"
      ],
      "description": "Pyramids aligned to Orion and Sirius, representing Osiris and Isis"
    },
    {
      "event": "Creation through Divine Word",
      "participants": [
        "Ptah"
      ],
      "description": "Ptah created the world through thought and speech"
    },
    {
      "event": "Creation from Cosmic Egg",
      "participants": [
        "Ahura Mazda"
      ],
      "description": "Ahura Mazda created the world in six stages",
      "significance": "Origin of the cosmos"
    },
    {
      "event": "Attack by Angra Mainyu",
      "participants": [
        "Angra Mainyu"
      ],
      "description": "Angra Mainyu attacked and corrupted the creation",
      "significance": "Introduction of evil into the world"
    },
    {
      "event": "Building of the Vara",
      "participants": [
        "Yima"
      ],
      "description": "Yima built an underground enclosure to survive a terrible winter",
      "significance": "Preservation of life during a catastrophic event"
    },
    {
      "event": "Final Renovation",
      "participants": [
        "Saoshyant"
      ],
      "description": "Saoshyant will raise the dead, judge all souls, and purify the world",
      "significance": "Restoration of the world to its original perfection"
    },
    {
      "event": "Creation from Cosmic Egg",
      "participants": [
        "Pangu"
      ],
      "description": "Pangu breaks open egg, separates heaven and earth",
      "significance": "Origin of the cosmos"
    },
    {
      "event": "Creation of Humans",
      "participants": [
        "Nüwa"
      ],
      "description": "Nüwa creates humans from clay",
      "significance": "Origin of humanity"
    },
    {
      "event": "Destruction of Sky Pillar",
      "participants": [
        "Gong Gong"
      ],
      "description": "Gong Gong breaks sky pillar, causing flood",
      "significance": "Catastrophic event leading to restoration"
    },
    {
      "event": "Restoration of Order",
      "participants": [
        "Nüwa"
      ],
      "description": "Nüwa repairs sky and channels flood waters",
      "significance": "Reestablishment of cosmic balance"
    },
    {
      "event": "TDD arrive from Northern Islands with Four Treasures",
      "participants": [
        "TDD"
      ],
      "description": "TDD arrive with powerful artifacts",
      "significance": "Establishes TDD's power"
    },
    {
      "event": "Bres made king, tyranny and enslavement of gods",
      "participants": [
        "Bres",
        "TDD"
      ],
      "description": "Half-Fomorian Bres becomes tyrannical king",
      "significance": "Leads to Bres's deposition"
    },
    {
      "event": "Lug arrives at Tara, proves mastery, given kingship",
      "participants": [
        "Lug",
        "TDD"
      ],
      "description": "Lug demonstrates his skills, becomes king",
      "significance": "Lug leads TDD to victory"
    },
    {
      "event": "Battle: Lug kills Balor, Ogma kills Indech, Nuadu falls",
      "participants": [
        "Lug",
        "Balor",
        "Ogma",
        "Indech",
        "Nuadu"
      ],
      "description": "Key deities fight and die in the battle",
      "significance": "TDD defeat Fomorians, establish divine order"
    },
    {
      "event": "Morrigan prophesies peace, then the end of the world",
      "participants": [
        "Morrigan"
      ],
      "description": "Morrigan announces victory, then foretells the end",
      "significance": "Foreshadows future events"
    }
  ],
  "cross_cultural_patterns": [
    {
      "pattern_id": "arch-001",
      "name": "Divine Creation of Humans as Workers",
      "description": "Gods/divine beings create humans specifically to perform labor or serve the gods. Humans are fashioned from clay, blood, or divine substance.",
      "appears_in": [
        "Atra-Hasis (Sumerian)",
        "Enuma Elish (Babylonian)",
        "Genesis (Hebrew)",
        "Popol Vuh (Mayan)",
        "Prometheus myth (Greek)"
      ],
      "indicators": [
        "humans created from clay",
        "gods tired of labor",
        "divine blood mixed with earth",
        "humans made to serve"
      ],
      "significance": "Universal motif suggesting either shared cultural memory or independent convergence on the same metaphysical question"
    },
    {
      "pattern_id": "arch-002",
      "name": "Catastrophic Flood as Divine Reset",
      "description": "Divine council decides to destroy humanity via flood. One righteous human is warned and survives via a vessel. Post-flood, gods regret or grant immortality.",
      "appears_in": [
        "Gilgamesh Tablet XI",
        "Atra-Hasis",
        "Genesis 6-9",
        "Eridu Genesis",
        "Matsya Purana (Hindu)",
        "Popol Vuh",
        "Deucalion (Greek)",
        "Nu Wa (Chinese)"
      ],
      "indicators": [
        "divine council",
        "flood warning to one person",
        "vessel/ark constructed",
        "animals preserved",
        "rainbow/covenant after"
      ],
      "significance": "Appears in 200+ cultures globally. Either cultural diffusion from one event or independent flood memories from sea level rise (~12000 BCE)"
    },
    {
      "pattern_id": "arch-003",
      "name": "Divine/Human Interbreeding",
      "description": "Gods or divine beings mate with human women, producing semi-divine offspring with extraordinary powers. These offspring are often heroes or giants.",
      "appears_in": [
        "Genesis 6 (Nephilim)",
        "Gilgamesh (2/3 divine)",
        "Greek mythology (demigods)",
        "Book of Enoch (Watchers)",
        "Irish (Tuatha x humans)",
        "Mahabharata (Pandavas)"
      ],
      "indicators": [
        "sons of gods",
        "daughters of men",
        "giant offspring",
        "semi-divine hero",
        "forbidden union"
      ],
      "significance": "Recurring theme of divine genetics entering human bloodline â€” interpreted by AA as genetic engineering"
    },
    {
      "pattern_id": "arch-004",
      "name": "Underground Retreat of the Gods",
      "description": "Divine beings retreat underground or to another dimension, remaining present but hidden. They can be contacted at specific locations or times.",
      "appears_in": [
        "Tuatha DÃ© Danann â†’ SÃ­dhe (Irish)",
        "Anunnaki â†’ Abzu (Sumerian)",
        "Greek gods â†’ Underworld",
        "Hopi Ant People â†’ underground",
        "Hindu Nagas â†’ Patala"
      ],
      "indicators": [
        "gods go underground",
        "hollow hills",
        "dimensional gateway",
        "still present but hidden",
        "accessible at sacred sites"
      ],
      "significance": "Connected to Irish sacred site data â€” passage tombs as 'entrances to otherworld'"
    },
    {
      "pattern_id": "arch-005",
      "name": "Advanced Pre-Flood Civilization",
      "description": "Before the catastrophic flood, a highly advanced civilization existed. Post-flood survivors carried fragments of this knowledge. The civilization had technology beyond its era.",
      "appears_in": [
        "Sumerian King List (pre-flood kings)",
        "Plato's Atlantis",
        "Vedic Dwarka",
        "Irish Hy-Brasil",
        "Edgar Cayce readings",
        "GÃ¶bekli Tepe (archaeological)"
      ],
      "indicators": [
        "impossibly long reigns",
        "lost continent",
        "advanced construction",
        "star knowledge",
        "sudden civilization emergence"
      ],
      "significance": "GÃ¶bekli Tepe (9600 BCE) provides archaeological evidence of advanced construction pre-dating agriculture"
    },
    {
      "pattern_id": "arch-006",
      "name": "Solar/Astronomical Alignment Knowledge",
      "description": "Ancient structures demonstrate precise astronomical knowledge (solstice/equinox alignment, star mapping) that shouldn't have been possible without advanced instruments.",
      "appears_in": [
        "Newgrange (Irish)",
        "Giza (Egyptian)",
        "GÃ¶bekli Tepe (Turkish)",
        "Angkor Wat (Cambodian)",
        "Stonehenge (British)",
        "Chichen Itza (Mayan)"
      ],
      "indicators": [
        "solstice alignment",
        "equinox light box",
        "star constellation mapping",
        "precession awareness",
        "global coordinate system"
      ],
      "significance": "Direct connection to Irish Sacred Sites data â€” Newgrange winter solstice roofbox, Loughcrew equinox alignment"
    },
    {
      "pattern_id": "arch-007",
      "name": "Divine Kingship / Mandate of Heaven",
      "description": "Rulers claim direct descent from gods, with divine right to rule. Kingship 'descends from heaven' as a gift from the gods to humanity.",
      "appears_in": [
        "Sumerian King List",
        "Egyptian pharaohs (son of Ra)",
        "Chinese Mandate of Heaven",
        "Japanese emperor (Amaterasu descent)",
        "Irish High Kings (Tuatha lineage)"
      ],
      "indicators": [
        "kingship from heaven",
        "divine blood",
        "god-king",
        "pharaoh as living god",
        "sacred coronation site"
      ],
      "significance": "Connects political authority to divine origin across ALL major ancient civilizations"
    }
  ],
  "extractions": [
    {
      "source_text": "Enuma Elish Creation Epic",
      "culture": "Babylonian",
      "entities": [
        {
          "name": "Apsu",
          "type": "deity",
          "culture": "Babylonian",
          "description": "The primeval freshwater ocean that existed before the creation of the cosmos.",
          "aliases": []
        },
        {
          "name": "Tiamat",
          "type": "deity",
          "culture": "Babylonian",
          "description": "The primeval saltwater ocean that existed before the creation of the cosmos, also the mother of the gods.",
          "aliases": [
            "Ummu-Hubur"
          ]
        },
        {
          "name": "Lahmu",
          "type": "deity",
          "culture": "Babylonian",
          "description": "One of the first pair of gods to be created.",
          "aliases": []
        },
        {
          "name": "Lahamu",
          "type": "deity",
          "culture": "Babylonian",
          "description": "One of the first pair of gods to be created.",
          "aliases": []
        },
        {
          "name": "Ansar",
          "type": "deity",
          "culture": "Babylonian",
          "description": "A primordial deity, one of the first generation of gods.",
          "aliases": []
        },
        {
          "name": "Kisar",
          "type": "deity",
          "culture": "Babylonian",
          "description": "A primordial deity, one of the first generation of gods.",
          "aliases": []
        },
        {
          "name": "Anu",
          "type": "deity",
          "culture": "Babylonian",
          "description": "The sky god, ruler of the heavens.",
          "aliases": []
        },
        {
          "name": "Nudimmud",
          "type": "deity",
          "culture": "Babylonian",
          "description": "Another name for the god Ea, the god of wisdom and fresh water.",
          "aliases": [
            "Ea"
          ]
        },
        {
          "name": "Mummu",
          "type": "deity",
          "culture": "Babylonian",
          "description": "The minister and vizier of Apsu.",
          "aliases": []
        },
        {
          "name": "Kingu",
          "type": "deity",
          "culture": "Babylonian",
          "description": "One of Tiamat's sons, whom she exalted and made the leader of her forces against the other gods.",
          "aliases": []
        },
        {
          "name": "Anunnaki",
          "type": "group",
          "culture": "Babylonian",
          "description": "The group of major Mesopotamian deities.",
          "aliases": []
        },
        {
          "name": "Gaga",
          "type": "deity",
          "culture": "Babylonian",
          "description": "Ansar's minister, sent to deliver a message to Lahmu and Lahamu.",
          "aliases": []
        },
        {
          "name": "Marduk",
          "type": "deity",
          "culture": "Babylonian",
          "description": "The god who is destined to become the champion and avenger of the other gods against Tiamat.",
          "aliases": []
        },
        {
          "name": "Upsukkinaku",
          "type": "location",
          "culture": "Babylonian",
          "description": "The assembly hall of the gods.",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Apsu",
          "target": "Tiamat",
          "type": "parent_of",
          "context": "Apsu and Tiamat are the primeval freshwater and saltwater oceans that existed before the creation of the cosmos."
        },
        {
          "source": "Tiamat",
          "target": "Lahmu",
          "type": "parent_of",
          "context": "Tiamat is the mother of the gods, including Lahmu and Lahamu."
        },
        {
          "source": "Tiamat",
          "target": "Lahamu",
          "type": "parent_of",
          "context": "Tiamat is the mother of the gods, including Lahmu and Lahamu."
        },
        {
          "source": "Ansar",
          "target": "Kisar",
          "type": "sibling_of",
          "context": "Ansar and Kisar are primordial deities, the first generation of gods."
        },
        {
          "source": "Ansar",
          "target": "Ea",
          "type": "parent_of",
          "context": "Ea (also known as Nudimmud) is the son of Ansar."
        },
        {
          "source": "Tiamat",
          "target": "Kingu",
          "type": "exalted",
          "context": "Tiamat exalted Kingu and made him the leader of her forces against the other gods."
        },
        {
          "source": "Ansar",
          "target": "Gaga",
          "type": "servant",
          "context": "Gaga is Ansar's minister, sent to deliver a message."
        },
        {
          "source": "Marduk",
          "target": "Tiamat",
          "type": "battles",
          "context": "Marduk is destined to become the champion and avenger of the gods against Tiamat."
        }
      ],
      "cross_cultural_patterns": [
        {
          "pattern": "Primordial Deities",
          "description": "The concept of primordial deities, such as Apsu and Tiamat, who existed before the creation of the cosmos, is a common motif in ancient Near Eastern creation myths.",
          "appears_in": [
            "Babylonian",
            "Sumerian",
            "Akkadian"
          ]
        },
        {
          "pattern": "Cosmic Battle",
          "description": "The narrative of a cosmic battle between a creator god and a primordial, chaotic force is a recurring theme in many ancient creation myths.",
          "appears_in": [
            "Babylonian",
            "Sumerian",
            "Hittite",
            "Greek"
          ]
        },
        {
          "pattern": "Exaltation of a Hero",
          "description": "The motif of a deity or hero being exalted and given special powers or status to lead a battle or accomplish a task is found in various ancient mythologies.",
          "appears_in": [
            "Babylonian",
            "Sumerian",
            "Egyptian",
            "Hittite"
          ]
        }
      ],
      "key_events": [
        {
          "event": "Tiamat's Rebellion",
          "participants": [
            "Tiamat",
            "Apsu",
            "Mummu"
          ],
          "description": "Tiamat, the primordial saltwater ocean, conceives a hatred for the other gods and plans to destroy them. She arms herself and her son Kingu to lead her forces against the gods.",
          "significance": "This sets up the central conflict of the epic, the cosmic battle between Tiamat and the gods led by Marduk."
        },
        {
          "event": "Ansar Summons Marduk",
          "participants": [
            "Ansar",
            "Ea",
            "Marduk"
          ],
          "description": "Ansar, one of the primordial deities, summons his son Marduk and appoints him as the champion to defeat Tiamat and her forces.",
          "significance": "This establishes Marduk as the destined hero who will save the gods and create the cosmos from the chaos of Tiamat."
        },
        {
          "event": "Gaga Delivers Ansar's Message",
          "participants": [
            "Ansar",
            "Gaga",
            "Lahmu",
            "Lahamu"
          ],
          "description": "Ansar sends his minister Gaga to deliver a message to the gods Lahmu and Lahamu, informing them of Tiamat's rebellion and the need for Marduk to be appointed as the avenger.",
          "significance": "This sets the stage for the gods to gather and formally appoint Marduk as their champion against Tiamat."
        }
      ],
      "source_file": "Enuma_Elish_Creation_Epic.pdf"
    },
    {
      "source_text": "The Epic of Gilgamesh",
      "culture": "Mesopotamian",
      "entities": [
        {
          "name": "Gilgamesh",
          "type": "hero",
          "culture": "Mesopotamian",
          "description": "The king of Uruk, a demigod with superhuman strength and wisdom.",
          "aliases": []
        },
        {
          "name": "Enkidu",
          "type": "hero",
          "culture": "Mesopotamian",
          "description": "A wild man created by the gods to be Gilgamesh's equal and companion.",
          "aliases": []
        },
        {
          "name": "Uruk",
          "type": "location",
          "culture": "Mesopotamian",
          "description": "The great city where Gilgamesh rules as king.",
          "aliases": []
        },
        {
          "name": "Anu",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "The god of the heavens.",
          "aliases": []
        },
        {
          "name": "Ishtar",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "The goddess of love and war.",
          "aliases": []
        },
        {
          "name": "Aruru",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "The goddess of creation who made Enkidu.",
          "aliases": []
        },
        {
          "name": "Ninurta",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "The god of war, whose virtues were present in Enkidu.",
          "aliases": []
        },
        {
          "name": "Samugan",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "The god of cattle, whose appearance Enkidu shared.",
          "aliases": []
        },
        {
          "name": "Nisaba",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "The goddess of corn, whose hair Enkidu's resembled.",
          "aliases": []
        },
        {
          "name": "Ninsun",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "Gilgamesh's mother, a wise goddess.",
          "aliases": []
        },
        {
          "name": "Shamash",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "The glorious sun god who endowed Gilgamesh with beauty.",
          "aliases": []
        },
        {
          "name": "Adad",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "The god of the storm who endowed Gilgamesh with courage.",
          "aliases": []
        },
        {
          "name": "Enlil",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "One of the chief gods who gave Gilgamesh deep understanding.",
          "aliases": []
        },
        {
          "name": "Ea",
          "type": "deity",
          "culture": "Mesopotamian",
          "description": "The wise god who gave Gilgamesh deep understanding.",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Gilgamesh",
          "target": "Uruk",
          "type": "rules_over",
          "context": "Gilgamesh is the king of Uruk."
        },
        {
          "source": "Anu",
          "target": "Uruk",
          "type": "rules_over",
          "context": "Anu is the god of the firmament, to whom the temple of Eanna in Uruk is dedicated."
        },
        {
          "source": "Ishtar",
          "target": "Uruk",
          "type": "rules_over",
          "context": "Ishtar is the goddess of love, to whom the temple of Eanna in Uruk is also dedicated."
        },
        {
          "source": "Aruru",
          "target": "Enkidu",
          "type": "created",
          "context": "Aruru created Enkidu to be Gilgamesh's equal."
        },
        {
          "source": "Ninurta",
          "target": "Enkidu",
          "type": "possesses",
          "context": "Enkidu has the virtues of the god of war, Ninurta."
        },
        {
          "source": "Samugan",
          "target": "Enkidu",
          "type": "possesses",
          "context": "Enkidu's body is covered in matted hair like the god of cattle, Samugan."
        },
        {
          "source": "Nisaba",
          "target": "Enkidu",
          "type": "possesses",
          "context": "Enkidu's hair waves like the hair of the goddess of corn, Nisaba."
        },
        {
          "source": "Ninsun",
          "target": "Gilgamesh",
          "type": "parent_of",
          "context": "Ninsun is Gilgamesh's mother."
        },
        {
          "source": "Shamash",
          "target": "Gilgamesh",
          "type": "gave",
          "context": "Shamash the sun god endowed Gilgamesh with beauty."
        },
        {
          "source": "Adad",
          "target": "Gilgamesh",
          "type": "gave",
          "context": "Adad the storm god endowed Gilgamesh with courage."
        },
        {
          "source": "Enlil",
          "target": "Gilgamesh",
          "type": "gave",
          "context": "Enlil was one of the chief gods who gave Gilgamesh deep understanding."
        },
        {
          "source": "Ea",
          "target": "Gilgamesh",
          "type": "gave",
          "context": "Ea the wise god gave Gilgamesh deep understanding."
        }
      ],
      "cross_cultural_patterns": [
        {
          "pattern": "Demigod hero",
          "description": "A hero who is part divine and part human, possessing superhuman abilities.",
          "appears_in": [
            "Mesopotamian",
            "Greek",
            "Hindu"
          ]
        },
        {
          "pattern": "Creation of a companion",
          "description": "The gods create a companion for the hero to challenge and balance them.",
          "appears_in": [
            "Mesopotamian",
            "Greek",
            "Norse"
          ]
        },
        {
          "pattern": "Descent to the underworld",
          "description": "The hero undertakes a journey to the underworld or realm of the dead.",
          "appears_in": [
            "Mesopotamian",
            "Greek",
            "Egyptian"
          ]
        }
      ],
      "key_events": [
        {
          "event": "Gilgamesh's tyrannical rule",
          "participants": [
            "Gilgamesh",
            "people of Uruk"
          ],
          "description": "The people of Uruk lament Gilgamesh's tyrannical rule, as he abuses his power and takes their sons and daughters.",
          "significance": "This establishes Gilgamesh as a flawed hero who needs to be balanced and challenged."
        },
        {
          "event": "Creation of Enkidu",
          "participants": [
            "Aruru",
            "Enkidu"
          ],
          "description": "The goddess Aruru creates Enkidu, a wild man, to be Gilgamesh's equal and companion.",
          "significance": "Enkidu's creation sets up the central conflict and relationship of the epic."
        },
        {
          "event": "Enkidu's transformation",
          "participants": [
            "Enkidu",
            "harlot",
            "shepherds"
          ],
          "description": "Enkidu is civilized by a harlot, who teaches him the ways of human society and leads him to Uruk to challenge Gilgamesh.",
          "significance": "Enkidu's transformation from a wild man to a civilized being sets the stage for his encounter with Gilgamesh."
        },
        {
          "event": "Enkidu's challenge to Gilgamesh",
          "participants": [
            "Enkidu",
            "Gilgamesh"
          ],
          "description": "Enkidu enters Uruk and challenges Gilgamesh, declaring that he has come to change the old order.",
          "significance": "This confrontation between the two heroes sets up the central conflict and relationship of the epic."
        }
      ],
      "source_file": "Epic_of_Gilgamesh_Sandars.pdf"
    },
    {
      "source_text": "Atra-Hasis Epic",
      "culture": "Akkadian",
      "entities": [
        {
          "name": "Anu",
          "type": "deity",
          "culture": "Akkadian",
          "description": "Sky god",
          "aliases": []
        },
        {
          "name": "Enlil",
          "type": "deity",
          "culture": "Akkadian",
          "description": "Storm and authority god",
          "aliases": []
        },
        {
          "name": "Enki/Ea",
          "type": "deity",
          "culture": "Akkadian",
          "description": "Wisdom god",
          "aliases": []
        },
        {
          "name": "Nintu/Mami/Belet-ili",
          "type": "deity",
          "culture": "Akkadian",
          "description": "Birth goddess",
          "aliases": [
            "Mami",
            "Belet-kala-ili"
          ]
        },
        {
          "name": "Adad",
          "type": "deity",
          "culture": "Akkadian",
          "description": "Storm god",
          "aliases": []
        },
        {
          "name": "Anunna",
          "type": "divine beings",
          "culture": "Akkadian",
          "description": "The great gods",
          "aliases": []
        },
        {
          "name": "Igigi",
          "type": "divine beings",
          "culture": "Akkadian",
          "description": "The lower gods who revolted",
          "aliases": []
        },
        {
          "name": "Atrahasis",
          "type": "hero",
          "culture": "Akkadian",
          "description": "Flood survivor, described as 'exceedingly wise'",
          "aliases": []
        },
        {
          "name": "Aw-ilu",
          "type": "deity",
          "culture": "Akkadian",
          "description": "God who was slaughtered, whose blood was used to create humans",
          "aliases": []
        },
        {
          "name": "Anzu",
          "type": "creature",
          "culture": "Akkadian",
          "description": "Mythical bird",
          "aliases": []
        },
        {
          "name": "Tigris",
          "type": "location",
          "culture": "Akkadian",
          "description": "River",
          "aliases": []
        },
        {
          "name": "Euphrates",
          "type": "location",
          "culture": "Akkadian",
          "description": "River",
          "aliases": []
        },
        {
          "name": "Ekur",
          "type": "location",
          "culture": "Akkadian",
          "description": "Enlil's temple",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Anunna",
          "target": "Igigi",
          "type": "rules_over",
          "context": "The Anunna-gods burdened the Igigi-gods with forced labor"
        },
        {
          "source": "Ea",
          "target": "Nintu",
          "type": "proposes",
          "context": "Ea proposes that Nintu create a human to relieve the gods' forced labor"
        },
        {
          "source": "Nintu",
          "target": "Enki",
          "type": "defers_to",
          "context": "Nintu says the task of creating humans is Enki's"
        },
        {
          "source": "Enki",
          "target": "Aw-ilu",
          "type": "sacrifices",
          "context": "Enki has the god Aw-ilu slaughtered, and his flesh and blood used to create humans"
        },
        {
          "source": "Enki",
          "target": "Atrahasis",
          "type": "warns",
          "context": "Enki warns Atrahasis in a dream about the coming flood"
        },
        {
          "source": "Enlil",
          "target": "Humans",
          "type": "punishes",
          "context": "Enlil decides to extinguish mankind by a Great Flood"
        },
        {
          "source": "Enki",
          "target": "Nintu",
          "type": "proposes",
          "context": "Enki proposes measures to Nintu to limit human population after the flood"
        }
      ],
      "cross_cultural_patterns": [
        {
          "pattern": "Creation from clay and divine substance",
          "description": "Humans are fashioned from clay mixed with the blood of a sacrificed divine being",
          "appears_in": [
            "Genesis 2:7",
            "Enuma Elish",
            "Popol Vuh"
          ]
        },
        {
          "pattern": "Flood narrative",
          "description": "A great flood sent by the gods to destroy humanity, with one human survivor warned in advance",
          "appears_in": [
            "Gilgamesh XI",
            "Genesis 6-9",
            "Matsya Purana",
            "Deucalion"
          ]
        },
        {
          "pattern": "God warns one human",
          "description": "A deity warns a single human about an impending disaster",
          "appears_in": [
            "Noah",
            "Utnapishtim",
            "Manu",
            "Deucalion"
          ]
        },
        {
          "pattern": "Humans as servants of gods",
          "description": "Humans are created specifically to perform labor and serve the gods",
          "appears_in": [
            "Sumerian myths",
            "Enuma Elish"
          ]
        },
        {
          "pattern": "Divine blood in humanity",
          "description": "Humans contain a divine component, such as the blood of a god",
          "appears_in": [
            "Enuma Elish",
            "Norse (Ask and Embla)"
          ]
        }
      ],
      "key_events": [
        {
          "event": "Revolt of the Lower Gods",
          "participants": [
            "Igigi",
            "Enlil"
          ],
          "description": "The Igigi-gods, burdened with forced labor, revolt against Enlil and attack his dwelling",
          "significance": "This revolt leads to the creation of humans to replace the Igigi and perform the gods' labor"
        },
        {
          "event": "Creation of Humans",
          "participants": [
            "Ea",
            "Nintu",
            "Aw-ilu"
          ],
          "description": "Ea proposes that Nintu create a human being from clay mixed with the flesh and blood of the slaughtered god Aw-ilu",
          "significance": "Humans are created specifically to bear the 'yoke' and 'drudgery of the gods', replacing the Igigi laborers"
        },
        {
          "event": "The Great Flood",
          "participants": [
            "Enlil",
            "Atrahasis",
            "Enki",
            "Adad",
            "Anzu"
          ],
          "description": "Enlil decides to destroy humanity with a great flood, but Enki warns the flood survivor Atrahasis in a dream. Atrahasis builds an ark, and the flood is unleashed with Adad's storms and Anzu's talons rending the sky.",
          "significance": "The flood serves as divine punishment for human overpopulation and noise, but Atrahasis is saved to restart humanity"
        },
        {
          "event": "Post-Flood Regulations",
          "participants": [
            "Enki",
            "Nintu"
          ],
          "description": "Enki proposes to Nintu measures to limit human population after the flood, including death, infertility, and celibacy",
          "significance": "These regulations establish a new order for humanity, with population control measures imposed by the gods"
        }
      ],
      "source_file": "Atra-Hasis_Epic.txt"
    },
    {
      "source_text": "Book of Enoch (1 Enoch)",
      "culture": "Hebrew Apocalyptic",
      "entities": [
        {
          "name": "Semjaza",
          "type": "angel",
          "culture": "Hebrew",
          "description": "Leader of the 200 fallen Watchers who descended to Mount Hermon",
          "aliases": [
            "Semjazaz",
            "Shemyaza"
          ]
        },
        {
          "name": "Arakiba",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Rameel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Kokabiel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Tamiel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Ramiel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Danel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Ezequeel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Baraqijal",
          "type": "angel",
          "culture": "Hebrew",
          "aliases": []
        },
        {
          "name": "Asael",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Armaros",
          "type": "angel",
          "culture": "Hebrew",
          "aliases": []
        },
        {
          "name": "Batarel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Ananel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Zaqiel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Samsapeel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Satarel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Turel",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Jomjael",
          "type": "angel",
          "culture": "Hebrew"
        },
        {
          "name": "Sariel",
          "type": "angel",
          "culture": "Hebrew",
          "aliases": []
        },
        {
          "name": "Azazel",
          "type": "angel",
          "culture": "Hebrew",
          "description": "Taught humans forbidden knowledge"
        },
        {
          "name": "Armaros",
          "type": "angel",
          "culture": "Hebrew",
          "description": "Taught the resolving of enchantments"
        },
        {
          "name": "Baraqijal",
          "type": "angel",
          "culture": "Hebrew",
          "description": "Taught astrology"
        },
        {
          "name": "Kokabel",
          "type": "angel",
          "culture": "Hebrew",
          "description": "Taught the constellations"
        },
        {
          "name": "Ezeqeel",
          "type": "angel",
          "culture": "Hebrew",
          "description": "Taught the knowledge of the clouds"
        },
        {
          "name": "Araqiel",
          "type": "angel",
          "culture": "Hebrew",
          "description": "Taught the signs of the earth"
        },
        {
          "name": "Shamsiel",
          "type": "angel",
          "culture": "Hebrew",
          "description": "Taught the signs of the sun"
        },
        {
          "name": "Sariel",
          "type": "angel",
          "culture": "Hebrew",
          "description": "Taught the course of the moon"
        },
        {
          "name": "Michael",
          "type": "archangel",
          "culture": "Hebrew"
        },
        {
          "name": "Uriel",
          "type": "archangel",
          "culture": "Hebrew"
        },
        {
          "name": "Raphael",
          "type": "archangel",
          "culture": "Hebrew"
        },
        {
          "name": "Gabriel",
          "type": "archangel",
          "culture": "Hebrew"
        },
        {
          "name": "Noah",
          "type": "human",
          "culture": "Hebrew"
        },
        {
          "name": "Lamech",
          "type": "human",
          "culture": "Hebrew"
        },
        {
          "name": "Methuselah",
          "type": "human",
          "culture": "Hebrew"
        },
        {
          "name": "Mount Hermon",
          "type": "location",
          "culture": "Hebrew"
        },
        {
          "name": "Dudael",
          "type": "location",
          "culture": "Hebrew"
        },
        {
          "name": "Watchers",
          "type": "group",
          "culture": "Hebrew",
          "description": "200 angels who descended to Earth and took human wives"
        },
        {
          "name": "Lord of Spirits",
          "type": "divine",
          "culture": "Hebrew"
        },
        {
          "name": "Head of Days",
          "type": "divine",
          "culture": "Hebrew"
        },
        {
          "name": "Son of Man",
          "type": "divine",
          "culture": "Hebrew"
        },
        {
          "name": "Nephilim",
          "type": "group",
          "culture": "Hebrew",
          "description": "Giants born from the union of the Watchers and human women"
        }
      ],
      "relationships": [
        {
          "source": "Semjaza",
          "target": "Watchers",
          "type": "leads",
          "context": "Led 200 angels to descend to Earth"
        },
        {
          "source": "Azazel",
          "target": "humans",
          "type": "taught",
          "context": "Taught humans forbidden knowledge"
        },
        {
          "source": "Armaros",
          "target": "humans",
          "type": "taught",
          "context": "Taught the resolving of enchantments"
        },
        {
          "source": "Baraqijal",
          "target": "humans",
          "type": "taught",
          "context": "Taught astrology"
        },
        {
          "source": "Kokabel",
          "target": "humans",
          "type": "taught",
          "context": "Taught the constellations"
        },
        {
          "source": "Ezeqeel",
          "target": "humans",
          "type": "taught",
          "context": "Taught the knowledge of the clouds"
        },
        {
          "source": "Araqiel",
          "target": "humans",
          "type": "taught",
          "context": "Taught the signs of the earth"
        },
        {
          "source": "Shamsiel",
          "target": "humans",
          "type": "taught",
          "context": "Taught the signs of the sun"
        },
        {
          "source": "Sariel",
          "target": "humans",
          "type": "taught",
          "context": "Taught the course of the moon"
        },
        {
          "source": "Michael",
          "target": "humans",
          "type": "observed",
          "context": "Observed the lawlessness on Earth"
        },
        {
          "source": "Uriel",
          "target": "Noah",
          "type": "instructed",
          "context": "Instructed Noah about the coming flood"
        },
        {
          "source": "Raphael",
          "target": "Azazel",
          "type": "bound",
          "context": "Bound Azazel and cast him into Dudael"
        },
        {
          "source": "Watchers",
          "target": "humans",
          "type": "mated with",
          "context": "Took human wives and produced the Nephilim giants"
        }
      ],
      "key_events": [
        {
          "event": "Fall of the Watchers",
          "participants": [
            "Semjaza",
            "Watchers"
          ],
          "description": "200 angels descended to Mount Hermon and took human wives",
          "significance": "Origin of evil and the Nephilim giants"
        }
      ],
      "source_file": "Book_of_Enoch_Charles_1917.txt"
    },
    {
      "source_text": "Lebor Gabala Erenn (Book of Invasions)",
      "culture": "Irish/Celtic",
      "entities": [
        {
          "name": "Dagda",
          "type": "deity",
          "culture": "Irish",
          "description": "Chief of the Tuatha De Danann, father god, associated with Brug na Boinne (Newgrange)",
          "aliases": [
            "Eochu Ollathair",
            "In Dagda Mor",
            "the Great Good Father"
          ]
        },
        {
          "name": "Lugh",
          "type": "deity",
          "culture": "Irish",
          "description": "A hero-god of the Tuatha Dé Danann"
        },
        {
          "name": "Nuada",
          "type": "deity",
          "culture": "Irish",
          "description": "King of the Tuatha Dé Danann"
        },
        {
          "name": "Brigid",
          "type": "deity",
          "culture": "Irish",
          "description": "Daughter of the Dagda, goddess of poetry, healing, and smithcraft"
        },
        {
          "name": "Morrigan",
          "type": "deity",
          "culture": "Irish",
          "description": "Goddess of war, fate, and sovereignty"
        },
        {
          "name": "Dian Cecht",
          "type": "deity",
          "culture": "Irish",
          "description": "God of healing"
        },
        {
          "name": "Manannán",
          "type": "deity",
          "culture": "Irish",
          "description": "God of the sea"
        },
        {
          "name": "Ogma",
          "type": "deity",
          "culture": "Irish",
          "description": "God of eloquence and writing"
        },
        {
          "name": "Balor",
          "type": "deity",
          "culture": "Irish",
          "description": "Leader of the Fomorians"
        },
        {
          "name": "Bres",
          "type": "deity",
          "culture": "Irish",
          "description": "A king of the Tuatha Dé Danann"
        },
        {
          "name": "Tuatha Dé Danann",
          "type": "group",
          "culture": "Irish",
          "description": "The gods and goddesses of Irish mythology"
        },
        {
          "name": "Fomorians",
          "type": "group",
          "culture": "Irish",
          "description": "Mythical semi-divine beings who were enemies of the Tuatha Dé Danann"
        },
        {
          "name": "Brug na Boinne",
          "type": "location",
          "culture": "Irish",
          "description": "A sacred site associated with the Dagda and the Tuatha Dé Danann"
        }
      ],
      "relationships": [
        {
          "source": "Dagda",
          "target": "Brigid",
          "type": "parent_of",
          "context": "Brigid was the daughter of the Dagda"
        },
        {
          "source": "Dagda",
          "target": "Brug na Boinne",
          "type": "associated_with",
          "context": "The Brug na Boinne was persistently associated with the Dagda and his family"
        },
        {
          "source": "Dagda",
          "target": "Fomorians",
          "type": "fought_against",
          "context": "The Dagda fought against the Fomorians in the Second Battle of Mag Tuired"
        },
        {
          "source": "Lugh",
          "target": "Dagda",
          "type": "succeeded",
          "context": "Lugh succeeded the Dagda as king of the Tuatha Dé Danann"
        },
        {
          "source": "Nuada",
          "target": "Dian Cecht",
          "type": "cured_by",
          "context": "Dian Cecht cured Nuada's wounded arm"
        },
        {
          "source": "Morrigan",
          "target": "Dagda",
          "type": "associated_with",
          "context": "The Morrigan is associated with the Dagda in Irish mythology"
        },
        {
          "source": "Manannán",
          "target": "Tuatha Dé Danann",
          "type": "associated_with",
          "context": "Manannán is a figure associated with the Tuatha Dé Danann"
        },
        {
          "source": "Ogma",
          "target": "Delbaeth",
          "type": "parent_of",
          "context": "Delbaeth was the son of Ogma"
        },
        {
          "source": "Balor",
          "target": "Lugh",
          "type": "grandfather_of",
          "context": "Lugh was the grandson of Balor"
        },
        {
          "source": "Bres",
          "target": "Tuatha Dé Danann",
          "type": "king_of",
          "context": "Bres was a king of the Tuatha Dé Danann"
        }
      ],
      "key_events": [
        {
          "event": "Second Battle of Mag Tuired",
          "participants": [
            "Dagda",
            "Lugh",
            "Balor"
          ],
          "description": "The Tuatha Dé Danann defeat the Fomorians",
          "significance": "Establishes the Tuatha Dé Danann's rule in Ireland"
        },
        {
          "event": "Death of the Dagda",
          "participants": [
            "Dagda"
          ],
          "description": "The Dagda dies from a mortal wound inflicted by Cethlenn",
          "significance": "Marks the end of the Dagda's reign as king of the Tuatha Dé Danann"
        },
        {
          "event": "Healing of Nuada",
          "participants": [
            "Nuada",
            "Dian Cecht"
          ],
          "description": "Dian Cecht heals Nuada's wounded arm, restoring him as king",
          "significance": "Allows Nuada to continue ruling the Tuatha Dé Danann"
        },
        {
          "event": "Birth of Lugh",
          "participants": [
            "Lugh",
            "Balor"
          ],
          "description": "Lugh is born to Balor's daughter, a version of the Perseus myth",
          "significance": "Lugh's birth sets the stage for his eventual defeat of Balor"
        },
        {
          "event": "Reign of the Dagda",
          "participants": [
            "Dagda"
          ],
          "description": "The Dagda reigns as king of the Tuatha Dé Danann for 80 years",
          "significance": "Establishes the Dagda as a central figure in Irish mythology"
        }
      ],
      "source_file": "Lebor_Gabala_Index_Extracts.txt"
    },
    {
      "source_text": "Sumerian King List",
      "culture": "Sumerian",
      "entities": [
        {
          "name": "Alulim",
          "type": "deity",
          "culture": "Sumerian",
          "description": "First king of Eridu, ruled for 28,800 years",
          "aliases": []
        },
        {
          "name": "Alalgar",
          "type": "deity",
          "culture": "Sumerian",
          "description": "Second king of Eridu, ruled for 36,000 years",
          "aliases": []
        },
        {
          "name": "Enmen-lu-ana",
          "type": "deity",
          "culture": "Sumerian",
          "description": "King of Bad-tibira, ruled for 43,200 years",
          "aliases": []
        },
        {
          "name": "Enmen-gal-ana",
          "type": "deity",
          "culture": "Sumerian",
          "description": "King of Bad-tibira, ruled for 28,800 years",
          "aliases": []
        },
        {
          "name": "Dumuzi",
          "type": "deity",
          "culture": "Sumerian",
          "description": "The shepherd king of Bad-tibira, ruled for 36,000 years",
          "aliases": []
        },
        {
          "name": "En-sipad-zid-ana",
          "type": "deity",
          "culture": "Sumerian",
          "description": "King of Larak, ruled for 28,800 years",
          "aliases": []
        },
        {
          "name": "Enmen-dur-ana",
          "type": "deity",
          "culture": "Sumerian",
          "description": "King of Sippar, ruled for 21,000 years",
          "aliases": []
        },
        {
          "name": "Ubara-Tutu",
          "type": "deity",
          "culture": "Sumerian",
          "description": "King of Shuruppak, ruled for 18,600 years",
          "aliases": []
        },
        {
          "name": "Etana",
          "type": "deity",
          "culture": "Sumerian",
          "description": "Shepherd king of Kish who ascended to heaven, ruled for 1,500 years",
          "aliases": []
        },
        {
          "name": "Enmen-baragesi",
          "type": "deity",
          "culture": "Sumerian",
          "description": "King of Kish who destroyed Elam's weapons, ruled for 900 years",
          "aliases": []
        },
        {
          "name": "Agga",
          "type": "deity",
          "culture": "Sumerian",
          "description": "Son of Enmen-baragesi, king of Kish, ruled for 625 years",
          "aliases": []
        },
        {
          "name": "Mes-ki'ag-gaser",
          "type": "deity",
          "culture": "Sumerian",
          "description": "Lord and king of Uruk, son of the sun god Utu, ruled for 324 years",
          "aliases": []
        },
        {
          "name": "Enmerkar",
          "type": "deity",
          "culture": "Sumerian",
          "description": "King of Uruk, son of Mes-ki'ag-gaser, ruled for 420 years",
          "aliases": []
        },
        {
          "name": "Lugal-banda",
          "type": "deity",
          "culture": "Sumerian",
          "description": "The shepherd king of Uruk, ruled for 1,200 years",
          "aliases": []
        },
        {
          "name": "Gilgamesh",
          "type": "deity",
          "culture": "Sumerian",
          "description": "Lord of Kulaba, whose father was an invisible being, ruled for 126 years",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Alulim",
          "target": "Eridu",
          "type": "ruled",
          "context": "First king of Eridu"
        },
        {
          "source": "Alalgar",
          "target": "Eridu",
          "type": "ruled",
          "context": "Second king of Eridu"
        },
        {
          "source": "Enmen-lu-ana",
          "target": "Bad-tibira",
          "type": "ruled",
          "context": "King of Bad-tibira"
        },
        {
          "source": "Enmen-gal-ana",
          "target": "Bad-tibira",
          "type": "ruled",
          "context": "King of Bad-tibira"
        },
        {
          "source": "Dumuzi",
          "target": "Bad-tibira",
          "type": "ruled",
          "context": "The shepherd king of Bad-tibira"
        },
        {
          "source": "En-sipad-zid-ana",
          "target": "Larak",
          "type": "ruled",
          "context": "King of Larak"
        },
        {
          "source": "Enmen-dur-ana",
          "target": "Sippar",
          "type": "ruled",
          "context": "King of Sippar"
        },
        {
          "source": "Ubara-Tutu",
          "target": "Shuruppak",
          "type": "ruled",
          "context": "King of Shuruppak"
        },
        {
          "source": "Etana",
          "target": "Kish",
          "type": "ruled",
          "context": "Shepherd king of Kish who ascended to heaven"
        },
        {
          "source": "Enmen-baragesi",
          "target": "Kish",
          "type": "ruled",
          "context": "King of Kish who destroyed Elam's weapons"
        },
        {
          "source": "Agga",
          "target": "Kish",
          "type": "ruled",
          "context": "King of Kish, son of Enmen-baragesi"
        },
        {
          "source": "Mes-ki'ag-gaser",
          "target": "Uruk",
          "type": "ruled",
          "context": "Lord and king of Uruk, son of the sun god Utu"
        },
        {
          "source": "Enmerkar",
          "target": "Uruk",
          "type": "ruled",
          "context": "King of Uruk, son of Mes-ki'ag-gaser"
        },
        {
          "source": "Lugal-banda",
          "target": "Uruk",
          "type": "ruled",
          "context": "The shepherd king of Uruk"
        },
        {
          "source": "Gilgamesh",
          "target": "Kulaba",
          "type": "ruled",
          "context": "Lord of Kulaba, whose father was an invisible being"
        }
      ],
      "key_events": [
        {
          "event": "Kingship descended from heaven",
          "participants": [],
          "description": "The kingship was believed to have descended from heaven to various Sumerian cities",
          "significance": "Indicates the divine mandate and sacred nature of Sumerian kingship"
        },
        {
          "event": "The Flood",
          "participants": [],
          "description": "The Flood is described as a clear dividing line in Sumerian history, separating the pre-flood and post-flood eras",
          "significance": "The Flood is a major mythological event that reset civilization, similar to the biblical Flood"
        },
        {
          "event": "Etana ascended to heaven",
          "participants": [
            "Etana"
          ],
          "description": "Etana, the shepherd king of Kish, is described as ascending to heaven",
          "significance": "This motif of a mortal ascending to heaven is found in other ancient Near Eastern traditions, such as Enoch in the Bible"
        },
        {
          "event": "Gilgamesh's father was an invisible being",
          "participants": [
            "Gilgamesh"
          ],
          "description": "Gilgamesh, the lord of Kulaba, is described as having an invisible or phantom-like father",
          "significance": "This suggests a divine or supernatural parentage for Gilgamesh, similar to the concept of divine-human hybrids (Nephilim) in other ancient traditions"
        }
      ],
      "source_file": "Sumerian_King_List.txt"
    },
    {
      "source_text": "Popol Vuh Spence 1908",
      "culture": "Kiché (Maya)",
      "entities": [
        {
          "name": "Hurakan",
          "type": "deity",
          "culture": "Kiché (Maya)",
          "description": "The mighty wind, the Heart of Heaven, creator god",
          "aliases": []
        },
        {
          "name": "Gucumatz",
          "type": "deity",
          "culture": "Kiché (Maya)",
          "description": "The Feathered Serpent, creator god",
          "aliases": []
        },
        {
          "name": "Xpiyacoc",
          "type": "deity",
          "culture": "Kiché (Maya)",
          "description": "Father god, creator",
          "aliases": []
        },
        {
          "name": "Xmucane",
          "type": "deity",
          "culture": "Kiché (Maya)",
          "description": "Mother goddess, creator",
          "aliases": []
        },
        {
          "name": "Tepeu",
          "type": "deity",
          "culture": "Kiché (Maya)",
          "description": "King/creator god",
          "aliases": []
        },
        {
          "name": "Hun-Ahpu",
          "type": "hero",
          "culture": "Kiché (Maya)",
          "description": "The Master, Magician, hero twin",
          "aliases": []
        },
        {
          "name": "Xbalanque",
          "type": "hero",
          "culture": "Kiché (Maya)",
          "description": "Little Tiger, hero twin",
          "aliases": []
        },
        {
          "name": "Vukub-Cakix",
          "type": "titan",
          "culture": "Kiché (Maya)",
          "description": "Seven-fires, arrogant titan",
          "aliases": []
        },
        {
          "name": "Zipacna",
          "type": "titan",
          "culture": "Kiché (Maya)",
          "description": "Mountain-maker, titan son of Vukub-Cakix",
          "aliases": []
        },
        {
          "name": "Cabrakan",
          "type": "titan",
          "culture": "Kiché (Maya)",
          "description": "Earthquake, titan son of Vukub-Cakix",
          "aliases": []
        },
        {
          "name": "Hun-Came",
          "type": "underworld lord",
          "culture": "Kiché (Maya)",
          "description": "Ruler of the Underworld (Xibalba)",
          "aliases": []
        },
        {
          "name": "Vukub-Came",
          "type": "underworld lord",
          "culture": "Kiché (Maya)",
          "description": "Ruler of the Underworld (Xibalba)",
          "aliases": []
        },
        {
          "name": "Camazotz",
          "type": "underworld lord",
          "culture": "Kiché (Maya)",
          "description": "Ruler of Bats in the Underworld",
          "aliases": []
        },
        {
          "name": "Balam-Quitze",
          "type": "first man",
          "culture": "Kiché (Maya)",
          "description": "Tiger with the Sweet Smile, one of the first four men",
          "aliases": []
        },
        {
          "name": "Balam-Agab",
          "type": "first man",
          "culture": "Kiché (Maya)",
          "description": "Tiger of the Night, one of the first four men",
          "aliases": []
        },
        {
          "name": "Mahucutah",
          "type": "first man",
          "culture": "Kiché (Maya)",
          "description": "The Distinguished Name, one of the first four men",
          "aliases": []
        },
        {
          "name": "Iqi-Balam",
          "type": "first man",
          "culture": "Kiché (Maya)",
          "description": "Tiger of the Moon, one of the first four men",
          "aliases": []
        },
        {
          "name": "Tohil",
          "type": "tribal god",
          "culture": "Kiché (Maya)",
          "description": "The creator of fire, given to Balam-Quitze",
          "aliases": []
        },
        {
          "name": "Avilix",
          "type": "tribal god",
          "culture": "Kiché (Maya)",
          "description": "Given to Balam-Agab",
          "aliases": []
        },
        {
          "name": "Hacavitz",
          "type": "tribal god",
          "culture": "Kiché (Maya)",
          "description": "Given to Mahucutah",
          "aliases": []
        },
        {
          "name": "Xquiq",
          "type": "virgin",
          "culture": "Kiché (Maya)",
          "description": "Blood, virgin mother of the hero twins",
          "aliases": []
        },
        {
          "name": "Hunhun-Ahpu",
          "type": "father",
          "culture": "Kiché (Maya)",
          "description": "Father of the hero twins",
          "aliases": []
        },
        {
          "name": "400 youths",
          "type": "group",
          "culture": "Kiché (Maya)",
          "description": "Slain by Zipacna, became the stars",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Hurakan",
          "target": "Gucumatz",
          "type": "creator",
          "context": "Deliberated and created the world"
        },
        {
          "source": "Hurakan",
          "target": "Xpiyacoc",
          "type": "creator",
          "context": "Deliberated and created the world"
        },
        {
          "source": "Hurakan",
          "target": "Xmucane",
          "type": "creator",
          "context": "Deliberated and created the world"
        },
        {
          "source": "Hurakan",
          "target": "Tepeu",
          "type": "creator",
          "context": "Deliberated and created the world"
        },
        {
          "source": "Hun-Ahpu",
          "target": "Xbalanque",
          "type": "twin",
          "context": "Hero twins who defeated the titans"
        },
        {
          "source": "Vukub-Cakix",
          "target": "Zipacna",
          "type": "parent",
          "context": "Vukub-Cakix was the father of Zipacna and Cabrakan"
        },
        {
          "source": "Vukub-Cakix",
          "target": "Cabrakan",
          "type": "parent",
          "context": "Vukub-Cakix was the father of Zipacna and Cabrakan"
        },
        {
          "source": "Hun-Came",
          "target": "Vukub-Came",
          "type": "ruler",
          "context": "Co-rulers of the Underworld (Xibalba)"
        },
        {
          "source": "Balam-Quitze",
          "target": "Tohil",
          "type": "patron",
          "context": "Tohil was the tribal god given to Balam-Quitze"
        },
        {
          "source": "Balam-Agab",
          "target": "Avilix",
          "type": "patron",
          "context": "Avilix was the tribal god given to Balam-Agab"
        },
        {
          "source": "Mahucutah",
          "target": "Hacavitz",
          "type": "patron",
          "context": "Hacavitz was the tribal god given to Mahucutah"
        },
        {
          "source": "Xquiq",
          "target": "Hunhun-Ahpu",
          "type": "mother",
          "context": "Xquiq was impregnated by Hunhun-Ahpu and bore the hero twins"
        },
        {
          "source": "400 youths",
          "target": "stars",
          "type": "transformation",
          "context": "The 400 youths slain by Zipacna became the stars in the sky"
        }
      ],
      "key_events": [
        {
          "event": "Creation of the world",
          "participants": [
            "Hurakan",
            "Gucumatz",
            "Xpiyacoc",
            "Xmucane",
            "Tepeu"
          ],
          "description": "The creator gods deliberated and brought forth the earth and animals, but not yet man.",
          "significance": "Establishes the Kiché creation myth and the pantheon of creator deities."
        },
        {
          "event": "Destruction of the wooden men",
          "participants": [
            "Hurakan",
            "wooden men"
          ],
          "description": "The wooden men created by the gods displeased them, so Hurakan caused a great flood to destroy them.",
          "significance": "Demonstrates the theme of failed creations being destroyed, a common motif in creation myths."
        },
        {
          "event": "Defeat of the titans",
          "participants": [
            "Hun-Ahpu",
            "Xbalanque",
            "Vukub-Cakix",
            "Zipacna",
            "Cabrakan"
          ],
          "description": "The hero twins Hun-Ahpu and Xbalanque defeated the arrogant titans Vukub-Cakix, Zipacna, and Cabrakan.",
          "significance": "Establishes the hero twins as the champions who overcome the destructive forces of the titans."
        },
        {
          "event": "Descent to the Underworld",
          "participants": [
            "Hun-Ahpu",
            "Xbalanque",
            "Hun-Came",
            "Vukub-Came",
            "Camazotz"
          ],
          "description": "The hero twins underwent ordeals in the Underworld (Xibalba) and defeated the Underworld lords.",
          "significance": "Demonstrates the theme of the hero twins' journey to the Underworld and their triumph over the forces of death, a common motif in mythology."
        },
        {
          "event": "Creation of the first men",
          "participants": [
            "Creator and Former",
            "Balam-Quitze",
            "Balam-Agab",
            "Mahucutah",
            "Iqi-Balam"
          ],
          "description": "The Creator and Former made the first four perfect men from maize, and then created their wives.",
          "significance": "Establishes the Kiché origin of humanity, with the first men created from maize, a common theme in Mesoamerican mythology."
        }
      ],
      "source_file": "Popol_Vuh_Spence_1908.txt"
    },
    {
      "source_text": "Descent of Inanna Kramer",
      "culture": "Sumerian",
      "entities": [
        {
          "name": "Inanna",
          "type": "deity",
          "culture": "Sumerian",
          "description": "Queen of Heaven",
          "aliases": []
        },
        {
          "name": "Ereshkigal",
          "type": "deity",
          "culture": "Sumerian",
          "description": "Queen of the Underworld",
          "aliases": []
        },
        {
          "name": "Enki",
          "type": "deity",
          "culture": "Sumerian",
          "description": "God of Wisdom",
          "aliases": []
        },
        {
          "name": "Enlil",
          "type": "deity",
          "culture": "Sumerian",
          "description": "Refused to help Inanna",
          "aliases": []
        },
        {
          "name": "Nanna",
          "type": "deity",
          "culture": "Sumerian",
          "description": "Refused to help Inanna",
          "aliases": []
        },
        {
          "name": "Utu",
          "type": "deity",
          "culture": "Sumerian",
          "description": "God of Justice, helped Dumuzi",
          "aliases": []
        },
        {
          "name": "Ninshubur",
          "type": "servant",
          "culture": "Sumerian",
          "description": "Faithful servant/sukkal of Inanna",
          "aliases": []
        },
        {
          "name": "Neti",
          "type": "servant",
          "culture": "Sumerian",
          "description": "Gatekeeper of the Underworld",
          "aliases": []
        },
        {
          "name": "Shara",
          "type": "offspring",
          "culture": "Sumerian",
          "description": "Son of Inanna",
          "aliases": []
        },
        {
          "name": "Lulal",
          "type": "offspring",
          "culture": "Sumerian",
          "description": "Son of Inanna",
          "aliases": []
        },
        {
          "name": "Dumuzi",
          "type": "husband",
          "culture": "Sumerian",
          "description": "Shepherd, given as substitute for Inanna",
          "aliases": []
        },
        {
          "name": "Kurgarra",
          "type": "creature",
          "culture": "Sumerian",
          "description": "Neither male nor female, created by Enki from dirt",
          "aliases": []
        },
        {
          "name": "Galatur",
          "type": "creature",
          "culture": "Sumerian",
          "description": "Neither male nor female, created by Enki from dirt",
          "aliases": []
        },
        {
          "name": "Galla",
          "type": "demon",
          "culture": "Sumerian",
          "description": "Demons of the Underworld, know no food, drink, love",
          "aliases": []
        },
        {
          "name": "Annuna",
          "type": "group",
          "culture": "Sumerian",
          "description": "Judges of the Underworld",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Inanna",
          "target": "Ereshkigal",
          "type": "sibling",
          "context": "Inanna visits her sister Ereshkigal in the Underworld"
        },
        {
          "source": "Inanna",
          "target": "Ninshubur",
          "type": "servant",
          "context": "Ninshubur is the faithful servant/sukkal of Inanna"
        },
        {
          "source": "Inanna",
          "target": "Shara",
          "type": "parent",
          "context": "Shara is the son of Inanna"
        },
        {
          "source": "Inanna",
          "target": "Lulal",
          "type": "parent",
          "context": "Lulal is the son of Inanna"
        },
        {
          "source": "Inanna",
          "target": "Dumuzi",
          "type": "spouse",
          "context": "Dumuzi is the husband of Inanna"
        },
        {
          "source": "Enki",
          "target": "Kurgarra",
          "type": "creator",
          "context": "Enki fashioned the Kurgarra from dirt"
        },
        {
          "source": "Enki",
          "target": "Galatur",
          "type": "creator",
          "context": "Enki fashioned the Galatur from dirt"
        },
        {
          "source": "Enlil",
          "target": "Inanna",
          "type": "refusal",
          "context": "Enlil refused to help Inanna"
        },
        {
          "source": "Nanna",
          "target": "Inanna",
          "type": "refusal",
          "context": "Nanna refused to help Inanna"
        },
        {
          "source": "Utu",
          "target": "Dumuzi",
          "type": "help",
          "context": "Utu helped Dumuzi"
        },
        {
          "source": "Galla",
          "target": "Inanna",
          "type": "pursuit",
          "context": "The Galla demons pursued Inanna after she left the Underworld"
        }
      ],
      "key_events": [
        {
          "event": "Inanna's Descent to the Underworld",
          "participants": [
            "Inanna",
            "Ereshkigal"
          ],
          "description": "Inanna, Queen of Heaven, descends to the Underworld (kur) to visit her sister Ereshkigal. She passes through 7 gates, losing one of her 7 divine garments/objects (me) at each gate. Stripped naked, she is killed by Ereshkigal and hung on a hook.",
          "significance": "This descent and stripping of power/identity is a key theme in the myth, paralleling similar motifs in other cultures."
        },
        {
          "event": "Inanna's Resurrection",
          "participants": [
            "Inanna",
            "Ninshubur",
            "Enki",
            "Kurgarra",
            "Galatur"
          ],
          "description": "After 3 days, Inanna's servant Ninshubur seeks help from the gods. Enki creates two beings, the Kurgarra and Galatur, from dirt. They retrieve Inanna's corpse and sprinkle her with the food and water of life, reviving her.",
          "significance": "Inanna's death and resurrection is a key motif, paralleling similar dying and reviving deity figures in other mythologies."
        },
        {
          "event": "Substitution of Dumuzi",
          "participants": [
            "Inanna",
            "Dumuzi"
          ],
          "description": "Inanna must provide a substitute to take her place in the Underworld. She chooses her husband Dumuzi, the shepherd, who did not mourn for her.",
          "significance": "The requirement of a substitute is a common theme in mythology, seen in the scapegoat ritual and the Christian concept of Christ as a substitute for humanity."
        }
      ],
      "source_file": "Descent_of_Inanna_Kramer.txt"
    },
    {
      "source_text": "Matsya Purana Flood",
      "culture": "Hindu/Indian",
      "entities": [
        {
          "name": "Vishnu",
          "type": "deity",
          "culture": "Hindu/Indian",
          "description": "Supreme preserver god, takes Matsya avatar",
          "aliases": []
        },
        {
          "name": "Brahma",
          "type": "deity",
          "culture": "Hindu/Indian",
          "description": "Creator, whose Vedas were stolen",
          "aliases": []
        },
        {
          "name": "Matsya",
          "type": "avatar",
          "culture": "Hindu/Indian",
          "description": "The divine fish - Vishnu's first incarnation",
          "aliases": []
        },
        {
          "name": "Manu/Satyavrata/Vaivasvata",
          "type": "human",
          "culture": "Hindu/Indian",
          "description": "7th Manu, flood survivor, progenitor of humanity",
          "aliases": []
        },
        {
          "name": "Ila/Shraddha",
          "type": "human",
          "culture": "Hindu/Indian",
          "description": "First woman post-flood",
          "aliases": []
        },
        {
          "name": "Saptarishi",
          "type": "sage",
          "culture": "Hindu/Indian",
          "description": "Seven Great Sages who survive on the ship",
          "aliases": []
        },
        {
          "name": "Hayagriva",
          "type": "demon",
          "culture": "Hindu/Indian",
          "description": "Horse-headed demon who stole the Vedas",
          "aliases": []
        },
        {
          "name": "Vasuki",
          "type": "creature",
          "culture": "Hindu/Indian",
          "description": "Cosmic serpent, used as rope to tie ship to fish's horn",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Vishnu",
          "target": "Matsya",
          "type": "avatar",
          "context": "Vishnu takes the Matsya avatar"
        },
        {
          "source": "Vishnu",
          "target": "Manu/Satyavrata/Vaivasvata",
          "type": "warns",
          "context": "Vishnu warns Manu about the impending flood"
        },
        {
          "source": "Manu/Satyavrata/Vaivasvata",
          "target": "Saptarishi",
          "type": "collects",
          "context": "Manu collects the Seven Great Sages to board the ship"
        },
        {
          "source": "Hayagriva",
          "target": "Vedas",
          "type": "steals",
          "context": "Hayagriva steals the Vedas and hides them in the cosmic ocean"
        },
        {
          "source": "Vishnu",
          "target": "Vedas",
          "type": "recovers",
          "context": "Vishnu recovers the Vedas from the cosmic ocean"
        },
        {
          "source": "Manu/Satyavrata/Vaivasvata",
          "target": "Ila/Shraddha",
          "type": "progenitors",
          "context": "Manu and Ila/Shraddha become the progenitors of all humanity"
        },
        {
          "source": "Matsya",
          "target": "Ship",
          "type": "guides",
          "context": "Vishnu-as-Matsya guides the ship through the cosmic waters"
        },
        {
          "source": "Vasuki",
          "target": "Ship",
          "type": "ties",
          "context": "Vasuki is used as a rope to tie the ship to Matsya's horn"
        }
      ],
      "key_events": [
        {
          "event": "Vishnu warns Manu about the impending flood",
          "participants": [
            "Vishnu",
            "Manu/Satyavrata/Vaivasvata"
          ],
          "description": "Vishnu appears to Manu as a small fish and warns him about the upcoming great deluge, instructing him to build a ship and gather the necessary supplies.",
          "significance": "This event sets the stage for the flood narrative and Manu's role as the survivor and progenitor of humanity."
        },
        {
          "event": "Manu collects the Saptarishi, seeds, and animals onto the ship",
          "participants": [
            "Manu/Satyavrata/Vaivasvata",
            "Saptarishi"
          ],
          "description": "Manu gathers the Seven Great Sages, seeds of all plants, and pairs of all animals onto the ship as instructed by Vishnu.",
          "significance": "This ensures the preservation of life on Earth during the flood, allowing for the recreation of the world after the waters recede."
        },
        {
          "event": "The great flood (pralaya) submerges the three worlds",
          "participants": [
            "Manu/Satyavrata/Vaivasvata",
            "Saptarishi"
          ],
          "description": "The cosmic flood, or pralaya, submerges the three worlds, destroying all life except for those on the ship guided by Matsya.",
          "significance": "This event represents the destruction of the old world and the preparation for the recreation of life on Earth."
        },
        {
          "event": "Vishnu recovers the stolen Vedas from the demon Hayagriva",
          "participants": [
            "Vishnu",
            "Hayagriva"
          ],
          "description": "While the flood is in progress, Vishnu descends into the cosmic ocean and recovers the Vedas, which had been stolen by the demon Hayagriva.",
          "significance": "The preservation of the sacred knowledge of the Vedas ensures the continuity of Hindu tradition and culture after the flood."
        },
        {
          "event": "Manu and Ila/Shraddha become the progenitors of humanity",
          "participants": [
            "Manu/Satyavrata/Vaivasvata",
            "Ila/Shraddha"
          ],
          "description": "After the flood, Manu performs a sacrifice, and from the sacrifice a woman named Ila/Shraddha appears. Together, Manu and Ila/Shraddha become the progenitors of all humanity.",
          "significance": "This event represents the recreation of life on Earth and the continuation of the human lineage after the great flood."
        }
      ],
      "source_file": "Matsya_Purana_Flood.txt"
    },
    {
      "source_text": "Prose Edda Gylfaginning",
      "culture": "Norse/Scandinavian",
      "entities": [
        {
          "name": "Odin",
          "type": "deity",
          "culture": "Norse/Scandinavian",
          "description": "Allfather, wisdom, war, death, poetry, runes — hung on Yggdrasil 9 days to gain knowledge of runes",
          "aliases": []
        },
        {
          "name": "Thor",
          "type": "deity",
          "culture": "Norse/Scandinavian",
          "description": "thunder, strength, protector of Midgard",
          "aliases": []
        },
        {
          "name": "Loki",
          "type": "deity",
          "culture": "Norse/Scandinavian",
          "description": "trickster, shape-shifter, father of monsters — Fenrir wolf, Jormungandr serpent, Hel",
          "aliases": []
        },
        {
          "name": "Freya",
          "type": "deity",
          "culture": "Norse/Scandinavian",
          "description": "love, fertility, war, magic/seidr",
          "aliases": []
        },
        {
          "name": "Baldur",
          "type": "deity",
          "culture": "Norse/Scandinavian",
          "description": "beauty, light, beloved of all — killed by Loki's trickery",
          "aliases": []
        },
        {
          "name": "Tyr",
          "type": "deity",
          "culture": "Norse/Scandinavian",
          "description": "law, justice, sacrificed hand to bind Fenrir",
          "aliases": []
        },
        {
          "name": "Heimdall",
          "type": "deity",
          "culture": "Norse/Scandinavian",
          "description": "watchman of gods, blows Gjallarhorn at Ragnarok",
          "aliases": []
        },
        {
          "name": "Ymir",
          "type": "giant",
          "culture": "Norse/Scandinavian",
          "description": "first being, killed to make the world",
          "aliases": []
        },
        {
          "name": "Surtr",
          "type": "giant",
          "culture": "Norse/Scandinavian",
          "description": "fire giant who destroys the world at Ragnarok",
          "aliases": []
        },
        {
          "name": "Thrym",
          "type": "giant",
          "culture": "Norse/Scandinavian",
          "description": "stole Thor's hammer",
          "aliases": []
        },
        {
          "name": "Fenrir",
          "type": "monster",
          "culture": "Norse/Scandinavian",
          "description": "great wolf that breaks free at Ragnarok",
          "aliases": []
        },
        {
          "name": "Jormungandr",
          "type": "monster",
          "culture": "Norse/Scandinavian",
          "description": "world serpent that rises from the ocean, flooding the land",
          "aliases": []
        },
        {
          "name": "Hel",
          "type": "monster",
          "culture": "Norse/Scandinavian",
          "description": "death goddess",
          "aliases": []
        },
        {
          "name": "Ask",
          "type": "human",
          "culture": "Norse/Scandinavian",
          "description": "first man, created from an ash tree",
          "aliases": []
        },
        {
          "name": "Embla",
          "type": "human",
          "culture": "Norse/Scandinavian",
          "description": "first woman, created from an elm tree",
          "aliases": []
        },
        {
          "name": "Lif",
          "type": "human",
          "culture": "Norse/Scandinavian",
          "description": "one of the two humans who survive Ragnarok, hidden in Yggdrasil",
          "aliases": []
        },
        {
          "name": "Lifthrasir",
          "type": "human",
          "culture": "Norse/Scandinavian",
          "description": "one of the two humans who survive Ragnarok, hidden in Yggdrasil",
          "aliases": []
        },
        {
          "name": "Audhumla",
          "type": "cosmic",
          "culture": "Norse/Scandinavian",
          "description": "primeval cow that nourished Ymir",
          "aliases": []
        },
        {
          "name": "Buri",
          "type": "cosmic",
          "culture": "Norse/Scandinavian",
          "description": "first of the gods, revealed by Audhumla",
          "aliases": []
        },
        {
          "name": "Yggdrasil",
          "type": "cosmic",
          "culture": "Norse/Scandinavian",
          "description": "the great ash tree that structures the cosmos",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Odin",
          "target": "Vili",
          "type": "brother",
          "context": "Odin, Vili, and Ve killed Ymir and created the world"
        },
        {
          "source": "Odin",
          "target": "Ve",
          "type": "brother",
          "context": "Odin, Vili, and Ve killed Ymir and created the world"
        },
        {
          "source": "Odin",
          "target": "Ask",
          "type": "creator",
          "context": "Odin, Vili, and Ve created the first humans, Ask and Embla"
        },
        {
          "source": "Odin",
          "target": "Embla",
          "type": "creator",
          "context": "Odin, Vili, and Ve created the first humans, Ask and Embla"
        },
        {
          "source": "Loki",
          "target": "Fenrir",
          "type": "father",
          "context": "Loki is the father of the monsters Fenrir, Jormungandr, and Hel"
        },
        {
          "source": "Loki",
          "target": "Jormungandr",
          "type": "father",
          "context": "Loki is the father of the monsters Fenrir, Jormungandr, and Hel"
        },
        {
          "source": "Loki",
          "target": "Hel",
          "type": "father",
          "context": "Loki is the father of the monsters Fenrir, Jormungandr, and Hel"
        },
        {
          "source": "Ymir",
          "target": "world",
          "type": "creator",
          "context": "Ymir's body was used to create the world"
        },
        {
          "source": "Audhumla",
          "target": "Ymir",
          "type": "nourisher",
          "context": "Audhumla, the primeval cow, nourished Ymir"
        },
        {
          "source": "Audhumla",
          "target": "Buri",
          "type": "revealer",
          "context": "Audhumla revealed Buri, the first of the gods"
        }
      ],
      "key_events": [
        {
          "event": "Creation of the world",
          "participants": [
            "Odin",
            "Vili",
            "Ve"
          ],
          "description": "Odin, Vili, and Ve killed Ymir and used his body to create the world: his flesh = earth, his blood = seas, his bones = mountains, his skull = sky, his brains = clouds, his eyebrows = Midgard",
          "significance": "The creation of the world from the body of the primordial being Ymir is a common motif in mythology, seen in traditions like Enuma Elish and Chinese mythology."
        },
        {
          "event": "Creation of the first humans",
          "participants": [
            "Odin",
            "Vili",
            "Ve"
          ],
          "description": "Odin, Vili, and Ve created the first humans, Ask and Embla, from an ash tree and an elm tree. Odin gave them breath/spirit, Vili gave them understanding/movement, and Ve gave them form/speech/senses.",
          "significance": "The creation of the first humans from natural materials is a recurring theme in mythology, seen in traditions like the creation of Adam from dust in the Bible and the creation of humans from clay in Mesopotamian myths."
        },
        {
          "event": "Ragnarok",
          "participants": [
            "Odin",
            "Thor",
            "Loki",
            "Heimdall",
            "Fenrir",
            "Jormungandr",
            "Surtr"
          ],
          "description": "Fimbulwinter, the great wolf Fenrir breaking free, Jormungandr rising from the ocean, Loki leading the armies of the dead against Asgard, and the fire giant Surtr advancing with a flaming sword. Odin is swallowed by Fenrir, Thor kills Jormungandr but dies from its venom, Heimdall and Loki kill each other, and Surtr engulfs everything in fire, causing the earth to sink into the sea.",
          "significance": "Ragnarok, the apocalyptic destruction of the world, is a central event in Norse mythology that parallels the Great Flood and other catastrophic events in other mythological traditions. The subsequent renewal of the world is also a common theme."
        }
      ],
      "source_file": "Prose_Edda_Gylfaginning.txt"
    },
    {
      "source_text": "Genesis 1-11",
      "culture": "Hebrew/Israelite",
      "entities": [
        {
          "name": "God",
          "type": "divine",
          "culture": "Hebrew/Israelite",
          "description": "Creator of heaven and earth",
          "aliases": [
            "Elohim",
            "Yahweh/LORD God"
          ]
        },
        {
          "name": "Adam",
          "type": "human",
          "culture": "Hebrew/Israelite",
          "description": "First man created from dust",
          "aliases": []
        },
        {
          "name": "Eve",
          "type": "human",
          "culture": "Hebrew/Israelite",
          "description": "First woman, created from Adam's rib",
          "aliases": []
        },
        {
          "name": "Cain",
          "type": "human",
          "culture": "Hebrew/Israelite",
          "description": "Son of Adam and Eve, murdered Abel",
          "aliases": []
        },
        {
          "name": "Abel",
          "type": "human",
          "culture": "Hebrew/Israelite",
          "description": "Son of Adam and Eve, killed by Cain",
          "aliases": []
        },
        {
          "name": "Noah",
          "type": "human",
          "culture": "Hebrew/Israelite",
          "description": "Survivor of the Flood, built the Ark",
          "aliases": []
        },
        {
          "name": "Shem",
          "type": "human",
          "culture": "Hebrew/Israelite",
          "description": "One of Noah's sons, ancestor of Semitic peoples",
          "aliases": []
        },
        {
          "name": "Ham",
          "type": "human",
          "culture": "Hebrew/Israelite",
          "description": "One of Noah's sons, ancestor of Hamitic peoples",
          "aliases": []
        },
        {
          "name": "Japheth",
          "type": "human",
          "culture": "Hebrew/Israelite",
          "description": "One of Noah's sons, ancestor of Japhetic peoples",
          "aliases": []
        },
        {
          "name": "Nimrod",
          "type": "human",
          "culture": "Hebrew/Israelite",
          "description": "Mighty hunter and builder of cities",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "God",
          "target": "Adam",
          "type": "created",
          "context": "Formed from dust of the ground"
        },
        {
          "source": "God",
          "target": "Eve",
          "type": "created",
          "context": "Formed from Adam's rib"
        },
        {
          "source": "Cain",
          "target": "Abel",
          "type": "killed",
          "context": "Cain murdered Abel"
        },
        {
          "source": "God",
          "target": "Noah",
          "type": "instructed",
          "context": "Told Noah to build the Ark"
        },
        {
          "source": "God",
          "target": "Humanity",
          "type": "destroyed",
          "context": "Destroyed humanity with the Flood"
        },
        {
          "source": "Noah",
          "target": "Animals",
          "type": "saved",
          "context": "Noah saved pairs of animals in the Ark"
        },
        {
          "source": "God",
          "target": "Noah",
          "type": "made covenant",
          "context": "God made a covenant with Noah after the Flood"
        },
        {
          "source": "Sons of God",
          "target": "Daughters of men",
          "type": "mated",
          "context": "Produced the Nephilim"
        },
        {
          "source": "Tubal-cain",
          "target": "Humans",
          "type": "taught",
          "context": "Taught metalworking to humans"
        },
        {
          "source": "Nimrod",
          "target": "Cities",
          "type": "built",
          "context": "Built cities like Babel, Erech, Accad, and Nineveh"
        }
      ],
      "key_events": [
        {
          "event": "The Creation",
          "participants": [
            "God"
          ],
          "description": "God creates heaven, earth, and all life in 6 days",
          "significance": "Establishes God as creator of the universe"
        },
        {
          "event": "The Flood",
          "participants": [
            "God",
            "Noah"
          ],
          "description": "God destroys earth with flood, Noah survives in ark",
          "significance": "Divine reset of humanity"
        },
        {
          "event": "The Tower of Babel",
          "participants": [
            "Humans",
            "God"
          ],
          "description": "Humans build a tower to reach heaven, God confuses their language",
          "significance": "Limits human ambition and technological advancement"
        },
        {
          "event": "The Nephilim",
          "participants": [
            "Sons of God",
            "Daughters of men"
          ],
          "description": "Supernatural beings mate with humans, producing giants",
          "significance": "Demonstrates divine/human interbreeding"
        },
        {
          "event": "The Expulsion from Eden",
          "participants": [
            "Adam",
            "Eve",
            "God"
          ],
          "description": "Adam and Eve are expelled from the Garden of Eden",
          "significance": "Humans lose access to the divine realm"
        }
      ],
      "source_file": "Genesis_1-11_Primeval_History.txt"
    },
    {
      "source_text": "Book of Giants (Dead Sea Scrolls)",
      "culture": "Jewish Aramaic",
      "entities": [
        {
          "name": "Ohya",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "Prominent giant, son of Semjaza"
        },
        {
          "name": "Hahya",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "Giant, son of Semjaza, brother of Ohya"
        },
        {
          "name": "Mahaway",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "Messenger giant who flew to Enoch"
        },
        {
          "name": "Gilgamesh",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "Appeared as one of the giants"
        },
        {
          "name": "Hobabish",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "One of the named giants"
        },
        {
          "name": "Baraq'el",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "Named after the Watcher Baraqiel"
        },
        {
          "name": "Semjaza",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "Leader of the Watchers"
        },
        {
          "name": "Azazel",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "One of the Watchers"
        },
        {
          "name": "Baraqiel",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "One of the Watchers"
        },
        {
          "name": "Enoch",
          "type": "human",
          "culture": "Jewish Aramaic",
          "description": "Scribe, interpreter of dreams"
        }
      ],
      "relationships": [
        {
          "source": "Semjaza",
          "target": "Ohya",
          "type": "father",
          "context": "Ohya was the son of Semjaza"
        },
        {
          "source": "Semjaza",
          "target": "Hahya",
          "type": "father",
          "context": "Hahya was the son of Semjaza"
        },
        {
          "source": "Ohya",
          "target": "Hahya",
          "type": "sibling",
          "context": "Ohya and Hahya were brothers"
        },
        {
          "source": "Mahaway",
          "target": "Enoch",
          "type": "messenger",
          "context": "Mahaway flew to Enoch to interpret dreams"
        },
        {
          "source": "Baraq'el",
          "target": "Baraqiel",
          "type": "named after",
          "context": "Baraq'el was named after the Watcher Baraqiel"
        },
        {
          "source": "Gilgamesh",
          "target": "Nephilim",
          "type": "member",
          "context": "Gilgamesh appeared as one of the giants"
        },
        {
          "source": "Watchers",
          "target": "Giants",
          "type": "fathers",
          "context": "The Watchers were the fathers of the Giants"
        },
        {
          "source": "Giants",
          "target": "Monsters",
          "type": "offspring",
          "context": "The Giants produced animal-human hybrid Monsters"
        },
        {
          "source": "Ohya",
          "target": "Flood",
          "type": "dreamed",
          "context": "Ohya had a dream about the coming Flood"
        },
        {
          "source": "Hahya",
          "target": "Flood",
          "type": "dreamed",
          "context": "Hahya had a dream about the coming Flood"
        }
      ],
      "key_events": [
        {
          "event": "The Flood",
          "participants": [
            "God",
            "Noah"
          ],
          "description": "God destroys earth with flood, Noah survives",
          "significance": "Divine reset of humanity"
        },
        {
          "event": "Giants' Dreams of Flood",
          "participants": [
            "Ohya",
            "Hahya"
          ],
          "description": "Giants receive visions of the coming Flood",
          "significance": "Foreshadows the Flood's destruction"
        },
        {
          "event": "Mahaway's Flight to Enoch",
          "participants": [
            "Mahaway",
            "Enoch"
          ],
          "description": "Messenger giant flies to Enoch for dream interpretation",
          "significance": "Giants seek Enoch's divine knowledge"
        },
        {
          "event": "Enoch Confirms Destruction",
          "participants": [
            "Enoch",
            "Giants"
          ],
          "description": "Enoch tells giants their judgment is sealed",
          "significance": "Giants cannot prevent their doom"
        },
        {
          "event": "Giants' Corruption and Violence",
          "participants": [
            "Giants"
          ],
          "description": "Giants fill earth with violence and abominations",
          "significance": "Triggers divine judgment"
        }
      ],
      "source_file": "Book_of_Giants_DSS.txt"
    },
    {
      "source_text": "Hesiod's Theogony",
      "culture": "Greek",
      "entities": [
        {
          "name": "Zeus",
          "type": "deity",
          "culture": "Greek",
          "description": "King of the Olympian gods",
          "aliases": []
        },
        {
          "name": "Kronos",
          "type": "deity",
          "culture": "Greek",
          "description": "Titan who ruled before Zeus"
        },
        {
          "name": "Gaia",
          "type": "deity",
          "culture": "Greek",
          "description": "Primordial goddess of the Earth"
        },
        {
          "name": "Ouranos",
          "type": "deity",
          "culture": "Greek",
          "description": "Primordial god of the Sky"
        },
        {
          "name": "Titans",
          "type": "group",
          "culture": "Greek",
          "description": "Twelve children of Gaia and Ouranos"
        },
        {
          "name": "Cyclopes",
          "type": "group",
          "culture": "Greek",
          "description": "One-eyed giants"
        },
        {
          "name": "Hecatoncheires",
          "type": "group",
          "culture": "Greek",
          "description": "Hundred-handed giants"
        },
        {
          "name": "Prometheus",
          "type": "deity",
          "culture": "Greek",
          "description": "Titan who gave fire to humans"
        },
        {
          "name": "Pandora",
          "type": "character",
          "culture": "Greek",
          "description": "First woman, created by Zeus"
        },
        {
          "name": "Deucalion",
          "type": "character",
          "culture": "Greek",
          "description": "Survivor of the great flood"
        },
        {
          "name": "Pyrrha",
          "type": "character",
          "culture": "Greek",
          "description": "Wife of Deucalion"
        },
        {
          "name": "Giants",
          "type": "group",
          "culture": "Greek",
          "description": "Born from Ouranos' blood"
        },
        {
          "name": "Heracles",
          "type": "deity",
          "culture": "Greek",
          "description": "Demigod hero"
        },
        {
          "name": "Aphrodite",
          "type": "deity",
          "culture": "Greek",
          "description": "Goddess of love and beauty"
        },
        {
          "name": "Athena",
          "type": "deity",
          "culture": "Greek",
          "description": "Goddess of wisdom and war"
        }
      ],
      "relationships": [
        {
          "source": "Zeus",
          "target": "Kronos",
          "type": "overthrew",
          "context": "Led Titanomachy against his father"
        },
        {
          "source": "Kronos",
          "target": "Ouranos",
          "type": "overthrew",
          "context": "Castrated Ouranos"
        },
        {
          "source": "Gaia",
          "target": "Ouranos",
          "type": "produced",
          "context": "Together they produced the Titans"
        },
        {
          "source": "Prometheus",
          "target": "Humans",
          "type": "created",
          "context": "Fashioned humans from clay"
        },
        {
          "source": "Prometheus",
          "target": "Fire",
          "type": "stole",
          "context": "Gave fire to humanity"
        },
        {
          "source": "Zeus",
          "target": "Prometheus",
          "type": "punished",
          "context": "Chained him to a rock for stealing fire"
        },
        {
          "source": "Zeus",
          "target": "Pandora",
          "type": "created",
          "context": "As punishment for humanity"
        },
        {
          "source": "Deucalion",
          "target": "Pyrrha",
          "type": "married",
          "context": "Survived the great flood together"
        },
        {
          "source": "Heracles",
          "target": "Giants",
          "type": "defeated",
          "context": "Helped the gods defeat the Giants"
        },
        {
          "source": "Zeus",
          "target": "Humanity",
          "type": "destroyed",
          "context": "Sent the great flood to destroy humanity"
        }
      ],
      "key_events": [
        {
          "event": "Titanomachy",
          "participants": [
            "Zeus",
            "Kronos"
          ],
          "description": "Olympians defeat Titans",
          "significance": "New divine order established"
        },
        {
          "event": "Prometheus steals fire",
          "participants": [
            "Prometheus",
            "Humans"
          ],
          "description": "Prometheus gives fire to humanity",
          "significance": "Humans gain forbidden knowledge"
        },
        {
          "event": "Deucalion's Flood",
          "participants": [
            "Zeus",
            "Deucalion",
            "Pyrrha"
          ],
          "description": "Zeus destroys humanity, Deucalion and Pyrrha survive",
          "significance": "New humans created from stones"
        },
        {
          "event": "Gigantomachy",
          "participants": [
            "Olympian gods",
            "Giants"
          ],
          "description": "Gods defeat the Giants",
          "significance": "Olympian order solidified"
        },
        {
          "event": "Creation of Pandora",
          "participants": [
            "Zeus",
            "Pandora"
          ],
          "description": "Zeus creates Pandora as punishment for humanity",
          "significance": "Introduces evils into the world"
        }
      ],
      "source_file": "Greek_Theogony_Hesiod.txt"
    },
    {
      "source_text": "Mahabharata Vimana Passages",
      "culture": "Hindu/Indian",
      "entities": [
        {
          "name": "Pushpaka Vimana",
          "type": "vehicle",
          "culture": "Hindu/Indian",
          "description": "A flying palace/chariot originally belonging to Kubera"
        },
        {
          "name": "Arjuna's chariot",
          "type": "vehicle",
          "culture": "Hindu/Indian",
          "description": "Provided by Indra, drawn by celestial horses"
        },
        {
          "name": "Krishna's chariot Jaitra",
          "type": "vehicle",
          "culture": "Hindu/Indian",
          "description": "Divine chariot used by Krishna"
        },
        {
          "name": "Surya's chariot",
          "type": "vehicle",
          "culture": "Hindu/Indian",
          "description": "Chariot of the sun god, drawn by seven horses"
        },
        {
          "name": "Brahmastra",
          "type": "weapon",
          "culture": "Hindu/Indian",
          "description": "Brahma's weapon, a powerful incandescent projectile"
        },
        {
          "name": "Pasupatastra",
          "type": "weapon",
          "culture": "Hindu/Indian",
          "description": "Shiva's weapon, capable of destroying all creation"
        },
        {
          "name": "Narayanastra",
          "type": "weapon",
          "culture": "Hindu/Indian",
          "description": "Vishnu's weapon, releases millions of missiles"
        },
        {
          "name": "Varunastra",
          "type": "weapon",
          "culture": "Hindu/Indian",
          "description": "Varuna's weapon, controls water and creates floods"
        },
        {
          "name": "Vayavyastra",
          "type": "weapon",
          "culture": "Hindu/Indian",
          "description": "Vayu's weapon, creates hurricanes and tornados"
        },
        {
          "name": "Agneyastra",
          "type": "weapon",
          "culture": "Hindu/Indian",
          "description": "Agni's weapon, generates unquenchable fire"
        },
        {
          "name": "Yudhishthira",
          "type": "hero",
          "culture": "Hindu/Indian",
          "description": "Son of Dharma, the god of justice"
        },
        {
          "name": "Bhima",
          "type": "hero",
          "culture": "Hindu/Indian",
          "description": "Son of Vayu, the wind god"
        },
        {
          "name": "Arjuna",
          "type": "hero",
          "culture": "Hindu/Indian",
          "description": "Son of Indra, the king of gods"
        },
        {
          "name": "Nakula and Sahadeva",
          "type": "heroes",
          "culture": "Hindu/Indian",
          "description": "Sons of the Ashvin twins, divine physicians"
        },
        {
          "name": "Krishna",
          "type": "avatar",
          "culture": "Hindu/Indian",
          "description": "8th avatar of Vishnu incarnated as a human prince"
        }
      ],
      "relationships": [
        {
          "source": "Pushpaka Vimana",
          "target": "Kubera",
          "type": "belonged to",
          "context": "Originally belonging to the god of wealth"
        },
        {
          "source": "Pushpaka Vimana",
          "target": "Ravana",
          "type": "stolen by",
          "context": "Stolen by Ravana in the Ramayana"
        },
        {
          "source": "Arjuna's chariot",
          "target": "Indra",
          "type": "provided by",
          "context": "Provided by the king of gods"
        },
        {
          "source": "Brahmastra",
          "target": "Brahma",
          "type": "associated with",
          "context": "Brahma's powerful weapon"
        },
        {
          "source": "Pasupatastra",
          "target": "Shiva",
          "type": "associated with",
          "context": "Shiva's weapon, capable of destroying all creation"
        },
        {
          "source": "Narayanastra",
          "target": "Vishnu",
          "type": "associated with",
          "context": "Vishnu's weapon, releases millions of missiles"
        },
        {
          "source": "Varunastra",
          "target": "Varuna",
          "type": "associated with",
          "context": "Varuna's weapon, controls water and creates floods"
        },
        {
          "source": "Vayavyastra",
          "target": "Vayu",
          "type": "associated with",
          "context": "Vayu's weapon, creates hurricanes and tornados"
        },
        {
          "source": "Agneyastra",
          "target": "Agni",
          "type": "associated with",
          "context": "Agni's weapon, generates unquenchable fire"
        },
        {
          "source": "Yudhishthira",
          "target": "Dharma",
          "type": "son of",
          "context": "Son of the god of justice"
        }
      ],
      "key_events": [
        {
          "event": "Kurukshetra War",
          "participants": [
            "Pandavas",
            "Kauravas"
          ],
          "description": "Great war between two royal families",
          "significance": "Devastated the landscape, marked the end of Dvapara Yuga"
        },
        {
          "event": "Use of divine weapons",
          "participants": [
            "Pandavas",
            "Kauravas"
          ],
          "description": "Weapons of mass destruction used in the war",
          "significance": "Caused widespread destruction and loss of life"
        },
        {
          "event": "Dwarka submerged",
          "participants": [
            "Krishna"
          ],
          "description": "Krishna's city of Dwarka now underwater",
          "significance": "Parallels other submerged ancient civilizations"
        },
        {
          "event": "Divine/human interbreeding",
          "participants": [
            "Pandava heroes",
            "gods"
          ],
          "description": "Heroes fathered by gods through mantras",
          "significance": "Reflects themes of divine kingship and demigods"
        },
        {
          "event": "Brahmastra usage restrictions",
          "participants": [
            "Mahabharata text"
          ],
          "description": "Brahmastra should never be used on civilians",
          "significance": "Reflects divine laws of war"
        }
      ],
      "source_file": "Mahabharata_Vimana_Weapons.txt"
    },
    {
      "source_text": "Egyptian Pyramid Texts & Book of the Dead",
      "culture": "Egyptian",
      "entities": [
        {
          "name": "Nun",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Primeval waters"
        },
        {
          "name": "Atum",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Self-created creator god"
        },
        {
          "name": "Shu",
          "type": "deity",
          "culture": "Egyptian",
          "description": "God of air"
        },
        {
          "name": "Tefnut",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Goddess of moisture"
        },
        {
          "name": "Geb",
          "type": "deity",
          "culture": "Egyptian",
          "description": "God of earth"
        },
        {
          "name": "Nut",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Goddess of sky"
        },
        {
          "name": "Osiris",
          "type": "deity",
          "culture": "Egyptian",
          "description": "God of the dead"
        },
        {
          "name": "Isis",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Goddess of magic"
        },
        {
          "name": "Set",
          "type": "deity",
          "culture": "Egyptian",
          "description": "God of chaos"
        },
        {
          "name": "Nephthys",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Goddess of death"
        },
        {
          "name": "Horus",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Falcon-headed god"
        },
        {
          "name": "Anubis",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Jackal-headed god of embalming"
        },
        {
          "name": "Thoth",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Ibis-headed god of wisdom"
        },
        {
          "name": "Ma'at",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Goddess of truth and justice"
        },
        {
          "name": "Hathor",
          "type": "deity",
          "culture": "Egyptian",
          "description": "Cow-headed goddess of love and sky"
        }
      ],
      "relationships": [
        {
          "source": "Atum",
          "target": "Shu",
          "type": "created",
          "context": "Atum created Shu and Tefnut"
        },
        {
          "source": "Shu",
          "target": "Geb",
          "type": "created",
          "context": "Shu and Tefnut created Geb and Nut"
        },
        {
          "source": "Geb",
          "target": "Osiris",
          "type": "created",
          "context": "Geb and Nut created Osiris, Isis, Set, and Nephthys"
        },
        {
          "source": "Osiris",
          "target": "Set",
          "type": "killed",
          "context": "Set killed Osiris"
        },
        {
          "source": "Isis",
          "target": "Osiris",
          "type": "resurrected",
          "context": "Isis resurrected Osiris"
        },
        {
          "source": "Horus",
          "target": "Set",
          "type": "defeated",
          "context": "Horus defeated Set"
        },
        {
          "source": "Anubis",
          "target": "Osiris",
          "type": "judged",
          "context": "Anubis judged the deceased in the underworld"
        },
        {
          "source": "Ma'at",
          "target": "Osiris",
          "type": "judged",
          "context": "The heart was weighed against the feather of Ma'at"
        },
        {
          "source": "Ra",
          "target": "Apophis",
          "type": "battled",
          "context": "Ra battled the chaos serpent Apophis"
        },
        {
          "source": "Pharaoh",
          "target": "Ra",
          "type": "incarnated",
          "context": "The pharaoh was the living incarnation of Horus, son of Ra"
        }
      ],
      "key_events": [
        {
          "event": "Creation from Primeval Waters",
          "participants": [
            "Nun",
            "Atum"
          ],
          "description": "Atum arose from the primeval waters of Nun"
        },
        {
          "event": "Osiris Myth",
          "participants": [
            "Osiris",
            "Set",
            "Isis",
            "Horus"
          ],
          "description": "Osiris was killed by Set, resurrected by Isis, and avenged by Horus"
        },
        {
          "event": "Underworld Journey",
          "participants": [
            "Ba",
            "Anubis",
            "Ma'at"
          ],
          "description": "The soul travels through the underworld, judged by Anubis and Ma'at"
        },
        {
          "event": "Stellar Alignment",
          "participants": [
            "Pharaoh",
            "Orion",
            "Sirius"
          ],
          "description": "Pyramids aligned to Orion and Sirius, representing Osiris and Isis"
        },
        {
          "event": "Creation through Divine Word",
          "participants": [
            "Ptah"
          ],
          "description": "Ptah created the world through thought and speech"
        }
      ],
      "source_file": "Egyptian_Pyramid_Texts.txt"
    },
    {
      "source_text": "Zoroastrian Bundahishn",
      "culture": "Persian/Zoroastrian",
      "entities": [
        {
          "name": "Ahura Mazda",
          "type": "deity",
          "culture": "Persian/Zoroastrian",
          "description": "Wise Lord, supreme creator god",
          "aliases": []
        },
        {
          "name": "Angra Mainyu",
          "type": "deity",
          "culture": "Persian/Zoroastrian",
          "description": "Destructive Spirit, evil",
          "aliases": [
            "Ahriman"
          ]
        },
        {
          "name": "Gayomart",
          "type": "primordial",
          "culture": "Persian/Zoroastrian",
          "description": "First Man, shining, white, tall as a tree",
          "aliases": []
        },
        {
          "name": "Gavaevodata",
          "type": "primordial",
          "culture": "Persian/Zoroastrian",
          "description": "Primeval Bull",
          "aliases": []
        },
        {
          "name": "Mashya",
          "type": "primordial",
          "culture": "Persian/Zoroastrian",
          "description": "First human couple with Mashyana",
          "aliases": []
        },
        {
          "name": "Mashyana",
          "type": "primordial",
          "culture": "Persian/Zoroastrian",
          "description": "First human couple with Mashya",
          "aliases": []
        },
        {
          "name": "Yima",
          "type": "king",
          "culture": "Persian/Zoroastrian",
          "description": "First mortal king, ruled during Golden Age",
          "aliases": [
            "Jamshid"
          ]
        },
        {
          "name": "Saoshyant",
          "type": "savior",
          "culture": "Persian/Zoroastrian",
          "description": "Final savior, born of virgin, raises dead",
          "aliases": []
        },
        {
          "name": "Amesha Spentas",
          "type": "divine",
          "culture": "Persian/Zoroastrian",
          "description": "Holy Immortals, including Vohu Manah, Asha Vahishta, Armaiti, Khshathra Vairya, Haurvatat, Ameretat",
          "aliases": []
        },
        {
          "name": "Asha",
          "type": "concept",
          "culture": "Persian/Zoroastrian",
          "description": "Truth/Cosmic Order",
          "aliases": []
        },
        {
          "name": "Druj",
          "type": "concept",
          "culture": "Persian/Zoroastrian",
          "description": "The Lie",
          "aliases": []
        },
        {
          "name": "Vara",
          "type": "location",
          "culture": "Persian/Zoroastrian",
          "description": "Underground enclosure/fortress",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Ahura Mazda",
          "target": "World",
          "type": "created",
          "context": "In six stages"
        },
        {
          "source": "Angra Mainyu",
          "target": "World",
          "type": "attacked",
          "context": "Burst through sky, polluted water, cracked earth, withered plants, killed Bull and Gayomart"
        },
        {
          "source": "Gayomart",
          "target": "Mashya",
          "type": "seed",
          "context": "Gayomart's seed grew into first human couple"
        },
        {
          "source": "Mashya",
          "target": "Angra Mainyu",
          "type": "deceived",
          "context": "Declared Angra Mainyu as creator, first lie/sin"
        },
        {
          "source": "Yima",
          "target": "Vara",
          "type": "built",
          "context": "Underground enclosure to survive terrible winter"
        },
        {
          "source": "Ahura Mazda",
          "target": "Fravashis",
          "type": "consulted",
          "context": "Before creation, asked if they wanted to incarnate and fight Angra Mainyu"
        },
        {
          "source": "Saoshyant",
          "target": "World",
          "type": "purify",
          "context": "With molten metal, at end of time"
        },
        {
          "source": "Angra Mainyu",
          "target": "World",
          "type": "destroyed",
          "context": "At end of time, by Saoshyant"
        }
      ],
      "key_events": [
        {
          "event": "Creation from Cosmic Egg",
          "participants": [
            "Ahura Mazda"
          ],
          "description": "Ahura Mazda created the world in six stages",
          "significance": "Origin of the cosmos"
        },
        {
          "event": "Attack by Angra Mainyu",
          "participants": [
            "Angra Mainyu"
          ],
          "description": "Angra Mainyu attacked and corrupted the creation",
          "significance": "Introduction of evil into the world"
        },
        {
          "event": "Building of the Vara",
          "participants": [
            "Yima"
          ],
          "description": "Yima built an underground enclosure to survive a terrible winter",
          "significance": "Preservation of life during a catastrophic event"
        },
        {
          "event": "Final Renovation",
          "participants": [
            "Saoshyant"
          ],
          "description": "Saoshyant will raise the dead, judge all souls, and purify the world",
          "significance": "Restoration of the world to its original perfection"
        }
      ],
      "source_file": "Zoroastrian_Bundahishn.txt"
    },
    {
      "source_text": "Chinese Creation Myths",
      "culture": "Chinese",
      "entities": [
        {
          "name": "Pangu",
          "type": "deity",
          "culture": "Chinese",
          "description": "First Being who created the world from cosmic egg",
          "aliases": []
        },
        {
          "name": "Nüwa",
          "type": "deity",
          "culture": "Chinese",
          "description": "Female deity, creator of humans from clay",
          "aliases": []
        },
        {
          "name": "Gong Gong",
          "type": "deity",
          "culture": "Chinese",
          "description": "Water god, destroyed sky pillar causing flood",
          "aliases": []
        },
        {
          "name": "Zhurong",
          "type": "deity",
          "culture": "Chinese",
          "description": "Fire god",
          "aliases": []
        },
        {
          "name": "Fuxi",
          "type": "deity",
          "culture": "Chinese",
          "description": "Nüwa's brother/husband, invented writing and technology",
          "aliases": []
        },
        {
          "name": "Huangdi",
          "type": "human",
          "culture": "Chinese",
          "description": "Legendary ancestor, civilizer, ascended to heaven",
          "aliases": [
            "Yellow Emperor"
          ]
        },
        {
          "name": "Gun",
          "type": "human",
          "culture": "Chinese",
          "description": "Tried to stop flood, failed and was executed",
          "aliases": []
        },
        {
          "name": "Yu",
          "type": "human",
          "culture": "Chinese",
          "description": "Channeled flood waters, became first Xia emperor",
          "aliases": []
        },
        {
          "name": "Chi You",
          "type": "monster",
          "culture": "Chinese",
          "description": "Monstrous rebel defeated by Huangdi",
          "aliases": []
        },
        {
          "name": "Xiangliu",
          "type": "monster",
          "culture": "Chinese",
          "description": "Nine-headed serpent",
          "aliases": []
        },
        {
          "name": "Yin/Yang",
          "type": "concept",
          "culture": "Chinese",
          "description": "Dual forces",
          "aliases": []
        },
        {
          "name": "Wu Xing",
          "type": "concept",
          "culture": "Chinese",
          "description": "Five elements",
          "aliases": []
        }
      ],
      "relationships": [
        {
          "source": "Pangu",
          "target": "World",
          "type": "created",
          "context": "His body became earth, sky, rivers"
        },
        {
          "source": "Nüwa",
          "target": "Humans",
          "type": "created",
          "context": "Molded humans from clay"
        },
        {
          "source": "Gong Gong",
          "target": "Sky Pillar",
          "type": "destroyed",
          "context": "Broke pillar, causing flood"
        },
        {
          "source": "Nüwa",
          "target": "Sky Pillar",
          "type": "repaired",
          "context": "Patched hole in sky"
        },
        {
          "source": "Huangdi",
          "target": "Heaven",
          "type": "ascended",
          "context": "Ascended to heaven on a dragon"
        },
        {
          "source": "Huangdi",
          "target": "Knowledge",
          "type": "possessed",
          "context": "Had knowledge of technology and civilization"
        },
        {
          "source": "Gun",
          "target": "Flood",
          "type": "tried to stop",
          "context": "Stole 'breathing earth' but failed"
        },
        {
          "source": "Yu",
          "target": "Flood",
          "type": "channeled",
          "context": "Worked for 13 years to channel the waters"
        }
      ],
      "key_events": [
        {
          "event": "Creation from Cosmic Egg",
          "participants": [
            "Pangu"
          ],
          "description": "Pangu breaks open egg, separates heaven and earth",
          "significance": "Origin of the cosmos"
        },
        {
          "event": "Creation of Humans",
          "participants": [
            "Nüwa"
          ],
          "description": "Nüwa creates humans from clay",
          "significance": "Origin of humanity"
        },
        {
          "event": "Destruction of Sky Pillar",
          "participants": [
            "Gong Gong"
          ],
          "description": "Gong Gong breaks sky pillar, causing flood",
          "significance": "Catastrophic event leading to restoration"
        },
        {
          "event": "Restoration of Order",
          "participants": [
            "Nüwa"
          ],
          "description": "Nüwa repairs sky and channels flood waters",
          "significance": "Reestablishment of cosmic balance"
        }
      ],
      "source_file": "Chinese_Pangu_Nuwa_Creation.txt"
    },
    {
      "source_text": "Cath Maige Tuired",
      "culture": "Irish/Celtic",
      "entities": [
        {
          "name": "Lug",
          "type": "deity",
          "culture": "Irish",
          "description": "Master of all arts, kills Balor",
          "aliases": [
            "Lugh",
            "Samildanach"
          ]
        },
        {
          "name": "Nuadu Airgetlam",
          "type": "deity",
          "culture": "Irish",
          "description": "First king of TDD, lost and regained hand"
        },
        {
          "name": "Dagda",
          "type": "deity",
          "culture": "Irish",
          "description": "Wields a powerful club, owns a cauldron"
        },
        {
          "name": "Morrigan",
          "type": "deity",
          "culture": "Irish",
          "description": "War goddess, mates with Dagda before battle"
        },
        {
          "name": "Dian Cecht",
          "type": "deity",
          "culture": "Irish",
          "description": "Physician, makes Nuadu's silver hand"
        },
        {
          "name": "Goibniu",
          "type": "deity",
          "culture": "Irish",
          "description": "Smith, forges unbreakable weapons"
        },
        {
          "name": "Ogma",
          "type": "deity",
          "culture": "Irish",
          "description": "Champion, kills Indech in single combat"
        },
        {
          "name": "Bres mac Elathan",
          "type": "deity",
          "culture": "Irish",
          "description": "Half-Fomorian, tyrannical king"
        },
        {
          "name": "Balor",
          "type": "deity",
          "culture": "Irish",
          "description": "Fomorian champion, killed by Lug"
        },
        {
          "name": "Cian",
          "type": "deity",
          "culture": "Irish",
          "description": "Father of Lug"
        },
        {
          "name": "Ethne",
          "type": "deity",
          "culture": "Irish",
          "description": "Mother of Lug, daughter of Balor"
        },
        {
          "name": "Tailtiu",
          "type": "deity",
          "culture": "Irish",
          "description": "Foster mother of Lug"
        },
        {
          "name": "Miach",
          "type": "deity",
          "culture": "Irish",
          "description": "Son of Dian Cecht, heals Nuadu's hand"
        },
        {
          "name": "Airmed",
          "type": "deity",
          "culture": "Irish",
          "description": "Daughter of Dian Cecht, grows herbs from Miach's grave"
        },
        {
          "name": "Elatha",
          "type": "deity",
          "culture": "Irish",
          "description": "Fomorian king, father of Bres and Ogma"
        },
        {
          "name": "Eriu",
          "type": "deity",
          "culture": "Irish",
          "description": "Mother of Bres, daughter of TDD"
        },
        {
          "name": "Coirpre",
          "type": "deity",
          "culture": "Irish",
          "description": "Poet, composes first satire against Bres"
        },
        {
          "name": "Net",
          "type": "deity",
          "culture": "Irish",
          "description": "Grandfather of Balor"
        },
        {
          "name": "Macha",
          "type": "deity",
          "culture": "Irish",
          "description": "Killed by Balor in battle"
        },
        {
          "name": "Mac Oc",
          "type": "deity",
          "culture": "Irish",
          "description": "Son of Dagda, tricks him out of Brú na Bóinne"
        }
      ],
      "relationships": [
        {
          "source": "Lug",
          "target": "Balor",
          "type": "kills",
          "context": "Sling stone through the Evil Eye"
        },
        {
          "source": "Lug",
          "target": "Cian",
          "type": "son of",
          "context": "Son of Cian (son of Dian Cecht)"
        },
        {
          "source": "Lug",
          "target": "Ethne",
          "type": "son of",
          "context": "Son of Ethne (daughter of Balor)"
        },
        {
          "source": "Lug",
          "target": "Tailtiu",
          "type": "foster son of",
          "context": "Foster son of Tailtiu"
        },
        {
          "source": "Dagda",
          "target": "Morrigan",
          "type": "mates with",
          "context": "Mates with the Morrigan at the Ford of the Unshin before battle"
        },
        {
          "source": "Dagda",
          "target": "Mac Oc",
          "type": "father of",
          "context": "Father of Mac Oc (Aengus Óg) who tricks him out of Brú na Bóinne"
        },
        {
          "source": "Dian Cecht",
          "target": "Miach",
          "type": "father of",
          "context": "Father of Miach"
        },
        {
          "source": "Dian Cecht",
          "target": "Airmed",
          "type": "father of",
          "context": "Father of Airmed"
        },
        {
          "source": "Dian Cecht",
          "target": "Cian",
          "type": "father of",
          "context": "Father of Cian"
        },
        {
          "source": "Bres",
          "target": "Elatha",
          "type": "son of",
          "context": "Son of Elatha (Fomorian) and Eriu (TDD)"
        },
        {
          "source": "Nuadu",
          "target": "Lug",
          "type": "gives kingship to",
          "context": "Gives kingship to Lug"
        },
        {
          "source": "Goibniu",
          "target": "Luchta",
          "type": "part of trinity with",
          "context": "With Luchta (carpenter) and Credne (brazier) = trinity of craftsmen"
        },
        {
          "source": "Goibniu",
          "target": "Credne",
          "type": "part of trinity with",
          "context": "With Luchta (carpenter) and Credne (brazier) = trinity of craftsmen"
        },
        {
          "source": "Ogma",
          "target": "Indech mac De Domnann",
          "type": "kills",
          "context": "Kills Indech mac De Domnann in single combat"
        },
        {
          "source": "Balor",
          "target": "Lug",
          "type": "killed by",
          "context": "Killed by Lug: sling stone carries eye through back of head"
        }
      ],
      "key_events": [
        {
          "event": "TDD arrive from Northern Islands with Four Treasures",
          "participants": [
            "TDD"
          ],
          "description": "TDD arrive with powerful artifacts",
          "significance": "Establishes TDD's power"
        },
        {
          "event": "Bres made king, tyranny and enslavement of gods",
          "participants": [
            "Bres",
            "TDD"
          ],
          "description": "Half-Fomorian Bres becomes tyrannical king",
          "significance": "Leads to Bres's deposition"
        },
        {
          "event": "Lug arrives at Tara, proves mastery, given kingship",
          "participants": [
            "Lug",
            "TDD"
          ],
          "description": "Lug demonstrates his skills, becomes king",
          "significance": "Lug leads TDD to victory"
        },
        {
          "event": "Battle: Lug kills Balor, Ogma kills Indech, Nuadu falls",
          "participants": [
            "Lug",
            "Balor",
            "Ogma",
            "Indech",
            "Nuadu"
          ],
          "description": "Key deities fight and die in the battle",
          "significance": "TDD defeat Fomorians, establish divine order"
        },
        {
          "event": "Morrigan prophesies peace, then the end of the world",
          "participants": [
            "Morrigan"
          ],
          "description": "Morrigan announces victory, then foretells the end",
          "significance": "Foreshadows future events"
        }
      ],
      "source_file": "Cath_Maige_Tuired_Second_Battle.txt"
    }
  ],
  "stats": {
    "total_entities": 266,
    "total_relationships": 188,
    "total_events": 75,
    "total_patterns": 7,
    "sources_processed": 19
  }
};
