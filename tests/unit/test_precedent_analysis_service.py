"""Unit tests for PrecedentAnalysisService.

Covers:
- find_precedents returns at most 10 matches with scores in [0, 100]
- compute_ruling_distribution percentages sum to 100 (within ±1 tolerance)
- Limited precedent disclaimer when < 3 matches above 50
- OpenSearch fallback to Neptune-only similarity
- Sentencing advisory contains precedent case name and USSG reference
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from src.models.prosecutor import (
    PrecedentMatch,
    RulingDistribution,
    RulingOutcome,
    SentencingAdvisory,
)
from src.services.precedent_analysis_service import PrecedentAnalysisService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FreshBytesIO:
    """Returns fresh bytes on each .read() call."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data


def _bedrock_response(payload: dict | list) -> dict:
    """Build a mock Bedrock invoke_model response."""
    body_text = json.dumps(payload)
    content = json.dumps({"content": [{"text": body_text}]})
    return {"body": _FreshBytesIO(content.encode())}


def _make_precedent_row(
    precedent_id: str,
    case_reference: str,
    charge_type: str = "18 U.S.C. § 1341",
    ruling: str = "guilty",
    sentence: str = "60 months",
    key_factors: list | None = None,
    aggravating_factors: list | None = None,
    mitigating_factors: list | None = None,
    case_summary: str = "Fraud case summary",
    judge: str = "Judge Smith",
    jurisdiction: str = "S.D.N.Y.",
) -> tuple:
    """Build a precedent_cases row tuple matching the SELECT column order."""
    return (
        precedent_id,
        case_reference,
        charge_type,
        ruling,
        sentence,
        judge,
        jurisdiction,
        case_summary,
        key_factors or [],
        aggravating_factors or [],
        mitigating_factors or [],
    )


def _make_mock_db(precedent_rows=None, case_factors=None, case_summary=None):
    """Build a mock Aurora connection manager."""
    if precedent_rows is None:
        precedent_rows = []
    if case_factors is None:
        case_factors = []

    cursor = MagicMock()

    def _execute(sql, params=None):
        sql_lower = sql.strip().lower()
        if "precedent_cases" in sql_lower:
            cursor.fetchall.return_value = precedent_rows
        elif "case_statutes" in sql_lower:
            cursor.fetchall.return_value = case_factors
        elif "case_files" in sql_lower:
            cursor.fetchone.return_value = (
                ("Test Case", "Test description") if case_summary is None else case_summary
            )
        else:
            cursor.fetchall.return_value = []
            cursor.fetchone.return_value = None

    cursor.execute = _execute

    db = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield cursor

    db.cursor = _cursor_ctx
    return db


def _make_mock_neptune(entities=None):
    """Build a mock Neptune connection manager with traversal_source."""
    mock_g = MagicMock()
    # Chain: g.V().hasLabel(x).project(...).by(...).by(...).toList()
    mock_g.V.return_value = mock_g
    mock_g.hasLabel.return_value = mock_g
    mock_g.project.return_value = mock_g
    mock_g.by.return_value = mock_g
    mock_g.toList.return_value = entities or []

    cm = MagicMock()

    @contextmanager
    def _traversal_ctx():
        yield mock_g

    cm.traversal_source = _traversal_ctx
    return cm


def _make_matches(count: int, base_score: int = 70) -> list[PrecedentMatch]:
    """Create a list of PrecedentMatch objects for testing."""
    rulings = list(RulingOutcome)
    matches = []
    for i in range(count):
        matches.append(
            PrecedentMatch(
                precedent_id=f"prec-{i}",
                case_reference=f"United States v. Defendant{i}",
                charge_type="18 U.S.C. § 1341",
                ruling=rulings[i % len(rulings)],
                sentence=f"{12 * (i + 1)} months",
                similarity_score=max(0, min(100, base_score - i * 5)),
                key_factors=["fraud", "wire transfer"],
                judge=f"Judge {i}",
                jurisdiction="S.D.N.Y.",
            )
        )
    return matches


