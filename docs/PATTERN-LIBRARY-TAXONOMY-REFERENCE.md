# TALOS Crime Pattern Library — Taxonomy Reference

## Overview

The Crime Pattern Library is the core intelligence asset of the TALOS platform. It encodes how crimes work and how they get caught into machine-readable detection signatures that can be scored against any dataset in real-time.

**Architecture:** One master library (15 typologies, 150+ needles) with domain-specific expanded libraries that go deeper into individual fraud/crime domains.

**Location in codebase:**
- Master Library UI: `frontend/src/app/crime-patterns/page.tsx`
- Master Library API: `frontend/src/app/api/crime-patterns/`
- Master Library Data: `.gitlab-hsi-push/data/crime-pattern-library/`
- OpenSearch Index: `talos-trade` (150 vectors) + `talos-fema-signatures` (172 vectors)
- Neptune Graph: `neptunedbcluster-qoxzlhiau0ao`

---

## Taxonomy Hierarchy (5 Levels)

```
DOMAIN (4 domains)
  └── TYPOLOGY (15 crime typologies)
        └── METHOD (how the crime is committed)
              └── SIGNATURE / NEEDLE (specific testable detection condition)
                    └── CASE (real DOJ prosecution that validates the signature)
```

---

## Level 1: Domains (4)

