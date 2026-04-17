"""Unit tests for PipelineConfigService."""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, call
from uuid import UUID, uuid4

import pytest

from src.models.pipeline_config import ConfigVersion, PipelineConfig
from src.services.config_validation_service import CONFIG_TEMPLATES, ConfigValidationService
from src.services.config_resolution_service import ConfigResolutionService
from src.services.pipeline_config_service import PipelineConfigService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER_CASE_ID = "11111111-2222-3333-4444-555555555555"
USER = "investigator@doj.gov"
NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

VALID_CONFIG = {
    "extract": {
        "confidence_threshold": 0.7,
        "entity_types": ["person", "organization"],
    },
    "graph_load": {"batch_size": 1000},
}

INVALID_CONFIG = {
    "extract": {"confidence_threshold": 2.0},  # out of range
}


@pytest.fixture()
def mock_cursor():
    return MagicMock()


@pytest.fixture()
def mock_db(mock_cursor):
    db = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield mock_cursor

    db.cursor = _cursor_ctx
    return db


@pytest.fixture()
def validator():
    return ConfigValidationService()


@pytest.fixture()
def resolution(mock_db):
    return ConfigResolutionService(mock_db)


@pytest.fixture()
def service(mock_db, validator, resolution):
    return PipelineConfigService(mock_db, validator, resolution)


# ---------------------------------------------------------------------------
# create_or_update_config tests
# ---------------------------------------------------------------------------


class TestCreateOrUpdateConfig:
    def test_creates_first_version(self, service, mock_cursor):
        config_id = uuid4()
        mock_cursor.fetchone.side_effect = [
            (0,),                    # MAX(version) = 0
            (config_id, NOW),        # INSERT RETURNING
        ]

        result = service.create_or_update_config(CASE_ID, VALID_CONFIG, USER)

        assert isinstance(result, ConfigVersion)
        assert result.version == 1
        assert result.config_json == VALID_CONFIG
        assert result.created_by == USER
        assert result.config_id == config_id

    def test_increments_version(self, service, mock_cursor):
        config_id = uuid4()
        mock_cursor.fetchone.side_effect = [
            (3,),                    # MAX(version) = 3
            (config_id, NOW),        # INSERT RETURNING
        ]

        result = service.create_or_update_config(CASE_ID, VALID_CONFIG, USER)
        assert result.version == 4

    def test_deactivates_previous_version(self, service, mock_cursor):
        config_id = uuid4()
        mock_cursor.fetchone.side_effect = [
            (1,),
            (config_id, NOW),
        ]

        service.create_or_update_config(CASE_ID, VALID_CONFIG, USER)

        # Verify the UPDATE SET is_active = FALSE was called
        calls = mock_cursor.execute.call_args_list
        deactivate_call = calls[1]
        assert "is_active = FALSE" in deactivate_call[0][0]
        assert deactivate_call[0][1] == (CASE_ID,)

    def test_rejects_invalid_config(self, service, mock_cursor):
        with pytest.raises(ValueError, match="Config validation failed"):
            service.create_or_update_config(CASE_ID, INVALID_CONFIG, USER)

        # Should not have executed any SQL
        mock_cursor.execute.assert_not_called()

    def test_rejects_unknown_top_level_key(self, service, mock_cursor):
        bad_config = {"bogus_section": {"key": "val"}}
        with pytest.raises(ValueError, match="Config validation failed"):
            service.create_or_update_config(CASE_ID, bad_config, USER)

    def test_inserts_config_json_as_json_string(self, service, mock_cursor):
        config_id = uuid4()
        mock_cursor.fetchone.side_effect = [
            (0,),
            (config_id, NOW),
        ]

        service.create_or_update_config(CASE_ID, VALID_CONFIG, USER)

        insert_call = mock_cursor.execute.call_args_list[2]
        # The 4th param (index 3) should be the JSON-serialized config
        assert insert_call[0][1][2] == json.dumps(VALID_CONFIG)


# ---------------------------------------------------------------------------
# get_active_config tests
# ---------------------------------------------------------------------------


