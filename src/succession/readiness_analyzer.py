"""
Executive Succession Planning — Readiness Analyzer

Computes gap heatmaps, time-to-readiness estimates, development costs,
and ROI projections for succession candidates against target role requirements.

Correctness Properties:
  P5: months >= 0 always (no negative time-to-readiness)
  P6: more/larger gaps → equal or higher months (monotonicity)
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import CRITERIA_25 from scoring engine; define locally as fallback
try:
    from src.succession.scoring_engine import CRITERIA_25
except ImportError:
    CRITERIA_25 = [
        # 12 Personal Attributes
        "strategic_vision", "integrity", "cognitive_ability", "resilience",
        "results_orientation", "emotional_intelligence", "adaptability",
        "self_awareness", "learning_agility", "executive_presence",
        "decisiveness", "energy_drive",
        # 13 Professional Attributes
        "industry_expertise", "functional_excellence", "financial_acumen",
        "digital_fluency", "global_perspective", "talent_development",
        "stakeholder_management", "board_governance", "crisis_leadership",
        "innovation_leadership", "change_management", "customer_centricity",
        "operational_excellence",
    ]


# =============================================================================
# Constants
# =============================================================================

# Criterion classification for development velocity
SKILLS_CRITERIA = [
    'functional_excellence', 'financial_acumen', 'digital_fluency',
    'industry_expertise', 'operational_excellence',
]

BEHAVIORAL_CRITERIA = [
    'emotional_intelligence', 'adaptability', 'self_awareness',
    'learning_agility', 'executive_presence', 'energy_drive',
]

EXPERIENCE_CRITERIA = [
    'board_governance', 'crisis_leadership', 'global_perspective',
    'talent_development', 'stakeholder_management',
]

# Months per score point to close a gap
VELOCITY = {
    'skills': 3,
    'behavioral': 6,
    'experience': 12,
}

# Concurrency factor (multiple gaps developed in parallel)
CONCURRENCY_FACTOR = 0.6

# Max months (cap)
MAX_TTR_MONTHS = 36

# Development cost assumptions (USD)
COST_COACHING_PER_QUARTER = 25000
COST_INTERNATIONAL_ROTATION = 150000
COST_UPSKILLING_PROGRAM = 10000
COST_BOARD_PROGRAM_PER_YEAR = 50000


# =============================================================================
# Data Types
# =============================================================================

@dataclass
class GapCell:
    """A single criterion gap analysis result."""
    criterion_id: str
    candidate_score: int
    requirement: int
    gap: int
    category: str  # EXCEEDS, MEETS, DEVELOPMENT_NEEDED, CRITICAL_GAP


@dataclass
class ReadinessEstimate:
    """Time-to-readiness projection."""
    months: int
    category: str  # READY_NOW, NEAR_READY, DEVELOPING, LONG_TERM, BEYOND_HORIZON


@dataclass
class ROIEstimate:
    """Return on investment projection for development."""
    percentage: float
    breakeven_months: int
    is_negative: bool


# =============================================================================
# Readiness Analyzer
# =============================================================================

class ReadinessAnalyzer:
    """Analyzes candidate readiness against role requirements.

    Computes gap heatmaps, time-to-readiness, development costs, and ROI.
    """

    def compute_gap_heatmap(self, candidate_scores: dict, role_requirements: dict) -> list[GapCell]:
        """Compute gap analysis for all 25 criteria.

        Args:
            candidate_scores: {criterion_id: score (1-10)}
            role_requirements: {criterion_id: required_score (1-10)}

        Returns:
            List of 25 GapCell objects with gap categorization.
        """
        cells = []
        for criterion in CRITERIA_25:
            requirement = role_requirements.get(criterion, 7)
            candidate_score = candidate_scores.get(criterion, 5)
            gap = requirement - candidate_score

            if gap <= -2:
                category = "EXCEEDS"
            elif gap <= 1:
                category = "MEETS"
            elif gap <= 3:
                category = "DEVELOPMENT_NEEDED"
            else:
                category = "CRITICAL_GAP"

            cells.append(GapCell(
                criterion_id=criterion,
                candidate_score=candidate_score,
                requirement=requirement,
                gap=gap,
                category=category,
            ))

        return cells

    def compute_fit_percentage(self, gaps: list[GapCell]) -> float:
        """Compute overall fit percentage from gap heatmap.

        Returns:
            Percentage of criteria where candidate EXCEEDS or MEETS requirement.
        """
        if not gaps:
            return 0.0
        meets_or_exceeds = sum(
            1 for g in gaps if g.category in ("EXCEEDS", "MEETS")
        )
        return meets_or_exceeds / len(gaps) * 100

    def compute_time_to_readiness(self, gaps: list[GapCell]) -> ReadinessEstimate:
        """Estimate months to readiness based on development gaps.

        For each gap requiring development, applies velocity rates based on
        criterion type (skills=3mo/pt, behavioral=6mo/pt, experience=12mo/pt).
        Applies concurrency factor and caps at MAX_TTR_MONTHS.

        Args:
            gaps: List of GapCell objects from compute_gap_heatmap.

        Returns:
            ReadinessEstimate with months and readiness category.
        """
        total_months = 0

        for gap_cell in gaps:
            if gap_cell.category not in ("DEVELOPMENT_NEEDED", "CRITICAL_GAP"):
                continue

            # Determine velocity based on criterion type
            velocity = self._get_velocity(gap_cell.criterion_id)
            months_for_gap = gap_cell.gap * velocity
            total_months += months_for_gap

        # Apply concurrency factor
        adjusted = round(total_months * CONCURRENCY_FACTOR)

        # Cap at maximum
        capped = min(adjusted, MAX_TTR_MONTHS)

        # Ensure non-negative (Property P5)
        capped = max(capped, 0)

        # Determine category
        category = self._classify_readiness(capped, adjusted)

        return ReadinessEstimate(months=capped, category=category)

    def compute_development_cost(self, gaps: list[GapCell], ttr_months: int) -> float:
        """Estimate total development cost based on gap types.

        Args:
            gaps: List of GapCell objects.
            ttr_months: Time-to-readiness in months.

        Returns:
            Total development cost in USD.
        """
        total_cost = 0.0

        experience_gaps = []
        behavioral_gaps = []
        skills_gaps = []

        for gap_cell in gaps:
            if gap_cell.category not in ("DEVELOPMENT_NEEDED", "CRITICAL_GAP"):
                continue

            if gap_cell.criterion_id in EXPERIENCE_CRITERIA:
                experience_gaps.append(gap_cell)
            elif gap_cell.criterion_id in BEHAVIORAL_CRITERIA:
                behavioral_gaps.append(gap_cell)
            else:
                skills_gaps.append(gap_cell)

        # Experience gaps: board program cost
        if experience_gaps:
            total_cost += COST_BOARD_PROGRAM_PER_YEAR * (ttr_months / 12)

        # Behavioral gaps: coaching cost
        if behavioral_gaps:
            total_cost += COST_COACHING_PER_QUARTER * (ttr_months / 3)

        # Skills gaps: upskilling per gap
        if skills_gaps:
            total_cost += COST_UPSKILLING_PROGRAM * len(skills_gaps)

        # International rotation if global_perspective gap exists
        needs_global = any(
            g.criterion_id == 'global_perspective'
            for g in gaps
            if g.category in ("DEVELOPMENT_NEEDED", "CRITICAL_GAP")
        )
        if needs_global:
            total_cost += COST_INTERNATIONAL_ROTATION

        return total_cost

    def compute_roi(self, role_annual_value: float, acquisition_cost: float, dev_cost: float) -> ROIEstimate:
        """Compute ROI estimate for candidate development investment.

        Args:
            role_annual_value: Annual value of the role (revenue impact).
            acquisition_cost: Cost to acquire/retain the candidate.
            dev_cost: Development cost from compute_development_cost.

        Returns:
            ROIEstimate with percentage, breakeven months, and negativity flag.
        """
        total_investment = acquisition_cost + dev_cost

        if total_investment == 0:
            return ROIEstimate(percentage=0.0, breakeven_months=0, is_negative=False)

        roi = (role_annual_value - total_investment) / total_investment * 100
        is_negative = roi < 0

        if role_annual_value > 0:
            breakeven_months = round(total_investment / (role_annual_value / 12))
        else:
            breakeven_months = 999

        return ROIEstimate(
            percentage=roi,
            breakeven_months=breakeven_months,
            is_negative=is_negative,
        )

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _get_velocity(self, criterion_id: str) -> int:
        """Get development velocity (months per score point) for a criterion."""
        if criterion_id in SKILLS_CRITERIA:
            return VELOCITY['skills']
        elif criterion_id in BEHAVIORAL_CRITERIA:
            return VELOCITY['behavioral']
        elif criterion_id in EXPERIENCE_CRITERIA:
            return VELOCITY['experience']
        else:
            # Default to skills velocity
            return VELOCITY['skills']

    def _classify_readiness(self, capped_months: int, raw_adjusted: int) -> str:
        """Classify readiness category based on months.

        Uses raw_adjusted (before cap) to detect BEYOND_HORIZON.
        """
        if raw_adjusted > MAX_TTR_MONTHS:
            return "BEYOND_HORIZON"
        if capped_months == 0:
            return "READY_NOW"
        elif capped_months <= 6:
            return "NEAR_READY"
        elif capped_months <= 18:
            return "DEVELOPING"
        elif capped_months <= 36:
            return "LONG_TERM"
        else:
            return "BEYOND_HORIZON"
