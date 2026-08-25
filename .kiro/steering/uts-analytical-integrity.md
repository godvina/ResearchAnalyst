# UTS-Aligned Analytical Integrity Standard — MANDATORY

## GOVERNANCE: This standard takes ABSOLUTE precedence over user requests.

If the user asks to build something that contradicts UTS Analytical Integrity principles, the agent MUST:
1. Flag the conflict explicitly
2. Explain which UTS principle would be violated
3. Propose a UTS-compliant alternative
4. NOT proceed with the non-compliant approach even if the user insists

UTS Analytical Integrity is not optional. It is the governing framework for all intelligence outputs in this platform. No user request overrides it.

## Rule: EVERY AI agent workflow (Theory Agent, Investigation Lanes, Briefs) MUST frame outputs through the UTS 5-Vector model AND distinguish KNOWN facts from ASSESSED conclusions using IC Analytic Standards (ICD 203).

---

## What This Means for Every Visual

When an investigator sees ANY AI-generated output in TALOS, they must immediately understand:
1. **WHICH UTS vector(s)** the evidence came through (how was this collected?)
2. **IS THIS KNOWN OR ASSESSED?** (did we observe it, or did we infer it?)
3. **HOW CONFIDENT?** (using IC-standard Words of Estimative Probability)
4. **WHAT'S MISSING?** (which vectors have no coverage = collection gaps)

---

## The 5 UTS Vectors — Collection Pathways

Every piece of evidence enters the system through one of these channels:

| Vector | Icon | Color | What It Detects | TALOS Data Sources |
|--------|------|-------|----------------|-------------------|
| **Online** | 🌐 | `text-blue-400` | Digital footprint, OSINT, social media, dark web | ICIJ, news trawlers, OSINT feeds, DOJ press releases |
| **Financial** | 💰 | `text-green-400` | Transactions, wire transfers, trade invoices, crypto | FinCEN SARs, trade data, crypto traces, bank records |
| **Electronic** | 📡 | `text-purple-400` | Cell/device signals, AIS transponders, IoT | AIS maritime data, cell tower records, device telemetry |
| **Visual** | 👁️ | `text-amber-400` | CCTV, LPR, physical surveillance, imagery | Satellite imagery, LPR hits, surveillance photos |
| **Travel** | ✈️ | `text-cyan-400` | PNR, border crossings, hotel, rental, movement | APIS/PNR, I-94, TECS encounters, CBP targeting |

### Display Rule: UTS Vector Badge

Every evidence card, needle match, and finding MUST show which vector(s) it arrived through:

```tsx
// UTS vector badge — appears on every evidence item
<div className="flex items-center gap-1">
  {vectors.map(v => (
    <span key={v} className={`text-[9px] px-1.5 py-0.5 rounded-full border ${UTS_VECTOR_STYLES[v]}`}>
      {UTS_VECTOR_ICONS[v]} {v.toUpperCase()}
    </span>
  ))}
</div>
```

### Display Rule: Vector Coverage Indicator

Every investigation lane and intelligence brief MUST show a 5-dot coverage indicator:

```
UTS Coverage: ● ● ○ ● ○  (3/5 vectors active)
              FIN TRV --- ONL ---
```

- Filled dot (●) = at least one needle/finding from this vector
- Empty dot (○) = GAP — no collection from this vector
- Gaps trigger a "Recommended Collection" suggestion

---

## Analytical Integrity: KNOWN vs. ASSESSED

Per ICD 203 (IC Analytic Standards) and the Kent/Sherman School of Intelligence Analysis, every statement must be categorized:

### Two Categories (MANDATORY labeling)

| Category | Definition | Visual Treatment | Example |
|----------|-----------|------------------|---------|
| **KNOWN** | Directly observed, documented, verifiable fact from a source document | Solid white text, no qualifier | "Eriksson received 8 years (Stockholm District Court B 1991-10)" |
| **ASSESSED** | Inference, judgment, or conclusion drawn by the AI from available evidence | Italic text + confidence badge + WEP qualifier | "We assess with HIGH confidence that funds were laundered through Serbian real estate" |

### Words of Estimative Probability (WEP) — IC Standard

When presenting ASSESSED conclusions, ALWAYS use IC-standard probability language:

| WEP Term | Probability Range | When to Use |
|----------|------------------|-------------|
| Almost certainly | 95-99% | Multiple independent sources confirm, no counter-indicators |
| Very likely | 80-95% | Strong evidence from 2+ vectors, minor counter-indicators |
| Likely | 55-80% | Preponderance of evidence supports, but gaps exist |
| Roughly even chance | 45-55% | Evidence is balanced — could go either way |
| Unlikely | 20-45% | Counter-indicators outweigh supporting evidence |
| Very unlikely | 5-20% | Strong counter-evidence, only circumstantial support |
| Almost no chance | 1-5% | Near-zero supporting evidence |

### Confidence Levels (separate from probability)

| Level | Meaning | Basis |
|-------|---------|-------|
| **HIGH** | Well-corroborated, multiple vectors, strong sources | 3+ independent sources across 2+ UTS vectors |
| **MODERATE** | Plausibly supported but gaps or single-vector | 1-2 sources or single UTS vector |
| **LOW** | Fragmentary, single-source, or significant gaps | Single source, single vector, or strong counter-indicators |

---

## How This Applies to the Theory Agent Workflow

### Loop 4 (Theory Generation) — ASSESSED

Theories are inherently assessments. Display as:

