# FATF Typology Reports — Manual Download Required

FATF's CDN blocks programmatic downloads. Download via browser from fatf-gafi.org.
Save to this folder (`docs/fatf/`).

## Priority 1: Most Relevant to Pattern Library

### Money Laundering Methods
- [ ] **Trade-Based Money Laundering** (2006, updated 2020)
  - URL: https://www.fatf-gafi.org/en/publications/Methodsandtrends/Trade-based-money-laundering.html
  - Save as: `FATF_Trade_Based_ML.pdf`
  - ~100 red flag indicators for trade-based laundering

### Virtual Assets
- [ ] **Virtual Assets Red Flag Indicators** (2020)
  - URL: https://www.fatf-gafi.org/en/publications/Methodsandtrends/Virtual-assets-red-flag-indicators.html
  - Save as: `FATF_Virtual_Assets_Red_Flags.pdf`
  - Key for crypto/fentanyl payment tracking

### Professional Money Laundering
- [ ] **Professional Money Laundering** (2018)
  - URL: https://www.fatf-gafi.org/en/publications/Methodsandtrends/Professional-money-laundering.html
  - Save as: `FATF_Professional_ML.pdf`
  - Lawyers, accountants, real estate agents as facilitators

### Terrorist Financing
- [ ] **Terrorist Financing Risk Assessment Guidance** (2019)
  - URL: https://www.fatf-gafi.org/en/publications/Methodsandtrends/Terrorist-Financing-Risk-Assessment-Guidance.html
  - Save as: `FATF_Terror_Financing_Guidance.pdf`

### Proliferation Financing
- [ ] **Proliferation Financing Report** (2021)
  - URL: https://www.fatf-gafi.org/en/publications/Methodsandtrends/Proliferation-Financing-Report.html
  - Save as: `FATF_Proliferation_Financing.pdf`
  - Sanctions evasion, WMD supply chain patterns

## Priority 2: Additional Reports

- [ ] **Money Laundering and Terrorist Financing Vulnerabilities of Legal Professionals** (2013)
- [ ] **Money Laundering through the Real Estate Sector** (2007)
- [ ] **Laundering the Proceeds of Corruption** (2011)
- [ ] **Money Laundering Risks from "Gatekeepers"** (2021)
- [ ] **Crowdfunding for Terrorism Financing** (2023)
- [ ] **Illicit Financial Flows from Cyber-Enabled Fraud** (2023)

## After Download

Run the ingestion pipeline:
```
python scripts/ingest_fincen_fatf.py --source fatf
```

## Expected Output

Each FATF report typically yields:
- 20-60 red flag indicators per report
- 5-15 typology methods per report
- Total expected: 200-400 new signatures from 6 priority reports

These get converted to:
1. Machine-readable detection signatures
2. Vector embeddings (Titan Embed v2)  
3. Loaded into OpenSearch `typology-patterns` index
4. Tagged with source provenance (e.g., "FATF-2020-VA-RED-FLAGS")
