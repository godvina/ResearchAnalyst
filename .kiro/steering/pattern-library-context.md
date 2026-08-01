---
inclusion: auto
---

# Pattern Library Taxonomy Context

This project uses a 5-level Pattern Library Taxonomy for scoring cases against known prosecution patterns.

## Taxonomy Hierarchy

```
Domain → Typology → Method → Signature → Case
```

- **Domain**: Broad enforcement area (Antitrust, Sex Trafficking, Fraud/Waste/Abuse)
- **Typology**: Crime category (e.g., Procurement Collusion, Price Fixing)
- **Method**: Specific technique (e.g., Bid Rotation, Cover Bidding)
- **Signature**: Detectable evidence pattern with vector embedding for k-NN matching
- **Case**: DOJ precedent case proving the signature

## Key File: `src/data/pattern-library-taxonomy.json`

This is the machine-readable taxonomy containing all signatures. Each signature has:
- `signature_id`: Unique ID (format: `{domain}-{typology}-{method}-{seq}`)
- `vector_text`: The text that gets embedded via Titan Embed v2 for k-NN matching
- `indicators`: Observable signals an analyst should look for
- `precedent_case`: The DOJ case that proves this pattern exists
- `severity`: critical | high | moderate | low

## How Scoring Works

1. `extract_subgraph.py` pulls entities + edges from Neptune for each sub-category
2. `score_typology.py` embeds evidence via Titan Embed v2 (1024-dim)
3. Vector queried against `typology-patterns` OpenSearch index via k-NN
4. Top-k matches scored by cosine similarity
5. Blended: 60% k-NN + 40% graph density
6. Results stored in Aurora `typology_precomputed_results`

## Antitrust Domain (6 Typologies, 138 total signatures)

| Typology | Needles | Methods | Color |
|----------|---------|---------|-------|
| Procurement Collusion | 28 | Bid Rotation, Cover Bidding, Phantom Bidding, Market Allocation by Customer, Subcontract Kickback | #ef4444 (red) |
| Price Fixing | 24 | Horizontal Price Agreement, Information Exchange, Output Restriction, Market Division | #fb923c (orange) |
| Criminal Cartel | 26 | International Cartel, Domestic Conspiracy, Obstruction/Cover-up, Recidivism | #a855f7 (purple) |
| Monopolization | 22 | Exclusionary Conduct, Predatory Pricing, Acquisitions to Maintain Monopoly, Platform Self-Preferencing | #3b82f6 (blue) |
| Market Allocation | 20 | Geographic Division, Customer Allocation, No-Poach Agreements, Wage-Fixing | #22c55e (green) |
| Merger Review | 18 | Horizontal Concentration, Vertical Foreclosure, Coordinated Effects, Innovation Harm | #ec4899 (pink) |

## When Analyzing a Case

When reviewing any case (e.g., "Epstein Truck Fraud"), the system should:
1. Identify which domain/typology the case falls under
2. Score case evidence against ALL signatures in that typology via k-NN
3. Surface the top matching signatures with their precedent cases
4. Show which specific methods and indicators triggered
5. Cross-reference against other typologies for multi-domain patterns

## Other Domains

### Ancient Mysteries (`src/data/ancient-mysteries-taxonomy.json`)
A non-crime domain demonstrating the platform's universality. Same scoring infrastructure applied to alternative history research.

| Theory Class | Signatures | Methods |
|-------------|-----------|---------|
| Advanced Ancient Technology | 18 | Pyramid Power, Precision Machining, Ancient Electricity, Acoustic Tech, Ancient Aviation, Lost Metallurgy |
| Global Grid & Earth Energy | 9 | Ley Lines, Energy Nodes, Equidistant Placement, Geomagnetic Construction, Sacred Geometry Placement |
| Lost Civilizations | 11 | Pre-Flood Architecture, Younger Dryas Impact, Flood Narratives, Impossible Dating, Knowledge Preservation |
| Extraterrestrial Contact | 9 | Ancient Astronaut Art, Genetic Intervention, Star Knowledge, Sacred Texts as Contact |
| Sacred Geometry & Mathematics | 7 | Encoded Constants, Astronomical Precession, Universal Measurements, Cymatics |
| Consciousness & Non-Physical | 8 | Pineal/Third Eye, Psychedelic Sacraments, Sound Frequency, Crystal Technology |

### Sports / RINK (pending from other session)
Hockey pattern recognition — to be integrated when pattern library reference doc is provided.

## Reference Files
- #[[file:src/data/pattern-library-taxonomy.json]]
- #[[file:src/data/ancient-mysteries-taxonomy.json]]
