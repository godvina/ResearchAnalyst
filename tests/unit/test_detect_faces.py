"""Unit tests for scripts/detect_faces.py — photograph selection, metadata generation, and helpers."""

import os
import sys

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.detect_faces import (
    select_photographs,
    extract_document_id,
    build_crop_s3_key,
    build_face_detection_entry,
    build_crop_metadata_entries,
)


# ---------------------------------------------------------------------------
# select_photographs — pure function tests
# ---------------------------------------------------------------------------

class TestSelectPhotographs:
    """Test filtering classification entries to photographs only."""

    def test_returns_only_photographs(self):
        classifications = [
            {"s3_key": "a.jpg", "classification": "photograph"},
            {"s3_key": "b.jpg", "classification": "document_page"},
            {"s3_key": "c.jpg", "classification": "photograph"},
            {"s3_key": "d.jpg", "classification": "blank"},
            {"s3_key": "e.jpg", "classification": "redacted_text"},
        ]
        result = select_photographs(classifications)
        assert len(result) == 2
        assert all(e["classification"] == "photograph" for e in result)

    def test_empty_input(self):
        assert select_photographs([]) == []

    def test_no_photographs(self):
        classifications = [
            {"s3_key": "a.jpg", "classification": "document_page"},
            {"s3_key": "b.jpg", "classification": "blank"},
        ]
        assert select_photographs(classifications) == []

    def test_all_photographs(self):
        classifications = [
            {"s3_key": "a.jpg", "classification": "photograph"},
            {"s3_key": "b.jpg", "classification": "photograph"},
        ]
        result = select_photographs(classifications)
        assert len(result) == 2

    def test_missing_classification_key(self):
        """Entries without a classification key should be excluded."""
        classifications = [
            {"s3_key": "a.jpg"},
            {"s3_key": "b.jpg", "classification": "photograph"},
        ]
        result = select_photographs(classifications)
        assert len(result) == 1

    def test_preserves_entry_data(self):
        """Selected entries should retain all their original fields."""
        entry = {"s3_key": "photo.jpg", "classification": "photograph", "metrics": {"entropy": 6.0}}
        result = select_photographs([entry])
        assert result[0] == entry


# ---------------------------------------------------------------------------
# extract_document_id
# ---------------------------------------------------------------------------

class TestExtractDocumentId:
    """Test document ID extraction from S3 keys."""

    def test_efta_pattern(self):
        key = "cases/abc/extracted-images/EFTA01234567_page_1.jpg"
        assert extract_document_id(key) == "EFTA01234567"

    def test_efta_pattern_no_suffix(self):
        key = "cases/abc/extracted-images/EFTA01619633.jpg"
        assert extract_document_id(key) == "EFTA01619633"

    def test_fallback_to_stem(self):
        key = "cases/abc/extracted-images/some_random_file.jpg"
        assert extract_document_id(key) == "some_random_file"

    def test_no_extension(self):
        key = "cases/abc/extracted-images/EFTA99999999"
        assert extract_document_id(key) == "EFTA99999999"

    def test_nested_path(self):
        key = "deep/nested/path/EFTA00000001_crop.png"
        assert extract_document_id(key) == "EFTA00000001"


# ---------------------------------------------------------------------------
# build_crop_s3_key
# ---------------------------------------------------------------------------

class TestBuildCropS3Key:
    """Test crop S3 key generation."""

    def test_returns_correct_prefix(self):
        key = build_crop_s3_key("case123", "source.jpg", 0)
        assert key.startswith("cases/case123/face-crops/unidentified/")

    def test_returns_jpg_extension(self):
        key = build_crop_s3_key("case123", "source.jpg", 0)
        assert key.endswith(".jpg")

    def test_different_face_indices_produce_different_keys(self):
        key0 = build_crop_s3_key("case123", "source.jpg", 0)
        key1 = build_crop_s3_key("case123", "source.jpg", 1)
        assert key0 != key1

    def test_different_sources_produce_different_keys(self):
        key_a = build_crop_s3_key("case123", "a.jpg", 0)
        key_b = build_crop_s3_key("case123", "b.jpg", 0)
        assert key_a != key_b


# ---------------------------------------------------------------------------
# build_face_detection_entry
# ---------------------------------------------------------------------------

