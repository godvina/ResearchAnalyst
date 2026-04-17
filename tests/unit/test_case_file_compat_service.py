"""Unit tests for CaseFileCompatService — backward-compatible shim over MatterService."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.models.case_file import CaseFile, CaseFileStatus, SearchTier
from src.models.hierarchy import Matter, MatterStatus
from src.services.case_file_compat_service import (
    CaseFileCompatService,
    _matter_to_case_file,
)
from src.services.matter_service import MatterService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_ID = "org-default"
_NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_matter(
    matter_id="mat-001",
    org_id=_ORG_ID,
    matter_name="Test Investigation",
    description="A test matter",
    status=MatterStatus.CREATED,
    matter_type="investigation",
    created_by="analyst",
    created_at=_NOW,
    last_activity=_NOW,
    s3_prefix="orgs/org-default/matters/mat-001/",
    neptune_subgraph_label="Entity_mat-001",
    total_documents=10,
    total_entities=50,
    total_relationships=30,
    search_tier="standard",
    error_details=None,
) -> Matter:
    return Matter(
        matter_id=matter_id,
        org_id=org_id,
        matter_name=matter_name,
        description=description,
        status=status,
        matter_type=matter_type,
        created_by=created_by,
        created_at=created_at,
        last_activity=last_activity,
        s3_prefix=s3_prefix,
        neptune_subgraph_label=neptune_subgraph_label,
        total_documents=total_documents,
        total_entities=total_entities,
        total_relationships=total_relationships,
        search_tier=search_tier,
        error_details=error_details,
    )


@pytest.fixture()
def mock_matter_service():
    return MagicMock(spec=MatterService)


@pytest.fixture()
def compat_service(mock_matter_service):
    return CaseFileCompatService(mock_matter_service, _ORG_ID)


# ---------------------------------------------------------------------------
# _matter_to_case_file translation
# ---------------------------------------------------------------------------


class TestMatterToCaseFileTranslation:
    def test_maps_matter_id_to_case_id(self):
        cf = _matter_to_case_file(_make_matter(matter_id="mat-xyz"))
        assert cf.case_id == "mat-xyz"

    def test_maps_matter_name_to_topic_name(self):
        cf = _matter_to_case_file(_make_matter(matter_name="Alien Research"))
        assert cf.topic_name == "Alien Research"

    def test_maps_total_documents_to_document_count(self):
        cf = _matter_to_case_file(_make_matter(total_documents=42))
        assert cf.document_count == 42

    def test_maps_total_entities_to_entity_count(self):
        cf = _matter_to_case_file(_make_matter(total_entities=99))
        assert cf.entity_count == 99

    def test_maps_total_relationships_to_relationship_count(self):
        cf = _matter_to_case_file(_make_matter(total_relationships=17))
        assert cf.relationship_count == 17

    def test_preserves_description(self):
        cf = _matter_to_case_file(_make_matter(description="Deep dive"))
        assert cf.description == "Deep dive"

    def test_preserves_s3_prefix(self):
        cf = _matter_to_case_file(_make_matter(s3_prefix="orgs/o/matters/m/"))
        assert cf.s3_prefix == "orgs/o/matters/m/"

    def test_preserves_neptune_label(self):
        cf = _matter_to_case_file(_make_matter(neptune_subgraph_label="Entity_m1"))
        assert cf.neptune_subgraph_label == "Entity_m1"

    def test_preserves_timestamps(self):
        cf = _matter_to_case_file(_make_matter(created_at=_NOW, last_activity=_NOW))
        assert cf.created_at == _NOW
        assert cf.last_activity == _NOW

    def test_preserves_error_details(self):
        cf = _matter_to_case_file(_make_matter(error_details="something broke"))
        assert cf.error_details == "something broke"

    def test_maps_search_tier(self):
        cf = _matter_to_case_file(_make_matter(search_tier="enterprise"))
        assert cf.search_tier == SearchTier.ENTERPRISE

    def test_defaults_unknown_search_tier_to_standard(self):
        cf = _matter_to_case_file(_make_matter(search_tier="unknown_tier"))
        assert cf.search_tier == SearchTier.STANDARD

    def test_parent_case_id_is_none(self):
        cf = _matter_to_case_file(_make_matter())
        assert cf.parent_case_id is None

    def test_status_translation_all_values(self):
        for ms, cfs in [
            (MatterStatus.CREATED, CaseFileStatus.CREATED),
            (MatterStatus.INGESTING, CaseFileStatus.INGESTING),
            (MatterStatus.INDEXED, CaseFileStatus.INDEXED),
            (MatterStatus.INVESTIGATING, CaseFileStatus.INVESTIGATING),
            (MatterStatus.ARCHIVED, CaseFileStatus.ARCHIVED),
            (MatterStatus.ERROR, CaseFileStatus.ERROR),
        ]:
            cf = _matter_to_case_file(_make_matter(status=ms))
            assert cf.status == cfs, f"Expected {cfs} for {ms}, got {cf.status}"


# ---------------------------------------------------------------------------
# get_case_file
# ---------------------------------------------------------------------------


class TestGetCaseFile:
    def test_delegates_to_matter_service(self, compat_service, mock_matter_service):
        mock_matter_service.get_matter.return_value = _make_matter()
        compat_service.get_case_file("mat-001")
        mock_matter_service.get_matter.assert_called_once_with("mat-001", _ORG_ID)

    def test_returns_case_file(self, compat_service, mock_matter_service):
        mock_matter_service.get_matter.return_value = _make_matter()
        cf = compat_service.get_case_file("mat-001")
        assert cf.__class__.__name__ == "CaseFile"
        assert cf.case_id == "mat-001"
        assert cf.topic_name == "Test Investigation"

    def test_propagates_key_error(self, compat_service, mock_matter_service):
        mock_matter_service.get_matter.side_effect = KeyError("Matter not found: x")
        with pytest.raises(KeyError, match="Matter not found"):
            compat_service.get_case_file("x")


# ---------------------------------------------------------------------------
# list_case_files
# ---------------------------------------------------------------------------


class TestListCaseFiles:
    def test_delegates_to_matter_service(self, compat_service, mock_matter_service):
        mock_matter_service.list_matters.return_value = []
        compat_service.list_case_files()
        mock_matter_service.list_matters.assert_called_once_with(_ORG_ID)

    def test_passes_kwargs(self, compat_service, mock_matter_service):
        mock_matter_service.list_matters.return_value = []
        compat_service.list_case_files(status="archived")
        mock_matter_service.list_matters.assert_called_once_with(_ORG_ID, status="archived")

    def test_returns_list_of_case_files(self, compat_service, mock_matter_service):
        mock_matter_service.list_matters.return_value = [
            _make_matter(matter_id="m1", matter_name="First"),
            _make_matter(matter_id="m2", matter_name="Second"),
        ]
        result = compat_service.list_case_files()
        assert len(result) == 2
        assert all(cf.__class__.__name__ == "CaseFile" for cf in result)
        assert result[0].case_id == "m1"
        assert result[1].case_id == "m2"

    def test_empty_list(self, compat_service, mock_matter_service):
        mock_matter_service.list_matters.return_value = []
        result = compat_service.list_case_files()
        assert result == []


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    def test_translates_case_file_status_to_matter_status(self, compat_service, mock_matter_service):
        mock_matter_service.update_status.return_value = _make_matter(status=MatterStatus.INGESTING)
        compat_service.update_status("mat-001", CaseFileStatus.INGESTING)
        mock_matter_service.update_status.assert_called_once_with(
            "mat-001", _ORG_ID, MatterStatus.INGESTING, error_details=None
        )

    def test_accepts_string_status(self, compat_service, mock_matter_service):
        mock_matter_service.update_status.return_value = _make_matter(status=MatterStatus.INDEXED)
        compat_service.update_status("mat-001", "indexed")
        mock_matter_service.update_status.assert_called_once_with(
            "mat-001", _ORG_ID, MatterStatus.INDEXED, error_details=None
        )

    def test_passes_error_details(self, compat_service, mock_matter_service):
        mock_matter_service.update_status.return_value = _make_matter(
            status=MatterStatus.ERROR, error_details="boom"
        )
        compat_service.update_status("mat-001", CaseFileStatus.ERROR, error_details="boom")
        mock_matter_service.update_status.assert_called_once_with(
            "mat-001", _ORG_ID, MatterStatus.ERROR, error_details="boom"
        )

    def test_returns_case_file(self, compat_service, mock_matter_service):
        mock_matter_service.update_status.return_value = _make_matter(status=MatterStatus.ARCHIVED)
        cf = compat_service.update_status("mat-001", CaseFileStatus.ARCHIVED)
        assert cf.__class__.__name__ == "CaseFile"
        assert cf.status == CaseFileStatus.ARCHIVED

    def test_all_statuses_translate_correctly(self, compat_service, mock_matter_service):
        for cfs, ms in [
            (CaseFileStatus.CREATED, MatterStatus.CREATED),
            (CaseFileStatus.INGESTING, MatterStatus.INGESTING),
            (CaseFileStatus.INDEXED, MatterStatus.INDEXED),
            (CaseFileStatus.INVESTIGATING, MatterStatus.INVESTIGATING),
            (CaseFileStatus.ARCHIVED, MatterStatus.ARCHIVED),
            (CaseFileStatus.ERROR, MatterStatus.ERROR),
        ]:
            mock_matter_service.update_status.return_value = _make_matter(status=ms)
            cf = compat_service.update_status("mat-001", cfs)
            assert cf.status == cfs

    def test_propagates_key_error(self, compat_service, mock_matter_service):
        mock_matter_service.update_status.side_effect = KeyError("Matter not found: x")
        with pytest.raises(KeyError, match="Matter not found"):
            compat_service.update_status("x", CaseFileStatus.INGESTING)

    def test_invalid_string_status_raises(self, compat_service, mock_matter_service):
        with pytest.raises(ValueError):
            compat_service.update_status("mat-001", "bogus")
