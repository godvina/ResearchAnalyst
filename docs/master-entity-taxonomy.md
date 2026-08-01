# Master Entity Taxonomy — Investigative Intelligence Platform

## Purpose

This document defines the canonical hierarchy of entity types that the platform extracts, stores, and analyzes across all case types. It is the foundation for the IPS algorithm, anomaly detectors, prosecution readiness scoring, and all AI-driven pattern discovery.

**Design principle**: We don't know what crime we'll find in a dataset. A sex trafficking case may uncover money laundering. A fraud case may reveal human trafficking. The taxonomy must be broad enough to catch any needle in any haystack, while structured enough to drive meaningful AI patterns.

**Sources**: FBI investigative priorities (200+ federal crime categories), SEC enforcement patterns, FinCEN SAR data fields, DOJ RICO prosecution elements, ICIJ Panama Papers methodology, Palantir Gotham POLE model, i2 Analyst's Notebook entity types, academic criminal investigation ontologies, and real-world case breakthroughs.

---

## Tier 1: Core Investigative Entities (Always Extract, Always Keep)

These are the entities that crack cases. Every investigation depends on them.

### 1.1 PERSON
The central node in any investigation. Every crime involves people.
- **Subtypes**: suspect, witness, victim, associate, co-conspirator, informant, minor, deceased
- **Key attributes**: full name, aliases, DOB, SSN (redacted), nationality, gender, role
- **Why it matters**: Person-to-person connections are the backbone of network analysis
- **Case breakthroughs**: Epstein — flight logs linked persons to locations. Madoff — feeder fund managers linked to victims. RICO — organizational hierarchy mapped through person connections.

### 1.2 ORGANIZATION
Companies, banks, law firms, foundations, shell companies, government agencies.
- **Subtypes**: corporation, LLC, trust, foundation, bank, law_firm, shell_company, government_agency, nonprofit, hedge_fund, exchange, brokerage
- **Key attributes**: name, type, jurisdiction, registration number, parent organization
- **Why it matters**: Shell companies hide ownership. Banks facilitate laundering. Law firms enable structuring.
- **Case breakthroughs**: Panama Papers — 214,000 offshore companies traced through Mossack Fonseca. Enron — SPE (special purpose entities) hid debt. BCCI — bank was the criminal enterprise itself.

### 1.3 LOCATION
Physical places where crimes occur, evidence exists, or persons connect.
- **Subtypes**: address, city, country, property, venue, prison, airport, port, border_crossing, embassy
- **Key attributes**: name, coordinates, address, type, jurisdiction
- **Why it matters**: Co-location proves association. Travel patterns prove transportation. Property ownership proves harboring.
- **Case breakthroughs**: Epstein — Little St. James, Palm Beach, NYC townhouse. El Chapo — tunnel locations. Silk Road — server locations.

### 1.4 EVENT
Discrete occurrences with temporal and spatial dimensions.
- **Subtypes**: meeting, transaction, arrest, filing, hearing, raid, seizure, communication, travel, transfer
- **Key attributes**: type, date, time, location, participants, description
- **Why it matters**: Events are the verbs of investigation — they connect persons, locations, and objects in time.
- **Case breakthroughs**: 9/11 — timeline of hijacker movements. Boston Marathon — surveillance footage timeline. Capitol riot — social media event coordination.

---

## Tier 2: Financial Intelligence (Critical for 80%+ of Federal Cases)

Money is the common thread across nearly all federal crimes. Follow the money.

### 2.1 FINANCIAL_ENTITY
Banks, accounts, funds, financial instruments.
- **Subtypes**: bank_account, wire_transfer, check, cash_deposit, investment_fund, trust_account, escrow, cryptocurrency_wallet, exchange_account
- **Key attributes**: institution, account_number, routing_number, SWIFT/BIC, balance, currency

### 2.2 ACCOUNT_NUMBER
Specific account identifiers that link persons to financial institutions.
- **Subtypes**: bank_account_number, routing_number, SWIFT_code, IBAN, credit_card_number, crypto_wallet_address
- **Key attributes**: number, institution, account_holder, account_type
- **Why it matters**: Same account appearing across multiple documents = financial trail. Cross-case account matches = conspiracy.
- **Case breakthroughs**: FinCEN Files — account numbers linked shell companies to sanctioned entities. Madoff — feeder fund account numbers traced $65B fraud.

