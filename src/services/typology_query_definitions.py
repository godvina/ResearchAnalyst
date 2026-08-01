"""Typology query definitions — Neptune Gremlin templates for crime typology scoring.

This module defines the query templates and entity/relationship configurations
for all 11 crime typology modules (each with 6 sub-categories). These templates
are used by the typology scoring engine to extract relevant subgraphs from Neptune
for pattern detection and scoring.

Each query template uses a ``{label}`` placeholder for the per-case vertex label
(``Entity_{case_id}``), and applies ``.limit(5000)`` on edge traversals to bound
result sets for large cases.

This is configuration only — no runtime logic.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_ENTITY_THRESHOLD: int = 10_000
"""Entity count above which a case is considered 'large' and requires
pre-computation rather than real-time query execution."""

ALL_TYPOLOGY_MODULES: list[str] = [
    "sex_trafficking",
    "fraud_waste_abuse",
    "drug_trafficking",
    "money_laundering",
    "cybercrime",
    "terrorism_financing",
    "public_corruption",
    "organized_crime",
    "child_exploitation",
    "sanctions_evasion",
    "environmental_crime",
    "ancient_mysteries",
]
"""All 12 typology module identifiers (11 crime + 1 alternative history)."""


# ---------------------------------------------------------------------------
# Helper — query template builder
# ---------------------------------------------------------------------------

def _build_query_template(entity_types: list[str], relationship_types: list[str]) -> str:
    """Build a Gremlin query template with the given entity and relationship filters.

    The returned template contains a ``{label}`` placeholder for the case vertex label.
    Note: Uses the actual relationship types stored in Neptune (co-occurrence, thematic,
    causal, temporal, geographic) rather than domain-specific names. The entity_type
    filter provides the typology specificity.
    """
    entity_types_str = ", ".join(f"'{t}'" for t in entity_types)
    # Use broad relationship types that actually exist in Neptune
    # The entity_type filter provides typology-specific filtering
    return (
        "g.V().hasLabel('{label}')"
        f".has('entity_type', within({entity_types_str}))"
        ".bothE('RELATED_TO').limit(500)"
        ".project('src','tgt','type','weight')"
        ".by(outV().values('canonical_name'))"
        ".by(inV().values('canonical_name'))"
        ".by(coalesce(values('relationship_type'), constant('co-occurrence')))"
        ".by(coalesce(values('weight'), constant(1)))"
    )


# ---------------------------------------------------------------------------
# Sub-category definition helper
# ---------------------------------------------------------------------------

def _sub(
    entity_types: list[str],
    relationship_filter: list[str],
    indicators: list[str],
) -> dict:
    """Construct a sub-category definition dict."""
    return {
        "entity_types": entity_types,
        "relationship_filter": relationship_filter,
        "indicators": indicators,
        "query_template": _build_query_template(entity_types, relationship_filter),
    }


# ---------------------------------------------------------------------------
# TYPOLOGY_QUERIES — all 11 modules × 6 sub-categories
# ---------------------------------------------------------------------------

TYPOLOGY_QUERIES: dict[str, dict[str, dict]] = {

    # -----------------------------------------------------------------------
    # SEX TRAFFICKING
    # -----------------------------------------------------------------------
    "sex_trafficking": {
        "recruitment_grooming": _sub(
            entity_types=["person", "phone_number", "email", "location"],
            relationship_filter=[
                "contacted", "recruited", "communicated_with", "traveled_to",
            ],
            indicators=[
                "Age disparity in communication",
                "High-frequency contact with minor",
                "Gift or payment to recruit",
                "Social media grooming pattern",
            ],
        ),
        "transportation_movement": _sub(
            entity_types=["person", "location", "event", "date"],
            relationship_filter=[
                "traveled_to", "transported", "accompanied", "booked",
            ],
            indicators=[
                "Multi-city travel pattern",
                "One-way ticket purchases",
                "Cross-border movement",
                "Hotel booking clusters",
            ],
        ),
        "financial_control": _sub(
            entity_types=["person", "financial_amount", "account_number", "organization"],
            relationship_filter=[
                "paid", "received_funds", "controls_account", "deposited",
            ],
            indicators=[
                "Victim wages diverted to controller",
                "Structured deposits below reporting threshold",
                "Shared account access with controller",
                "Cash-intensive business fronts",
            ],
        ),
        "communication_networks": _sub(
            entity_types=["person", "phone_number", "email", "artifact"],
            relationship_filter=[
                "communicated_with", "messaged", "called", "shared_device",
            ],
            indicators=[
                "Burner phone rotation",
                "Encrypted messaging app usage",
                "Communication at unusual hours",
                "Network hub connecting victims",
            ],
        ),
        "venue_infrastructure": _sub(
            entity_types=["location", "organization", "person", "phone_number"],
            relationship_filter=[
                "operates_at", "owns", "manages", "advertised_at",
            ],
            indicators=[
                "Illicit massage businesses",
                "Residential brothel indicators",
                "Online advertisement patterns",
                "Hotel/motel recurring bookings",
            ],
        ),
        "power_control": _sub(
            entity_types=["person", "event", "artifact", "theme"],
            relationship_filter=[
                "controls", "threatens", "coerced", "isolated",
            ],
            indicators=[
                "Document confiscation",
                "Physical violence indicators",
                "Debt bondage mechanisms",
                "Isolation from support network",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # FRAUD, WASTE & ABUSE
    # -----------------------------------------------------------------------
    "fraud_waste_abuse": {
        "procurement_fraud": _sub(
            entity_types=["organization", "person", "financial_amount", "artifact"],
            relationship_filter=[
                "awarded_contract", "bid_on", "submitted", "approved",
            ],
            indicators=[
                "Sole-source awards to connected entities",
                "Bid rotation patterns",
                "Inflated pricing above market rate",
                "Artificial contract splitting",
            ],
        ),
        "billing_schemes": _sub(
            entity_types=["organization", "financial_amount", "person", "date"],
            relationship_filter=[
                "invoiced", "billed", "paid", "approved",
            ],
            indicators=[
                "Duplicate invoices",
                "Ghost vendor billing",
                "Services not rendered",
                "Billing above contracted rate",
            ],
        ),
        "conflict_of_interest": _sub(
            entity_types=["person", "organization", "financial_amount", "event"],
            relationship_filter=[
                "employed_by", "owns", "related_to", "awarded_contract",
            ],
            indicators=[
                "Decision-maker ownership in vendor",
                "Family relationship with contractor",
                "Undisclosed financial interest",
                "Revolving door employment",
            ],
        ),
        "grant_misuse": _sub(
            entity_types=["organization", "financial_amount", "person", "artifact"],
            relationship_filter=[
                "received_grant", "spent", "reported", "diverted",
            ],
            indicators=[
                "Funds used outside scope",
                "Fabricated progress reports",
                "Double-dipping across grants",
                "Personal use of grant funds",
            ],
        ),
        "kickback_schemes": _sub(
            entity_types=["person", "financial_amount", "organization", "account_number"],
            relationship_filter=[
                "paid", "received_funds", "referred", "approved",
            ],
            indicators=[
                "Payments timed to contract awards",
                "Percentage-based referral fees",
                "Shell company pass-throughs",
                "Luxury purchase correlation",
            ],
        ),
        "data_manipulation": _sub(
            entity_types=["person", "artifact", "event", "date"],
            relationship_filter=[
                "modified", "accessed", "deleted", "falsified",
            ],
            indicators=[
                "Backdated records",
                "After-hours system access",
                "Audit trail gaps",
                "Overridden system controls",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # DRUG TRAFFICKING
    # -----------------------------------------------------------------------
    "drug_trafficking": {
        "supply_chain": _sub(
            entity_types=["person", "organization", "location", "artifact"],
            relationship_filter=[
                "supplies", "sources_from", "manufactures", "imports",
            ],
            indicators=[
                "Precursor chemical purchases",
                "Known source-country connections",
                "Lab equipment acquisitions",
                "Bulk shipping anomalies",
            ],
        ),
        "distribution_network": _sub(
            entity_types=["person", "location", "phone_number", "organization"],
            relationship_filter=[
                "distributes_to", "delivers", "coordinates", "supplies",
            ],
            indicators=[
                "Hierarchical distribution structure",
                "Territory-based assignments",
                "High-frequency short-duration meetings",
                "Street-level dealer networks",
            ],
        ),
        "money_movement": _sub(
            entity_types=["person", "financial_amount", "account_number", "organization"],
            relationship_filter=[
                "paid", "transferred", "deposited", "structured",
            ],
            indicators=[
                "Structured cash deposits",
                "Money service business usage",
                "Bulk cash smuggling indicators",
                "Trade-based laundering",
            ],
        ),
        "communication_ops": _sub(
            entity_types=["person", "phone_number", "email", "artifact"],
            relationship_filter=[
                "communicated_with", "messaged", "called", "coded_language",
            ],
            indicators=[
                "Coded language usage",
                "Counter-surveillance behavior",
                "Encrypted app rotation",
                "Communication bursts before shipments",
            ],
        ),
        "stash_infrastructure": _sub(
            entity_types=["location", "person", "organization", "artifact"],
            relationship_filter=[
                "stored_at", "rented", "owns", "operates_at",
            ],
            indicators=[
                "Rental properties under aliases",
                "Storage unit clusters",
                "Trap house indicators",
                "Vehicle compartment modifications",
            ],
        ),
        "violence_enforcement": _sub(
            entity_types=["person", "event", "location", "artifact"],
            relationship_filter=[
                "threatened", "assaulted", "enforced", "intimidated",
            ],
            indicators=[
                "Debt collection violence",
                "Territorial enforcement acts",
                "Witness intimidation",
                "Weapons possession correlations",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # MONEY LAUNDERING
    # -----------------------------------------------------------------------
    "money_laundering": {
        "placement": _sub(
            entity_types=["person", "financial_amount", "account_number", "organization"],
            relationship_filter=[
                "deposited", "structured", "purchased", "exchanged",
            ],
            indicators=[
                "Structured deposits below reporting threshold",
                "Cash-intensive business deposits",
                "Smurfing across multiple accounts",
                "Currency exchange patterns",
            ],
        ),
        "layering": _sub(
            entity_types=["organization", "account_number", "financial_amount", "person"],
            relationship_filter=[
                "transferred", "wired", "converted", "routed_through",
            ],
            indicators=[
                "Rapid fund transfers between entities",
                "Shell company layering",
                "Jurisdictional hopping",
                "Nominee account usage",
            ],
        ),
        "integration": _sub(
            entity_types=["person", "organization", "financial_amount", "location"],
            relationship_filter=[
                "purchased", "invested", "acquired", "owns",
            ],
            indicators=[
                "Real estate purchases with laundered funds",
                "Luxury asset acquisition",
                "Business acquisition patterns",
                "Loan-back schemes",
            ],
        ),
        "trade_based": _sub(
            entity_types=["organization", "financial_amount", "artifact", "location"],
            relationship_filter=[
                "invoiced", "shipped", "traded", "over_valued",
            ],
            indicators=[
                "Over/under invoicing",
                "Phantom shipments",
                "Multiple invoicing for same goods",
                "Misrepresented goods or services",
            ],
        ),
        "crypto_channels": _sub(
            entity_types=["person", "account_number", "financial_amount", "artifact"],
            relationship_filter=[
                "transferred", "exchanged", "mixed", "converted",
            ],
            indicators=[
                "Mixer/tumbler usage",
                "Privacy coin conversions",
                "Peer-to-peer exchange patterns",
                "Unhosted wallet transfers",
            ],
        ),
        "shell_structures": _sub(
            entity_types=["organization", "person", "location", "account_number"],
            relationship_filter=[
                "owns", "directs", "registered_at", "controls",
            ],
            indicators=[
                "Layered corporate ownership",
                "Nominee directors",
                "Registered agent clustering",
                "Dormant company reactivation",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # CYBERCRIME
    # -----------------------------------------------------------------------
    "cybercrime": {
        "initial_access": _sub(
            entity_types=["person", "email", "artifact", "event"],
            relationship_filter=[
                "phished", "exploited", "compromised", "delivered",
            ],
            indicators=[
                "Phishing campaign indicators",
                "Credential harvesting",
                "Exploit kit deployment",
                "Watering hole attacks",
            ],
        ),
        "lateral_movement": _sub(
            entity_types=["artifact", "person", "event", "account_number"],
            relationship_filter=[
                "accessed", "escalated", "pivoted", "exploited",
            ],
            indicators=[
                "Privilege escalation events",
                "Pass-the-hash techniques",
                "Internal reconnaissance",
                "Service account abuse",
            ],
        ),
        "data_exfiltration": _sub(
            entity_types=["artifact", "person", "location", "event"],
            relationship_filter=[
                "exfiltrated", "transferred", "staged", "compressed",
            ],
            indicators=[
                "Large outbound data transfers",
                "Staging area detection",
                "DNS tunneling indicators",
                "Cloud storage exfil patterns",
            ],
        ),
        "financial_fraud": _sub(
            entity_types=["person", "financial_amount", "account_number", "email"],
            relationship_filter=[
                "transferred", "invoiced", "impersonated", "redirected",
            ],
            indicators=[
                "Business email compromise",
                "Wire transfer redirection",
                "Invoice manipulation",
                "Payroll diversion schemes",
            ],
        ),
        "infrastructure": _sub(
            entity_types=["artifact", "location", "organization", "account_number"],
            relationship_filter=[
                "hosted_on", "registered", "proxied_through", "operates",
            ],
            indicators=[
                "Bulletproof hosting usage",
                "Domain generation algorithms",
                "Fast-flux DNS patterns",
                "VPN/proxy infrastructure",
            ],
        ),
        "social_engineering": _sub(
            entity_types=["person", "email", "phone_number", "event"],
            relationship_filter=[
                "impersonated", "contacted", "deceived", "manipulated",
            ],
            indicators=[
                "Pretexting patterns",
                "Vishing campaigns",
                "Deepfake usage indicators",
                "Authority impersonation",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # TERRORISM FINANCING
    # -----------------------------------------------------------------------
    "terrorism_financing": {
        "fundraising": _sub(
            entity_types=["person", "organization", "financial_amount", "account_number"],
            relationship_filter=[
                "donated", "raised_funds", "collected", "solicited",
            ],
            indicators=[
                "Charity front fundraising",
                "Crowdfunding campaign abuse",
                "Diaspora community exploitation",
                "Social media fundraising",
            ],
        ),
        "transfer_channels": _sub(
            entity_types=["person", "financial_amount", "organization", "location"],
            relationship_filter=[
                "transferred", "hawala", "couriered", "wired",
            ],
            indicators=[
                "Hawala/informal value transfer",
                "Cash courier networks",
                "Nested correspondent banking",
                "Prepaid card loading patterns",
            ],
        ),
        "material_support": _sub(
            entity_types=["person", "organization", "artifact", "financial_amount"],
            relationship_filter=[
                "provided", "procured", "shipped", "facilitated",
            ],
            indicators=[
                "Dual-use equipment purchases",
                "Logistical support provision",
                "Safe house facilitation",
                "Travel facilitation for operatives",
            ],
        ),
        "recruitment_radicalization": _sub(
            entity_types=["person", "email", "phone_number", "event"],
            relationship_filter=[
                "recruited", "radicalized", "communicated_with", "influenced",
            ],
            indicators=[
                "Online radicalization patterns",
                "Recruiter-recruit communication chains",
                "Extremist content distribution",
                "Isolation from family/community",
            ],
        ),
        "operational_planning": _sub(
            entity_types=["person", "location", "event", "artifact"],
            relationship_filter=[
                "surveilled", "planned", "reconnoitered", "coordinated",
            ],
            indicators=[
                "Surveillance of targets",
                "Operational security behaviors",
                "Pre-attack logistics",
                "Test runs and rehearsals",
            ],
        ),
        "front_organizations": _sub(
            entity_types=["organization", "person", "financial_amount", "location"],
            relationship_filter=[
                "controls", "funds_through", "operates", "directs",
            ],
            indicators=[
                "NGO front operations",
                "Business front for fund movement",
                "Religious institution exploitation",
                "Parallel financial systems",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # PUBLIC CORRUPTION
    # -----------------------------------------------------------------------
    "public_corruption": {
        "bribery": _sub(
            entity_types=["person", "financial_amount", "organization", "event"],
            relationship_filter=[
                "paid", "gifted", "entertained", "received_benefit",
            ],
            indicators=[
                "Cash payments to officials",
                "Gifts exceeding thresholds",
                "Travel/entertainment for officials",
                "Quid pro quo timing patterns",
            ],
        ),
        "extortion": _sub(
            entity_types=["person", "event", "financial_amount", "artifact"],
            relationship_filter=[
                "threatened", "demanded", "coerced", "leveraged",
            ],
            indicators=[
                "Shakedown payment patterns",
                "Color-of-office threats",
                "Regulatory pressure as leverage",
                "Protection racket indicators",
            ],
        ),
        "embezzlement": _sub(
            entity_types=["person", "financial_amount", "account_number", "organization"],
            relationship_filter=[
                "diverted", "misappropriated", "transferred", "concealed",
            ],
            indicators=[
                "Fund diversion from public accounts",
                "Ghost employee schemes",
                "Unauthorized expenditures",
                "Personal use of public resources",
            ],
        ),
        "honest_services": _sub(
            entity_types=["person", "organization", "event", "financial_amount"],
            relationship_filter=[
                "failed_to_disclose", "self_dealt", "conflicted", "favored",
            ],
            indicators=[
                "Undisclosed conflicts of interest",
                "Self-dealing arrangements",
                "Favoritism in official acts",
                "Breach of fiduciary duty",
            ],
        ),
        "revolving_door": _sub(
            entity_types=["person", "organization", "event", "date"],
            relationship_filter=[
                "employed_by", "lobbied", "influenced", "contracted_with",
            ],
            indicators=[
                "Post-employment lobbying",
                "Cooling-off period violations",
                "Pre-arrangement employment promises",
                "Regulatory capture patterns",
            ],
        ),
        "obstruction": _sub(
            entity_types=["person", "event", "artifact", "date"],
            relationship_filter=[
                "obstructed", "destroyed", "concealed", "influenced_witness",
            ],
            indicators=[
                "Evidence destruction",
                "Witness tampering",
                "False statements to investigators",
                "Obstruction of audits",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # ORGANIZED CRIME
    # -----------------------------------------------------------------------
    "organized_crime": {
        "hierarchy_structure": _sub(
            entity_types=["person", "organization", "event", "theme"],
            relationship_filter=[
                "leads", "reports_to", "commands", "oversees",
            ],
            indicators=[
                "Boss-underboss-captain hierarchy",
                "Initiation/induction evidence",
                "Family/clan structure",
                "Oath and loyalty indicators",
            ],
        ),
        "predicate_acts": _sub(
            entity_types=["person", "event", "location", "financial_amount"],
            relationship_filter=[
                "committed", "participated_in", "planned", "facilitated",
            ],
            indicators=[
                "Pattern of racketeering activity",
                "Murder/assault for enterprise",
                "Extortion as enterprise method",
                "Narcotics trafficking predicate",
            ],
        ),
        "enterprise_operations": _sub(
            entity_types=["organization", "person", "financial_amount", "location"],
            relationship_filter=[
                "operates", "conducts", "manages", "profits_from",
            ],
            indicators=[
                "Ongoing criminal enterprise indicators",
                "Revenue generation schemes",
                "Legitimate business infiltration",
                "Union/labor racketeering",
            ],
        ),
        "territory_control": _sub(
            entity_types=["location", "person", "event", "organization"],
            relationship_filter=[
                "controls", "operates_in", "contested", "enforces",
            ],
            indicators=[
                "Geographic territory demarcation",
                "Inter-gang conflict zones",
                "Protection territory maps",
                "Market control indicators",
            ],
        ),
        "witness_intimidation": _sub(
            entity_types=["person", "event", "phone_number", "location"],
            relationship_filter=[
                "threatened", "intimidated", "surveilled", "contacted",
            ],
            indicators=[
                "Witness threat communications",
                "Surveillance of witnesses",
                "Retaliation patterns",
                "Jury tampering indicators",
            ],
        ),
        "money_operations": _sub(
            entity_types=["person", "financial_amount", "organization", "account_number"],
            relationship_filter=[
                "laundered", "collected", "invested", "structured",
            ],
            indicators=[
                "Enterprise fund collection",
                "Laundering through businesses",
                "Investment of criminal proceeds",
                "Cash-intensive business usage",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # CHILD EXPLOITATION
    # -----------------------------------------------------------------------
    "child_exploitation": {
        "production": _sub(
            entity_types=["person", "artifact", "location", "event"],
            relationship_filter=[
                "produced", "recorded", "photographed", "coerced",
            ],
            indicators=[
                "CSAM production indicators",
                "Victim identification markers",
                "Location metadata in material",
                "Series identification patterns",
            ],
        ),
        "distribution": _sub(
            entity_types=["person", "artifact", "email", "account_number"],
            relationship_filter=[
                "distributed", "shared", "uploaded", "traded",
            ],
            indicators=[
                "Peer-to-peer sharing networks",
                "Dark web forum participation",
                "Trading/exchange patterns",
                "Cloud storage distribution",
            ],
        ),
        "possession": _sub(
            entity_types=["person", "artifact", "event", "date"],
            relationship_filter=[
                "possessed", "downloaded", "stored", "accessed",
            ],
            indicators=[
                "Known hash matches",
                "Volume of material",
                "Organization/categorization behavior",
                "Escalation over time",
            ],
        ),
        "grooming_recruitment": _sub(
            entity_types=["person", "phone_number", "email", "event"],
            relationship_filter=[
                "groomed", "contacted", "gifted", "manipulated",
            ],
            indicators=[
                "Age-inappropriate communication",
                "Gift/reward patterns",
                "Trust-building progression",
                "Platform migration behavior",
            ],
        ),
        "commercial_exploitation": _sub(
            entity_types=["person", "financial_amount", "organization", "account_number"],
            relationship_filter=[
                "paid", "purchased", "advertised", "profited",
            ],
            indicators=[
                "Commercial CSAM sites",
                "Payment for access",
                "Subscription service patterns",
                "Cryptocurrency payment trails",
            ],
        ),
        "technology_facilitation": _sub(
            entity_types=["artifact", "person", "organization", "email"],
            relationship_filter=[
                "hosted", "encrypted", "anonymized", "facilitated",
            ],
            indicators=[
                "Anonymization tool usage",
                "Encrypted storage indicators",
                "Hosting infrastructure",
                "Evasion technology deployment",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # SANCTIONS EVASION
    # -----------------------------------------------------------------------
    "sanctions_evasion": {
        "front_companies": _sub(
            entity_types=["organization", "person", "location", "account_number"],
            relationship_filter=[
                "controls", "owns", "registered_at", "operates_through",
            ],
            indicators=[
                "Sanctioned entity ownership chains",
                "Newly formed entities in pattern",
                "Common address clustering",
                "Nominee shareholder usage",
            ],
        ),
        "transshipment": _sub(
            entity_types=["organization", "location", "artifact", "event"],
            relationship_filter=[
                "shipped_through", "transited", "relabeled", "diverted",
            ],
            indicators=[
                "Goods routed through third countries",
                "Port of origin misrepresentation",
                "Re-export without license",
                "Flagging vessel changes",
            ],
        ),
        "financial_circumvention": _sub(
            entity_types=["organization", "financial_amount", "account_number", "person"],
            relationship_filter=[
                "transferred", "converted", "structured", "routed_through",
            ],
            indicators=[
                "Correspondent bank exploitation",
                "Currency conversion to avoid controls",
                "Structured transactions below thresholds",
                "Alternative payment systems",
            ],
        ),
        "deceptive_practices": _sub(
            entity_types=["organization", "artifact", "person", "event"],
            relationship_filter=[
                "falsified", "misrepresented", "concealed", "altered",
            ],
            indicators=[
                "False end-user certificates",
                "Altered shipping documents",
                "Dual-use goods misclassification",
                "Identity document fraud",
            ],
        ),
        "technology_transfer": _sub(
            entity_types=["organization", "person", "artifact", "location"],
            relationship_filter=[
                "exported", "transferred", "shared", "collaborated",
            ],
            indicators=[
                "Controlled technology exports",
                "Academic/research collaboration cover",
                "Intangible technology transfer",
                "Deemed export violations",
            ],
        ),
        "diplomatic_channels": _sub(
            entity_types=["person", "organization", "location", "event"],
            relationship_filter=[
                "facilitated", "leveraged", "abused", "coordinated",
            ],
            indicators=[
                "Diplomatic pouch misuse",
                "Embassy-linked procurement",
                "Diplomatic immunity exploitation",
                "State-actor coordination",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # ENVIRONMENTAL CRIME
    # -----------------------------------------------------------------------
    "environmental_crime": {
        "illegal_dumping": _sub(
            entity_types=["organization", "location", "person", "event"],
            relationship_filter=[
                "dumped_at", "transported", "disposed", "contracted",
            ],
            indicators=[
                "Unauthorized disposal sites",
                "Midnight dumping patterns",
                "Waste manifest discrepancies",
                "Cost savings vs. legal disposal",
            ],
        ),
        "wildlife_trafficking": _sub(
            entity_types=["person", "organization", "location", "artifact"],
            relationship_filter=[
                "traded", "transported", "poached", "sold",
            ],
            indicators=[
                "CITES-listed species trafficking",
                "Smuggling route patterns",
                "Online marketplace sales",
                "Permit fraud for specimens",
            ],
        ),
        "emissions_fraud": _sub(
            entity_types=["organization", "artifact", "person", "date"],
            relationship_filter=[
                "falsified", "reported", "concealed", "manipulated",
            ],
            indicators=[
                "Defeat device usage",
                "Falsified monitoring data",
                "Credit trading fraud",
                "Unreported excess emissions",
            ],
        ),
        "water_contamination": _sub(
            entity_types=["organization", "location", "event", "person"],
            relationship_filter=[
                "discharged", "contaminated", "concealed", "violated",
            ],
            indicators=[
                "Unpermitted discharges",
                "Groundwater contamination",
                "Monitoring data falsification",
                "Pipe bypass indicators",
            ],
        ),
        "hazardous_materials": _sub(
            entity_types=["organization", "person", "location", "artifact"],
            relationship_filter=[
                "stored", "transported", "mishandled", "concealed",
            ],
            indicators=[
                "Improper storage of hazmat",
                "Unlicensed transport",
                "Missing manifests",
                "Worker exposure concealment",
            ],
        ),
        "permit_fraud": _sub(
            entity_types=["organization", "person", "artifact", "date"],
            relationship_filter=[
                "falsified", "submitted", "forged", "misrepresented",
            ],
            indicators=[
                "Falsified permit applications",
                "Forged compliance documents",
                "Inspector bribery",
                "Operating without required permits",
            ],
        ),
    },

    # -----------------------------------------------------------------------
    # ANCIENT MYSTERIES & ALTERNATIVE HISTORY
    # -----------------------------------------------------------------------
    "ancient_mysteries": {
        "advanced_ancient_technology": _sub(
            entity_types=["artifact", "location", "organization", "person", "event"],
            relationship_filter=[
                "constructed", "discovered", "measured", "analyzed", "located_at",
            ],
            indicators=[
                "Pyramid energy systems",
                "Precision machining evidence",
                "Ancient electrical artifacts",
                "Acoustic levitation traditions",
                "Ancient aviation descriptions",
                "Lost metallurgical knowledge",
                "Mercury reservoirs",
                "Piezoelectric construction",
            ],
        ),
        "global_grid_earth_energy": _sub(
            entity_types=["location", "artifact", "event", "theme"],
            relationship_filter=[
                "aligned_with", "connected_to", "located_at", "measured",
            ],
            indicators=[
                "Ley line alignment",
                "Earth energy vortex site",
                "Equidistant geodetic placement",
                "Geomagnetic construction",
                "Sacred geometry in positioning",
                "Great circle route",
            ],
        ),
        "lost_civilizations": _sub(
            entity_types=["location", "civilization", "event", "artifact", "date"],
            relationship_filter=[
                "predates", "constructed", "destroyed", "preserved", "discovered",
            ],
            indicators=[
                "Pre-cataclysm architecture",
                "Younger Dryas impact evidence",
                "Anomalous site dating",
                "Global flood narrative",
                "Knowledge preservation network",
                "Underwater megalithic structure",
            ],
        ),
        "extraterrestrial_contact": _sub(
            entity_types=["person", "artifact", "event", "vehicle", "civilization", "location"],
            relationship_filter=[
                "depicted", "described", "witnessed", "contacted", "created",
            ],
            indicators=[
                "Ancient astronaut depiction",
                "Impossible astronomical knowledge",
                "Genetic intervention evidence",
                "Sacred text contact report",
                "Star knowledge",
                "Non-human artifact",
            ],
        ),
        "sacred_geometry_mathematics": _sub(
            entity_types=["artifact", "location", "theme", "event"],
            relationship_filter=[
                "encoded", "measured", "constructed", "aligned_with",
            ],
            indicators=[
                "Mathematical constant encoding",
                "Precession cycle numbers in myth",
                "Universal measurement system",
                "Cymatics vibrational geometry",
                "Phi ratio in architecture",
            ],
        ),
        "consciousness_nonphysical": _sub(
            entity_types=["person", "artifact", "event", "theme", "location"],
            relationship_filter=[
                "practiced", "consumed", "experienced", "activated", "produced",
            ],
            indicators=[
                "Pineal gland third eye symbolism",
                "Psychedelic sacrament",
                "Sound frequency technology",
                "Crystal piezoelectric technology",
                "Altered consciousness state",
                "Mystery school tradition",
            ],
        ),
    },
}
# ---------------------------------------------------------------------------

TYPE_TO_TYPOLOGY: dict[str, list[str]] = {
    "person": ALL_TYPOLOGY_MODULES,  # persons are relevant to every module
    "organization": [
        "fraud_waste_abuse",
        "money_laundering",
        "terrorism_financing",
        "organized_crime",
        "sanctions_evasion",
        "environmental_crime",
        "drug_trafficking",
        "cybercrime",
        "child_exploitation",
    ],
    "location": [
        "sex_trafficking",
        "drug_trafficking",
        "organized_crime",
        "sanctions_evasion",
        "environmental_crime",
        "ancient_mysteries",
    ],
    "financial_amount": [
        "fraud_waste_abuse",
        "money_laundering",
        "terrorism_financing",
        "public_corruption",
        "organized_crime",
    ],
    "account_number": [
        "money_laundering",
        "fraud_waste_abuse",
        "terrorism_financing",
        "cybercrime",
        "sanctions_evasion",
    ],
    "phone_number": [
        "sex_trafficking",
        "drug_trafficking",
        "organized_crime",
        "child_exploitation",
    ],
    "email": [
        "cybercrime",
        "sex_trafficking",
        "child_exploitation",
        "terrorism_financing",
    ],
    "date": [
        "fraud_waste_abuse",
        "public_corruption",
        "environmental_crime",
    ],
    "event": [
        "public_corruption",
        "organized_crime",
        "terrorism_financing",
        "cybercrime",
        "drug_trafficking",
        "ancient_mysteries",
    ],
    "theme": [
        "sex_trafficking",
        "organized_crime",
        "terrorism_financing",
        "ancient_mysteries",
    ],
    "artifact": [
        "cybercrime",
        "child_exploitation",
        "sanctions_evasion",
        "environmental_crime",
        "drug_trafficking",
        "ancient_mysteries",
    ],
    "civilization": [
        "ancient_mysteries",
    ],
    "vehicle": [
        "drug_trafficking",
        "ancient_mysteries",
    ],
}
"""Maps each entity_type to the list of typology module IDs that should
be re-evaluated when an entity of that type is added or modified."""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_queries_for_module(typology_module_id: str) -> dict:
    """Return the sub-category query definitions for a given typology module.

    Args:
        typology_module_id: One of the IDs in ``ALL_TYPOLOGY_MODULES``.

    Returns:
        Dict keyed by sub_category_id, each containing entity_types,
        relationship_filter, indicators, and query_template.

    Raises:
        KeyError: If the module ID is not recognized.
    """
    if typology_module_id not in TYPOLOGY_QUERIES:
        raise KeyError(
            f"Unknown typology module: '{typology_module_id}'. "
            f"Valid modules: {ALL_TYPOLOGY_MODULES}"
        )
    return TYPOLOGY_QUERIES[typology_module_id]


def get_affected_typologies(entity_types: list[str]) -> set[str]:
    """Return which typology modules are affected by a set of entity types.

    Given a list of entity_type values (e.g., from newly ingested entities),
    returns the union of all typology modules that should be re-scored.

    Args:
        entity_types: List of entity_type strings (e.g., ['person', 'location']).

    Returns:
        Set of typology_module_id strings that are affected.
    """
    affected: set[str] = set()
    for et in entity_types:
        if et in TYPE_TO_TYPOLOGY:
            affected.update(TYPE_TO_TYPOLOGY[et])
    return affected
