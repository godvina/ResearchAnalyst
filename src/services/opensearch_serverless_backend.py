"""OpenSearchServerlessBackend — SearchBackend implementation using OpenSearch Serverless.

Supports semantic (kNN), keyword (BM25), and hybrid (compound query with RRF)
search modes with faceted filtering. Uses SigV4-signed HTTP requests via
urllib.request and botocore, consistent with the existing Neptune HTTP pattern.

Each case file gets its own OpenSearch index: 'case-{case_id}'.
"""

import json
import logging
import os
import socket
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import boto3  # noqa: F401 — used indirectly via botocore
import botocore.auth
import botocore.awsrequest
import botocore.credentials
from botocore.session import Session as BotocoreSession

from models.search import FacetedFilter, SearchResult
from services.search_backend import IndexDocumentRequest

logger = logging.getLogger(__name__)

# Feature flag: when "false", OpenSearch operations return empty results
_OPENSEARCH_ENABLED = os.environ.get("OPENSEARCH_ENABLED", "true") == "true"

# Vector dimension for Amazon Titan Embed Text v2
_EMBEDDING_DIMENSION = 1536




def _urlopen_ipv4(req, context=None, timeout=30):
    """Open a URL forcing IPv4 resolution.

    Monkey-patches socket.getaddrinfo temporarily to force AF_INET,
    avoiding IPv6 'Cannot assign requested address' errors in VPC Lambdas.
    """
    _orig_getaddrinfo = socket.getaddrinfo

    def _ipv4_only_getaddrinfo(*args, **kwargs):
        # Force AF_INET (IPv4)
        responses = _orig_getaddrinfo(*args, **kwargs)
        return [r for r in responses if r[0] == socket.AF_INET] or responses

    socket.getaddrinfo = _ipv4_only_getaddrinfo
    try:
        return urllib.request.urlopen(req, context=context, timeout=timeout)
    finally:
        socket.getaddrinfo = _orig_getaddrinfo


