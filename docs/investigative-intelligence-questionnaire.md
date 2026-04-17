# Investigative Intelligence Platform — CIO Planning Call Questionnaire

**Purpose:** Scope a 500TB pilot for an AI-powered investigative intelligence platform using Neptune, OpenSearch, Aurora, Bedrock, and S3.
**Meeting Duration:** 1 hour | **Format:** Take notes directly in the Answer column

---

## 1. BUSINESS OBJECTIVES (10 min)

| # | Question | Answer |
|---|----------|--------|
| 1.1 | What is the primary mission outcome you want from this pilot? (e.g., faster case resolution, cross-case pattern detection, analyst productivity) | |
| 1.2 | Who are the end users? (investigators, analysts, prosecutors, leadership?) How many? | |
| 1.3 | What does success look like at the end of the pilot? What would make you say "let's go to production"? | |
| 1.4 | Is there a specific case or investigation type you want to pilot with first? | |
| 1.5 | What are the top 3 capabilities from the demo that matter most? (cross-case analysis, AI summaries, pattern discovery, entity graph, geospatial, other) | |
| 1.6 | Is there a timeline or event driving this? (budget cycle, leadership review, active investigation) | |

## 2. DATA LANDSCAPE (15 min)

| # | Question | Answer |
|---|----------|--------|
| 2.1 | Of the 500TB, what file types? (PDF, Word, Excel, images, email, structured DB exports, other) | |
| 2.2 | Are the PDFs machine-readable (text layer) or scanned images requiring OCR? Rough % split? | |
| 2.3 | Is the data already in S3 or does it need to be migrated? From where? | |
| 2.4 | Is there an existing hierarchy? (Matter → Case → Collection → Document, or flat files?) | |
| 2.5 | Are there existing metadata fields? (case ID, date, custodian, classification, sensitivity labels) | |
| 2.6 | What is the data sensitivity level? (CUI, classified, law enforcement sensitive, PII?) | |
| 2.7 | Is there existing entity data? (people, organizations, locations already tagged or in a database) | |
| 2.8 | How frequently does new data arrive? (batch daily, streaming, ad-hoc uploads) | |
| 2.9 | For the pilot, can we start with a representative subset? What size? (e.g., 1TB, 10TB, 50TB) | |

## 3. TECHNICAL ENVIRONMENT (10 min)

| # | Question | Answer |
|---|----------|--------|
| 3.1 | Is this GovCloud? Which region? Existing account or new? | |
| 3.2 | What AWS services are already in use? (S3, VPC, IAM, existing databases) | |
| 3.3 | Is there an existing VPC and networking setup we need to integrate with? | |
| 3.4 | Authentication requirements? (PIV/CAC, SAML/OIDC, Active Directory) | |
| 3.5 | Any FedRAMP, FISMA, or ATO requirements for the pilot? | |
| 3.6 | Are there data residency or encryption requirements beyond AWS defaults? | |

## 4. TEAM & IMPLEMENTATION (10 min)

| # | Question | Answer |
|---|----------|--------|
| 4.1 | Do you have a technical team to implement, or do you need ProServe / a partner? | |
| 4.2 | If internal team — how many engineers? Familiar with AWS? Python? Graph databases? | |
| 4.3 | Is there a preferred implementation model? (AWS builds it, your team builds with guidance, hybrid) | |
| 4.4 | Who is the technical decision maker and day-to-day point of contact? | |
| 4.5 | Are there existing tools this needs to integrate with? (case management system, BI tools, SIEM) | |

## 5. BUDGET & TIMELINE (10 min)

| # | Question | Answer |
|---|----------|--------|
| 5.1 | Confirmed ~$200K budget — is that combined ProServe + AWS service consumption? | |
| 5.2 | Is there flexibility if the pilot scope requires more? Or is $200K a hard cap? | |
| 5.3 | Desired pilot start date and duration? (e.g., 8 weeks, 12 weeks) | |
| 5.4 | When do you need a decision/readout to leadership? | |
| 5.5 | Is there a path to production funding if the pilot succeeds? Rough timeline? | |

## 6. DATA GOVERNANCE & ACCESS CONTROL (10 min)

| # | Question | Answer |
|---|----------|--------|
| 6.1 | How many distinct teams or task forces will use the platform simultaneously? (Single team vs. multiple teams with case isolation) | |
| 6.2 | Do teams need to be prevented from seeing each other's cases, or is cross-case visibility acceptable? | |
| 6.3 | What roles exist in your investigative workflow? (Lead Investigator, Analyst, Prosecutor, Read-Only Reviewer, Administrator, other) | |
| 6.4 | Does your agency use a formal classification hierarchy for evidence? (UNCLASSIFIED, CUI, SECRET, TOP SECRET, or custom) | |
| 6.5 | Can classification labels change over time? (e.g., evidence reclassified during investigation) | |
| 6.6 | Are there documents that specific individuals must never see, regardless of clearance level? (conflict-of-interest exclusions) | |
| 6.7 | What identity provider does your agency use? (AWS SSO, Okta, Azure AD, PIV/CAC via SAML, other) | |
| 6.8 | Do users authenticate with PIV/CAC smart cards? | |
| 6.9 | Is there an existing user directory to integrate with, or should the platform manage its own user registry? | |
| 6.10 | What audit retention requirements apply? (e.g., 7 years for federal records) | |
| 6.11 | Do you require audit logs to be tamper-evident? (signed, write-once storage) | |
| 6.12 | Are there specific NIST 800-53 controls that must be documented? | |
| 6.13 | What is the expected data retention period for ingested evidence? | |
| 6.14 | Is there a requirement to purge or redact data after a case is closed? | |
| 6.15 | Can AI-generated analysis (theories, case files, entity extractions) be deleted independently of source evidence? | |

## 7. SCOPE PRIORITIES (5 min)

**Rank these 1-5 for the pilot (1 = must have, 5 = nice to have):**

| Capability | Priority |
|------------|----------|
| Document ingestion & search (S3 → OpenSearch) | |
| Entity extraction & knowledge graph (Bedrock → Neptune) | |
| AI case summaries & briefings (Bedrock) | |
| Cross-case pattern analysis (Neptune + Bedrock) | |
| Geospatial evidence mapping | |
| User access control & multi-tenancy | |
| Custom loader aligned with future managed service | |

---

**Next Steps After This Call:**
- [ ] Compile answers into 2-page Project Statement
- [ ] Generate PoC Success Plan with timeline and evaluation criteria
- [ ] Schedule technical deep-dive with their engineering team
- [ ] Identify pilot dataset and begin data assessment