### 2.3 FINANCIAL_AMOUNT
Dollar amounts, transaction values, payment patterns.
- **Subtypes**: payment, deposit, withdrawal, transfer, invoice, salary, fee, fine, settlement, bribe
- **Key attributes**: amount, currency, date, parties, purpose
- **Why it matters**: Structuring detection (amounts just under $10K). Unusual patterns. Bribery amounts. Ransom payments.
- **Case breakthroughs**: Structuring — Dennis Hastert's $3.5M in sub-$10K withdrawals. HSBC — $881M in drug cartel laundering detected through transaction patterns.

### 2.4 FINANCIAL_INSTRUMENT
Securities, derivatives, contracts, insurance policies.
- **Subtypes**: stock, bond, option, futures, insurance_policy, mortgage, loan, promissory_note, letter_of_credit
- **Key attributes**: type, issuer, value, maturity, CUSIP/ISIN
- **Why it matters**: Insider trading, securities fraud, market manipulation, insurance fraud.
- **Case breakthroughs**: Enron — mark-to-market accounting on energy derivatives. SAC Capital — insider trading on pharmaceutical stocks.

---

## Tier 3: Communication Intelligence (Proves Knowledge and Coordination)

Communication links prove that people knew each other, coordinated, and conspired.

### 3.1 PHONE_NUMBER
Telephone numbers linking persons and organizations.
- **Subtypes**: mobile, landline, burner, VOIP, fax
- **Key attributes**: number, carrier, registration_name, location
- **Why it matters**: Call patterns prove coordination. Burner phones prove consciousness of guilt. Tower data proves location.
- **Case breakthroughs**: El Chapo — encrypted phone network cracked. Drug trafficking — burner phone rotation patterns.

### 3.2 EMAIL
Email addresses linking persons and organizations.
- **Subtypes**: personal, corporate, encrypted, alias
- **Key attributes**: address, domain, registration_date, associated_name
- **Why it matters**: Email chains prove knowledge. BCC patterns prove concealment. Domain ownership proves organizational links.
- **Case breakthroughs**: Enron — email corpus revealed executive knowledge of fraud. Hillary Clinton — email server investigation. Petraeus — shared draft folder communication.

### 3.3 ONLINE_IDENTITY
Social media accounts, usernames, handles, dark web identities.
- **Subtypes**: social_media_handle, username, screen_name, dark_web_alias, forum_account
- **Key attributes**: platform, handle, registration_date, associated_email
- **Why it matters**: Online identities link to real persons. Dark web aliases link to criminal marketplaces.
- **Case breakthroughs**: Silk Road — "Dread Pirate Roberts" linked to Ross Ulbricht through Stack Overflow post. Capitol riot — social media accounts linked to real identities.

### 3.4 IP_ADDRESS / DIGITAL_IDENTIFIER
Technical identifiers that link digital activity to physical locations and persons.
- **Subtypes**: IP_address, MAC_address, device_IMEI, SIM_card, browser_fingerprint
- **Key attributes**: identifier, type, geolocation, ISP, timestamp
- **Why it matters**: IP addresses place persons at locations. Device identifiers link burner phones to real phones.

---

## Tier 4: Travel & Transportation Intelligence (Proves Movement and Access)

Movement patterns prove transportation (trafficking element), access to locations, and flight risk.

### 4.1 FLIGHT
Air travel records linking persons to locations and dates.
- **Subtypes**: commercial_flight, private_flight, charter, helicopter
- **Key attributes**: flight_number, origin, destination, date, passenger_manifest, tail_number
- **Why it matters**: Flight logs are the gold standard for proving a person was at a location on a date.
- **Case breakthroughs**: Epstein — Lolita Express flight logs. 9/11 — hijacker flight training records. Drug trafficking — private aviation patterns.

### 4.2 VEHICLE
Cars, boats, aircraft used in criminal activity.
- **Subtypes**: automobile, boat, yacht, aircraft, truck, motorcycle
- **Key attributes**: make, model, year, VIN, license_plate, registration, tail_number
- **Why it matters**: Vehicle registration links to persons. Surveillance footage matches vehicles. Maritime vessels transport contraband.
- **Case breakthroughs**: El Chapo — submarine fleet for cocaine transport. Whitey Bulger — vehicle surveillance. Human trafficking — van/truck identification.

