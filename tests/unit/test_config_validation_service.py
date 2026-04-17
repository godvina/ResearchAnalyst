"""Unit tests for ConfigValidationService."""

import pytest

from src.models.entity import EntityType
from src.services.config_validation_service import (
    CONFIG_TEMPLATES,
    ConfigValidationService,
)


@pytest.fixture()
def validator():
    return ConfigValidationService()


# ---------------------------------------------------------------------------
# Valid configs — should produce zero errors
# ---------------------------------------------------------------------------


class TestValidConfigs:
    def test_empty_config_is_valid(self, validator):
        assert validator.validate({}) == []

    def test_minimal_valid_config(self, validator):
        config = {
            "extract": {"confidence_threshold": 0.5},
        }
        assert validator.validate(config) == []

    def test_full_valid_config(self, validator):
        config = {
            "parse": {"pdf_method": "hybrid", "ocr_enabled": True, "table_extraction_enabled": True},
            "extract": {
                "prompt_template": "custom_v2",
                "entity_types": ["person", "organization", "location"],
                "llm_model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "chunk_size_chars": 8000,
                "confidence_threshold": 0.7,
                "relationship_inference_enabled": False,
            },
            "embed": {
                "embedding_model_id": "amazon.titan-embed-text-v1",
                "search_tier": "enterprise",
                "opensearch_settings": {"index_refresh_interval": "10s"},
            },
            "graph_load": {
                "load_strategy": "gremlin",
                "batch_size": 1000,
                "normalization_rules": {"case_folding": True},
            },
            "store_artifact": {"artifact_format": "jsonl", "include_raw_text": True},
        }
        assert validator.validate(config) == []

    def test_boundary_confidence_threshold_zero(self, validator):
        assert validator.validate({"extract": {"confidence_threshold": 0.0}}) == []

    def test_boundary_confidence_threshold_one(self, validator):
        assert validator.validate({"extract": {"confidence_threshold": 1.0}}) == []

    def test_boundary_chunk_size_min(self, validator):
        assert validator.validate({"extract": {"chunk_size_chars": 500}}) == []

    def test_boundary_chunk_size_max(self, validator):
        assert validator.validate({"extract": {"chunk_size_chars": 100000}}) == []

    def test_all_entity_types_valid(self, validator):
        all_types = [et.value for et in EntityType]
        assert validator.validate({"extract": {"entity_types": all_types}}) == []

    def test_all_pdf_methods(self, validator):
        for method in ("text", "ocr", "hybrid"):
            assert validator.validate({"parse": {"pdf_method": method}}) == []

    def test_all_load_strategies(self, validator):
        for strategy in ("bulk_csv", "gremlin"):
            assert validator.validate({"graph_load": {"load_strategy": strategy}}) == []

    def test_all_artifact_formats(self, validator):
        for fmt in ("json", "jsonl"):
            assert validator.validate({"store_artifact": {"artifact_format": fmt}}) == []


# ---------------------------------------------------------------------------
# Invalid configs — should produce errors
# ---------------------------------------------------------------------------


class TestInvalidConfigs:
    def test_unknown_top_level_key(self, validator):
        errors = validator.validate({"bogus_section": {}})
        assert len(errors) == 1
        assert errors[0].field_path == "bogus_section"
        assert "Unknown top-level key" in errors[0].reason

    def test_confidence_threshold_too_high(self, validator):
        errors = validator.validate({"extract": {"confidence_threshold": 1.5}})
        assert len(errors) == 1
        assert errors[0].field_path == "extract.confidence_threshold"

    def test_confidence_threshold_negative(self, validator):
        errors = validator.validate({"extract": {"confidence_threshold": -0.1}})
        assert len(errors) == 1
        assert errors[0].field_path == "extract.confidence_threshold"

    def test_confidence_threshold_not_a_number(self, validator):
        errors = validator.validate({"extract": {"confidence_threshold": "high"}})
        assert len(errors) == 1
        assert errors[0].field_path == "extract.confidence_threshold"

    def test_chunk_size_too_small(self, validator):
        errors = validator.validate({"extract": {"chunk_size_chars": 499}})
        assert len(errors) == 1
        assert errors[0].field_path == "extract.chunk_size_chars"

    def test_chunk_size_too_large(self, validator):
        errors = validator.validate({"extract": {"chunk_size_chars": 100001}})
        assert len(errors) == 1
        assert errors[0].field_path == "extract.chunk_size_chars"

    def test_chunk_size_not_int(self, validator):
        errors = validator.validate({"extract": {"chunk_size_chars": 5000.5}})
        assert len(errors) == 1
        assert errors[0].field_path == "extract.chunk_size_chars"

    def test_invalid_entity_type(self, validator):
        errors = validator.validate({"extract": {"entity_types": ["person", "alien"]}})
        assert len(errors) == 1
        assert errors[0].field_path == "extract.entity_types"
        assert "alien" in errors[0].reason

    def test_entity_types_not_a_list(self, validator):
        errors = validator.validate({"extract": {"entity_types": "person"}})
        assert len(errors) == 1
        assert errors[0].field_path == "extract.entity_types"

    def test_invalid_load_strategy(self, validator):
        errors = validator.validate({"graph_load": {"load_strategy": "sparql"}})
        assert len(errors) == 1
        assert errors[0].field_path == "graph_load.load_strategy"

    def test_invalid_pdf_method(self, validator):
        errors = validator.validate({"parse": {"pdf_method": "magic"}})
        assert len(errors) == 1
        assert errors[0].field_path == "parse.pdf_method"

    def test_invalid_artifact_format(self, validator):
        errors = validator.validate({"store_artifact": {"artifact_format": "xml"}})
        assert len(errors) == 1
        assert errors[0].field_path == "store_artifact.artifact_format"

    def test_unknown_key_in_section(self, validator):
        errors = validator.validate({"extract": {"unknown_param": True}})
        assert len(errors) == 1
        assert errors[0].field_path == "extract.unknown_param"


