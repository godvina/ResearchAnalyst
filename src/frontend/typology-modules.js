/**
 * Crime Typology Module Category Definitions
 * 
 * Contains category arrays for all 11 typology modules.
 * Loaded by typology-lens.js — each module has 6 categories with:
 *   id, icon, name, color, indicators, exampleText, stat
 */

// Drug Trafficking categories
const DRUG_TRAFFICKING_CATEGORIES = [
    {
        id: 'supply_chain',
        icon: '🚢',
        name: 'Supply Chain & Sourcing',
        color: '#9f7aea',
        indicators: 'Source country connections, precursor chemical procurement, bulk importation, cartel affiliations',
        exampleText: 'Subject A received 14 wire transfers totaling $2.3M from Sinaloa-linked accounts. Precursor chemical shipments from China traced to 3 clandestine labs. Typology flags: <em>source country nexus + precursor diversion + bulk importation</em>.',
        stat: 'Mexican cartels control 80% of US methamphetamine and fentanyl supply. DEA identifies 6 primary trafficking corridors. (DEA National Drug Threat Assessment, 2024)'
    },
    {
        id: 'distribution_network',
        icon: '🕸️',
        name: 'Distribution Network',
        color: '#b794f4',
        indicators: 'Cell structure, mid-level distributors, territory control, retail operations, customer base patterns',
        exampleText: 'Network analysis reveals 3-tier distribution: Subject A (wholesale) → 4 mid-level distributors → 22 retail dealers. Cell phone analysis shows strict hierarchical communication. Typology flags: <em>cell structure + territory markers + tiered distribution</em>.',
        stat: 'Average drug trafficking organization has 3.4 hierarchical levels. Mid-level distributors handle $50K-$500K/month in product. (HIDTA Annual Report, 2024)'
    },
    {
        id: 'stash_logistics',
        icon: '🏠',
        name: 'Stash Houses & Logistics',
        color: '#6b46c1',
        indicators: 'Residential stash houses, trap vehicles, counter-surveillance, load drivers, safe houses for couriers',
        exampleText: '3 rental properties in Subject A\'s girlfriend\'s name used as rotating stash locations. Lease payments in cash. Surveillance cameras installed facing street. Typology flags: <em>nominee property + cash lease + counter-surveillance</em>.',
        stat: '67% of stash houses are residential rentals in third-party names. Average stash house rotation: every 45 days. (DEA Domestic Operations, 2023)'
    },
    {
        id: 'drug_financial',
        icon: '💵',
        name: 'Drug Proceeds & Laundering',
        color: '#553c9a',
        indicators: 'Bulk cash movement, money service businesses, trade-based laundering, crypto conversion, funnel accounts',
        exampleText: 'Subject A shipped $4.2M in vacuum-sealed cash via commercial trucking to Laredo. Funds converted to pesos through Black Market Peso Exchange. Typology flags: <em>bulk cash smuggling + BMPE + commercial vehicle concealment</em>.',
        stat: 'Drug trafficking generates $64B annually in US proceeds. 90% of laundered drug money crosses the border as bulk cash. (ONDCP, 2024)'
    },
    {
        id: 'violence_enforcement',
        icon: '⚠️',
        name: 'Violence & Enforcement',
        color: '#e53e3e',
        indicators: 'Territorial disputes, debt collection violence, witness intimidation, retaliatory actions, firearms trafficking',
        exampleText: 'Subject A connected to 3 shootings near distribution points over 6 months. Victims were rival dealers or debtors. Firearms traced to straw purchases by associate. Typology flags: <em>territorial violence + debt enforcement + straw purchases</em>.',
        stat: '45% of homicides in major cities are drug-market related. Average DTO maintains 2.8 firearms per member. (FBI UCR + ATF Trace Data, 2023)'
    },
    {
        id: 'communication_opsec',
        icon: '📡',
        name: 'Communication & OPSEC',
        color: '#805ad5',
        indicators: 'Encrypted platforms, code words, burner rotation, counter-surveillance tradecraft, dead drops',
        exampleText: 'Subject A rotates Signal accounts weekly. Uses food-related code words for quantities (a "pizza" = 1 kilo). Changes phones every 14 days. Dead drop locations identified at 3 public parks. Typology flags: <em>encrypted comms + coded language + operational security</em>.',
        stat: '78% of DTOs now use end-to-end encrypted messaging. Average code word dictionary: 15-30 terms. Phone rotation average: 10-21 days. (DEA OCDETF, 2024)'
    }
];

