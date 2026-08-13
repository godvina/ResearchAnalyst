# Archon Library — Full Build Plan

## Overview
Expand the Archon Library from 3 source texts (34 entities) to a comprehensive cross-cultural mythology intelligence system with 11+ source traditions, 150+ entities, and direct crosswalk to the existing Irish Sacred Sites / Ancient Mysteries module.

---

## Phase 1: Source Text Acquisition & Processing
**Goal:** Get all P0 and P1 texts downloaded and entity-extracted.

### Step 1: Download P0 texts (most critical — connect to existing data)
- [ ] **Lebor Gabála Érenn** (Irish Book of Invasions) — Tuatha Dé Danann source text
  - Source: https://celt.ucc.ie/published/T100001A/ (CELT Project, UCC — full English translation, public domain)
  - Why P0: DIRECTLY names the entities at your Irish Sacred Sites (Dagda → Newgrange, Nuada → Tara, Lugh → multiple sites)
- [ ] **Atra-Hasis** — Complete Anunnaki creation + flood
  - Source: https://www.livius.org/sources/content/anet/104-106-the-epic-of-atrahasis/
  - Why P0: Fills the "humans created as workers" gap in Gilgamesh
- [ ] **Book of Enoch** (1 Enoch, chapters 1-36)
  - Source: https://sacred-texts.com/bib/boe/index.htm (R.H. Charles 1917 translation, public domain)
  - Why P0: Most detailed "Watchers descend, mate with humans, produce giants" text

### Step 2: Process P0 texts through Bedrock extraction
- Run archon_process_texts.py (already built) on new PDFs/texts
- Expected output: ~60-80 new entities, ~50 relationships
- Key entities to extract: all Tuatha Dé Danann members (Dagda, Lugh, Nuada, Brigid, Dian Cécht, Morrigan, Manannán), all Watchers (Semjâzâ, Azâzêl, etc.), Nephilim

### Step 3: Download P1 texts
- [ ] Sumerian King List (ETCSL Oxford — public domain)
- [ ] Mahabharata Vimana sections (sacred-texts.com)
- [ ] Popol Vuh (sacred-texts.com — Goetz/Morley translation)

### Step 4: Process P1 texts
- Same pipeline. Expected: +40-60 entities, +30 relationships
- Focus: Mayan parallels (zero cultural contact with Mesopotamia), Hindu vimanas, pre-flood king lifespans

---

## Phase 2: Entity Crosswalk (Archon ↔ Geographic Explorer)
**Goal:** Connect mythology entities to physical sites already in the system.

### Step 5: Build the Tuatha Dé Danann ↔ Irish Sites mapping
```json
{
  "Dagda": ["newgrange", "brugh_na_boinne"],
  "Nuada": ["tara", "hill_of_tara"],
  "Lugh": ["carrowkeel", "teltown"],
  "Brigid": ["kildare", "imbolc_sites"],
  "Angus_Og": ["newgrange"],
  "Morrigan": ["rathcroghan", "cave_of_cats"]
}
```

### Step 6: Build the Anunnaki ↔ Mesopotamian Sites mapping
```json
{
  "Anu": ["uruk", "eanna_temple"],
  "Enki": ["eridu"],
  "Enlil": ["nippur"],
  "Inanna": ["uruk"],
  "Marduk": ["babylon", "esagila"]
}
```

### Step 7: Create "Mythology Layer" in Geographic Explorer
- Toggle on the map: show divine associations at each site
- When active: sites display which deities are associated + which texts reference them
- Color-code by tradition (gold=Sumerian, green=Irish, blue=Greek, orange=Hindu)

---

## Phase 3: Cross-Cultural Pattern Scoring
**Goal:** Use the same k-NN scoring approach as the crime library to find pattern matches across traditions.

### Step 8: Embed all 7 Archon patterns as vectors
- Use Titan Embed v2 on each pattern's indicator text
- Store in Aurora pgvector (alongside crime signatures but in separate table)
- Index: `archon_patterns` (distinct from `typology_patterns`)