class TestGetActiveConfig:
    def test_returns_active_config(self, service, mock_cursor):
        config_id = uuid4()
        case_uuid = UUID(CASE_ID)
        mock_cursor.fetchone.return_value = (
            config_id, case_uuid, 2, VALID_CONFIG, NOW, USER, True,
        )

        result = service.get_active_config(CASE_ID)

        assert isinstance(result, PipelineConfig)
        assert result.version == 2
        assert result.config_json == VALID_CONFIG
        assert result.is_active is True

    def test_returns_none_when_no_active(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        result = service.get_active_config(CASE_ID)
        assert result is None

    def test_handles_json_string_config(self, service, mock_cursor):
        config_id = uuid4()
        case_uuid = UUID(CASE_ID)
        mock_cursor.fetchone.return_value = (
            config_id, case_uuid, 1, json.dumps(VALID_CONFIG), NOW, USER, True,
        )

        result = service.get_active_config(CASE_ID)
        assert result.config_json == VALID_CONFIG


# ---------------------------------------------------------------------------
# list_versions tests
# ---------------------------------------------------------------------------


class TestListVersions:
    def test_returns_versions_desc(self, service, mock_cursor):
        config_id_1 = uuid4()
        config_id_2 = uuid4()
        case_uuid = UUID(CASE_ID)
        mock_cursor.fetchall.return_value = [
            (config_id_2, case_uuid, 2, VALID_CONFIG, NOW, USER),
            (config_id_1, case_uuid, 1, {"extract": {"confidence_threshold": 0.5}}, NOW, USER),
        ]

        result = service.list_versions(CASE_ID)

        assert len(result) == 2
        assert result[0].version == 2
        assert result[1].version == 1

    def test_returns_empty_list_when_no_versions(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = service.list_versions(CASE_ID)
        assert result == []

    def test_handles_json_string_config(self, service, mock_cursor):
        config_id = uuid4()
        case_uuid = UUID(CASE_ID)
        mock_cursor.fetchall.return_value = [
            (config_id, case_uuid, 1, json.dumps(VALID_CONFIG), NOW, USER),
        ]

        result = service.list_versions(CASE_ID)
        assert result[0].config_json == VALID_CONFIG


# ---------------------------------------------------------------------------
# get_version tests
# ---------------------------------------------------------------------------


class TestGetVersion:
    def test_returns_specific_version(self, service, mock_cursor):
        config_id = uuid4()
        case_uuid = UUID(CASE_ID)
        mock_cursor.fetchone.return_value = (
            config_id, case_uuid, 3, VALID_CONFIG, NOW, USER,
        )

        result = service.get_version(CASE_ID, 3)

        assert isinstance(result, ConfigVersion)
        assert result.version == 3
        assert result.config_json == VALID_CONFIG

    def test_raises_when_not_found(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(ValueError, match="Config version 99 not found"):
            service.get_version(CASE_ID, 99)


# ---------------------------------------------------------------------------
# rollback_to_version tests
# ---------------------------------------------------------------------------


class TestRollbackToVersion:
    def test_creates_new_version_with_target_content(self, service, mock_cursor):
        config_id = uuid4()
        new_config_id = uuid4()
        case_uuid = UUID(CASE_ID)
        target_config = {"extract": {"confidence_threshold": 0.6}}

        # First call: get_version (SELECT by case_id + version)
        # Second call: create_or_update_config → MAX(version)
        # Third call: create_or_update_config → INSERT RETURNING
        mock_cursor.fetchone.side_effect = [
            (config_id, case_uuid, 2, target_config, NOW, USER),  # get_version
            (5,),                                                   # MAX(version) = 5
            (new_config_id, NOW),                                   # INSERT RETURNING
        ]

        result = service.rollback_to_version(CASE_ID, 2, USER)

        assert result.version == 6
        assert result.config_json == target_config

    def test_raises_when_target_not_found(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(ValueError, match="Config version 99 not found"):
            service.rollback_to_version(CASE_ID, 99, USER)


# ---------------------------------------------------------------------------
# export_config tests
# ---------------------------------------------------------------------------


class TestExportConfig:
    def test_exports_with_metadata(self, service, mock_cursor):
        config_id = uuid4()
        case_uuid = UUID(CASE_ID)
        mock_cursor.fetchone.return_value = (
            config_id, case_uuid, 3, VALID_CONFIG, NOW, USER, True,
        )

        result = service.export_config(CASE_ID)

        assert "metadata" in result
        assert "config_json" in result
        assert result["config_json"] == VALID_CONFIG
        assert result["metadata"]["source_case_id"] == CASE_ID
        assert result["metadata"]["config_version"] == 3
        assert "exported_at" in result["metadata"]

    def test_raises_when_no_active_config(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(ValueError, match="No active config found"):
            service.export_config(CASE_ID)


# ---------------------------------------------------------------------------
# import_config tests
# ---------------------------------------------------------------------------


class TestImportConfig:
    def test_imports_valid_config(self, service, mock_cursor):
        config_id = uuid4()
        export_doc = {
            "metadata": {
                "source_case_id": OTHER_CASE_ID,
                "config_version": 5,
                "exported_at": "2024-06-15T12:00:00+00:00",
            },
            "config_json": VALID_CONFIG,
        }

        mock_cursor.fetchone.side_effect = [
            (0,),                    # MAX(version)
            (config_id, NOW),        # INSERT RETURNING
        ]

        result = service.import_config(CASE_ID, export_doc, USER)

        assert isinstance(result, ConfigVersion)
        assert result.version == 1
        assert result.config_json == VALID_CONFIG

    def test_raises_when_missing_config_json(self, service, mock_cursor):
        export_doc = {"metadata": {"source_case_id": OTHER_CASE_ID}}
        with pytest.raises(ValueError, match="config_json"):
            service.import_config(CASE_ID, export_doc, USER)

    def test_rejects_invalid_imported_config(self, service, mock_cursor):
        export_doc = {"config_json": INVALID_CONFIG}
        with pytest.raises(ValueError, match="Config validation failed"):
            service.import_config(CASE_ID, export_doc, USER)


# ---------------------------------------------------------------------------
# apply_template tests
# ---------------------------------------------------------------------------


class TestApplyTemplate:
    def test_applies_antitrust_template(self, service, mock_cursor):
        config_id = uuid4()
        mock_cursor.fetchone.side_effect = [
            (0,),
            (config_id, NOW),
        ]

        result = service.apply_template(CASE_ID, "antitrust", USER)

        assert result.config_json == CONFIG_TEMPLATES["antitrust"]
        assert result.version == 1

    def test_applies_criminal_template(self, service, mock_cursor):
        config_id = uuid4()
        mock_cursor.fetchone.side_effect = [
            (0,),
            (config_id, NOW),
        ]

        result = service.apply_template(CASE_ID, "criminal", USER)
        assert result.config_json == CONFIG_TEMPLATES["criminal"]

    def test_applies_financial_fraud_template(self, service, mock_cursor):
        config_id = uuid4()
        mock_cursor.fetchone.side_effect = [
            (0,),
            (config_id, NOW),
        ]

        result = service.apply_template(CASE_ID, "financial_fraud", USER)
        assert result.config_json == CONFIG_TEMPLATES["financial_fraud"]

    def test_raises_for_unknown_template(self, service, mock_cursor):
        with pytest.raises(ValueError, match="Unknown template 'nonexistent'"):
            service.apply_template(CASE_ID, "nonexistent", USER)

    def test_all_templates_produce_valid_configs(self, service, mock_cursor):
        """Each template should pass validation when applied."""
        for name in CONFIG_TEMPLATES:
            config_id = uuid4()
            mock_cursor.fetchone.side_effect = [
                (0,),
                (config_id, NOW),
            ]
            # Should not raise
            result = service.apply_template(CASE_ID, name, USER)
            assert result.config_json == CONFIG_TEMPLATES[name]


# ---------------------------------------------------------------------------
# Integration-style: export → import round-trip
# ---------------------------------------------------------------------------


class TestExportImportRoundTrip:
    def test_round_trip_preserves_config(self, service, mock_cursor):
        config_id_1 = uuid4()
        config_id_2 = uuid4()
        case_uuid = UUID(CASE_ID)

        # Setup: export from source case
        mock_cursor.fetchone.return_value = (
            config_id_1, case_uuid, 2, VALID_CONFIG, NOW, USER, True,
        )
        export_doc = service.export_config(CASE_ID)

        # Import into target case
        mock_cursor.fetchone.side_effect = [
            (0,),                        # MAX(version)
            (config_id_2, NOW),          # INSERT RETURNING
        ]
        result = service.import_config(OTHER_CASE_ID, export_doc, USER)

        assert result.config_json == VALID_CONFIG