// Money Laundering categories
const MONEY_LAUNDERING_CATEGORIES = [
    {
        id: 'placement',
        icon: '🏧',
        name: 'Placement',
        color: '#38b2ac',
        indicators: 'Structuring deposits, smurfing networks, cash-intensive businesses, funnel accounts, casino chips',
        exampleText: '23 individuals deposited $9,500 each across 8 banks on the same day. Total: $218K placed without CTR filings. All depositors linked to Subject A via phone records. Typology flags: <em>smurfing network + CTR avoidance + coordinated placement</em>.',
        stat: 'Structuring accounts for 31% of all BSA/AML enforcement actions. Average smurfing network uses 8-15 runners. (FinCEN Enforcement, 2024)'
    },
    {
        id: 'layering',
        icon: '🔄',
        name: 'Layering & Obfuscation',
        color: '#319795',
        indicators: 'Shell company chains, wire transfer cascades, trade-based laundering, crypto mixing, round-trip loans',
        exampleText: 'Funds moved through 7 shell companies across 4 jurisdictions (US→Panama→BVI→Cayman) in 48 hours. Each entity held funds <24hrs. Ultimate beneficial owner obscured. Typology flags: <em>shell chain + rapid transfers + jurisdiction hopping</em>.',
        stat: 'Average layering scheme uses 4.7 intermediary entities. Trade-based laundering accounts for $2T annually worldwide. (FATF Typology Report, 2024)'
    },
    {
        id: 'integration',
        icon: '🏢',
        name: 'Integration',
        color: '#2c7a7b',
        indicators: 'Real estate purchases, luxury assets, legitimate business investment, loan-back schemes, commingling',
        exampleText: 'Subject A purchased $12M in Miami real estate through 4 LLCs. Properties rented to generate "legitimate" income. Mortgage payments from offshore accounts. Typology flags: <em>real estate integration + LLC layering + offshore funding</em>.',
        stat: 'Real estate is used in 30% of money laundering cases. Miami, NYC, and LA are top integration markets. Average ML real estate transaction: $3.2M. (FinCEN GTO, 2024)'
    },
    {
        id: 'trade_based',
        icon: '📦',
        name: 'Trade-Based Laundering',
        color: '#285e61',
        indicators: 'Over/under-invoicing, phantom shipments, multiple invoicing, Black Market Peso Exchange',
        exampleText: 'Company A exported $500K in goods to Company B (same owner, different country) invoiced at $2.5M. $2M excess paid as "trade credit" — clean money enters US banking. Typology flags: <em>over-invoicing + related party trade + value transfer</em>.',
        stat: 'TBML represents 80% of illicit financial flows from developing countries. Over-invoicing detected in 12% of trade between high-risk corridors. (GFI, 2023)'
    },
    {
        id: 'crypto_laundering',
        icon: '₿',
        name: 'Cryptocurrency Laundering',
        color: '#4fd1c5',
        indicators: 'Mixing services, chain-hopping, privacy coins, unhosted wallets, DeFi protocols, P2P exchanges',
        exampleText: 'Subject A converted $3.4M BTC through 3 mixing services, then to Monero, then back to BTC at new addresses. Final conversion to USD via P2P exchange in UAE. Typology flags: <em>mixer usage + chain hopping + P2P off-ramp</em>.',
        stat: 'Crypto-related laundering reached $22.2B in 2023. Mixing services process $3B annually. DeFi protocols used in 17% of laundering cases. (Chainalysis, 2024)'
    },
    {
        id: 'professional_enablers',
        icon: '👔',
        name: 'Professional Enablers',
        color: '#234e52',
        indicators: 'Complicit attorneys, accountants, real estate agents, company formation agents, nominee directors',
        exampleText: 'Attorney X formed 47 shell companies for Subject A over 3 years. All registered to same office address. Attorney holds power of attorney over 12 accounts. Typology flags: <em>formation agent + nominee services + gatekeeper complicity</em>.',
        stat: '87% of complex ML schemes involve at least one professional enabler. Attorneys implicated in 34% of grand corruption cases. (FATF Gatekeeper Study, 2023)'
    }
];

// Cybercrime categories
const CYBERCRIME_CATEGORIES = [
    {
        id: 'ransomware',
        icon: '🔒',
        name: 'Ransomware Operations',
        color: '#4299e1',
        indicators: 'Initial access brokers, lateral movement, data exfiltration before encryption, cryptocurrency demands, RaaS affiliates',
        exampleText: 'Subject A purchased RDP access to 14 corporate networks via initial access broker. Deployed Lockbit 3.0 within 72hrs. Exfiltrated 2.3TB before encryption. Demanded $4.5M in BTC. Typology flags: <em>IAB purchase + pre-encryption exfil + RaaS deployment</em>.',
        stat: 'Ransomware payments exceeded $1.1B in 2023. Average dwell time before encryption: 5 days. 70% of attacks involve data exfiltration. (FBI IC3, 2024)'
    },
    {
        id: 'bec_fraud',
        icon: '📧',
        name: 'Business Email Compromise',
        color: '#3182ce',
        indicators: 'Domain spoofing, executive impersonation, vendor email compromise, payroll diversion, invoice manipulation',
        exampleText: 'Attacker compromised CFO email via credential phishing. Sent wire instruction change to AP team during CFO travel. $2.8M wired to Hong Kong account. Funds moved within 4 hours. Typology flags: <em>executive impersonation + travel timing + urgent wire request</em>.',
        stat: 'BEC losses exceeded $2.9B in 2023 (highest of any cybercrime). Average loss: $125K per incident. Recovery rate: only 29%. (FBI IC3, 2024)'
    },
    {
        id: 'credential_theft',
        icon: '🔑',
        name: 'Credential Theft & Access',
        color: '#2b6cb0',
        indicators: 'Phishing campaigns, credential stuffing, infostealers, MFA bypass, session hijacking, dark web sales',
        exampleText: 'Subject A operated infostealer infrastructure harvesting 2.3M credential pairs/month. Sold via Telegram channels at $10-50 per corporate login. Premium pricing for .gov and financial sector. Typology flags: <em>infostealer operation + credential marketplace + sector targeting</em>.',
        stat: 'Stolen credentials involved in 86% of breaches. Average credential marketplace lists 24M+ pairs. Corporate credentials sell for $10-$500 each. (Verizon DBIR, 2024)'
    },
    {
        id: 'data_exfil',
        icon: '📤',
        name: 'Data Exfiltration & Extortion',
        color: '#2a4365',
        indicators: 'Insider access abuse, cloud misconfiguration, API exploitation, double extortion, data broker sales',
        exampleText: 'Former employee used retained VPN access to exfiltrate 450K customer records over 3 weeks. Data posted on dark web forum with $500K extortion demand. Company PII sold separately for $0.50/record. Typology flags: <em>insider access + slow exfiltration + double monetization</em>.',
        stat: '83% of data breaches involve external actors. Insider threats take average 292 days to detect. Healthcare records sell for $250+ each on dark web. (IBM Cost of Breach, 2024)'
    },
    {
        id: 'infrastructure_attacks',
        icon: '🏗️',
        name: 'Critical Infrastructure',
        color: '#1a365d',
        indicators: 'ICS/SCADA targeting, supply chain compromise, state-sponsored APTs, zero-day exploitation, pre-positioning',
        exampleText: 'APT group maintained persistent access to water treatment SCADA for 14 months. Altered chemical dosing parameters within safe ranges as proof-of-capability. C2 infrastructure traced to state-affiliated IP ranges. Typology flags: <em>ICS access + living-off-the-land + state nexus</em>.',
        stat: 'Critical infrastructure attacks increased 140% in 2023. Average APT dwell time: 197 days. 62% of CI attacks attributed to state actors. (CISA, 2024)'
    },
    {
        id: 'crypto_crime',
        icon: '🪙',
        name: 'Cryptocurrency Crime',
        color: '#63b3ed',
        indicators: 'Exchange hacks, DeFi exploits, rug pulls, pig butchering, crypto jacking, bridge attacks',
        exampleText: 'Subject A operated 4 fraudulent DeFi protocols. Attracted $34M TVL through fake yield promises. Executed rug pull via admin key, draining all liquidity in 12 minutes. Funds bridged to Tornado Cash. Typology flags: <em>DeFi rug pull + admin key abuse + mixer obfuscation</em>.',
        stat: 'Crypto crime losses exceeded $24.2B in 2023. DeFi exploits: $1.7B stolen. Pig butchering scams: $3.3B in losses. (Chainalysis, 2024)'
    }
];

