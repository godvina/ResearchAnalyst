"""Neptune graph loader — hybrid bulk CSV and Gremlin loading.

Handles loading entities and relationships into Neptune Serverless via
bulk CSV loading (for large batches) or incremental Gremlin writes
(for small updates).

The bulk loader uses Neptune's REST API at ``https://{endpoint}:{port}/loader``
and requires an IAM role with S3 read access for the CSV files.
"""

import csv
import io
import os
import time
import uuid
from typing import Any, Protocol

# Feature flag: when "false", all Neptune operations return empty results
_NEPTUNE_ENABLED = os.environ.get("NEPTUNE_ENABLED", "true") == "true"

from db.neptune import (
    BULK_LOAD_EDGES_COLUMNS,
    BULK_LOAD_NODES_COLUMNS,
    EDGE_PROP_CONFIDENCE,
    EDGE_PROP_RELATIONSHIP_TYPE,
    EDGE_PROP_SOURCE_DOCUMENT_REF,
    EDGE_RELATED_TO,
    NODE_PROP_CANONICAL_NAME,
    NODE_PROP_CASE_FILE_ID,
    NODE_PROP_CONFIDENCE,
    NODE_PROP_ENTITY_TYPE,
    NODE_PROP_OCCURRENCE_COUNT,
    NeptuneConnectionManager,
    entity_label,
)
from models.entity import ExtractedEntity, ExtractedRelationship
from storage.s3_helper import PrefixType, upload_file

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POLL_INTERVAL_SECONDS = 5
MAX_POLL_ATTEMPTS = 120  # 10 minutes at 5-second intervals

LOAD_COMPLETED = "LOAD_COMPLETED"
LOAD_FAILED = "LOAD_FAILED"


# ---------------------------------------------------------------------------
# HTTP client protocol (for testability)
# ---------------------------------------------------------------------------


class HttpClient(Protocol):
    """Minimal requests-compatible HTTP client interface."""

    def post(self, url: str, **kwargs: Any) -> Any: ...
    def get(self, url: str, **kwargs: Any) -> Any: ...


# ---------------------------------------------------------------------------
# NeptuneGraphLoader
# ---------------------------------------------------------------------------


