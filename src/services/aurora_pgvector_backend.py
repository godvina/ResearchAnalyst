"""AuroraPgvectorBackend — SearchBackend implementation using Aurora pgvector.

Wraps the existing Aurora Serverless v2 + pgvector vector search logic
behind the SearchBackend protocol. Supports semantic (cosine similarity)
search only.
"""

import json
import logging
from typing import Optional

from db.connection import ConnectionManager
from models.search import FacetedFilter, SearchResult
from services.search_backend import IndexDocumentRequest

logger = logging.getLogger(__name__)


class AuroraPgvectorBackend:
    """SearchBackend implementation using Aurora Serverless v2 + pgvector.

    Supports semantic (vector similarity) search only.
    Delegates to the existing ConnectionManager for database access.
    """

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._db = connection_manager

    @property
    def supported_modes(self) -> list[str]:
        return ["semantic"]

    def index_documents(
        self,
        case_id: str,
        documents: list[IndexDocumentRequest],
    ) -> int:
        """Store document embeddings in the Aurora documents table.

        Uses INSERT ... ON CONFLICT for idempotent upserts.
        Returns count of successfully indexed documents.
        """
        indexed = 0
        with self._db.cursor() as cur:
            for doc in documents:
                cur.execute(
                    """
                    INSERT INTO documents
                        (document_id, case_file_id, source_filename,
                         source_metadata, raw_text, sections, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        raw_text = EXCLUDED.raw_text,
                        sections = EXCLUDED.sections,
                        source_filename = EXCLUDED.source_filename,
                        source_metadata = EXCLUDED.source_metadata
                    """,
                    (
                        doc.document_id,
                        doc.case_file_id,
                        doc.metadata.get("source_filename", ""),
                        json.dumps(doc.metadata),
                        doc.text,
                        json.dumps(doc.metadata.get("sections", [])),
                        str(doc.embedding),
                    ),
                )
                indexed += 1
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
        """Cosine similarity search via pgvector.

        Raises ValueError if mode is not 'semantic'.
        """
        if mode != "semantic":
            raise ValueError(
                f"Search mode '{mode}' is not available for standard tier. "
                f"Available modes: {self.supported_modes}"
            )
        if embedding is None:
            raise ValueError("Embedding is required for semantic search")

        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT document_id, raw_text, source_filename,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM documents
                WHERE case_file_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (str(embedding), case_id, str(embedding), top_k),
            )
            rows = cur.fetchall()

        results: list[SearchResult] = []
        for row in rows:
            doc_id, raw_text, source_filename, similarity = row
            score = max(0.0, min(1.0, float(similarity)))
            passage = raw_text[:500] if raw_text else ""
            results.append(
                SearchResult(
                    document_id=doc_id,
                    passage=passage,
                    relevance_score=score,
                    source_document_ref=source_filename or "",
                )
            )
        return results

    def delete_documents(
        self,
        case_id: str,
        document_ids: Optional[list[str]] = None,
    ) -> int:
        """Delete from Aurora documents table by case_id and optional document_ids.

        If document_ids is None, deletes all documents for the case.
        Returns count of deleted documents.
        """
        with self._db.cursor() as cur:
            if document_ids is not None:
                if not document_ids:
                    return 0
                placeholders = ",".join(["%s"] * len(document_ids))
                cur.execute(
                    f"""
                    DELETE FROM documents
                    WHERE case_file_id = %s AND document_id IN ({placeholders})
                    """,
                    (case_id, *document_ids),
                )
            else:
                cur.execute(
                    "DELETE FROM documents WHERE case_file_id = %s",
                    (case_id,),
                )
            return cur.rowcount