# ---------------------------------------------------------------------------
# Rekognition validation
# ---------------------------------------------------------------------------


class TestRekognitionValidation:
    def test_valid_rekognition_config(self, validator):
        config = {
            "rekognition": {
                "enabled": True,
                "min_face_confidence": 0.8,
                "min_object_confidence": 0.7,
                "video_segment_length_seconds": 60,
            },
        }
        assert validator.validate(config) == []

    def test_min_face_confidence_out_of_range(self, validator):
        errors = validator.validate({"rekognition": {"min_face_confidence": 1.5}})
        assert len(errors) == 1
        assert errors[0].field_path == "rekognition.min_face_confidence"

    def test_min_object_confidence_negative(self, validator):
        errors = validator.validate({"rekognition": {"min_object_confidence": -0.1}})
        assert len(errors) == 1
        assert errors[0].field_path == "rekognition.min_object_confidence"

    def test_video_segment_zero(self, validator):
        errors = validator.validate({"rekognition": {"video_segment_length_seconds": 0}})
        assert len(errors) == 1
        assert errors[0].field_path == "rekognition.video_segment_length_seconds"

    def test_video_segment_negative(self, validator):
        errors = validator.validate({"rekognition": {"video_segment_length_seconds": -10}})
        assert len(errors) == 1
        assert errors[0].field_path == "rekognition.video_segment_length_seconds"

    def test_unknown_rekognition_key(self, validator):
        errors = validator.validate({"rekognition": {"unknown_key": True}})
        assert len(errors) == 1
        assert errors[0].field_path == "rekognition.unknown_key"


# ---------------------------------------------------------------------------
# Multiple errors collected (non-fail-fast)
# ---------------------------------------------------------------------------


class TestMultipleErrors:
    def test_collects_all_errors(self, validator):
        config = {
            "extract": {
                "confidence_threshold": 2.0,
                "chunk_size_chars": 10,
                "entity_types": ["alien"],
            },
            "graph_load": {"load_strategy": "sparql"},
            "unknown_section": {},
        }
        errors = validator.validate(config)
        field_paths = {e.field_path for e in errors}
        assert "extract.confidence_threshold" in field_paths
        assert "extract.chunk_size_chars" in field_paths
        assert "extract.entity_types" in field_paths
        assert "graph_load.load_strategy" in field_paths
        assert "unknown_section" in field_paths
        assert len(errors) == 5


# ---------------------------------------------------------------------------
# CONFIG_TEMPLATES validation
# ---------------------------------------------------------------------------


class TestConfigTemplates:
    def test_all_templates_are_valid(self, validator):
        for name, template in CONFIG_TEMPLATES.items():
            errors = validator.validate(template)
            assert errors == [], f"Template '{name}' has validation errors: {errors}"

    def test_template_names(self):
        assert set(CONFIG_TEMPLATES.keys()) == {"antitrust", "criminal", "financial_fraud"}

    def test_antitrust_has_high_confidence(self):
        assert CONFIG_TEMPLATES["antitrust"]["extract"]["confidence_threshold"] == 0.6

    def test_criminal_has_low_confidence(self):
        assert CONFIG_TEMPLATES["criminal"]["extract"]["confidence_threshold"] == 0.4

    def test_financial_fraud_has_enterprise_search(self):
        assert CONFIG_TEMPLATES["financial_fraud"]["embed"]["search_tier"] == "enterprise"
