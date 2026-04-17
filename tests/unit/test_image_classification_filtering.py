"""Unit tests for image classification loading and filtering in image_evidence_handler.

Tests the helper functions: _parse_classification_param, load_classification_artifact,
build_classification_lookup, compute_classification_counts, filter_images_by_classification,
load_face_match_results, build_entity_match_lookup, merge_entity_matches.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.api.case_files import (
    _parse_classification_param,
    build_classification_lookup,
    build_entity_match_lookup,
    compute_classification_counts,
    filter_images_by_classification,
    load_classification_artifact,
    load_face_match_results,
    merge_entity_matches,
)


# ---------------------------------------------------------------------------
# _parse_classification_param
# ---------------------------------------------------------------------------


class TestParseClassificationParam:
    def test_default_empty_string(self):
        assert _parse_classification_param("") == "photograph"

    def test_default_none_like(self):
        assert _parse_classification_param("") == "photograph"

    def test_valid_photograph(self):
        assert _parse_classification_param("photograph") == "photograph"

    def test_valid_document_page(self):
        assert _parse_classification_param("document_page") == "document_page"

    def test_valid_redacted_text(self):
        assert _parse_classification_param("redacted_text") == "redacted_text"

    def test_valid_blank(self):
        assert _parse_classification_param("blank") == "blank"

    def test_valid_all(self):
        assert _parse_classification_param("all") == "all"

    def test_invalid_value_defaults_to_photograph(self):
        assert _parse_classification_param("invalid_junk") == "photograph"

    def test_case_insensitive(self):
        assert _parse_classification_param("PHOTOGRAPH") == "photograph"
        assert _parse_classification_param("All") == "all"

    def test_whitespace_stripped(self):
        assert _parse_classification_param("  photograph  ") == "photograph"


# ---------------------------------------------------------------------------
# load_classification_artifact
# ---------------------------------------------------------------------------


class TestLoadClassificationArtifact:
    def test_returns_classifications_list(self):
        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = json.dumps({
            "classifications": [
                {"s3_key": "cases/c1/extracted-images/a.jpg", "classification": "photograph"},
            ]
        }).encode()
        s3.get_object.return_value = {"Body": body}

        result = load_classification_artifact(s3, "bucket", "c1")
        assert result is not None
        assert len(result) == 1
        assert result[0]["classification"] == "photograph"
        s3.get_object.assert_called_once_with(
            Bucket="bucket",
            Key="cases/c1/rekognition-artifacts/image_classification.json",
        )

    def test_returns_none_when_missing(self):
        s3 = MagicMock()
        s3.get_object.side_effect = Exception("NoSuchKey")
        assert load_classification_artifact(s3, "bucket", "c1") is None

    def test_returns_none_when_malformed(self):
        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = b"not json"
        s3.get_object.return_value = {"Body": body}
        assert load_classification_artifact(s3, "bucket", "c1") is None

    def test_returns_none_when_classifications_not_list(self):
        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = json.dumps({"classifications": "bad"}).encode()
        s3.get_object.return_value = {"Body": body}
        assert load_classification_artifact(s3, "bucket", "c1") is None


# ---------------------------------------------------------------------------
# build_classification_lookup
# ---------------------------------------------------------------------------


class TestBuildClassificationLookup:
    def test_builds_lookup_dict(self):
        entries = [
            {"s3_key": "cases/c1/extracted-images/a.jpg", "classification": "photograph"},
            {"s3_key": "cases/c1/extracted-images/b.jpg", "classification": "blank"},
        ]
        lookup = build_classification_lookup(entries)
        assert lookup == {
            "cases/c1/extracted-images/a.jpg": "photograph",
            "cases/c1/extracted-images/b.jpg": "blank",
        }

    def test_skips_entries_without_key(self):
        entries = [
            {"s3_key": "", "classification": "photograph"},
            {"classification": "blank"},
            {"s3_key": "k1", "classification": "document_page"},
        ]
        lookup = build_classification_lookup(entries)
        assert lookup == {"k1": "document_page"}

    def test_empty_list(self):
        assert build_classification_lookup([]) == {}


# ---------------------------------------------------------------------------
# compute_classification_counts
# ---------------------------------------------------------------------------


class TestComputeClassificationCounts:
    def test_counts_all_categories(self):
        entries = [
            {"s3_key": "a", "classification": "photograph"},
            {"s3_key": "b", "classification": "photograph"},
            {"s3_key": "c", "classification": "document_page"},
            {"s3_key": "d", "classification": "redacted_text"},
            {"s3_key": "e", "classification": "blank"},
            {"s3_key": "f", "classification": "blank"},
            {"s3_key": "g", "classification": "blank"},
        ]
        counts = compute_classification_counts(entries)
        assert counts == {
            "photograph": 2,
            "document_page": 1,
            "redacted_text": 1,
            "blank": 3,
        }

    def test_empty_list(self):
        counts = compute_classification_counts([])
        assert counts == {"photograph": 0, "document_page": 0, "redacted_text": 0, "blank": 0}

    def test_ignores_unknown_categories(self):
        entries = [
            {"s3_key": "a", "classification": "photograph"},
            {"s3_key": "b", "classification": "unknown_type"},
        ]
        counts = compute_classification_counts(entries)
        assert counts["photograph"] == 1
        assert sum(counts.values()) == 1


# ---------------------------------------------------------------------------
# filter_images_by_classification
# ---------------------------------------------------------------------------


class TestFilterImagesByClassification:
    def _make_images(self):
        return [
            {"s3_key": "a.jpg", "filename": "a.jpg"},
            {"s3_key": "b.jpg", "filename": "b.jpg"},
            {"s3_key": "c.jpg", "filename": "c.jpg"},
            {"s3_key": "d.jpg", "filename": "d.jpg"},
        ]

    def _make_lookup(self):
        return {
            "a.jpg": "photograph",
            "b.jpg": "document_page",
            "c.jpg": "blank",
            "d.jpg": "redacted_text",
        }

    def test_filter_photograph(self):
        images = self._make_images()
        result = filter_images_by_classification(images, self._make_lookup(), "photograph")
        assert len(result) == 1
        assert result[0]["s3_key"] == "a.jpg"
        assert result[0]["classification"] == "photograph"

    def test_filter_all_returns_everything(self):
        images = self._make_images()
        result = filter_images_by_classification(images, self._make_lookup(), "all")
        assert len(result) == 4

    def test_filter_blank(self):
        images = self._make_images()
        result = filter_images_by_classification(images, self._make_lookup(), "blank")
        assert len(result) == 1
        assert result[0]["s3_key"] == "c.jpg"

    def test_filter_document_page(self):
        images = self._make_images()
        result = filter_images_by_classification(images, self._make_lookup(), "document_page")
        assert len(result) == 1
        assert result[0]["s3_key"] == "b.jpg"

    def test_unknown_images_excluded_unless_all(self):
        images = [{"s3_key": "unknown.jpg", "filename": "unknown.jpg"}]
        lookup = {}  # not in lookup
        result = filter_images_by_classification(images, lookup, "photograph")
        assert len(result) == 0
        # But 'all' includes them
        images2 = [{"s3_key": "unknown.jpg", "filename": "unknown.jpg"}]
        result2 = filter_images_by_classification(images2, lookup, "all")
        assert len(result2) == 1
        assert result2[0]["classification"] == "unknown"

    def test_classification_field_added_to_all_images(self):
        images = self._make_images()
        filter_images_by_classification(images, self._make_lookup(), "all")
        for img in images:
            assert "classification" in img


# ---------------------------------------------------------------------------
# load_face_match_results
# ---------------------------------------------------------------------------


class TestLoadFaceMatchResults:
    def test_returns_parsed_data(self):
        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = json.dumps({
            "matches": [
                {"crop": "abc.jpg", "entity": "John_Doe", "similarity": 95.2},
            ],
            "no_match": ["xyz.jpg"],
            "threshold": 80.0,
        }).encode()
        s3.get_object.return_value = {"Body": body}

        result = load_face_match_results(s3, "bucket", "c1")
        assert result is not None
        assert len(result["matches"]) == 1
        assert result["matches"][0]["entity"] == "John_Doe"
        s3.get_object.assert_called_once_with(
            Bucket="bucket",
            Key="cases/c1/rekognition-artifacts/face_match_results.json",
        )

    def test_returns_none_when_missing(self):
        s3 = MagicMock()
        s3.get_object.side_effect = Exception("NoSuchKey")
        assert load_face_match_results(s3, "bucket", "c1") is None

    def test_returns_none_when_malformed(self):
        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = b"not json"
        s3.get_object.return_value = {"Body": body}
        assert load_face_match_results(s3, "bucket", "c1") is None

    def test_returns_none_when_matches_not_list(self):
        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = json.dumps({"matches": "bad"}).encode()
        s3.get_object.return_value = {"Body": body}
        assert load_face_match_results(s3, "bucket", "c1") is None


# ---------------------------------------------------------------------------
# build_entity_match_lookup
# ---------------------------------------------------------------------------


class TestBuildEntityMatchLookup:
    def test_builds_lookup_from_matches(self):
        match_results = {
            "matches": [
                {"crop": "abc.jpg", "entity": "John_Doe", "similarity": 95.2},
                {"crop": "def.jpg", "entity": "Jane_Smith", "similarity": 88.5},
            ],
            "no_match": ["xyz.jpg"],
        }
        lookup = build_entity_match_lookup(match_results)
        assert lookup == {
            "abc.jpg": {"entity_name": "John_Doe", "similarity": 95.2},
            "def.jpg": {"entity_name": "Jane_Smith", "similarity": 88.5},
        }

    def test_returns_empty_for_none(self):
        assert build_entity_match_lookup(None) == {}

    def test_returns_empty_for_no_matches(self):
        assert build_entity_match_lookup({"matches": []}) == {}

    def test_skips_entries_without_crop_or_entity(self):
        match_results = {
            "matches": [
                {"crop": "", "entity": "John_Doe", "similarity": 90.0},
                {"crop": "abc.jpg", "entity": "", "similarity": 90.0},
                {"crop": "good.jpg", "entity": "Valid", "similarity": 85.0},
            ],
        }
        lookup = build_entity_match_lookup(match_results)
        assert lookup == {"good.jpg": {"entity_name": "Valid", "similarity": 85.0}}


# ---------------------------------------------------------------------------
# merge_entity_matches
# ---------------------------------------------------------------------------


class TestMergeEntityMatches:
    def test_merges_matched_entities_into_images(self):
        images = [
            {
                "s3_key": "photo1.jpg",
                "faces": [
                    {"crop_key": "cases/c1/face-crops/unidentified/abc.jpg", "entity_name": "unidentified"},
                    {"crop_key": "cases/c1/face-crops/unidentified/def.jpg", "entity_name": "unidentified"},
                ],
            },
        ]
        match_lookup = {
            "abc.jpg": {"entity_name": "John_Doe", "similarity": 95.2},
        }
        merge_entity_matches(images, match_lookup)
        assert images[0]["matched_entities"] == [
            {"entity_name": "John_Doe", "similarity": 95.2},
        ]

    def test_empty_matched_entities_when_no_matches(self):
        images = [
            {
                "s3_key": "photo1.jpg",
                "faces": [
                    {"crop_key": "cases/c1/face-crops/unidentified/xyz.jpg", "entity_name": "unidentified"},
                ],
            },
        ]
        merge_entity_matches(images, {})
        assert images[0]["matched_entities"] == []

    def test_empty_matched_entities_when_no_faces(self):
        images = [
            {"s3_key": "photo1.jpg", "faces": []},
            {"s3_key": "photo2.jpg"},  # no faces key at all
        ]
        merge_entity_matches(images, {"abc.jpg": {"entity_name": "John", "similarity": 90.0}})
        assert images[0]["matched_entities"] == []
        assert images[1]["matched_entities"] == []

    def test_multiple_matched_entities_per_image(self):
        images = [
            {
                "s3_key": "photo1.jpg",
                "faces": [
                    {"crop_key": "cases/c1/face-crops/unidentified/a.jpg"},
                    {"crop_key": "cases/c1/face-crops/unidentified/b.jpg"},
                ],
            },
        ]
        match_lookup = {
            "a.jpg": {"entity_name": "Alice", "similarity": 92.0},
            "b.jpg": {"entity_name": "Bob", "similarity": 87.5},
        }
        merge_entity_matches(images, match_lookup)
        assert len(images[0]["matched_entities"]) == 2
        names = {e["entity_name"] for e in images[0]["matched_entities"]}
        assert names == {"Alice", "Bob"}

    def test_handles_empty_crop_key(self):
        images = [
            {
                "s3_key": "photo1.jpg",
                "faces": [{"crop_key": "", "entity_name": "unidentified"}],
            },
        ]
        merge_entity_matches(images, {"abc.jpg": {"entity_name": "John", "similarity": 90.0}})
        assert images[0]["matched_entities"] == []
