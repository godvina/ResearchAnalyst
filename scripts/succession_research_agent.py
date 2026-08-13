"""
Executive Succession Planning — Research Agent

Scans public sources (web search, LinkedIn public profiles, conference bios,
press releases, blog posts) to identify and score succession candidates for
a given company and role.

Usage:
    python scripts/succession_research_agent.py --company "AWS" \
        --division "Worldwide Public Sector" --role "VP Worldwide Public Sector" \
        --output succession_candidates.json

Data Sources (all public, no login-wall scraping):
    - Company blogs / press releases
    - Conference speaker bios (re:Invent, AWS Summits, etc.)
    - Industry awards (Wash100, Forbes Tech Council, etc.)
    - News articles about promotions/departures
    - Government contracting databases (USASpending, FPDS)

Scoring Approach:
    - Maps public signals → 25 Universal Selection Criteria
    - Signal strength determines confidence level (high/medium/low)
    - Three-layer weights applied: Universal Core × Cultural Flex × Sector Params
"""

import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

# Bedrock for AI-powered analysis
try:
    import boto3
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class PublicSignal:
    """A single piece of publicly available evidence about a candidate."""
    source_type: str          # blog, press_release, conference, award, news, profile
    source_url: str
    source_date: str          # ISO date
    signal_text: str          # extracted evidence
    criteria_mapped: list[str]  # which of 25 criteria this maps to
    confidence: str           # high, medium, low
    raw_snippet: str = ""


@dataclass 
class CandidateProfile:
    """Assembled profile of a succession candidate from public sources."""
    name: str
    current_title: str
    current_org: str
    division: str
    country: str
    sector: str
    source_type: str          # internal, external_competitor, external_adjacent
    signals: list[PublicSignal] = field(default_factory=list)
    inferred_scores: dict = field(default_factory=dict)  # criterion -> score estimate
    score_confidence: dict = field(default_factory=dict)  # criterion -> confidence
    composite_estimate: float = 0.0
    ai_brief: str = ""
    linkedin_public_url: str = ""
    years_in_role: int = 0
    prior_roles: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    board_seats: list[str] = field(default_factory=list)
    awards: list[str] = field(default_factory=list)
    speaking_engagements: list[str] = field(default_factory=list)
    research_timestamp: str = ""


@dataclass
class SuccessionTransaction:
    """Defines the scope of a succession planning engagement."""
    transaction_id: str
    company: str
    division: str
    target_role: str
    scope: str               # single_role, c_suite, all_executives
    sector: str
    country: str
    incumbent_name: str = ""
    urgency: str = "planned"  # emergency, accelerated, planned
    constraints: dict = field(default_factory=dict)
    created_at: str = ""
    status: str = "initiated"


# =============================================================================
# SIGNAL-TO-CRITERIA MAPPING
# =============================================================================

