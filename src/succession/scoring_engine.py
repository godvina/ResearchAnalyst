"""
Executive Succession Planning — Scoring Engine

Implements the three-layer weighted scoring algorithm:
  Layer 1: Universal Core (base weights for 25 criteria)
  Layer 2: Cultural Flex (GLOBE/Hofstede adjustments, range 0.7-1.3)
  Layer 3: Sector Parameters (sector-specific adjustments)

Formula: Score = Σ(w_i × s_i) where w_i = normalize(Layer1 + Layer2_adj + Layer3_adj)

Correctness Properties:
  P1: Weight Normalization — Σ(w_i) = 1.0 (±0.0001), all w_i > 0
  P2: Threshold Enforcement — below minimum on any core attribute → excluded
  P3: Threshold Floor Protection — cultural/sector adjustments cannot lower core below floor
  P4: Score Range — criterion scores ∈ [1,10] integer; composite ∈ [0,100]
  P5: Ranked Output Ordering — strictly descending; tiebreaker = highest universal core score
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Data Types
# =============================================================================

@dataclass
class CriterionScore:
    """A single criterion evaluation for a candidate."""
    criterion_id: str
    name: str
    raw_score: int          # 1-10
    weight: float = 0.0     # Normalized, sum = 1.0 across all criteria
    weighted_score: float = 0.0
    layer1_weight: float = 0.0
    layer2_adjustment: float = 0.0
    layer3_adjustment: float = 0.0


@dataclass
class ThresholdViolation:
    """Records when a candidate fails a Universal Core threshold."""
    attribute: str
    score: int
    minimum_required: int


@dataclass
class ScoringResult:
    """Complete scoring output for a candidate."""
    candidate_id: str
    composite_score: float              # 0-100
    layer_breakdown: dict               # {universal_core: float, cultural_flex: float, sector_parameter: float}
    criterion_scores: list[CriterionScore]
    master_variable_scores: list[dict]  # 15 master variables
    threshold_violations: list[ThresholdViolation]
    below_minimum: bool
    model_version: str = "1.0.0"
    timestamp: str = ""
    scoring_decision_id: str = ""


@dataclass
class RoleConfig:
    """Weight configuration for a specific sector-country-role combination."""
    id: str
    tenant_id: str
    sector: str                 # PRIVATE, GOVERNMENT, MILITARY
    country: str                # ISO 3166-1 alpha-2
    role_type: str              # CEO, CFO, etc.
    context: str                # baseline, crisis, growth
    universal_core: dict        # {attribute_name: weight (1-10)}
    cultural_flex: dict         # {attribute_name: adjustment (-0.15 to +0.15)}
    sector_params: dict         # {attribute_name: adjustment}
    master_variable_weights: dict  # {variable_name: weight (1-10)}
    universal_core_thresholds: dict  # {attribute_name: minimum_score (1-10)}


# Universal Core Attributes (the 5 non-negotiable minimums)
UNIVERSAL_CORE_ATTRIBUTES = [
    "strategic_vision",
    "integrity",
    "cognitive_ability",
    "resilience",
    "results_orientation",
]

# All 25 Universal Selection Criteria
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

# 15 Master Variable Set
MASTER_VARIABLES = [
    "strategic_vision", "profit_value_orientation", "political_savvy",
    "innovation_tolerance", "stakeholder_consensus", "relationship_networks",
    "hierarchical_respect", "physical_fitness", "exam_test_rigor",
    "cultural_faith_ethics", "resilience", "mission_execution",
    "chain_of_command", "coalition_building", "emotional_intelligence",
]


# =============================================================================
# Scoring Engine
# =============================================================================

class ScoringEngine:
    """Three-layer weighted scoring algorithm for executive succession planning.

    Algorithm flow:
    1. Load role configuration (sector + country + role → weight profile)
    2. Retrieve candidate scores for all 25 criteria
    3. Apply Layer 1 universal core weights
    4. Apply Layer 2 cultural flex adjustments
    5. Apply Layer 3 sector parameter adjustments
    6. Enforce threshold floor protection (P3)
    7. Normalize weights: Σ(w_i) = 1.0 (P1)
    8. Compute composite: Score = Σ(w_i × s_i)
    9. Validate universal core thresholds (P2)
    10. Return scored result with full breakdown
    """

    def __init__(self, aurora_conn=None, graph_service=None):
        """Initialize with database connections.

        Args:
            aurora_conn: Aurora ConnectionManager for persisting scoring decisions.
            graph_service: SuccessionGraphService for retrieving candidate scores from Neptune.
        """
        self._db = aurora_conn
        self._graph = graph_service

    def compute_score(self, candidate_id: str, role_config: RoleConfig,
                      candidate_scores: dict[str, int]) -> ScoringResult:
        """Compute composite score for a single candidate.

        Args:
            candidate_id: UUID of the candidate.
            role_config: The role configuration with all three layers of weights.
            candidate_scores: Dict mapping criterion_name → score (1-10 integer).

        Returns:
            ScoringResult with full breakdown.
        """
        now = datetime.now(timezone.utc).isoformat()
        decision_id = str(uuid.uuid4())

        # Step 1: Combine three-layer weights
        combined_weights = self._combine_layers(role_config)

        # Step 2: Enforce threshold floor protection (Property 3)
        combined_weights = self._enforce_floor_protection(
            combined_weights, role_config.universal_core_thresholds
        )

        # Step 3: Normalize weights (Property 1: Σ = 1.0)
        normalized_weights = self._normalize_weights(combined_weights)

        # Step 4: Compute criterion scores
        criterion_results = []
        raw_weighted_sum = 0.0
        max_possible = 0.0

        for criterion in CRITERIA_25:
            raw_score = candidate_scores.get(criterion, 0)
            # Validate score range (Property 4: 1-10 integer)
            if raw_score < 1 or raw_score > 10:
                raw_score = max(1, min(10, raw_score))

            weight = normalized_weights.get(criterion, 0.0)
            weighted_score = weight * raw_score

            raw_weighted_sum += weighted_score
            max_possible += weight * 10  # Max score per criterion is 10

            criterion_results.append(CriterionScore(
                criterion_id=criterion,
                name=criterion.replace("_", " ").title(),
                raw_score=raw_score,
                weight=weight,
                weighted_score=weighted_score,
                layer1_weight=role_config.universal_core.get(criterion, 0),
                layer2_adjustment=role_config.cultural_flex.get(criterion, 0),
                layer3_adjustment=role_config.sector_params.get(criterion, 0),
            ))

        # Step 5: Normalize composite to 0-100 (Property 4)
        composite_score = (raw_weighted_sum / max_possible * 100) if max_possible > 0 else 0.0
        composite_score = round(min(100.0, max(0.0, composite_score)), 2)

        # Step 6: Check universal core thresholds (Property 2)
        threshold_violations = []
        for attr in UNIVERSAL_CORE_ATTRIBUTES:
            threshold = role_config.universal_core_thresholds.get(attr, 1)
            score = candidate_scores.get(attr, 0)
            if score < threshold:
                threshold_violations.append(ThresholdViolation(
                    attribute=attr,
                    score=score,
                    minimum_required=threshold,
                ))

        below_minimum = len(threshold_violations) > 0

        # Step 7: Compute layer breakdown (for explainability)
        layer_breakdown = self._compute_layer_breakdown(
            criterion_results, role_config
        )

        # Step 8: Compute master variable scores
        master_variable_scores = self._compute_master_variables(
            candidate_scores, role_config
        )

        result = ScoringResult(
            candidate_id=candidate_id,
            composite_score=composite_score,
            layer_breakdown=layer_breakdown,
            criterion_scores=criterion_results,
            master_variable_scores=master_variable_scores,
            threshold_violations=threshold_violations,
            below_minimum=below_minimum,
            model_version="1.0.0",
            timestamp=now,
            scoring_decision_id=decision_id,
        )

        return result

    def rank_candidates(self, candidates: list[ScoringResult]) -> list[ScoringResult]:
        """Rank candidates by composite score (Property 5: strictly descending).

        Tiebreaker: highest Universal Core attribute score.
        Excludes candidates with below_minimum = True.

        Args:
            candidates: List of scored candidates.

        Returns:
            Ranked list (descending composite score), excluding below-minimum candidates.
        """
        # Filter out below-minimum candidates
        eligible = [c for c in candidates if not c.below_minimum]

        # Sort: primary = composite_score (desc), tiebreaker = max core score (desc)
        eligible.sort(
            key=lambda c: (
                c.composite_score,
                self._get_max_core_score(c),
            ),
            reverse=True,
        )

        return eligible

    def compute_batch_scores(self, candidate_scores_map: dict[str, dict[str, int]],
                             role_config: RoleConfig) -> list[ScoringResult]:
        """Score multiple candidates for the same role configuration.

        Args:
            candidate_scores_map: Dict mapping candidate_id → {criterion: score}.
            role_config: Shared role configuration for all candidates.

        Returns:
            List of ScoringResults (unranked — call rank_candidates() to order).
        """
        results = []
        for candidate_id, scores in candidate_scores_map.items():
            result = self.compute_score(candidate_id, role_config, scores)
            results.append(result)
        return results

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    def _combine_layers(self, config: RoleConfig) -> dict[str, float]:
        """Combine all three layers into raw combined weights.

        Layer 1 (Universal Core): base weight (1-10 scale)
        Layer 2 (Cultural Flex): multiplicative adjustment (0.7-1.3)
        Layer 3 (Sector Params): additive adjustment

        Combined = Layer1_base * Layer2_flex_multiplier + Layer3_additive
        """
        combined = {}
        for criterion in CRITERIA_25:
            # Layer 1: base weight
            base = config.universal_core.get(criterion, 5.0)  # default 5 if not specified

            # Layer 2: cultural flex (multiplicative, range 0.7-1.3, default 1.0)
            flex = config.cultural_flex.get(criterion, 0.0)
            flex_multiplier = 1.0 + flex  # flex is [-0.15, +0.15] → multiplier [0.85, 1.15]
            # Clamp multiplier to valid range
            flex_multiplier = max(0.7, min(1.3, flex_multiplier))

            # Layer 3: sector params (additive)
            sector_adj = config.sector_params.get(criterion, 0.0)

            # Combined weight
            combined[criterion] = (base * flex_multiplier) + sector_adj

        return combined

    def _enforce_floor_protection(self, weights: dict[str, float],
                                   thresholds: dict[str, int]) -> dict[str, float]:
        """Ensure core attribute weights never fall below a minimum floor (Property 3).

        The floor is defined as: weight >= threshold / 2 (ensures core attributes
        maintain meaningful contribution even after adjustments).
        """
        for attr in UNIVERSAL_CORE_ATTRIBUTES:
            threshold = thresholds.get(attr, 1)
            min_weight = threshold / 2.0  # Floor: half the threshold score
            if weights.get(attr, 0) < min_weight:
                weights[attr] = min_weight
        return weights

    def _normalize_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """Normalize weights so Σ(w_i) = 1.0 (Property 1).

        All weights must be > 0 after normalization.
        """
        # Ensure all weights are positive
        for k in weights:
            if weights[k] <= 0:
                weights[k] = 0.01  # minimum positive weight

        total = sum(weights.values())
        if total == 0:
            # Fallback: equal weights
            n = len(weights)
            return {k: 1.0 / n for k in weights}

        normalized = {k: v / total for k, v in weights.items()}

        # Verify normalization (Property 1)
        final_sum = sum(normalized.values())
        assert abs(final_sum - 1.0) < 0.0001, f"Normalization failed: sum = {final_sum}"

        return normalized

    def _compute_layer_breakdown(self, criteria: list[CriterionScore],
                                  config: RoleConfig) -> dict:
        """Compute how much each layer contributes to the final score.

        Returns absolute contributions and percentages for explainability.
        """
        layer1_contribution = 0.0
        layer2_contribution = 0.0
        layer3_contribution = 0.0

        for c in criteria:
            # Approximate layer contributions based on weight proportions
            total_raw = c.layer1_weight + abs(c.layer2_adjustment) + abs(c.layer3_adjustment)
            if total_raw > 0:
                l1_pct = c.layer1_weight / total_raw
                l2_pct = abs(c.layer2_adjustment) / total_raw
                l3_pct = abs(c.layer3_adjustment) / total_raw
            else:
                l1_pct, l2_pct, l3_pct = 1.0, 0.0, 0.0

            layer1_contribution += c.weighted_score * l1_pct
            layer2_contribution += c.weighted_score * l2_pct
            layer3_contribution += c.weighted_score * l3_pct

        total_contribution = layer1_contribution + layer2_contribution + layer3_contribution
        if total_contribution > 0:
            return {
                "universal_core": round(layer1_contribution / total_contribution * 100, 2),
                "cultural_flex": round(layer2_contribution / total_contribution * 100, 2),
                "sector_parameter": round(layer3_contribution / total_contribution * 100, 2),
            }
        return {"universal_core": 100.0, "cultural_flex": 0.0, "sector_parameter": 0.0}

    def _compute_master_variables(self, candidate_scores: dict[str, int],
                                   config: RoleConfig) -> list[dict]:
        """Compute weighted master variable scores (15 variables)."""
        results = []
        for var in MASTER_VARIABLES:
            score = candidate_scores.get(var, 0)
            weight = config.master_variable_weights.get(var, 5)
            results.append({
                "variable": var,
                "name": var.replace("_", " ").title(),
                "score": score,
                "weight": weight,
                "weighted_score": score * weight,
            })
        return results

    def _get_max_core_score(self, result: ScoringResult) -> int:
        """Get the highest Universal Core attribute score (for tiebreaking)."""
        max_score = 0
        for c in result.criterion_scores:
            if c.criterion_id in UNIVERSAL_CORE_ATTRIBUTES:
                max_score = max(max_score, c.raw_score)
        return max_score

    # =========================================================================
    # PERSISTENCE (Audit Trail — Requirements R10.2, R10.6, R17.2)
    # =========================================================================

    def persist_scoring_decision(self, result: ScoringResult,
                                  role_config: RoleConfig) -> str:
        """Write scoring decision to Aurora for audit trail (5-year retention).

        Returns the scoring_decision_id.
        """
        if not self._db:
            logger.warning("No Aurora connection — skipping audit trail persistence")
            return result.scoring_decision_id

        try:
            import json
            with self._db.cursor() as cur:
                cur.execute(
                    """INSERT INTO succession.scoring_decisions
                       (id, tenant_id, candidate_id, role_config_id, composite_score,
                        layer_breakdown, criterion_scores, master_variable_scores,
                        threshold_violations, weights_applied, model_version, below_minimum, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        result.scoring_decision_id,
                        role_config.tenant_id,
                        result.candidate_id,
                        role_config.id,
                        result.composite_score,
                        json.dumps(result.layer_breakdown),
                        json.dumps([{
                            "criterion_id": c.criterion_id,
                            "raw_score": c.raw_score,
                            "weight": c.weight,
                            "weighted_score": c.weighted_score,
                        } for c in result.criterion_scores]),
                        json.dumps(result.master_variable_scores),
                        json.dumps([{
                            "attribute": v.attribute,
                            "score": v.score,
                            "minimum_required": v.minimum_required,
                        } for v in result.threshold_violations]),
                        json.dumps({
                            "universal_core": role_config.universal_core,
                            "cultural_flex": role_config.cultural_flex,
                            "sector_params": role_config.sector_params,
                        }),
                        result.model_version,
                        result.below_minimum,
                        result.timestamp,
                    ),
                )
            logger.info("Persisted scoring decision %s for candidate %s",
                       result.scoring_decision_id, result.candidate_id)
        except Exception as e:
            logger.error("Failed to persist scoring decision: %s", e)

        return result.scoring_decision_id
