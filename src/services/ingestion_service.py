"""Ingestion service — orchestrates the full document ingestion pipeline.

Coordinates document upload, parsing, entity extraction, embedding generation,
graph population, and knowledge base indexing for a case file.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from db.connection import ConnectionManager
from models.case_file import CaseFileStatus
from models.document import BatchResult, ExtractionResult
from models.entity import ExtractedEntity, ExtractedRelationship
from services.backend_factory import BackendFactory
from services.case_file_service import CaseFileService
from services.document_parser import DocumentParser
from services.entity_extraction_service import EntityExtractionService
from services.neptune_graph_loader import NeptuneGraphLoader
from services.search_backend import IndexDocumentRequest
from storage.s3_helper import PrefixType, download_file, list_files, upload_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BULK_LOAD_THRESHOLD = 20

# Default Bedrock embedding model
_DEFAULT_EMBEDDING_MODEL = "amazon.titan-embed-text-v1"


class IngestionService:
    """Orchestrates the full ingestion pipeline for a case file."""

    def __init__(
        self,
        document_parser: DocumentParser,
        entity_extraction_service: EntityExtractionService,
        neptune_graph_loader: NeptuneGraphLoader,
        case_file_service: CaseFileService,
        bedrock_client: Any,
        aurora_connection_manager: ConnectionManager,
        *,
        s3_bucket: str | None = None,
        embedding_model_id: str = _DEFAULT_EMBEDDING_MODEL,
        iam_role_arn: str = "",
        backend_factory: BackendFactory | None = None,
    ) -> None:
        self._parser = document_parser
        self._extractor = entity_extraction_service
        self._graph_loader = neptune_graph_loader
        self._case_service = case_file_service
        self._bedrock = bedrock_client
        self._aurora = aurora_connection_manager
        self._s3_bucket = s3_bucket
        self._embedding_model_id = embedding_model_id
        self._iam_role_arn = iam_role_arn
        self._backend_factory = backend_factory

    # ------------------------------------------------------------------
    # upload_documents
    # ------------------------------------------------------------------

    def upload_documents(
        self,
        case_id: str,
        files: list[tuple[str, bytes]],
    ) -> list[str]:
        """Upload raw files to S3 under ``cases/{case_id}/raw/{document_id}.{ext}``.

        Args:
            case_id: The case file identifier.
            files: A list of ``(filename, content)`` tuples.

        Returns:
            A list of generated document IDs (one per file).
        """
        document_ids: list[str] = []
        for filename, content in files:
            document_id = str(uuid.uuid4())
            ext = filename.rsplit(".", 1)[-1] if "." in filename else "txt"
            s3_filename = f"{document_id}.{ext}"
            upload_file(
                case_id,
                PrefixType.RAW,
                s3_filename,
                content,
                bucket=self._s3_bucket,
            )
            document_ids.append(document_id)
        return document_ids

    # ------------------------------------------------------------------
    # process_document
    # ------------------------------------------------------------------

    def process_document(
        self,
        case_id: str,
        document_id: str,
    ) -> ExtractionResult:
        """Process a single document through the full extraction pipeline.

        Steps:
        1. Download raw file from S3
        2. Parse with DocumentParser
        3. Extract entities and relationships with EntityExtractionService
        4. Generate embedding via Bedrock embedding model
        5. Store embedding + metadata in Aurora documents table
        6. Store extraction artifact JSON to S3 extractions prefix
        7. Return ExtractionResult

        Args:
            case_id: The case file identifier.
            document_id: The document identifier.

        Returns:
            An ExtractionResult with extracted entities and relationships.
        """
        # 1. Download raw file from S3
        raw_files = self._find_raw_file(case_id, document_id)
        file_size_bytes = len(raw_files)
        raw_content = raw_files.decode("utf-8")

        # 2. Parse
        parsed = self._parser.parse(
            raw_content=raw_content,
            document_id=document_id,
            case_file_id=case_id,
        )

        # Attach page count and file size to parsed document
        page_count = max(1, len(raw_content) // 3000)
        parsed.page_count = page_count
        parsed.file_size_bytes = file_size_bytes

        # 3. Extract entities and relationships
        entities = self._extractor.extract_entities(parsed.raw_text, document_id)
        relationships = self._extractor.extract_relationships(
            parsed.raw_text, entities, document_id
        )

        # 4. Generate embedding
        embedding = self._generate_embedding(parsed.raw_text)

        # 5. Index via backend factory (or fall back to direct Aurora storage)
        if self._backend_factory is not None:
            case_file = self._case_service.get_case_file(case_id)
            backend = self._backend_factory.get_backend(case_file.search_tier)
            index_req = IndexDocumentRequest(
                document_id=document_id,
                case_file_id=case_id,
                text=parsed.raw_text,
                embedding=embedding,
                metadata={
                    "source_filename": parsed.source_metadata.get("filename", ""),
                    "sections": parsed.sections,
                },
            )
            backend.index_documents(case_id, [index_req])
        else:
            self._store_document_embedding(
                document_id=document_id,
                case_file_id=case_id,
                parsed=parsed,
                embedding=embedding,
            )

        # 6. Store extraction artifact JSON to S3
        artifact = {
            "document_id": document_id,
            "case_file_id": case_id,
            "entities": [e.model_dump(mode="json") for e in entities],
            "relationships": [r.model_dump(mode="json") for r in relationships],
            "provenance": {
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "source_s3_key": f"cases/{case_id}/raw/{document_id}",
                "parse_method": "DocumentParser.parse",
                "extraction_model": str(getattr(self._extractor, "_model_id", "unknown")),
                "embedding_model": self._embedding_model_id,
                "entity_count": len(entities),
                "relationship_count": len(relationships),
                "document_type": str(getattr(self._extractor, "_last_document_type", "miscellaneous")),
                "file_size_bytes": file_size_bytes,
                "page_count_estimate": page_count,
                "chunk_count": len(self._extractor.chunk_text(parsed.raw_text)),
            },
        }
        artifact_filename = f"{document_id}_extraction.json"
        upload_file(
            case_id,
            PrefixType.EXTRACTIONS,
            artifact_filename,
            json.dumps(artifact),
            bucket=self._s3_bucket,
        )

        # 7. Return ExtractionResult
        return ExtractionResult(
            document_id=document_id,
            entities=[e.model_dump(mode="json") for e in entities],
            relationships=[r.model_dump(mode="json") for r in relationships],
        )

    # ------------------------------------------------------------------
    # process_batch
    # ------------------------------------------------------------------

    def process_batch(
        self,
        case_id: str,
        document_ids: list[str],
    ) -> BatchResult:
        """Process a batch of documents, continuing on individual failures.

        Steps:
        1. Process all documents individually (collecting results and failures)
        2. Merge all entities across documents
        3. Choose loading strategy: bulk CSV if batch >= threshold, Gremlin otherwise
        4. Update case file status to "indexed" with statistics
        5. Return BatchResult

        Args:
            case_id: The case file identifier.
            document_ids: List of document IDs to process.

        Returns:
            A BatchResult summarising the batch run.
        """
        results: list[ExtractionResult] = []
        failures: list[dict] = []

        # 1. Process each document individually
        for doc_id in document_ids:
            try:
                result = self.process_document(case_id, doc_id)
                results.append(result)
            except Exception as exc:
                backend_type = "unknown"
                if self._backend_factory is not None:
                    try:
                        case_file = self._case_service.get_case_file(case_id)
                        backend = self._backend_factory.get_backend(case_file.search_tier)
                        backend_type = type(backend).__name__
                    except Exception:
                        pass
                logger.error(
                    "Indexing failed for document_id=%s backend=%s: %s",
                    doc_id,
                    backend_type,
                    exc,
                )
                failures.append({"document_id": doc_id, "error": str(exc)})

        # 2. Merge all entities across documents
        all_entities: list[ExtractedEntity] = []
        all_relationships: list[ExtractedRelationship] = []
        for result in results:
            doc_entities = [ExtractedEntity(**e) for e in result.entities]
            doc_rels = [ExtractedRelationship(**r) for r in result.relationships]
            all_entities = EntityExtractionService.merge_entities(all_entities, doc_entities)
            all_relationships.extend(doc_rels)

        # 3. Choose graph loading strategy
        if all_entities or all_relationships:
            if len(document_ids) >= BULK_LOAD_THRESHOLD:
                nodes_key = self._graph_loader.generate_nodes_csv(case_id, all_entities)
                edges_key = self._graph_loader.generate_edges_csv(
                    case_id, all_entities, all_relationships
                )
                self._graph_loader.bulk_load(
                    nodes_csv_s3_path=nodes_key,
                    edges_csv_s3_path=edges_key,
                    iam_role_arn=self._iam_role_arn,
                    s3_bucket=self._s3_bucket,
                )
            else:
                self._graph_loader.load_via_gremlin(
                    case_id, all_entities, all_relationships
                )

        # 4. Update case file status to "indexed" with statistics
        self._case_service.update_status(case_id, CaseFileStatus.INDEXED)
        self._update_case_statistics(
            case_id=case_id,
            document_count=len(results),
            entity_count=len(all_entities),
            relationship_count=len(all_relationships),
        )

        # 5. Return BatchResult
        return BatchResult(
            case_file_id=case_id,
            total_documents=len(document_ids),
            successful=len(results),
            failed=len(failures),
            document_count=len(results),
            entity_count=len(all_entities),
            relationship_count=len(all_relationships),
            failures=failures,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_raw_file(self, case_id: str, document_id: str) -> bytes:
        """Download the raw file for a document from S3.

        Tries common extensions to locate the file.
        """
        raw_files = list_files(case_id, PrefixType.RAW, bucket=self._s3_bucket)
        for filename in raw_files:
            if filename.startswith(document_id):
                return download_file(
                    case_id, PrefixType.RAW, filename, bucket=self._s3_bucket
                )
        raise FileNotFoundError(
            f"Raw file not found for document {document_id} in case {case_id}"
        )

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate a vector embedding via Bedrock embedding model."""
        body = json.dumps({"inputText": text})
        response = self._bedrock.invoke_model(
            modelId=self._embedding_model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        response_body = json.loads(response["body"].read())
        return response_body["embedding"]

    def _store_document_embedding(
        self,
        document_id: str,
        case_file_id: str,
        parsed: Any,
        embedding: list[float],
    ) -> None:
        """Store document embedding and metadata in Aurora documents table."""
        with self._aurora.cursor() as cur:
            # Ensure new columns exist (safe for repeated runs)
            for col_def in [
                "page_count INTEGER DEFAULT 0",
                "file_size_bytes BIGINT DEFAULT 0",
                "document_type TEXT DEFAULT 'miscellaneous'",
            ]:
                col_name = col_def.split()[0]
                cur.execute(
                    f"ALTER TABLE documents ADD COLUMN IF NOT EXISTS {col_def}"
                )

            cur.execute(
                """
                INSERT INTO documents
                    (document_id, case_file_id, source_filename,
                     source_metadata, raw_text, sections, embedding,
                     page_count, file_size_bytes, document_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    raw_text = EXCLUDED.raw_text,
                    sections = EXCLUDED.sections,
                    page_count = EXCLUDED.page_count,
                    file_size_bytes = EXCLUDED.file_size_bytes,
                    document_type = EXCLUDED.document_type
                """,
                (
                    document_id,
                    case_file_id,
                    parsed.source_metadata.get("filename", ""),
                    json.dumps(parsed.source_metadata),
                    parsed.raw_text,
                    json.dumps(parsed.sections),
                    str(embedding),
                    getattr(parsed, "page_count", 0),
                    getattr(parsed, "file_size_bytes", 0),
                    str(getattr(self._extractor, "_last_document_type", "miscellaneous")),
                ),
            )

    def _update_case_statistics(
        self,
        case_id: str,
        document_count: int,
        entity_count: int,
        relationship_count: int,
    ) -> None:
        """Update case file statistics in Aurora."""
        with self._aurora.cursor() as cur:
            cur.execute(
                """
                UPDATE case_files
                SET document_count = %s,
                    entity_count = %s,
                    relationship_count = %s
                WHERE case_id = %s
                """,
                (document_count, entity_count, relationship_count, case_id),
            )
