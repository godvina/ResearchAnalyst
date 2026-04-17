"""Quarantine management for persistently failing documents.

Tracks documents that fail extraction or ingestion after all retry attempts,
persisting them to scripts/quarantine.json so they are excluded from future
batch discovery.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_DEFAULT_QUARANTINE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "quarantine.json"
)


@dataclass
class QuarantineEntry:
    """A single quarantined document."""

    s3_key: str
    reason: str
    failed_at: str
    retry_count: int
    batch_number: int


class QuarantineManager:
    """Load, save, and query the quarantine file."""

    def __init__(self, quarantine_path: str = _DEFAULT_QUARANTINE_PATH):
        self.quarantine_path = quarantine_path
        self._entries: list[QuarantineEntry] = []

    def load(self) -> list[QuarantineEntry]:
        """Load quarantine entries from the JSON file on disk."""
        if not os.path.exists(self.quarantine_path):
            self._entries = []
            return self._entries

        try:
            with open(self.quarantine_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._entries = [
                QuarantineEntry(**entry)
                for entry in data.get("quarantined_keys", [])
            ]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse quarantine file: %s", exc)
            self._entries = []

        return self._entries

    def save(self) -> None:
        """Persist current entries to the JSON file."""
        data = {"quarantined_keys": [asdict(e) for e in self._entries]}
        os.makedirs(os.path.dirname(self.quarantine_path) or ".", exist_ok=True)
        with open(self.quarantine_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    def add(self, s3_key: str, reason: str, retry_count: int, batch_number: int) -> None:
        """Add a new quarantine entry with the current UTC timestamp."""
        entry = QuarantineEntry(
            s3_key=s3_key,
            reason=reason,
            failed_at=datetime.now(timezone.utc).isoformat(),
            retry_count=retry_count,
            batch_number=batch_number,
        )
        self._entries.append(entry)

    def get_quarantined_keys(self) -> set[str]:
        """Return the set of all quarantined S3 keys."""
        return {e.s3_key for e in self._entries}

    def is_quarantined(self, s3_key: str) -> bool:
        """Check whether a given S3 key is quarantined."""
        return any(e.s3_key == s3_key for e in self._entries)


def check_failure_threshold(failed_count: int, total_count: int, threshold: float) -> bool:
    """Return True if the failure ratio exceeds the threshold (signals pause).

    If total_count is zero, returns False (no documents means no failure).
    """
    if total_count <= 0:
        return False
    return (failed_count / total_count) > threshold