class OpenSearchServerlessBackend:
    """SearchBackend implementation using OpenSearch Serverless.

    Supports semantic, keyword, and hybrid search modes.
    Each case file gets its own OpenSearch index: 'case-{case_id}'.
    """

    def __init__(self, collection_endpoint: Optional[str] = None) -> None:
        self._endpoint = (
            collection_endpoint
            or os.environ.get("OPENSEARCH_ENDPOINT", "")
        ).rstrip("/")
        if not self._endpoint and not _OPENSEARCH_ENABLED:
            # OpenSearch is disabled — methods will return empty results
            self._sign_host = ""
            self._connect_endpoint = ""
            self._region = os.environ.get("AWS_REGION", "us-east-1")
            self._ssl_ctx = ssl.create_default_context()
            return
        if not self._endpoint:
            raise EnvironmentError(
                "OpenSearch Serverless endpoint not configured. "
                "Set OPENSEARCH_ENDPOINT environment variable."
            )
        # Ensure endpoint has https:// prefix
        if not self._endpoint.startswith("https://"):
            self._endpoint = f"https://{self._endpoint}"

        # Extract the original host for SigV4 signing
        self._sign_host = urlparse(self._endpoint).hostname or ""

        # If a VPC endpoint URL is configured, use it for actual connections
        # but keep the original host for SigV4 signing and Host header
        vpce_url = os.environ.get("OPENSEARCH_VPCE_URL", "")
        if vpce_url:
            self._connect_endpoint = vpce_url.rstrip("/")
            if not self._connect_endpoint.startswith("https://"):
                self._connect_endpoint = f"https://{self._connect_endpoint}"
        else:
            self._connect_endpoint = self._endpoint

        self._region = os.environ.get("AWS_REGION", "us-east-1")
        self._ssl_ctx = ssl.create_default_context()
        # When using VPC endpoint URL, hostname won't match cert
        if vpce_url:
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        if not self._endpoint.startswith("https://"):
            self._endpoint = f"https://{self._endpoint}"

        self._region = os.environ.get("AWS_REGION", "us-east-1")
        self._ssl_ctx = ssl.create_default_context()

    # ------------------------------------------------------------------
    # SearchBackend Protocol implementation
    # ------------------------------------------------------------------

    @property
    def supported_modes(self) -> list[str]:
        return ["semantic", "keyword", "hybrid"]

    def index_documents(
        self,
        case_id: str,
        documents: list[IndexDocumentRequest],
    ) -> int:
        """Bulk index documents into OpenSearch Serverless.

        Creates the index if it doesn't exist, then uses the _bulk API.
        Returns count of successfully indexed documents.
        """
        if not _OPENSEARCH_ENABLED:
            return 0

        if not documents:
            return 0

        self._ensure_index(case_id)
        index_name = self._index_name(case_id)

        # Build NDJSON bulk payload
        lines: list[str] = []
        for doc in documents:
            action = json.dumps({"index": {"_index": index_name}})
            body = {
                "document_id": doc.document_id,
                "case_file_id": doc.case_file_id,
                "text": doc.text,
                "embedding": doc.embedding,
                "source_filename": doc.metadata.get("source_filename", ""),
                "document_type": doc.metadata.get("document_type", ""),
                "persons": doc.metadata.get("persons", []),
                "entity_types": doc.metadata.get("entity_types", []),
                "date_indexed": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "date_range_start": doc.metadata.get("date_range_start"),
                "date_range_end": doc.metadata.get("date_range_end"),
            }
            lines.append(action)
            lines.append(json.dumps(body))

        bulk_payload = "\n".join(lines) + "\n"

        resp = self._request(
            "POST",
            "/_bulk",
            body=bulk_payload,
            content_type="application/x-ndjson",
        )

        # Parse bulk response to count successes
        indexed = 0
        if resp.get("errors"):
            for item in resp.get("items", []):
                op = item.get("index", item.get("create", {}))
                if op.get("status") in (200, 201):
                    indexed += 1
                else:
                    err = op.get("error", {})
                    logger.warning(
                        "Bulk index failure for doc %s: %s",
                        op.get("_id", "?"),
                        json.dumps(err)[:300],
                    )
        else:
            indexed = len(documents)

        logger.info("Bulk indexed %d/%d documents into %s", indexed, len(documents), index_name)
        return indexed

    def search(
        self,
        case_id: str,
        query: str,
        *,
        mode: str = "semantic",
        embedding: Optional[list[float]] = None,
        filters: Optional[FacetedFilter] = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Execute search based on mode.

        - 'keyword': BM25 full-text match on text field
        - 'semantic': kNN on embedding field
        - 'hybrid': compound query combining BM25 + kNN with RRF
        Applies faceted filters as OpenSearch bool filter clauses.
        """
        if not _OPENSEARCH_ENABLED:
            return []

        if mode not in self.supported_modes:
            raise ValueError(
                f"Search mode '{mode}' is not supported. "
                f"Available modes: {self.supported_modes}"
            )

        index_name = self._index_name(case_id)

        # Check if index exists; return empty results if not
        if not self._index_exists(index_name):
            return []

        filter_clauses = self._build_filter_clauses(filters) if filters else []

        if mode == "keyword":
            os_query = self._build_keyword_query(query, filter_clauses, top_k)
        elif mode == "semantic":
            if embedding is None:
                raise ValueError("Embedding is required for semantic search")
            os_query = self._build_semantic_query(embedding, filter_clauses, top_k)
        else:  # hybrid
            if embedding is None:
                raise ValueError("Embedding is required for hybrid search")
            os_query = self._build_hybrid_query(query, embedding, filter_clauses, top_k)

        resp = self._request("POST", f"/{index_name}/_search", body=json.dumps(os_query))
        return self._parse_search_response(resp)

    def delete_documents(
        self,
        case_id: str,
        document_ids: Optional[list[str]] = None,
    ) -> int:
        """Delete documents from the case's OpenSearch index.

        If document_ids is None, delete the entire index.
        Returns count of deleted documents.
        """
        if not _OPENSEARCH_ENABLED:
            return 0

        index_name = self._index_name(case_id)

        if not self._index_exists(index_name):
            return 0

        if document_ids is None:
            # Delete entire index
            count = self._get_doc_count(index_name)
            self._request("DELETE", f"/{index_name}")
            logger.info("Deleted index %s (%d documents)", index_name, count)
            return count

        if not document_ids:
            return 0

        # Delete by query matching document_ids
        delete_query = {
            "query": {
                "terms": {"document_id": document_ids}
            }
        }
        resp = self._request(
            "POST",
            f"/{index_name}/_delete_by_query",
            body=json.dumps(delete_query),
        )
        deleted = resp.get("deleted", 0)
        logger.info("Deleted %d documents from %s", deleted, index_name)
        return deleted

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _index_name(self, case_id: str) -> str:
        """Return the OpenSearch index name for a case."""
        return f"case-{case_id}"

    def _ensure_index(self, case_id: str) -> None:
        """Create the OpenSearch index with correct mappings if it doesn't exist."""
        index_name = self._index_name(case_id)
        if self._index_exists(index_name):
            return

        mapping = self._build_index_mapping()
        try:
            self._request("PUT", f"/{index_name}", body=json.dumps(mapping))
            logger.info("Created index %s", index_name)
        except Exception as exc:
            # Index may have been created concurrently — check again
            if self._index_exists(index_name):
                logger.info("Index %s already exists (concurrent creation)", index_name)
            else:
                raise RuntimeError(f"Failed to create index {index_name}: {exc}") from exc

    def _index_exists(self, index_name: str) -> bool:
        """Check if an OpenSearch index exists."""
        try:
            self._request("HEAD", f"/{index_name}")
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            raise

    def _get_doc_count(self, index_name: str) -> int:
        """Return the document count for an index."""
        try:
            resp = self._request("GET", f"/{index_name}/_count")
            return resp.get("count", 0)
        except Exception:
            return 0

    def _build_index_mapping(self) -> dict:
        """Return the OpenSearch index mapping with text, knn_vector, and metadata fields."""
        return {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 512,
                }
            },
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "case_file_id": {"type": "keyword"},
                    "text": {
                        "type": "text",
                        "analyzer": "standard",
                    },
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": _EMBEDDING_DIMENSION,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 512,
                                "m": 16,
                            },
                        },
                    },
                    "source_filename": {"type": "keyword"},
                    "document_type": {"type": "keyword"},
                    "persons": {"type": "keyword"},
                    "entity_types": {"type": "keyword"},
                    "date_indexed": {"type": "date"},
                    "date_range_start": {"type": "date"},
                    "date_range_end": {"type": "date"},
                }
            },
        }

    # ------------------------------------------------------------------
    # Query builders
    # ------------------------------------------------------------------

    def _build_keyword_query(
        self, query: str, filter_clauses: list[dict], top_k: int
    ) -> dict:
        """Build a BM25 full-text search query."""
        must = [{"match": {"text": {"query": query}}}]
        body: dict = {
            "size": top_k,
            "query": {
                "bool": {
                    "must": must,
                    "filter": filter_clauses,
                }
            },
        }
        return body

    def _build_semantic_query(
        self, embedding: list[float], filter_clauses: list[dict], top_k: int
    ) -> dict:
        """Build a kNN vector similarity search query."""
        body: dict = {
            "size": top_k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": embedding,
                        "k": top_k,
                    }
                }
            },
        }
        # Apply filters via post_filter for kNN queries
        if filter_clauses:
            body["post_filter"] = {"bool": {"filter": filter_clauses}}
        return body

    def _build_hybrid_query(
        self,
        query: str,
        embedding: list[float],
        filter_clauses: list[dict],
        top_k: int,
    ) -> dict:
        """Build a hybrid query combining BM25 + kNN with RRF normalization."""
        body: dict = {
            "size": top_k,
            "query": {
                "hybrid": {
                    "queries": [
                        {
                            "match": {
                                "text": {"query": query}
                            }
                        },
                        {
                            "knn": {
                                "embedding": {
                                    "vector": embedding,
                                    "k": top_k,
                                }
                            }
                        },
                    ]
                }
            },
        }
        if filter_clauses:
            body["post_filter"] = {"bool": {"filter": filter_clauses}}
        return body

    # ------------------------------------------------------------------
    # Faceted filter translation
    # ------------------------------------------------------------------

    def _build_filter_clauses(self, filters: FacetedFilter) -> list[dict]:
        """Translate FacetedFilter into OpenSearch bool filter clauses."""
        clauses: list[dict] = []

        if filters.date_from or filters.date_to:
            date_range: dict = {}
            if filters.date_from:
                date_range["gte"] = filters.date_from
            if filters.date_to:
                date_range["lte"] = filters.date_to
            clauses.append({"range": {"date_indexed": date_range}})

        if filters.person:
            clauses.append({"term": {"persons": filters.person}})

        if filters.document_type:
            clauses.append({"term": {"document_type": filters.document_type}})

        if filters.entity_type:
            clauses.append({"term": {"entity_types": filters.entity_type}})

        return clauses

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_search_response(self, resp: dict) -> list[SearchResult]:
        """Parse an OpenSearch search response into SearchResult objects."""
        hits = resp.get("hits", {}).get("hits", [])
        results: list[SearchResult] = []
        for hit in hits:
            source = hit.get("_source", {})
            raw_score = hit.get("_score", 0.0)
            # Normalize score to [0, 1] — OpenSearch BM25 scores can exceed 1
            score = max(0.0, min(1.0, float(raw_score) if raw_score <= 1.0 else 1.0 / (1.0 + 1.0 / float(raw_score))))
            text = source.get("text", "")
            passage = text[:500] if text else ""
            results.append(
                SearchResult(
                    document_id=source.get("document_id", hit.get("_id", "")),
                    passage=passage,
                    relevance_score=score,
                    source_document_ref=source.get("source_filename", ""),
                )
            )
        return results

    # ------------------------------------------------------------------
    # HTTP transport with SigV4 signing
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[str] = None,
        content_type: str = "application/json",
    ) -> dict:
        """Execute a SigV4-signed HTTP request against OpenSearch Serverless.

        Uses botocore's own HTTP session for correct SigV4 handling.
        AOSS requires explicit X-Amz-Content-Sha256 header for write operations.
        """
        import hashlib

        url = f"{self._endpoint}{path}"

        session = BotocoreSession()
        credentials = session.get_credentials()
        if credentials is None:
            raise EnvironmentError("No AWS credentials available for SigV4 signing")
        credentials = credentials.get_frozen_credentials()

        headers = {
            "Content-Type": content_type,
        }
        body_bytes = body.encode("utf-8") if body else b""

        # AOSS requires explicit content SHA256 for write operations
        headers["X-Amz-Content-Sha256"] = hashlib.sha256(body_bytes).hexdigest()

        aws_request = botocore.awsrequest.AWSRequest(
            method=method, url=url, headers=headers, data=body_bytes,
        )
        signer = botocore.auth.SigV4Auth(credentials, "aoss", self._region)
        signer.add_auth(aws_request)

        prepared = aws_request.prepare()

        try:
            from botocore.httpsession import URLLib3Session
            http_session = URLLib3Session()
            response = http_session.send(prepared)

            resp_body = response.content.decode("utf-8") if response.content else ""
            print(f"AOSS DEBUG: {method} {path} -> {response.status_code} body={resp_body[:300]}")

            if response.status_code >= 400:
                if method == "HEAD":
                    raise urllib.error.HTTPError(url, response.status_code, "Error", {}, None)
                logger.error(
                    "OpenSearch HTTP error %s %s -> %s: %s",
                    method, path, response.status_code, resp_body[:500],
                )
                raise urllib.error.HTTPError(url, response.status_code, "Error", {}, None)

            if not resp_body:
                return {}
            return json.loads(resp_body)
        except urllib.error.HTTPError:
            raise
        except Exception as exc:
            logger.error("OpenSearch connection error: %s", str(exc))
            raise

