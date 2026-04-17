"""Unit tests for scripts/classify_images.py — classification logic and helpers."""

import io
import json
import os
import sys
import tempfile

import numpy as np
import pytest
from PIL import Image

# Ensure scripts/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.classify_images import (
    classify_image_metrics,
    compute_metrics,
    build_summary,
)


# ---------------------------------------------------------------------------
# classify_image_metrics — pure function tests
# ---------------------------------------------------------------------------

class TestClassifyImageMetrics:
    """Test the priority-based classification rules."""

    def test_blank_low_entropy(self):
        assert classify_image_metrics(entropy=1.5, color_variance=10, edge_density=0.1) == "blank"

    def test_blank_zero_entropy(self):
        assert classify_image_metrics(entropy=0.0, color_variance=0, edge_density=0.0) == "blank"

    def test_blank_wins_over_redacted(self):
        """Blank priority beats redacted_text even when redacted conditions also match."""
        assert classify_image_metrics(entropy=1.0, color_variance=10, edge_density=0.1) == "blank"

    def test_blank_wins_over_document(self):
        """Blank priority beats document_page even when document conditions also match."""
        assert classify_image_metrics(entropy=1.0, color_variance=20, edge_density=0.5) == "blank"

    def test_redacted_text(self):
        assert classify_image_metrics(entropy=3.0, color_variance=15, edge_density=0.1) == "redacted_text"

    def test_redacted_text_boundary_entropy_at_2(self):
        """entropy == 2.0 is NOT blank (< 2.0 required), so can be redacted_text."""
        assert classify_image_metrics(entropy=2.0, color_variance=10, edge_density=0.1) == "redacted_text"

    def test_redacted_text_high_cv(self):
        """New: redacted_text no longer requires low CV — entropy < 4.0 is enough."""
        assert classify_image_metrics(entropy=3.5, color_variance=60, edge_density=0.1) == "redacted_text"

    def test_not_redacted_when_entropy_at_4(self):
        """entropy == 4.0 is NOT < 4.0, so redacted_text rule doesn't fire."""
        result = classify_image_metrics(entropy=4.0, color_variance=10, edge_density=0.1)
        assert result != "redacted_text"

    def test_document_page_low_entropy_low_cv(self):
        """entropy < 5.5 AND color_variance < 50 → document_page."""
        assert classify_image_metrics(entropy=4.5, color_variance=40, edge_density=0.1) == "document_page"

    def test_document_page_low_cv_moderate_edge(self):
        """color_variance < 35 AND edge_density > 0.15 → document_page."""
        assert classify_image_metrics(entropy=6.0, color_variance=30, edge_density=0.2) == "document_page"

    def test_not_document_when_high_entropy_high_cv(self):
        """High entropy + high CV → photograph, not document."""
        result = classify_image_metrics(entropy=7.0, color_variance=60, edge_density=0.1)
        assert result == "photograph"

    def test_photograph_default(self):
        assert classify_image_metrics(entropy=6.0, color_variance=50, edge_density=0.1) == "photograph"

    def test_photograph_high_entropy_high_variance(self):
        assert classify_image_metrics(entropy=7.5, color_variance=80, edge_density=0.05) == "photograph"

    def test_return_type_is_string(self):
        result = classify_image_metrics(entropy=5.0, color_variance=40, edge_density=0.2)
        assert isinstance(result, str)

    def test_all_valid_categories(self):
        """Every possible return value is one of the four categories."""
        valid = {"blank", "redacted_text", "document_page", "photograph"}
        test_cases = [
            (0.5, 5, 0.1),       # blank
            (3.0, 10, 0.1),      # redacted_text
            (4.5, 40, 0.1),      # document_page
            (7.0, 60, 0.1),      # photograph
        ]
        for e, cv, ed in test_cases:
            assert classify_image_metrics(e, cv, ed) in valid

    def test_real_data_low_entropy_photo_now_redacted(self):
        """Images like ent=2.4, cv=25 that were misclassified as photo should now be redacted."""
        assert classify_image_metrics(entropy=2.4, color_variance=25, edge_density=0.11) == "redacted_text"

    def test_real_data_mid_entropy_low_cv_now_document(self):
        """Images like ent=5.0, cv=20 should be document_page."""
        assert classify_image_metrics(entropy=5.0, color_variance=20, edge_density=0.03) == "document_page"

    def test_real_data_high_entropy_high_cv_stays_photo(self):
        """Images like ent=7.3, cv=85 should remain photograph."""
        assert classify_image_metrics(entropy=7.3, color_variance=85, edge_density=0.14) == "photograph"


