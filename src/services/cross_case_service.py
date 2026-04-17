"""Cross-Case Analysis Service — entity matching, graph creation, overlap detection.

Manages cross-case entity matching, cross-reference report generation,
cross-case graph creation, automatic overlap scanning, and analyst-confirmed
connection creation.

Dependencies are injected via the constructor for testability:
    - NeptuneConnectionManager for Gremlin graph queries
    - ConnectionManager for Aurora metadata queries
    - CaseFileService for cross-case graph CRUD
    - A Bedrock client for AI-generated cross-case analysis
"""

import json
import uuid
from typing import Any, Protocol

from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import P

from db.connection import ConnectionManager
from db.neptune import (
    EDGE_CROSS_CASE_LINK,
    EDGE_PROP_CONFIDENCE,
    EDGE_PROP_CROSS_CASE_GRAPH_ID,
    EDGE_PROP_RELATIONSHIP_TYPE,
    NODE_PROP_CANONICAL_NAME,
    NODE_PROP_CASE_FILE_ID,
    NODE_PROP_CONFIDENCE,
    NODE_PROP_ENTITY_ID,
    NODE_PROP_ENTITY_TYPE,
    NODE_PROP_OCCURRENCE_COUNT,
    NODE_PROP_SOURCE_DOCUMENT_REFS,
    NeptuneConnectionManager,
    cross_case_label,
    entity_label,
)
from models.pattern import CrossCaseMatch, CrossReferenceReport
from services.case_file_service import CaseFileService


# ---------------------------------------------------------------------------
# Bedrock client protocol (for testability)
# ---------------------------------------------------------------------------


class BedrockClient(Protocol):
    """Minimal Bedrock client interface."""

    def invoke_model(self, **kwargs: Any) -> Any: ...


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"


# ---------------------------------------------------------------------------
# CrossCaseService
# ---------------------------------------------------------------------------