class NeptuneGraphLoader:
    """Loads entities and relationships into Neptune via bulk CSV or Gremlin."""

    def __init__(
        self,
        connection_manager: NeptuneConnectionManager,
        http_client: Any | None = None,
        s3_bucket: str | None = None,
    ) -> None:
        """Initialise the loader.

        Args:
            connection_manager: A ``NeptuneConnectionManager`` for Gremlin access.
            http_client: An optional *requests*-compatible HTTP client used for
                the Neptune bulk loader REST API.  When ``None`` the stdlib
                ``requests`` library is imported lazily.
            s3_bucket: Optional S3 bucket name override.  Falls back to the
                ``S3_BUCKET_NAME`` environment variable via ``s3_helper``.
        """
        self._conn = connection_manager
        self._http = http_client
        self._s3_bucket = s3_bucket

    # -- internal helpers ---------------------------------------------------

    def _get_http_client(self) -> Any:
        if self._http is not None:
            return self._http
        import requests  # noqa: F811
        return requests

    def _loader_url(self) -> str:
        """Build the Neptune bulk loader REST endpoint URL."""
        # The ws_url looks like wss://host:port/gremlin — extract host:port.
        ws = self._conn.ws_url  # wss://host:port/gremlin
        # Strip scheme and path to get host:port
        host_port = ws.replace("wss://", "").replace("/gremlin", "")
        return f"https://{host_port}/loader"

    # -- CSV generation -----------------------------------------------------

    def generate_nodes_csv(
        self,
        case_id: str,
        entities: list[ExtractedEntity],
    ) -> str:
        """Generate a Neptune bulk-loader nodes CSV and upload to S3.

        Columns follow ``BULK_LOAD_NODES_COLUMNS``:
        ``~id, ~label, entity_type, canonical_name, confidence,
        occurrence_count, case_file_id``

        Args:
            case_id: The case file identifier.
            entities: Extracted entities to write as graph nodes.

        Returns:
            The S3 key where the CSV was uploaded.
        """
        label = entity_label(case_id)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(BULK_LOAD_NODES_COLUMNS)

        for ent in entities:
            node_id = f"{case_id}_{ent.entity_type.value}_{ent.canonical_name}"
            writer.writerow([
                node_id,
                label,
                ent.entity_type.value,
                ent.canonical_name,
                ent.confidence,
                ent.occurrences,
                case_id,
            ])

        csv_content = buf.getvalue()
        batch_id = uuid.uuid4().hex[:12]
        filename = f"{batch_id}_nodes.csv"
        s3_key = upload_file(
            case_id,
            PrefixType.BULK_LOAD,
            filename,
            csv_content,
            bucket=self._s3_bucket,
        )
        return s3_key

    def generate_edges_csv(
        self,
        case_id: str,
        entities: list[ExtractedEntity],
        relationships: list[ExtractedRelationship],
    ) -> str:
        """Generate a Neptune bulk-loader edges CSV and upload to S3.

        Columns follow ``BULK_LOAD_EDGES_COLUMNS``:
        ``~id, ~from, ~to, ~label, relationship_type, confidence,
        source_document_ref``

        Args:
            case_id: The case file identifier.
            entities: Extracted entities (used to build node IDs for ~from/~to).
            relationships: Extracted relationships to write as graph edges.

        Returns:
            The S3 key where the CSV was uploaded.
        """
        # Build a lookup from canonical_name -> node_id so we can resolve
        # relationship source/target to the correct ~from / ~to values.
        entity_node_ids: dict[str, str] = {}
        for ent in entities:
            node_id = f"{case_id}_{ent.entity_type.value}_{ent.canonical_name}"
            entity_node_ids[ent.canonical_name] = node_id

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(BULK_LOAD_EDGES_COLUMNS)

        for rel in relationships:
            from_id = entity_node_ids.get(rel.source_entity, rel.source_entity)
            to_id = entity_node_ids.get(rel.target_entity, rel.target_entity)
            edge_id = f"{case_id}_edge_{rel.source_entity}_{rel.target_entity}_{rel.relationship_type.value}"
            writer.writerow([
                edge_id,
                from_id,
                to_id,
                EDGE_RELATED_TO,
                rel.relationship_type.value,
                rel.confidence,
                rel.source_document_ref,
            ])

        csv_content = buf.getvalue()
        batch_id = uuid.uuid4().hex[:12]
        filename = f"{batch_id}_edges.csv"
        s3_key = upload_file(
            case_id,
            PrefixType.BULK_LOAD,
            filename,
            csv_content,
            bucket=self._s3_bucket,
        )
        return s3_key

    # -- Bulk loader API ----------------------------------------------------

    def bulk_load(
        self,
        nodes_csv_s3_path: str,
        edges_csv_s3_path: str,
        iam_role_arn: str,
        s3_bucket: str | None = None,
    ) -> dict:
        """Trigger the Neptune bulk loader for the given S3 CSVs.

        Args:
            nodes_csv_s3_path: S3 key for the nodes CSV.
            edges_csv_s3_path: S3 key for the edges CSV.
            iam_role_arn: IAM role ARN with S3 read access.
            s3_bucket: S3 bucket name (defaults to instance bucket).

        Returns:
            A dict with ``load_id`` and ``status`` from the loader response.
        """
        if not _NEPTUNE_ENABLED:
            return {"nodes": {"load_id": "", "status": "DISABLED"}, "edges": {"load_id": "", "status": "DISABLED"}}

        bucket = s3_bucket or self._s3_bucket
        http = self._get_http_client()
        url = self._loader_url()

        results: dict[str, Any] = {}
        for label, s3_key in [("nodes", nodes_csv_s3_path), ("edges", edges_csv_s3_path)]:
            payload = {
                "source": f"s3://{bucket}/{s3_key}",
                "format": "csv",
                "iamRoleArn": iam_role_arn,
                "region": "us-east-1",
                "failOnError": "FALSE",
            }
            response = http.post(url, json=payload)
            body = response.json() if callable(getattr(response, "json", None)) else response.json
            load_id = body.get("payload", {}).get("loadId", "")
            results[label] = {"load_id": load_id, "status": body.get("status", "UNKNOWN")}

        return results

    def poll_bulk_load_status(self, load_id: str) -> str:
        """Poll the Neptune bulk loader until the load completes or fails.

        Args:
            load_id: The load ID returned by ``bulk_load()``.

        Returns:
            Final status string: ``LOAD_COMPLETED`` or ``LOAD_FAILED``.

        Raises:
            TimeoutError: If polling exceeds ``MAX_POLL_ATTEMPTS``.
        """
        http = self._get_http_client()
        url = f"{self._loader_url()}/{load_id}"

        for _ in range(MAX_POLL_ATTEMPTS):
            response = http.get(url)
            body = response.json() if callable(getattr(response, "json", None)) else response.json
            overall_status = (
                body.get("payload", {}).get("overallStatus", {}).get("status", "")
            )
            if overall_status == LOAD_COMPLETED:
                return LOAD_COMPLETED
            if overall_status == LOAD_FAILED:
                return LOAD_FAILED
            time.sleep(POLL_INTERVAL_SECONDS)

        raise TimeoutError(
            f"Neptune bulk load {load_id} did not complete within "
            f"{MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS} seconds"
        )

    # -- Gremlin incremental loading ----------------------------------------

    def load_via_gremlin(
        self,
        case_id: str,
        entities: list[ExtractedEntity],
        relationships: list[ExtractedRelationship],
    ) -> dict:
        """Write entities and relationships to Neptune via Gremlin.

        Used for small incremental updates below the bulk-load threshold.

        Args:
            case_id: The case file identifier.
            entities: Entities to add as graph nodes.
            relationships: Relationships to add as graph edges.

        Returns:
            A dict with ``nodes_created`` and ``edges_created`` counts.
        """
        if not _NEPTUNE_ENABLED:
            return {"nodes_created": 0, "edges_created": 0}

        label = entity_label(case_id)
        nodes_created = 0
        edges_created = 0

        with self._conn.traversal_source() as g:
            # Add entity nodes
            for ent in entities:
                node_id = f"{case_id}_{ent.entity_type.value}_{ent.canonical_name}"
                (
                    g.addV(label)
                    .property("id", node_id)
                    .property(NODE_PROP_ENTITY_TYPE, ent.entity_type.value)
                    .property(NODE_PROP_CANONICAL_NAME, ent.canonical_name)
                    .property(NODE_PROP_CONFIDENCE, ent.confidence)
                    .property(NODE_PROP_OCCURRENCE_COUNT, ent.occurrences)
                    .property(NODE_PROP_CASE_FILE_ID, case_id)
                    .next()
                )
                nodes_created += 1

            # Build lookup for edge creation
            entity_node_ids: dict[str, str] = {}
            for ent in entities:
                node_id = f"{case_id}_{ent.entity_type.value}_{ent.canonical_name}"
                entity_node_ids[ent.canonical_name] = node_id

            # Add relationship edges
            for rel in relationships:
                from_id = entity_node_ids.get(rel.source_entity)
                to_id = entity_node_ids.get(rel.target_entity)
                if from_id is None or to_id is None:
                    continue

                (
                    g.V(from_id)
                    .addE(EDGE_RELATED_TO)
                    .to(g.V(to_id))
                    .property(EDGE_PROP_RELATIONSHIP_TYPE, rel.relationship_type.value)
                    .property(EDGE_PROP_CONFIDENCE, rel.confidence)
                    .property(EDGE_PROP_SOURCE_DOCUMENT_REF, rel.source_document_ref)
                    .next()
                )
                edges_created += 1

        return {"nodes_created": nodes_created, "edges_created": edges_created}

    # -- Duplicate merging --------------------------------------------------

    def merge_duplicate_nodes(
        self,
        case_id: str,
        canonical_name: str,
        entity_type: str,
    ) -> None:
        """Merge duplicate entity nodes by canonical name + type.

        Finds all nodes in the case subgraph matching the given name and type,
        aggregates their occurrence counts, and removes the duplicates — keeping
        a single canonical node.

        Args:
            case_id: The case file identifier.
            canonical_name: The entity canonical name to deduplicate.
            entity_type: The entity type string (e.g. ``"person"``).
        """
        if not _NEPTUNE_ENABLED:
            return

        label = entity_label(case_id)

        with self._conn.traversal_source() as g:
            # Find all matching nodes
            duplicates = (
                g.V()
                .hasLabel(label)
                .has(NODE_PROP_CANONICAL_NAME, canonical_name)
                .has(NODE_PROP_ENTITY_TYPE, entity_type)
                .toList()
            )

            if len(duplicates) <= 1:
                return  # nothing to merge

            # Aggregate occurrence counts from all duplicates
            total_occurrences = 0
            for node in duplicates:
                count_val = g.V(node).values(NODE_PROP_OCCURRENCE_COUNT).next()
                total_occurrences += int(count_val)

            # Keep the first node, update its count, drop the rest
            keeper = duplicates[0]
            g.V(keeper).property(NODE_PROP_OCCURRENCE_COUNT, total_occurrences).next()

            for duplicate in duplicates[1:]:
                # Re-link incoming/outgoing edges to the keeper
                # Incoming edges
                in_edges = g.V(duplicate).inE().toList()
                for edge in in_edges:
                    props = g.E(edge).valueMap().next()
                    from_vertex = g.E(edge).outV().next()
                    edge_label = g.E(edge).label().next()
                    new_edge = g.V(from_vertex).addE(edge_label).to(g.V(keeper))
                    for k, v in props.items():
                        new_edge = new_edge.property(k, v)
                    new_edge.next()

                # Outgoing edges
                out_edges = g.V(duplicate).outE().toList()
                for edge in out_edges:
                    props = g.E(edge).valueMap().next()
                    to_vertex = g.E(edge).inV().next()
                    edge_label = g.E(edge).label().next()
                    new_edge = g.V(keeper).addE(edge_label).to(g.V(to_vertex))
                    for k, v in props.items():
                        new_edge = new_edge.property(k, v)
                    new_edge.next()

                # Drop the duplicate node (and its now-orphaned edges)
                g.V(duplicate).drop().iterate()
