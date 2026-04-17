"""Unit tests for PipelineStatusService."""

import json
import time
from unittest.mock import MagicMock, call, patch

import pytest

from src.services.pipeline_status_service import PipelineStatusService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "abc-123"
BUCKET = "test-bucket"


@pytest.fixture()
def s3_client():
    return MagicMock()


@pytest.fixture()
def service(s3_client):
    svc = PipelineStatusService(
        s3_client=s3_client,
        aurora_cm=None,
        neptune_endpoint="",
        neptune_port="8182",
        opensearch_endpoint="",
    )
    svc._bucket = BUCKET
    return svc


# ---------------------------------------------------------------------------
# _get_s3_stats tests
# ---------------------------------------------------------------------------


class TestGetS3StatsMultiPrefix:
    """Tests for the refactored multi-prefix _get_s3_stats method."""

    def test_aggregates_counts_across_all_prefixes(self, service, s3_client):
        """Counts from all three prefixes are summed into total_objects."""
        def mock_list(**kwargs):
            prefix = kwargs["Prefix"]
            if prefix == f"cases/{CASE_ID}/raw/":
                return {"KeyCount": 100, "IsTruncated": False}
            elif prefix == f"cases/{CASE_ID}/documents/":
                return {"KeyCount": 50, "IsTruncated": False}
            elif prefix == "epstein_files/":
                return {"KeyCount": 200, "IsTruncated": False}
            return {"KeyCount": 0, "IsTruncated": False}

        s3_client.list_objects_v2.side_effect = mock_list

        result = service._get_s3_stats(CASE_ID)

        assert result["total_objects"] == 350
        assert len(result["matched_prefixes"]) == 3
        assert f"cases/{CASE_ID}/raw/" in result["matched_prefixes"]
        assert f"cases/{CASE_ID}/documents/" in result["matched_prefixes"]
        assert "epstein_files/" in result["matched_prefixes"]

    def test_only_non_zero_prefixes_in_matched(self, service, s3_client):
        """matched_prefixes only includes prefixes with count > 0."""
        def mock_list(**kwargs):
            prefix = kwargs["Prefix"]
            if prefix == f"cases/{CASE_ID}/raw/":
                return {"KeyCount": 0, "IsTruncated": False}
            elif prefix == f"cases/{CASE_ID}/documents/":
                return {"KeyCount": 75, "IsTruncated": False}
            elif prefix == "epstein_files/":
                return {"KeyCount": 0, "IsTruncated": False}
            return {"KeyCount": 0, "IsTruncated": False}

        s3_client.list_objects_v2.side_effect = mock_list

        result = service._get_s3_stats(CASE_ID)

        assert result["total_objects"] == 75
        assert result["matched_prefixes"] == [f"cases/{CASE_ID}/documents/"]

    def test_all_prefixes_empty(self, service, s3_client):
        """Returns 0 total and empty matched_prefixes when all prefixes are empty."""
        s3_client.list_objects_v2.return_value = {"KeyCount": 0, "IsTruncated": False}

        result = service._get_s3_stats(CASE_ID)

        assert result["total_objects"] == 0
        assert result["matched_prefixes"] == []
        assert result["truncated"] is False

    def test_pagination_aggregates_multiple_pages(self, service, s3_client):
        """Paginated responses are correctly aggregated for a single prefix."""
        responses = [
            # First prefix, page 1
            {"KeyCount": 1000, "IsTruncated": True, "NextContinuationToken": "tok1"},
            # First prefix, page 2
            {"KeyCount": 500, "IsTruncated": False},
            # Second prefix
            {"KeyCount": 0, "IsTruncated": False},
            # Third prefix
            {"KeyCount": 0, "IsTruncated": False},
        ]
        s3_client.list_objects_v2.side_effect = responses

        result = service._get_s3_stats(CASE_ID)

        assert result["total_objects"] == 1500
        assert result["matched_prefixes"] == [f"cases/{CASE_ID}/raw/"]

    def test_per_prefix_error_is_skipped_gracefully(self, service, s3_client):
        """A failing prefix is logged and skipped; other prefixes still counted."""
        call_count = 0

        def mock_list(**kwargs):
            nonlocal call_count
            call_count += 1
            prefix = kwargs["Prefix"]
            if prefix == f"cases/{CASE_ID}/raw/":
                raise Exception("Access Denied")
            elif prefix == f"cases/{CASE_ID}/documents/":
                return {"KeyCount": 30, "IsTruncated": False}
            elif prefix == "epstein_files/":
                return {"KeyCount": 20, "IsTruncated": False}
            return {"KeyCount": 0, "IsTruncated": False}

        s3_client.list_objects_v2.side_effect = mock_list

        result = service._get_s3_stats(CASE_ID)

        assert result["total_objects"] == 50
        assert f"cases/{CASE_ID}/raw/" not in result["matched_prefixes"]
        assert result["per_prefix_counts"][f"cases/{CASE_ID}/raw/"] == 0
        assert result["per_prefix_counts"][f"cases/{CASE_ID}/documents/"] == 30

    def test_timeout_guard_stops_early(self, service, s3_client):
        """When deadline is exceeded, remaining prefixes are skipped and truncated=True."""
        s3_client.list_objects_v2.return_value = {"KeyCount": 10, "IsTruncated": False}

        # Patch time.time to simulate timeout after first prefix completes
        base = 1000.0
        call_idx = [0]

        def mock_time():
            call_idx[0] += 1
            # Calls 1-4: initial deadline set + first prefix check + inside _count_s3_prefix (2 calls)
            if call_idx[0] <= 4:
                return base
            # After first prefix, jump past the deadline (base + 25 = 1025)
            return base + 30

        with patch("src.services.pipeline_status_service.time") as mock_time_module:
            mock_time_module.time = mock_time

            result = service._get_s3_stats(CASE_ID)

        assert result["truncated"] is True
        # First prefix was counted successfully
        assert result["total_objects"] == 10
        assert len(result["per_prefix_counts"]) < 3  # Not all prefixes attempted

    def test_returns_per_prefix_counts(self, service, s3_client):
        """per_prefix_counts dict contains counts for each prefix attempted."""
        def mock_list(**kwargs):
            prefix = kwargs["Prefix"]
            if prefix == f"cases/{CASE_ID}/raw/":
                return {"KeyCount": 10, "IsTruncated": False}
            elif prefix == f"cases/{CASE_ID}/documents/":
                return {"KeyCount": 0, "IsTruncated": False}
            elif prefix == "epstein_files/":
                return {"KeyCount": 5, "IsTruncated": False}
            return {"KeyCount": 0, "IsTruncated": False}

        s3_client.list_objects_v2.side_effect = mock_list

        result = service._get_s3_stats(CASE_ID)

        assert result["per_prefix_counts"][f"cases/{CASE_ID}/raw/"] == 10
        assert result["per_prefix_counts"][f"cases/{CASE_ID}/documents/"] == 0
        assert result["per_prefix_counts"]["epstein_files/"] == 5

    def test_uses_maxkeys_1000(self, service, s3_client):
        """list_objects_v2 is called with MaxKeys=1000."""
        s3_client.list_objects_v2.return_value = {"KeyCount": 0, "IsTruncated": False}

        service._get_s3_stats(CASE_ID)

        for c in s3_client.list_objects_v2.call_args_list:
            assert c.kwargs["MaxKeys"] == 1000

    def test_bucket_in_response(self, service, s3_client):
        """Response includes the bucket name."""
        s3_client.list_objects_v2.return_value = {"KeyCount": 0, "IsTruncated": False}

        result = service._get_s3_stats(CASE_ID)

        assert result["bucket"] == BUCKET


