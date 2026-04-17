"""Lead Ingestion Service — orchestrates lead-to-investigation flow.

Validates incoming lead JSON, creates Matter/Collection in Aurora,
seeds Neptune with subjects and connections, runs AI research,
and triggers the existing Step Functions pipeline.

All changes EXTEND existing services — nothing is replaced.
"""

import json
import logging
import os
import re
import ssl
import urllib.request
import uuid
import time
from datetime import datetime, timezone
from typing import Optional

from db.connection import ConnectionManager
from models.lead import LeadJSON
from services.collection_service import CollectionService
from services.matter_service import MatterService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")
S3_BUCKET = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", ""))


def _slug(name: str) -> str:
    """Convert a name to a filesystem-safe slug."""
    s = name.lower().strip().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", s) or "unknown"


def _gremlin_http(query: str) -> dict:
    """Execute a Gremlin query via Neptune HTTP API (not WebSocket)."""
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _escape(s: str) -> str:
    """Escape a string for Gremlin query injection."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


class ConflictError(Exception):
    """Raised when a duplicate lead_id is detected."""

    def __init__(self, message: str, matter_id: str):
        super().__init__(message)
        self.matter_id = matter_id


class LeadIngestionService:
    """Orchestrates the full lead-to-investigation flow."""

    def __init__(
        self,
        connection_manager: ConnectionManager,
        matter_service: MatterService,
        collection_service: CollectionService,
    ) -> None:
        self._db = connection_manager
        self._matter_svc = matter_service
        self._collection_svc = collection_service

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_lead_json(self, payload: dict) -> list[str]:
        """Validate lead JSON against schema. Returns list of error messages."""
        try:
            LeadJSON(**payload)
            return []
        except Exception as exc:
            return [str(exc)]

    def check_duplicate(self, lead_id: str) -> Optional[str]:
        """Check if lead_id already ingested. Returns matter_id or None."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT matter_id FROM matters WHERE lead_id = %s",
                (lead_id,),
            )
            row = cur.fetchone()
        return str(row[0]) if row else None

    # ------------------------------------------------------------------
    # Matter/Collection creation
    # ------------------------------------------------------------------

    def create_matter_from_lead(self, lead: LeadJSON, org_id: str) -> tuple:
        """Create Matter + Collection from validated lead. Returns (matter, collection)."""
        matter = self._matter_svc.create_matter(
            org_id=org_id,
            matter_name=lead.title,
            description=lead.summary,
            matter_type="lead_investigation",
        )

        collection = self._collection_svc.create_collection(
            matter_id=matter.matter_id,
            org_id=org_id,
            collection_name=f"Lead: {lead.lead_id}",
            source_description=f"{lead.source_app} | {lead.classification} | {lead.subcategory}",
        )

        # Store lead.json in S3
        self._store_lead_json(collection.s3_prefix, lead)

        # Set lead-specific columns on matter row
        metadata = lead.lead_metadata_subset()
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE matters
                SET lead_metadata = %s, lead_status = 'accepted', lead_id = %s
                WHERE matter_id = %s
                """,
                (json.dumps(metadata), lead.lead_id, matter.matter_id),
            )

        return matter, collection

    def _store_lead_json(self, s3_prefix: str, lead: LeadJSON) -> None:
        """Store the full lead JSON in S3."""
        import boto3

        s3 = boto3.client("s3")
        key = f"{s3_prefix}lead_data/lead.json"
        body = lead.model_dump_json(indent=2, by_alias=True)
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=body, ContentType="application/json")
        logger.info("Stored lead JSON at s3://%s/%s", S3_BUCKET, key)

    # ------------------------------------------------------------------
    # Status tracking
    # ------------------------------------------------------------------

    def update_lead_status(
        self, matter_id: str, status: str, error_details: Optional[str] = None,
    ) -> None:
        """Update lead_status and last_activity on the matter row."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE matters
                SET lead_status = %s, error_details = %s, last_activity = NOW()
                WHERE matter_id = %s
                """,
                (status, error_details, matter_id),
            )

    def get_lead_status(self, lead_id: str) -> Optional[dict]:
        """Query matter by lead_id, return processing status summary."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT matter_id, matter_name, lead_status, lead_metadata,
                       total_documents, total_entities, total_relationships,
                       error_details, last_activity
                FROM matters WHERE lead_id = %s
                """,
                (lead_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "matter_id": str(row[0]),
            "matter_name": row[1],
            "lead_status": row[2],
            "lead_metadata": row[3],
            "total_documents": row[4] or 0,
            "total_entities": row[5] or 0,
            "total_relationships": row[6] or 0,
            "error_details": row[7],
            "last_activity": str(row[8]) if row[8] else None,
        }

    def get_lead_metadata(self, matter_id: str) -> Optional[dict]:
        """Return the lead_metadata JSONB from the matter row."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT lead_metadata FROM matters WHERE matter_id = %s",
                (matter_id,),
            )
            row = cur.fetchone()
        if not row or not row[0]:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])


    # ------------------------------------------------------------------
    # Neptune graph seeding
    # ------------------------------------------------------------------

    def seed_neptune_graph(self, matter_id: str, neptune_label: str, lead: LeadJSON) -> dict:
        """Create Neptune nodes for subjects and edges for connections.

        Returns: {subjects_seeded, connections_seeded, failures}
        """
        seeded = 0
        conn_seeded = 0
        failures = 0

        for subj in lead.subjects:
            try:
                props = (
                    f".property('canonical_name','{_escape(subj.name)}')"
                    f".property('entity_type','{_escape(subj.type)}')"
                    f".property('confidence',1.0)"
                    f".property('occurrence_count',1)"
                    f".property('case_file_id','{_escape(matter_id)}')"
                )
                for alias in subj.aliases:
                    props += f".property(list,'aliases','{_escape(alias)}')"
                for k, v in subj.identifiers.items():
                    props += f".property('id_{_escape(k)}','{_escape(v)}')"

                q = f"g.addV('{_escape(neptune_label)}'){props}"
                _gremlin_http(q)
                seeded += 1
            except Exception as exc:
                logger.error("Failed to seed subject '%s': %s", subj.name, str(exc)[:200])
                failures += 1

        for conn in lead.connections:
            try:
                q = (
                    f"g.V().hasLabel('{_escape(neptune_label)}')"
                    f".has('canonical_name','{_escape(conn.from_subject)}')"
                    f".addE('RELATED_TO')"
                    f".to(g.V().hasLabel('{_escape(neptune_label)}')"
                    f".has('canonical_name','{_escape(conn.to_subject)}'))"
                    f".property('relationship_type','{_escape(conn.relationship)}')"
                    f".property('confidence',{conn.confidence})"
                    f".property('source_document_ref','lead:{_escape(lead.lead_id)}')"
                )
                _gremlin_http(q)
                conn_seeded += 1
            except Exception as exc:
                logger.error("Failed to seed connection '%s'->'%s': %s",
                             conn.from_subject, conn.to_subject, str(exc)[:200])
                failures += 1

        logger.info("Neptune seeding: %d subjects, %d connections, %d failures",
                     seeded, conn_seeded, failures)
        return {"subjects_seeded": seeded, "connections_seeded": conn_seeded, "failures": failures}

    # ------------------------------------------------------------------
    # Research + Pipeline
    # ------------------------------------------------------------------

    def run_research_and_pipeline(
        self, matter_id: str, collection_id: str, s3_prefix: str,
        lead: LeadJSON, neptune_label: str,
    ) -> dict:
        """Run AI research for all subjects, store docs, trigger pipeline."""
        from services.ai_research_agent import AIResearchAgent

        agent = AIResearchAgent()
        subjects_dicts = [s.model_dump() for s in lead.subjects]
        hints_dicts = [h.model_dump() for h in lead.evidence_hints]

        results = agent.research_all_subjects(
            subjects_dicts, lead.osint_directives, hints_dicts
        )

        # Store research docs in S3 and register in Aurora
        import boto3
        s3 = boto3.client("s3")
        doc_ids = []

        for r in results:
            if not r["success"] or not r["research_text"]:
                continue
            slug = r["slug"]
            filename = f"research/{slug}.txt"
            s3_key = f"{s3_prefix}{filename}"

            # Store in S3
            s3.put_object(
                Bucket=S3_BUCKET, Key=s3_key,
                Body=r["research_text"].encode("utf-8"),
                ContentType="text/plain",
            )

            # Register in Aurora documents table
            doc_id = str(uuid.uuid4())
            with self._db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (document_id, case_file_id, source_filename, source_metadata, raw_text)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        doc_id, matter_id, filename,
                        json.dumps({
                            "source": "ai_research_agent",
                            "subject": r["subject_name"],
                            "lead_id": lead.lead_id,
                        }),
                        r["research_text"],
                    ),
                )
            doc_ids.append(doc_id)

        logger.info("Stored %d research documents for matter %s", len(doc_ids), matter_id)

        # Trigger Step Functions pipeline if we have docs
        if doc_ids:
            self.update_lead_status(matter_id, "pipeline_running")
            self._trigger_pipeline(matter_id, doc_ids)
        else:
            self.update_lead_status(matter_id, "indexed")

        return {"documents_stored": len(doc_ids), "document_ids": doc_ids}

    def _trigger_pipeline(self, matter_id: str, doc_ids: list[str]) -> None:
        """Trigger the existing Step Functions pipeline."""
        import boto3

        sfn_arn = os.environ.get("STATE_MACHINE_ARN", "")
        if not sfn_arn:
            logger.warning("STATE_MACHINE_ARN not set — skipping pipeline trigger")
            return

        sfn = boto3.client("stepfunctions")
        sfn.start_execution(
            stateMachineArn=sfn_arn,
            name=f"lead-{matter_id[:8]}-{int(time.time())}",
            input=json.dumps({
                "case_id": matter_id,
                "upload_result": {
                    "document_ids": doc_ids,
                    "document_count": len(doc_ids),
                },
            }),
        )
        logger.info("Triggered pipeline for matter %s with %d docs", matter_id, len(doc_ids))

    # ------------------------------------------------------------------
    # Full orchestration
    # ------------------------------------------------------------------

    def ingest_lead(self, payload: dict) -> dict:
        """Full orchestration: validate → create → seed → research → pipeline.

        Returns: {matter_id, collection_id, status, lead_id}
        """
        # 1. Validate
        errors = self.validate_lead_json(payload)
        if errors:
            raise ValueError("; ".join(errors))

        lead = LeadJSON(**payload)

        # 2. Check duplicate
        existing = self.check_duplicate(lead.lead_id)
        if existing:
            raise ConflictError(
                f"Lead '{lead.lead_id}' already ingested as matter {existing}",
                matter_id=existing,
            )

        # 3. Create Matter + Collection
        org_id = os.environ.get("DEFAULT_ORG_ID", "")
        if not org_id:
            # Fetch default org from DB
            with self._db.cursor() as cur:
                cur.execute("SELECT org_id FROM organizations LIMIT 1")
                row = cur.fetchone()
                org_id = str(row[0]) if row else ""
        if not org_id:
            raise RuntimeError("No organization found — run migration 006 first")

        matter, collection = self.create_matter_from_lead(lead, org_id)
        matter_id = matter.matter_id
        collection_id = collection.collection_id

        try:
            # 4. Seed Neptune graph
            self.update_lead_status(matter_id, "seeding_graph")
            seed_result = self.seed_neptune_graph(
                matter_id, matter.neptune_subgraph_label, lead
            )
            if seed_result["subjects_seeded"] == 0 and len(lead.subjects) > 0:
                self.update_lead_status(matter_id, "error", "All subjects failed Neptune seeding")
                return {
                    "matter_id": matter_id,
                    "collection_id": collection_id,
                    "status": "error",
                    "lead_id": lead.lead_id,
                    "seed_result": seed_result,
                }

            # 5. AI Research
            self.update_lead_status(matter_id, "researching")
            research_result = self.run_research_and_pipeline(
                matter_id, collection_id, collection.s3_prefix,
                lead, matter.neptune_subgraph_label,
            )

            # 6. Return processing status
            return {
                "matter_id": matter_id,
                "collection_id": collection_id,
                "status": "processing",
                "lead_id": lead.lead_id,
                "seed_result": seed_result,
                "research_result": research_result,
            }

        except Exception as exc:
            logger.exception("Lead ingestion failed for %s", lead.lead_id)
            self.update_lead_status(matter_id, "error", str(exc)[:500])
            raise