# ---------------------------------------------------------------------------
# Tests: find_precedents bounds and score range
# ---------------------------------------------------------------------------


class TestFindPrecedents:
    """find_precedents returns at most 10 matches with scores in [0, 100]."""

    def test_returns_at_most_10_matches(self):
        """Even with 15 precedent rows, result is capped at 10."""
        rows = [
            _make_precedent_row(f"prec-{i}", f"US v. Def{i}")
            for i in range(15)
        ]
        db = _make_mock_db(precedent_rows=rows)
        neptune = _make_mock_neptune()

        svc = PrecedentAnalysisService(
            aurora_cm=db, neptune_cm=neptune, bedrock_client=None
        )

        matches = svc.find_precedents("case-1", "18 U.S.C. § 1341", top_k=10)

        assert len(matches) <= 10

    def test_scores_in_valid_range(self):
        """All similarity scores must be in [0, 100]."""
        rows = [
            _make_precedent_row("prec-1", "US v. Smith", charge_type="18 U.S.C. § 1341"),
            _make_precedent_row("prec-2", "US v. Jones", charge_type="18 U.S.C. § 1343"),
            _make_precedent_row("prec-3", "US v. Brown", charge_type="21 U.S.C. § 846"),
        ]
        db = _make_mock_db(precedent_rows=rows)
        neptune = _make_mock_neptune()

        svc = PrecedentAnalysisService(
            aurora_cm=db, neptune_cm=neptune, bedrock_client=None
        )

        matches = svc.find_precedents("case-1", "18 U.S.C. § 1341")

        for m in matches:
            assert 0 <= m.similarity_score <= 100

    def test_empty_precedent_table_returns_empty(self):
        """No precedent rows → empty result."""
        db = _make_mock_db(precedent_rows=[])
        neptune = _make_mock_neptune()

        svc = PrecedentAnalysisService(
            aurora_cm=db, neptune_cm=neptune, bedrock_client=None
        )

        matches = svc.find_precedents("case-1", "18 U.S.C. § 1341")

        assert matches == []

    def test_exact_charge_match_scores_higher(self):
        """Precedent with exact charge type match should score higher."""
        rows = [
            _make_precedent_row("prec-1", "US v. Exact", charge_type="18 U.S.C. § 1341"),
            _make_precedent_row("prec-2", "US v. Different", charge_type="21 U.S.C. § 846"),
        ]
        db = _make_mock_db(precedent_rows=rows)
        neptune = _make_mock_neptune()

        svc = PrecedentAnalysisService(
            aurora_cm=db, neptune_cm=neptune, bedrock_client=None
        )

        matches = svc.find_precedents("case-1", "18 U.S.C. § 1341")

        exact = next(m for m in matches if m.precedent_id == "prec-1")
        diff = next(m for m in matches if m.precedent_id == "prec-2")
        assert exact.similarity_score >= diff.similarity_score


# ---------------------------------------------------------------------------
# Tests: compute_ruling_distribution sums to 100
# ---------------------------------------------------------------------------