// Terrorism Financing categories
const TERRORISM_FINANCING_CATEGORIES = [
    {
        id: 'fundraising',
        icon: '🕌',
        name: 'Fundraising & Collection',
        color: '#dd6b20',
        indicators: 'Charity fronts, crowdfunding campaigns, zakat diversion, social media solicitation, diaspora networks',
        exampleText: 'Charity X collected $4.2M in donations. Only 12% reached stated humanitarian projects. $3.1M transferred to accounts in Turkey linked to designated entities. Board members connected to 3 FTO-affiliated organizations. Typology flags: <em>charity front + diversion + FTO nexus</em>.',
        stat: '23% of terrorism financing cases involve charity/NPO abuse. Average front charity diverts 60-80% of funds. (FATF NPO Study, 2024)'
    },
    {
        id: 'transfer_mechanisms',
        icon: '🌐',
        name: 'Transfer Mechanisms',
        color: '#c05621',
        indicators: 'Hawala/hundi networks, nested correspondents, cash couriers, crypto channels, trade-based value transfer',
        exampleText: 'Hawala network operating through 12 money service businesses across 5 states. Annual throughput: $23M. Terminal nodes in Pakistan, Somalia, Syria. No CTRs filed despite volume. Typology flags: <em>hawala network + high-risk corridors + reporting failure</em>.',
        stat: 'Hawala/informal value transfer moves estimated $400B annually. 78% of TF cases involve informal transfer systems. (World Bank/FATF, 2023)'
    },
    {
        id: 'material_support',
        icon: '🎯',
        name: 'Material Support (§ 2339)',
        color: '#9c4221',
        indicators: 'Equipment procurement, travel facilitation, training provision, personnel recruitment, expert services',
        exampleText: 'Subject A purchased $45K in communications equipment shipped to intermediary in Turkey. Also arranged travel for 3 individuals to conflict zone. Social media posts show FTO propaganda sharing. Typology flags: <em>equipment procurement + travel facilitation + propaganda support</em>.',
        stat: 'DOJ prosecuted 200+ material support cases since 2001. Average sentence: 13.5 years. 40% involve travel/attempt to join FTO. (DOJ NSD, 2024)'
    },
    {
        id: 'radicalization_pipeline',
        icon: '📱',
        name: 'Radicalization Pipeline',
        color: '#7b341e',
        indicators: 'Online recruitment, encrypted channels, escalation patterns, echo chambers, attack planning communications',
        exampleText: 'Subject A progressed from propaganda consumption to active recruitment over 8 months. Created 14 Telegram channels. Communicated with known IS virtual entrepreneur. Discussed specific targets in encrypted chats. Typology flags: <em>escalation pattern + virtual planner contact + target discussion</em>.',
        stat: 'Average online radicalization timeline: 6-18 months. 88% of recent lone-actor plots involved online radicalization. 62% used encrypted messaging. (GW Program on Extremism, 2024)'
    },
    {
        id: 'operational_planning',
        icon: '🗺️',
        name: 'Operational Planning',
        color: '#652b19',
        indicators: 'Surveillance of targets, weapons/materials procurement, communications security, timeline coordination',
        exampleText: 'Subject A conducted surveillance of 3 locations over 4 weeks. Purchased materials consistent with IED construction. Encrypted phone contained target photos with annotations. Travel pattern changed to avoid detection. Typology flags: <em>target surveillance + materials acquisition + operational security shift</em>.',
        stat: 'Average attack planning phase: 3-6 months. 80% of disrupted plots involved detectable pre-operational indicators. Surveillance is present in 92% of cases. (NCTC, 2024)'
    },
    {
        id: 'network_structure',
        icon: '🔗',
        name: 'Network Structure',
        color: '#ed8936',
        indicators: 'Cell-based organization, facilitation networks, command hierarchy, support nodes, lone-actor connections',
        exampleText: 'Network mapping reveals 4-cell structure with Subject A as coordinator. Cells operate independently with single point of contact. Support network of 12 facilitators providing logistics, finance, and documents. Typology flags: <em>cell structure + compartmentalization + facilitation ring</em>.',
        stat: 'Average disrupted network: 8.3 members across 2.1 cells. Facilitation networks average 3x the size of operational cells. (START, 2024)'
    }
];