# ---------------------------------------------------------------------------
# _count_s3_prefix tests
# ---------------------------------------------------------------------------


class TestCountS3Prefix:
    """Tests for the _count_s3_prefix pagination helper."""

    def test_single_page(self, service, s3_client):
        s3_client.list_objects_v2.return_value = {"KeyCount": 42, "IsTruncated": False}
        deadline = time.time() + 25

        count = service._count_s3_prefix("some/prefix/", deadline)

        assert count == 42

    def test_multi_page(self, service, s3_client):
        s3_client.list_objects_v2.side_effect = [
            {"KeyCount": 1000, "IsTruncated": True, "NextContinuationToken": "tok1"},
            {"KeyCount": 1000, "IsTruncated": True, "NextContinuationToken": "tok2"},
            {"KeyCount": 300, "IsTruncated": False},
        ]
        deadline = time.time() + 25

        count = service._count_s3_prefix("some/prefix/", deadline)

        assert count == 2300

    def test_passes_continuation_token(self, service, s3_client):
        s3_client.list_objects_v2.side_effect = [
            {"KeyCount": 1000, "IsTruncated": True, "NextContinuationToken": "my-token"},
            {"KeyCount": 500, "IsTruncated": False},
        ]
        deadline = time.time() + 25

        service._count_s3_prefix("some/prefix/", deadline)

        second_call = s3_client.list_objects_v2.call_args_list[1]
        assert second_call.kwargs["ContinuationToken"] == "my-token"

    def test_stops_on_deadline(self, service, s3_client):
        """Returns partial count when deadline is reached mid-pagination."""
        s3_client.list_objects_v2.return_value = {
            "KeyCount": 1000, "IsTruncated": True, "NextContinuationToken": "tok"
        }
        # Set deadline in the past so it stops after first page
        deadline = time.time() - 1

        count = service._count_s3_prefix("some/prefix/", deadline)

        # Should return 0 since deadline already passed before first call
        assert count == 0


