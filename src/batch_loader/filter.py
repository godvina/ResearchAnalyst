"""Blank document filtering for the incremental batch loader.

Filters out documents with insufficient non-whitespace text content
before they enter the ingestion pipeline, saving pipeline resources and costs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from batch_loader.config import BatchConfig


class ExtractionResultLike(Protocol):
    """Minimal protocol for extraction results consumed by the filter.

    The full ExtractionResult dataclass is defined in extractor.py (task 6.1).
    This protocol allows the filter to work with any object that has the
    required attributes.
    """

    s3_key: str
    text: str
    char_count: int


@dataclass
class FilterResult:
    """Result of blank-filtering a single document."""

    s3_key: str
    is_blank: bool
    char_count: int


class BlankFilter:
    """Filters out blank documents below a non-whitespace character threshold.

    A document is considered blank when its non-whitespace character count
    is less than the configured blank_threshold (default 10).
    """

    _NON_WHITESPACE = re.compile(r"\S")

    def __init__(self, config: BatchConfig) -> None:
        self.blank_threshold: int = config.blank_threshold

    def filter(self, extraction: ExtractionResultLike) -> FilterResult:
        """Determine if an extracted document is blank.

        Counts non-whitespace characters in the extracted text and marks
        the document as blank when that count falls below blank_threshold.
        """
        non_ws_count = len(self._NON_WHITESPACE.findall(extraction.text))
        return FilterResult(
            s3_key=extraction.s3_key,
            is_blank=non_ws_count < self.blank_threshold,
            char_count=non_ws_count,
        )

    def compute_blank_ratio(self, results: list[FilterResult]) -> float:
        """Return blank_count / total_count for a list of filter results.

        Returns 0.0 when the list is empty to avoid division by zero.
        """
        if not results:
            return 0.0
        blank_count = sum(1 for r in results if r.is_blank)
        return blank_count / len(results)