// Public Corruption categories
const PUBLIC_CORRUPTION_CATEGORIES = [
    {
        id: 'bribery',
        icon: '💼',
        name: 'Bribery & Gratuities',
        color: '#718096',
        indicators: 'Cash payments, campaign contributions, gifts exceeding thresholds, quid pro quo arrangements, intermediary payments',
        exampleText: 'City council member received $180K in cash payments through intermediary LLC over 2 years. Payments correlated with 6 favorable zoning votes. LLC registered to campaign donor. Typology flags: <em>intermediary payment + quid pro quo + temporal correlation</em>.',
        stat: 'DOJ Public Integrity Section prosecutes 500+ officials annually. Average bribery scheme: $340K over 2.3 years. Conviction rate: 90%. (DOJ PIN, 2024)'
    },
    {
        id: 'extortion_hobbs',
        icon: '🔨',
        name: 'Extortion (Hobbs Act)',
        color: '#4a5568',
        indicators: 'Pay-to-play schemes, permit/license conditioning, protection rackets, regulatory threats, contract steering',
        exampleText: 'Building inspector demanded $5K per project from contractors for favorable inspections. 23 contractors paid over 18 months. Those who refused received "failed" inspections on compliant work. Typology flags: <em>systematic extortion + regulatory abuse + retaliatory enforcement</em>.',
        stat: 'Hobbs Act extortion under color of official right requires no explicit demand. 340+ federal convictions annually. Average scheme duration: 3.2 years. (USAO Statistics, 2024)'
    },
    {
        id: 'honest_services',
        icon: '⚖️',
        name: 'Honest Services Fraud',
        color: '#2d3748',
        indicators: 'Self-dealing, undisclosed conflicts, secret profits, fiduciary breaches, kickback schemes',
        exampleText: 'State procurement director steered $14M in IT contracts to firm owned by brother-in-law. Relationship undisclosed on ethics forms. Director received $200K in "consulting fees" from the firm. Typology flags: <em>self-dealing + undisclosed relationship + kickback</em>.',
        stat: 'Honest services fraud (18 USC § 1346) requires bribery or kickback after Skilling. 45% of public corruption cases include honest services charges. (USSC, 2024)'
    },
    {
        id: 'election_fraud',
        icon: '🗳️',
        name: 'Election & Campaign Fraud',
        color: '#a0aec0',
        indicators: 'Straw donors, foreign contributions, vote buying, campaign fund misuse, PAC coordination violations',
        exampleText: 'Campaign received $800K through 47 straw donors. All donors reimbursed by Subject A via cash payments. Foreign national provided $500K through US shell company. Typology flags: <em>straw donor scheme + foreign contribution + reimbursement pattern</em>.',
        stat: 'FEC referred 125 cases to DOJ in 2023. Average illegal contribution scheme: $450K. Foreign national contribution cases increased 60% since 2020. (FEC Enforcement, 2024)'
    },
    {
        id: 'obstruction_coverup',
        icon: '🚧',
        name: 'Obstruction & Cover-Up',
        color: '#e2e8f0',
        indicators: 'Document destruction, witness tampering, false statements, investigation interference, evidence spoliation',
        exampleText: 'After learning of FBI investigation, Subject A deleted 4,200 emails, instructed 3 subordinates to "forget" meetings, and filed amended financial disclosures backdated 6 months. Typology flags: <em>evidence destruction + witness coaching + document falsification</em>.',
        stat: 'Obstruction charges added in 34% of public corruption cases. Sentencing enhancement of 2-4 levels for obstruction. 92% conviction rate when charged. (USSC, 2024)'
    },
    {
        id: 'revolving_door',
        icon: '🚪',
        name: 'Revolving Door Abuse',
        color: '#cbd5e0',
        indicators: 'Post-employment violations, pre-arrangement of employment, regulatory capture, industry favoritism during tenure',
        exampleText: 'FDA official approved 3 drugs from PharmaCo during final year in office. Resigned and joined PharmaCo as VP within 60 days at $1.2M salary. Communications show job discussions during approval process. Typology flags: <em>pre-arranged employment + favorable official action + cooling period violation</em>.',
        stat: '18 USC § 207 violations carry 5-year max sentence. 28% of senior officials join regulated industries within 2 years. Average salary increase: 300%. (POGO, 2024)'
    }
];

// Organized Crime (RICO) categories
const ORGANIZED_CRIME_CATEGORIES = [
    {
        id: 'enterprise_structure',
        icon: '🏗️',
        name: 'Enterprise Structure',
        color: '#2d3748',
        indicators: 'Hierarchical leadership, defined roles, succession planning, territorial control, membership criteria',
        exampleText: 'Organization operates with clear boss → underboss → captain → soldier hierarchy. 47 identified members across 4 crews. Territory divided by geographic zone. Regular meetings at social club. Typology flags: <em>formal hierarchy + territorial division + organizational meetings</em>.',
        stat: 'RICO requires proof of enterprise with common purpose. Average convicted RICO enterprise: 12.4 members. DOJ secures 95%+ conviction rate on RICO charges. (DOJ OC Section, 2024)'
    },
    {
        id: 'predicate_acts',
        icon: '📜',
        name: 'Predicate Acts (Pattern)',
        color: '#4a5568',
        indicators: 'Two or more racketeering acts within 10 years, related conduct, continuity threat, diverse criminal activity',
        exampleText: 'Enterprise committed 14 predicate acts over 7 years: 4 extortions, 3 arsons, 2 drug distributions, 3 frauds, 2 witness tamperings. Pattern shows continuous, related criminal activity. Typology flags: <em>multiple predicates + temporal continuity + diverse crime types</em>.',
        stat: 'RICO requires 2+ predicate acts within 10 years showing pattern. Average successful RICO prosecution proves 8.3 predicate acts. Sentencing: 20 years per count. (USSC, 2024)'
    },
    {
        id: 'protection_rackets',
        icon: '🛡️',
        name: 'Protection & Extortion',
        color: '#1a202c',
        indicators: 'Regular tribute payments, territorial enforcement, legitimate business penetration, labor racketeering, no-show jobs',
        exampleText: '34 businesses in 8-block radius paying $500-$2,000 monthly "protection." Non-payers experienced vandalism within 72 hours. Subject A collects from 12 businesses personally. Typology flags: <em>systematic extortion + territorial coverage + enforcement violence</em>.',
        stat: 'Extortion remains primary income for traditional OC. Average protection scheme covers 20-50 businesses. Annual revenue per crew: $2-5M. (FBI OC Program, 2024)'
    },
    {
        id: 'infiltration_legitimate',
        icon: '🏪',
        name: 'Legitimate Business Infiltration',
        color: '#718096',
        indicators: 'Union control, construction industry dominance, waste hauling monopolies, market manipulation, bid rigging',
        exampleText: 'Enterprise controls 3 unions covering construction, waste hauling, and food distribution. All major contracts require enterprise approval. 12 legitimate companies are fronts. Annual legitimate revenue: $45M. Typology flags: <em>union control + industry dominance + front companies</em>.',
        stat: 'OC infiltrates $500B+ in legitimate industry annually. Construction, waste, and food distribution most targeted. Average bust recovers $12M in forfeiture. (DOJ OCRS, 2024)'
    },
    {
        id: 'money_operations',
        icon: '💰',
        name: 'Financial Operations',
        color: '#a0aec0',
        indicators: 'Loan sharking, illegal gambling, money laundering networks, cryptocurrency operations, investment fraud',
        exampleText: 'Enterprise operates illegal sports betting generating $8M/year. Profits laundered through 6 cash businesses (pizzerias, car washes). Loan sharking arm at 3-5 points/week to 200+ borrowers. Typology flags: <em>illegal gambling + cash business laundering + usury</em>.',
        stat: 'Illegal gambling generates $150B+ annually in US. Average loan shark charges 3-5% per week (156-260% APR). OC controls 70% of illegal gambling markets. (FBI, 2024)'
    },
    {
        id: 'violence_discipline',
        icon: '⚔️',
        name: 'Violence & Internal Discipline',
        color: '#e53e3e',
        indicators: 'Murders for organizational purposes, witness elimination, internal discipline, intimidation campaigns, crew conflicts',
        exampleText: 'Enterprise linked to 7 murders over 5 years: 3 internal discipline, 2 rival eliminations, 2 witness tampering. All unsolved. Bodies disposed at enterprise-controlled locations. Typology flags: <em>organizational murder + witness elimination + disposal infrastructure</em>.',
        stat: 'RICO murder predicates carry mandatory life sentence. Average OC family involved in 2-4 murders per decade. Witness elimination present in 23% of RICO cases. (DOJ, 2024)'
    }
];

