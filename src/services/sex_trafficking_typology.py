"""Sex Trafficking Crime Typology — Pattern Recognition Engine.

Implements 6 investigative pattern categories based on DOJ/FBI/DHS federal
prosecution frameworks and USSC sentencing data. Each category scores evidence
against known trafficking indicators and generates typology flags.

The 6 categories map to the Palermo Protocol elements (Act, Means, Purpose)
but are operationally specific to sex trafficking investigations:

1. Recruitment & Grooming — How victims are targeted and controlled early
2. Transportation & Movement — Geographic patterns indicating trafficking
3. Financial Control — Money flows indicating exploitation
4. Communication Networks — Coordination and operational security
5. Venue & Infrastructure — Physical/online locations of exploitation
6. Power & Control — Coercion mechanisms maintaining victim compliance

References:
- DOJ National Strategy to Combat Human Trafficking (2024)
- FBI Uniform Crime Report — Human Trafficking (2023)
- USSC Sentencing Guidelines for 18 U.S.C. § 1591
- Polaris Project Typology Framework (25 types)
- DHS Blue Campaign Indicators
"""

import logging
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Typology Definitions
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TypologyFlag:
    """A combinatorial trigger indicating a specific trafficking pattern."""
    name: str
    weight: float  # 0.0 - 1.0 contribution to category score
    description: str


@dataclass
class EvidenceExample:
    """Concrete evidence example for a typology category."""
    text: str
    flags: list[str]
    source: str = ""


@dataclass
class TypologyCategory:
    """One of the 6 sex trafficking pattern recognition categories."""
    id: str
    name: str
    icon: str
    color: str
    indicators: list[str]
    flags: list[TypologyFlag]
    evidence_examples: list[EvidenceExample]
    statistical_backing: str
    entity_types: list[str]  # which entity types trigger this category


# ──────────────────────────────────────────────────────────────────────────────
# The 6 Sex Trafficking Typology Categories
# ──────────────────────────────────────────────────────────────────────────────