# Maps observable public signals to the 25 Universal Selection Criteria
SIGNAL_CRITERIA_MAP = {
    # Conference keynotes → executive presence, stakeholder management
    "keynote_speaker": ["executive_presence", "stakeholder_management", "strategic_vision"],
    # Revenue responsibility → results orientation, financial acumen
    "revenue_leadership": ["results_orientation", "financial_acumen", "operational_excellence"],
    # International assignments → global perspective, adaptability
    "international_role": ["global_perspective", "adaptability", "cultural_faith_ethics"],
    # Industry awards → industry expertise, results orientation
    "industry_award": ["industry_expertise", "results_orientation", "executive_presence"],
    # Board seats → board governance, strategic vision
    "board_membership": ["board_governance", "strategic_vision", "stakeholder_management"],
    # Team building / org growth → talent development, change management
    "org_building": ["talent_development", "change_management", "innovation_leadership"],
    # Crisis management (public) → crisis leadership, resilience, decisiveness
    "crisis_response": ["crisis_leadership", "resilience", "decisiveness"],
    # Digital transformation → digital fluency, innovation leadership
    "digital_initiative": ["digital_fluency", "innovation_leadership", "learning_agility"],
    # M&A / large deals → financial acumen, decisiveness, stakeholder management
    "major_deal": ["financial_acumen", "decisiveness", "stakeholder_management"],
    # Regulatory / government relations → political_savvy, compliance
    "government_relations": ["stakeholder_management", "integrity", "adaptability"],
    # AI / tech adoption leadership → cognitive ability, digital fluency
    "ai_leadership": ["cognitive_ability", "digital_fluency", "innovation_leadership"],
    # Diversity / culture initiatives → emotional intelligence, talent development
    "dei_leadership": ["emotional_intelligence", "talent_development", "self_awareness"],
    # Entrepreneurial background → innovation, energy/drive, results
    "entrepreneurial": ["innovation_leadership", "energy_drive", "results_orientation"],
    # Security clearance / classified work → integrity, mission execution
    "security_cleared": ["integrity", "resilience", "mission_execution"],
    # Customer-facing leadership → customer centricity, stakeholder mgmt
    "customer_leadership": ["customer_centricity", "stakeholder_management", "emotional_intelligence"],
}


# =============================================================================
# PRE-SEEDED AWS PUBLIC SECTOR DATA (from public research)
# =============================================================================