// Child Exploitation (CSAM) categories
const CHILD_EXPLOITATION_CATEGORIES = [
    {
        id: 'production',
        icon: '🚨',
        name: 'Production & Contact Offenses',
        color: '#c53030',
        indicators: 'Access to minors, grooming patterns, image/video creation, coercion of victims, recording equipment',
        exampleText: 'Subject A (youth coach) groomed 4 minors over 18 months. Progression: trust-building → boundary testing → image solicitation → contact offense. Devices contain produced material. Typology flags: <em>positional access + grooming progression + production evidence</em>.',
        stat: 'Producers average 36 victims over their offending history. 70% hold positions of trust. Average production scheme: 2.4 years before detection. (NCMEC, 2024)'
    },
    {
        id: 'distribution',
        icon: '🌐',
        name: 'Distribution Networks',
        color: '#9b2c2c',
        indicators: 'Dark web forums, peer-to-peer sharing, Tor hidden services, file hosting abuse, trading communities',
        exampleText: 'Subject A moderated dark web forum with 4,200 members. Required upload of new material for membership. 340K files shared over 3 years. Server infrastructure across 4 countries. Typology flags: <em>forum administration + membership gates + international infrastructure</em>.',
        stat: 'NCMEC received 36M reports in 2023. Average CSAM forum: 1,200+ active members. Dark web accounts for 30% of distribution. (NCMEC/Europol, 2024)'
    },
    {
        id: 'sextortion',
        icon: '📱',
        name: 'Sextortion & Coercion',
        color: '#822727',
        indicators: 'Online solicitation, image coercion escalation, threats of exposure, financial demands, multiple victims',
        exampleText: 'Subject A targeted 23 minors via Instagram/Snapchat over 6 months. Pattern: catfish → image exchange → escalation demands → exposure threats. 8 victims paid $50-500 to prevent sharing. Typology flags: <em>platform targeting + coercion escalation + financial sextortion</em>.',
        stat: 'FBI reports 7,000+ sextortion complaints involving minors in 2023. Average offender targets 20+ victims. Financial sextortion increased 300% since 2022. (FBI IC3, 2024)'
    },
    {
        id: 'victim_identification',
        icon: '🔍',
        name: 'Victim Identification Intel',
        color: '#742a2a',
        indicators: 'Background forensics, metadata analysis, series identification, victim rescue indicators, situational indicators',
        exampleText: 'Analysis of 47 images identified consistent background elements: specific wallpaper pattern, electrical outlet type (UK BS 1363), and school uniform visible in 3 images. Cross-referenced with NCMEC hash database. Typology flags: <em>background correlation + geographic indicators + series linkage</em>.',
        stat: 'NCMEC identified 19,600 child victims in 2023. Background analysis successful in 34% of cases. Average series contains 47 images. Hash matching identifies 60%+ of known material. (NCMEC, 2024)'
    },
    {
        id: 'online_enticement',
        icon: '💬',
        name: 'Online Enticement',
        color: '#e53e3e',
        indicators: 'Age deception, platform migration, gift cards/payments to minors, travel planning, meetup arrangements',
        exampleText: 'Subject A (38) posed as 17-year-old on 4 platforms. Contacted 12 minors. Pattern: age deception → rapport building → platform migration to encrypted → meetup planning. Sent gift cards to 3 victims. Typology flags: <em>age deception + platform hopping + incentive payments + travel intent</em>.',
        stat: 'Online enticement reports increased 82% since 2019. 78% of offenders use age deception. Average: 3.2 platforms used per offender. 40% involve travel/meetup plans. (NCMEC, 2024)'
    },
    {
        id: 'commercial_exploitation',
        icon: '💸',
        name: 'Commercial Sexual Exploitation',
        color: '#fc8181',
        indicators: 'Third-party facilitation, advertising of minors, buyer networks, venue facilitation, profit from exploitation',
        exampleText: 'Subject A advertised 3 minors (ages 14-16) on escort platforms using misleading age descriptions. Collected $2,400-$3,800 per week per victim. Hotel bookings in victim names at 6 rotating locations. Typology flags: <em>minor advertising + profit collection + venue rotation + third-party facilitation</em>.',
        stat: 'Average age of commercially exploited minors: 15 years. Facilitators earn $150K-$300K annually per victim. 60% of cases cross state lines triggering federal jurisdiction. (DOJ, 2024)'
    }
];

