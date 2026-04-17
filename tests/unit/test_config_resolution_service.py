"""Unit tests for ConfigResolutionService."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from src.services.config_resolution_service import ConfigResolutionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

SYSTEM_DEFAULT = {
    "parse": {"pdf_method": "text", "ocr_enabled": False, "table_extraction_enabled": False, "extract_images": True, "min_image_dimension": 50},
    "extract": {
        "prompt_template": "default_investigative_v1",
        "entity_types": ["person", "organization", "location"],
        "llm_model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
        "chunk_size_chars": 8000,
        "confidence_threshold": 0.5,
        "relationship_inference_enabled": True,
    },
    "embed": {"embedding_model_id": "amazon.titan-embed-text-v1", "search_tier": "standard"},
    "graph_load": {"load_strategy": "bulk_csv", "batch_size": 500},
    "store_artifact": {"artifact_format": "json", "include_raw_text": False},
    "face_crop": {"enabled": True, "min_face_confidence": 0.90, "thumbnail_size": 100, "thumbnail_format": "jpeg"},
}

CASE_OVERRIDE = {
    "extract": {
        "confidence_threshold": 0.8,
        "entity_types": ["person", "organization"],
    },
    "graph_load": {"batch_size": 1000},
}


@pytest.fixture()
def mock_cursor():
    cursor = MagicMock()
    return cursor


@pytest.fixture()
def mock_db(mock_cursor):
    db = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield mock_cursor

    db.cursor = _cursor_ctx
    return db


@pytest.fixture()
def service(mock_db):
    return ConfigResolutionService(mock_db)


# ---------------------------------------------------------------------------
# deep_merge tests
# ---------------------------------------------------------------------------


class TestDeepMerge:
    def test_override_replaces_leaf(self):
        base = {"a": 1, "b": 2}
        override = {"b": 99}
        result = ConfigResolutionService.deep_merge(base, override)
        assert result == {"a": 1, "b": 99}

    def test_base_keys_preserved(self):
        base = {"a": 1, "b": 2, "c": 3}
        override = {"b": 99}
        result = ConfigResolutionService.deep_merge(base, override)
        assert result["a"] == 1
        assert result["c"] == 3

    def test_nested_dict_merge(self):
        base = {"extract": {"threshold": 0.5, "model": "sonnet"}}
        override = {"extract": {"threshold": 0.8}}
        result = ConfigResolutionService.deep_merge(base, override)
        assert result["extract"]["threshold"] == 0.8
        assert result["extract"]["model"] == "sonnet"

    def test_lists_replaced_wholesale(self):
        base = {"types": [1, 2, 3]}
        override = {"types": [4, 5]}
        result = ConfigResolutionService.deep_merge(base, override)
        assert result["types"] == [4, 5]

    def test_empty_override_is_identity(self):
        base = {"a": 1, "nested": {"b": 2}}
        result = ConfigResolutionService.deep_merge(base, {})
        assert result == base

    def test_empty_base_returns_override(self):
        override = {"a": 1}
        result = ConfigResolutionService.deep_merge({}, override)
        assert result == {"a": 1}

    def test_deeply_nested_merge(self):
        base = {"l1": {"l2": {"l3": {"val": "base"}, "other": "keep"}}}
        override = {"l1": {"l2": {"l3": {"val": "override"}}}}
        result = ConfigResolutionService.deep_merge(base, override)
        assert result["l1"]["l2"]["l3"]["val"] == "override"
        assert result["l1"]["l2"]["other"] == "keep"

    def test_override_adds_new_key(self):
        base = {"a": 1}
        override = {"b": 2}
        result = ConfigResolutionService.deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_does_not_mutate_base(self):
        base = {"nested": {"a": 1}}
        override = {"nested": {"a": 2}}
        ConfigResolutionService.deep_merge(base, override)
        assert base["nested"]["a"] == 1

    def test_full_config_merge(self):
        result = ConfigResolutionService.deep_merge(SYSTEM_DEFAULT, CASE_OVERRIDE)
        # Overridden values
        assert result["extract"]["confidence_threshold"] == 0.8
        assert result["extract"]["entity_types"] == ["person", "organization"]
        assert result["graph_load"]["batch_size"] == 1000
        # Inherited values
        assert result["parse"]["pdf_method"] == "text"
        assert result["extract"]["llm_model_id"] == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert result["graph_load"]["load_strategy"] == "bulk_csv"


# ---------------------------------------------------------------------------
# resolve_effective_config tests
# ---------------------------------------------------------------------------


class TestResolveEffectiveConfig:
    def test_with_case_override(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (
            SYSTEM_DEFAULT,
            CASE_OVERRIDE,
            3,
        )
        result = service.resolve_effective_config(CASE_ID)

        assert isinstance(result.case_id, UUID)
        assert str(result.case_id) == CASE_ID
        assert result.config_version == 3
        assert result.effective_json["extract"]["confidence_threshold"] == 0.8
        assert result.effective_json["parse"]["pdf_method"] == "text"

    def test_without_case_override(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (SYSTEM_DEFAULT, None, None)
        result = service.resolve_effective_config(CASE_ID)

        assert result.config_version is None
        assert result.effective_json == SYSTEM_DEFAULT

    def test_no_system_default_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(RuntimeError, match="No active system default"):
            service.resolve_effective_config(CASE_ID)

    def test_json_string_input(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (
            json.dumps(SYSTEM_DEFAULT),
            json.dumps(CASE_OVERRIDE),
            1,
        )
        result = service.resolve_effective_config(CASE_ID)
        assert result.effective_json["extract"]["confidence_threshold"] == 0.8

    def test_origins_annotated(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (SYSTEM_DEFAULT, CASE_OVERRIDE, 1)
        result = service.resolve_effective_config(CASE_ID)

        assert result.origins["extract.confidence_threshold"] == "case_override"
        assert result.origins["extract.entity_types"] == "case_override"
        assert result.origins["graph_load.batch_size"] == "case_override"
        assert result.origins["parse.pdf_method"] == "system_default"
        assert result.origins["extract.llm_model_id"] == "system_default"
        assert result.origins["store_artifact.artifact_format"] == "system_default"

    def test_origins_all_system_default_when_no_override(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (SYSTEM_DEFAULT, None, None)
        result = service.resolve_effective_config(CASE_ID)

        for origin in result.origins.values():
            assert origin == "system_default"


# ---------------------------------------------------------------------------
# get_system_default tests
# ---------------------------------------------------------------------------


class TestGetSystemDefault:
    def test_returns_config_dict(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (SYSTEM_DEFAULT,)
        result = service.get_system_default()
        assert result == SYSTEM_DEFAULT

    def test_json_string_input(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (json.dumps(SYSTEM_DEFAULT),)
        result = service.get_system_default()
        assert result == SYSTEM_DEFAULT

    def test_no_active_default_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(RuntimeError, match="No active system default"):
            service.get_system_default()


# ---------------------------------------------------------------------------
# get_case_override tests
# ---------------------------------------------------------------------------


class TestGetCaseOverride:
    def test_returns_override_dict(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (CASE_OVERRIDE,)
        result = service.get_case_override(CASE_ID)
        assert result == CASE_OVERRIDE

    def test_returns_none_when_no_override(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        result = service.get_case_override(CASE_ID)
        assert result is None

    def test_json_string_input(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (json.dumps(CASE_OVERRIDE),)
        result = service.get_case_override(CASE_ID)
        assert result == CASE_OVERRIDE


# ---------------------------------------------------------------------------
# _compute_origins tests
# ---------------------------------------------------------------------------


class TestComputeOrigins:
    def test_all_system_default(self):
        origins = ConfigResolutionService._compute_origins(
            {"a": 1, "b": 2}, {}
        )
        assert origins == {"a": "system_default", "b": "system_default"}

    def test_all_case_override(self):
        origins = ConfigResolutionService._compute_origins(
            {"a": 1}, {"a": 99}
        )
        assert origins == {"a": "case_override"}

    def test_nested_mixed(self):
        sd = {"section": {"key1": "v1", "key2": "v2"}}
        co = {"section": {"key1": "override"}}
        origins = ConfigResolutionService._compute_origins(sd, co)
        assert origins["section.key1"] == "case_override"
        assert origins["section.key2"] == "system_default"

    def test_override_only_key(self):
        origins = ConfigResolutionService._compute_origins(
            {}, {"new_key": "val"}
        )
        assert origins == {"new_key": "case_override"}