# ---------------------------------------------------------------------------
# _classify_workload_tier tests
# ---------------------------------------------------------------------------


class TestClassifyWorkloadTier:
    """Tests for workload tier classification boundaries and recommendations."""

    def test_small_tier_zero(self, service):
        result = service._classify_workload_tier(0)
        assert result["tier"] == "Small"
        assert result["range"] == "< 100"
        assert "serial processing is fine" in result["recommendation"]

    def test_small_tier_boundary(self, service):
        result = service._classify_workload_tier(99)
        assert result["tier"] == "Small"

    def test_medium_tier_lower_boundary(self, service):
        result = service._classify_workload_tier(100)
        assert result["tier"] == "Medium"
        assert result["range"] == "100–10,000"
        assert "Step Functions Map state with concurrency 5–10" in result["recommendation"]

    def test_medium_tier_upper_boundary(self, service):
        result = service._classify_workload_tier(9_999)
        assert result["tier"] == "Medium"

    def test_large_tier_lower_boundary(self, service):
        result = service._classify_workload_tier(10_000)
        assert result["tier"] == "Large"
        assert result["range"] == "10,000–100,000"
        assert "concurrency 10–50" in result["recommendation"]

    def test_large_tier_upper_boundary(self, service):
        result = service._classify_workload_tier(99_999)
        assert result["tier"] == "Large"

    def test_enterprise_tier_lower_boundary(self, service):
        result = service._classify_workload_tier(100_000)
        assert result["tier"] == "Enterprise"
        assert result["range"] == "100,000+"
        assert "SQS fan-out" in result["recommendation"]

    def test_enterprise_tier_large_value(self, service):
        result = service._classify_workload_tier(1_000_000)
        assert result["tier"] == "Enterprise"

    def test_small_recommendation_includes_doc_count(self, service):
        result = service._classify_workload_tier(42)
        assert "42 docs" in result["recommendation"]


# ---------------------------------------------------------------------------
# _assess_health workload tier integration tests
# ---------------------------------------------------------------------------


