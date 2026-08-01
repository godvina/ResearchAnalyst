"""Signal Scorer — Pure-function scoring of findings against IoV hierarchies.

Evaluates finding text against flattened IoV indicators using keyword matching,
computes a weighted composite signal strength score (0-100), and classifies
into HIGH/MEDIUM/LOW tiers.

Pure functions only — no AI calls, no external dependencies, deterministic output.
No bulk processing, no EC2, no Bedrock.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from models.signal_mining import FlatIndicator, ScoringResult

logger = logging.getLogger(__name__)

# Tier boundaries
TIER_HIGH_MIN = 70
TIER_MEDIUM_MIN = 40

# Corroboration multiplier applied when matches span 2+ top-level categories
CORROBORATION_MULTIPLIER = 1.25


class SignalScorer:
    """Computes signal strength scores for findings against IoV hierarchies.

    All methods are pure functions — deterministic, no side effects,
    no external service calls. Suitable for high-frequency scoring.
    """

    def score_finding(
        self,
        finding_text: str,
        flat_indicators: list[FlatIndicator],
        pre_matched: Optional[list[FlatIndicator]] = None,
    ) -> ScoringResult:
        """Compute signal_strength score (0-100) for a finding.

        Algorithm:
        1. Match finding text against all indicators (or use pre_matched)
        2. Sum weighted indicator matches (top-level = higher weight)
        3. Apply corroboration multiplier if matches span 2+ top-level categories
        4. Normalize to 0-100 range
        5. Classify tier: HIGH (70-100), MEDIUM (40-69), LOW (0-39)

        Args:
            finding_text: The finding summary text to score.
            flat_indicators: Complete list of flattened indicators for the case type.
            pre_matched: Optional pre-computed matched indicators (skips matching step).

        Returns:
            ScoringResult with score, tier, matched_indicators, category_breakdown.
        """
        if pre_matched is not None:
            matched = pre_matched
        else:
            matched = self.match_indicators(finding_text, flat_indicators)

        if not matched:
            return ScoringResult(
                score=0,
                tier="LOW",
                matched_indicators=[],
                category_breakdown={},
                corroboration_applied=False,
            )

        # Compute weighted sum of matched indicators
        weighted_sum = sum(ind.weight for ind in matched)

        # Max possible is if ALL indicators matched at their weights
        max_possible = sum(ind.weight for ind in flat_indicators)

        if max_possible <= 0:
            return ScoringResult(
                score=0,
                tier="LOW",
                matched_indicators=matched,
                category_breakdown={},
                corroboration_applied=False,
            )

        # Normalize to 0-100
        raw_score = (weighted_sum / max_possible) * 100

        # Check corroboration: matches across 2+ top-level categories
        top_categories: set[str] = set()
        for ind in matched:
            if ind.category_path:
                top_categories.add(ind.category_path[0])

        corroboration_applied = len(top_categories) >= 2
        if corroboration_applied:
            raw_score = min(100.0, raw_score * CORROBORATION_MULTIPLIER)

        score = int(min(100, max(0, round(raw_score))))
        tier = self.classify_tier(score)

        # Build category breakdown
        category_breakdown: dict[str, int] = {}
        for ind in matched:
            if ind.category_path:
                cat = ind.category_path[0]
                category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

        return ScoringResult(
            score=score,
            tier=tier,
            matched_indicators=matched,
            category_breakdown=category_breakdown,
            corroboration_applied=corroboration_applied,
        )

    def match_indicators(
        self, finding_text: str, flat_indicators: list[FlatIndicator]
    ) -> list[FlatIndicator]:
        """Match finding text against flattened indicator list using keyword matching.

        Uses case-insensitive substring matching of significant keywords
        from each indicator against the finding text.

        Args:
            finding_text: The finding text to match against.
            flat_indicators: List of all indicators to check.

        Returns:
            List of FlatIndicator objects that matched the finding text.
        """
        if not finding_text or not flat_indicators:
            return []

        finding_lower = finding_text.lower()
        matched: list[FlatIndicator] = []

        for indicator in flat_indicators:
            if self._indicator_matches(indicator.indicator_text, finding_lower):
                matched.append(indicator)

        return matched

    def classify_tier(self, score: int) -> str:
        """Classify a score into HIGH/MEDIUM/LOW tier.

        Args:
            score: Signal strength score 0-100.

        Returns:
            "HIGH" (70-100), "MEDIUM" (40-69), or "LOW" (0-39).
        """
        if score >= TIER_HIGH_MIN:
            return "HIGH"
        elif score >= TIER_MEDIUM_MIN:
            return "MEDIUM"
        else:
            return "LOW"

    def _indicator_matches(self, indicator_text: str, finding_lower: str) -> bool:
        """Check if an indicator matches the finding text.

        Uses keyword extraction from the indicator and checks if significant
        keywords appear in the finding. Requires at least 2 keyword matches
        for indicators with 3+ keywords, or 1 match for short indicators.

        Args:
            indicator_text: The indicator description to match.
            finding_lower: Lowercased finding text.

        Returns:
            True if the indicator matches the finding.
        """
        # Extract significant keywords (3+ chars, not stopwords)
        keywords = self._extract_keywords(indicator_text)

        if not keywords:
            return False

        # Count how many keywords appear in the finding
        matches = sum(1 for kw in keywords if kw in finding_lower)

        # Threshold: at least 2 keywords for longer indicators, 1 for short
        threshold = 2 if len(keywords) >= 3 else 1
        return matches >= threshold

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract significant keywords from indicator text.

        Removes common stopwords and short words, returns lowercased keywords.

        Args:
            text: Indicator text to extract keywords from.

        Returns:
            List of significant lowercase keywords.
        """
        stopwords = {
            "the", "a", "an", "in", "on", "at", "to", "for", "of", "with",
            "by", "from", "and", "or", "is", "are", "was", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "can",
            "that", "this", "these", "those", "it", "its", "not", "no",
            "than", "more", "less", "very", "also", "just", "only",
            "through", "between", "after", "before", "during", "without",
        }

        words = re.findall(r"[a-z]+", text.lower())
        return [w for w in words if len(w) >= 3 and w not in stopwords]
