"""Document Classification Service — classifies documents and routes them to cases.

Supports three routing modes:
- folder_based: Extract case from S3 folder structure (cases/{case_id}/raw/file.pdf)
- metadata_routing: Apply regex patterns to filenames, PDF metadata, and first page text
- ai_classification: Use Bedrock Haiku to classify documents against existing cases

Requirements: 23.1, 23.2, 23.3, 23.4, 23.5, 23.6
"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from db.connection import ConnectionManager
from models.pipeline_config import ClassificationResult, RoutingOutcome


class DocumentClassificationService:
    """Classifies documents and routes them to cases."""

    def __init__(
        self,
        aurora_cm: ConnectionManager,
        bedrock_client: Any = None,
        s3_client: Any = None,
    ) -> None:
        self._db = aurora_cm
        self._bedrock = bedrock_client
        self._s3 = s3_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self,
        document_id: str,
        parsed_text: str,
        source_metadata: dict,
        config: dict,
    ) -> ClassificationResult:
        """Classify a single document based on routing_mode in config."""
        mode = config.get("routing_mode", "folder_based")
        if mode == "folder_based":
            return self._classify_folder_based(document_id, source_metadata)
        elif mode == "metadata_routing":
            return self._classify_metadata(
                document_id, parsed_text, source_metadata, config
            )
        elif mode == "ai_classification":
            return self._classify_ai(
                document_id, parsed_text, source_metadata, config
            )
        else:
            raise ValueError(f"Unknown routing_mode: {mode}")

    def route_document(
        self,
        document_id: str,
        result: ClassificationResult,
        config: Optional[dict] = None,
    ) -> RoutingOutcome:
        """Route document based on classification result.

        If matched_case_id and confidence > threshold → assign to case.
        Otherwise → add to triage queue.
        """
        threshold = config.get("confidence_threshold", 0.8) if config else 0.8
        if result.matched_case_id and result.confidence > threshold:
            self._assign_to_case(document_id, result.matched_case_id)
            return RoutingOutcome(
                action="assigned", case_id=result.matched_case_id
            )
        else:
            self._add_to_triage(document_id, result)
            return RoutingOutcome(
                action="triage",
                triage_reason=result.routing_reason or "Below confidence threshold",
            )

    def get_triage_queue(
        self, limit: int = 50, offset: int = 0, status: str = "pending"
    ) -> list[dict]:
        """List documents in the triage queue with pagination."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT triage_id, document_id, filename, s3_key,
                       classification_json, suggested_case_id, confidence,
                       status, assigned_case_id, assigned_by, assigned_at,
                       created_at
                FROM triage_queue
                WHERE status = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (status, limit, offset),
            )
            rows = cur.fetchall()

        return [
            {
                "triage_id": str(row[0]),
                "document_id": row[1],
                "filename": row[2],
                "s3_key": row[3],
                "classification_json": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}"),
                "suggested_case_id": str(row[5]) if row[5] else None,
                "confidence": row[6],
                "status": row[7],
                "assigned_case_id": str(row[8]) if row[8] else None,
                "assigned_by": row[9],
                "assigned_at": row[10].isoformat() if row[10] else None,
                "created_at": row[11].isoformat() if row[11] else None,
            }
            for row in rows
        ]

    def assign_from_triage(
        self, document_id: str, case_id: str, assigned_by: str
    ) -> dict:
        """Manually assign a triaged document to an existing case."""
        now = datetime.now(timezone.utc)
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE triage_queue
                SET status = 'assigned',
                    assigned_case_id = %s,
                    assigned_by = %s,
                    assigned_at = %s
                WHERE document_id = %s AND status = 'pending'
                RETURNING triage_id
                """,
                (case_id, assigned_by, now, document_id),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(
                    f"No pending triage item found for document: {document_id}"
                )

        self._assign_to_case(document_id, case_id)
        return {
            "triage_id": str(row[0]),
            "document_id": document_id,
            "case_id": case_id,
            "assigned_by": assigned_by,
            "assigned_at": now.isoformat(),
            "status": "assigned",
        }

    def create_case_from_triage(
        self, document_id: str, case_name: str, created_by: str
    ) -> dict:
        """Create a new case and assign the triaged document to it."""
        case_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        with self._db.cursor() as cur:
            # Create new case_files row
            cur.execute(
                """
                INSERT INTO case_files
                    (case_id, topic_name, description, status, created_at, last_activity)
                VALUES (%s, %s, %s, 'created', %s, %s)
                """,
                (case_id, case_name, f"Auto-created from triage for {document_id}", now, now),
            )
            # Update triage queue
            cur.execute(
                """
                UPDATE triage_queue
                SET status = 'new_case',
                    assigned_case_id = %s,
                    assigned_by = %s,
                    assigned_at = %s
                WHERE document_id = %s AND status = 'pending'
                RETURNING triage_id
                """,
                (case_id, created_by, now, document_id),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(
                    f"No pending triage item found for document: {document_id}"
                )

        self._assign_to_case(document_id, case_id)
        return {
            "triage_id": str(row[0]),
            "document_id": document_id,
            "case_id": case_id,
            "case_name": case_name,
            "created_by": created_by,
            "created_at": now.isoformat(),
            "status": "new_case",
        }

    # ------------------------------------------------------------------
    # Classification strategies
    # ------------------------------------------------------------------

    def _classify_folder_based(
        self, document_id: str, source_metadata: dict
    ) -> ClassificationResult:
        """Extract case_id from S3 key pattern: cases/{case_id}/raw/filename."""
        s3_key = source_metadata.get("s3_key", "")
        match = re.match(r"cases/([^/]+)/raw/.+", s3_key)
        if match:
            case_id = match.group(1)
            return ClassificationResult(
                document_id=document_id,
                matched_case_id=case_id,
                confidence=1.0,
                routing_reason="Matched from S3 folder structure",
                routing_mode="folder_based",
            )
        return ClassificationResult(
            document_id=document_id,
            confidence=0.0,
            routing_reason="S3 key does not match cases/{case_id}/raw/ pattern",
            routing_mode="folder_based",
        )

    def _classify_metadata(
        self,
        document_id: str,
        parsed_text: str,
        source_metadata: dict,
        config: dict,
    ) -> ClassificationResult:
        """Apply case_number_pattern regex to filename → PDF metadata → first page text.

        First match wins. Look up case in Aurora by case_number.
        """
        pattern = config.get("case_number_pattern", r"\d{4}-[A-Z]{2}-\d{5}")
        try:
            regex = re.compile(pattern)
        except re.error:
            return ClassificationResult(
                document_id=document_id,
                confidence=0.0,
                routing_reason=f"Invalid regex pattern: {pattern}",
                routing_mode="metadata_routing",
            )

        # 1) Scan filename
        filename = source_metadata.get("filename", "")
        match = regex.search(filename)

        # 2) Scan PDF metadata fields
        if not match:
            for field in ("author", "subject", "keywords"):
                value = source_metadata.get(field, "")
                if value:
                    match = regex.search(str(value))
                    if match:
                        break

        # 3) Scan first page text
        if not match and parsed_text:
            first_page = parsed_text[:5000]
            match = regex.search(first_page)

        if not match:
            return ClassificationResult(
                document_id=document_id,
                confidence=0.0,
                routing_reason="No case number found in filename, metadata, or text",
                routing_mode="metadata_routing",
            )

        case_number = match.group(0)
        # Look up case in Aurora by case_number (topic_name contains case number)
        case_row = self._lookup_case_by_number(case_number)
        if case_row:
            return ClassificationResult(
                document_id=document_id,
                matched_case_id=case_row["case_id"],
                case_number=case_number,
                confidence=0.95,
                routing_reason=f"Case number {case_number} matched via metadata",
                routing_mode="metadata_routing",
            )
        return ClassificationResult(
            document_id=document_id,
            case_number=case_number,
            confidence=0.5,
            routing_reason=f"Case number {case_number} found but no matching case in database",
            routing_mode="metadata_routing",
        )

    def _classify_ai(
        self,
        document_id: str,
        parsed_text: str,
        source_metadata: dict,
        config: dict,
    ) -> ClassificationResult:
        """Use Bedrock Haiku to classify document against existing cases."""
        max_chars = config.get("max_preview_chars", 5000)
        text_preview = parsed_text[:max_chars] if parsed_text else ""

        existing_cases = self._fetch_existing_cases()
        prompt = self._build_classification_prompt(
            text_preview, existing_cases, source_metadata
        )
        response = self._invoke_bedrock(prompt, config)

        # Parse AI response
        case_number = response.get("case_number")
        case_category = response.get("case_category", "unknown")
        confidence = float(response.get("confidence", 0.0))
        routing_reason = response.get("routing_reason", "AI classification")

        # Clamp confidence to [0.0, 1.0]
        confidence = max(0.0, min(1.0, confidence))

        # Match to existing case by case_number or topic_name similarity
        matched_case_id = None
        if case_number and existing_cases:
            for case in existing_cases:
                if case.get("case_number") == case_number:
                    matched_case_id = case["case_id"]
                    break
            # Fallback: match by topic_name similarity
            if not matched_case_id and case_category:
                for case in existing_cases:
                    topic = case.get("topic_name", "").lower()
                    if case_category.lower() in topic or topic in case_category.lower():
                        matched_case_id = case["case_id"]
                        break

        return ClassificationResult(
            document_id=document_id,
            matched_case_id=matched_case_id,
            case_number=case_number,
            case_category=case_category,
            confidence=confidence,
            routing_reason=routing_reason,
            routing_mode="ai_classification",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_existing_cases(self) -> list[dict]:
        """Query Aurora for existing non-archived cases."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT case_id, topic_name, case_id AS case_number
                FROM case_files
                WHERE status != 'archived'
                ORDER BY last_activity DESC
                """
            )
            rows = cur.fetchall()

        return [
            {
                "case_id": str(row[0]),
                "topic_name": row[1],
                "case_number": str(row[2]),
            }
            for row in rows
        ]

    def _build_classification_prompt(
        self,
        text_preview: str,
        existing_cases: list[dict],
        metadata: dict,
    ) -> str:
        """Build a prompt for Bedrock that includes document text, case list, and metadata."""
        case_list = "\n".join(
            f"- Case ID: {c['case_id']}, Name: {c['topic_name']}"
            for c in existing_cases
        ) or "No existing cases."

        filename = metadata.get("filename", "unknown")

        return (
            "You are a document classification assistant for a legal investigation platform.\n"
            "Analyze the following document and determine which existing case it belongs to.\n\n"
            f"Document filename: {filename}\n"
            f"Document preview:\n{text_preview}\n\n"
            f"Existing cases:\n{case_list}\n\n"
            "Respond with a JSON object containing:\n"
            '- "case_number": the case number if found in the document (string or null)\n'
            '- "case_category": the type of case (e.g., "antitrust", "criminal", "financial")\n'
            '- "confidence": your confidence in the classification (0.0 to 1.0)\n'
            '- "routing_reason": a brief explanation of why you classified it this way\n\n'
            "Respond ONLY with the JSON object, no other text."
        )

    def _invoke_bedrock(self, prompt: str, config: dict) -> dict:
        """Call Bedrock with the classification prompt and parse the response."""
        model_id = config.get(
            "ai_model_id", "anthropic.claude-3-haiku-20240307-v1:0"
        )
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            }
        )

        response = self._bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [{}])
        text = content[0].get("text", "{}") if content else "{}"

        # Parse JSON from response, handling potential markdown code blocks
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "case_number": None,
                "case_category": "unknown",
                "confidence": 0.0,
                "routing_reason": "Failed to parse AI response",
            }

    def _lookup_case_by_number(self, case_number: str) -> Optional[dict]:
        """Look up a case in Aurora by case number in topic_name."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT case_id, topic_name
                FROM case_files
                WHERE topic_name ILIKE %s AND status != 'archived'
                LIMIT 1
                """,
                (f"%{case_number}%",),
            )
            row = cur.fetchone()

        if row:
            return {"case_id": str(row[0]), "topic_name": row[1]}
        return None

    def _assign_to_case(self, document_id: str, case_id: str) -> None:
        """Update document record in Aurora to associate with case_id."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET case_id = %s
                WHERE document_id = %s
                """,
                (case_id, document_id),
            )

    def _add_to_triage(self, document_id: str, result: ClassificationResult) -> None:
        """Insert into triage_queue table with classification metadata."""
        triage_id = str(uuid.uuid4())
        classification_json = {
            "case_number": result.case_number,
            "case_category": result.case_category,
            "confidence": result.confidence,
            "routing_reason": result.routing_reason,
            "routing_mode": result.routing_mode,
        }
        # Extract filename from routing_reason or use document_id as fallback
        filename = result.document_id

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO triage_queue
                    (triage_id, document_id, filename, classification_json,
                     suggested_case_id, confidence, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
                """,
                (
                    triage_id,
                    document_id,
                    filename,
                    json.dumps(classification_json),
                    result.matched_case_id,
                    result.confidence,
                    datetime.now(timezone.utc),
                ),
            )

