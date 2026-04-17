"""Ingestion service v2 — collection-aware ingestion pipeline.

Extends IngestionService to create Collections on upload, write to the new
S3 hierarchy path (orgs/{org_id}/matters/{mid}/collections/{cid}/raw/),
and load entities into a staging subgraph (Entity_{collection_id}) instead
of directly into the Matter graph.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from db.neptune import collection_staging_label
from models.document import BatchResult, ExtractionResult
from models.entity import ExtractedEntity, ExtractedRelationship
from models.hierarchy import CollectionStatus
from services.collection_service import CollectionService
from services.entity_extraction_service import EntityExtractionService
from services.ingestion_service import BULK_LOAD_THRESHOLD, IngestionService
from storage.s3_helper import build_collection_key, PrefixType

logger = logging.getLogger(__name__)


class IngestionServiceV2(IngestionService):
    """Collection-aware ingestion pipeline.

    Overrides upload_documents and process_batch to work with the
    Organization > Matter > Collection > Document hierarchy.
    """

    def __init__(self, *args: Any, collection_service: CollectionService, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._collection_service = collection_service

    # ------------------------------------------------------------------
    # upload_documents (v2)
    # ------------------------------------------------------------------

    def upload_documents(
        self,
        matter_id: str,
        org_id: str,
        files: list[tuple[str, bytes]],
        collection_name: str = "",
        source_description: str = "",
    ) -> tuple[str, list[str]]:
        """Upload files into a new Collection under the new S3 hierarchy.

        Creates a Collection in staging status, uploads each file to
        ``orgs/{org_id}/matters/{matter_id}/collections/{collection_id}/raw/``,
        and inserts document rows with org_id, matter_id, collection_id.

        Args:
            matter_id: The matter identifier.
            org_id: The organization identifier.
            files: A list of ``(filename, content)`` tuples.
            collection_name: Human-readable name for the collection.
            source_description: Provenance description for the data load.

        Returns:
            A tuple of ``(collection_id, document_ids)``.
        """
        # Default collection name if not provided
        if not collection_name:
            collection_name = f"Upload {datetime.now(timezone.utc).isoformat()}"

        # Create collection in staging
        collection = self._collection_service.create_collection(
            matter_id=matter_id,
            org_id=org_id,
            collection_name=collection_name,
            source_description=source_description,
        )
        collection_id = collection.collection_id

        document_ids: list[str] = []
        for filename, content in files:
            document_id = str(uuid.uuid4())
            ext = filename.rsplit(".", 1)[-1] if "." in filename else "txt"
            s3_filename = f"{document_id}.{ext}"

            # Upload to new hierarchy path
            s3_key = build_collection_key(
                org_id, matter_id, collection_id, PrefixType.RAW, s3_filename,
            )
            self._upload_to_s3(s3_key, content)

            # Insert document row with org_id, matter_id, collection_id
            self._insert_document_row(
                document_id=document_id,
                org_id=org_id,
                matter_id=matter_id,
                collection_id=collection_id,
                source_filename=filename,
            )

            document_ids.append(document_id)

        return collection_id, document_ids

    # ------------------------------------------------------------------
    # process_batch (v2)
    # ------------------------------------------------------------------

    def process_batch(
        self,
        collection_id: str,
        document_ids: list[str],
    ) -> BatchResult:
        """Process documents into a staging subgraph for the collection.

        Loads entities into ``Entity_{collection_id}`` staging subgraph.
        On success, transitions the collection to qa_review.

        Args:
            collection_id: The collection identifier.
            document_ids: List of document IDs to process.

        Returns:
            A BatchResult summarising the batch run.
        """
        results: list[ExtractionResult] = []
        failures: list[dict] = []

        # Process each document individually
        for doc_id in document_ids:
            try:
                result = self._process_document_v2(collection_id, doc_id)
                results.append(result)
            except Exception as exc:
                logger.error(
                    "Processing failed for document_id=%s collection_id=%s: %s",
                    doc_id, collection_id, exc,
                )
                failures.append({"document_id": doc_id, "error": str(exc)})

        # Merge entities across documents
        all_entities: list[ExtractedEntity] = []
        all_relationships: list[ExtractedRelationship] = []
        for result in results:
            doc_entities = [ExtractedEntity(**e) for e in result.entities]
            doc_rels = [ExtractedRelationship(**r) for r in result.relationships]
            all_entities = EntityExtractionService.merge_entities(all_entities, doc_entities)
            all_relationships.extend(doc_rels)

        # Load into staging subgraph (Entity_{collection_id})
        if all_entities or all_relationships:
            staging_label = collection_staging_label(collection_id)
            self._graph_loader.load_via_gremlin(
                collection_id, all_entities, all_relationships,
            )

        # Transition collection to processing then qa_review on success
        try:
            # Get collection to find org_id
            collection = self._get_collection_for_transition(collection_id)
            org_id = collection.org_id

            self._collection_service.update_status(
                collection_id, org_id, CollectionStatus.PROCESSING,
            )
            self._collection_service.update_status(
                collection_id, org_id, CollectionStatus.QA_REVIEW,
            )
        except Exception as exc:
            logger.error(
                "Failed to transition collection %s to qa_review: %s",
                collection_id, exc,
            )

        return BatchResult(
            case_file_id=collection_id,
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

    def _upload_to_s3(self, s3_key: str, content: bytes | str) -> None:
        """Upload content to S3 using the pre-built key."""
        import boto3

        bucket = self._s3_bucket
        s3 = boto3.client("s3")
        if isinstance(content, str):
            content = content.encode("utf-8")
        s3.put_object(Bucket=bucket, Key=s3_key, Body=content)

    def _insert_document_row(
        self,
        document_id: str,
        org_id: str,
        matter_id: str,
        collection_id: str,
        source_filename: str,
    ) -> None:
        """Insert a document row with org_id, matter_id, collection_id."""
        with self._aurora.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents
                    (document_id, case_file_id, source_filename,
                     org_id, matter_id, collection_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id) DO UPDATE SET
                    org_id = EXCLUDED.org_id,
                    matter_id = EXCLUDED.matter_id,
                    collection_id = EXCLUDED.collection_id
                """,
                (document_id, matter_id, source_filename,
                 org_id, matter_id, collection_id),
            )

    def _process_document_v2(
        self,
        collection_id: str,
        document_id: str,
    ) -> ExtractionResult:
        """Process a single document for the v2 pipeline.

        Downloads the raw file, parses it, extracts entities and relationships,
        generates an embedding, and stores the extraction artifact.
        """
        # Reuse parent's process_document logic with collection_id as the scope
        return self.process_document(collection_id, document_id)

    def _get_collection_for_transition(self, collection_id: str):
        """Retrieve collection to get org_id for status transitions.

        Tries all orgs — in practice the caller should know the org_id,
        but for the batch pipeline we look it up from the DB.
        """
        with self._aurora.cursor() as cur:
            cur.execute(
                "SELECT org_id FROM collections WHERE collection_id = %s",
                (collection_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise KeyError(f"Collection not found: {collection_id}")

        from models.hierarchy import Collection

        org_id = str(row[0])
        return self._collection_service.get_collection(collection_id, org_id)