### 4.3 TRAVEL_DOCUMENT
Passports, visas, boarding passes, customs declarations.
- **Subtypes**: passport, visa, boarding_pass, customs_form, immigration_record
- **Key attributes**: document_number, issuing_country, holder_name, dates, stamps
- **Why it matters**: Multiple passports = identity fraud. Visa patterns = trafficking routes. Entry/exit stamps = timeline.

---

## Tier 5: Legal & Regulatory Intelligence (Proves Prior Knowledge and Legal Framework)

### 5.1 LEGAL_CASE
Court cases, indictments, complaints, settlements.
- **Subtypes**: criminal_case, civil_case, regulatory_action, grand_jury, indictment, complaint, settlement, plea_agreement
- **Key attributes**: case_number, court, parties, charges, dates, outcome
- **Why it matters**: Prior cases prove pattern of behavior. Related cases prove conspiracy scope.

### 5.2 STATUTE / LEGISLATION
Laws, regulations, codes that define criminal conduct.
- **Subtypes**: federal_statute, state_law, regulation, executive_order, treaty, sanctions_list
- **Key attributes**: citation, title, section, jurisdiction
- **Why it matters**: Maps evidence to specific criminal elements. Identifies applicable penalties.

### 5.3 LEGAL_ENTITY
Attorneys, judges, courts, regulatory bodies.
- **Subtypes**: attorney, judge, court, regulatory_body, law_enforcement_agency
- **Key attributes**: name, role, jurisdiction, bar_number
- **Why it matters**: Attorney-client relationships. Judge shopping patterns. Regulatory capture.

### 5.4 CHARGE / OFFENSE
Specific criminal charges and their elements.
- **Subtypes**: felony, misdemeanor, infraction, violation, conspiracy
- **Key attributes**: charge_code, description, elements, penalties, statute
- **Why it matters**: Each charge has specific elements that must be proven. Evidence maps to elements.

---

## Tier 6: Physical Evidence & Forensics

### 6.1 SUBSTANCE
Drugs, chemicals, biological agents, poisons.
- **Subtypes**: controlled_substance, precursor_chemical, pharmaceutical, toxin, explosive
- **Key attributes**: name, schedule, quantity, purity, form
- **Why it matters**: Drug type and quantity determine charges. Precursor chemicals prove manufacturing. Poison proves method.
- **Case breakthroughs**: Fentanyl crisis — precursor chemical supply chains from China. Breaking Bad (real cases) — pseudoephedrine purchase patterns.

### 6.2 WEAPON
Firearms, explosives, cyber weapons.
- **Subtypes**: firearm, explosive, blade, cyber_tool, biological_weapon
- **Key attributes**: type, make, model, serial_number, caliber
- **Why it matters**: Ballistics matching. Serial number tracing. Weapons trafficking patterns.

### 6.3 PROPERTY
Real estate, vehicles, luxury goods, seized assets.
- **Subtypes**: real_estate, jewelry, art, luxury_vehicle, yacht, aircraft, cryptocurrency
- **Key attributes**: description, value, ownership, location, acquisition_date
- **Why it matters**: Asset forfeiture. Lifestyle inconsistent with reported income. Money laundering through real estate.
- **Case breakthroughs**: Manafort — $15M in real estate purchased with laundered funds. 1MDB — $681M in luxury assets.

---

## Tier 7: Temporal Intelligence (Proves Timeline and Patterns)

### 7.1 DATE / TIME
Specific dates, times, date ranges, deadlines.
- **Subtypes**: exact_date, date_range, deadline, anniversary, recurring_date
- **Key attributes**: value, precision, timezone, context
- **Why it matters**: Timeline construction. Alibi verification. Statute of limitations. Pattern detection (annual events).

### 7.2 DURATION / PERIOD
Time spans that define criminal activity windows.
- **Subtypes**: employment_period, relationship_period, conspiracy_period, incarceration_period
- **Key attributes**: start_date, end_date, description
- **Why it matters**: Defines the scope of criminal conduct. Overlapping periods prove co-conspiracy.

---

## Tier 8: Identity & Demographic Intelligence