class TestAssessHealthWorkloadTier:
    """Tests that _assess_health integrates workload tier into its response."""

    def test_health_includes_workload_tier(self, service):
        health = service._assess_health(
            total_source=50, processed=50, failed=0, throughput=10,
            error_rate=0, entities_per_doc=5, edges_per_node=2,
            eta_hours=0, total_source_files=50,
        )
        assert health["workload_tier"] == "Small"
        assert health["tier_range"] == "< 100"

    def test_health_medium_tier(self, service):
        health = service._assess_health(
            total_source=500, processed=500, failed=0, throughput=10,
            error_rate=0, entities_per_doc=5, edges_per_node=2,
            eta_hours=0, total_source_files=500,
        )
        assert health["workload_tier"] == "Medium"
        assert health["tier_range"] == "100–10,000"

    def test_health_tier_recommendation_in_list(self, service):
        health = service._assess_health(
            total_source=50_000, processed=50_000, failed=0, throughput=100,
            error_rate=0, entities_per_doc=5, edges_per_node=2,
            eta_hours=0, total_source_files=50_000,
        )
        assert health["workload_tier"] == "Large"
        tier_recs = [r for r in health["recommendations"] if "concurrency 10–50" in r]
        assert len(tier_recs) == 1

    def test_health_enterprise_tier(self, service):
        health = service._assess_health(
            total_source=200_000, processed=200_000, failed=0, throughput=100,
            error_rate=0, entities_per_doc=5, edges_per_node=2,
            eta_hours=0, total_source_files=200_000,
        )
        assert health["workload_tier"] == "Enterprise"
        assert "SQS fan-out" in " ".join(health["recommendations"])

    def test_health_defaults_to_zero_source_files(self, service):
        """When total_source_files is not passed, defaults to 0 (Small tier)."""
        health = service._assess_health(
            total_source=0, processed=0, failed=0, throughput=0,
            error_rate=0, entities_per_doc=0, edges_per_node=0,
            eta_hours=0,
        )
        assert health["workload_tier"] == "Small"


# ---------------------------------------------------------------------------
# _get_opensearch_stats multi-index fallback tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def os_service(s3_client):
    """Service with an OpenSearch endpoint configured."""
    svc = PipelineStatusService(
        s3_client=s3_client,
        aurora_cm=None,
        neptune_endpoint="",
        neptune_port="8182",
        opensearch_endpoint="search-test.us-east-1.aoss.amazonaws.com",
    )
    svc._bucket = BUCKET
    return svc