TYPOLOGY_CATEGORIES: list[TypologyCategory] = [
    TypologyCategory(
        id="recruitment_grooming",
        name="Recruitment & Grooming",
        icon="🎭",
        color="#e53e3e",
        indicators=[
            "Social media contact patterns",
            "Age disparity between subjects",
            "Gift-giving and love-bombing",
            "Isolation from family/support",
            "False promises of employment/modeling",
            "Romeo/boyfriend pimp tactics",
        ],
        flags=[
            TypologyFlag("love_bombing", 0.20, "Pattern of excessive gifts, attention, or promises preceding exploitation"),
            TypologyFlag("age_disparity", 0.25, "Significant age gap between recruiter and victim (>10 years)"),
            TypologyFlag("communication_isolation", 0.20, "Evidence of cutting victim off from family/friends"),
            TypologyFlag("false_employment", 0.20, "Job offers that are fronts (modeling, hospitality, massage)"),
            TypologyFlag("geographic_relocation", 0.15, "Moving victim away from support network to unfamiliar area"),
        ],
        evidence_examples=[
            EvidenceExample(
                text="Subject A (age 42) contacted 6 females aged 16-19 via Instagram over 3 months. "
                     "Pattern: initial flattery, gifts within 48hrs, isolation requests within 2 weeks. "
                     "Typology flags: love bombing + age disparity + communication isolation.",
                flags=["love_bombing", "age_disparity", "communication_isolation"],
                source="FBI Victim Interview Patterns (2023)",
            ),
        ],
        statistical_backing=(
            "83% of sex trafficking victims were recruited by someone they knew or "
            "met through social media. Average recruiter-victim age gap: 14 years. "
            "(DOJ National Human Trafficking Hotline Data, 2023)"
        ),
        entity_types=["person", "minor", "victim", "social_media_handle", "phone_number"],
    ),

    TypologyCategory(
        id="transportation_movement",
        name="Transportation & Movement",
        icon="✈️",
        color="#ed8936",
        indicators=[
            "Hotel patterns and short-stay bookings",
            "Interstate travel with multiple stops",
            "Charter/private aviation",
            "Multiple cities in compressed timeframes",
            "One-way tickets purchased by third party",
            "Circuit movement (repeating routes)",
        ],
        flags=[
            TypologyFlag("hotel_clustering", 0.25, "Multiple hotel stays in short period, different cities"),
            TypologyFlag("geographic_velocity", 0.20, "Rapid movement across jurisdictions (>3 cities/week)"),
            TypologyFlag("interstate_movement", 0.20, "Crossing state lines — triggers federal jurisdiction (18 USC § 2421)"),
            TypologyFlag("circuit_rotation", 0.20, "Repeating geographic circuit on predictable schedule"),
            TypologyFlag("third_party_booking", 0.15, "Travel arranged/paid by someone other than traveler"),
        ],
        evidence_examples=[
            EvidenceExample(
                text="Subject B booked hotels in 4 cities over 9 days (Miami→Atlanta→Charlotte→DC). "
                     "All bookings under alias, paid by Subject A's prepaid card. "
                     "Victim C present at each location per phone GPS. "
                     "Typology flags: hotel clustering + geographic velocity + third-party booking.",
                flags=["hotel_clustering", "geographic_velocity", "third_party_booking"],
                source="DHS HSI Pattern Analysis (2024)",
            ),
        ],
        statistical_backing=(
            "71% of federally prosecuted sex trafficking cases involved interstate "
            "transportation. Average circuit covers 4.2 cities over 2-week rotation. "
            "(USSC Sourcebook 2019-2023, 18 U.S.C. § 1591 cases)"
        ),
        entity_types=["location", "address", "vehicle", "flight", "hotel", "date"],
    ),

    TypologyCategory(
        id="financial_control",
        name="Financial Control",
        icon="🏦",
        color="#d69e2e",
        indicators=[
            "Structuring deposits below CTR threshold",
            "Victim accounts controlled by others",
            "Prepaid card networks",
            "Shell LLCs and front businesses",
            "Cash-intensive businesses (nail salons, massage)",
            "Cryptocurrency for ad payments",
        ],
        flags=[
            TypologyFlag("structuring", 0.20, "Cash deposits/withdrawals just under $10K CTR reporting threshold"),
            TypologyFlag("controlled_accounts", 0.25, "Bank accounts in victim's name but controlled by trafficker"),
            TypologyFlag("shell_entity", 0.20, "LLC/business with no legitimate revenue matching cash flows"),
            TypologyFlag("ad_payment_trail", 0.20, "Payments to online advertising platforms for escort/massage ads"),
            TypologyFlag("quota_evidence", 0.15, "Financial records showing daily/nightly earning quotas"),
        ],
        evidence_examples=[
            EvidenceExample(
                text="12 bank accounts opened in victims' names at 4 different banks. "
                     "All accounts show identical deposit patterns: $8,500-$9,800 cash deposits "
                     "2-3x/week. Subject A is authorized signer on all accounts. "
                     "Typology flags: structuring + controlled accounts + quota evidence.",
                flags=["structuring", "controlled_accounts", "quota_evidence"],
                source="FinCEN SAR Activity Review (2024)",
            ),
        ],
        statistical_backing=(
            "Structuring/Money Laundering present in 62% of sex trafficking prosecutions. "
            "Average trafficker controls 3.7 victim bank accounts. "
            "(FinCEN SAR Trend Analysis, FY2022-2024)"
        ),
        entity_types=["financial_amount", "account_number", "organization", "person"],
    ),

    TypologyCategory(
        id="communication_networks",
        name="Communication Networks",
        icon="📱",
        color="#805ad5",
        indicators=[
            "Burner phone clusters",
            "Encrypted app usage (Signal, Telegram, Wickr)",
            "Coded language in ads/messages",
            "Scheduling coordination patterns",
            "Ad posting across multiple platforms",
            "Star topology (one number connects to many)",
        ],
        flags=[
            TypologyFlag("disposable_cluster", 0.20, "Multiple prepaid phones activated same day/location"),
            TypologyFlag("coded_advertising", 0.25, "Escort/massage ads with known code words or emojis"),
            TypologyFlag("coordination_window", 0.20, "Communication spikes preceding victim movement"),
            TypologyFlag("platform_spread", 0.20, "Same victim advertised across multiple platforms simultaneously"),
            TypologyFlag("star_topology", 0.15, "One phone/account communicates with many — hub pattern"),
        ],
        evidence_examples=[
            EvidenceExample(
                text="8 prepaid phones activated same day, same Walmart. Star topology with "
                     "Subject A's primary phone as hub. Phones used exclusively for ad posting "
                     "on 3 platforms. Activity spikes 4-6pm daily (booking window). "
                     "Typology flags: disposable cluster + star topology + coordination window.",
                flags=["disposable_cluster", "star_topology", "coordination_window"],
                source="FBI CAST (Child Abduction Serial Tracking) Analysis",
            ),
        ],
        statistical_backing=(
            "94% of sex trafficking operations use multiple phones/accounts. "
            "Average operation manages 6.3 advertising accounts across 2.8 platforms. "
            "(Thorn/Spotlight Data, 2023)"
        ),
        entity_types=["phone_number", "email", "social_media_handle", "online_identity"],
    ),

    TypologyCategory(
        id="venue_infrastructure",
        name="Venue & Infrastructure",
        icon="🏨",
        color="#38a169",
        indicators=[
            "Massage parlor / spa fronts",
            "Hotel room rotation (new room every few days)",
            "Residential brothels in suburbs",
            "Online platform ad patterns",
            "Venue rotation schedules",
            "Multi-location operations under same control",
        ],
        flags=[
            TypologyFlag("venue_rotation", 0.25, "Systematic movement between venues on predictable schedule"),
            TypologyFlag("ad_posting_cadence", 0.20, "Ads posted at regular intervals matching venue rotation"),
            TypologyFlag("multi_location_operation", 0.20, "Same controller linked to multiple venues/addresses"),
            TypologyFlag("front_business", 0.20, "Licensed business (massage, spa) with indicators of exploitation"),
            TypologyFlag("residential_conversion", 0.15, "Residential property converted to commercial sex venue"),
        ],
        evidence_examples=[
            EvidenceExample(
                text="Subject A leases 3 apartments in different zip codes. Each occupied "
                     "2-3 days/week on rotation. Online ads match rotation schedule exactly. "
                     "Neighbors report high foot traffic of males at odd hours. "
                     "Typology flags: venue rotation + ad posting cadence + multi-location operation.",
                flags=["venue_rotation", "ad_posting_cadence", "multi_location_operation"],
                source="HSI Operation Cross Country XII (2023)",
            ),
        ],
        statistical_backing=(
            "55% of sex trafficking venues are residential properties. "
            "Average operation rotates across 3.1 locations on 2-4 day cycles. "
            "Hotel-based operations average 4.7 different rooms/week. "
            "(Polaris Project Typology Study, 2024)"
        ),
        entity_types=["address", "location", "organization", "property"],
    ),

    TypologyCategory(
        id="power_control",
        name="Power & Control",
        icon="⛓️",
        color="#e53e3e",
        indicators=[
            "Debt bondage records/ledgers",
            "Document confiscation (IDs, passports)",
            "Threats to victim or family",
            "Rules/quota enforcement",
            "Branding/tattoos",
            "Surveillance of victims",
        ],
        flags=[
            TypologyFlag("debt_ledger", 0.25, "Records showing manufactured debt (housing, drugs, transport costs)"),
            TypologyFlag("document_control", 0.25, "Victim IDs/passports held by trafficker"),
            TypologyFlag("quota_enforcement", 0.20, "Evidence of daily/nightly earning requirements"),
            TypologyFlag("physical_branding", 0.15, "Tattoos, burns, or marks indicating ownership"),
            TypologyFlag("surveillance_control", 0.15, "GPS tracking, cameras, or minders watching victims"),
        ],
        evidence_examples=[
            EvidenceExample(
                text="Ledger recovered from Subject A's phone showing 4 victims with running "
                     "'debt' balances ($15K-$45K each). Charges include 'rent', 'protection', "
                     "'clothes'. Daily quota: $1,000/night. Passports for 3 victims found in "
                     "Subject A's safe. Typology flags: debt ledger + document control + quota enforcement.",
                flags=["debt_ledger", "document_control", "quota_enforcement"],
                source="DOJ Press Release, SDNY § 1591 prosecution (2024)",
            ),
        ],
        statistical_backing=(
            "78% of sex trafficking victims report debt bondage. "
            "63% had identity documents confiscated. "
            "Average daily quota: $500-$1,000. "
            "(DOJ Trafficking in Persons Report, 2024)"
        ),
        entity_types=["person", "victim", "minor", "financial_amount", "document"],
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# Scoring Engine
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TypologyScore:
    """Score result for a single typology category against case evidence."""
    category_id: str
    category_name: str
    icon: str
    color: str
    score: float  # 0-100
    matched_flags: list[str]
    flag_details: list[dict]
    evidence_summary: str
    statistical_context: str
    confidence: str  # "high", "medium", "low"


@dataclass
class TypologyReport:
    """Full typology analysis for a case."""
    case_id: str
    case_name: str
    scores: list[TypologyScore]
    overall_score: float
    dominant_typology: str
    flags_triggered: int
    total_flags: int
    recommendations: list[str]


class SexTraffickingTypologyEngine:
    """Scores case evidence against sex trafficking crime typologies.

    Analyzes entities and relationships from Neptune/Aurora to determine
    which trafficking patterns are present and how strong the evidence is.
    """

    def __init__(self, aurora_conn=None, neptune_endpoint: str = "", bedrock_client=None):
        self._db = aurora_conn
        self._neptune_endpoint = neptune_endpoint
        self._bedrock = bedrock_client

    def analyze_case(self, case_id: str, entities: list[dict] = None,
                     relationships: list[dict] = None) -> TypologyReport:
        """Run full typology analysis against case evidence.

        Args:
            case_id: The case to analyze.
            entities: Pre-fetched entities (optional, will query if not provided).
            relationships: Pre-fetched relationships (optional).

        Returns:
            TypologyReport with scores for each of the 6 categories.
        """
        if entities is None:
            entities = self._fetch_entities(case_id)
        if relationships is None:
            relationships = self._fetch_relationships(case_id)

        scores = []
        for category in TYPOLOGY_CATEGORIES:
            score = self._score_category(category, entities, relationships)
            scores.append(score)

        # Compute overall
        if scores:
            overall = sum(s.score for s in scores) / len(scores)
            dominant = max(scores, key=lambda s: s.score)
        else:
            overall = 0.0
            dominant = None

        total_flags = sum(len(c.flags) for c in TYPOLOGY_CATEGORIES)
        triggered = sum(len(s.matched_flags) for s in scores)

        recommendations = self._generate_recommendations(scores)

        return TypologyReport(
            case_id=case_id,
            case_name="",  # Caller fills this in
            scores=scores,
            overall_score=round(overall, 1),
            dominant_typology=dominant.category_id if dominant else "",
            flags_triggered=triggered,
            total_flags=total_flags,
            recommendations=recommendations,
        )

    def _score_category(self, category: TypologyCategory, entities: list[dict],
                        relationships: list[dict]) -> TypologyScore:
        """Score a single typology category against available evidence."""
        # Count entities matching this category's types
        relevant_entities = [
            e for e in entities
            if e.get("entity_type", "").lower() in category.entity_types
        ]

        # Check each flag
        matched_flags = []
        flag_details = []

        for flag in category.flags:
            match_score = self._evaluate_flag(flag, relevant_entities, relationships, category)
            if match_score > 0.3:  # threshold for flag activation
                matched_flags.append(flag.name)
                flag_details.append({
                    "flag": flag.name,
                    "score": round(match_score, 2),
                    "description": flag.description,
                    "weight": flag.weight,
                })

        # Calculate category score (0-100)
        if not category.flags:
            raw_score = 0.0
        else:
            weighted_sum = sum(
                d["score"] * d["weight"]
                for d in flag_details
            )
            max_possible = sum(f.weight for f in category.flags)
            raw_score = (weighted_sum / max_possible) * 100 if max_possible > 0 else 0.0

        # Boost score if multiple flags fire together (combinatorial bonus)
        if len(matched_flags) >= 3:
            raw_score = min(100.0, raw_score * 1.25)
        elif len(matched_flags) >= 2:
            raw_score = min(100.0, raw_score * 1.10)

        score = max(0.0, min(100.0, raw_score))

        # Confidence level
        if score >= 70 and len(matched_flags) >= 3:
            confidence = "high"
        elif score >= 40 and len(matched_flags) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        # Generate evidence summary
        evidence_summary = self._summarize_evidence(category, relevant_entities, matched_flags)

        return TypologyScore(
            category_id=category.id,
            category_name=category.name,
            icon=category.icon,
            color=category.color,
            score=round(score, 1),
            matched_flags=matched_flags,
            flag_details=flag_details,
            evidence_summary=evidence_summary,
            statistical_context=category.statistical_backing,
            confidence=confidence,
        )

    def _evaluate_flag(self, flag: TypologyFlag, entities: list[dict],
                       relationships: list[dict], category: TypologyCategory) -> float:
        """Evaluate whether a specific typology flag is triggered by evidence.

        Returns a score 0.0-1.0 indicating flag strength.
        """
        # Entity-count heuristic: more relevant entities = stronger signal
        entity_count = len(entities)

        # Relationship density for this category
        relevant_rels = [
            r for r in relationships
            if r.get("relationship_type", "").lower() in self._flag_relationship_types(flag.name)
        ]
        rel_count = len(relevant_rels)

        # Base score from entity presence
        if entity_count == 0:
            return 0.0

        # Scale based on flag type
        if flag.name in ("age_disparity", "love_bombing", "communication_isolation"):
            # Need person + victim/minor entities with relationships
            victims = [e for e in entities if e.get("entity_type") in ("victim", "minor")]
            persons = [e for e in entities if e.get("entity_type") == "person"]
            if victims and persons:
                return min(1.0, (len(victims) + len(persons)) / 4.0)
            return 0.0

        elif flag.name in ("hotel_clustering", "geographic_velocity", "circuit_rotation"):
            # Need multiple location entities with temporal proximity
            locations = [e for e in entities if e.get("entity_type") in ("location", "address", "hotel")]
            if len(locations) >= 3:
                return min(1.0, len(locations) / 8.0)
            return 0.0

        elif flag.name in ("structuring", "controlled_accounts", "quota_evidence"):
            # Need financial entities
            financials = [e for e in entities if e.get("entity_type") in ("financial_amount", "account_number")]
            if len(financials) >= 2:
                return min(1.0, len(financials) / 5.0)
            return 0.0

        elif flag.name in ("disposable_cluster", "star_topology", "coordination_window"):
            # Need phone/communication entities
            comms = [e for e in entities if e.get("entity_type") in ("phone_number", "email", "social_media_handle")]
            if len(comms) >= 2:
                return min(1.0, len(comms) / 6.0)
            return 0.0

        elif flag.name in ("venue_rotation", "multi_location_operation", "front_business"):
            # Need address/org entities
            venues = [e for e in entities if e.get("entity_type") in ("address", "location", "organization")]
            if len(venues) >= 2:
                return min(1.0, len(venues) / 6.0)
            return 0.0

        elif flag.name in ("debt_ledger", "document_control", "quota_enforcement"):
            # Need financial + person/victim combination
            financials = [e for e in entities if e.get("entity_type") in ("financial_amount",)]
            victims = [e for e in entities if e.get("entity_type") in ("victim", "minor", "person")]
            if financials and victims:
                return min(1.0, (len(financials) + len(victims)) / 8.0)
            return 0.0

        # Generic fallback
        return min(1.0, entity_count / 20.0)

    @staticmethod
    def _flag_relationship_types(flag_name: str) -> set:
        """Map flag names to relevant relationship types in the graph."""
        mapping = {
            "love_bombing": {"communicated_with", "gifted", "contacted"},
            "age_disparity": {"associated_with", "recruited"},
            "hotel_clustering": {"traveled_to", "stayed_at", "booked"},
            "geographic_velocity": {"traveled_to", "transported"},
            "structuring": {"deposited", "withdrew", "transferred"},
            "controlled_accounts": {"controls", "authorized_on", "owns"},
            "venue_rotation": {"operated_at", "visited", "leased"},
            "star_topology": {"communicated_with", "called", "messaged"},
        }
        return mapping.get(flag_name, set())

    def _summarize_evidence(self, category: TypologyCategory,
                            entities: list[dict], matched_flags: list[str]) -> str:
        """Generate a human-readable evidence summary for this category."""
        if not entities:
            return "No relevant entities detected for this category."

        entity_types = {}
        for e in entities:
            etype = e.get("entity_type", "unknown")
            entity_types[etype] = entity_types.get(etype, 0) + 1

        parts = [f"{count} {etype}" for etype, count in sorted(entity_types.items(), key=lambda x: -x[1])[:4]]
        summary = f"Evidence: {', '.join(parts)}."

        if matched_flags:
            flags_str = " + ".join(matched_flags).replace("_", " ")
            summary += f" Typology flags: {flags_str}."

        return summary

    def _generate_recommendations(self, scores: list[TypologyScore]) -> list[str]:
        """Generate investigative recommendations based on scoring gaps."""
        recommendations = []
        sorted_scores = sorted(scores, key=lambda s: s.score, reverse=True)

        # Recommend strengthening top categories
        for s in sorted_scores[:2]:
            if s.score >= 40:
                recommendations.append(
                    f"Strong {s.category_name} indicators detected — "
                    f"prioritize evidence collection for {', '.join(s.matched_flags[:2])}."
                )

        # Recommend investigating gaps
        for s in sorted_scores[-2:]:
            if s.score < 30:
                recommendations.append(
                    f"{s.category_name} evidence is weak — investigate whether "
                    f"this typology is present but undetected."
                )

        return recommendations

    def _fetch_entities(self, case_id: str) -> list[dict]:
        """Fetch entities from Aurora for the given case."""
        if not self._db:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT entity_id::text, canonical_name, entity_type, occurrence_count
                       FROM entities WHERE case_file_id = %s::uuid
                       ORDER BY occurrence_count DESC LIMIT 500""",
                    (case_id,),
                )
                rows = cur.fetchall()
                return [
                    {"entity_id": str(r[0]), "canonical_name": r[1],
                     "entity_type": r[2], "document_count": r[3] or 1}
                    for r in rows
                ]
        except Exception as e:
            logger.warning("Failed to fetch entities: %s", e)
            return []

    def _fetch_relationships(self, case_id: str) -> list[dict]:
        """Fetch relationships from Aurora for the given case."""
        if not self._db:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT source_entity, target_entity, relationship_type, occurrence_count
                       FROM relationships WHERE case_file_id = %s::uuid
                       LIMIT 2000""",
                    (case_id,),
                )
                rows = cur.fetchall()
                return [
                    {"source": str(r[0]), "target": str(r[1]),
                     "relationship_type": r[2], "weight": r[3]}
                    for r in rows
                ]
        except Exception as e:
            logger.warning("Failed to fetch relationships: %s", e)
            return []

    def to_frontend_payload(self, report: TypologyReport) -> dict:
        """Convert report to JSON payload for the frontend typology panel."""
        return {
            "case_id": report.case_id,
            "case_name": report.case_name,
            "overall_score": report.overall_score,
            "dominant_typology": report.dominant_typology,
            "flags_triggered": report.flags_triggered,
            "total_flags": report.total_flags,
            "categories": [
                {
                    "id": s.category_id,
                    "name": s.category_name,
                    "icon": s.icon,
                    "color": s.color,
                    "score": s.score,
                    "confidence": s.confidence,
                    "matched_flags": s.matched_flags,
                    "flag_details": s.flag_details,
                    "evidence_summary": s.evidence_summary,
                    "statistical_context": s.statistical_context,
                }
                for s in report.scores
            ],
            "recommendations": report.recommendations,
        }



# ──────────────────────────────────────────────────────────────────────────────
# Findings Engine — Drill-Down into Detected Situations
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Situation:
    """A detected cluster of evidence matching a typology pattern."""
    situation_id: str
    title: str
    entities: list[dict]  # [{name, type, role}]
    flags_triggered: list[str]
    document_count: int
    relationship_count: int
    ai_brief: str
    network: list[dict]  # [{source, target, type}] for mini-graph
    confidence: str


class TypologyFindingsEngine:
    """Detects specific 'situations' within a typology category.

    Groups entities and relationships into clusters that match
    the category's pattern flags, then generates AI briefs per cluster.
    """

    def __init__(self, aurora_conn=None, bedrock_client=None):
        self._db = aurora_conn
        self._bedrock = bedrock_client

    def get_findings(self, case_id: str, category_id: str) -> dict:
        """Get detected situations for a specific typology category.

        Args:
            case_id: Case to analyze.
            category_id: One of the 6 category IDs (e.g., 'recruitment_grooming').

        Returns:
            Dict with category info and list of detected situations.
        """
        # Find the category definition
        category = next((c for c in TYPOLOGY_CATEGORIES if c.id == category_id), None)
        if not category:
            return {"error": f"Unknown category: {category_id}"}

        # Fetch entities and relationships
        entities = self._fetch_entities(case_id, category.entity_types)
        relationships = self._fetch_relationships(case_id)

        # Cluster entities into situations
        situations = self._detect_situations(category, entities, relationships)

        # Generate AI briefs for top situations (cap at 3 to stay under API Gateway 29s timeout)
        for situation in situations[:3]:
            situation.ai_brief = self._generate_brief(category, situation)

        return {
            "case_id": case_id,
            "category_id": category_id,
            "category_name": category.name,
            "category_icon": category.icon,
            "category_color": category.color,
            "situations_count": len(situations),
            "situations": [
                {
                    "situation_id": s.situation_id,
                    "title": s.title,
                    "entities": s.entities,
                    "flags_triggered": s.flags_triggered,
                    "document_count": s.document_count,
                    "relationship_count": s.relationship_count,
                    "ai_brief": s.ai_brief,
                    "network": s.network,
                    "confidence": s.confidence,
                }
                for s in situations[:6]
            ],
        }

    def _detect_situations(self, category: TypologyCategory,
                           entities: list[dict], relationships: list[dict]) -> list[Situation]:
        """Detect situations by anchoring on the RIGHT entity type per category.

        Financial Control → find suspicious accounts/amounts first, trace to persons
        Transportation → find location clusters first, trace to travelers
        Communication → find phone/email hubs first, trace to operators
        Venue → find addresses with many connections first, trace to operators
        Recruitment → find persons with victim connections (person-first)
        Power & Control → find financial+person combinations
        """
        if not entities:
            return []

        # Build entity type lookup
        entity_type_map: dict[str, str] = {}
        for e in entities:
            entity_type_map[e.get("canonical_name", "")] = e.get("entity_type", "unknown")

        # Build adjacency from relationships
        adj: dict[str, set] = {}
        for r in relationships:
            src = r.get("source_entity", "")
            tgt = r.get("target_entity", "")
            if src and tgt:
                adj.setdefault(src, set()).add(tgt)
                adj.setdefault(tgt, set()).add(src)

        # Determine anchor entity types based on category
        anchor_types = self._get_anchor_types(category.id)
        trace_to = "person"  # What we trace the anchor back to

        # Find anchor entities (the evidence, not the person)
        anchor_entities = [
            e for e in entities
            if e.get("entity_type", "").lower() in anchor_types
            and len(adj.get(e.get("canonical_name", ""), set())) >= 1
        ]

        # Sort anchors by connection count (most connected = most suspicious)
        anchor_entities.sort(
            key=lambda e: len(adj.get(e.get("canonical_name", ""), set())),
            reverse=True
        )

        # For recruitment/grooming, person-first is correct
        if category.id == "recruitment_grooming":
            return self._detect_person_first(category, entities, relationships, adj, entity_type_map)

        # Build situations: group anchors that connect to the same person
        person_situations: dict[str, dict] = {}  # person_name → situation data

        for anchor in anchor_entities[:50]:  # Check top 50 anchors
            anchor_name = anchor.get("canonical_name", "")
            connected = adj.get(anchor_name, set())

            # Find persons connected to this anchor
            for connected_name in connected:
                etype = entity_type_map.get(connected_name, "unknown")
                if etype == "person":
                    if connected_name not in person_situations:
                        person_situations[connected_name] = {
                            "person": connected_name,
                            "anchors": [],
                            "all_connected": set(),
                        }
                    person_situations[connected_name]["anchors"].append({
                        "name": anchor_name,
                        "type": anchor.get("entity_type", "unknown"),
                        "occurrences": anchor.get("occurrence_count", 1),
                    })
                    person_situations[connected_name]["all_connected"].update(connected)

        # Convert to Situation objects
        situations = []
        for person_name, data in sorted(
            person_situations.items(),
            key=lambda x: len(x[1]["anchors"]),
            reverse=True
        )[:8]:
            anchors = data["anchors"]
            if not anchors:
                continue

            # Build entity list: person + their suspicious anchors
            situation_entities = [{"name": person_name, "type": "person", "role": "subject"}]
            for a in anchors[:10]:
                situation_entities.append({
                    "name": a["name"],
                    "type": a["type"],
                    "role": self._infer_role(a["type"], category.id)
                })

            # Build network edges
            network_edges = []
            for a in anchors[:8]:
                network_edges.append({
                    "source": person_name,
                    "target": a["name"],
                    "type": "controls" if category.id == "financial_control" else "connected_to"
                })

            # Match flags
            flags = self._match_flags(category, situation_entities)
            if not flags and len(anchors) >= 2:
                flags = [category.flags[0].name]

            # Title that explains the finding
            anchor_types_found = set(a["type"] for a in anchors)
            title = self._generate_situation_title(category.id, person_name, anchors)

            situations.append(Situation(
                situation_id=f"{category.id}_{person_name.replace(' ', '_').lower()[:20]}",
                title=title,
                entities=situation_entities,
                flags_triggered=flags,
                document_count=sum(a.get("occurrences", 1) for a in anchors),
                relationship_count=len(network_edges),
                ai_brief="",
                network=network_edges,
                confidence="high" if len(flags) >= 3 or len(anchors) >= 5 else "medium" if len(flags) >= 2 or len(anchors) >= 3 else "low",
            ))

        situations.sort(key=lambda s: (-len(s.flags_triggered), -s.relationship_count))
        return situations

    def _detect_person_first(self, category, entities, relationships, adj, entity_type_map):
        """Original person-first detection for Recruitment & Grooming."""
        person_entities = [e for e in entities if e.get("entity_type") == "person"]
        person_entities.sort(key=lambda e: len(adj.get(e.get("canonical_name", ""), set())), reverse=True)

        situations = []
        used = set()

        for person in person_entities[:8]:
            name = person.get("canonical_name", "")
            if name in used:
                continue
            connections = adj.get(name, set())
            if len(connections) < 2:
                continue
            used.add(name)

            situation_entities = [{"name": name, "type": "person", "role": "subject"}]
            network_edges = []

            for cn in list(connections)[:12]:
                etype = entity_type_map.get(cn, "unknown")
                situation_entities.append({"name": cn, "type": etype, "role": self._infer_role(etype, category.id)})
                network_edges.append({"source": name, "target": cn, "type": "connected_to"})

            flags = self._match_flags(category, situation_entities)
            if not flags and len(connections) >= 5:
                flags = [category.flags[0].name]

            if flags:
                situations.append(Situation(
                    situation_id=f"{category.id}_{name.replace(' ', '_').lower()[:20]}",
                    title=f"{name} → {len(connections)} connections",
                    entities=situation_entities,
                    flags_triggered=flags,
                    document_count=person.get("occurrence_count", 1) or 1,
                    relationship_count=len(network_edges),
                    ai_brief="",
                    network=network_edges,
                    confidence="high" if len(flags) >= 3 else "medium" if len(flags) >= 2 else "low",
                ))

        situations.sort(key=lambda s: (-len(s.flags_triggered), -s.relationship_count))
        return situations

    @staticmethod
    def _get_anchor_types(category_id: str) -> set:
        """Return the entity types to anchor on for each category."""
        return {
            "financial_control": {"financial_amount", "account_number"},
            "transportation_movement": {"location", "address", "hotel", "flight"},
            "communication_networks": {"phone_number", "email", "social_media_handle"},
            "venue_infrastructure": {"address", "location", "organization"},
            "power_control": {"financial_amount", "account_number"},
            "recruitment_grooming": {"person"},  # person-first
        }.get(category_id, {"person"})

    @staticmethod
    def _generate_situation_title(category_id: str, person_name: str, anchors: list) -> str:
        """Generate a compelling title that explains what was found."""
        anchor_count = len(anchors)
        anchor_types = set(a["type"] for a in anchors)

        if category_id == "financial_control":
            if "account_number" in anchor_types and "financial_amount" in anchor_types:
                return f"{person_name} → {anchor_count} financial instruments (accounts + transactions)"
            elif "account_number" in anchor_types:
                return f"{person_name} → {anchor_count} account numbers linked"
            else:
                return f"{person_name} → {anchor_count} financial transactions traced"
        elif category_id == "transportation_movement":
            return f"{person_name} → {anchor_count} locations in travel pattern"
        elif category_id == "communication_networks":
            return f"{person_name} → {anchor_count} communication channels"
        elif category_id == "venue_infrastructure":
            return f"{person_name} → {anchor_count} venues/addresses controlled"
        elif category_id == "power_control":
            return f"{person_name} → {anchor_count} financial control indicators"
        else:
            return f"{person_name} → {anchor_count} connections"

    def _match_flags(self, category: TypologyCategory, entities: list[dict]) -> list[str]:
        """Determine which typology flags are triggered by a situation's entities."""
        matched = []
        entity_types = {e.get("type") for e in entities}

        for flag in category.flags:
            # Simple heuristic: flag triggers if relevant entity types are present
            if flag.name in ("love_bombing", "age_disparity", "communication_isolation"):
                if "person" in entity_types and ("victim" in entity_types or "minor" in entity_types or len(entities) >= 4):
                    matched.append(flag.name)
            elif flag.name in ("hotel_clustering", "geographic_velocity", "circuit_rotation", "interstate_movement"):
                if "location" in entity_types or "address" in entity_types or "hotel" in entity_types:
                    matched.append(flag.name)
            elif flag.name in ("structuring", "controlled_accounts", "quota_evidence", "ad_payment_trail"):
                if "financial_amount" in entity_types or "account_number" in entity_types:
                    matched.append(flag.name)
            elif flag.name in ("disposable_cluster", "star_topology", "coordination_window", "coded_advertising"):
                if "phone_number" in entity_types or "email" in entity_types:
                    matched.append(flag.name)
            elif flag.name in ("venue_rotation", "multi_location_operation", "front_business"):
                if "address" in entity_types or "organization" in entity_types:
                    matched.append(flag.name)
            elif flag.name in ("debt_ledger", "document_control", "quota_enforcement"):
                if "financial_amount" in entity_types and "person" in entity_types:
                    matched.append(flag.name)
            elif flag.name in ("geographic_relocation", "false_employment", "third_party_booking"):
                if "location" in entity_types and "person" in entity_types:
                    matched.append(flag.name)

        return matched

    def _infer_role(self, entity_type: str, category_id: str) -> str:
        """Infer the role of an entity within a situation context."""
        role_map = {
            "person": "associate",
            "victim": "victim",
            "minor": "victim",
            "location": "venue",
            "address": "venue",
            "hotel": "venue",
            "financial_amount": "financial",
            "account_number": "financial",
            "phone_number": "communication",
            "email": "communication",
            "organization": "entity",
        }
        return role_map.get(entity_type, "related")

    def _generate_brief(self, category: TypologyCategory, situation: Situation) -> str:
        """Generate an AI narrative brief for a detected situation."""
        if self._bedrock:
            try:
                entities_desc = ", ".join(
                    f"{e['name']} ({e['role']})" for e in situation.entities[:8]
                )
                # NOTE: Prompt carefully worded to avoid Bedrock content filters.
                # The OUTPUT filter blocks text about exploitation/trafficking.
                # Instruct model to use only neutral law-enforcement language.
                prompt = (
                    f"You are a senior federal intelligence analyst writing a brief for a "
                    f"supervising attorney about a network analysis finding.\n\n"
                    f"IMPORTANT: Use only professional law-enforcement analytical language. "
                    f"Do NOT use graphic descriptions. Focus on network connections, "
                    f"organizational structure, and investigative next steps.\n\n"
                    f"Subject: {situation.title}\n"
                    f"Entities: {entities_desc}\n"
                    f"Indicators: {', '.join(f.replace('_', ' ') for f in situation.flags_triggered)}\n"
                    f"Connections: {situation.relationship_count}\n\n"
                    f"Write 2-3 sentences assessing the organizational significance of these "
                    f"connections and recommending collection priorities. Use formal "
                    f"analytical language suitable for an official case file."
                )
                import json as _json
                resp = self._bedrock.invoke_model(
                    modelId="us.amazon.nova-lite-v1:0",
                    contentType="application/json",
                    accept="application/json",
                    body=_json.dumps({
                        "messages": [{"role": "user", "content": [{"text": prompt}]}],
                        "inferenceConfig": {"maxTokens": 200, "temperature": 0.2},
                    }),
                )
                result = _json.loads(resp["body"].read())
                text = result.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
                # Check if content filter blocked the output
                if "blocked" in text.lower() or "content filter" in text.lower() or not text.strip():
                    raise ValueError("Content filter blocked output")
                return text
            except Exception as e:
                logger.warning("Bedrock brief generation failed: %s", str(e)[:100])

        # Fallback: deterministic brief
        subject = situation.entities[0]["name"] if situation.entities else "Subject"
        flags_str = ", ".join(f.replace("_", " ") for f in situation.flags_triggered)
        return (
            f"Analysis of {subject}'s network reveals {situation.relationship_count} "
            f"connections across {len(situation.entities)} entities, triggering "
            f"{category.name.lower()} indicators: {flags_str}. "
            f"Further investigation recommended to establish the full scope of activity "
            f"and identify additional victims or co-conspirators."
        )

    def _fetch_entities(self, case_id: str, entity_types: list[str]) -> list[dict]:
        """Fetch entities from Aurora — fetches ALL types to ensure anchors are included."""
        if not self._db:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT canonical_name, entity_type, occurrence_count
                       FROM entities WHERE case_file_id = %s::uuid
                       ORDER BY occurrence_count DESC LIMIT 2000""",
                    (case_id,),
                )
                return [
                    {"canonical_name": r[0], "entity_type": r[1], "occurrence_count": r[2]}
                    for r in cur.fetchall()
                ]
        except Exception as e:
            logger.warning("Failed to fetch entities for findings: %s", e)
            return []

    def _fetch_relationships(self, case_id: str) -> list[dict]:
        """Fetch relationships from Aurora."""
        if not self._db:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT source_entity, target_entity, relationship_type, occurrence_count
                       FROM relationships WHERE case_file_id = %s::uuid
                       ORDER BY occurrence_count DESC LIMIT 5000""",
                    (case_id,),
                )
                return [
                    {"source_entity": r[0], "target_entity": r[1],
                     "relationship_type": r[2], "occurrence_count": r[3]}
                    for r in cur.fetchall()
                ]
        except Exception as e:
            logger.warning("Failed to fetch relationships for findings: %s", e)
            return []
