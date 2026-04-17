"""Evidence Assembler Service — assembles evidence threads for investigation leads.

Retrieves relevant documents with key quotes, builds an entity mention timeline,
and extracts focused relationship edges from Neptune for a selected lead.
"""

import json
import logging
import re
import ssl
import urllib.request
from typing import Any, List

from services.lead_generator_service import (
    EvidenceThread,
    EvidenceDocument,
    EvidenceEntity,
    TimelineEntry,
    RelationshipEdge,
)

logger = logging.getLogger(__name__)

# Regex for extracting date-like strings from document content
_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{4})\b"
)


class EvidenceAssemblerService:
    """Assembles the evidence thread for a selected investigation lead.

    Queries Aurora for documents containing entity mentions, extracts key
    quotes, scores relevance, builds a chronological timeline, and queries
    Neptune for relationship edges between entities.
    """

    def __init__(
        self,
        aurora_cm: Any,
        neptune_endpoint: str = "",
        neptune_port: str = "8182",
    ) -> None:
        self._aurora = aurora_cm
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assemble_evidence(
        self,
        case_id: str,
        lead_id: str,
        entity_names: List[str],
        lead_type: str,
        narrative: str,
    ) -> EvidenceThread:
        """Assemble an evidence thread for the given lead.

        Steps:
        1. Query Aurora for documents containing any of entity_names
        2. Extract key quotes (up to 200 chars) from each document
        3. Score document relevance to the lead narrative
        4. Build chronological timeline of entity mentions
        5. Query Neptune for relationship edges between entity_names
        6. Cap at 20 documents (sorted by relevance desc), 30 entities
        Returns EvidenceThread.
        """
        # 1-3. Query Aurora for documents, extract quotes, score relevance
        documents, entity_map = self._query_aurora_documents(
            case_id, entity_names, narrative,
        )

        # Sort by relevance descending, cap at 20
        documents.sort(key=lambda d: d.relevance_score, reverse=True)
        documents = documents[:20]

        # Build entity list from entity_map, cap at 30
        entities = sorted(
            entity_map.values(),
            key=lambda e: e.mention_count,
            reverse=True,
        )[:30]

        # 4. Build chronological timeline
        timeline = self._build_timeline(case_id, entity_names, documents)

        # 5. Query Neptune for relationship edges
        relationship_edges = self._query_neptune_edges(case_id, entity_names)

        return EvidenceThread(
            documents=documents,
            entities=list(entities),
            timeline=timeline,
            relationship_edges=relationship_edges,
        )

    # ------------------------------------------------------------------
    # Aurora queries
    # ------------------------------------------------------------------

    def _query_aurora_documents(
        self,
        case_id: str,
        entity_names: List[str],
        narrative: str,
    ) -> tuple:
        """Query Aurora for documents containing any of entity_names.

        Returns (list[EvidenceDocument], dict[str, EvidenceEntity]).
        """
        documents: List[EvidenceDocument] = []
        entity_map: dict[str, EvidenceEntity] = {}

        if not entity_names:
            return documents, entity_map

        try:
            with self._aurora.cursor() as cur:
                # Build ILIKE OR conditions for each entity name
                conditions = []
                params: list = [case_id]
                for name in entity_names:
                    conditions.append("content ILIKE %s")
                    params.append(f"%{name}%")

                where_clause = " OR ".join(conditions)
                query = (
                    "SELECT document_id, source_filename, raw_text, indexed_at "
                    "FROM documents WHERE case_file_id = %s "
                    f"AND ({where_clause}) "
                    "ORDER BY indexed_at DESC LIMIT 50"
                )
                cur.execute(query, params)
                rows = cur.fetchall()

                for row in rows:
                    doc_id = row[0]
                    filename = row[1]
                    content = row[2] or ""
                    created_at = row[3]

                    # Extract key quotes — sentences containing entity names
                    key_quotes = self._extract_key_quotes(content, entity_names)

                    # Score relevance: count how many entity_names appear
                    relevance_score = self._score_relevance(content, entity_names)

                    # Build excerpt (first 500 chars)
                    excerpt = content[:500]

                    documents.append(EvidenceDocument(
                        doc_id=str(doc_id),
                        filename=filename or "",
                        excerpt=excerpt,
                        key_quotes=key_quotes,
                        relevance_score=relevance_score,
                    ))

                    # Track entity mentions
                    content_lower = content.lower()
                    for name in entity_names:
                        count = content_lower.count(name.lower())
                        if count > 0:
                            if name in entity_map:
                                entity_map[name].mention_count += count
                            else:
                                entity_map[name] = EvidenceEntity(
                                    name=name,
                                    type="unknown",
                                    mention_count=count,
                                )

                # Try to enrich entity types from entities table
                self._enrich_entity_types(cur, case_id, entity_map)

        except Exception as e:
            logger.error(
                "Aurora document query failed for evidence assembly (case=%s): %s",
                case_id, str(e)[:200],
            )

        return documents, entity_map

    def _enrich_entity_types(
        self, cur: Any, case_id: str, entity_map: dict,
    ) -> None:
        """Try to fill in entity types from the entities table."""
        if not entity_map:
            return
        try:
            names = list(entity_map.keys())
            placeholders = ", ".join(["%s"] * len(names))
            cur.execute(
                f"SELECT canonical_name, entity_type FROM entities "
                f"WHERE case_file_id = %s AND canonical_name IN ({placeholders})",
                [case_id] + names,
            )
            for erow in cur.fetchall():
                name, etype = erow[0], erow[1]
                if name in entity_map and etype:
                    entity_map[name].type = etype
        except Exception:
            pass  # entities table may not exist

    # ------------------------------------------------------------------
    # Quote extraction and relevance scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_key_quotes(
        content: str, entity_names: List[str],
    ) -> List[str]:
        """Extract sentences containing entity names, truncated to 200 chars."""
        if not content:
            return []

        # Split on sentence boundaries (period, question mark, exclamation, newline)
        sentences = re.split(r"[.!?\n]+", content)
        quotes: List[str] = []
        seen: set = set()

        for sentence in sentences:
            stripped = sentence.strip()
            if not stripped or len(stripped) < 10:
                continue
            lower = stripped.lower()
            for name in entity_names:
                if name.lower() in lower and stripped not in seen:
                    # Truncate to 200 chars
                    quote = stripped[:200]
                    quotes.append(quote)
                    seen.add(stripped)
                    break  # one match per sentence is enough

            if len(quotes) >= 10:
                break

        return quotes

    @staticmethod
    def _score_relevance(content: str, entity_names: List[str]) -> float:
        """Score document relevance: fraction of entity_names found in content.

        Returns 0.0–1.0 (count of matching entity names / total entity names).
        """
        if not entity_names or not content:
            return 0.0

        content_lower = content.lower()
        matches = sum(1 for name in entity_names if name.lower() in content_lower)
        return round(matches / len(entity_names), 4)

    # ------------------------------------------------------------------
    # Timeline construction
    # ------------------------------------------------------------------

    def _build_timeline(
        self,
        case_id: str,
        entity_names: List[str],
        documents: List[EvidenceDocument],
    ) -> List[TimelineEntry]:
        """Build chronological timeline of entity mentions.

        Extracts dates from document content or falls back to querying
        created_at from Aurora. Sorted ascending by date.
        """
        entries: List[TimelineEntry] = []

        for doc in documents:
            content = doc.excerpt or ""
            filename = doc.filename or "unknown"

            # Try to extract dates from content
            dates_found = _DATE_RE.findall(content)
            if dates_found:
                # Use the first date found in the content
                date_str = dates_found[0]
            else:
                # Fall back: query created_at from Aurora
                date_str = self._get_document_date(case_id, doc.doc_id)

            if not date_str:
                date_str = "unknown"

            # Build event description from entity mentions in this doc
            mentioned = [
                name for name in entity_names
                if name.lower() in content.lower()
            ]
            if mentioned:
                desc = f"{', '.join(mentioned[:3])} mentioned in {filename}"
            else:
                desc = f"Entity reference in {filename}"

            entries.append(TimelineEntry(
                date=date_str,
                event_description=desc,
                source_doc=filename,
            ))

        # Sort ascending by date string (lexicographic works for ISO dates)
        entries.sort(key=lambda e: e.date)
        return entries

    def _get_document_date(self, case_id: str, doc_id: str) -> str:
        """Query Aurora for a document's created_at date."""
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT created_at FROM documents "
                    "WHERE document_id = %s AND case_file_id = %s",
                    (doc_id, case_id),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])[:10]  # YYYY-MM-DD
        except Exception as e:
            logger.error(
                "Failed to get document date (doc=%s): %s",
                doc_id, str(e)[:200],
            )
        return ""

    # ------------------------------------------------------------------
    # Neptune queries
    # ------------------------------------------------------------------

    def _query_neptune_edges(
        self, case_id: str, entity_names: List[str],
    ) -> List[RelationshipEdge]:
        """Query Neptune for relationship edges between entity_names."""
        edges: List[RelationshipEdge] = []
        if not self._neptune_endpoint or len(entity_names) < 2:
            return edges

        label = f"Entity_{case_id}"
        url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
        ctx = ssl.create_default_context()

        def _gremlin(query: str, timeout: int = 30) -> list:
            data = json.dumps({"gremlin": query}).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            raw = body.get("result", {}).get("data", {})
            if isinstance(raw, dict) and "@value" in raw:
                raw = raw["@value"]
            return raw if isinstance(raw, list) else []

        def _unwrap(val):
            if isinstance(val, dict):
                if val.get("@type") == "g:Map" and "@value" in val:
                    flat = val["@value"]
                    if isinstance(flat, list):
                        return {
                            flat[i]: _unwrap(flat[i + 1])
                            for i in range(0, len(flat) - 1, 2)
                        }
                if "@value" in val:
                    return _unwrap(val["@value"])
            return val

        try:
            # Build a within() clause for all entity names
            escaped = [name.replace("'", "\\'") for name in entity_names]
            within_clause = ", ".join(f"'{e}'" for e in escaped)

            # Query edges between any pair of the entity_names
            q = (
                f"g.V().hasLabel('{label}')"
                f".has('canonical_name', within({within_clause}))"
                f".bothE().limit(200)"
                f".where(otherV().hasLabel('{label}')"
                f".has('canonical_name', within({within_clause})))"
                f".project('s','t','rel','w')"
                f".by(outV().values('canonical_name'))"
                f".by(inV().values('canonical_name'))"
                f".by(label)"
                f".by(coalesce(values('weight'), constant(1.0)))"
            )

            raw = _gremlin(q, timeout=25)
            seen: set = set()

            for r in raw:
                parsed = _unwrap(r)
                if not isinstance(parsed, dict):
                    continue

                source = parsed.get("s", "")
                target = parsed.get("t", "")
                rel = parsed.get("rel", "related_to")
                weight = parsed.get("w", 1.0)

                if isinstance(source, dict):
                    source = _unwrap(source)
                if isinstance(target, dict):
                    target = _unwrap(target)
                if isinstance(weight, dict):
                    weight = _unwrap(weight)

                source = str(source) if source else ""
                target = str(target) if target else ""

                if not source or not target:
                    continue

                # Deduplicate edges (treat A->B and B->A as same)
                edge_key = tuple(sorted([source, target])) + (str(rel),)
                if edge_key in seen:
                    continue
                seen.add(edge_key)

                edges.append(RelationshipEdge(
                    source=source,
                    target=target,
                    relationship_type=str(rel),
                    weight=float(weight) if weight else 1.0,
                ))

        except Exception as e:
            logger.error(
                "Neptune edge query failed for evidence assembly (case=%s): %s",
                case_id, str(e)[:200],
            )

        return edges