class TestGetOpensearchStatsMultiIndex:
    """Tests for the refactored multi-index _get_opensearch_stats method."""

    def test_returns_not_configured_when_no_endpoint(self, service):
        """Returns error when OpenSearch endpoint is empty."""
        result = service._get_opensearch_stats(CASE_ID)
        assert result["doc_count"] == 0
        assert "not configured" in result.get("error", "")

    def test_first_candidate_succeeds(self, os_service):
        """Returns immediately when the first index candidate has docs."""
        with patch.object(os_service, "_query_opensearch_count") as mock_count:
            mock_count.return_value = 500
            result = os_service._get_opensearch_stats(CASE_ID)

        assert result["doc_count"] == 500
        assert result["index"] == f"case_{CASE_ID.replace('-', '_')}"
        # Should only have been called once (first candidate succeeded)
        mock_count.assert_called_once_with(f"case_{CASE_ID.replace('-', '_')}")

    def test_falls_through_to_second_candidate(self, os_service):
        """Tries second candidate when first returns 0."""
        with patch.object(os_service, "_query_opensearch_count") as mock_count:
            mock_count.side_effect = [0, 250]
            result = os_service._get_opensearch_stats(CASE_ID)

        assert result["doc_count"] == 250
        assert result["index"] == f"case-{CASE_ID}"
        assert mock_count.call_count == 2

    def test_falls_through_to_third_candidate(self, os_service):
        """Tries third candidate when first two return 0."""
        with patch.object(os_service, "_query_opensearch_count") as mock_count:
            mock_count.side_effect = [0, 0, 100]
            result = os_service._get_opensearch_stats(CASE_ID)

        assert result["doc_count"] == 100
        assert result["index"] == CASE_ID
        assert mock_count.call_count == 3

    def test_cat_indices_discovery_fallback(self, os_service):
        """Falls back to _cat/indices discovery when all candidates return 0."""
        with patch.object(os_service, "_query_opensearch_count") as mock_count, \
             patch.object(os_service, "_discover_opensearch_index") as mock_discover:
            # All 3 candidates return 0, then discovered index returns 42
            mock_count.side_effect = [0, 0, 0, 42]
            mock_discover.return_value = "my_custom_index"

            result = os_service._get_opensearch_stats(CASE_ID)

        assert result["doc_count"] == 42
        assert result["index"] == "my_custom_index"
        mock_discover.assert_called_once_with(CASE_ID)

    def test_all_fail_returns_attempted_indices(self, os_service):
        """Returns 0 and attempted_indices when everything fails."""
        with patch.object(os_service, "_query_opensearch_count", return_value=0), \
             patch.object(os_service, "_discover_opensearch_index", return_value=None):
            result = os_service._get_opensearch_stats(CASE_ID)

        assert result["doc_count"] == 0
        assert "attempted_indices" in result
        expected_candidates = [
            f"case_{CASE_ID.replace('-', '_')}",
            f"case-{CASE_ID}",
            CASE_ID,
        ]
        assert result["attempted_indices"] == expected_candidates

    def test_discovery_returns_none_no_extra_query(self, os_service):
        """When _cat/indices finds nothing, no extra _count query is made."""
        with patch.object(os_service, "_query_opensearch_count") as mock_count, \
             patch.object(os_service, "_discover_opensearch_index", return_value=None):
            mock_count.return_value = 0
            result = os_service._get_opensearch_stats(CASE_ID)

        # 3 candidate queries, no extra for discovery
        assert mock_count.call_count == 3
        assert result["doc_count"] == 0

    def test_discovery_index_also_returns_zero(self, os_service):
        """When discovered index also returns 0, it's added to attempted_indices."""
        with patch.object(os_service, "_query_opensearch_count", return_value=0), \
             patch.object(os_service, "_discover_opensearch_index", return_value="found_idx"):
            result = os_service._get_opensearch_stats(CASE_ID)

        assert result["doc_count"] == 0
        assert "found_idx" in result["attempted_indices"]
        assert len(result["attempted_indices"]) == 4  # 3 candidates + discovered

    def test_index_candidates_order(self, os_service):
        """Verifies the exact order of index candidates tried."""
        with patch.object(os_service, "_query_opensearch_count") as mock_count, \
             patch.object(os_service, "_discover_opensearch_index", return_value=None):
            mock_count.return_value = 0
            os_service._get_opensearch_stats(CASE_ID)

        calls = [c.args[0] for c in mock_count.call_args_list]
        assert calls == [
            f"case_{CASE_ID.replace('-', '_')}",
            f"case-{CASE_ID}",
            CASE_ID,
        ]


class TestQueryOpensearchCount:
    """Tests for the _query_opensearch_count helper."""

    def test_returns_count_on_success(self, os_service):
        """Returns the count from a successful _count response."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"count": 123}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(os_service, "_build_sigv4_request"), \
             patch("urllib.request.urlopen", return_value=mock_response):
            result = os_service._query_opensearch_count("test_index")

        assert result == 123

    def test_returns_zero_on_exception(self, os_service):
        """Returns 0 when the request raises an exception."""
        with patch.object(os_service, "_build_sigv4_request"), \
             patch("urllib.request.urlopen", side_effect=Exception("404 Not Found")):
            result = os_service._query_opensearch_count("nonexistent_index")

        assert result == 0

    def test_returns_zero_when_count_missing(self, os_service):
        """Returns 0 when response body has no 'count' key."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(os_service, "_build_sigv4_request"), \
             patch("urllib.request.urlopen", return_value=mock_response):
            result = os_service._query_opensearch_count("test_index")

        assert result == 0