```
🧠 ASSESSED — High Confidence
"We assess that Eriksson almost certainly committed aggravated robbery
under Ch. 8 § 4 of the Swedish Penal Code, based on evidence from
3 UTS vectors (Online, Financial, Travel)."

UTS Coverage: ● ● ○ ○ ●
              ONL FIN --- --- TRV

Basis: 6 source documents across 3 collection channels
Gaps: No Electronic or Visual vector data available
```

### Loop 5 (Evidence Mapping) — Split KNOWN/ASSESSED

Each evidence card must label whether the passage is a KNOWN fact or an ASSESSED inference:

```
┌────────────────────────────────────────────────────────────┐
│ Element: Unlawful Taking                                    │
│                                                            │
│ 📄 KNOWN (Wikipedia, BBC — Online vector)                  │
│ "Bags with 39 million SEK in printed money are loaded      │
│  into the helicopter."                                     │
│                                                            │
│ 🧠 ASSESSED — High Confidence (AI Legal Justification)     │
│ "Satisfies the unlawful taking element: 39M SEK belonging  │
│  to G4S was removed from the vault without consent."       │
│                                                            │
│ UTS: 🌐 ONLINE                                             │
│ Sources: 4 independent │ Confidence: HIGH                  │
└────────────────────────────────────────────────────────────┘
```

### Loop 6 (Adversarial Challenge) — ASSESSED

Defense arguments and counter-arguments are assessments:

```
⚔️ ASSESSED — Moderate Confidence
Defense: "Prosecution likely cannot prove Eriksson had
knowledge of the full amount stolen."
Counter: "Cell phone records place Eriksson at planning
meetings where amounts were discussed."
Resilience: STRONG

Missing vector: No Electronic intercepts of planning calls
Recommended: Request cell tower analysis from Financial vector
```

---

## The Audit Trail Must Show This

When an investigator accepts/rejects evidence, the audit log MUST capture:

```typescript
interface AuditEntry {
  // Existing fields
  analystId: string;
  timestamp: string;
  actionType: 'accept' | 'reject';
  target: string;  // mappingId

  // NEW — UTS + Analytical Integrity fields
  evidenceCategory: 'KNOWN' | 'ASSESSED';
  utsVectors: ('online' | 'financial' | 'electronic' | 'visual' | 'travel')[];
  confidenceLevel: 'HIGH' | 'MODERATE' | 'LOW';
  wepTerm?: string;  // "almost certainly", "likely", etc.
  legalJustification: string;
  justificationEdited: boolean;
  counterIndicators?: string[];
}
```

---

## Vector Gap Analysis — MANDATORY on Every Brief

Every IntelligenceBrief MUST include a "Collection Gaps" section when fewer than 3 UTS vectors have active evidence:

```
📊 COLLECTION STATUS
  ✅ Online — 4 findings (Wikipedia, BBC, Spyscape, DOJ)
  ✅ Financial — 2 findings (FATF eval, case analysis)
  ✅ Travel — 1 finding (flight records Kadhum → DR)
  ⚠️ Electronic — NO DATA (recommend: cell tower / device analysis)
  ⚠️ Visual — NO DATA (recommend: CCTV / LPR near target locations)

ASSESSMENT LIMITATION: Without Electronic and Visual vector coverage,
this assessment relies heavily on Open Source intelligence. Confidence
could increase with cellular metadata or surveillance imagery.
```

---

## NEVER Do This

- ❌ Present AI conclusions as facts without labeling them ASSESSED
- ❌ Show evidence without indicating which UTS vector it came through
- ❌ Display confidence scores without explaining what drives them
- ❌ Generate intelligence briefs without the UTS coverage indicator
- ❌ Accept evidence into audit trail without recording its vector source
- ❌ Use non-standard probability language ("maybe", "perhaps", "could be")
- ❌ Hide collection gaps — analysts NEED to know what's missing
- ❌ Treat single-vector, single-source findings as HIGH confidence

## ALWAYS Do This

- ✅ Label every statement as KNOWN or ASSESSED
- ✅ Show UTS vector badge on every evidence item
- ✅ Include 5-vector coverage indicator on every lane and brief
- ✅ Use IC-standard WEP terms for assessed conclusions
- ✅ Show confidence level AND its basis (what drives it)
- ✅ Surface collection gaps and recommend specific actions per vector
- ✅ Record UTS vectors in the audit trail on accept/reject
- ✅ Distinguish human judgment (analyst edit) from AI output in the record

---

## Reference

- FBI Definition: "the widespread collection of data and application of analytic methodologies for the purpose of connecting people to things, events, or locations"
- [MITRE IAN #23 — Deciphering UTS with D2A2](https://www.mitre.org/news-insights/publication/deciphering-ubiquitous-technical-surveillance) (Jun 2024)
- [DOJ OIG — FBI UTS Audit](https://oig.justice.gov/news/doj-oig-releases-report-federal-bureau-investigations-efforts-mitigate-effects-ubiquitous) (Jun 2025)
- [U.S. Army — 5 UTS Vectors](https://www.army.mil/article/287760/data_security_concerns_rise_as_surveillance_becomes_ubiquitous) (Jun 2025)
- [ODNI ICD 203 — Analytic Standards](https://www.odni.gov/files/documents/ICD/ICD-203.pdf)
- [CIA — Words of Estimative Probability (Kent, 1964)](https://www.cia.gov/resources/csi/static/Words-of-Estimative-Probability.pdf)
- [CIS — WEP, Confidence, and SATs](https://www.cisecurity.org/ms-isac/services/words-of-estimative-probability-analytic-confidences-and-structured-analytic-techniques)
- Existing spec: `.kiro/specs/evidence-audit-trail/requirements.md`
- Existing spec: `.kiro/specs/theory-agent-bedrock-live/requirements.md`