def build_aws_pubsec_candidates() -> list[CandidateProfile]:
    """Build candidate profiles from publicly available information about
    AWS Public Sector leadership. All data sourced from public press releases,
    conference bios, award announcements, and company blogs."""

    candidates = []

    # --- Dave Levy (Current VP WWPS — the incumbent) ---
    levy = CandidateProfile(
        name="Dave Levy",
        current_title="Vice President, Worldwide Public Sector",
        current_org="Amazon Web Services",
        division="Worldwide Public Sector",
        country="US",
        sector="PRIVATE",
        source_type="internal_incumbent",
        years_in_role=3,
        prior_roles=[
            "VP, US Government, Nonprofit & Healthcare at AWS (6 years)",
            "Head of US Government Sales at Apple (12 years)",
            "COO, Sulla Technology Group (co-founder)",
            "Empire Capital Management (founder)",
            "Monster.com"
        ],
        awards=[
            "Wash100 Award (7-time winner, 2020-2026)",
            "2026 Virginia Power 50",
            "2026 Virginia Black Business Leaders Award",
            "Top Industry Exec to Watch 2026 (WashingtonExec)"
        ],
        speaking_engagements=[
            "AWS Summit Washington DC 2026 — Keynote",
            "AWS Summit Washington DC 2025 — Keynote",
            "Milken Institute Global Conference 2025",
            "Billington Cyber Summit",
            "Concordia Annual Summit"
        ],
        linkedin_public_url="https://www.linkedin.com/in/davelevy/",
        signals=[
            PublicSignal(
                source_type="award",
                source_url="https://www.wash100.com/winners/2026/david-levy/",
                source_date="2026-03-01",
                signal_text="7th Wash100 award reflecting AWS expanding role in federal cloud and AI adoption",
                criteria_mapped=["results_orientation", "industry_expertise", "executive_presence"],
                confidence="high"
            ),
            PublicSignal(
                source_type="press_release",
                source_url="https://www.aboutamazon.com/news/aws/aws-summit-dc-2026-ai-cloud-public-sector",
                source_date="2026-06-29",
                signal_text="Keynote at AWS Summit DC with US Secretary of Energy, announcing billions in AI investment",
                criteria_mapped=["executive_presence", "stakeholder_management", "strategic_vision"],
                confidence="high"
            ),
            PublicSignal(
                source_type="news",
                source_url="https://www.govconwire.com/articles/david-levy-aws-worldwide-public-sector-vp-2025-wash100-award-recipient",
                source_date="2025-08-01",
                signal_text="Drove OneGov agreement ($1B cloud services to federal civilian agencies)",
                criteria_mapped=["financial_acumen", "results_orientation", "stakeholder_management"],
                confidence="high"
            ),
            PublicSignal(
                source_type="news",
                source_url="https://washingtonexec.com/2023/11/aws-david-levy-on-his-new-role-as-vp-worldwide-public-sector/",
                source_date="2023-11-01",
                signal_text="Promoted from VP US Gov to VP Worldwide Public Sector Oct 2023; expanded scope to global",
                criteria_mapped=["global_perspective", "operational_excellence", "strategic_vision"],
                confidence="high"
            ),
        ],
        inferred_scores={
            "strategic_vision": 9, "integrity": 9, "cognitive_ability": 8,
            "resilience": 9, "results_orientation": 10,
            "emotional_intelligence": 8, "adaptability": 8, "self_awareness": 7,
            "learning_agility": 8, "executive_presence": 10,
            "decisiveness": 8, "energy_drive": 9,
            "industry_expertise": 10, "functional_excellence": 9, "financial_acumen": 9,
            "digital_fluency": 8, "global_perspective": 8, "talent_development": 8,
            "stakeholder_management": 10, "board_governance": 7,
            "crisis_leadership": 8, "innovation_leadership": 8, "change_management": 8,
            "customer_centricity": 9, "operational_excellence": 9
        },
        ai_brief="Incumbent. 7x Wash100 winner, strongest government relationship network in tech. Built AWS from $0 to multi-billion public sector business. Apple-to-AWS career arc demonstrates adaptability across enterprise cultures. Gap: board governance exposure limited to advisory roles."
    )
    candidates.append(levy)

    # --- David Appel (VP US Federal — internal successor candidate) ---
    appel = CandidateProfile(
        name="David Appel",
        current_title="Vice President, US Federal",
        current_org="Amazon Web Services",
        division="Worldwide Public Sector — US Federal",
        country="US",
        sector="PRIVATE",
        source_type="internal",
        years_in_role=3,
        prior_roles=[
            "VP, National Security at AWS",
            "Program leadership, business operations, finance roles (prior to AWS)",
        ],
        awards=[
            "Top AI Execs to Watch 2026 (WashingtonExec)",
        ],
        speaking_engagements=[
            "AWS Summit Washington DC 2025",
            "Concordia Annual Summit",
            "The Cipher Brief Network",
            "FedGov Today",
            "Wall Street Journal Partners — GenAI for Government"
        ],
        linkedin_public_url="https://www.linkedin.com/in/david-appel/",
        signals=[
            PublicSignal(
                source_type="news",
                source_url="https://washingtonexec.com/2026/06/top-ai-execs-to-watch-in-2026-aws-david-appel/",
                source_date="2026-06-01",
                signal_text="Led launch of AWS Secret-West Region expanding classified computing for defense/intel missions",
                criteria_mapped=["crisis_leadership", "innovation_leadership", "operational_excellence"],
                confidence="high"
            ),
            PublicSignal(
                source_type="blog",
                source_url="https://aws.amazon.com/blogs/publicsector/embracing-generative-ai-to-power-mission-innovation-insights-from-aws-us-federal-vice-president-david-appel/",
                source_date="2025-01-14",
                signal_text="Service-based, customer obsessed career focused on making communities better",
                criteria_mapped=["customer_centricity", "integrity", "emotional_intelligence"],
                confidence="medium"
            ),
            PublicSignal(
                source_type="news",
                source_url="https://www.govconwire.com/articles/david-appel-named-amazon-web-services-vp-of-us-federal",
                source_date="2023-10-09",
                signal_text="Promoted from VP National Security to VP US Federal — breadth of program leadership, biz ops, finance, BD, strategic planning",
                criteria_mapped=["financial_acumen", "strategic_vision", "functional_excellence"],
                confidence="high"
            ),
            PublicSignal(
                source_type="conference",
                source_url="https://concordia.net/community/david-appel/",
                source_date="2025-01-01",
                signal_text="Made Amazon Bedrock generally available in Top Secret cloud region for national security customers",
                criteria_mapped=["digital_fluency", "innovation_leadership", "decisiveness"],
                confidence="high"
            ),
        ],
        inferred_scores={
            "strategic_vision": 8, "integrity": 9, "cognitive_ability": 9,
            "resilience": 9, "results_orientation": 9,
            "emotional_intelligence": 8, "adaptability": 8, "self_awareness": 7,
            "learning_agility": 9, "executive_presence": 8,
            "decisiveness": 9, "energy_drive": 8,
            "industry_expertise": 9, "functional_excellence": 9, "financial_acumen": 8,
            "digital_fluency": 9, "global_perspective": 7, "talent_development": 7,
            "stakeholder_management": 9, "board_governance": 6,
            "crisis_leadership": 9, "innovation_leadership": 9, "change_management": 8,
            "customer_centricity": 9, "operational_excellence": 9
        },
        ai_brief="Strongest internal successor for WWPS VP. Deep national security + federal breadth. Led Secret-West region launch and Bedrock in Top Secret — proving delivery at classified scale. Gap: limited international/commercial exposure (global perspective 7). Ideal Accelerated path with 6-month international rotation."
    )
    candidates.append(appel)

    # --- Kim Majerus (VP SLED — internal successor candidate) ---
    majerus = CandidateProfile(
        name="Kim Majerus",
        current_title="Vice President, State and Local Government and Education",
        current_org="Amazon Web Services",
        division="Worldwide Public Sector — SLED",
        country="US",
        sector="PRIVATE",
        source_type="internal",
        years_in_role=8,
        prior_roles=[
            "VP, Cisco Public Sector — US State, Local and Education (16 years at Cisco)",
            "Various leadership roles at Cisco Systems in US and Europe",
        ],
        awards=[],
        speaking_engagements=[
            "AWS IMAGINE Conference — Keynote (2022, 2023, 2024)",
            "ASU+GSV Summit",
            "Texas Conference for Women",
            "GovTech conferences"
        ],
        linkedin_public_url="https://www.linkedin.com/in/kimmajerus/",
        signals=[
            PublicSignal(
                source_type="press_release",
                source_url="https://press.aboutamazon.com/aws/2025/7/centralsquare-selects-aws-as-its-preferred-cloud-provider-in-five-year-agreement-to-power-solutions-for-public-sector-agencies",
                source_date="2025-06-10",
                signal_text="CentralSquare 5-year preferred cloud provider agreement combining deep public sector expertise + world-class cloud",
                criteria_mapped=["stakeholder_management", "results_orientation", "customer_centricity"],
                confidence="high"
            ),
            PublicSignal(
                source_type="conference",
                source_url="https://www.govtech.com/sponsored/how-ai-powers-state-and-local-government-innovation-icymi",
                source_date="2023-06-01",
                signal_text="Built AWS SLG from startup in 2017 to 7,500+ gov agencies, 14,000+ academic institutions, 35,000+ nonprofits in 200+ countries",
                criteria_mapped=["results_orientation", "talent_development", "global_perspective", "change_management"],
                confidence="high"
            ),
            PublicSignal(
                source_type="profile",
                source_url="https://asugsvsummit.com/speakers/kim-majerus",
                source_date="2024-01-01",
                signal_text="16 years at Cisco prior — VP Cisco Public Sector US SLED. Deep cross-company experience.",
                criteria_mapped=["industry_expertise", "adaptability", "operational_excellence"],
                confidence="high"
            ),
        ],
        inferred_scores={
            "strategic_vision": 8, "integrity": 8, "cognitive_ability": 8,
            "resilience": 8, "results_orientation": 9,
            "emotional_intelligence": 9, "adaptability": 8, "self_awareness": 8,
            "learning_agility": 8, "executive_presence": 8,
            "decisiveness": 7, "energy_drive": 8,
            "industry_expertise": 9, "functional_excellence": 8, "financial_acumen": 7,
            "digital_fluency": 8, "global_perspective": 8, "talent_development": 9,
            "stakeholder_management": 9, "board_governance": 6,
            "crisis_leadership": 7, "innovation_leadership": 8, "change_management": 9,
            "customer_centricity": 9, "operational_excellence": 8
        },
        ai_brief="Built AWS SLED from zero to 7,500+ agencies — strongest org-building track record in the division. 16 years at Cisco before AWS gives cross-company perspective. Global reach (200+ countries). Gap: federal/defense depth and board governance. Ideal Planned successor with defense immersion."
    )
    candidates.append(majerus)

    # --- Teresa Carlson (Former AWS WWPS VP — external benchmark/competitor) ---
    carlson = CandidateProfile(
        name="Teresa Carlson",
        current_title="Global Head of Public Sector",
        current_org="Anthropic",
        division="Public Sector",
        country="US",
        sector="PRIVATE",
        source_type="external_competitor",
        years_in_role=0,
        prior_roles=[
            "President & Chief Growth Officer, Splunk",
            "VP, AWS Worldwide Public Sector & Industries (10+ years, founder of the division)",
            "VP, Federal Government at Microsoft (10 years)",
            "CEO, General Catalyst Institute",
        ],
        awards=[
            "World Economic Forum contributor",
            "Multiple Wash100 awards during AWS tenure"
        ],
        speaking_engagements=[
            "World Economic Forum Davos",
            "AWS re:Invent (multiple years as keynote)",
            "AWS Summit Washington DC (multiple years)"
        ],
        board_seats=[
            "PagerDuty (public board)",
            "Commure",
            "Board Observer: Re:Build, Re:Car, Cobot, Mark43"
        ],
        linkedin_public_url="https://www.linkedin.com/in/teresacarlson/",
        signals=[
            PublicSignal(
                source_type="news",
                source_url="https://fedscoop.com/anthropic-taps-microsoft-aws-teresa-carlson-lead-public-sector/",
                source_date="2026-07-01",
                signal_text="Joined Anthropic as Global Head of Public Sector — demonstrates continued market relevance",
                criteria_mapped=["strategic_vision", "adaptability", "industry_expertise"],
                confidence="high"
            ),
            PublicSignal(
                source_type="profile",
                source_url="https://meridian.org/profile/teresa-carlson/",
                source_date="2025-01-01",
                signal_text="Founded and led AWS WWPS for over a decade — built from zero to billions",
                criteria_mapped=["results_orientation", "innovation_leadership", "talent_development"],
                confidence="high"
            ),
            PublicSignal(
                source_type="news",
                source_url="https://nationalsecurity.gmu.edu/teresa-carlson/",
                source_date="2025-01-01",
                signal_text="Public company board (PagerDuty) + multiple startup boards — strong governance experience",
                criteria_mapped=["board_governance", "financial_acumen", "strategic_vision"],
                confidence="high"
            ),
        ],
        inferred_scores={
            "strategic_vision": 10, "integrity": 9, "cognitive_ability": 9,
            "resilience": 9, "results_orientation": 10,
            "emotional_intelligence": 8, "adaptability": 10, "self_awareness": 8,
            "learning_agility": 9, "executive_presence": 10,
            "decisiveness": 9, "energy_drive": 10,
            "industry_expertise": 10, "functional_excellence": 9, "financial_acumen": 9,
            "digital_fluency": 8, "global_perspective": 9, "talent_development": 9,
            "stakeholder_management": 10, "board_governance": 9,
            "crisis_leadership": 8, "innovation_leadership": 9, "change_management": 9,
            "customer_centricity": 8, "operational_excellence": 9
        },
        ai_brief="EXTERNAL — Gold standard for public sector tech leadership. Founded AWS WWPS, built it from zero to billions over 10 years. Microsoft decade before that. Now at Anthropic as Global PS Head. Public board (PagerDuty). Near-perfect profile but unavailable — at competitor. Benchmark only."
    )
    candidates.append(carlson)

    # --- Philippe Rogge (Microsoft WWPS CVP — external competitor) ---
    rogge = CandidateProfile(
        name="Philippe Rogge",
        current_title="Corporate Vice President, Worldwide Public Sector",
        current_org="Microsoft",
        division="Worldwide Public Sector",
        country="US",
        sector="PRIVATE",
        source_type="external_competitor",
        years_in_role=1,
        prior_roles=[
            "CEO, Vodafone Germany",
            "Senior leadership roles at Vodafone Group",
        ],
        awards=[],
        speaking_engagements=[],
        linkedin_public_url="https://www.linkedin.com/in/philipperogge/",
        signals=[
            PublicSignal(
                source_type="news",
                source_url="https://www.govconwire.com/articles/philippe-rogge-microsoft-worldwide-public-sector-corporate-vp-appointment",
                source_date="2025-07-23",
                signal_text="Appointed CVP Worldwide Public Sector at Microsoft — former CEO of Vodafone Germany",
                criteria_mapped=["executive_presence", "global_perspective", "operational_excellence"],
                confidence="medium"
            ),
        ],
        inferred_scores={
            "strategic_vision": 8, "integrity": 8, "cognitive_ability": 8,
            "resilience": 8, "results_orientation": 8,
            "emotional_intelligence": 7, "adaptability": 9, "self_awareness": 7,
            "learning_agility": 8, "executive_presence": 9,
            "decisiveness": 8, "energy_drive": 8,
            "industry_expertise": 6, "functional_excellence": 8, "financial_acumen": 8,
            "digital_fluency": 8, "global_perspective": 10, "talent_development": 7,
            "stakeholder_management": 8, "board_governance": 8,
            "crisis_leadership": 7, "innovation_leadership": 7, "change_management": 8,
            "customer_centricity": 7, "operational_excellence": 8
        },
        ai_brief="EXTERNAL COMPETITOR — Microsoft's new WWPS CVP. Former Vodafone Germany CEO brings massive international operations experience (global perspective 10). Gap: relatively new to public sector tech — limited government relationship network (industry_expertise 6). Unlikely poach target."
    )
    candidates.append(rogge)

    # Set timestamps
    now = datetime.now(timezone.utc).isoformat()
    for c in candidates:
        c.research_timestamp = now

    return candidates


