# FinCEN Advisories — Manual Download Required

These PDFs need to be downloaded via browser (FinCEN blocks programmatic access for some).
Save them to this folder (`docs/fincen/`).

## Priority 1: Already Downloaded ✅
- [x] FIN-2020-A006 — Ransomware (651KB)
- [x] FIN-2022-A002 — Elder Financial Exploitation (805KB)
- [x] FTA Identity-Related SAR 2024 (1128KB)

## Priority 2: Download These (Critical for Pattern Library)

### Fentanyl (CRITICAL — Finding Fentanyl crossover)
- [ ] **FIN-2024-A001** — Supplemental Advisory on Illicit Procurement of Fentanyl Precursor Chemicals
  - URL: https://www.fincen.gov/resources/advisoriesbulletinsfact-sheets/advisories
  - (Click "FIN-2024-A001" on the advisories page)
  - Save as: `FIN-2024-A001_Fentanyl_Precursors.pdf`

### Chinese Money Laundering Networks (HIGH — covers fentanyl financing)
- [ ] **FIN-2025-A001** — Advisory on Chinese Money Laundering Networks
  - URL: https://www.fincen.gov/news/news-releases/fincen-issues-advisory-and-financial-trend-analysis-chinese-money-laundering
  - Save as: `FIN-2025-A001_Chinese_ML_Networks.pdf`

### Iran Terrorism Financing (HIGH — Middle East succession planning crossover)
- [ ] **FIN-2024-A002** — Advisory to Counter the Financing of Iran-Backed Terrorist Organizations
  - Save as: `FIN-2024-A002_Iran_Terror_Financing.pdf`

### Human Trafficking (HIGH)
- [ ] **FIN-2020-A008** — Advisory on Human Trafficking
  - Save as: `FIN-2020-A008_Human_Trafficking.pdf`

### Drug Trafficking (HIGH — fentanyl financial patterns)
- [ ] **FIN-2019-A006** — Advisory on Fentanyl Trafficking Schemes (original 2019)
  - Save as: `FIN-2019-A006_Fentanyl_Original.pdf`

### Fentanyl Trend Analysis (HIGH)
- [ ] FinCEN Analysis of Fentanyl-Related Threat Patterns and Trends (April 2025)
  - URL: https://www.fincen.gov/resources/financial-trend-analyses
  - Save as: `FTA_Fentanyl_Trends_2025.pdf`

## Priority 3: Additional Advisories

- [ ] FIN-2021-A004 — Ransomware Updated (2021)
- [ ] FIN-2021-A001 — Environmental Crimes
- [ ] FIN-2020-A005 — COVID-19 Cybercrime/Fraud
- [ ] FIN-2020-A007 — Business Email Compromise
- [ ] FIN-2019-A003 — Corruption (Public/Private)
- [ ] FIN-2018-A005 — Casino/Gaming Red Flags

## After Download

Run the ingestion pipeline:
```
python scripts/ingest_fincen_fatf.py --source fincen
```
This will extract red flags/indicators from each PDF and convert them into pattern library signatures.