class TestBuildFaceDetectionEntry:
    """Test face detection result entry building."""

    def test_basic_entry(self):
        faces_response = [
            {
                "BoundingBox": {"Left": 0.3, "Top": 0.2, "Width": 0.15, "Height": 0.2},
                "Confidence": 99.1,
                "Gender": {"Value": "Male", "Confidence": 95.0},
                "AgeRange": {"Low": 40, "High": 55},
            }
        ]
        result = build_face_detection_entry("photo.jpg", faces_response, threshold=80.0)
        assert result["s3_key"] == "photo.jpg"
        assert len(result["faces"]) == 1
        assert result["faces"][0]["confidence"] == 99.1
        assert result["faces"][0]["bounding_box"]["Left"] == 0.3

    def test_filters_below_threshold(self):
        faces_response = [
            {"BoundingBox": {}, "Confidence": 50.0, "Gender": {}, "AgeRange": {}},
            {"BoundingBox": {}, "Confidence": 90.0, "Gender": {}, "AgeRange": {}},
        ]
        result = build_face_detection_entry("photo.jpg", faces_response, threshold=80.0)
        assert len(result["faces"]) == 1
        assert result["faces"][0]["confidence"] == 90.0

    def test_empty_faces(self):
        result = build_face_detection_entry("photo.jpg", [], threshold=80.0)
        assert result["s3_key"] == "photo.jpg"
        assert result["faces"] == []

    def test_all_below_threshold(self):
        faces_response = [
            {"BoundingBox": {}, "Confidence": 30.0, "Gender": {}, "AgeRange": {}},
        ]
        result = build_face_detection_entry("photo.jpg", faces_response, threshold=80.0)
        assert result["faces"] == []


# ---------------------------------------------------------------------------
# build_crop_metadata_entries
# ---------------------------------------------------------------------------

class TestBuildCropMetadataEntries:
    """Test crop metadata generation compatible with crop_faces.py."""

    def _sample_face(self, confidence=99.0):
        return {
            "BoundingBox": {"Left": 0.3, "Top": 0.2, "Width": 0.15, "Height": 0.2},
            "Confidence": confidence,
            "Gender": {"Value": "Male", "Confidence": 95.0},
            "AgeRange": {"Low": 40, "High": 55},
        }

    def test_basic_metadata(self):
        s3_key = "cases/abc/extracted-images/EFTA01234567_page_1.jpg"
        entries = build_crop_metadata_entries("abc", s3_key, [self._sample_face()], 80.0)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["source_s3_key"] == s3_key
        assert entry["crop_s3_key"].startswith("cases/abc/face-crops/unidentified/")
        assert entry["crop_s3_key"].endswith(".jpg")
        assert entry["bounding_box"]["Left"] == 0.3
        assert entry["bounding_box"]["Top"] == 0.2
        assert entry["bounding_box"]["Width"] == 0.15
        assert entry["bounding_box"]["Height"] == 0.2
        assert entry["confidence"] == 99.0
        assert entry["gender"] == "Male"
        assert entry["age_range"] == "40-55"
        assert entry["source_document_id"] == "EFTA01234567"

    def test_required_fields_present(self):
        """All fields required by crop_faces.py must be present."""
        s3_key = "cases/abc/extracted-images/EFTA01234567.jpg"
        entries = build_crop_metadata_entries("abc", s3_key, [self._sample_face()], 80.0)
        required_fields = {
            "source_s3_key", "crop_s3_key", "bounding_box",
            "confidence", "gender", "age_range", "source_document_id",
        }
        assert required_fields.issubset(set(entries[0].keys()))

    def test_bounding_box_keys(self):
        """Bounding box must have Left, Top, Width, Height."""
        s3_key = "cases/abc/extracted-images/EFTA01234567.jpg"
        entries = build_crop_metadata_entries("abc", s3_key, [self._sample_face()], 80.0)
        bbox = entries[0]["bounding_box"]
        assert set(bbox.keys()) == {"Left", "Top", "Width", "Height"}

    def test_filters_below_threshold(self):
        faces = [self._sample_face(confidence=50.0), self._sample_face(confidence=95.0)]
        entries = build_crop_metadata_entries("abc", "img.jpg", faces, 80.0)
        assert len(entries) == 1
        assert entries[0]["confidence"] == 95.0

    def test_multiple_faces(self):
        faces = [self._sample_face(99.0), self._sample_face(92.0)]
        entries = build_crop_metadata_entries("abc", "img.jpg", faces, 80.0)
        assert len(entries) == 2
        # Each should have a unique crop_s3_key
        keys = [e["crop_s3_key"] for e in entries]
        assert len(set(keys)) == 2

    def test_missing_gender_defaults_to_unknown(self):
        face = {
            "BoundingBox": {"Left": 0.1, "Top": 0.1, "Width": 0.1, "Height": 0.1},
            "Confidence": 95.0,
            "AgeRange": {"Low": 20, "High": 30},
        }
        entries = build_crop_metadata_entries("abc", "img.jpg", [face], 80.0)
        assert entries[0]["gender"] == "Unknown"

    def test_missing_age_range_defaults(self):
        face = {
            "BoundingBox": {"Left": 0.1, "Top": 0.1, "Width": 0.1, "Height": 0.1},
            "Confidence": 95.0,
            "Gender": {"Value": "Female", "Confidence": 90.0},
        }
        entries = build_crop_metadata_entries("abc", "img.jpg", [face], 80.0)
        assert entries[0]["age_range"] == "0-0"

    def test_empty_faces_list(self):
        entries = build_crop_metadata_entries("abc", "img.jpg", [], 80.0)
        assert entries == []
