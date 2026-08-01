# Data Gap Analysis & Research Plan

## Current State (as of 2026-08-01)

### What We Have
- 59/62 nodes researched (broad scan)
- 41/59 have at least one signature match
- 14 strong matches, 34 moderate, 33 weak
- 5 dominant signatures: se-004 (submerged), ga-003 (tectonic), cm-001 (sacred), cnp-004 (cluster), ga-002 (geometric)

### What's Missing — The Critical Gaps

| Gap | Impact | Fix |
|-----|--------|-----|
| **Ley line signatures (lla-001, lla-002) = 0 matches** | Can't show any alignment evidence on the ley line dashboard | Need great-circle alignment queries |
| **18 nodes with zero matches** (incl. Giza, Sedona, Nazca, Angkor, Easter Island!) | Our BEST sites have no scored signatures | Taxonomy-guided scan missed obvious sites |
| **Only 2 strong megalithic hits (san-001)** | Can't visualize the "impossible stone" pattern | Need specific construction queries |
| **Zero cross-node pattern hits (cnp-001, cnp-002)** meaningful | The most powerful Documentary story (same technique 5000km apart) has no data | Need comparative queries |
| **Generic indicators dominate** ("Within Xkm") | Network graph is noise — connections are meaningless proximity | Need specific trait indicators |
| **No expert/source data** | Can't populate documentary briefs | Need query layer for researchers, publications |

### Root Cause
The batch_research_taxonomy_guided.py ran ONE generic query per signature. Example for cm-001:
> "Indigenous oral tradition sacred site [coordinates]"

This is too broad. It matches anything with "indigenous" near any coordinate. We need SPECIFIC queries like:
> "What specific indigenous tradition marks [Sedona/Lake Baikal/etc.] as sacred? What ceremonies? What do they describe feeling there?"

---

## Research Plan: 3 Targeted Scans

### Scan 1: "Ley Line Deep Dive" (fills ley line dashboard)
**Goal**: Find which grid vertices lie on documented great-circle alignments
**Queries per node** (8 confirmed + near sites):
1. "great circle alignment ancient sites passing through [coordinates]"
2. "[Site name] alignment with other ancient monuments same line"  
3. "sites aligned between [Site A] and [Site B] on great circle"
4. "precise cardinal alignment measurement [site name] degrees arcminutes"
5. "[Site name] connection to [distant site] geometric relationship"

**Expected output**: Populate lla-001 and lla-002 signatures. Connect Giza → Angkor → Easter Island on the map.

### Scan 2: "Signature Deep Dive" (fills the 18 zero-match nodes)
**Goal**: Get specific evidence for our best-known sites
**Target nodes**: 1 (Giza), 17 (Sedona), 25 (Angkor), 35 (Nazca), 47 (Easter Island)
**Queries per node** (multi-signature):
1. MEGALITHIC: "[site] largest stone blocks weight tons quarry distance"
2. ASTRONOMICAL: "[site] astronomical alignment solstice equinox precession"
3. CONSTRUCTION: "[site] construction technique unexplained precision measurement"
4. CULTURAL: "[site] indigenous name meaning why sacred tradition ceremony"
5. COMPARISON: "[site] same technique as [other site] similar construction different continent"

### Scan 3: "Cross-Pattern Connection Scan" (the documentary gold)
**Goal**: Find SPECIFIC shared traits between distant sites
**This is the scan that finds the story.**
**Queries**:
1. "Same stone-cutting technique Sacsayhuaman Japan castle walls Alatri Italy"
2. "Orion belt alignment pyramids multiple civilizations Teotihuacan Angkor"
3. "Same astronomical precision different continents north alignment"
4. "Indigenous traditions buzzing vibrating energy specific sites worldwide"
5. "Pre-flood civilization sea level 120m lower coastal sites now underwater"

---

## Taxonomy Improvement: New Signatures to Add

### lla-003: "Great Circle Site Chain"
```
Description: 4+ major ancient sites lying within 0.5° of same great circle
Indicators: [4+ sites on line, < 0.5° deviation, 3+ different cultures, measurable by GPS]
Vector text: "Four or more major ancient sites from different cultures lying within half a degree of the same great circle route as measurable by modern GPS"
```

### cnp-005: "Same Impossible Weight"
```
Description: Sites on different grid nodes using stones of same extreme weight class (>100 tons)
Indicators: [>100 ton stones, different continents, same weight range, no modern explanation]
```

### cnp-006: "Same Calendar Encoding"
```
Description: Calendar system or astronomical cycle encoded in architecture at 3+ grid sites
Indicators: [Same cycle length, built into structure dimensions, different civilizations]
```

### doc-001: "Documentary Visual Asset"
```
Description: Location has confirmed aerial/drone footage potential for production
Indicators: [Dramatic landscape, accessible, visual anomaly, previously filmed]
```

---

## Best Research Sources for This Domain

### Tier 1: Academic/Measured
- USGS geological surveys and earthquake databases
- NOAA bathymetric databases (GEBCO)
- NASA/ESA LiDAR and satellite archives
- JSTOR archaeoastronomy papers
- Ordnance Survey (UK) precise monument coordinates

### Tier 2: Published Researchers (credentialed)
- Graham Hancock (comparative megalithic)
- Robert Bauval (Orion correlation, pyramid astronomy)
- Jim Alison (great circle alignments — PRECISE measurements)
- John Michell (ley lines, sacred geometry)
- Paul Devereux (earth mysteries, ley line measurement)
- Klaus Schmidt (Göbekli Tepe)
- Robert Schoch (geological dating of Sphinx)
- Randall Carlson (sacred geometry, catastrophism)

### Tier 3: Databases
- Megalithic Portal (megalithic.co.uk) — 45,000+ sites with coordinates
- The Modern Antiquarian (UK sites)
- World Heritage Site database (UNESCO)
- Open Archaeological Map
- Ancient Origins (ancientorigins.net)

### Tier 4: Indigenous Sources
- National Museum of the American Indian archives
- Australian Institute of Aboriginal and Torres Strait Islander Studies
- Cultural heritage databases by country

---

## Execution Priority

1. **Scan 2 first** (fix the embarrassing zeros at Giza/Sedona/Nazca)
2. **Scan 1 second** (populate the ley line dashboard we just built)
3. **Scan 3 third** (find the documentary stories)

Estimated time: 15 min per scan × 3 = 45 minutes of Bedrock + Brave queries.