class TestDiscoverOpensearchIndex:
    """Tests for the _discover_opensearch_index helper."""

    def test_finds_matching_index(self, os_service):
        """Discovers an index whose name contains the case id."""
        cat_response = [
            {"index": "unrelated_index"},
            {"index": f"data_case_{CASE_ID.replace('-', '_')}_v2"},
            {"index": "another_index"},
        ]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(cat_response).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(os_service, "_build_sigv4_request"), \
             patch("urllib.request.urlopen", return_value=mock_response):
            result = os_service._discover_opensearch_index(CASE_ID)

        assert result == f"data_case_{CASE_ID.replace('-', '_')}_v2"

    def test_returns_none_when_no_match(self, os_service):
        """Returns None when no index contains the case id."""
        cat_response = [
            {"index": "unrelated_index"},
            {"index": "another_index"},
        ]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(cat_response).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(os_service, "_build_sigv4_request"), \
             patch("urllib.request.urlopen", return_value=mock_response):
            result = os_service._discover_opensearch_index(CASE_ID)

        assert result is None

    def test_returns_none_on_exception(self, os_service):
        """Returns None when _cat/indices request fails."""
        with patch.object(os_service, "_build_sigv4_request"), \
             patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            result = os_service._discover_opensearch_index(CASE_ID)

        assert result is None

    def test_normalizes_hyphens_and_underscores(self, os_service):
        """Matching is case-insensitive and ignores hyphens/underscores."""
        cat_response = [
            {"index": "CASE_ABC_123_vectors"},
        ]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(cat_response).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(os_service, "_build_sigv4_request"), \
             patch("urllib.request.urlopen", return_value=mock_response):
            # CASE_ID is "abc-123", normalized to "abc123"
            # Index "CASE_ABC_123_vectors" normalized to "caseabc123vectors"
            result = os_service._discover_opensearch_index(CASE_ID)

        assert result == "CASE_ABC_123_vectors"

    def test_returns_first_match(self, os_service):
        """Returns the first matching index when multiple match."""
        cat_response = [
            {"index": f"old_{CASE_ID.replace('-', '_')}"},
            {"index": f"new_{CASE_ID.replace('-', '_')}"},
        ]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(cat_response).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(os_service, "_build_sigv4_request"), \
             patch("urllib.request.urlopen", return_value=mock_response):
            result = os_service._discover_opensearch_index(CASE_ID)

        assert result == f"old_{CASE_ID.replace('-', '_')}"


# ---------------------------------------------------------------------------
# get_status throughput_per_minute tests
# ---------------------------------------------------------------------------


class TestThroughputPerMinute:
    """Tests that get_status includes throughput_per_minute in the summary."""

    def test_throughput_per_minute_computed_correctly(self, service, s3_client):
        """throughput_per_minute = round(throughput_per_hour / 60, 1)."""
        s3_client.list_objects_v2.return_value = {"KeyCount": 0, "IsTruncated": False}

        result = service.get_status(CASE_ID)

        throughput_per_hour = result["summary"]["throughput_per_hour"]
        expected = round(throughput_per_hour / 60, 1)
        assert result["summary"]["throughput_per_minute"] == expected

    def test_throughput_per_minute_zero_when_no_throughput(self, service, s3_client):
        """When throughput_per_hour is 0, throughput_per_minute is 0."""
        s3_client.list_objects_v2.return_value = {"KeyCount": 0, "IsTruncated": False}

        result = service.get_status(CASE_ID)

        assert result["summary"]["throughput_per_hour"] == 0
        assert result["summary"]["throughput_per_minute"] == 0.0

    def test_throughput_per_minute_with_nonzero_throughput(self, service, s3_client):
        """Verifies computation with a known throughput value (90 docs/hr = 1.5 docs/min)."""
        s3_client.list_objects_v2.return_value = {"KeyCount": 10, "IsTruncated": False}

        # Patch _get_aurora_stats to return a known throughput
        with patch.object(service, "_get_aurora_stats") as mock_aurora:
            mock_aurora.return_value = {
                "document_count": 10,
                "failed_count": 0,
                "status_breakdown": {},
                "throughput_per_hour": 90,
                "last_activity": None,
            }
            result = service.get_status(CASE_ID)

        assert result["summary"]["throughput_per_hour"] == 90
        assert result["summary"]["throughput_per_minute"] == 1.5