### Step 9: Score source texts against patterns
- For each extracted text passage, embed and score against 7 patterns
- Output: "This passage from Popol Vuh matches 'Divine Creation of Humans as Workers' with 0.87 similarity"
- This is the "cross-cultural convergence detection" — same as cross-domain in crime

### Step 10: Score Irish Sacred Sites against Archon patterns
- Take existing site descriptions from Geographic Explorer
- Score each against Archon patterns
- Expected finding: Newgrange scores HIGH on "Solar/Astronomical Alignment" + "Underground Retreat" + "Divine Kingship"

---

## Phase 4: Enhanced Frontend
**Goal:** Make the Archon page a full research tool with crosswalk visualization.

### Step 11: Add crosswalk panel to archon.html
- Table showing: Sumerian entity | Irish equivalent | Greek | Hindu | Shared attributes
- Clickable — links to Geographic Explorer for physical sites

### Step 12: Add timeline view
- Horizontal timeline: texts ordered chronologically
- Show which patterns appear when (oldest → newest)
- Visual: "Flood pattern appears 2100 BCE (Eridu) → 1700 BCE (Atra-Hasis) → 1100 BCE (Gilgamesh XI) → 600 BCE (Genesis) → 300 BCE (Enoch)"

### Step 13: Add "Pattern Evidence" scoring panel
- For each of 7 cross-cultural patterns, show:
  - How many traditions contain it (out of 11)
  - Strength of each match (vector similarity)
  - Verdict: UNIVERSAL (8+), WIDESPREAD (5-7), REGIONAL (2-4), ISOLATED (1)

### Step 14: Add comparison view
- Side-by-side: pick 2-3 traditions
- Show entity crosswalk between them
- Highlight shared patterns vs. unique elements

---

## Phase 5: Integration with Ancient Aliens Case File
**Goal:** Connect Archon to the existing Ancient Aliens Investigation case (238 episodes extracted).

### Step 15: Score Ancient Aliens claims against Archon source texts
- Pull entity/claim data from the AA case file
- Score each claim against the actual source texts
- Output: "Ancient Aliens S03E05 claims X about the Anunnaki. Source text (Enuma Elish) actually says Y. Match: 60% / Embellishment: 40%"

### Step 16: Build "Fact vs. Fiction" panel
- For each AA claim: what the source text actually says vs. what AA claims
- Scored: ACCURATE, EXAGGERATED, MISATTRIBUTED, FABRICATED

---

## Estimated Effort & Costs

| Phase | Time | Bedrock Cost | Output |
|-------|------|-------------|--------|
| Phase 1 (acquisition + extraction) | 2-3 hours | ~$0.50 | 150+ entities, 100+ relationships |
| Phase 2 (crosswalk) | 1-2 hours | $0 (manual mapping) | Entity-site connections |
| Phase 3 (pattern scoring) | 1 hour | ~$0.30 | Scored patterns across traditions |
| Phase 4 (frontend) | 2-3 hours | $0 | Enhanced Archon UI |
| Phase 5 (AA integration) | 2-3 hours | ~$0.50 | Fact-checking 238 episodes worth of claims |
| **Total** | **8-12 hours** | **~$1.30** | Complete mythology intelligence system |

---

## Priority for Next Session

**Start with:** Phase 1, Steps 1-2 (Download Lebor Gabála Érenn + Atra-Hasis + Book of Enoch, process through existing pipeline)

**Why:** These 3 texts connect directly to your existing demo data:
- Lebor Gabála → names the Tuatha Dé Danann entities already referenced in Geographic Explorer
- Atra-Hasis → completes the Anunnaki narrative (fills gaps in Gilgamesh extraction)
- Enoch → adds the Watchers/Nephilim tradition (bridges Sumerian → Hebrew)

After those 3, you have a complete "Anunnaki dossier" that cross-references with your Irish sites AND stands alone as a mythology analysis tool.

---

*Created: 2026-08-09*
*Session note: Context was deep when this plan was written. Start fresh next session with Step 1.*
