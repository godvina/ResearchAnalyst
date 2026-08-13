"""
Executive Succession Planning — Risk Analyzer

Computes multi-dimensional risk scores for succession candidates:
  - Flight Risk: likelihood a candidate leaves voluntarily
  - Poachability: attractiveness to external recruiters
  - Cultural Risk: Hofstede-dimension distance between origin/target countries
  - Compliance Risk: sanctions and reputational red flags
  - Notice Period: contractual/legal availability timeline

Correctness Properties:
  P3: All scores clamped to [0, 100]
  P4: Cultural distance is symmetric — distance(A, B) == distance(B, A)
"""

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# Data Types
# =============================================================================

@dataclass
class RiskScore:
    """Quantified risk assessment with tier classification."""
    score: int              # 0-100
    tier: str               # LOW, MEDIUM, HIGH
    factors: list[str]      # Top contributing factor descriptions


@dataclass
class CulturalRisk:
    """Hofstede cultural distance assessment between two countries."""
    level: str              # LOW, MEDIUM, HIGH, CRITICAL
    distance: float         # Euclidean distance across 6 dimensions
    dimension_gaps: list[str]  # Dimensions with >30 point difference


@dataclass
class ComplianceRisk:
    """Sanctions and reputational risk assessment."""
    sanctions: str          # CLEAR, LOW, MEDIUM, HIGH, CRITICAL, INSUFFICIENT_DATA
    reputational: str       # CLEAR, LOW, MEDIUM, HIGH, CRITICAL, INSUFFICIENT_DATA
    sources: list[str]      # Signal texts that triggered flags


@dataclass
class NoticePeriod:
    """Contractual availability timeline estimate."""
    notice_months: int
    non_compete_months: int
    earliest_available_months: int
    enforceable: bool
    confidence: str         # HIGH, MEDIUM, LOW


# =============================================================================
# Constants
# =============================================================================

HOFSTEDE_DIMENSIONS = [
    "power_distance",
    "individualism",
    "masculinity",
    "uncertainty_avoidance",
    "long_term_orientation",
    "indulgence",
]

SANCTIONS_KEYWORDS = ["ofac", "sanctioned", "sdn list", "restricted entity"]
CONTROVERSY_KEYWORDS = ["lawsuit", "investigation", "fraud", "scandal", "fired", "terminated"]

# Countries with well-documented employment law (high confidence)
KNOWN_RULES_COUNTRIES = {"DE", "FR", "NL", "BE", "AT", "CH", "SE", "NO", "DK", "FI", "JP", "KR", "SG"}

# Common-law countries (medium confidence — more variable enforcement)
COMMON_LAW_COUNTRIES = {"US", "GB", "CA", "AU", "NZ", "IE", "IN", "HK"}


# =============================================================================
# Risk Analyzer
# =============================================================================