class TestRulingDistribution:
    """compute_ruling_distribution percentages sum to 100."""

    def test_percentages_sum_to_100(self):
        """Distribution percentages must sum to 100 within ±1 tolerance."""
        matches = _make_matches(7)

        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=None
        )

        dist = svc.compute_ruling_distribution(matches)

        total = (
            dist.guilty_pct
            + dist.not_guilty_pct
            + dist.plea_deal_pct
            + dist.dismissed_pct
            + dist.settled_pct
        )
        assert abs(total - 100.0) <= 1.0

    def test_single_ruling_type(self):
        """All guilty → 100% guilty, rest 0%."""
        matches = [
            PrecedentMatch(
                precedent_id=f"p-{i}",
                case_reference=f"US v. D{i}",
                charge_type="fraud",
                ruling=RulingOutcome.GUILTY,
                similarity_score=80,
            )
            for i in range(5)
        ]

        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=None
        )

        dist = svc.compute_ruling_distribution(matches)

        assert dist.guilty_pct == 100.0
        assert dist.not_guilty_pct == 0.0
        assert dist.total_cases == 5

    def test_empty_matches_returns_zero(self):
        """Empty matches → all zeros."""
        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=None
        )

        dist = svc.compute_ruling_distribution([])

        assert dist.total_cases == 0
        assert dist.guilty_pct == 0.0

    def test_two_ruling_types_split(self):
        """2 guilty + 2 not_guilty → 50/50 split."""
        matches = [
            PrecedentMatch(
                precedent_id="p-1", case_reference="US v. A",
                charge_type="fraud", ruling=RulingOutcome.GUILTY, similarity_score=80,
            ),
            PrecedentMatch(
                precedent_id="p-2", case_reference="US v. B",
                charge_type="fraud", ruling=RulingOutcome.GUILTY, similarity_score=75,
            ),
            PrecedentMatch(
                precedent_id="p-3", case_reference="US v. C",
                charge_type="fraud", ruling=RulingOutcome.NOT_GUILTY, similarity_score=70,
            ),
            PrecedentMatch(
                precedent_id="p-4", case_reference="US v. D",
                charge_type="fraud", ruling=RulingOutcome.NOT_GUILTY, similarity_score=65,
            ),
        ]

        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=None
        )

        dist = svc.compute_ruling_distribution(matches)

        assert dist.guilty_pct == 50.0
        assert dist.not_guilty_pct == 50.0
        assert dist.total_cases == 4


# ---------------------------------------------------------------------------
# Tests: Limited precedent disclaimer
# ---------------------------------------------------------------------------


class TestLimitedPrecedentDisclaimer:
    """Disclaimer when < 3 matches above similarity 50."""

    def test_disclaimer_when_fewer_than_3_above_50(self):
        """Only 2 matches above 50 → disclaimer present."""
        matches = [
            PrecedentMatch(
                precedent_id="p-1", case_reference="US v. A",
                charge_type="fraud", ruling=RulingOutcome.GUILTY,
                similarity_score=60,
            ),
            PrecedentMatch(
                precedent_id="p-2", case_reference="US v. B",
                charge_type="fraud", ruling=RulingOutcome.PLEA_DEAL,
                similarity_score=55,
            ),
            PrecedentMatch(
                precedent_id="p-3", case_reference="US v. C",
                charge_type="fraud", ruling=RulingOutcome.NOT_GUILTY,
                similarity_score=30,
            ),
        ]

        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=None
        )

        advisory = svc.generate_sentencing_advisory("case-1", matches)

        assert advisory.disclaimer is not None
        assert "limited precedent" in advisory.disclaimer.lower()

    def test_no_disclaimer_when_3_or_more_above_50(self):
        """3+ matches above 50 → no disclaimer."""
        matches = _make_matches(5, base_score=80)

        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=None
        )

        advisory = svc.generate_sentencing_advisory("case-1", matches)

        assert advisory.disclaimer is None

    def test_disclaimer_with_zero_matches(self):
        """No matches → disclaimer present."""
        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=None
        )

        advisory = svc.generate_sentencing_advisory("case-1", [])

        assert advisory.disclaimer is not None


# ---------------------------------------------------------------------------
# Tests: OpenSearch fallback
# ---------------------------------------------------------------------------