# ---------------------------------------------------------------------------
# compute_metrics — integration with Pillow
# ---------------------------------------------------------------------------

def _make_image_bytes(width=100, height=100, color=128, mode="L") -> bytes:
    """Create a simple test image as bytes."""
    img = Image.new(mode, (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestComputeMetrics:
    """Test metric computation on synthetic images."""

    def test_returns_all_keys(self):
        img_bytes = _make_image_bytes()
        metrics = compute_metrics(img_bytes)
        assert "entropy" in metrics
        assert "color_variance" in metrics
        assert "edge_density" in metrics

    def test_uniform_image_low_entropy(self):
        """A solid-color image should have very low entropy."""
        img_bytes = _make_image_bytes(color=128)
        metrics = compute_metrics(img_bytes)
        assert metrics["entropy"] < 1.0

    def test_uniform_image_zero_variance(self):
        """A solid-color image should have zero color variance."""
        img_bytes = _make_image_bytes(color=128)
        metrics = compute_metrics(img_bytes)
        assert metrics["color_variance"] == 0.0

    def test_edge_density_in_range(self):
        img_bytes = _make_image_bytes()
        metrics = compute_metrics(img_bytes)
        assert 0.0 <= metrics["edge_density"] <= 1.0

    def test_rgb_image_converted_to_grayscale(self):
        """RGB images should be handled correctly."""
        img_bytes = _make_image_bytes(mode="RGB", color=(100, 150, 200))
        metrics = compute_metrics(img_bytes)
        assert "entropy" in metrics

    def test_noisy_image_higher_entropy(self):
        """A noisy image should have higher entropy than a uniform one."""
        rng = np.random.RandomState(42)
        arr = rng.randint(0, 256, (100, 100), dtype=np.uint8)
        img = Image.fromarray(arr, mode="L")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        metrics = compute_metrics(buf.getvalue())
        assert metrics["entropy"] > 5.0


# ---------------------------------------------------------------------------
# build_summary
# ---------------------------------------------------------------------------

class TestBuildSummary:
    """Test summary count aggregation."""

    def test_empty_list(self):
        summary = build_summary([])
        assert summary["total"] == 0
        assert summary["photograph"] == 0

    def test_counts_match(self):
        classifications = [
            {"classification": "photograph"},
            {"classification": "photograph"},
            {"classification": "document_page"},
            {"classification": "blank"},
        ]
        summary = build_summary(classifications)
        assert summary["total"] == 4
        assert summary["photograph"] == 2
        assert summary["document_page"] == 1
        assert summary["blank"] == 1
        assert summary["redacted_text"] == 0

    def test_sum_equals_total(self):
        classifications = [
            {"classification": "photograph"},
            {"classification": "redacted_text"},
            {"classification": "redacted_text"},
            {"classification": "document_page"},
            {"classification": "blank"},
        ]
        summary = build_summary(classifications)
        cat_sum = summary["photograph"] + summary["document_page"] + summary["redacted_text"] + summary["blank"]
        assert cat_sum == summary["total"]

    def test_errors_default_zero(self):
        summary = build_summary([{"classification": "photograph"}])
        assert summary["errors"] == 0
