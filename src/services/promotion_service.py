"""Promotion Service — merges Collection entities into the Matter graph.

Handles the irreversible promotion of a Collection from qa_review into the
Matter's Neptune subgraph, including duplicate merging, snapshot creation,
and aggregated count updates.
"""

import uuid
from datetime import datetime, timezone

from db.connection import ConnectionManager
from db.neptune import (
    NeptuneConnectionManager,
    collection_staging_label,
    entity_label,
    EDGE_RELATED_TO,
    NODE_PROP_CANONICAL_NAME,
    NODE_PROP_ENTITY_TYPE,
    NODE_PROP_OCCURRENCE_COUNT,
    NODE_PROP_MATTER_ID,
    NODE_PROP_COLLECTION_ID,
)
from models.hierarchy import PromotionSnapshot


class PromotionService:
    """Promotes a Collection's staging subgraph into the Matter graph."""

    def __init__(
        self,
        connection_manager: ConnectionManager,
        neptune_manager: NeptuneConnectionManager,
    ) -> None:
        self._db = connection_manager
        self._neptune = neptune_manager

    # ------------------------------------------------------------------
    # Promote
    # ------------------------------------------------------------------

    def promote_collection(
        self,
        matter_id: str,
        collection_id: str,
        org_id: str,
    ) -> PromotionSnapshot:
        """Merge a Collection's entities into the Matter's Neptune subgraph.

        Steps:
            1. Lock the collection row (SELECT FOR UPDATE), verify status = qa_review
            2. Copy nodes from staging subgraph to matter subgraph
            3. Merge duplicate nodes by canonical_name
            4. Update collection status to promoted
            5. Create promotion_snapshot
            6. Update matter aggregated counts

        On Neptune failure the collection stays in qa_review so the
        operation can be retried.

        Raises:
            KeyError: If the collection does not exist for the given org.
            ValueError: If the collection is not in qa_review status.
        """
        # 1. Lock collection row and verify status
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT collection_id, matter_id, org_id, status,
                       entity_count, relationship_count
                FROM collections
                WHERE collection_id = %s AND org_id = %s
                FOR UPDATE
                """,
                (collection_id, org_id),
            )
            row = cur.fetchone()

        if row is None:
            raise KeyError(f"Collection not found: {collection_id}")

        current_status = row[3]
        if current_status != "qa_review":
            raise ValueError(
                f"Collection must be in qa_review status to promote "
                f"(current: {current_status})"
            )

        staging_label = collection_staging_label(collection_id)
        matter_label = entity_label(matter_id)

        # 2–3. Copy entities from staging to matter subgraph, merge duplicates
        entities_added = 0
        relationships_added = 0

        try:
            with self._neptune.traversal_source() as g:
                # Get all nodes in the staging subgraph
                staging_nodes = g.V().hasLabel(staging_label).toList()

                # Copy each node to the matter subgraph
                node_mapping: dict = {}  # staging node id -> matter node id
                for node in staging_nodes:
                    props = g.V(node).valueMap().next()
                    canonical_name = props.get(NODE_PROP_CANONICAL_NAME, [""])[0] if isinstance(props.get(NODE_PROP_CANONICAL_NAME), list) else props.get(NODE_PROP_CANONICAL_NAME, "")
                    entity_type = props.get(NODE_PROP_ENTITY_TYPE, [""])[0] if isinstance(props.get(NODE_PROP_ENTITY_TYPE), list) else props.get(NODE_PROP_ENTITY_TYPE, "")
                    occurrence_count = props.get(NODE_PROP_OCCURRENCE_COUNT, [1])[0] if isinstance(props.get(NODE_PROP_OCCURRENCE_COUNT), list) else props.get(NODE_PROP_OCCURRENCE_COUNT, 1)

                    node_id = f"{matter_id}_{entity_type}_{canonical_name}"

                    new_node = (
                        g.addV(matter_label)
                        .property("id", node_id)
                        .property(NODE_PROP_CANONICAL_NAME, canonical_name)
                        .property(NODE_PROP_ENTITY_TYPE, entity_type)
                        .property(NODE_PROP_OCCURRENCE_COUNT, occurrence_count)
                        .property(NODE_PROP_MATTER_ID, matter_id)
                        .property(NODE_PROP_COLLECTION_ID, collection_id)
                        .next()
                    )

                    node_mapping[node] = new_node
                    entities_added += 1

                # Copy edges from staging subgraph
                for staging_node in staging_nodes:
                    out_edges = g.V(staging_node).outE(EDGE_RELATED_TO).toList()
                    for edge in out_edges:
                        target_node = g.E(edge).inV().next()
                        if target_node in node_mapping:
                            edge_props = g.E(edge).valueMap().next()
                            new_edge = (
                                g.V(node_mapping[staging_node])
                                .addE(EDGE_RELATED_TO)
                                .to(g.V(node_mapping[target_node]))
                            )
                            for k, v in edge_props.items():
                                val = v[0] if isinstance(v, list) else v
                                new_edge = new_edge.property(k, val)
                            new_edge.next()
                            relationships_added += 1

                # Merge duplicate nodes in the matter subgraph by canonical_name
                seen_names: set = set()
                for node in staging_nodes:
                    props = g.V(node).valueMap().next()
                    canonical_name = props.get(NODE_PROP_CANONICAL_NAME, [""])[0] if isinstance(props.get(NODE_PROP_CANONICAL_NAME), list) else props.get(NODE_PROP_CANONICAL_NAME, "")
                    entity_type = props.get(NODE_PROP_ENTITY_TYPE, [""])[0] if isinstance(props.get(NODE_PROP_ENTITY_TYPE), list) else props.get(NODE_PROP_ENTITY_TYPE, "")
                    merge_key = f"{entity_type}:{canonical_name}"
                    if merge_key not in seen_names:
                        seen_names.add(merge_key)
                        self._merge_duplicates(g, matter_label, canonical_name, entity_type)

                # Clean up staging subgraph
                g.V().hasLabel(staging_label).drop().iterate()

        except Exception:
            # Neptune failure — leave collection in qa_review, clean up partial data
            try:
                with self._neptune.traversal_source() as g:
                    g.V().hasLabel(staging_label).drop().iterate()
            except Exception:
                pass  # Best-effort cleanup
            raise

        # 4–6. Update Aurora (only on Neptune success)
        now = datetime.now(timezone.utc)
        snapshot_id = str(uuid.uuid4())

        with self._db.cursor() as cur:
            # Update collection status to promoted
            cur.execute(
                """
                UPDATE collections
                SET status = 'promoted', promoted_at = %s
                WHERE collection_id = %s AND org_id = %s
                """,
                (now, collection_id, org_id),
            )

            # Create promotion snapshot
            cur.execute(
                """
                INSERT INTO promotion_snapshots
                    (snapshot_id, collection_id, matter_id,
                     entities_added, relationships_added, promoted_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (snapshot_id, collection_id, matter_id,
                 entities_added, relationships_added, now),
            )

            # Update matter aggregated counts
            cur.execute(
                """
                UPDATE matters
                SET total_documents = total_documents + (
                        SELECT COALESCE(document_count, 0)
                        FROM collections
                        WHERE collection_id = %s
                    ),
                    total_entities = total_entities + %s,
                    total_relationships = total_relationships + %s,
                    last_activity = %s
                WHERE matter_id = %s AND org_id = %s
                """,
                (collection_id, entities_added, relationships_added,
                 now, matter_id, org_id),
            )

        return PromotionSnapshot(
            snapshot_id=snapshot_id,
            collection_id=collection_id,
            matter_id=matter_id,
            entities_added=entities_added,
            relationships_added=relationships_added,
            promoted_at=now,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_promotion_snapshot(self, collection_id: str) -> PromotionSnapshot:
        """Retrieve the promotion snapshot for a collection.

        Raises:
            KeyError: If no snapshot exists for the given collection.
        """
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT snapshot_id, collection_id, matter_id,
                       entities_added, relationships_added,
                       promoted_at, promoted_by
                FROM promotion_snapshots
                WHERE collection_id = %s
                """,
                (collection_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise KeyError(
                f"Promotion snapshot not found for collection: {collection_id}"
            )

        return PromotionSnapshot(
            snapshot_id=str(row[0]),
            collection_id=str(row[1]),
            matter_id=str(row[2]),
            entities_added=row[3],
            relationships_added=row[4],
            promoted_at=row[5],
            promoted_by=row[6] or "",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_duplicates(g, label: str, canonical_name: str, entity_type: str) -> None:
        """Merge duplicate nodes in the matter subgraph by canonical_name + entity_type."""
        duplicates = (
            g.V()
            .hasLabel(label)
            .has(NODE_PROP_CANONICAL_NAME, canonical_name)
            .has(NODE_PROP_ENTITY_TYPE, entity_type)
            .toList()
        )

        if len(duplicates) <= 1:
            return

        # Aggregate occurrence counts
        total_occurrences = 0
        for node in duplicates:
            count_val = g.V(node).values(NODE_PROP_OCCURRENCE_COUNT).next()
            total_occurrences += int(count_val)

        keeper = duplicates[0]
        g.V(keeper).property(NODE_PROP_OCCURRENCE_COUNT, total_occurrences).next()

        for duplicate in duplicates[1:]:
            # Re-link incoming edges
            in_edges = g.V(duplicate).inE().toList()
            for edge in in_edges:
                props = g.E(edge).valueMap().next()
                from_vertex = g.E(edge).outV().next()
                edge_label = g.E(edge).label().next()
                new_edge = g.V(from_vertex).addE(edge_label).to(g.V(keeper))
                for k, v in props.items():
                    new_edge = new_edge.property(k, v)
                new_edge.next()

            # Re-link outgoing edges
            out_edges = g.V(duplicate).outE().toList()
            for edge in out_edges:
                props = g.E(edge).valueMap().next()
                to_vertex = g.E(edge).inV().next()
                edge_label = g.E(edge).label().next()
                new_edge = g.V(keeper).addE(edge_label).to(g.V(to_vertex))
                for k, v in props.items():
                    new_edge = new_edge.property(k, v)
                new_edge.next()

            g.V(duplicate).drop().iterate()