class TestOpenSearchFallback:
    """When OpenSearch is unavailable, use Neptune-only similarity."""

    def test_fallback_without_opensearch(self):
        """opensearch_client=None → still returns matches using Neptune-only."""
        rows = [
            _make_precedent_row("prec-1", "US v. Smith", charge_type="18 U.S.C. § 1341"),
        ]
        db = _make_mock_db(precedent_rows=rows)
        neptune = _make_mock_neptune()

        svc = PrecedentAnalysisService(
            aurora_cm=db, neptune_cm=neptune, bedrock_client=None,
            opensearch_client=None,
        )

        matches = svc.find_precedents("case-1", "18 U.S.C. § 1341")

        assert len(matches) >= 1
        for m in matches:
            assert 0 <= m.similarity_score <= 100

    def test_opensearch_failure_falls_back(self):
        """OpenSearch that raises → falls back to Neptune-only."""
        rows = [
            _make_precedent_row("prec-1", "US v. Smith", charge_type="18 U.S.C. § 1341"),
        ]
        db = _make_mock_db(precedent_rows=rows)
        neptune = _make_mock_neptune()

        broken_opensearch = MagicMock()
        broken_opensearch.search.side_effect = Exception("OpenSearch down")

        svc = PrecedentAnalysisService(
            aurora_cm=db, neptune_cm=neptune, bedrock_client=None,
            opensearch_client=broken_opensearch,
        )

        # Should not raise — falls back gracefully
        matches = svc.find_precedents("case-1", "18 U.S.C. § 1341")

        assert len(matches) >= 1
        for m in matches:
            assert 0 <= m.similarity_score <= 100


# ---------------------------------------------------------------------------
# Tests: Sentencing advisory cites precedent and USSG
# ---------------------------------------------------------------------------


class TestSentencingAdvisory:
    """Advisory must contain precedent case name and USSG reference."""

    def test_advisory_with_bedrock_contains_case_reference(self):
        """Bedrock-generated advisory cites at least one precedent case name."""
        matches = _make_matches(5, base_score=80)

        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response({
            "likely_sentence": (
                "Based on United States v. Defendant0, the likely sentence is "
                "60-84 months under USSG §2B1.1(b)(1)."
            ),
            "fine_or_penalty": (
                "Fine of $50,000-$250,000 per USSG §5E1.2."
            ),
            "supervised_release": (
                "3-5 years supervised release per USSG §5D1.2."
            ),
        })

        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=bedrock
        )

        advisory = svc.generate_sentencing_advisory("case-1", matches)

        combined = (
            advisory.likely_sentence
            + advisory.fine_or_penalty
            + advisory.supervised_release
        )
        # Must contain at least one case reference
        assert any(
            m.case_reference in combined for m in matches
        ), f"No case reference found in: {combined}"

    def test_advisory_with_bedrock_contains_ussg_reference(self):
        """Bedrock-generated advisory references USSG §."""
        matches = _make_matches(5, base_score=80)

        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response({
            "likely_sentence": "60 months based on United States v. Defendant0",
            "fine_or_penalty": "Fine per USSG §5E1.2",
            "supervised_release": "3 years per USSG §5D1.2",
        })

        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=bedrock
        )

        advisory = svc.generate_sentencing_advisory("case-1", matches)

        combined = (
            advisory.likely_sentence
            + advisory.fine_or_penalty
            + advisory.supervised_release
        )
        assert "USSG" in combined or "U.S.S.G." in combined

    def test_static_advisory_fallback_contains_references(self):
        """Fallback advisory (no Bedrock) still contains case name and USSG."""
        matches = _make_matches(5, base_score=80)

        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=None
        )

        advisory = svc.generate_sentencing_advisory("case-1", matches)

        combined = (
            advisory.likely_sentence
            + advisory.fine_or_penalty
            + advisory.supervised_release
        )
        # Static fallback should reference the top case
        assert matches[0].case_reference in combined
        assert "USSG" in combined

    def test_advisory_bedrock_failure_falls_back(self):
        """Bedrock exception → falls back to static advisory."""
        matches = _make_matches(3, base_score=80)

        bedrock = MagicMock()
        bedrock.invoke_model.side_effect = Exception("Bedrock down")

        svc = PrecedentAnalysisService(
            aurora_cm=None, neptune_cm=None, bedrock_client=bedrock
        )

        advisory = svc.generate_sentencing_advisory("case-1", matches)

        # Should not raise, should return a valid advisory
        assert advisory.likely_sentence
        assert advisory.fine_or_penalty