// Sanctions Evasion categories
const SANCTIONS_EVASION_CATEGORIES = [
    {
        id: 'front_companies',
        icon: '🏢',
        name: 'Front Companies & Nominees',
        color: '#b83280',
        indicators: 'Shell companies in non-sanctioned jurisdictions, nominee directors, obscured beneficial ownership, corporate layering',
        exampleText: 'Sanctioned entity operates through 8 shell companies in UAE, Turkey, and Malaysia. All share same registered agent. Nominee directors are paid $500/month. True UBO obscured through 4 layers. Typology flags: <em>nominee structure + jurisdiction shopping + corporate layering</em>.',
        stat: 'OFAC designations increased 40% in 2023. Average evasion scheme uses 5.3 front companies across 3.2 jurisdictions. Penalties average $3.4M per violation. (OFAC, 2024)'
    },
    {
        id: 'transshipment',
        icon: '🚢',
        name: 'Transshipment & Diversion',
        color: '#97266d',
        indicators: 'Third-country routing, falsified end-user certificates, dual-use technology diversion, port-hopping, flag changes',
        exampleText: 'US-origin semiconductor chips sold to UAE distributor. Re-exported to shell company in Kyrgyzstan. Final delivery to sanctioned Russian defense entity. Falsified end-user certificates at each hop. Typology flags: <em>transshipment route + falsified EUC + dual-use diversion</em>.',
        stat: 'Technology diversion to Russia increased 300% through Central Asian corridors since 2022. 65% involves dual-use semiconductors. Average transshipment chain: 2.7 intermediary countries. (BIS, 2024)'
    },
    {
        id: 'financial_evasion',
        icon: '🏦',
        name: 'Financial Sanctions Evasion',
        color: '#702459',
        indicators: 'Correspondent banking abuse, U-turn transactions, payment stripping (cover payments), crypto circumvention',
        exampleText: 'Bank X processed $340M in transactions for sanctioned Iranian entities over 5 years. Wire messages stripped of originator information referencing Iran. Payments routed through nested correspondents in UAE. Typology flags: <em>payment stripping + nested correspondent + volume pattern</em>.',
        stat: 'Financial institutions paid $4.5B in sanctions penalties in 2023. Average payment stripping scheme: $200M+ over 3+ years. 89% involve correspondent banking. (OFAC/FinCEN, 2024)'
    },
    {
        id: 'maritime_evasion',
        icon: '⚓',
        name: 'Maritime & Shipping Evasion',
        color: '#d53f8c',
        indicators: 'AIS manipulation (dark ships), ship-to-ship transfers, flag hopping, document fraud, sanctions fleet identification',
        exampleText: 'Tanker disabled AIS transponder for 14 days during transit through sanctioned waters. Satellite imagery shows STS transfer to Iranian-flagged vessel. Previously flagged in Panama, reflagged to Cameroon. Typology flags: <em>AIS dark period + STS transfer + flag hopping</em>.',
        stat: 'Dark fleet of 600+ tankers carries sanctioned oil globally. AIS gaps average 11 days. STS transfers up 200% since 2022. Sanctioned oil shipped: 5M barrels/day. (S&P Global, 2024)'
    },
    {
        id: 'crypto_sanctions',
        icon: '🔐',
        name: 'Crypto Sanctions Circumvention',
        color: '#ed64a6',
        indicators: 'Sanctioned wallet interactions, mixer usage, DeFi protocol abuse, OTC desk transactions, cross-chain bridges',
        exampleText: 'North Korean APT converted $620M in stolen crypto through Tornado Cash. Funds split across 4,000+ addresses. Converted to BTC via DeFi protocols. Final off-ramp through Chinese OTC desks. Typology flags: <em>sanctioned mixer + address proliferation + OTC off-ramp</em>.',
        stat: 'Sanctioned entities received $14.9B in crypto in 2023. DPRK stole $1.7B via crypto hacks. OFAC sanctioned Tornado Cash (first DeFi protocol sanctioned). (Chainalysis, 2024)'
    },
    {
        id: 'trade_controls',
        icon: '📋',
        name: 'Export Control Violations',
        color: '#b83280',
        indicators: 'EAR violations, ITAR diversions, deemed exports, technology transfer to denied parties, academic espionage',
        exampleText: 'Professor X shared controlled aerospace research with visiting scholars from sanctioned country. No deemed export licenses obtained. Research has direct military application. University compliance unaware. Typology flags: <em>deemed export + military end-use + compliance bypass</em>.',
        stat: 'BIS opened 2,900+ investigations in 2023. Denial orders increased 75%. Average export control violation penalty: $1.2M. Academic/research sector: 18% of cases. (BIS Annual Report, 2024)'
    }
];