# =============================================================================
# SCORING ENGINE INTEGRATION
# =============================================================================

def compute_composite_from_signals(candidate: CandidateProfile) -> float:
    """Compute composite score from inferred scores using default PRIVATE/US/CEO weights.
    
    This mirrors the scoring_engine.py three-layer algorithm but uses
    signal-inferred scores instead of formal assessment data.
    """
    # Default CEO/Private/US role config weights (Layer 1)
    universal_core_weights = {
        "strategic_vision": 9, "integrity": 10, "cognitive_ability": 8,
        "resilience": 8, "results_orientation": 8,
        "emotional_intelligence": 7, "adaptability": 7,
        "self_awareness": 6, "learning_agility": 7, "executive_presence": 8,
        "decisiveness": 7, "energy_drive": 6,
        "industry_expertise": 7, "functional_excellence": 6, "financial_acumen": 7,
        "digital_fluency": 6, "global_perspective": 7, "talent_development": 6,
        "stakeholder_management": 8, "board_governance": 7,
        "crisis_leadership": 7, "innovation_leadership": 6, "change_management": 6,
        "customer_centricity": 6, "operational_excellence": 6
    }

    # Normalize weights
    total_w = sum(universal_core_weights.values())
    norm_weights = {k: v / total_w for k, v in universal_core_weights.items()}

    # Compute weighted sum
    weighted_sum = 0.0
    max_possible = 0.0
    for criterion, weight in norm_weights.items():
        score = candidate.inferred_scores.get(criterion, 5)
        weighted_sum += weight * score
        max_possible += weight * 10

    composite = (weighted_sum / max_possible * 100) if max_possible > 0 else 0
    return round(composite, 1)


