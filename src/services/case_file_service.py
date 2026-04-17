"""Case File Service — CRUD operations for case files.

Manages creation, retrieval, listing, status updates, archiving, and deletion
of case files in Aurora, with coordinated cleanup of S3 and Neptune resources.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import P

from db.connection import ConnectionManager
from db.neptune import (
    NeptuneConnectionManager,
    entity_label,
    cross_case_label,
    EDGE_RELATED_TO,
    NODE_PROP_ENTITY_ID,
    NODE_PROP_ENTITY_TYPE,
    NODE_PROP_CANONICAL_NAME,
    NODE_PROP_OCCURRENCE_COUNT,
    NODE_PROP_CONFIDENCE,
    NODE_PROP_SOURCE_DOCUMENT_REFS,
    NODE_PROP_CASE_FILE_ID,
    EDGE_PROP_RELATIONSHIP_TYPE,
    EDGE_PROP_CONFIDENCE,
    EDGE_PROP_SOURCE_DOCUMENT_REF,
)
from models.case_file import CaseFile, CaseFileStatus, CrossCaseGraph, SearchTier
from storage.s3_helper import case_prefix, delete_case_prefix

# Valid statuses as a set for fast membership checks.
_VALID_STATUSES = frozenset(s.value for s in CaseFileStatus)


class CaseFileService:
    """Handles case file CRUD, validation, and lifecycle management."""

    def __init__(
        self,
        connection_manager: ConnectionManager,
        neptune_manager: NeptuneConnectionManager,
    ) -> None:
        self._db = connection_manager
        self._neptune = neptune_manager

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_case_file(
        self,
        topic_name: str,
        description: str,
        parent_case_id: Optional[str] = None,
        search_tier: Optional[str] = None,
    ) -> CaseFile:
        """Create a new case file with logical separation in S3, Neptune, and Aurora.

        Raises:
            ValueError: If *topic_name* or *description* is missing/empty,
                        or if *search_tier* is not a valid SearchTier value.
        """
        if not topic_name or not topic_name.strip():
            raise ValueError("topic_name is required and cannot be empty")
        if not description or not description.strip():
            raise ValueError("description is required and cannot be empty")

        # Resolve and validate search_tier (default to "standard").
        resolved_tier = self._validate_search_tier(search_tier)

        case_id = str(uuid.uuid4())
        s3_pfx = case_prefix(case_id)
        neptune_label = entity_label(case_id)
        now = datetime.now(timezone.utc)

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO case_files
                    (case_id, topic_name, description, status,
                     parent_case_id, s3_prefix, neptune_subgraph_label,
                     created_at, last_activity, search_tier)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    case_id,
                    topic_name.strip(),
                    description.strip(),
                    CaseFileStatus.CREATED.value,
                    parent_case_id,
                    s3_pfx,
                    neptune_label,
                    now,
                    now,
                    resolved_tier.value,
                ),
            )

        return CaseFile(
            case_id=case_id,
            topic_name=topic_name.strip(),
            description=description.strip(),
            status=CaseFileStatus.CREATED,
            created_at=now,
            parent_case_id=parent_case_id,
            s3_prefix=s3_pfx,
            neptune_subgraph_label=neptune_label,
            last_activity=now,
            search_tier=resolved_tier,
        )

    def create_sub_case_file(
        self,
        parent_case_id: str,
        topic_name: str,
        description: str,
        entity_names: Optional[list[str]] = None,
        pattern_id: Optional[str] = None,
    ) -> CaseFile:
        """Create a sub-case file seeded with entities/relationships from the parent.

        Copies relevant entity nodes and relationship edges from the parent's
        Neptune subgraph into the new sub-case's subgraph.  If *entity_names*
        is provided, only those entities (and edges between them) are copied.
        If *pattern_id* is provided it is stored as metadata context but the
        entity scoping is driven by *entity_names*.  When neither is given,
        all entities from the parent subgraph are copied.

        The sub-case file can subsequently ingest additional data through the
        standard ingestion pipeline.

        Raises:
            KeyError: If the parent case file does not exist.
            ValueError: If *topic_name* or *description* is missing/empty.
        """
        # 1. Verify parent exists and grab its Neptune label.
        parent = self.get_case_file(parent_case_id)
        parent_label = parent.neptune_subgraph_label

        # 2. Create the child case file (delegates validation to create_case_file).
        sub_case = self.create_case_file(
            topic_name=topic_name,
            description=description,
            parent_case_id=parent_case_id,
        )
        sub_label = sub_case.neptune_subgraph_label

        # 3. Copy entity nodes and relationship edges from parent → sub-case.
        self._copy_subgraph_seed(parent_label, sub_label, entity_names)

        return sub_case

    # ------------------------------------------------------------------
    # Subgraph seed copy helpers
    # ------------------------------------------------------------------

    def _copy_subgraph_seed(
        self,
        parent_label: str,
        sub_label: str,
        entity_names: Optional[list[str]] = None,
    ) -> None:
        """Copy entity nodes and their inter-relationships from *parent_label*
        subgraph into *sub_label* subgraph in Neptune."""
        with self._neptune.traversal_source() as g:
            # --- Fetch nodes ---------------------------------------------------
            traversal = g.V().has_label(parent_label)
            if entity_names:
                traversal = traversal.has(NODE_PROP_CANONICAL_NAME,
                                          P.within(*entity_names))
            nodes = traversal.element_map().to_list()

            if not nodes:
                return

            # Build a set of copied node IDs for edge filtering.
            copied_node_ids: set[str] = set()

            for node in nodes:
                node_id = str(node.get(NODE_PROP_ENTITY_ID, ""))
                copied_node_ids.add(node_id)

                g.add_v(sub_label).property(
                    NODE_PROP_ENTITY_ID, node_id
                ).property(
                    NODE_PROP_ENTITY_TYPE,
                    str(node.get(NODE_PROP_ENTITY_TYPE, "")),
                ).property(
                    NODE_PROP_CANONICAL_NAME,
                    str(node.get(NODE_PROP_CANONICAL_NAME, "")),
                ).property(
                    NODE_PROP_OCCURRENCE_COUNT,
                    node.get(NODE_PROP_OCCURRENCE_COUNT, 0),
                ).property(
                    NODE_PROP_CONFIDENCE,
                    node.get(NODE_PROP_CONFIDENCE, 0.0),
                ).property(
                    NODE_PROP_SOURCE_DOCUMENT_REFS,
                    str(node.get(NODE_PROP_SOURCE_DOCUMENT_REFS, "[]")),
                ).property(
                    NODE_PROP_CASE_FILE_ID,
                    str(node.get(NODE_PROP_CASE_FILE_ID, "")),
                ).iterate()

            # --- Fetch and copy edges between copied nodes ---------------------
            edges = (
                g.V()
                .has_label(parent_label)
                .has(NODE_PROP_ENTITY_ID, P.within(*copied_node_ids))
                .outE(EDGE_RELATED_TO)
                .as_("e")
                .inV()
                .has(NODE_PROP_ENTITY_ID, P.within(*copied_node_ids))
                .select("e")
                .element_map()
                .to_list()
            )

            for edge in edges:
                src_id = str(edge.get("OUT_V", edge.get("outV", "")))
                tgt_id = str(edge.get("IN_V", edge.get("inV", "")))

                g.V().has_label(sub_label).has(
                    NODE_PROP_ENTITY_ID, src_id
                ).add_e(EDGE_RELATED_TO).to(
                    __.V().has_label(sub_label).has(NODE_PROP_ENTITY_ID, tgt_id)
                ).property(
                    EDGE_PROP_RELATIONSHIP_TYPE,
                    str(edge.get(EDGE_PROP_RELATIONSHIP_TYPE, "")),
                ).property(
                    EDGE_PROP_CONFIDENCE,
                    edge.get(EDGE_PROP_CONFIDENCE, 0.0),
                ).property(
                    EDGE_PROP_SOURCE_DOCUMENT_REF,
                    str(edge.get(EDGE_PROP_SOURCE_DOCUMENT_REF, "")),
                ).iterate()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_case_file(self, case_id: str) -> CaseFile:
        """Retrieve a case file by ID.

        Raises:
            KeyError: If the case file does not exist.
        """
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT case_id, topic_name, description, status,
                       parent_case_id, s3_prefix, neptune_subgraph_label,
                       document_count, entity_count, relationship_count,
                       error_details, created_at, last_activity, search_tier
                FROM case_files
                WHERE case_id = %s
                """,
                (case_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise KeyError(f"Case file not found: {case_id}")

        return self._row_to_case_file(row)

    def list_case_files(
        self,
        *,
        status: Optional[str] = None,
        topic_keyword: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        entity_count_min: Optional[int] = None,
        entity_count_max: Optional[int] = None,
    ) -> list[CaseFile]:
        """List case files with optional filters."""
        clauses: list[str] = []
        params: list = []

        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        if topic_keyword is not None:
            clauses.append("to_tsvector('english', topic_name) @@ plainto_tsquery('english', %s)")
            params.append(topic_keyword)
        if date_from is not None:
            clauses.append("created_at >= %s")
            params.append(date_from)
        if date_to is not None:
            clauses.append("created_at <= %s")
            params.append(date_to)
        if entity_count_min is not None:
            clauses.append("entity_count >= %s")
            params.append(entity_count_min)
        if entity_count_max is not None:
            clauses.append("entity_count <= %s")
            params.append(entity_count_max)

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        query = f"""
            SELECT case_id, topic_name, description, status,
                   parent_case_id, s3_prefix, neptune_subgraph_label,
                   document_count, entity_count, relationship_count,
                   error_details, created_at, last_activity, search_tier
            FROM case_files
            {where}
            ORDER BY document_count DESC, created_at DESC
        """

        with self._db.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [self._row_to_case_file(row) for row in rows]

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_status(
        self,
        case_id: str,
        status: CaseFileStatus,
        error_details: Optional[str] = None,
        **kwargs,
    ) -> CaseFile:
        """Update case file status with valid status set enforcement.

        Raises:
            ValueError: If *status* is not a valid ``CaseFileStatus``,
                        or if *kwargs* contains ``search_tier`` (tier is immutable).
            KeyError: If the case file does not exist.
        """
        if "search_tier" in kwargs:
            raise ValueError("TIER_IMMUTABLE: search_tier cannot be changed after case file creation")

        if isinstance(status, str):
            if status not in _VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Must be one of: {sorted(_VALID_STATUSES)}"
                )
            status = CaseFileStatus(status)
        elif not isinstance(status, CaseFileStatus):
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {sorted(_VALID_STATUSES)}"
            )

        now = datetime.now(timezone.utc)

        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE case_files
                SET status = %s, error_details = %s, last_activity = %s
                WHERE case_id = %s
                RETURNING case_id
                """,
                (status.value, error_details, now, case_id),
            )
            if cur.fetchone() is None:
                raise KeyError(f"Case file not found: {case_id}")

        return self.get_case_file(case_id)

    # ------------------------------------------------------------------
    # Archive
    # ------------------------------------------------------------------

    def update_search_tier(self, case_id: str, search_tier: str) -> None:
        """Reject any attempt to change search_tier on an existing case file.

        Raises:
            ValueError: Always — search_tier is immutable after creation.
        """
        raise ValueError(
            "TIER_IMMUTABLE: search_tier cannot be changed after case file creation"
        )

    # ------------------------------------------------------------------
    # Archive (continued)
    # ------------------------------------------------------------------

    def archive_case_file(self, case_id: str) -> CaseFile:
        """Archive a case file — sets status to 'archived' without deleting data.

        Raises:
            KeyError: If the case file does not exist.
        """
        return self.update_status(case_id, CaseFileStatus.ARCHIVED)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_case_file(self, case_id: str) -> None:
        """Delete a case file and all associated data (Aurora, S3, Neptune).

        Removes:
        - Aurora metadata record
        - S3 prefix (all objects under ``cases/{case_id}/``)
        - Neptune subgraph (all nodes with the case's label)
        - Vector embeddings (cascade-deleted via Aurora FK)

        Raises:
            KeyError: If the case file does not exist.
        """
        # Verify existence first.
        case_file = self.get_case_file(case_id)

        # 1. Delete Neptune subgraph nodes and edges.
        self._delete_neptune_subgraph(case_file.neptune_subgraph_label)

        # 2. Delete S3 prefix.
        delete_case_prefix(case_id)

        # 3. Delete Aurora record (cascades to documents, findings, etc.).
        with self._db.cursor() as cur:
            cur.execute("DELETE FROM case_files WHERE case_id = %s", (case_id,))

    # ------------------------------------------------------------------
    # Cross-Case Graph CRUD
    # ------------------------------------------------------------------

    def create_cross_case_graph(
        self,
        name: str,
        case_ids: list[str],
    ) -> CrossCaseGraph:
        """Create a new cross-case graph workspace linking multiple case files.

        Generates a UUID, creates a Neptune subgraph label, inserts metadata
        into Aurora, and inserts member records for each case ID.

        Raises:
            ValueError: If *name* is missing/empty or *case_ids* has fewer than 2 entries.
        """
        if not name or not name.strip():
            raise ValueError("name is required and cannot be empty")
        if not case_ids or len(case_ids) < 2:
            raise ValueError("At least two case IDs are required to create a cross-case graph")

        graph_id = str(uuid.uuid4())
        neptune_label = cross_case_label(graph_id)
        now = datetime.now(timezone.utc)

        with self._db.cursor() as cur:
            # Insert graph metadata.
            cur.execute(
                """
                INSERT INTO cross_case_graphs
                    (graph_id, name, neptune_subgraph_label, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (graph_id, name.strip(), neptune_label, now),
            )
            # Insert member records.
            for cid in case_ids:
                cur.execute(
                    """
                    INSERT INTO cross_case_graph_members (graph_id, case_id)
                    VALUES (%s, %s)
                    """,
                    (graph_id, cid),
                )

        return CrossCaseGraph(
            graph_id=graph_id,
            name=name.strip(),
            linked_case_ids=list(case_ids),
            created_at=now,
            neptune_subgraph_label=neptune_label,
        )

    def get_cross_case_graph(self, graph_id: str) -> CrossCaseGraph:
        """Retrieve a cross-case graph by ID.

        Raises:
            KeyError: If the cross-case graph does not exist.
        """
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT graph_id, name, neptune_subgraph_label,
                       analyst_notes, status, created_at
                FROM cross_case_graphs
                WHERE graph_id = %s
                """,
                (graph_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise KeyError(f"Cross-case graph not found: {graph_id}")

        # Fetch linked case IDs.
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT case_id FROM cross_case_graph_members
                WHERE graph_id = %s
                """,
                (graph_id,),
            )
            member_rows = cur.fetchall()

        linked_case_ids = [str(r[0]) for r in member_rows]

        return CrossCaseGraph(
            graph_id=str(row[0]),
            name=row[1],
            neptune_subgraph_label=row[2],
            analyst_notes=row[3] or "",
            status=row[4] or "active",
            created_at=row[5],
            linked_case_ids=linked_case_ids,
        )

    def update_cross_case_graph(
        self,
        graph_id: str,
        add_case_ids: list[str] | None = None,
        remove_case_ids: list[str] | None = None,
    ) -> CrossCaseGraph:
        """Add or remove case files from an existing cross-case graph.

        Updates the membership table in Aurora and manages Neptune cross-case
        edges accordingly.

        Raises:
            KeyError: If the cross-case graph does not exist.
            ValueError: If the update would leave fewer than 2 members.
        """
        # Verify existence.
        existing = self.get_cross_case_graph(graph_id)

        current_ids = set(existing.linked_case_ids)
        to_add = set(add_case_ids or [])
        to_remove = set(remove_case_ids or [])

        new_ids = (current_ids | to_add) - to_remove

        if len(new_ids) < 2:
            raise ValueError(
                "A cross-case graph must link at least 2 case files after update"
            )

        with self._db.cursor() as cur:
            # Remove members.
            for cid in to_remove & current_ids:
                cur.execute(
                    "DELETE FROM cross_case_graph_members WHERE graph_id = %s AND case_id = %s",
                    (graph_id, cid),
                )
            # Add new members.
            for cid in to_add - current_ids:
                cur.execute(
                    """
                    INSERT INTO cross_case_graph_members (graph_id, case_id)
                    VALUES (%s, %s)
                    """,
                    (graph_id, cid),
                )

        # Update Neptune edges: drop edges for removed cases, add placeholder
        # edges for newly added cases.
        neptune_label = existing.neptune_subgraph_label
        with self._neptune.traversal_source() as g:
            for cid in to_remove & current_ids:
                g.V().has_label(neptune_label).has(
                    "case_file_id", cid
                ).bothE("CROSS_CASE_LINK").drop().iterate()
            # Note: actual cross-case link edges are created by CrossCaseService
            # during analysis. Here we only clean up removed members.

        return self.get_cross_case_graph(graph_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _delete_neptune_subgraph(self, label: str) -> None:
        """Drop all vertices with the given label from Neptune."""
        with self._neptune.traversal_source() as g:
            g.V().has_label(label).drop().iterate()

    @staticmethod
    def _validate_search_tier(tier: Optional[str]) -> SearchTier:
        """Validate and resolve a search tier value.

        Returns SearchTier.STANDARD when *tier* is None or absent.

        Raises:
            ValueError: If *tier* is not a valid SearchTier value.
        """
        if tier is None:
            return SearchTier.STANDARD
        try:
            return SearchTier(tier)
        except ValueError:
            allowed = [t.value for t in SearchTier]
            raise ValueError(
                f"Invalid search_tier '{tier}'. Must be one of: {allowed}"
            )

    @staticmethod
    def _row_to_case_file(row: tuple) -> CaseFile:
        """Map a database row to a ``CaseFile`` model instance."""
        # search_tier is at index 13; default to "standard" if absent/None.
        raw_tier = row[13] if len(row) > 13 else None
        tier = SearchTier(raw_tier) if raw_tier else SearchTier.STANDARD

        return CaseFile(
            case_id=str(row[0]),
            topic_name=row[1],
            description=row[2],
            status=CaseFileStatus(row[3]),
            parent_case_id=str(row[4]) if row[4] else None,
            s3_prefix=row[5],
            neptune_subgraph_label=row[6],
            document_count=row[7],
            entity_count=row[8],
            relationship_count=row[9],
            error_details=row[10],
            created_at=row[11],
            last_activity=row[12],
            search_tier=tier,
        )