| Domain | Color | Typologies | Focus |
|--------|-------|-----------|-------|
| Trade & Smuggling | Cyan (#06B6D4) | 5 | Physical goods, border, maritime |
| Financial Crime | Amber (#F59E0B) | 4 | Money flows, fraud, corruption |
| Violence & Exploitation | Red (#DC3545) | 3 | Human trafficking, gangs, smuggling |
| Digital Crime | Blue (#3B82F6) | 3 | Cyber, exploitation, scams |

---

## Level 2: Typologies (15)

### Trade & Smuggling Domain
| # | Typology ID | Name | Needles | Key Methods |
|---|-------------|------|---------|-------------|
| 1 | drug-trafficking | Drug Trafficking | 14 | Precursor Diversion, Corridor Smuggling, Dark Market Distribution |
| 2 | organized-crime | Organized Crime | 10 | Cartel Hierarchy, Franchise Model, Enterprise Violence |
| 3 | sanctions-evasion | Sanctions Evasion | 8 | Front Company Network, Vessel Deception, Financial Circumvention |
| 4 | counter-proliferation | Counter-Proliferation | 7 | Dual-Use Technology Diversion, WMD Supply Chain |
| 5 | environmental-crime | Environmental Crime | 7 | Wildlife Trafficking, Resource Extraction, Waste Crime |

### Financial Crime Domain
| # | Typology ID | Name | Needles | Key Methods |
|---|-------------|------|---------|-------------|
| 6 | money-laundering | Money Laundering | 20 | Trade-Based ML, Shell Layering, Structuring, Crypto Laundering |
| 7 | fraud-identity | Fraud & Identity Crime | 15 | Phantom Beneficiary, Procurement Fraud, Healthcare Billing, FEMA Disaster Fraud, Immigration Fraud |
| 8 | terrorism-financing | Terrorism Financing | 7 | Charity Front, Hawala Network, Self-Funding |
| 9 | public-corruption | Public Corruption | 5 | Bribery, Official Abuse, Regulatory Capture |

### Violence & Exploitation Domain
| # | Typology ID | Name | Needles | Key Methods |
|---|-------------|------|---------|-------------|
| 10 | human-trafficking | Human Trafficking | 8 | Circuit Rotation, Labor Exploitation, Online Recruitment |
| 11 | transnational-gangs | Transnational Gangs | 5 | Territory Control, Recruitment Pipeline |
| 12 | human-smuggling | Human Smuggling | 6 | Stash Houses, Document Fraud, Maritime Crossing |

### Digital Crime Domain
| # | Typology ID | Name | Needles | Key Methods |
|---|-------------|------|---------|-------------|
| 13 | cybercrime | Cybercrime | 6 | Ransomware, Credential Markets, BEC |
| 14 | child-exploitation | Child Exploitation | 4 | Distribution, Production, Online Enticement |
| 15 | scam-centers | Scam Centers | 5 | Pig Butchering, Call Centers, Investment Schemes |

---

## Expanded Libraries (Deep-Dive Domains)

These take a single typology and expand it into 100+ specific signatures with full case validation:

| Library | Parent Typology | Types | Methods | Signatures | Cases | Route | Deck |
|---------|----------------|-------|---------|-----------|-------|-------|------|
| ICE Immigration Fraud | fraud-identity | 10 | 43 | 215 | 25 | `/hsi/immigration-fraud` | ICE-Asylum-Fraud-Deck.html |
| FEMA Fraud Waste Abuse | fraud-identity | 10 | 42 | 168 | 25 | `/fema/fraud-patterns` | FEMA-FWA-Deck.html |

---

## Level 3: Methods (Examples from Expanded Libraries)

### Immigration Fraud (10 Types, 43 Methods)
| Type | Methods |
|------|---------|
| Benefit Fraud | SNAP/EBT misuse, DACA misuse, Work authorization fraud, Identity theft for benefits, Eligibility manipulation |
| Document & Passport Fraud | Forged passport, Counterfeit green card, Fraudulent immigration docs, False ID docs |
| Visa Fraud | Sham marriage, Staged crimes for U-visa, H-1B petition fraud, Fraudulent employment petitions, Student visa fraud |
| Naturalization Fraud | Concealed criminal history, False good moral character, Fraudulent residence claims, Identity fraud in naturalization |
| Preparer/Notario Fraud | False representation as attorney, VAWA fraud filing, Coaching clients to lie, Template application recycling |
| Identity Fraud (immigration) | Stolen SSN for employment, Multiple identities across filings, Perjured immigration documents, Biometric mismatch |
| Smuggling + Fraud | Alien smuggling conspiracy, Concealment in vehicles, Fraudulent sponsorship, Document fraud at border |
| Marriage Fraud | Sham marriage ring, Paid spouse arrangements, Marriage certificate fraud, Serial petitioners |
| Employment/Labor Fraud | H-1B mill operation, H-2A worker exploitation, Forced labor with visa coercion, Fraudulent work authorization |
| Asylum Fraud | Immigration scam network, Coached narrative cluster, Document fabrication, Credible fear exploitation, Identity fraud in asylum |

### FEMA FWA (10 Types, 42 Methods)
| Type | Methods |
|------|---------|
| Individual Assistance Fraud | False address claims, Stolen identity applications, Duplicate benefit claims, Inflated damage claims, Fabricated losses |
| Contractor & Debris Removal | Debris volume inflation, Phantom debris removal, Bid rigging & collusion, Inflated labor charges, Kickback schemes |
| Public Assistance Grant Fraud | Pre-existing damage attribution, Change order abuse, Duplicate project worksheets, Fraudulent cost documentation, Ineligible facility claims |
| Hazard Mitigation Grant Fraud | Phantom elevation projects, Acquisition buyout manipulation, Mitigation non-completion, BCA manipulation |
| National Flood Insurance Fraud | Inflated flood claims, Staged/pre-existing damage, WYO carrier fraud, Policy manipulation |
| Identity Theft & Synthetic | Stolen SSN rings, Synthetic identity claims, Organized fraud rings, Insider-facilitated fraud |
| FEMA Impersonation & Scams | Fake inspector schemes, Fraudulent application assistance, Phishing/social engineering, Disaster charity fraud |
| Procurement & Contracting | Non-competitive steering, False invoicing, MBE/WBE pass-through, Product substitution |
| Housing Assistance Fraud | Rental diversion, Transitional shelter fraud, Home repair misrepresentation, Manufactured housing fraud |
| Pandemic Disaster Fraud | Funeral assistance fraud, Lost wages fraud, Mass fraud schemes, Program stacking |

---

## Level 4: Signatures (Examples)

A signature is a **specific, testable, observable detection condition** proven by DOJ prosecution:

### Asylum Fraud Signatures (7 key examples)
| Signature | Method | Proven By |
|-----------|--------|-----------|
| Same preparer address on 50+ filings in 12 months | Immigration scam network | AF-001 Tampa (487 filings) |
| Near-identical persecution narratives from unrelated applicants | Coached narrative cluster | AF-002 Brooklyn (312 clients) |
| PDF metadata creation date post-dates claimed persecution event by 2+ years | Document fabrication | AF-005 Newark |
| Same verbatim trigger phrase used at 200+ credible fear screenings in single month | Credible fear exploitation | AF-004 San Ysidro (2,340) |
| Biometric/fingerprint match to prior removal order under different name | Identity fraud in asylum | AF-007 Miami (34 matches) |
| Same witness names cited in 10+ unrelated filings across jurisdictions | Coached narrative cluster | AF-002 Brooklyn |
| Zero I-589 filings after credible fear approval (EAD obtained, asylum never pursued) | Credible fear exploitation | AF-018 Phoenix (670 apps) |

### FEMA FWA Signatures (7 key examples)
| Signature | Method | Proven By |
|-----------|--------|-----------|
| SSN belongs to deceased individual per SSA Death Master File | Stolen identity applications | FWA-001 Williams ($1.74M) |
| Claimed address not in FEMA-declared disaster zone | False address claims | FWA-003 Lahaina/CA |
| Cubic yard counts exceed estimated structure volume by 200%+ | Debris volume inflation | FWA-007 Augusta |
| Bid amounts within 1% of each other across 3+ firms | Bid rigging & collusion | FWA-011 Hurricane Maria PR |
| Property elevation claimed but LiDAR shows no change in foundation height | Phantom elevation projects | FWA-012 Houston |
| 500+ applications from same geographic cluster within 72 hours | Mass fraud schemes | FWA-010 Miami ($12.4M) |
| Death certificate cause of death not COVID-related | Funeral assistance fraud | FWA-008 Newark |

---

## Technical Implementation

### How Signatures Become Vectors
```
Signature text → Titan Embed v1 → 1536-dim vector → OpenSearch kNN index
```

### How Scoring Works
```
New document → Embed → kNN search against signature vectors → 
Top matches (cosine > 0.82) → Nova Pro validates → Risk score + alert
```

### Key Files
| File | Purpose |
|------|---------|
| `data/crime-pattern-library/taxonomy.json` | Full taxonomy structure (all 15 typologies) |
| `data/crime-pattern-library/manifest.json` | All 150 master needles with DOJ source URLs |
| `data/fema-cases/embed-fema-signatures.mjs` | Script to embed FEMA signatures |
| `data/fema-cases/generate-neptune-graph.mjs` | Script to generate Neptune graph from cases |
| `frontend/src/app/hsi/immigration-fraud/page.tsx` | Immigration fraud 215 signatures (inline) |
| `frontend/src/app/fema/fraud-patterns/page.tsx` | FEMA FWA 168 signatures (inline) |

### AWS Resources
| Resource | ID/Endpoint |
|----------|-------------|
| OpenSearch Collection | hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com |
| Master Signatures Index | `talos-trade` (150 vectors) |
| FEMA Signatures Index | `talos-fema-signatures` (172 vectors) |
| Neptune Cluster | neptunedbcluster-qoxzlhiau0ao |
| S3 Bucket | research-analyst-data-lake-974220725866 |
| Embedding Model | amazon.titan-embed-text-v1 (1536 dims) |
| Scoring Model | amazon.nova-pro-v1:0 |

---

## How to Add a New Domain

Follow the Pattern Library Build Guide (`.kiro/steering/pattern-library-builds.md`):

1. **Research** — Collect DOJ/OIG source cases for the domain
2. **Extract** — Use Nova Pro to extract types, methods, signatures from cases
3. **Validate** — Confirm each signature against source prosecution (>80% confirmation)
4. **Embed** — Run Titan Embed on validated signatures, load to OpenSearch
5. **Graph** — Extract entities from cases, load to Neptune
6. **Build UI** — Create page following 3-part structure (Library + Cases + Deck)
7. **Register** — Add to master library sidebar + update this reference doc

**Time estimate:** 5-8 working days per new domain.

---

## Cross-References to Research Analyst

The Research Analyst project (`/.gitlab-hsi-push/research-analyst/`) uses the same:
- Neptune cluster (entity graph, case relationships)
- OpenSearch collection (vector search)
- Bedrock models (Titan Embed, Nova Pro)
- S3 data lake (same bucket, different prefixes)
- Aurora database (case management, user data)

The Pattern Library provides the **scoring backbone** that the Research Analyst's case processing pipeline uses to classify and score new intelligence.
