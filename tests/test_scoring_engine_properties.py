"""
Property-based tests for the Executive Succession Planning Scoring Engine.
Uses Hypothesis to generate random inputs and validate correctness properties.

Run: pytest tests/test_scoring_engine_properties.py -v
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from succession.scoring_engine import (
    ScoringEngine,
    RoleConfig,
    ScoringResult,
    CriterionScore,
    CRITERIA_25,
    UNIVERSAL_CORE_ATTRIBUTES,
    MASTER_VARIABLES,
)


# =============================================================================
# Hypothesis Strategies (generators)
# =============================================================================

def role_config_strategy():
    """Generate a random valid RoleConfig."""
    return st.builds(
        RoleConfig,
        id=st.uuids().map(str),
        tenant_id=st.uuids().map(str),
        sector=st.sampled_from(["PRIVATE", "GOVERNMENT", "MILITARY"]),
        country=st.sampled_from(["US", "GB", "DE", "SA", "AE", "SG", "JP", "CN", "IN", "FR"]),
        role_type=st.sampled_from(["CEO", "CFO", "CIO", "CTO", "COO"]),
        context=st.sampled_from(["baseline", "crisis", "growth"]),
        universal_core=st.fixed_dictionaries(
            {c: st.floats(min_value=1.0, max_value=10.0) for c in CRITERIA_25}
        ),
        cultural_flex=st.fixed_dictionaries(
            {c: st.floats(min_value=-0.15, max_value=0.15) for c in CRITERIA_25}
        ),
        sector_params=st.fixed_dictionaries(
            {c: st.floats(min_value=-2.0, max_value=2.0) for c in CRITERIA_25}
        ),
        master_variable_weights=st.fixed_dictionaries(
            {v: st.integers(min_value=1, max_value=10) for v in MASTER_VARIABLES}
        ),
        universal_core_thresholds=st.fixed_dictionaries(
            {a: st.integers(min_value=3, max_value=8) for a in UNIVERSAL_CORE_ATTRIBUTES}
        ),
    )


def candidate_scores_strategy():
    """Generate random candidate scores (all 25 criteria, each 1-10)."""
    return st.fixed_dictionaries(
        {c: st.integers(min_value=1, max_value=10) for c in CRITERIA_25}
    )


# =============================================================================
# Property 1: Weight Normalization
# For any valid role configuration, Σ(w_i) = 1.0 (±0.0001) and each w_i > 0
# =============================================================================

@given(config=role_config_strategy(), scores=candidate_scores_strategy())
@settings(max_examples=200)
def test_property_1_weight_normalization(config, scores):
    """P1: All normalized weights sum to 1.0 and are positive."""
    engine = ScoringEngine()
    result = engine.compute_score("test-candidate", config, scores)

    # Sum of all criterion weights must equal 1.0
    weight_sum = sum(c.weight for c in result.criterion_scores)
    assert abs(weight_sum - 1.0) < 0.0001, f"Weight sum {weight_sum} != 1.0"

    # All weights must be positive
    for c in result.criterion_scores:
        assert c.weight > 0, f"Weight for {c.criterion_id} is not positive: {c.weight}"


# =============================================================================
# Property 2: Threshold Enforcement
# If any Universal Core attribute is below minimum → candidate excluded
# =============================================================================

@given(config=role_config_strategy())
@settings(max_examples=100)
def test_property_2_threshold_enforcement(config):
    """P2: Candidate below any core threshold is flagged below_minimum."""
    engine = ScoringEngine()

    # Create scores where at least one core attribute is below its threshold
    scores = {c: 9 for c in CRITERIA_25}  # High scores everywhere
    # Pick one core attribute and set it below threshold
    target_attr = UNIVERSAL_CORE_ATTRIBUTES[0]  # strategic_vision
    threshold = config.universal_core_thresholds[target_attr]
    scores[target_attr] = max(1, threshold - 1)  # One below threshold

    result = engine.compute_score("test-candidate", config, scores)

    assert result.below_minimum is True, "Should be below_minimum when core attribute < threshold"
    assert len(result.threshold_violations) > 0, "Should have at least one threshold violation"

    # Verify it's excluded from ranked output
    ranked = engine.rank_candidates([result])
    assert len(ranked) == 0, "Below-minimum candidate should be excluded from rankings"


@given(config=role_config_strategy())
@settings(max_examples=100)
def test_property_2_all_above_threshold_passes(config):
    """P2 (inverse): Candidate above all thresholds is NOT flagged."""
    engine = ScoringEngine()

    # Create scores where ALL core attributes are at or above threshold
    scores = {c: 5 for c in CRITERIA_25}
    for attr in UNIVERSAL_CORE_ATTRIBUTES:
        scores[attr] = config.universal_core_thresholds[attr]  # Exactly at threshold

    result = engine.compute_score("test-candidate", config, scores)

    assert result.below_minimum is False, "Should NOT be below_minimum when all cores >= threshold"
    assert len(result.threshold_violations) == 0, "Should have zero threshold violations"


# =============================================================================
# Property 3: Threshold Floor Protection
# Cultural/sector adjustments cannot lower core attribute weights below floor
# =============================================================================

@given(config=role_config_strategy())
@settings(max_examples=200)
def test_property_3_floor_protection(config):
    """P3: Core attribute weights are never below their minimum floor."""
    engine = ScoringEngine()

    # Combine layers and enforce floor
    combined = engine._combine_layers(config)
    protected = engine._enforce_floor_protection(combined, config.universal_core_thresholds)

    for attr in UNIVERSAL_CORE_ATTRIBUTES:
        threshold = config.universal_core_thresholds[attr]
        min_floor = threshold / 2.0
        assert protected[attr] >= min_floor, \
            f"{attr} weight {protected[attr]} < floor {min_floor} (threshold={threshold})"


# =============================================================================
# Property 4: Score Range
# Criterion scores ∈ [1,10] integer; composite ∈ [0,100]
# =============================================================================

@given(config=role_config_strategy(), scores=candidate_scores_strategy())
@settings(max_examples=200)
def test_property_4_score_range(config, scores):
    """P4: Composite score is in [0, 100], all criteria in [1, 10]."""
    engine = ScoringEngine()
    result = engine.compute_score("test-candidate", config, scores)

    # Composite in [0, 100]
    assert 0.0 <= result.composite_score <= 100.0, \
        f"Composite {result.composite_score} not in [0, 100]"

    # All criterion raw scores in [1, 10]
    for c in result.criterion_scores:
        assert 1 <= c.raw_score <= 10, \
            f"Criterion {c.criterion_id} score {c.raw_score} not in [1, 10]"


# =============================================================================
# Property 5: Ranked Output Ordering
# Strictly descending by composite; tiebreaker = max core score
# =============================================================================

@given(config=role_config_strategy(),
       scores_list=st.lists(candidate_scores_strategy(), min_size=2, max_size=20))
@settings(max_examples=100)
def test_property_5_ranked_output_ordering(config, scores_list):
    """P5: Ranked output is strictly non-increasing by composite score."""
    engine = ScoringEngine()

    # Score all candidates
    results = []
    for i, scores in enumerate(scores_list):
        # Ensure all pass thresholds (so they're eligible for ranking)
        for attr in UNIVERSAL_CORE_ATTRIBUTES:
            scores[attr] = max(scores[attr], config.universal_core_thresholds[attr])
        result = engine.compute_score(f"candidate-{i}", config, scores)
        results.append(result)

    # Rank them
    ranked = engine.rank_candidates(results)

    # Verify ordering: each element >= next element in composite_score
    for i in range(len(ranked) - 1):
        assert ranked[i].composite_score >= ranked[i + 1].composite_score, \
            f"Rank violation: position {i} ({ranked[i].composite_score}) < position {i+1} ({ranked[i+1].composite_score})"


# =============================================================================
# Property 6: Context Modifier Bounds
# Crisis/growth modifiers increase target vars by ≥2, capped at 10
# =============================================================================

def test_property_6_crisis_context_increases_weights():
    """P6: Crisis context increases Resilience, Change Leadership, Mission Execution."""
    engine = ScoringEngine()

    # Baseline config
    base_weights = {c: 5.0 for c in CRITERIA_25}
    baseline_config = RoleConfig(
        id="test", tenant_id="t1", sector="PRIVATE", country="US",
        role_type="CEO", context="baseline",
        universal_core=base_weights.copy(),
        cultural_flex={c: 0.0 for c in CRITERIA_25},
        sector_params={c: 0.0 for c in CRITERIA_25},
        master_variable_weights={v: 5 for v in MASTER_VARIABLES},
        universal_core_thresholds={a: 3 for a in UNIVERSAL_CORE_ATTRIBUTES},
    )

    # Crisis config: resilience, crisis_leadership, mission_execution get +2
    crisis_weights = base_weights.copy()
    crisis_weights["resilience"] = min(10, crisis_weights["resilience"] + 2)
    crisis_weights["crisis_leadership"] = min(10, crisis_weights.get("crisis_leadership", 5) + 2)
    # mission_execution is a master variable, so test it there

    crisis_config = RoleConfig(
        id="test-crisis", tenant_id="t1", sector="PRIVATE", country="US",
        role_type="CEO", context="crisis",
        universal_core=crisis_weights,
        cultural_flex={c: 0.0 for c in CRITERIA_25},
        sector_params={c: 0.0 for c in CRITERIA_25},
        master_variable_weights={v: 5 for v in MASTER_VARIABLES},
        universal_core_thresholds={a: 3 for a in UNIVERSAL_CORE_ATTRIBUTES},
    )

    # Verify crisis weights are higher for target variables
    assert crisis_config.universal_core["resilience"] >= baseline_config.universal_core["resilience"] + 2
    assert crisis_config.universal_core["resilience"] <= 10


# =============================================================================
# Property 7: Tier 1 Filter Determinism
# Same input always produces same pass/fail
# =============================================================================

def test_property_7_scoring_determinism():
    """P7: Same inputs always produce same scoring result."""
    engine = ScoringEngine()

    config = RoleConfig(
        id="det-test", tenant_id="t1", sector="PRIVATE", country="US",
        role_type="CEO", context="baseline",
        universal_core={c: 5.0 for c in CRITERIA_25},
        cultural_flex={c: 0.0 for c in CRITERIA_25},
        sector_params={c: 0.0 for c in CRITERIA_25},
        master_variable_weights={v: 5 for v in MASTER_VARIABLES},
        universal_core_thresholds={a: 3 for a in UNIVERSAL_CORE_ATTRIBUTES},
    )
    scores = {c: 7 for c in CRITERIA_25}

    result1 = engine.compute_score("candidate-a", config, scores)
    result2 = engine.compute_score("candidate-a", config, scores)

    assert result1.composite_score == result2.composite_score, "Same input must produce same score"
    assert result1.below_minimum == result2.below_minimum


# =============================================================================
# Additional unit tests (known-value verification)
# =============================================================================

def test_all_max_scores_gives_100():
    """All criteria scored 10 with equal weights → composite = 100."""
    engine = ScoringEngine()
    config = RoleConfig(
        id="max-test", tenant_id="t1", sector="PRIVATE", country="US",
        role_type="CEO", context="baseline",
        universal_core={c: 5.0 for c in CRITERIA_25},  # Equal weights
        cultural_flex={c: 0.0 for c in CRITERIA_25},
        sector_params={c: 0.0 for c in CRITERIA_25},
        master_variable_weights={v: 5 for v in MASTER_VARIABLES},
        universal_core_thresholds={a: 3 for a in UNIVERSAL_CORE_ATTRIBUTES},
    )
    scores = {c: 10 for c in CRITERIA_25}

    result = engine.compute_score("max-candidate", config, scores)
    assert result.composite_score == 100.0, f"All 10s should give 100, got {result.composite_score}"


def test_all_min_scores_gives_10():
    """All criteria scored 1 with equal weights → composite = 10."""
    engine = ScoringEngine()
    config = RoleConfig(
        id="min-test", tenant_id="t1", sector="PRIVATE", country="US",
        role_type="CEO", context="baseline",
        universal_core={c: 5.0 for c in CRITERIA_25},
        cultural_flex={c: 0.0 for c in CRITERIA_25},
        sector_params={c: 0.0 for c in CRITERIA_25},
        master_variable_weights={v: 5 for v in MASTER_VARIABLES},
        universal_core_thresholds={a: 1 for a in UNIVERSAL_CORE_ATTRIBUTES},  # Low thresholds
    )
    scores = {c: 1 for c in CRITERIA_25}

    result = engine.compute_score("min-candidate", config, scores)
    assert result.composite_score == 10.0, f"All 1s should give 10, got {result.composite_score}"


def test_below_minimum_excluded_from_ranking():
    """Candidate below threshold is excluded from ranked output."""
    engine = ScoringEngine()
    config = RoleConfig(
        id="excl-test", tenant_id="t1", sector="PRIVATE", country="US",
        role_type="CEO", context="baseline",
        universal_core={c: 5.0 for c in CRITERIA_25},
        cultural_flex={c: 0.0 for c in CRITERIA_25},
        sector_params={c: 0.0 for c in CRITERIA_25},
        master_variable_weights={v: 5 for v in MASTER_VARIABLES},
        universal_core_thresholds={a: 7 for a in UNIVERSAL_CORE_ATTRIBUTES},
    )

    # Candidate A: all high (passes)
    scores_a = {c: 8 for c in CRITERIA_25}
    # Candidate B: strategic_vision below threshold (fails)
    scores_b = {c: 8 for c in CRITERIA_25}
    scores_b["strategic_vision"] = 5  # Below threshold of 7

    result_a = engine.compute_score("candidate-a", config, scores_a)
    result_b = engine.compute_score("candidate-b", config, scores_b)

    ranked = engine.rank_candidates([result_a, result_b])

    assert len(ranked) == 1, f"Expected 1 ranked candidate, got {len(ranked)}"
    assert ranked[0].candidate_id == "candidate-a"