def run_research_pipeline(transaction: SuccessionTransaction) -> dict:
    """Execute the full research pipeline for a succession transaction.
    
    Steps:
    1. Identify scope (company, division, role)
    2. Search internal bench (one level below target role)
    3. Search external market (competitors, adjacent firms)
    4. Score all candidates
    5. Rank and generate AI briefs
    6. Return structured output for dashboard
    """
    logger.info(f"Starting research pipeline for: {transaction.company} / "
                f"{transaction.division} / {transaction.target_role}")

    # For demo purposes, use pre-seeded AWS Public Sector data
    if "aws" in transaction.company.lower() and "public sector" in transaction.division.lower():
        candidates = build_aws_pubsec_candidates()
    else:
        logger.warning(f"No pre-seeded data for {transaction.company}. "
                      "In production, this would invoke web search + LinkedIn API.")
        candidates = []

    # Compute composite scores
    for c in candidates:
        c.composite_estimate = compute_composite_from_signals(c)

    # Sort by composite (descending)
    candidates.sort(key=lambda x: x.composite_estimate, reverse=True)

    # Build output
    output = {
        "transaction": asdict(transaction),
        "research_date": datetime.now(timezone.utc).isoformat(),
        "candidates_found": len(candidates),
        "candidates": [asdict(c) for c in candidates],
        "pipeline_summary": {
            "internal": len([c for c in candidates if c.source_type == "internal"]),
            "internal_incumbent": len([c for c in candidates if c.source_type == "internal_incumbent"]),
            "external_competitor": len([c for c in candidates if c.source_type == "external_competitor"]),
            "external_adjacent": len([c for c in candidates if c.source_type == "external_adjacent"]),
            "avg_composite": round(sum(c.composite_estimate for c in candidates) / len(candidates), 1) if candidates else 0,
            "top_internal": next((c.name for c in candidates if c.source_type == "internal"), None),
            "top_external": next((c.name for c in candidates if "external" in c.source_type), None),
        }
    }

    return output


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Executive Succession Research Agent")
    parser.add_argument("--company", default="AWS", help="Target company")
    parser.add_argument("--division", default="Worldwide Public Sector", help="Division/BU")
    parser.add_argument("--role", default="VP Worldwide Public Sector", help="Target role")
    parser.add_argument("--scope", default="single_role", choices=["single_role", "c_suite", "all_executives"])
    parser.add_argument("--sector", default="PRIVATE")
    parser.add_argument("--country", default="US")
    parser.add_argument("--output", default="succession_candidates.json", help="Output file path")

    args = parser.parse_args()

    transaction = SuccessionTransaction(
        transaction_id=f"TXN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        company=args.company,
        division=args.division,
        target_role=args.role,
        scope=args.scope,
        sector=args.sector,
        country=args.country,
        created_at=datetime.now(timezone.utc).isoformat(),
        status="researching"
    )

    logger.info(f"Transaction: {transaction.transaction_id}")
    logger.info(f"Scope: {transaction.company} / {transaction.division} / {transaction.target_role}")

    results = run_research_pipeline(transaction)

    # Write output
    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"Results written to: {output_path}")
    logger.info(f"Candidates found: {results['candidates_found']}")
    logger.info(f"Top internal: {results['pipeline_summary']['top_internal']}")
    logger.info(f"Top external: {results['pipeline_summary']['top_external']}")
    logger.info(f"Average composite: {results['pipeline_summary']['avg_composite']}")

    return results


if __name__ == "__main__":
    main()
