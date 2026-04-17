"""Unit tests for Matter and Collection API Lambda handlers.

Tests cover request parsing, validation, delegation to services, and
structured response formatting for all matter/collection endpoints.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.models.hierarchy import (
    Collection,
    CollectionStatus,
    Matter,
    MatterStatus,
    PromotionSnapshot,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

def _make_matter(**overrides) -> Matter:
    defaults = dict(
        matter_id="m-001",
        org_id="org-001",
        matter_name="Test Matter",
        description="A test matter",
        status=MatterStatus.CREATED,
        matter_type="investigation",
        created_by="",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        last_activity=datetime(2024, 1, 1, tzinfo=timezone.utc),
        s3_prefix="orgs/org-001/matters/m-001/",
        neptune_subgraph_label="Entity_m-001",
    )
    defaults.update(overrides)
    return Matter(**defaults)


def _make_collection(**overrides) -> Collection:
    defaults = dict(
        collection_id="c-001",
        matter_id="m-001",
        org_id="org-001",
        collection_name="Test Collection",
        source_description="Test source",
        status=CollectionStatus.STAGING,
        uploaded_by="",
        uploaded_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        s3_prefix="orgs/org-001/matters/m-001/collections/c-001/",
    )
    defaults.update(overrides)
    return Collection(**defaults)


def _make_snapshot(**overrides) -> PromotionSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        collection_id="c-001",
        matter_id="m-001",
        entities_added=10,
        relationships_added=5,
        promoted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return PromotionSnapshot(**defaults)


def _api_event(body=None, path_params=None, query_params=None, headers=None,
               method="GET", resource="/"):
    """Build a minimal API Gateway proxy event."""
    event = {
        "httpMethod": method,
        "resource": resource,
        "requestContext": {"requestId": "req-123"},
        "pathParameters": path_params,
        "queryStringParameters": query_params,
        "headers": headers,
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


# -----------------------------------------------------------------------
# dispatch_handler routing tests
# -----------------------------------------------------------------------

class TestDispatchHandler:
    def test_options_returns_cors(self):
        from src.lambdas.api.matters import dispatch_handler

        event = _api_event(method="OPTIONS", resource="/matters/{id}")
        resp = dispatch_handler(event, None)
        assert resp["statusCode"] == 200
        assert "Access-Control-Allow-Origin" in resp["headers"]

    def test_unknown_route_returns_404(self):
        from src.lambdas.api.matters import dispatch_handler

        event = _api_event(method="GET", resource="/unknown")
        resp = dispatch_handler(event, None)
        assert resp["statusCode"] == 404


# -----------------------------------------------------------------------
# Matter handler tests
# -----------------------------------------------------------------------

class TestListMatters:
    @patch("src.lambdas.api.matters._build_matter_service")
    def test_list_matters_success(self, mock_build):
        from src.lambdas.api.matters import list_matters

        svc = MagicMock()
        svc.list_matters.return_value = [_make_matter()]
        mock_build.return_value = svc

        event = _api_event(path_params={"org_id": "org-001"})
        resp = list_matters(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert len(body["matters"]) == 1
        assert body["matters"][0]["matter_id"] == "m-001"

    def test_list_matters_missing_org_id(self):
        from src.lambdas.api.matters import list_matters

        event = _api_event(path_params={})
        resp = list_matters(event, None)
        assert resp["statusCode"] == 400


class TestCreateMatter:
    @patch("src.lambdas.api.matters._build_matter_service")
    def test_create_matter_success(self, mock_build):
        from src.lambdas.api.matters import create_matter

        svc = MagicMock()
        svc.create_matter.return_value = _make_matter()
        mock_build.return_value = svc

        event = _api_event(
            body={"matter_name": "Test", "description": "Desc"},
            path_params={"org_id": "org-001"},
        )
        resp = create_matter(event, None)

        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert body["matter_id"] == "m-001"

    def test_create_matter_missing_fields(self):
        from src.lambdas.api.matters import create_matter

        event = _api_event(
            body={"matter_name": ""},
            path_params={"org_id": "org-001"},
        )
        resp = create_matter(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "matter_name" in body["error"]["message"]


class TestGetMatter:
    @patch("src.lambdas.api.matters._build_matter_service")
    def test_get_matter_success(self, mock_build):
        from src.lambdas.api.matters import get_matter

        svc = MagicMock()
        svc.get_matter.return_value = _make_matter()
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-001"},
            query_params={"org_id": "org-001"},
        )
        resp = get_matter(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["matter_id"] == "m-001"

    @patch("src.lambdas.api.matters._build_matter_service")
    def test_get_matter_not_found(self, mock_build):
        from src.lambdas.api.matters import get_matter

        svc = MagicMock()
        svc.get_matter.side_effect = KeyError("Matter not found")
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-999"},
            query_params={"org_id": "org-001"},
        )
        resp = get_matter(event, None)
        assert resp["statusCode"] == 404

    def test_get_matter_missing_org_id(self):
        from src.lambdas.api.matters import get_matter

        event = _api_event(path_params={"id": "m-001"})
        resp = get_matter(event, None)
        assert resp["statusCode"] == 400


class TestUpdateStatus:
    @patch("src.lambdas.api.matters._build_matter_service")
    def test_update_status_success(self, mock_build):
        from src.lambdas.api.matters import update_status

        svc = MagicMock()
        svc.update_status.return_value = _make_matter(status=MatterStatus.INGESTING)
        mock_build.return_value = svc

        event = _api_event(
            body={"status": "ingesting"},
            path_params={"id": "m-001"},
            query_params={"org_id": "org-001"},
        )
        resp = update_status(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["status"] == "ingesting"

    def test_update_status_missing_status(self):
        from src.lambdas.api.matters import update_status

        event = _api_event(
            body={},
            path_params={"id": "m-001"},
            query_params={"org_id": "org-001"},
        )
        resp = update_status(event, None)
        assert resp["statusCode"] == 400


class TestDeleteMatter:
    @patch("src.lambdas.api.matters._build_matter_service")
    def test_delete_matter_success(self, mock_build):
        from src.lambdas.api.matters import delete_matter

        svc = MagicMock()
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-001"},
            query_params={"org_id": "org-001"},
        )
        resp = delete_matter(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["deleted"] is True

    @patch("src.lambdas.api.matters._build_matter_service")
    def test_delete_matter_not_found(self, mock_build):
        from src.lambdas.api.matters import delete_matter

        svc = MagicMock()
        svc.delete_matter.side_effect = KeyError("Matter not found")
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-999"},
            query_params={"org_id": "org-001"},
        )
        resp = delete_matter(event, None)
        assert resp["statusCode"] == 404


# -----------------------------------------------------------------------
# Collection handler tests
# -----------------------------------------------------------------------

class TestListCollections:
    @patch("src.lambdas.api.matters._build_collection_service")
    def test_list_collections_success(self, mock_build):
        from src.lambdas.api.matters import list_collections

        svc = MagicMock()
        svc.list_collections.return_value = [_make_collection()]
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-001"},
            query_params={"org_id": "org-001"},
        )
        resp = list_collections(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert len(body["collections"]) == 1
        assert body["collections"][0]["collection_id"] == "c-001"

    def test_list_collections_missing_org_id(self):
        from src.lambdas.api.matters import list_collections

        event = _api_event(path_params={"id": "m-001"})
        resp = list_collections(event, None)
        assert resp["statusCode"] == 400


class TestCreateCollection:
    @patch("src.lambdas.api.matters._build_collection_service")
    def test_create_collection_success(self, mock_build):
        from src.lambdas.api.matters import create_collection

        svc = MagicMock()
        svc.create_collection.return_value = _make_collection()
        mock_build.return_value = svc

        event = _api_event(
            body={"collection_name": "Batch 1", "source_description": "FBI files"},
            path_params={"id": "m-001"},
            query_params={"org_id": "org-001"},
        )
        resp = create_collection(event, None)

        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert body["collection_id"] == "c-001"

    def test_create_collection_missing_name(self):
        from src.lambdas.api.matters import create_collection

        event = _api_event(
            body={},
            path_params={"id": "m-001"},
            query_params={"org_id": "org-001"},
        )
        resp = create_collection(event, None)
        assert resp["statusCode"] == 400


class TestGetCollection:
    @patch("src.lambdas.api.matters._build_collection_service")
    def test_get_collection_success(self, mock_build):
        from src.lambdas.api.matters import get_collection

        svc = MagicMock()
        svc.get_collection.return_value = _make_collection()
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-001", "cid": "c-001"},
            query_params={"org_id": "org-001"},
        )
        resp = get_collection(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["collection_id"] == "c-001"

    @patch("src.lambdas.api.matters._build_collection_service")
    def test_get_collection_not_found(self, mock_build):
        from src.lambdas.api.matters import get_collection

        svc = MagicMock()
        svc.get_collection.side_effect = KeyError("Collection not found")
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-001", "cid": "c-999"},
            query_params={"org_id": "org-001"},
        )
        resp = get_collection(event, None)
        assert resp["statusCode"] == 404


class TestPromoteCollection:
    @patch("src.lambdas.api.matters._build_promotion_service")
    def test_promote_collection_success(self, mock_build):
        from src.lambdas.api.matters import promote_collection

        svc = MagicMock()
        svc.promote_collection.return_value = _make_snapshot()
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-001", "cid": "c-001"},
            query_params={"org_id": "org-001"},
        )
        resp = promote_collection(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["snapshot_id"] == "snap-001"
        assert body["entities_added"] == 10

    @patch("src.lambdas.api.matters._build_promotion_service")
    def test_promote_collection_wrong_status(self, mock_build):
        from src.lambdas.api.matters import promote_collection

        svc = MagicMock()
        svc.promote_collection.side_effect = ValueError("Collection must be in qa_review")
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-001", "cid": "c-001"},
            query_params={"org_id": "org-001"},
        )
        resp = promote_collection(event, None)
        assert resp["statusCode"] == 409


class TestRejectCollection:
    @patch("src.lambdas.api.matters._build_collection_service")
    def test_reject_collection_success(self, mock_build):
        from src.lambdas.api.matters import reject_collection

        svc = MagicMock()
        svc.reject_collection.return_value = _make_collection(status=CollectionStatus.REJECTED)
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-001", "cid": "c-001"},
            query_params={"org_id": "org-001"},
        )
        resp = reject_collection(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["status"] == "rejected"

    @patch("src.lambdas.api.matters._build_collection_service")
    def test_reject_collection_wrong_status(self, mock_build):
        from src.lambdas.api.matters import reject_collection

        svc = MagicMock()
        svc.reject_collection.side_effect = ValueError("Cannot reject")
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "m-001", "cid": "c-001"},
            query_params={"org_id": "org-001"},
        )
        resp = reject_collection(event, None)
        assert resp["statusCode"] == 409
