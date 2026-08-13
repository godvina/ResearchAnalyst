"""
Property-based tests for Executive Compensation Intelligence.
Uses Hypothesis to validate correctness properties across randomized inputs.

Run: pytest tests/test_compensation_intelligence_properties.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime, timedelta, timezone
from itertools import permutations

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from succession.compensation_engine import CompensationEngine, CompEstimate, CompGap
from succession.risk_analyzer import RiskAnalyzer, HOFSTEDE_DIMENSIONS
from succession.readiness_analyzer import (
    ReadinessAnalyzer,
    CRITERIA_25,
    GapCell,
)
from succession.process_tracker import (
    ProcessTracker,
    STAGE_ORDER,
    DEFAULT_SLA,
)


# =============================================================================
# Property 1: Total comp = sum of parts
# =============================================================================

@given(
    base=st.floats(min_value=50000, max_value=1000000),
    bonus_pct=st.floats(min_value=0, max_value=200),
    equity=st.floats(min_value=0, max_value=5000000),
    benefits=st.floats(min_value=0, max_value=100000),
)
@settings(max_examples=200)
def test_total_comp_sum_of_parts(base, bonus_pct, equity, benefits):
    """P1: Total compensation must equal base + bonus + equity + benefits + allowances (within $1)."""
    engine = CompensationEngine()

    # Build a mock lookup entry, call compute_total_comp, verify total == sum of components ± $1
    lookup_key = "TECH_US_VP"
    lookup = {
        lookup_key: {
            "base": {"p50": base},
            "bonus_pct": {"p50": bonus_pct},
            "equity": {"p50": equity},
            "benefits": benefits,
            "allowances": {},
        }
    }
    candidate = {"sector": "TECH", "country": "US", "seniority": "VP"}

    result = engine.compute_total_comp(candidate, lookup)

    expected_bonus = base * (bonus_pct / 100)
    expected_total = base + expected_bonus + equity + benefits

    assert abs(result.total - expected_total) <= 1.0, (
        f"Total {result.total} != expected {expected_total} "
        f"(base={base}, bonus_pct={bonus_pct}, equity={equity}, benefits={benefits})"
    )


# =============================================================================
# Property 2: Gap sign matches label
# =============================================================================

@given(
    candidate_comp=st.floats(min_value=100000, max_value=5000000),
    role_p50=st.floats(min_value=100000, max_value=5000000),
)
@settings(max_examples=200)
def test_gap_label_matches_sign(candidate_comp, role_p50):
    """P2: Positive gap → PREMIUM_REQUIRED, negative/zero gap → BELOW_MARKET."""
    engine = CompensationEngine()

    gap = engine.compute_comp_gap(candidate_comp, role_p50)

    if gap.amount > 0:
        assert gap.label == "PREMIUM_REQUIRED", (
            f"Positive gap {gap.amount} should be PREMIUM_REQUIRED, got {gap.label}"
        )
    elif gap.amount < 0:
        assert gap.label == "BELOW_MARKET", (
            f"Negative gap {gap.amount} should be BELOW_MARKET, got {gap.label}"
        )
    else:
        # Edge case: zero gap treated as not premium
        assert gap.label == "BELOW_MARKET", (
            f"Zero gap should be BELOW_MARKET, got {gap.label}"
        )


# =============================================================================
# Property 3: Risk scores bounded [0, 100]
# =============================================================================

@given(
    years=st.floats(min_value=0, max_value=30),
    instability=st.floats(min_value=0, max_value=1),
    comp_below=st.floats(min_value=0, max_value=1),
    promotions=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=200)
def test_flight_risk_bounded(years, instability, comp_below, promotions):
    """P3a: Flight risk score must be 0 <= x <= 100."""
    analyzer = RiskAnalyzer()

    candidate = {
        "years_in_role": years,
        "org_instability": instability,
        "comp_below_market": comp_below,
        "promotions_last_5yr": promotions,
    }

    flight_risk = analyzer.compute_flight_risk(candidate)
    assert 0 <= flight_risk.score <= 100, (
        f"Flight risk score {flight_risk.score} out of bounds [0, 100]"
    )


@given(
    comp_gap_pct=st.floats(min_value=-100, max_value=100),
    years_to_ret=st.floats(min_value=0, max_value=40),
    org_changes=st.integers(min_value=0, max_value=10),
    instability=st.floats(min_value=0, max_value=1),
)
@settings(max_examples=200)
def test_poachability_bounded(comp_gap_pct, years_to_ret, org_changes, instability):
    """P3b: Poachability score must be 0 <= x <= 100."""
    analyzer = RiskAnalyzer()

    candidate = {
        "years_to_retirement": years_to_ret,
        "org_changes_15yr": org_changes,
        "org_instability": instability,
    }

    poachability = analyzer.compute_poachability(candidate, comp_gap_pct=comp_gap_pct)
    assert 0 <= poachability.score <= 100, (
        f"Poachability score {poachability.score} out of bounds [0, 100]"
    )


# =============================================================================
# Property 4: Cultural distance symmetry
# =============================================================================

# Representative Hofstede profiles for testing symmetry
HOFSTEDE_PROFILES = {
    "US": {"power_distance": 40, "individualism": 91, "masculinity": 62,
            "uncertainty_avoidance": 46, "long_term_orientation": 26, "indulgence": 68},
    "JP": {"power_distance": 54, "individualism": 46, "masculinity": 95,
            "uncertainty_avoidance": 92, "long_term_orientation": 88, "indulgence": 42},
    "DE": {"power_distance": 35, "individualism": 67, "masculinity": 66,
            "uncertainty_avoidance": 65, "long_term_orientation": 83, "indulgence": 40},
    "SA": {"power_distance": 95, "individualism": 25, "masculinity": 60,
            "uncertainty_avoidance": 80, "long_term_orientation": 36, "indulgence": 52},
    "GB": {"power_distance": 35, "individualism": 89, "masculinity": 66,
            "uncertainty_avoidance": 35, "long_term_orientation": 51, "indulgence": 69},
    "CN": {"power_distance": 80, "individualism": 20, "masculinity": 66,
            "uncertainty_avoidance": 30, "long_term_orientation": 87, "indulgence": 24},
    "IN": {"power_distance": 77, "individualism": 48, "masculinity": 56,
            "uncertainty_avoidance": 40, "long_term_orientation": 51, "indulgence": 26},
    "SG": {"power_distance": 74, "individualism": 20, "masculinity": 48,
            "uncertainty_avoidance": 8, "long_term_orientation": 72, "indulgence": 46},
    "FR": {"power_distance": 68, "individualism": 71, "masculinity": 43,
            "uncertainty_avoidance": 86, "long_term_orientation": 63, "indulgence": 48},
    "AE": {"power_distance": 90, "individualism": 25, "masculinity": 50,
            "uncertainty_avoidance": 80, "long_term_orientation": 23, "indulgence": 43},
}


def test_cultural_distance_symmetry():
    """P4: Cultural distance(A→B) == distance(B→A) for all pairs."""
    analyzer = RiskAnalyzer()
    countries = list(HOFSTEDE_PROFILES.keys())

    for i, country_a in enumerate(countries):
        for country_b in countries[i + 1:]:
            risk_ab = analyzer.compute_cultural_risk(country_a, country_b, HOFSTEDE_PROFILES)
            risk_ba = analyzer.compute_cultural_risk(country_b, country_a, HOFSTEDE_PROFILES)

            assert risk_ab.distance == risk_ba.distance, (
                f"Asymmetric distance: {country_a}→{country_b} = {risk_ab.distance}, "
                f"{country_b}→{country_a} = {risk_ba.distance}"
            )


# =============================================================================
# Property 5: TTR non-negative
# =============================================================================

@given(
    scores=st.dictionaries(
        st.sampled_from(CRITERIA_25),
        st.integers(min_value=1, max_value=10),
        min_size=25,
        max_size=25,
    ),
)
@settings(max_examples=200)
def test_ttr_non_negative(scores):
    """P5: Time-to-readiness must always be >= 0 months."""
    analyzer = ReadinessAnalyzer()

    # Use fixed high requirements so gaps are generated
    role_requirements = {c: 9 for c in CRITERIA_25}

    gaps = analyzer.compute_gap_heatmap(scores, role_requirements)
    ttr = analyzer.compute_time_to_readiness(gaps)

    assert ttr.months >= 0, (
        f"TTR is negative: {ttr.months} months"
    )


# =============================================================================
# Property 6: TTR monotonicity
# =============================================================================

def test_ttr_monotonic():
    """P6: Larger gaps produce equal or higher TTR than smaller gaps."""
    analyzer = ReadinessAnalyzer()

    # Create two gap sets: one with small gaps, one with larger gaps
    small_gap_scores = {c: 7 for c in CRITERIA_25}
    small_gap_reqs = {c: 8 for c in CRITERIA_25}

    large_gap_scores = {c: 4 for c in CRITERIA_25}
    large_gap_reqs = {c: 8 for c in CRITERIA_25}

    small_gaps = analyzer.compute_gap_heatmap(small_gap_scores, small_gap_reqs)
    large_gaps = analyzer.compute_gap_heatmap(large_gap_scores, large_gap_reqs)

    ttr_small = analyzer.compute_time_to_readiness(small_gaps)
    ttr_large = analyzer.compute_time_to_readiness(large_gaps)

    # Assert larger_ttr >= smaller_ttr
    assert ttr_large.months >= ttr_small.months, (
        f"Monotonicity violated: larger gaps TTR ({ttr_large.months}) "
        f"< smaller gaps TTR ({ttr_small.months})"
    )


@given(
    base_scores=st.lists(
        st.integers(min_value=5, max_value=9),
        min_size=25, max_size=25,
    ),
    delta=st.integers(min_value=1, max_value=4),
)
@settings(max_examples=200)
def test_ttr_monotonic_hypothesis(base_scores, delta):
    """P6 (hypothesis): Uniformly worsening scores cannot decrease TTR."""
    analyzer = ReadinessAnalyzer()
    requirements = {c: 9 for c in CRITERIA_25}

    # Small gap scenario
    small_gap_scores = {CRITERIA_25[i]: base_scores[i] for i in range(25)}

    # Large gap scenario: reduce each score by delta (floor at 1)
    large_gap_scores = {
        CRITERIA_25[i]: max(1, base_scores[i] - delta) for i in range(25)
    }

    small_gaps = analyzer.compute_gap_heatmap(small_gap_scores, requirements)
    large_gaps = analyzer.compute_gap_heatmap(large_gap_scores, requirements)

    ttr_small = analyzer.compute_time_to_readiness(small_gaps)
    ttr_large = analyzer.compute_time_to_readiness(large_gaps)

    assert ttr_large.months >= ttr_small.months, (
        f"Monotonicity violated: larger gaps TTR ({ttr_large.months}) "
        f"< smaller gaps TTR ({ttr_small.months})"
    )


# =============================================================================
# Property 7: Stage ordering enforced
# =============================================================================

def test_stage_backward_raises():
    """P7: Moving a candidate backward in the pipeline raises ValueError."""
    tracker = ProcessTracker()
    tracker.advance_stage("c1", "LONG_LIST", user="user")
    tracker.advance_stage("c1", "SHORT_LIST", user="user")
    tracker.advance_stage("c1", "SCREEN", user="user")

    with pytest.raises(ValueError):
        tracker.advance_stage("c1", "LONG_LIST", user="user")  # backward!


def test_stage_same_raises():
    """P7: Advancing to the same stage raises ValueError."""
    tracker = ProcessTracker()
    tracker.advance_stage("c1", "LONG_LIST", user="user")
    tracker.advance_stage("c1", "SCREEN", user="user")

    with pytest.raises(ValueError):
        tracker.advance_stage("c1", "SCREEN", user="user")  # same stage!


def test_stage_invalid_rejected():
    """P7: Invalid stage names are rejected."""
    tracker = ProcessTracker()

    with pytest.raises(ValueError, match="Invalid stage"):
        tracker.advance_stage("c1", "INVALID_STAGE", user="user")


# =============================================================================
# Property 8: SLA breach correctness
# =============================================================================

def test_sla_breach_boundary():
    """P8: SLA breach boundary — at exactly sla_days: NOT breach (> not >=).
    At sla_days + 1: IS breach."""
    tracker = ProcessTracker()
    candidate_id = "test-candidate-boundary"

    tracker.advance_stage(candidate_id, "LONG_LIST", user="test")
    current = tracker.get_current_stage(candidate_id)

    # At exactly 14 days (SLA for LONG_LIST) — NOT a breach (> not >=)
    current.entered_at = datetime.now(timezone.utc) - timedelta(days=14)
    sla_status = tracker.check_sla(candidate_id)
    assert sla_status.is_breach is False, (
        f"Exactly at SLA boundary (14 days) should NOT breach, "
        f"got is_breach={sla_status.is_breach}"
    )

    # At sla_days + 1 = 15 days — IS a breach
    current.entered_at = datetime.now(timezone.utc) - timedelta(days=15)
    sla_status = tracker.check_sla(candidate_id)
    assert sla_status.is_breach is True, (
        f"At SLA + 1 day (15 days) should breach, "
        f"got is_breach={sla_status.is_breach}"
    )


def test_sla_breach_under_limit():
    """P8: Days below SLA limit should NOT be a breach."""
    tracker = ProcessTracker()
    candidate_id = "test-candidate-sla"

    # Advance to LONG_LIST (SLA = 14 days)
    tracker.advance_stage(candidate_id, "LONG_LIST", user="test")
    current = tracker.get_current_stage(candidate_id)

    # Set entered_at to 13 days ago (should NOT breach: 13 <= 14)
    current.entered_at = datetime.now(timezone.utc) - timedelta(days=13)

    sla_status = tracker.check_sla(candidate_id)
    assert sla_status.is_breach is False, (
        f"Expected no SLA breach with 13 days in LONG_LIST (SLA=14), "
        f"got is_breach={sla_status.is_breach}, days_in_stage={sla_status.days_in_stage}"
    )
    assert sla_status.stage == "LONG_LIST"
    assert sla_status.sla_days == 14