// Environmental Crime categories
const ENVIRONMENTAL_CRIME_CATEGORIES = [
    {
        id: 'illegal_dumping',
        icon: '🗑️',
        name: 'Illegal Dumping & Disposal',
        color: '#276749',
        indicators: 'Midnight dumping, falsified manifests, unlicensed disposal sites, waste broker fraud, RCRA violations',
        exampleText: 'Company X generated 4,500 tons of hazardous waste. Manifests show delivery to licensed facility, but GPS tracking of trucks shows 60% dumped at 3 illegal sites on company-owned rural property. Typology flags: <em>manifest fraud + unlicensed disposal + midnight dumping</em>.',
        stat: 'EPA criminal enforcement: 150+ cases annually. Average cleanup cost for illegal dump sites: $4.2M. Criminal penalties average $2.8M per case. (EPA CID, 2024)'
    },
    {
        id: 'emissions_fraud',
        icon: '🏭',
        name: 'Emissions & Discharge Fraud',
        color: '#2f855a',
        indicators: 'Falsified monitoring data, bypass of treatment systems, Clean Air/Water Act violations, defeat devices',
        exampleText: 'Plant X operated coal-fired boiler without required scrubbers for 3 years. Continuous emissions monitoring system tampered — reported values 70% below actual. 14,000 tons excess SO2 released. Typology flags: <em>monitoring fraud + treatment bypass + permit exceedance</em>.',
        stat: 'Clean Air Act criminal violations carry up to 5 years per day of violation. VW emissions scandal: $30B+ in penalties. Average CAA criminal fine: $4.5M. (EPA, 2024)'
    },
    {
        id: 'wildlife_trafficking',
        icon: '🐘',
        name: 'Wildlife Trafficking',
        color: '#38a169',
        indicators: 'CITES violations, poaching networks, transit routes, online sales platforms, document fraud',
        exampleText: 'Network shipped 2.3 tons of ivory from Tanzania through Vietnam to China. Used furniture shipments as cover. Customs documents listed "plastic ornaments." Connected to 4 poaching syndicates. Typology flags: <em>CITES violation + concealment method + transit routing + document fraud</em>.',
        stat: 'Wildlife trafficking: $23B annual market (4th largest criminal enterprise). 100 elephants killed daily for ivory. Lacey Act violations carry 5-year felony sentences. (USFWS, 2024)'
    },
    {
        id: 'water_contamination',
        icon: '💧',
        name: 'Water Contamination',
        color: '#319795',
        indicators: 'Unpermitted discharges, PFAS contamination, groundwater pollution, Safe Drinking Water Act violations',
        exampleText: 'Chemical plant discharged 2.4M gallons of PFAS-contaminated wastewater into tributary over 8 months. Internal memos show knowledge of contamination. Public water supply downstream serves 45,000 residents. Typology flags: <em>knowing discharge + PFAS contamination + public health threat + internal knowledge</em>.',
        stat: 'Clean Water Act criminal cases: 40+ annually. PFAS contamination affects 100M+ Americans. Average CWA criminal fine: $3.1M. Maximum: 6 years per violation. (EPA, 2024)'
    },
    {
        id: 'toxic_substances',
        icon: '☢️',
        name: 'Toxic Substances & Asbestos',
        color: '#e53e3e',
        indicators: 'Asbestos NESHAP violations, lead paint fraud, TSCA violations, worker exposure cover-ups, false certifications',
        exampleText: 'Demolition company removed asbestos from 23 buildings without proper containment. Workers given no PPE. Air monitoring results falsified. Waste disposed in construction dumpsters. Typology flags: <em>NESHAP violation + worker endangerment + monitoring fraud + improper disposal</em>.',
        stat: 'Asbestos-related deaths: 40,000 annually in US. Criminal NESHAP violations: 15-year max sentence. Average fine: $1.4M. Worker endangerment enhancement: +4 sentencing levels. (EPA/OSHA, 2024)'
    },
    {
        id: 'environmental_fraud',
        icon: '📊',
        name: 'Environmental Fraud & Schemes',
        color: '#68d391',
        indicators: 'Carbon credit fraud, renewable energy certificate fraud, brownfield/Superfund fraud, false compliance certifications',
        exampleText: 'Company X sold $45M in fraudulent carbon credits for non-existent forest preservation projects. Satellite imagery shows forests were never at risk. Certifying body received $2M in payments from company. Typology flags: <em>carbon credit fraud + phantom project + certifier corruption</em>.',
        stat: 'Carbon market fraud estimated at $1.5B annually. Renewable fuel credit fraud: $1B+ in DOJ recoveries. Average environmental fraud scheme: $12M. (DOJ ENRD, 2024)'
    }
];

// === MODULE CATEGORY LOOKUP ===
// Maps module ID to its category array for easy lookup
var MODULE_CATEGORIES_MAP = {
    sex_trafficking: null,  // Uses TYPOLOGY_CATEGORIES from typology-lens.js
    fraud_waste_abuse: FWA_CATEGORIES,
    drug_trafficking: DRUG_TRAFFICKING_CATEGORIES,
    money_laundering: MONEY_LAUNDERING_CATEGORIES,
    cybercrime: CYBERCRIME_CATEGORIES,
    terrorism_financing: TERRORISM_FINANCING_CATEGORIES,
    public_corruption: PUBLIC_CORRUPTION_CATEGORIES,
    organized_crime: ORGANIZED_CRIME_CATEGORIES,
    child_exploitation: CHILD_EXPLOITATION_CATEGORIES,
    sanctions_evasion: SANCTIONS_EVASION_CATEGORIES,
    environmental_crime: ENVIRONMENTAL_CRIME_CATEGORIES,
    ancient_mysteries: null  // Uses sub-module selector (6 theory classes)
};

/**
 * Get the category array for a given module ID.
 * Falls back to TYPOLOGY_CATEGORIES (sex trafficking) if module not found.
 */
function getModuleCategories(moduleId) {
    if (moduleId === 'sex_trafficking') {
        return (typeof TYPOLOGY_CATEGORIES !== 'undefined') ? TYPOLOGY_CATEGORIES : [];
    }
    if (moduleId === 'fraud_waste_abuse') {
        return (typeof FWA_CATEGORIES !== 'undefined') ? FWA_CATEGORIES : [];
    }
    if (moduleId === 'drug_trafficking') return DRUG_TRAFFICKING_CATEGORIES;
    if (moduleId === 'money_laundering') return MONEY_LAUNDERING_CATEGORIES;
    if (moduleId === 'cybercrime') return CYBERCRIME_CATEGORIES;
    if (moduleId === 'terrorism_financing') return TERRORISM_FINANCING_CATEGORIES;
    if (moduleId === 'public_corruption') return PUBLIC_CORRUPTION_CATEGORIES;
    if (moduleId === 'organized_crime') return ORGANIZED_CRIME_CATEGORIES;
    if (moduleId === 'child_exploitation') return CHILD_EXPLOITATION_CATEGORIES;
    if (moduleId === 'sanctions_evasion') return SANCTIONS_EVASION_CATEGORIES;
    if (moduleId === 'environmental_crime') return ENVIRONMENTAL_CRIME_CATEGORIES;
    if (moduleId === 'ancient_mysteries') return (typeof ANCIENT_MYSTERIES_CATEGORIES !== 'undefined') ? ANCIENT_MYSTERIES_CATEGORIES : [];
    return [];
}