class CrossCaseService:
    """Manages cross-case analysis and dynamic knowledge graphs."""

    def __init__(
        self,
        neptune_conn: NeptuneConnectionManager,
        aurora_conn: ConnectionManager,
        case_file_service: CaseFileService,
        bedrock_client: Any,
    ) -> None:
        self._neptune = neptune_conn
        self._aurora = aurora_conn
        self._case_file_service = case_file_service
        self._bedrock = bedrock_client

    # ------------------------------------------------------------------
    # Find shared entities
    # ------------------------------------------------------------------

    def find_shared_entities(self, case_ids: list[str]) -> list[CrossCaseMatch]:
        """Query Neptune for shared/similar entities across case subgraphs.

        Entities are matched by ``canonical_name`` across different case
        subgraph labels.  For each matching pair, a ``CrossCaseMatch`` is
        produced with a similarity score of 1.0 (exact name match).

        Args:
            case_ids: Two or more case file identifiers.

        Returns:
            A list of ``CrossCaseMatch`` objects for shared entities.
        """
        if len(case_ids) < 2:
            return []

        # Collect entities per case from Neptune.
        entities_by_case: dict[str, list[dict]] = {}
        with self._neptune.traversal_source() as g:
            for cid in case_ids:
                label = entity_label(cid)
                nodes = (
                    g.V()
                    .hasLabel(label)
                    .project("entity_id", "canonical_name", "entity_type", "case_file_id")
                    .by(NODE_PROP_ENTITY_ID)
                    .by(NODE_PROP_CANONICAL_NAME)
                    .by(NODE_PROP_ENTITY_TYPE)
                    .by(NODE_PROP_CASE_FILE_ID)
                    .toList()
                )
                entities_by_case[cid] = nodes

        # Match entities across cases by canonical_name.
        matches: list[CrossCaseMatch] = []
        case_id_list = list(case_ids)
        for i in range(len(case_id_list)):
            for j in range(i + 1, len(case_id_list)):
                cid_a = case_id_list[i]
                cid_b = case_id_list[j]
                entities_a = entities_by_case.get(cid_a, [])
                entities_b = entities_by_case.get(cid_b, [])

                # Build lookup by canonical_name for case B.
                name_to_b: dict[str, list[dict]] = {}
                for ent in entities_b:
                    name = ent.get("canonical_name", "")
                    name_to_b.setdefault(name, []).append(ent)

                for ent_a in entities_a:
                    name_a = ent_a.get("canonical_name", "")
                    if name_a in name_to_b:
                        for ent_b in name_to_b[name_a]:
                            matches.append(
                                CrossCaseMatch(
                                    entity_a={
                                        "entity_id": ent_a.get("entity_id", ""),
                                        "name": name_a,
                                        "type": ent_a.get("entity_type", ""),
                                        "case_id": cid_a,
                                    },
                                    entity_b={
                                        "entity_id": ent_b.get("entity_id", ""),
                                        "name": ent_b.get("canonical_name", ""),
                                        "type": ent_b.get("entity_type", ""),
                                        "case_id": cid_b,
                                    },
                                    similarity_score=1.0,
                                )
                            )

        return matches

    # ------------------------------------------------------------------
    # Generate cross-reference report
    # ------------------------------------------------------------------

    def generate_cross_reference_report(
        self, case_ids: list[str],
    ) -> CrossReferenceReport:
        """Produce a cross-reference report with shared entities, parallel
        patterns, and AI analysis via Bedrock.

        Args:
            case_ids: Two or more case file identifiers.

        Returns:
            A ``CrossReferenceReport`` with shared entities, parallel
            patterns, and an AI-generated analysis section.
        """
        shared = self.find_shared_entities(case_ids)

        # Build parallel patterns from shared entity groupings.
        parallel_patterns = self._build_parallel_patterns(shared)

        # Generate AI analysis via Bedrock.
        ai_analysis = self._generate_ai_analysis(case_ids, shared, parallel_patterns)

        return CrossReferenceReport(
            report_id=str(uuid.uuid4()),
            case_ids=list(case_ids),
            shared_entities=shared,
            parallel_patterns=parallel_patterns,
            ai_analysis=ai_analysis,
        )

    def _build_parallel_patterns(
        self, matches: list[CrossCaseMatch],
    ) -> list[dict]:
        """Group shared entity matches into parallel patterns by entity type."""
        type_groups: dict[str, list[CrossCaseMatch]] = {}
        for m in matches:
            etype = m.entity_a.get("type", "unknown")
            type_groups.setdefault(etype, []).append(m)

        patterns: list[dict] = []
        for etype, group in type_groups.items():
            if len(group) >= 1:
                patterns.append({
                    "entity_type": etype,
                    "match_count": len(group),
                    "entity_names": list({m.entity_a.get("name", "") for m in group}),
                })
        return patterns

    def _generate_ai_analysis(
        self,
        case_ids: list[str],
        matches: list[CrossCaseMatch],
        parallel_patterns: list[dict],
    ) -> str:
        """Call Bedrock to generate AI analysis of cross-case connections."""
        entity_summary = ", ".join(
            f"{m.entity_a.get('name', '')} (shared between cases)"
            for m in matches[:10]  # limit prompt size
        )
        pattern_summary = ", ".join(
            f"{p.get('entity_type', '')}: {p.get('match_count', 0)} matches"
            for p in parallel_patterns
        )

        prompt = (
            f"Analyze the cross-case connections between research case files "
            f"{', '.join(case_ids)}.\n\n"
            f"Shared entities: {entity_summary or 'None found'}\n"
            f"Parallel patterns: {pattern_summary or 'None found'}\n\n"
            f"Provide a concise analysis of the significance of these "
            f"cross-case connections and what they might mean for the investigation."
        )

        try:
            response = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(response["body"].read())
            return body.get("content", [{}])[0].get("text", "")
        except Exception:
            return (
                f"Cross-case analysis between cases {', '.join(case_ids)}: "
                f"{len(matches)} shared entities found across "
                f"{len(parallel_patterns)} entity type groups."
            )

    # ------------------------------------------------------------------
    # Create cross-case graph
    # ------------------------------------------------------------------

    def create_cross_case_graph(
        self,
        name: str,
        case_ids: list[str],
        matches: list[CrossCaseMatch],
    ) -> str:
        """Create a dedicated Neptune subgraph with CROSS_CASE_LINK edges.

        Creates the cross-case graph metadata via ``CaseFileService``, then
        writes CROSS_CASE_LINK edges into a dedicated Neptune subgraph
        **without modifying** the original case file subgraphs.

        Args:
            name: Human-readable name for the cross-case graph.
            case_ids: Case file identifiers to link.
            matches: Shared entity matches to persist as edges.

        Returns:
            The ``graph_id`` of the newly created cross-case graph.
        """
        # Create metadata record in Aurora via CaseFileService.
        graph = self._case_file_service.create_cross_case_graph(
            name=name, case_ids=case_ids,
        )
        graph_id = graph.graph_id
        neptune_label = graph.neptune_subgraph_label

        # Write CROSS_CASE_LINK edges into the dedicated subgraph.
        with self._neptune.traversal_source() as g:
            for match in matches:
                node_a_id = str(uuid.uuid4())
                node_b_id = str(uuid.uuid4())

                # Create reference nodes in the cross-case subgraph.
                g.addV(neptune_label).property(
                    NODE_PROP_ENTITY_ID, node_a_id,
                ).property(
                    NODE_PROP_CANONICAL_NAME, match.entity_a.get("name", ""),
                ).property(
                    NODE_PROP_ENTITY_TYPE, match.entity_a.get("type", ""),
                ).property(
                    NODE_PROP_CASE_FILE_ID, match.entity_a.get("case_id", ""),
                ).property(
                    NODE_PROP_CONFIDENCE, match.similarity_score,
                ).iterate()

                g.addV(neptune_label).property(
                    NODE_PROP_ENTITY_ID, node_b_id,
                ).property(
                    NODE_PROP_CANONICAL_NAME, match.entity_b.get("name", ""),
                ).property(
                    NODE_PROP_ENTITY_TYPE, match.entity_b.get("type", ""),
                ).property(
                    NODE_PROP_CASE_FILE_ID, match.entity_b.get("case_id", ""),
                ).property(
                    NODE_PROP_CONFIDENCE, match.similarity_score,
                ).iterate()

                # Create CROSS_CASE_LINK edge between the reference nodes.
                g.V().hasLabel(neptune_label).has(
                    NODE_PROP_ENTITY_ID, node_a_id,
                ).addE(EDGE_CROSS_CASE_LINK).to(
                    __.V().hasLabel(neptune_label).has(
                        NODE_PROP_ENTITY_ID, node_b_id,
                    ),
                ).property(
                    EDGE_PROP_CROSS_CASE_GRAPH_ID, graph_id,
                ).property(
                    EDGE_PROP_CONFIDENCE, match.similarity_score,
                ).property(
                    EDGE_PROP_RELATIONSHIP_TYPE, "cross-case",
                ).iterate()

        return graph_id

    # ------------------------------------------------------------------
    # Scan for overlaps
    # ------------------------------------------------------------------

    def scan_for_overlaps(self, new_case_id: str) -> list[CrossCaseMatch]:
        """Scan a new case against all existing cases for entity overlaps.

        Returns candidate ``CrossCaseMatch`` objects **without** creating
        any CROSS_CASE_LINK edges in Neptune.

        Args:
            new_case_id: The newly ingested case file identifier.

        Returns:
            A list of candidate ``CrossCaseMatch`` objects.
        """
        # Get all case IDs from Aurora.
        with self._aurora.cursor() as cur:
            cur.execute(
                "SELECT case_id FROM case_files WHERE case_id != %s",
                (new_case_id,),
            )
            rows = cur.fetchall()

        existing_case_ids = [str(row[0]) for row in rows]
        if not existing_case_ids:
            return []

        # Collect entities for the new case.
        new_entities: list[dict] = []
        with self._neptune.traversal_source() as g:
            new_label = entity_label(new_case_id)
            new_entities = (
                g.V()
                .hasLabel(new_label)
                .project("entity_id", "canonical_name", "entity_type", "case_file_id")
                .by(NODE_PROP_ENTITY_ID)
                .by(NODE_PROP_CANONICAL_NAME)
                .by(NODE_PROP_ENTITY_TYPE)
                .by(NODE_PROP_CASE_FILE_ID)
                .toList()
            )

        if not new_entities:
            return []

        new_names = {ent.get("canonical_name", "") for ent in new_entities}
        new_by_name: dict[str, list[dict]] = {}
        for ent in new_entities:
            name = ent.get("canonical_name", "")
            new_by_name.setdefault(name, []).append(ent)

        # Scan each existing case for matching canonical names.
        candidates: list[CrossCaseMatch] = []
        with self._neptune.traversal_source() as g:
            for cid in existing_case_ids:
                label = entity_label(cid)
                existing_entities = (
                    g.V()
                    .hasLabel(label)
                    .project("entity_id", "canonical_name", "entity_type", "case_file_id")
                    .by(NODE_PROP_ENTITY_ID)
                    .by(NODE_PROP_CANONICAL_NAME)
                    .by(NODE_PROP_ENTITY_TYPE)
                    .by(NODE_PROP_CASE_FILE_ID)
                    .toList()
                )

                for ent_existing in existing_entities:
                    name = ent_existing.get("canonical_name", "")
                    if name in new_names:
                        for ent_new in new_by_name.get(name, []):
                            candidates.append(
                                CrossCaseMatch(
                                    entity_a={
                                        "entity_id": ent_new.get("entity_id", ""),
                                        "name": name,
                                        "type": ent_new.get("entity_type", ""),
                                        "case_id": new_case_id,
                                    },
                                    entity_b={
                                        "entity_id": ent_existing.get("entity_id", ""),
                                        "name": name,
                                        "type": ent_existing.get("entity_type", ""),
                                        "case_id": cid,
                                    },
                                    similarity_score=1.0,
                                )
                            )

        return candidates

    # ------------------------------------------------------------------
    # Confirm connection
    # ------------------------------------------------------------------

    def confirm_connection(
        self, match: CrossCaseMatch, graph_id: str,
    ) -> None:
        """Add an analyst-confirmed CROSS_CASE_LINK edge to a cross-case graph.

        Creates reference nodes in the cross-case graph's Neptune subgraph
        and a CROSS_CASE_LINK edge between them.

        Args:
            match: The confirmed ``CrossCaseMatch``.
            graph_id: The cross-case graph to add the connection to.
        """
        graph = self._case_file_service.get_cross_case_graph(graph_id)
        neptune_label = graph.neptune_subgraph_label

        with self._neptune.traversal_source() as g:
            node_a_id = str(uuid.uuid4())
            node_b_id = str(uuid.uuid4())

            # Create reference nodes in the cross-case subgraph.
            g.addV(neptune_label).property(
                NODE_PROP_ENTITY_ID, node_a_id,
            ).property(
                NODE_PROP_CANONICAL_NAME, match.entity_a.get("name", ""),
            ).property(
                NODE_PROP_ENTITY_TYPE, match.entity_a.get("type", ""),
            ).property(
                NODE_PROP_CASE_FILE_ID, match.entity_a.get("case_id", ""),
            ).property(
                NODE_PROP_CONFIDENCE, match.similarity_score,
            ).iterate()

            g.addV(neptune_label).property(
                NODE_PROP_ENTITY_ID, node_b_id,
            ).property(
                NODE_PROP_CANONICAL_NAME, match.entity_b.get("name", ""),
            ).property(
                NODE_PROP_ENTITY_TYPE, match.entity_b.get("type", ""),
            ).property(
                NODE_PROP_CASE_FILE_ID, match.entity_b.get("case_id", ""),
            ).property(
                NODE_PROP_CONFIDENCE, match.similarity_score,
            ).iterate()

            # Create CROSS_CASE_LINK edge.
            g.V().hasLabel(neptune_label).has(
                NODE_PROP_ENTITY_ID, node_a_id,
            ).addE(EDGE_CROSS_CASE_LINK).to(
                __.V().hasLabel(neptune_label).has(
                    NODE_PROP_ENTITY_ID, node_b_id,
                ),
            ).property(
                EDGE_PROP_CROSS_CASE_GRAPH_ID, graph_id,
            ).property(
                EDGE_PROP_CONFIDENCE, match.similarity_score,
            ).property(
                EDGE_PROP_RELATIONSHIP_TYPE, "cross-case",
            ).iterate()


    # ------------------------------------------------------------------
    # Sub-case creation from conspirator profile
    # ------------------------------------------------------------------

    def create_sub_case_from_conspirator(
        self,
        parent_case_id: str,
        person_name: str,
        relevant_entity_names: list[str],
        relevant_doc_ids: list[str],
    ) -> str:
        """Create a sub-case linked to the parent case.

        1. Create new case_files record in Aurora
        2. Copy relevant Neptune subgraph entities/relationships
        3. Create CROSS_CASE_LINK edges between parent and sub-case
        4. Preserve provenance links back to parent case

        Returns the new sub_case_id.
        """
        sub_case_id = str(uuid.uuid4())
        parent_label = entity_label(parent_case_id)
        sub_label = entity_label(sub_case_id)

        # 1. Create new case_files record in Aurora
        with self._aurora.cursor() as cur:
            cur.execute(
                """
                INSERT INTO case_files (case_id, case_name, status, metadata)
                SELECT %s,
                       'Sub-case: ' || %s || ' (from ' || case_name || ')',
                       'created',
                       jsonb_build_object(
                           'parent_case_id', %s,
                           'spawned_from_person', %s,
                           'provenance', 'conspiracy_network_discovery'
                       )
                FROM case_files WHERE case_id = %s
                """,
                (sub_case_id, person_name, parent_case_id, person_name, parent_case_id),
            )

        # 2. Copy relevant Neptune subgraph entities
        with self._neptune.traversal_source() as g:
            for entity_name in relevant_entity_names:
                # Get entity properties from parent subgraph
                props = g.V().hasLabel(parent_label).has(
                    NODE_PROP_CANONICAL_NAME, entity_name,
                ).valueMap(True).toList()

                if not props:
                    continue

                node_props = props[0] if props else {}
                new_entity_id = str(uuid.uuid4())

                # Create entity in sub-case subgraph
                t = g.addV(sub_label).property(
                    NODE_PROP_ENTITY_ID, new_entity_id,
                ).property(
                    NODE_PROP_CANONICAL_NAME, entity_name,
                ).property(
                    NODE_PROP_CASE_FILE_ID, sub_case_id,
                )

                # Copy entity_type if available
                etype = node_props.get(NODE_PROP_ENTITY_TYPE, [""])[0] if isinstance(
                    node_props.get(NODE_PROP_ENTITY_TYPE), list
                ) else node_props.get(NODE_PROP_ENTITY_TYPE, "")
                if etype:
                    t = t.property(NODE_PROP_ENTITY_TYPE, etype)

                t.iterate()

            # Copy relationships between relevant entities
            for entity_name in relevant_entity_names:
                edges = g.V().hasLabel(parent_label).has(
                    NODE_PROP_CANONICAL_NAME, entity_name,
                ).outE("RELATED_TO").as_("e").inV().hasLabel(parent_label).has(
                    NODE_PROP_CANONICAL_NAME, P.within(relevant_entity_names),
                ).select("e").project("src", "tgt", "type").by(
                    __.outV().values(NODE_PROP_CANONICAL_NAME)
                ).by(
                    __.inV().values(NODE_PROP_CANONICAL_NAME)
                ).by(
                    __.coalesce(__.values(EDGE_PROP_RELATIONSHIP_TYPE), __.constant("related"))
                ).toList()

                for edge in edges:
                    if not isinstance(edge, dict):
                        continue
                    src = edge.get("src", "")
                    tgt = edge.get("tgt", "")
                    rel_type = edge.get("type", "related")

                    # Create edge in sub-case subgraph
                    g.V().hasLabel(sub_label).has(
                        NODE_PROP_CANONICAL_NAME, src,
                    ).addE("RELATED_TO").to(
                        __.V().hasLabel(sub_label).has(
                            NODE_PROP_CANONICAL_NAME, tgt,
                        ),
                    ).property(
                        EDGE_PROP_RELATIONSHIP_TYPE, rel_type,
                    ).property(
                        "provenance_case_id", parent_case_id,
                    ).iterate()

            # 3. Create CROSS_CASE_LINK edges between parent and sub-case
            g.V().hasLabel(parent_label).has(
                NODE_PROP_CANONICAL_NAME, person_name,
            ).addE(EDGE_CROSS_CASE_LINK).to(
                __.V().hasLabel(sub_label).has(
                    NODE_PROP_CANONICAL_NAME, person_name,
                ),
            ).property(
                EDGE_PROP_CROSS_CASE_GRAPH_ID, f"subcase_{sub_case_id}",
            ).property(
                EDGE_PROP_CONFIDENCE, 1.0,
            ).property(
                EDGE_PROP_RELATIONSHIP_TYPE, "sub_case_provenance",
            ).iterate()

        return sub_case_id