class RiskAnalyzer:
    """Multi-dimensional risk assessment for executive succession candidates.

    All score outputs are clamped to [0, 100] (Property 3).
    Cultural distance is symmetric by construction (Property 4).
    """

    def compute_flight_risk(self, candidate: dict) -> RiskScore:
        """Compute probability a candidate leaves voluntarily.

        Factors (each 0-1, multiplied by weight):
          - tenure_factor (weight 30): shorter tenure = higher risk
          - org_stability (weight 25): organizational turmoil increases flight
          - comp_trend (weight 20): below-market compensation drives exits
          - progression (weight 25): stalled career progression increases risk

        Args:
            candidate: Dict with keys years_in_role, org_instability,
                      comp_below_market, promotions_last_5yr.

        Returns:
            RiskScore with score 0-100, tier, and top 3 contributing factors.
        """
        # Compute individual factors (each 0-1)
        tenure_factor = max(0.0, 1.0 - candidate.get("years_in_role", 3) / 10.0)
        org_stability = candidate.get("org_instability", 0.3)
        comp_trend = candidate.get("comp_below_market", 0.2)
        progression = max(0.0, 1.0 - candidate.get("promotions_last_5yr", 1) / 3.0)

        # Weighted sum
        raw_score = round(
            tenure_factor * 30
            + org_stability * 25
            + comp_trend * 20
            + progression * 25
        )

        # Clamp to [0, 100] (Property 3)
        score = max(0, min(100, raw_score))

        # Classify tier
        if score >= 70:
            tier = "HIGH"
        elif score >= 40:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        # Identify top 3 contributing factors (sorted by weighted contribution)
        contributions = [
            (tenure_factor * 30, f"Short tenure ({candidate.get('years_in_role', 3):.1f} years in role)"),
            (org_stability * 25, f"Organizational instability ({org_stability:.0%})"),
            (comp_trend * 20, f"Below-market compensation ({comp_trend:.0%} gap)"),
            (progression * 25, f"Stalled progression ({candidate.get('promotions_last_5yr', 1)} promotions in 5yr)"),
        ]
        contributions.sort(key=lambda x: x[0], reverse=True)
        factors = [desc for _, desc in contributions[:3]]

        return RiskScore(score=score, tier=tier, factors=factors)

    def compute_poachability(self, candidate: dict, comp_gap_pct: float) -> RiskScore:
        """Compute attractiveness to external recruiters.

        Factors (each 0-1, multiplied by weight):
          - comp_gap_factor (weight 30): negative gap = below market = more poachable
          - career_stage (weight 20): peak poachability at ~15 years to retirement
          - mobility (weight 25): history of org changes indicates willingness to move
          - org_instability (weight 25): turmoil makes poaching easier

        Args:
            candidate: Dict with keys years_to_retirement, org_changes_15yr, org_instability.
            comp_gap_pct: Compensation gap percentage (negative = below market).

        Returns:
            RiskScore with score 0-100, tier, and top contributing factors.
        """
        # Compute individual factors (each 0-1)
        comp_gap_factor = min(1.0, max(0.0, -comp_gap_pct / 50.0))
        years_to_ret = candidate.get("years_to_retirement", 15)
        career_stage = 1.0 - abs(years_to_ret - 15) / 15.0
        career_stage = max(0.0, min(1.0, career_stage))
        mobility = min(1.0, candidate.get("org_changes_15yr", 2) / 4.0)
        org_instability = candidate.get("org_instability", 0.3)

        # Weighted sum
        raw_score = round(
            comp_gap_factor * 30
            + career_stage * 20
            + mobility * 25
            + org_instability * 25
        )

        # Clamp to [0, 100] (Property 3)
        score = max(0, min(100, raw_score))

        # Classify tier
        if score >= 67:
            tier = "HIGH"
        elif score >= 34:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        # Identify contributing factors
        contributions = [
            (comp_gap_factor * 30, f"Below-market compensation ({comp_gap_pct:+.1f}% gap)"),
            (career_stage * 20, f"Peak career stage ({years_to_ret} years to retirement)"),
            (mobility * 25, f"High mobility history ({candidate.get('org_changes_15yr', 2)} org changes in 15yr)"),
            (org_instability * 25, f"Organizational instability ({org_instability:.0%})"),
        ]
        contributions.sort(key=lambda x: x[0], reverse=True)
        factors = [desc for _, desc in contributions[:3]]

        return RiskScore(score=score, tier=tier, factors=factors)

    def compute_cultural_risk(self, origin_country: str, target_country: str,
                              profiles: dict) -> CulturalRisk:
        """Compute Hofstede cultural distance between two countries.

        Uses Euclidean distance across 6 dimensions:
          power_distance, individualism, masculinity, uncertainty_avoidance,
          long_term_orientation, indulgence

        Classification:
          LOW: distance < 30
          MEDIUM: 30 <= distance <= 60
          HIGH: 60 < distance <= 90
          CRITICAL: distance > 90

        Property 4: distance(A, B) == distance(B, A) — symmetric by construction.

        Args:
            origin_country: ISO country code for candidate's origin.
            target_country: ISO country code for target role location.
            profiles: Dict mapping country codes to Hofstede dimension scores.

        Returns:
            CulturalRisk with level, distance, and dimension gaps > 30 points.
        """
        origin_profile = profiles.get(origin_country, {})
        target_profile = profiles.get(target_country, {})

        # Compute Euclidean distance (symmetric: sqrt(Σ(a-b)²) == sqrt(Σ(b-a)²))
        sum_sq = 0.0
        dimension_gaps = []

        for dim in HOFSTEDE_DIMENSIONS:
            a = origin_profile.get(dim, 50)  # Default to midpoint if missing
            b = target_profile.get(dim, 50)
            diff = a - b
            sum_sq += diff ** 2

            # Track dimensions with large gaps
            if abs(diff) > 30:
                dim_label = dim.replace("_", " ").title()
                dimension_gaps.append(f"{dim_label} gap: {abs(diff)} points")

        distance = math.sqrt(sum_sq)

        # Classify level
        if distance > 90:
            level = "CRITICAL"
        elif distance > 60:
            level = "HIGH"
        elif distance >= 30:
            level = "MEDIUM"
        else:
            level = "LOW"

        return CulturalRisk(level=level, distance=round(distance, 2), dimension_gaps=dimension_gaps)

    def compute_compliance_risk(self, candidate: dict, signals: list) -> ComplianceRisk:
        """Assess sanctions and reputational compliance risk.

        Scans signals for:
          - Sanctions keywords: OFAC, sanctioned, SDN list, restricted entity
          - Controversy keywords: lawsuit, investigation, fraud, scandal, fired, terminated

        Args:
            candidate: Candidate profile dict (used for context/future extension).
            signals: List of signal text strings to scan.

        Returns:
            ComplianceRisk with sanctions level, reputational level, and triggering sources.
        """
        if not signals:
            return ComplianceRisk(
                sanctions="INSUFFICIENT_DATA",
                reputational="INSUFFICIENT_DATA",
                sources=[],
            )

        sanctions_level = "CLEAR"
        reputational_level = "CLEAR"
        triggered_sources = []

        for signal in signals:
            signal_lower = signal.lower()

            # Check sanctions keywords
            for keyword in SANCTIONS_KEYWORDS:
                if keyword in signal_lower:
                    sanctions_level = "CRITICAL"
                    if signal not in triggered_sources:
                        triggered_sources.append(signal)
                    break

            # Check controversy keywords
            for keyword in CONTROVERSY_KEYWORDS:
                if keyword in signal_lower:
                    reputational_level = "HIGH"
                    if signal not in triggered_sources:
                        triggered_sources.append(signal)
                    break

        return ComplianceRisk(
            sanctions=sanctions_level,
            reputational=reputational_level,
            sources=triggered_sources,
        )

    def estimate_notice_period(self, country: str, seniority: str,
                               notice_data: dict, noncompete_data: dict) -> NoticePeriod:
        """Estimate contractual availability timeline.

        Looks up notice period and non-compete enforceability by country and seniority.

        Non-compete months by enforceability:
          enforceable: VP=6, C_SUITE=12, DIRECTOR=3
          limited: VP=3, C_SUITE=6, DIRECTOR=0
          unenforceable: all=0

        Args:
            country: ISO country code.
            seniority: One of VP, C_SUITE, DIRECTOR.
            notice_data: Dict[country][seniority] → notice_months.
            noncompete_data: Dict[country] → enforceability string.

        Returns:
            NoticePeriod with timeline and confidence assessment.
        """
        # Look up notice months
        country_notice = notice_data.get(country, {})
        if isinstance(country_notice, dict):
            notice_months = country_notice.get(seniority, 3)
        else:
            notice_months = 3

        # Look up non-compete enforceability
        enforceability = noncompete_data.get(country, "limited")

        # Determine non-compete months based on enforceability and seniority
        if enforceability == "enforceable":
            nc_months_map = {"VP": 6, "C_SUITE": 12, "DIRECTOR": 3}
            non_compete_months = nc_months_map.get(seniority, 3)
            enforceable = True
        elif enforceability == "unenforceable":
            non_compete_months = 0
            enforceable = False
        else:  # "limited" or unknown
            nc_months_map = {"VP": 3, "C_SUITE": 6, "DIRECTOR": 0}
            non_compete_months = nc_months_map.get(seniority, 0)
            enforceable = False

        # Compute earliest availability
        earliest_available_months = notice_months + non_compete_months

        # Determine confidence level
        if country in KNOWN_RULES_COUNTRIES:
            confidence = "HIGH"
        elif country in COMMON_LAW_COUNTRIES:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return NoticePeriod(
            notice_months=notice_months,
            non_compete_months=non_compete_months,
            earliest_available_months=earliest_available_months,
            enforceable=enforceable,
            confidence=confidence,
        )
