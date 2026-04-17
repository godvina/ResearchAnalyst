"""Canonical Entity Index — persistent O(n) entity dedup lookup.

Maintains a JSON-backed index on S3 mapping (normalized_name, entity_type)
to canonical entries. Enables O(n) entity resolution at batch boundaries
instead of O(n²) pairwise comparison.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from batch_loader.config import BatchConfig

logger = logging.getLogger(__name__)


@dataclass
class CanonicalEntry:
    """A single canonical entity with its aliases."""

    canonical_name: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)
    occurrence_count: int = 0


class CanonicalEntityIndex:
    """Persistent lookup table for O(n) entity dedup.

    The index is stored on S3 at canonical-entity-index/{case_id}.json
    and keyed internally by "{entity_type}::{normalized_name}".
    An alias_map provides O(1) lookup for aliases as well.
    """

    def __init__(self, config: BatchConfig, s3_client):
        self._config = config
        self._s3 = s3_client
        self._bucket = config.data_lake_bucket
        self._key = f"canonical-entity-index/{config.case_id}.json"
        self._entries: dict[str, CanonicalEntry] = {}
        self._alias_map: dict[tuple[str, str], CanonicalEntry] = {}
        self._batches_processed: int = 0

    @staticmethod
    def _normalize(name: str) -> str:
        """Normalize a name for index lookup: lowercase + strip."""
        return name.strip().lower()

    @staticmethod
    def _make_key(normalized_name: str, entity_type: str) -> str:
        """Build the dict key: '{entity_type}::{normalized_name}'."""
        return f"{entity_type}::{normalized_name}"

    def load(self) -> dict[tuple[str, str], CanonicalEntry]:
        """Load index from S3 or initialize empty. Returns entries keyed by (norm_name, type)."""
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=self._key)
            data = json.loads(resp["Body"].read().decode("utf-8"))
            self._batches_processed = data.get("stats", {}).get("batches_processed", 0)

            for composite_key, entry_data in data.get("entries", {}).items():
                entry = CanonicalEntry(
                    canonical_name=entry_data["canonical_name"],
                    entity_type=entry_data["entity_type"],
                    aliases=entry_data.get("aliases", []),
                    occurrence_count=entry_data.get("occurrence_count", 0),
                )
                self._entries[composite_key] = entry

                # Build alias_map for O(1) alias lookups
                norm_canonical = self._normalize(entry.canonical_name)
                self._alias_map[(norm_canonical, entry.entity_type)] = entry
                for alias in entry.aliases:
                    norm_alias = self._normalize(alias)
                    self._alias_map[(norm_alias, entry.entity_type)] = entry

            logger.info(
                "Loaded canonical entity index: %d entries, %d alias mappings",
                len(self._entries),
                len(self._alias_map),
            )
        except self._s3.exceptions.NoSuchKey:
            logger.info("No existing canonical entity index — starting fresh")
        except Exception as exc:
            logger.warning("Failed to load canonical entity index: %s", str(exc)[:200])

        # Return a dict keyed by (normalized_name, entity_type)
        result: dict[tuple[str, str], CanonicalEntry] = {}
        for entry in self._entries.values():
            norm = self._normalize(entry.canonical_name)
            result[(norm, entry.entity_type)] = entry
        return result

    def lookup(self, normalized_name: str, entity_type: str) -> CanonicalEntry | None:
        """O(1) lookup by (normalized_name, entity_type).

        Checks canonical name keys first, then alias_map.
        """
        norm = self._normalize(normalized_name)

        # Check alias_map (covers both canonical names and aliases)
        entry = self._alias_map.get((norm, entity_type))
        if entry is not None:
            return entry

        # Fallback: check entries dict directly
        composite_key = self._make_key(norm, entity_type)
        return self._entries.get(composite_key)

    def register_merge(self, canonical: str, aliases: list[str], entity_type: str):
        """Add a new merge cluster to the index.

        Maps the canonical name and all aliases to the same CanonicalEntry.
        If the canonical already exists, merges new aliases into it.
        """
        norm_canonical = self._normalize(canonical)
        composite_key = self._make_key(norm_canonical, entity_type)

        existing = self._entries.get(composite_key)
        if existing is not None:
            # Merge new aliases into existing entry
            existing_alias_set = set(existing.aliases)
            for alias in aliases:
                if alias not in existing_alias_set and self._normalize(alias) != norm_canonical:
                    existing.aliases.append(alias)
                    existing_alias_set.add(alias)
            entry = existing
        else:
            # Create new entry
            filtered_aliases = [
                a for a in aliases if self._normalize(a) != norm_canonical
            ]
            entry = CanonicalEntry(
                canonical_name=canonical,
                entity_type=entity_type,
                aliases=filtered_aliases,
                occurrence_count=0,
            )
            self._entries[composite_key] = entry

        # Update alias_map for canonical name and all aliases
        self._alias_map[(norm_canonical, entity_type)] = entry
        for alias in entry.aliases:
            norm_alias = self._normalize(alias)
            self._alias_map[(norm_alias, entity_type)] = entry

    def save(self):
        """Persist index back to S3."""
        total_aliases = sum(len(e.aliases) for e in self._entries.values())
        self._batches_processed += 1

        data = {
            "version": 1,
            "case_id": self._config.case_id,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "entries": {},
            "stats": {
                "total_canonical_entities": len(self._entries),
                "total_aliases": total_aliases,
                "batches_processed": self._batches_processed,
            },
        }

        for composite_key, entry in self._entries.items():
            data["entries"][composite_key] = {
                "canonical_name": entry.canonical_name,
                "entity_type": entry.entity_type,
                "aliases": entry.aliases,
                "occurrence_count": entry.occurrence_count,
            }

        body = json.dumps(data, indent=2)
        self._s3.put_object(
            Bucket=self._bucket,
            Key=self._key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        logger.info(
            "Saved canonical entity index: %d entries, %d aliases",
            len(self._entries),
            total_aliases,
        )