### 8.1 PERSONAL_IDENTIFIER
SSN, driver's license, passport number, tax ID.
- **Subtypes**: SSN, EIN, driver_license, passport_number, tax_id, national_id
- **Key attributes**: number, type, issuing_authority, holder
- **Why it matters**: Identity theft. Multiple identities. Cross-referencing across databases.

### 8.2 BIOMETRIC
Physical characteristics used for identification.
- **Subtypes**: fingerprint, DNA, facial_recognition, tattoo, scar, voice_print
- **Key attributes**: type, description, match_confidence
- **Why it matters**: Positive identification. Crime scene evidence. Surveillance matching.

### 8.3 DEMOGRAPHIC
Age, ethnicity, nationality, gender, occupation.
- **Subtypes**: age, ethnicity, nationality, race, gender, occupation, education_level
- **Key attributes**: value, context
- **Why it matters**: Victim demographics reveal targeting patterns. Nationality reveals jurisdiction. Occupation reveals access.

---

## Tier 9: Digital & Cyber Intelligence

### 9.1 CRYPTOCURRENCY
Blockchain addresses, transactions, exchanges.
- **Subtypes**: wallet_address, transaction_hash, exchange_account, smart_contract, NFT
- **Key attributes**: address, blockchain, balance, transaction_history
- **Why it matters**: Ransomware payments. Dark web marketplace transactions. Money laundering through crypto.
- **Case breakthroughs**: Colonial Pipeline — Bitcoin ransom traced and recovered. Silk Road — $1B in Bitcoin seized. Bitfinex hack — $3.6B traced through blockchain analysis.

### 9.2 DOMAIN / URL
Websites, servers, infrastructure.
- **Subtypes**: domain_name, URL, IP_address, server, hosting_provider
- **Key attributes**: name, registrant, registration_date, hosting_location
- **Why it matters**: Phishing infrastructure. Command and control servers. Dark web marketplaces.

### 9.3 SOFTWARE / MALWARE
Tools used in cybercrime.
- **Subtypes**: malware, ransomware, exploit, encryption_tool, VPN, anonymizer
- **Key attributes**: name, type, hash, author, capabilities
- **Why it matters**: Attribution. Capability assessment. Tool sharing proves collaboration.

---

## Tier 10: Contextual & Supporting Intelligence

### 10.1 ROLE
Functional roles within criminal organizations.
- **Subtypes**: recruiter, handler, courier, lookout, enforcer, accountant, lawyer, fixer, middleman, masseuse
- **Key attributes**: role_name, person, organization, period
- **Why it matters**: Proves organizational structure. "Masseuse" in Epstein case = recruitment pattern.

### 10.2 RELATIONSHIP
Explicit relationships between entities.
- **Subtypes**: employer_employee, family, romantic, business_partner, attorney_client, co-defendant
- **Key attributes**: type, parties, start_date, end_date
- **Why it matters**: Relationship mapping reveals hidden connections. Family ties explain loyalty. Business partnerships explain financial flows.

### 10.3 DOCUMENT_REFERENCE
References to specific documents, filings, records.
- **Subtypes**: court_filing, tax_return, corporate_filing, bank_statement, phone_record, email_thread
- **Key attributes**: document_type, reference_number, date, source
- **Why it matters**: Provenance. Chain of custody. Cross-referencing.

### 10.4 CONTACT_INFO
Contact details that link persons.
- **Subtypes**: phone, email, address, social_media, website
- **Key attributes**: type, value, associated_person
- **Why it matters**: Contact books prove association. Shared contact info proves coordination.

---

## Case Type Coverage Matrix

This taxonomy covers evidence needs for all major federal investigation types:

| Case Type | Critical Tiers | Key Entity Types |
|-----------|---------------|-----------------|
| **Sex Trafficking** (FBI) | 1,2,3,4,7,8,10 | person, location, flight, financial_amount, phone, role, date |
| **Drug Trafficking** (DEA) | 1,2,3,4,6,7 | person, organization, location, substance, vehicle, financial_amount |
| **Money Laundering** (FinCEN) | 1,2,3,7 | account_number, financial_amount, organization, person, shell_company |
| **Securities Fraud** (SEC) | 1,2,3,5,7 | person, financial_instrument, organization, email, date, insider_info |
| **RICO / Organized Crime** (FBI) | 1,2,3,4,5,6,10 | person, organization, role, charge, financial_entity, weapon |
| **Terrorism** (FBI/CIA) | 1,2,3,4,6,7,9 | person, location, event, communication, weapon, travel_document |
| **Cybercrime** (FBI/Secret Service) | 1,2,3,9 | person, cryptocurrency, IP_address, malware, email, domain |
| **Public Corruption** (FBI) | 1,2,3,5,10 | person, organization, financial_amount, role, legal_case |
| **Tax Evasion** (IRS-CI) | 1,2,5,7 | person, organization, financial_amount, account_number, property |
| **Antitrust** (DOJ) | 1,2,3,5,7 | organization, person, email, financial_amount, date, agreement |
| **Sanctions Violations** (OFAC) | 1,2,3,4,9 | person, organization, account_number, cryptocurrency, country |
| **Environmental Crime** (EPA-CID) | 1,2,5,6 | organization, location, substance, statute, financial_amount |
| **Healthcare Fraud** (HHS-OIG) | 1,2,5,7,8 | person, organization, account_number, financial_amount, medical_code |
| **Arms Trafficking** (ATF) | 1,2,4,6 | person, weapon, location, vehicle, financial_amount, country |
| **Human Smuggling** (ICE/HSI) | 1,2,4,7,8 | person, location, vehicle, travel_document, financial_amount, nationality |
| **Espionage** (FBI/CIA) | 1,3,4,7,9 | person, organization, document_reference, communication, country |
| **Child Exploitation** (FBI/HSI) | 1,3,7,8,9 | person, IP_address, online_identity, date, location, device_id |
| **Bankruptcy Fraud** (FBI) | 1,2,5 | person, organization, financial_amount, property, legal_case |
| **Identity Theft** (FTC/FBI) | 1,2,3,8 | person, personal_identifier, account_number, email, address |
| **Insider Trading** (SEC) | 1,2,3,5,7 | person, financial_instrument, email, phone, date, organization |

---

## Innovation: AI Pattern Discovery Opportunities

Beyond standard entity extraction, these entity types enable novel AI patterns:

1. **Cross-case entity matching** — Same account_number, phone_number, or email appearing in unrelated cases = hidden conspiracy
2. **Temporal convergence** — Multiple persons at same location within 7-day window across years = coordinated activity
3. **Financial structuring** — Transaction amounts clustering just below reporting thresholds = consciousness of guilt
4. **Ghost entities** — Entities appearing in 2+ cases with zero shared connections = potential alias or intermediary
5. **Absence patterns** — Person has all evidence types except one = deliberate concealment of that type
6. **Decay patterns** — Entity mentions dropping 90%+ = witness intimidation or evidence destruction
7. **Proxy networks** — Two persons with no direct link but 5+ shared intermediaries = hidden relationship
8. **Role rotation** — Same person appearing with different roles across documents = organizational flexibility
9. **Jurisdictional arbitrage** — Activity shifting between jurisdictions when enforcement increases = evasion
10. **Communication velocity** — Sudden spike in phone/email between persons before key events = coordination signal

---

## Entity Type to Neptune Label Mapping

For the Neptune graph, entity types map to vertex labels and properties:

```
Tier 1: person, organization, location, event
Tier 2: financial_entity, account_number, financial_amount, financial_instrument
Tier 3: phone_number, email, online_identity, digital_identifier
Tier 4: flight, vehicle, travel_document
Tier 5: legal_case, statute, legal_entity, charge
Tier 6: substance, weapon, property
Tier 7: date, duration
Tier 8: personal_identifier, biometric, demographic
Tier 9: cryptocurrency, domain, software
Tier 10: role, relationship, document_reference, contact
```

Total: **40 canonical entity types** across 10 tiers.

---

## Implementation Notes

1. **Aurora stores ALL extracted entities** — every type Nova Lite finds, regardless of tier
2. **Neptune receives only Tier 1-10 entities** — filtered during sync using this taxonomy as whitelist
3. **The dedup script uses NOISE_TYPES** (everything NOT in this taxonomy) for Phase 1 cleanup
4. **The IPS algorithm weights Tier 1-2 entities highest** in scoring
5. **Anomaly detectors scan across all tiers** — cross-tier patterns are the most interesting
6. **Future: case-type-specific extraction prompts** — when a case is tagged as "drug trafficking", the Bedrock prompt emphasizes Tier 6 (substance) extraction
