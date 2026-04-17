"""Unit tests for discover_top_patterns and _synthesize_questions methods."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from src.db.connection import ConnectionManager
from src.models.pattern import EvidenceModality, PatternQuestion, TopPatternReport
from src.services.pattern_discovery_service import (
    NEPTUNE_TIMEOUT_THRESHOLD,
    PatternDiscoveryService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-top5-001"


def _make_raw_pattern(
    entities=None,
    modalities=None,
    evidence_strength=0.5,
    novelty_score=0.5,
    source_documents=None,
    source_images=None,
    face_crops=None,
):
    """Helper to build a raw pattern dict."""
    return {
        "entities": entities or [
            {"name": "Entity A", "type": "PERSON", "role": "hub"},
            {"name": "Entity B", "type": "ORGANIZATION", "role": "connected"},
        ],
        "modalities": modalities or [EvidenceModality.TEXT],
        "source_documents": source_documents or [],
        "source_images": source_images or [],
        "face_crops": face_crops or [],
        "evidence_strength": evidence_strength,
        "cross_modal_score": 0.5,
        "novelty_score": novelty_score,
        "composite_score": 0.0,
    }


@pytest.fixture
def mock_aurora():
    return MagicMock(spec=ConnectionManager)


@pytest.fixture
def mock_bedrock():
    return MagicMock()


@pytest.fixture
def service(mock_aurora, mock_bedrock):
    return PatternDiscoveryService(
        neptune_conn=MagicMock(),
        aurora_conn=mock_aurora,
        bedrock_client=mock_bedrock,
    )


def _setup_bedrock_synthesis_response(mock_bedrock, results):
    """Configure mock Bedrock to return a JSON array of question results."""
    body_mock = MagicMock()
    body_mock.read.return_value = json.dumps({
        "content": [{"text": json.dumps(results)}],
    }).encode()
    mock_bedrock.invoke_model.return_value = {"body": body_mock}


# ---------------------------------------------------------------------------
# discover_top_patterns
# ---------------------------------------------------------------------------


class TestDiscoverTopPatterns:
    def test_returns_dict_with_top_pattern_report_structure(self, service, mock_bedrock):
        """discover_top_patterns returns a dict matching TopPatternReport."""
        patterns = [_make_raw_pattern() for _ in range(6)]
        with patch.object(service, "_query_text_entity_patterns", return_value=patterns[:2]), \
             patch.object(service, "_query_visual_entity_patterns", return_value=patterns[2:4]), \
             patch.object(service, "_query_face_match_patterns", return_value=patterns[4:5]), \
             patch.object(service, "_query_cooccurrence_patterns", return_value=patterns[5:6]):
            _setup_bedrock_synthesis_response(mock_bedrock, [
                {"question": f"Q{i}?", "confidence": 70, "summary": f"Summary {i}"}
                for i in range(1, 6)
            ])

            result = service.discover_top_patterns(CASE_ID)

        assert result["case_file_id"] == CASE_ID
        assert "patterns" in result
        assert "generated_at" in result
        assert len(result["patterns"]) <= 5

    def test_returns_at_most_5_patterns(self, service, mock_bedrock):
        """Even with many raw patterns, only top 5 are returned."""
        patterns = [
            _make_raw_pattern(
                entities=[{"name": f"E{i}", "type": "PERSON", "role": "hub"}],
                evidence_strength=0.1 * (i + 1),
                novelty_score=0.1 * (i + 1),
            )
            for i in range(10)
        ]
        with patch.object(service, "_query_text_entity_patterns", return_value=patterns), \
             patch.object(service, "_query_visual_entity_patterns", return_value=[]), \
             patch.object(service, "_query_face_match_patterns", return_value=[]), \
             patch.object(service, "_query_cooccurrence_patterns", return_value=[]):
            _setup_bedrock_synthesis_response(mock_bedrock, [
                {"question": f"Q{i}?", "confidence": 70, "summary": f"S{i}"}
                for i in range(5)
            ])

            result = service.discover_top_patterns(CASE_ID)

        assert len(result["patterns"]) == 5

    def test_fewer_than_5_sets_explanation(self, service, mock_bedrock):
        """When fewer than 5 patterns exist, fewer_patterns_explanation is set."""
        patterns = [_make_raw_pattern()]
        with patch.object(service, "_query_text_entity_patterns", return_value=patterns), \
             patch.object(service, "_query_visual_entity_patterns", return_value=[]), \
             patch.object(service, "_query_face_match_patterns", return_value=[]), \
             patch.object(service, "_query_cooccurrence_patterns", return_value=[]):
            _setup_bedrock_synthesis_response(mock_bedrock, [
                {"question": "Q1?", "confidence": 70, "summary": "S1"}
            ])

            result = service.discover_top_patterns(CASE_ID)

        assert len(result["patterns"]) == 1
        assert result["fewer_patterns_explanation"] != ""
        assert "1" in result["fewer_patterns_explanation"]

    def test_patterns_sorted_descending_by_composite_score(self, service, mock_bedrock):
        """Patterns are sorted by composite_score descending."""
        p_low = _make_raw_pattern(
            entities=[{"name": "Low", "type": "X", "role": "hub"}],
            evidence_strength=0.1, novelty_score=0.1,
        )
        p_high = _make_raw_pattern(
            entities=[{"name": "High", "type": "X", "role": "hub"}],
            evidence_strength=0.9, novelty_score=0.9,
        )
        with patch.object(service, "_query_text_entity_patterns", return_value=[p_low, p_high]), \
             patch.object(service, "_query_visual_entity_patterns", return_value=[]), \
             patch.object(service, "_query_face_match_patterns", return_value=[]), \
             patch.object(service, "_query_cooccurrence_patterns", return_value=[]):
            _setup_bedrock_synthesis_response(mock_bedrock, [
                {"question": "High?", "confidence": 90, "summary": "High"},
                {"question": "Low?", "confidence": 30, "summary": "Low"},
            ])

            result = service.discover_top_patterns(CASE_ID)

        # First pattern should be the high-scoring one
        assert result["patterns"][0]["question"] == "High?"

    def test_patterns_have_1_based_indices(self, service, mock_bedrock):
        """Each pattern has a 1-based index."""
        patterns = [_make_raw_pattern(
            entities=[{"name": f"E{i}", "type": "X", "role": "hub"}],
        ) for i in range(3)]
        with patch.object(service, "_query_text_entity_patterns", return_value=patterns), \
             patch.object(service, "_query_visual_entity_patterns", return_value=[]), \
             patch.object(service, "_query_face_match_patterns", return_value=[]), \
             patch.object(service, "_query_cooccurrence_patterns", return_value=[]):
            _setup_bedrock_synthesis_response(mock_bedrock, [
                {"question": f"Q{i}?", "confidence": 70, "summary": f"S{i}"}
                for i in range(3)
            ])

            result = service.discover_top_patterns(CASE_ID)

        indices = [p["index"] for p in result["patterns"]]
        assert indices == [1, 2, 3]

    def test_empty_graph_returns_empty_patterns(self, service, mock_bedrock):
        """Empty graph returns 0 patterns with explanation."""
        with patch.object(service, "_query_text_entity_patterns", return_value=[]), \
             patch.object(service, "_query_visual_entity_patterns", return_value=[]), \
             patch.object(service, "_query_face_match_patterns", return_value=[]), \
             patch.object(service, "_query_cooccurrence_patterns", return_value=[]):

            result = service.discover_top_patterns(CASE_ID)

        assert result["patterns"] == []
        assert result["fewer_patterns_explanation"] != ""

    def test_skips_bedrock_when_neptune_exceeds_timeout(self, service, mock_bedrock):
        """When Neptune queries take > 15s, fallback templates are used."""
        patterns = [_make_raw_pattern()]

        def slow_query(*args, **kwargs):
            return patterns

        # Simulate slow Neptune by patching time.monotonic
        call_count = [0]
        original_monotonic = time.monotonic

        def mock_monotonic():
            call_count[0] += 1
            if call_count[0] == 1:
                return 0.0  # start
            return 20.0  # elapsed > 15s

        with patch.object(service, "_query_text_entity_patterns", return_value=patterns), \
             patch.object(service, "_query_visual_entity_patterns", return_value=[]), \
             patch.object(service, "_query_face_match_patterns", return_value=[]), \
             patch.object(service, "_query_cooccurrence_patterns", return_value=[]), \
             patch("src.services.pattern_discovery_service.time.monotonic", side_effect=mock_monotonic):

            result = service.discover_top_patterns(CASE_ID)

        # Bedrock should NOT have been called
        mock_bedrock.invoke_model.assert_not_called()
        # Should still have patterns (from fallback)
        assert len(result["patterns"]) == 1
        assert "Investigate the connection" in result["patterns"][0]["question"]

    def test_merges_cross_modal_patterns(self, service, mock_bedrock):
        """Patterns sharing entities across modalities are merged."""
        text_p = _make_raw_pattern(
            entities=[{"name": "John Doe", "type": "PERSON", "role": "hub"}],
            modalities=[EvidenceModality.TEXT],
        )
        face_p = _make_raw_pattern(
            entities=[{"name": "John Doe", "type": "PERSON", "role": "matched_identity"}],
            modalities=[EvidenceModality.FACE],
            face_crops=[{"crop_s3_key": "crop1.jpg", "entity_name": "John Doe", "similarity": 0.95}],
        )
        with patch.object(service, "_query_text_entity_patterns", return_value=[text_p]), \
             patch.object(service, "_query_visual_entity_patterns", return_value=[]), \
             patch.object(service, "_query_face_match_patterns", return_value=[face_p]), \
             patch.object(service, "_query_cooccurrence_patterns", return_value=[]):
            _setup_bedrock_synthesis_response(mock_bedrock, [
                {"question": "Q1?", "confidence": 80, "summary": "Merged pattern"}
            ])

            result = service.discover_top_patterns(CASE_ID)

        # Should be merged into 1 pattern with both modalities
        assert len(result["patterns"]) == 1
        modalities = result["patterns"][0]["modalities"]
        assert EvidenceModality.TEXT in modalities
        assert EvidenceModality.FACE in modalities


# ---------------------------------------------------------------------------
# _synthesize_questions
# ---------------------------------------------------------------------------


class TestSynthesizeQuestions:
    def test_calls_bedrock_with_entity_context(self, service, mock_bedrock):
        """_synthesize_questions sends entity names and types to Bedrock."""
        patterns = [_make_raw_pattern(
            entities=[
                {"name": "Alice", "type": "PERSON", "role": "hub"},
                {"name": "Acme Corp", "type": "ORGANIZATION", "role": "connected"},
            ],
            modalities=[EvidenceModality.TEXT, EvidenceModality.VISUAL],
        )]
        _setup_bedrock_synthesis_response(mock_bedrock, [
            {"question": "What is Alice's role?", "confidence": 85, "summary": "Alice connected to Acme."}
        ])

        result = service._synthesize_questions(CASE_ID, patterns)

        assert len(result) == 1
        assert result[0]["question"] == "What is Alice's role?"
        assert result[0]["confidence"] == 85
        # Verify Bedrock was called with entity names in prompt
        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        body = json.loads(call_kwargs["body"])
        prompt_text = body["messages"][0]["content"]
        assert "Alice" in prompt_text
        assert "Acme Corp" in prompt_text
        assert "PERSON" in prompt_text

    def test_returns_correct_structure(self, service, mock_bedrock):
        """Each returned question has all required fields."""
        patterns = [_make_raw_pattern()]
        _setup_bedrock_synthesis_response(mock_bedrock, [
            {"question": "Q?", "confidence": 75, "summary": "Summary text."}
        ])

        result = service._synthesize_questions(CASE_ID, patterns)

        q = result[0]
        assert "index" in q
        assert "question" in q
        assert "confidence" in q
        assert "modalities" in q
        assert "summary" in q
        assert "document_count" in q
        assert "image_count" in q
        assert "raw_pattern" in q

    def test_confidence_clamped_to_0_100(self, service, mock_bedrock):
        """Confidence values are clamped to [0, 100]."""
        patterns = [_make_raw_pattern(), _make_raw_pattern(
            entities=[{"name": "X", "type": "Y", "role": "z"}],
        )]
        _setup_bedrock_synthesis_response(mock_bedrock, [
            {"question": "Q1?", "confidence": 150, "summary": "S1"},
            {"question": "Q2?", "confidence": -10, "summary": "S2"},
        ])

        result = service._synthesize_questions(CASE_ID, patterns)

        assert result[0]["confidence"] == 100
        assert result[1]["confidence"] == 0

    def test_fallback_on_bedrock_failure(self, service, mock_bedrock):
        """On Bedrock failure, fallback template questions are generated."""
        mock_bedrock.invoke_model.side_effect = Exception("Bedrock unavailable")
        patterns = [_make_raw_pattern(
            entities=[
                {"name": "Entity A", "type": "PERSON", "role": "hub"},
                {"name": "Entity B", "type": "ORGANIZATION", "role": "connected"},
            ],
            modalities=[EvidenceModality.TEXT],
        )]

        result = service._synthesize_questions(CASE_ID, patterns)

        assert len(result) == 1
        q = result[0]
        assert "Investigate the connection" in q["question"]
        assert "Entity A" in q["question"]
        assert "Entity B" in q["question"]
        assert q["confidence"] == 50

    def test_fallback_includes_modality_names(self, service, mock_bedrock):
        """Fallback template includes modality names."""
        mock_bedrock.invoke_model.side_effect = Exception("timeout")
        patterns = [_make_raw_pattern(
            modalities=[EvidenceModality.TEXT, EvidenceModality.VISUAL],
        )]

        result = service._synthesize_questions(CASE_ID, patterns)

        assert "text" in result[0]["question"]
        assert "visual" in result[0]["question"]

    def test_empty_patterns_returns_empty(self, service, mock_bedrock):
        """Empty pattern list returns empty questions list."""
        result = service._synthesize_questions(CASE_ID, [])
        assert result == []

    def test_face_match_context_in_prompt(self, service, mock_bedrock):
        """Face match details are included in the Bedrock prompt."""
        patterns = [_make_raw_pattern(
            modalities=[EvidenceModality.FACE],
            face_crops=[
                {"crop_s3_key": "crop1.jpg", "entity_name": "John Doe", "similarity": 0.95},
            ],
        )]
        _setup_bedrock_synthesis_response(mock_bedrock, [
            {"question": "Q?", "confidence": 80, "summary": "S"}
        ])

        service._synthesize_questions(CASE_ID, patterns)

        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        body = json.loads(call_kwargs["body"])
        prompt_text = body["messages"][0]["content"]
        assert "John Doe" in prompt_text
        assert "0.95" in prompt_text

    def test_uses_correct_model_id(self, service, mock_bedrock):
        """_synthesize_questions uses the synthesis model ID."""
        patterns = [_make_raw_pattern()]
        _setup_bedrock_synthesis_response(mock_bedrock, [
            {"question": "Q?", "confidence": 70, "summary": "S"}
        ])

        service._synthesize_questions(CASE_ID, patterns)

        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == "us.anthropic.claude-3-haiku-20240307-v1:0"

    def test_invalid_json_from_bedrock_uses_fallback(self, service, mock_bedrock):
        """If Bedrock returns invalid JSON, fallback is used."""
        body_mock = MagicMock()
        body_mock.read.return_value = json.dumps({
            "content": [{"text": "This is not valid JSON"}],
        }).encode()
        mock_bedrock.invoke_model.return_value = {"body": body_mock}

        patterns = [_make_raw_pattern()]
        result = service._synthesize_questions(CASE_ID, patterns)

        assert len(result) == 1
        assert result[0]["confidence"] == 50
        assert "Investigate the connection" in result[0]["question"]


# ---------------------------------------------------------------------------
# _merge_cross_modal_patterns
# ---------------------------------------------------------------------------


class TestMergeCrossModalPatterns:
    def test_merges_shared_entities_different_modalities(self):
        """Patterns sharing entities with different modalities are merged."""
        p1 = _make_raw_pattern(
            entities=[{"name": "X", "type": "PERSON", "role": "hub"}],
            modalities=[EvidenceModality.TEXT],
        )
        p2 = _make_raw_pattern(
            entities=[{"name": "X", "type": "PERSON", "role": "visual_label"}],
            modalities=[EvidenceModality.VISUAL],
            source_images=["img1.jpg"],
        )

        result = PatternDiscoveryService._merge_cross_modal_patterns([p1, p2])

        assert len(result) == 1
        assert EvidenceModality.TEXT in result[0]["modalities"]
        assert EvidenceModality.VISUAL in result[0]["modalities"]
        assert "img1.jpg" in result[0]["source_images"]

    def test_no_merge_same_modality(self):
        """Patterns with same modality are not merged even if sharing entities."""
        p1 = _make_raw_pattern(
            entities=[{"name": "X", "type": "PERSON", "role": "hub"}],
            modalities=[EvidenceModality.TEXT],
        )
        p2 = _make_raw_pattern(
            entities=[{"name": "X", "type": "PERSON", "role": "hub"}],
            modalities=[EvidenceModality.TEXT],
        )

        result = PatternDiscoveryService._merge_cross_modal_patterns([p1, p2])

        assert len(result) == 2

    def test_no_merge_different_entities(self):
        """Patterns with no shared entities are not merged."""
        p1 = _make_raw_pattern(
            entities=[{"name": "A", "type": "PERSON", "role": "hub"}],
            modalities=[EvidenceModality.TEXT],
        )
        p2 = _make_raw_pattern(
            entities=[{"name": "B", "type": "PERSON", "role": "hub"}],
            modalities=[EvidenceModality.VISUAL],
        )

        result = PatternDiscoveryService._merge_cross_modal_patterns([p1, p2])

        assert len(result) == 2

    def test_empty_input(self):
        result = PatternDiscoveryService._merge_cross_modal_patterns([])
        assert result == []

    def test_merged_takes_max_strength(self):
        """Merged pattern takes the max evidence_strength and novelty_score."""
        p1 = _make_raw_pattern(
            entities=[{"name": "X", "type": "PERSON", "role": "hub"}],
            modalities=[EvidenceModality.TEXT],
            evidence_strength=0.3,
            novelty_score=0.2,
        )
        p2 = _make_raw_pattern(
            entities=[{"name": "X", "type": "PERSON", "role": "hub"}],
            modalities=[EvidenceModality.FACE],
            evidence_strength=0.8,
            novelty_score=0.9,
        )

        result = PatternDiscoveryService._merge_cross_modal_patterns([p1, p2])

        assert result[0]["evidence_strength"] == 0.8
        assert result[0]["novelty_score"] == 0.9


# ---------------------------------------------------------------------------
# _generate_fallback_questions
# ---------------------------------------------------------------------------


class TestGenerateFallbackQuestions:
    def test_template_format(self, service):
        """Fallback uses the specified template format."""
        patterns = [_make_raw_pattern(
            entities=[
                {"name": "Alice", "type": "PERSON", "role": "hub"},
                {"name": "Bob", "type": "PERSON", "role": "connected"},
            ],
            modalities=[EvidenceModality.TEXT, EvidenceModality.FACE],
            source_documents=["doc1", "doc2"],
        )]

        result = service._generate_fallback_questions(patterns)

        assert len(result) == 1
        q = result[0]
        assert "Investigate the connection between Alice and Bob" in q["question"]
        assert "2 documents" in q["question"]
        assert "text, face" in q["question"]
        assert q["confidence"] == 50

    def test_single_entity_fallback(self, service):
        """Fallback handles patterns with only one entity."""
        patterns = [_make_raw_pattern(
            entities=[{"name": "Solo", "type": "PERSON", "role": "hub"}],
        )]

        result = service._generate_fallback_questions(patterns)

        assert "Solo" in result[0]["question"]
        assert "Unknown" in result[0]["question"]
