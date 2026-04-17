"""Neptune Serverless graph schema constants and connection helper.

Defines node/edge label conventions, property names, bulk loader CSV
column formats, and a Gremlin connection helper for Neptune Serverless.

Environment variables:
    NEPTUNE_ENDPOINT — Neptune cluster endpoint (e.g. my-cluster.abc123.neptune.amazonaws.com)
    NEPTUNE_PORT     — Neptune port (default 8182)
"""

import os
from contextlib import contextmanager
from typing import Generator

from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal

# Feature flag: when "false", Neptune connections are not attempted
_NEPTUNE_ENABLED = os.environ.get("NEPTUNE_ENABLED", "true") == "true"

# ---------------------------------------------------------------------------
# Node label templates
# ---------------------------------------------------------------------------

ENTITY_LABEL_PREFIX = "Entity_"
CROSS_CASE_LABEL_PREFIX = "CrossCase_"


def entity_label(case_id: str) -> str:
    """Return the Neptune node label for per-case entities: ``Entity_{case_id}``."""
    return f"{ENTITY_LABEL_PREFIX}{case_id}"


def collection_staging_label(collection_id: str) -> str:
    """Return the staging subgraph label for a collection: ``Entity_{collection_id}``."""
    return f"{ENTITY_LABEL_PREFIX}{collection_id}"


def cross_case_label(graph_id: str) -> str:
    """Return the Neptune node label for cross-case references: ``CrossCase_{graph_id}``."""
    return f"{CROSS_CASE_LABEL_PREFIX}{graph_id}"


# ---------------------------------------------------------------------------
# Edge labels
# ---------------------------------------------------------------------------

EDGE_RELATED_TO = "RELATED_TO"
EDGE_CROSS_CASE_LINK = "CROSS_CASE_LINK"

# ---------------------------------------------------------------------------
# Node property names
# ---------------------------------------------------------------------------

NODE_PROP_ENTITY_ID = "entity_id"
NODE_PROP_ENTITY_TYPE = "entity_type"
NODE_PROP_CANONICAL_NAME = "canonical_name"
NODE_PROP_OCCURRENCE_COUNT = "occurrence_count"
NODE_PROP_CONFIDENCE = "confidence"
NODE_PROP_SOURCE_DOCUMENT_REFS = "source_document_refs"
NODE_PROP_CASE_FILE_ID = "case_file_id"
NODE_PROP_MATTER_ID = "matter_id"
NODE_PROP_COLLECTION_ID = "collection_id"

# ---------------------------------------------------------------------------
# Edge property names
# ---------------------------------------------------------------------------

EDGE_PROP_RELATIONSHIP_TYPE = "relationship_type"
EDGE_PROP_CONFIDENCE = "confidence"
EDGE_PROP_SOURCE_DOCUMENT_REF = "source_document_ref"
EDGE_PROP_CROSS_CASE_GRAPH_ID = "cross_case_graph_id"

# ---------------------------------------------------------------------------
# Valid values (mirrors src/models/entity.py enums for reference)
# ---------------------------------------------------------------------------

VALID_ENTITY_TYPES = frozenset(
    {"person", "location", "date", "artifact", "civilization", "theme", "event"}
)

VALID_RELATIONSHIP_TYPES = frozenset(
    {"co-occurrence", "causal", "temporal", "geographic", "thematic"}
)

# ---------------------------------------------------------------------------
# Neptune bulk loader CSV column formats
# ---------------------------------------------------------------------------

BULK_LOAD_NODES_COLUMNS = [
    "~id",
    "~label",
    f"{NODE_PROP_ENTITY_TYPE}:String",
    f"{NODE_PROP_CANONICAL_NAME}:String",
    f"{NODE_PROP_CONFIDENCE}:Float",
    f"{NODE_PROP_OCCURRENCE_COUNT}:Int",
    f"{NODE_PROP_CASE_FILE_ID}:String",
]

BULK_LOAD_EDGES_COLUMNS = [
    "~id",
    "~from",
    "~to",
    "~label",
    f"{EDGE_PROP_RELATIONSHIP_TYPE}:String",
    f"{EDGE_PROP_CONFIDENCE}:Float",
    f"{EDGE_PROP_SOURCE_DOCUMENT_REF}:String",
]

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

_DEFAULT_PORT = "8182"


def _get_env(name: str, default: str | None = None) -> str:
    """Return an environment variable or raise if missing and no default."""
    value = os.environ.get(name, default)
    if value is None:
        raise EnvironmentError(f"Required environment variable {name} is not set")
    return value


def _build_ws_url(endpoint: str, port: str) -> str:
    """Build the WebSocket URL for Neptune Gremlin connections."""
    return f"wss://{endpoint}:{port}/gremlin"


class NeptuneConnectionManager:
    """Manages a Gremlin connection to Neptune Serverless."""

    def __init__(
        self,
        endpoint: str | None = None,
        port: str | None = None,
    ) -> None:
        self._endpoint = endpoint or (_get_env("NEPTUNE_ENDPOINT") if _NEPTUNE_ENABLED else "")
        self._port = port or _get_env("NEPTUNE_PORT", _DEFAULT_PORT)

    @property
    def ws_url(self) -> str:
        """The WebSocket URL used for Gremlin connections."""
        return _build_ws_url(self._endpoint, self._port)

    @contextmanager
    def connection(self) -> Generator[DriverRemoteConnection, None, None]:
        """Yield a ``DriverRemoteConnection``, closing it on exit."""
        conn = DriverRemoteConnection(self.ws_url, "g")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def traversal_source(self) -> Generator:
        """Yield a Gremlin ``GraphTraversalSource`` bound to Neptune."""
        with self.connection() as conn:
            g = traversal().with_remote(conn)
            yield g


# Module-level singleton for convenience.
neptune_connection_manager = NeptuneConnectionManager()