// =============================================================================
// SOURCES & ATTRIBUTION — Crime Typology Frameworks
// =============================================================================
// The crime typology categories, indicators, and statistical references in this
// file are derived from the following authoritative sources:
//
// GENERAL FRAMEWORKS:
// - FATF (Financial Action Task Force) Typologies Reports (2020-2024)
//   https://www.fatf-gafi.org/en/topics/methodsandtrends.html
// - FBI Uniform Crime Reporting (UCR) Program & IC3 Annual Reports
//   https://www.fbi.gov/investigate
// - U.S. Sentencing Commission (USSC) Guidelines Manual & Annual Reports
//   https://www.ussc.gov/research/annual-reports-and-sourcebooks
//
// SEX TRAFFICKING:
// - DOJ National Human Trafficking Hotline Data (2023-2024)
// - Polaris Project Typology Framework (2017, updated 2024)
//   https://polarisproject.org/the-typology-of-modern-slavery/
// - 18 USC § 1591 — Sex Trafficking of Children or by Force, Fraud, or Coercion
// - USSC Trafficking Offense Guideline §2G1.1, §2G1.3
//
// FRAUD, WASTE & ABUSE:
// - ACFE (Association of Certified Fraud Examiners) Report to the Nations (2024)
//   https://www.acfe.com/report-to-the-nations/
// - GAO (Government Accountability Office) Improper Payments Reports
//   https://www.gao.gov/improper-payments
// - DOJ Civil Division, Anti-Kickback Act Enforcement (2023-2024)
//
// DRUG TRAFFICKING:
// - DEA National Drug Threat Assessment (2024)
//   https://www.dea.gov/documents/national-drug-threat-assessment
// - HIDTA (High Intensity Drug Trafficking Areas) Annual Reports
// - ONDCP (Office of National Drug Control Policy) Data
// - OCDETF (Organized Crime Drug Enforcement Task Forces) Case Analysis
//
// MONEY LAUNDERING:
// - FinCEN (Financial Crimes Enforcement Network) SAR Statistics & Advisories
//   https://www.fincen.gov/resources/advisories
// - FATF Money Laundering Typologies (2024)
// - Basel AML Index (2024) — https://index.baselgovernance.org/
// - Transparency International Corruption Perceptions Index
// - Chainalysis Crypto Crime Report (2024)
//   https://www.chainalysis.com/crypto-crime-report/
//
// CYBERCRIME:
// - FBI Internet Crime Complaint Center (IC3) Annual Report (2024)
//   https://www.ic3.gov/AnnualReport
// - Mandiant M-Trends Report (2024) — https://www.mandiant.com/m-trends
// - CrowdStrike Global Threat Report (2024)
// - IBM Cost of a Data Breach Report (2024)
// - MITRE ATT&CK Framework — https://attack.mitre.org/
// - Sophos State of Ransomware (2024)
//
// TERRORISM FINANCING:
// - FATF Terrorist Financing Typologies Report (2024)
// - DOJ National Security Division (NSD) Case Data
// - START (National Consortium for the Study of Terrorism) — https://www.start.umd.edu/
// - NCTC (National Counterterrorism Center) Assessments
// - GW Program on Extremism — https://extremism.gwu.edu/
// - 18 USC § 2339A/B — Material Support for Terrorism
//
// PUBLIC CORRUPTION:
// - DOJ Public Integrity Section (PIN) Annual Reports
//   https://www.justice.gov/criminal/criminal-pin
// - FBI Public Corruption Program Statistics
// - 18 USC § 1346 (Honest Services Fraud), § 1951 (Hobbs Act)
// - OGE (Office of Government Ethics) / CREW Analyses
// - FEC Enforcement Statistics
//
// ORGANIZED CRIME (RICO):
// - FBI Organized Crime Program — https://www.fbi.gov/investigate/organized-crime
// - 18 USC § 1962 (RICO Statute) & § 1959 (Violent Crimes in Aid of Racketeering)
// - DOJ Organized Crime Section Case Data
// - USSC RICO Sentencing Data (2024)
//
// CHILD EXPLOITATION (CSAM):
// - NCMEC (National Center for Missing & Exploited Children) Annual Reports
//   https://www.missingkids.org/theissues/csam
// - FBI ICAC (Internet Crimes Against Children) Task Force Data
// - 18 USC § 2251-2260A (Sexual Exploitation of Children)
// - DOJ CEOS (Child Exploitation and Obscenity Section)
// - Thorn Digital Defenders Report — https://www.thorn.org/
//
// SANCTIONS EVASION:
// - OFAC (Office of Foreign Assets Control) Enforcement Actions
//   https://ofac.treasury.gov/civil-penalties-and-enforcement-information
// - BIS (Bureau of Industry and Security) Denied Parties & Export Enforcement
// - UN Panel of Experts Reports (DPRK, Iran)
// - Chainalysis Sanctions Compliance Report (2024)
//
// ENVIRONMENTAL CRIME:
// - EPA Criminal Enforcement Division Annual Results
//   https://www.epa.gov/enforcement/criminal-enforcement
// - INTERPOL Environmental Crime Programme
// - UNODC Wildlife & Forest Crime Reports
// - TRAFFIC Wildlife Trade Monitoring — https://www.traffic.org/
// - GFI (Global Financial Integrity) Illegal Logging/Mining Reports
//
// STATISTICAL METHODOLOGY NOTE:
// Statistics cited in category cards are drawn from the most recent publicly
// available reports as of 2024. Some figures represent estimates or averages
// derived from case analysis rather than precise census data. Statistics are
// used for analyst context and should not be cited as evidence in legal filings.
//
// Last updated: June 2026
// Compiled for: Investigative Intelligence Platform — Crime Typology Module
// =============================================================================
