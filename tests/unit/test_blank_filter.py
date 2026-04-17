"""Unit tests for scripts/batch_loader/filter.py — BlankFilter and FilterResult."""

from dataclasses import dataclass

import pytest

from scripts.batch_loader.config import BatchConfig
from scripts.batch_loader.filter import BlankFilter, FilterResult


@dataclass
class FakeExtraction:
    """Minimal stand-in for ExtractionResult (not yet created in extractor.py)."""

    s3_key: str
    text: str
    char_count: int


class TestFilterResult:
    """Verify FilterResult dataclass fields."""

    def test_fields(self):
        r = FilterResult(s3_key="pdfs/a.pdf", is_blank=True, char_count=3)
        assert r.s3_key == "pdfs/a.pdf"
        assert r.is_blank is True
        assert r.char_count == 3


class TestBlankFilterInit:
    """Verify BlankFilter stores blank_threshold from config."""

    def test_default_threshold(self):
        bf = BlankFilter(BatchConfig())
        assert bf.blank_threshold == 10

    def test_custom_threshold(self):
        bf = BlankFilter(BatchConfig(blank_threshold=25))
        assert bf.blank_threshold == 25


class TestBlankFilterFilter:
    """Verify filter marks documents blank based on non-whitespace char count."""

    def _make_filter(self, threshold: int = 10) -> BlankFilter:
        return BlankFilter(BatchConfig(blank_threshold=threshold))

    def test_empty_text_is_blank(self):
        bf = self._make_filter()
        result = bf.filter(FakeExtraction(s3_key="k", text="", char_count=0))
        assert result.is_blank is True
        assert result.char_count == 0

    def test_whitespace_only_is_blank(self):
        bf = self._make_filter()
        result = bf.filter(FakeExtraction(s3_key="k", text="   \n\t  ", char_count=0))
        assert result.is_blank is True
        assert result.char_count == 0

    def test_below_threshold_is_blank(self):
        bf = self._make_filter(threshold=10)
        result = bf.filter(FakeExtraction(s3_key="k", text="abc def", char_count=6))
        assert result.is_blank is True
        assert result.char_count == 6  # "abcdef" = 6 non-ws chars

    def test_at_threshold_is_not_blank(self):
        bf = self._make_filter(threshold=5)
        result = bf.filter(FakeExtraction(s3_key="k", text="ab cd e", char_count=5))
        assert result.is_blank is False
        assert result.char_count == 5

    def test_above_threshold_is_not_blank(self):
        bf = self._make_filter(threshold=5)
        result = bf.filter(FakeExtraction(s3_key="k", text="hello world!", char_count=11))
        assert result.is_blank is False
        assert result.char_count == 11

    def test_s3_key_preserved(self):
        bf = self._make_filter()
        result = bf.filter(FakeExtraction(s3_key="pdfs/DOC_001.pdf", text="x" * 20, char_count=20))
        assert result.s3_key == "pdfs/DOC_001.pdf"

    def test_mixed_whitespace_counted_correctly(self):
        bf = self._make_filter(threshold=4)
        # "a \t b \n c" has 3 non-ws chars: a, b, c
        result = bf.filter(FakeExtraction(s3_key="k", text="a \t b \n c", char_count=3))
        assert result.is_blank is True
        assert result.char_count == 3

    def test_threshold_one(self):
        bf = self._make_filter(threshold=1)
        blank = bf.filter(FakeExtraction(s3_key="k", text="   ", char_count=0))
        assert blank.is_blank is True
        not_blank = bf.filter(FakeExtraction(s3_key="k", text=" x ", char_count=1))
        assert not_blank.is_blank is False
        assert not_blank.char_count == 1


class TestComputeBlankRatio:
    """Verify compute_blank_ratio returns blank_count / total_count."""

    def _make_filter(self) -> BlankFilter:
        return BlankFilter(BatchConfig())

    def test_empty_list_returns_zero(self):
        bf = self._make_filter()
        assert bf.compute_blank_ratio([]) == 0.0

    def test_all_blank(self):
        bf = self._make_filter()
        results = [FilterResult("a", True, 0), FilterResult("b", True, 2)]
        assert bf.compute_blank_ratio(results) == 1.0

    def test_none_blank(self):
        bf = self._make_filter()
        results = [FilterResult("a", False, 100), FilterResult("b", False, 200)]
        assert bf.compute_blank_ratio(results) == 0.0

    def test_half_blank(self):
        bf = self._make_filter()
        results = [
            FilterResult("a", True, 0),
            FilterResult("b", False, 100),
        ]
        assert bf.compute_blank_ratio(results) == 0.5

    def test_ratio_precision(self):
        bf = self._make_filter()
        results = [
            FilterResult("a", True, 0),
            FilterResult("b", True, 1),
            FilterResult("c", False, 50),
        ]
        assert bf.compute_blank_ratio(results) == pytest.approx(2 / 3)

    def test_single_blank(self):
        bf = self._make_filter()
        assert bf.compute_blank_ratio([FilterResult("a", True, 0)]) == 1.0

    def test_single_not_blank(self):
        bf = self._make_filter()
        assert bf.compute_blank_ratio([FilterResult("a", False, 50)]) == 0.0
