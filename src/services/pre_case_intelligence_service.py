"""Pre-Case Intelligence Service - Orchestrator for the antitrust pre-case workflow.

Coordinates the complete pre-case lifecycle from lead intake through formal case
opening. Delegates to specialized services for classification, OSINT gathering,
prosecution readiness assessment, and continuous monitoring.

No bulk processing (100+ items), no EC2 launches, no direct Bedrock calls.
All AI calls are delegated to CaseTypeClassifier and ProsecutionReadinessAssessment.

Follows Protocol/constructor-injection pattern for testability.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Valid workflow transitions
VALID_TRANSITIONS = {
    "intake": ["classifying", "closed"],
    "classifying": ["gathering", "closed"],
    "gathering": ["assessing", "closed"],
    "assessing": ["monitoring", "closed"],
    "monitoring": ["promoted", "closed"],
}


class PreCaseIntelligenceService:
    """Orchestrates the antitrust pre-case intelligence workflow.

    Coordinates lead submission, classification, OSINT gathering, prosecution
    readiness assessment, and promotion to formal investigation.
    """

    def __init__(
        self,
        aurora_cm: Any,
        redshift_client: Any,
        neptune_endpoint: str,
        neptune_port: str = "8182",
        bedrock_client: Any = None,
        case_type_classifier: Any = None,
        osint_gatherer: Any = None,
        prosecution_assessment: Any = None,
        pre_case_trawler: Any = None,
        decision_workflow_svc: Any = None,
        bulk_ingestion_svc: Any = None,
        cross_case_detector: Any = None,
    ) -> None:
        self.aurora_cm = aurora_cm
        self.redshift_client = redshift_client
        self.neptune_endpoint = neptune_endpoint
        self.neptune_port = neptune_port
        self.bedrock_client = bedrock_client
        self.case_type_classifier = case_type_classifier
        self.osint_gatherer = osint_gatherer
        self.prosecution_assessment = prosecution_assessment
        self.pre_case_trawler = pre_case_trawler
        self.decision_workflow_svc = decision_workflow_svc
        self.bulk_ingestion_svc = bulk_ingestion_svc
        self.cross_case_detector = cross_case_detector

    # ------------------------------------------------------------------
    # Lead Submission
    # ------------------------------------------------------------------

    def submit_lead(self, lead_data: dict) -> dict:
        """Create a new pre-case lead record and trigger classification.

        Args:
            lead_data: Dict with title, summary, source_type, source_content,
                       and optional priority, assigned_analyst fields.

        Returns:
            Dict with lead_id, status, and classification_triggered flag.
        """
        lead_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        title = lead_data.get("title", "Untitled Lead")
        summary = lead_data.get("summary", "")
        source_type = lead_data.get("source_type", "tip")
        source_content = lead_data.get("source_content", lead_data)
        priority = lead_data.get("priority", "medium")
        assigned_analyst = lead_data.get("assigned_analyst")

        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pre_case_leads
                        (lead_id, title, summary, source_type, source_content,
                         status, priority, assigned_analyst, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        lead_id, title, summary, source_type,
                        json.dumps(source_content) if isinstance(source_content, dict) else source_content,
                        "intake", priority, assigned_analyst, now, now,
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to create lead: {e}")
            raise

        self._create_audit_record(
            lead_id=lead_id,
            action_type="lead_submitted",
            actor=assigned_analyst or "system",
            action_detail={"title": title, "source_type": source_type, "priority": priority},
            previous_state=None,
        )

        # Trigger classification
        classification_triggered = False
        try:
            self._transition_status(lead_id, "intake", "classifying")
            if self.case_type_classifier:
                content = json.dumps(source_content) if isinstance(source_content, dict) else str(source_content)
                self.case_type_classifier.classify(content)
                classification_triggered = True
        except Exception as e:
            logger.warning(f"Auto-classification failed for {lead_id}: {e}")

        return {
            "lead_id": lead_id,
            "status": "classifying" if classification_triggered else "intake",
            "classification_triggered": classification_triggered,
            "created_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify_lead(self, lead_id: str, additional_context: str = "") -> dict:
        """Classify or reclassify a lead by delegating to CaseTypeClassifier.

        Args:
            lead_id: UUID of the lead.
            additional_context: Optional additional evidence for reclassification.

        Returns:
            Dict with classification result details.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise KeyError(f"Lead {lead_id} not found")

        previous_state = {"status": lead["status"], "case_type": lead.get("case_type")}

        # Ensure valid transition
        if lead["status"] not in ("intake", "classifying"):
            self._transition_status(lead_id, lead["status"], "classifying")

        if additional_context:
            result = self.case_type_classifier.reclassify(lead_id, additional_context)
        else:
            content = lead.get("source_content", "")
            if isinstance(content, dict):
                content = json.dumps(content)
            result = self.case_type_classifier.classify(str(content))

        # Update lead with classification result
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pre_case_leads
                    SET case_type = %s, classification_confidence = %s,
                        status = 'classifying', updated_at = %s
                    WHERE lead_id = %s
                    """,
                    (result.case_type, result.confidence, datetime.now(timezone.utc), lead_id),
                )
        except Exception as e:
            logger.error(f"Failed to update lead classification: {e}")

        self._create_audit_record(
            lead_id=lead_id,
            action_type="lead_classified",
            actor="system",
            action_detail={
                "case_type": result.case_type,
                "confidence": result.confidence,
                "manual_review": result.manual_review,
                "classification_id": result.classification_id,
            },
            previous_state=previous_state,
        )

        return {
            "lead_id": lead_id,
            "case_type": result.case_type,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "alternatives": result.alternatives,
            "manual_review": result.manual_review,
            "classification_id": result.classification_id,
        }

    # ------------------------------------------------------------------
    # OSINT Gathering
    # ------------------------------------------------------------------

    def gather_osint(self, lead_id: str, sources: list = None, subjects: list = None) -> dict:
        """Gather OSINT data for a lead by delegating to OsintDataGatherer.

        Args:
            lead_id: UUID of the lead.
            sources: Optional list of specific sources to query.
            subjects: Optional list of subjects to focus on.

        Returns:
            Dict with gathering results summary.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise KeyError(f"Lead {lead_id} not found")

        previous_state = {"status": lead["status"]}

        # Transition to gathering if not already
        if lead["status"] == "classifying":
            self._transition_status(lead_id, "classifying", "gathering")

        case_type = lead.get("case_type", "procurement_collusion")

        # Extract subjects from lead content if not provided
        if not subjects:
            content = lead.get("source_content", {})
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    content = {}
            subjects = content.get("subjects", [])
            if not subjects:
                subjects = [lead.get("title", "")]

        result = self.osint_gatherer.gather(
            lead_id=lead_id,
            case_type=case_type,
            subjects=subjects,
            sources=sources,
        )

        self._create_audit_record(
            lead_id=lead_id,
            action_type="osint_gathered",
            actor="system",
            action_detail={
                "sources_queried": result.sources_queried if hasattr(result, "sources_queried") else [],
                "records_found": result.total_records if hasattr(result, "total_records") else 0,
                "sources_failed": result.sources_failed if hasattr(result, "sources_failed") else [],
            },
            previous_state=previous_state,
        )

        # Return result as dict
        if hasattr(result, "__dict__"):
            return {
                "lead_id": lead_id,
                "status": "gathering",
                "sources_queried": getattr(result, "sources_queried", []),
                "total_records": getattr(result, "total_records", 0),
                "sources_failed": getattr(result, "sources_failed", []),
                "evidence_gaps": getattr(result, "evidence_gaps", []),
            }
        return {"lead_id": lead_id, "status": "gathering", "result": str(result)}

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def assess_lead(self, lead_id: str) -> dict:
        """Assess prosecution readiness by delegating to ProsecutionReadinessAssessment.

        Args:
            lead_id: UUID of the lead.

        Returns:
            Dict with assessment score, recommendation, and evidence gaps.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise KeyError(f"Lead {lead_id} not found")

        previous_state = {"status": lead["status"], "score": lead.get("pre_assessment_score")}

        # Transition to assessing
        if lead["status"] == "gathering":
            self._transition_status(lead_id, "gathering", "assessing")

        case_type = lead.get("case_type", "procurement_collusion")

        # Gather evidence from OSINT data
        evidence = self._get_lead_evidence(lead_id)

        result = self.prosecution_assessment.assess(
            lead_id=lead_id,
            evidence=evidence,
            case_type=case_type,
        )

        # Update lead score
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pre_case_leads
                    SET pre_assessment_score = %s, status = 'assessing', updated_at = %s
                    WHERE lead_id = %s
                    """,
                    (result.score, datetime.now(timezone.utc), lead_id),
                )
        except Exception as e:
            logger.error(f"Failed to update lead score: {e}")

        self._create_audit_record(
            lead_id=lead_id,
            action_type="lead_assessed",
            actor="system",
            action_detail={
                "score": result.score,
                "recommendation": result.recommendation,
                "assessment_id": result.assessment_id if hasattr(result, "assessment_id") else None,
            },
            previous_state=previous_state,
        )

        return {
            "lead_id": lead_id,
            "score": result.score,
            "recommendation": result.recommendation,
            "evidence_matrix": result.evidence_matrix if hasattr(result, "evidence_matrix") else {},
            "evidence_gaps": result.evidence_gaps if hasattr(result, "evidence_gaps") else [],
            "legal_reasoning": result.legal_reasoning if hasattr(result, "legal_reasoning") else "",
            "scoring_framework": result.scoring_framework if hasattr(result, "scoring_framework") else "",
        }

    # ------------------------------------------------------------------
    # Promote to Investigation
    # ------------------------------------------------------------------

    def promote_to_investigation(self, lead_id: str, prosecutor_id: str) -> dict:
        """Promote a pre-case lead to a formal investigation.

        Creates a formal investigation case and transfers all gathered data.
        Requires the lead to be in 'monitoring' status.

        Args:
            lead_id: UUID of the lead to promote.
            prosecutor_id: ID of the prosecutor approving promotion.

        Returns:
            Dict with case_id and promotion details.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise KeyError(f"Lead {lead_id} not found")

        if lead["status"] != "monitoring":
            raise ValueError(
                f"Cannot promote lead in status '{lead['status']}'. "
                f"Lead must be in 'monitoring' status."
            )

        previous_state = {"status": lead["status"], "score": lead.get("pre_assessment_score")}

        # Create formal investigation case
        case_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pre_case_leads
                    SET status = 'promoted', promoted_case_id = %s, updated_at = %s
                    WHERE lead_id = %s
                    """,
                    (case_id, now, lead_id),
                )
        except Exception as e:
            logger.error(f"Failed to promote lead {lead_id}: {e}")
            raise

        # Transfer monitoring to case-level trawler
        if self.pre_case_trawler:
            try:
                self.pre_case_trawler.transfer_to_case_trawler(lead_id, case_id)
            except Exception as e:
                logger.warning(f"Failed to transfer trawler config: {e}")

        self._create_audit_record(
            lead_id=lead_id,
            action_type="lead_promoted",
            actor=prosecutor_id,
            action_detail={
                "case_id": case_id,
                "prosecutor_id": prosecutor_id,
                "pre_assessment_score": lead.get("pre_assessment_score"),
            },
            previous_state=previous_state,
        )

        return {
            "lead_id": lead_id,
            "case_id": case_id,
            "status": "promoted",
            "promoted_by": prosecutor_id,
            "promoted_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # Lead Detail
    # ------------------------------------------------------------------

    def get_lead_detail(self, lead_id: str) -> dict:
        """Return complete lead detail with classification, OSINT, assessment, alerts, brief.

        Args:
            lead_id: UUID of the lead.

        Returns:
            Dict with full lead information including cached brief.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise KeyError(f"Lead {lead_id} not found")

        # Get classification history
        classifications = self._get_classifications(lead_id)

        # Get OSINT data summary
        osint_data = self._get_osint_summary(lead_id)

        # Get assessments
        assessments = self._get_assessments(lead_id)

        # Get audit trail
        audit_trail = self._get_audit_trail(lead_id)

        # Get alerts (from trawler)
        alerts = self._get_alerts(lead_id)

        # Get cached brief (auto-generated by pipeline)
        brief = self.get_cached_brief(lead_id)

        return {
            "lead": lead,
            "classifications": classifications,
            "osint_data": osint_data,
            "assessments": assessments,
            "alerts": alerts,
            "audit_trail": audit_trail,
            "brief": brief,
        }

    def get_cached_brief(self, lead_id: str) -> Optional[dict]:
        """Check audit log for a previously generated brief and return it if found.

        Looks for the most recent 'brief_generated' action_type in the audit log
        for the given lead.

        Args:
            lead_id: UUID of the lead.

        Returns:
            Dict with brief sections (executive_summary, key_findings, etc.) or None.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT action_detail
                    FROM pre_case_audit_log
                    WHERE lead_id = %s AND action_type = 'brief_generated'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (lead_id,),
                )
                row = cur.fetchone()
                if row:
                    detail = row[0]
                    if isinstance(detail, str):
                        detail = json.loads(detail)
                    return detail.get("brief") if isinstance(detail, dict) else None
        except Exception as e:
            logger.error(f"Failed to fetch cached brief for {lead_id}: {e}")
        return None

    # ------------------------------------------------------------------
    # List Leads
    # ------------------------------------------------------------------

    def list_leads(self, filters: dict = None, page: int = 1, page_size: int = 50) -> dict:
        """List pre-case leads with pagination and filtering.

        Args:
            filters: Optional dict with case_type, status, priority,
                     assigned_analyst, min_score, max_score.
            page: Page number (1-indexed).
            page_size: Number of results per page.

        Returns:
            Dict with leads list, total count, and pagination info.
        """
        filters = filters or {}
        offset = (page - 1) * page_size

        where_clauses = []
        params = []

        if filters.get("case_type"):
            where_clauses.append("case_type = %s")
            params.append(filters["case_type"])

        if filters.get("status"):
            where_clauses.append("status = %s")
            params.append(filters["status"])

        if filters.get("priority"):
            where_clauses.append("priority = %s")
            params.append(filters["priority"])

        if filters.get("assigned_analyst"):
            where_clauses.append("assigned_analyst = %s")
            params.append(filters["assigned_analyst"])

        if filters.get("min_score") is not None:
            where_clauses.append("pre_assessment_score >= %s")
            params.append(filters["min_score"])

        if filters.get("max_score") is not None:
            where_clauses.append("pre_assessment_score <= %s")
            params.append(filters["max_score"])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        try:
            with self.aurora_cm.cursor() as cur:
                # Get total count
                cur.execute(
                    f"SELECT COUNT(*) FROM pre_case_leads WHERE {where_sql}",
                    params,
                )
                total = cur.fetchone()[0]

                # Get paginated results
                cur.execute(
                    f"""
                    SELECT lead_id, title, summary, source_type, case_type,
                           classification_confidence, pre_assessment_score,
                           status, priority, assigned_analyst, monitoring_frequency,
                           promoted_case_id, closure_reason, created_at, updated_at
                    FROM pre_case_leads
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    params + [page_size, offset],
                )
                rows = cur.fetchall()

            leads = []
            for row in rows:
                leads.append({
                    "lead_id": str(row[0]),
                    "title": row[1],
                    "summary": row[2],
                    "source_type": row[3],
                    "case_type": row[4],
                    "classification_confidence": row[5],
                    "pre_assessment_score": row[6],
                    "status": row[7],
                    "priority": row[8],
                    "assigned_analyst": row[9],
                    "monitoring_frequency": row[10],
                    "promoted_case_id": str(row[11]) if row[11] else None,
                    "closure_reason": row[12],
                    "created_at": row[13].isoformat() if row[13] else None,
                    "updated_at": row[14].isoformat() if row[14] else None,
                })

            return {
                "leads": leads,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
            }

        except Exception as e:
            logger.error(f"Failed to list leads: {e}")
            raise

    # ------------------------------------------------------------------
    # Update Lead
    # ------------------------------------------------------------------

    def update_lead(self, lead_id: str, updates: dict) -> dict:
        """Update lead fields: priority, assigned_analyst, monitoring_frequency, status.

        Args:
            lead_id: UUID of the lead.
            updates: Dict with fields to update.

        Returns:
            Dict with updated lead info.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise KeyError(f"Lead {lead_id} not found")

        previous_state = {
            "priority": lead.get("priority"),
            "assigned_analyst": lead.get("assigned_analyst"),
            "monitoring_frequency": lead.get("monitoring_frequency"),
            "status": lead.get("status"),
        }

        allowed_fields = {"priority", "assigned_analyst", "monitoring_frequency", "status", "closure_reason"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return {"lead_id": lead_id, "message": "No valid fields to update"}

        # Validate status transition if status is being changed
        if "status" in filtered_updates:
            new_status = filtered_updates["status"]
            current_status = lead["status"]
            if new_status != current_status:
                valid_next = VALID_TRANSITIONS.get(current_status, [])
                if new_status not in valid_next:
                    raise ValueError(
                        f"Invalid status transition: {current_status} -> {new_status}. "
                        f"Valid transitions: {valid_next}"
                    )

        # Build UPDATE query
        set_clauses = []
        params = []
        for field, value in filtered_updates.items():
            set_clauses.append(f"{field} = %s")
            params.append(value)

        set_clauses.append("updated_at = %s")
        params.append(datetime.now(timezone.utc))
        params.append(lead_id)

        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE pre_case_leads
                    SET {', '.join(set_clauses)}
                    WHERE lead_id = %s
                    """,
                    params,
                )
        except Exception as e:
            logger.error(f"Failed to update lead {lead_id}: {e}")
            raise

        self._create_audit_record(
            lead_id=lead_id,
            action_type="lead_updated",
            actor=updates.get("actor", "analyst"),
            action_detail=filtered_updates,
            previous_state=previous_state,
        )

        return {"lead_id": lead_id, "updated_fields": list(filtered_updates.keys()), "status": "updated"}

    # ------------------------------------------------------------------
    # Auto-Pipeline Execution (Task 6.1)
    # ------------------------------------------------------------------

    def run_pipeline(self, lead_id: str) -> dict:
        """Execute classify → gather → assess synchronously.

        Validates lead is in 'intake' status before starting.
        Records each step in audit log with pipeline_run_id.
        Stops at first failure, leaves lead in failed step's status.

        Args:
            lead_id: UUID of the lead.

        Returns:
            Dict with pipeline_run_id, status, current_step, steps results, error.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise KeyError(f"Lead {lead_id} not found")

        if lead["status"] not in ("intake", "classifying", "gathering", "assessing"):
            raise ValueError(
                f"Cannot run pipeline on lead in status '{lead['status']}'. "
                f"Lead must be in 'intake', 'classifying', 'gathering', or 'assessing' status."
            )

        pipeline_run_id = str(uuid.uuid4())
        steps = {"classify": {"status": "pending"}, "gather": {"status": "pending"}, "assess": {"status": "pending"}}
        current_step = "classify"
        error = None

        self._create_audit_record(
            lead_id=lead_id,
            action_type="pipeline_started",
            actor="system",
            action_detail={"pipeline_run_id": pipeline_run_id},
        )

        # Step 1: Classify
        try:
            steps["classify"]["status"] = "running"
            if lead["status"] == "intake":
                self._transition_status(lead_id, "intake", "classifying")
            classify_result = self.classify_lead(lead_id)
            steps["classify"]["status"] = "completed"
            steps["classify"]["result"] = classify_result
            current_step = "gather"
        except Exception as e:
            steps["classify"]["status"] = "failed"
            steps["classify"]["error"] = str(e)
            error = f"Classification failed: {e}"
            self._create_audit_record(
                lead_id=lead_id,
                action_type="pipeline_failed",
                actor="system",
                action_detail={"pipeline_run_id": pipeline_run_id, "failed_step": "classify", "error": str(e)},
            )
            return {
                "pipeline_run_id": pipeline_run_id,
                "status": "failed",
                "current_step": "classify",
                "steps": steps,
                "error": error,
            }

        # Step 2: Gather OSINT
        try:
            steps["gather"]["status"] = "running"
            # Extract subjects from classification result or lead content
            subjects = []
            if classify_result.get("case_type"):
                content = lead.get("source_content", {})
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        content = {}
                subjects = content.get("subjects", [])
                if not subjects:
                    subjects = [lead.get("title", "")]

            gather_result = self.gather_osint(lead_id, subjects=subjects)
            steps["gather"]["status"] = "completed"
            steps["gather"]["result"] = gather_result
            current_step = "assess"
        except Exception as e:
            steps["gather"]["status"] = "failed"
            steps["gather"]["error"] = str(e)
            error = f"OSINT gathering failed: {e}"
            self._create_audit_record(
                lead_id=lead_id,
                action_type="pipeline_failed",
                actor="system",
                action_detail={"pipeline_run_id": pipeline_run_id, "failed_step": "gather", "error": str(e)},
            )
            return {
                "pipeline_run_id": pipeline_run_id,
                "status": "failed",
                "current_step": "gather",
                "steps": steps,
                "error": error,
            }

        # Step 3: Assess
        try:
            steps["assess"]["status"] = "running"
            assess_result = self.assess_lead(lead_id)
            steps["assess"]["status"] = "completed"
            steps["assess"]["result"] = assess_result
            current_step = "completed"

            # Transition to monitoring on success
            try:
                self._transition_status(lead_id, "assessing", "monitoring")
            except Exception:
                pass  # May already be in monitoring
        except Exception as e:
            steps["assess"]["status"] = "failed"
            steps["assess"]["error"] = str(e)
            error = f"Assessment failed: {e}"
            self._create_audit_record(
                lead_id=lead_id,
                action_type="pipeline_failed",
                actor="system",
                action_detail={"pipeline_run_id": pipeline_run_id, "failed_step": "assess", "error": str(e)},
            )
            return {
                "pipeline_run_id": pipeline_run_id,
                "status": "failed",
                "current_step": "assess",
                "steps": steps,
                "error": error,
            }

        # Step 4: Auto-generate investigative brief (non-blocking)
        try:
            import boto3
            from services.investigative_brief_service import InvestigativeBriefService

            bedrock = boto3.client("bedrock-runtime")
            brief_svc = InvestigativeBriefService(bedrock_client=bedrock)

            # Gather inputs for brief generation
            lead_data = self._get_lead(lead_id)
            osint_data = self._get_osint_summary(lead_id)
            classifications = self._get_classifications(lead_id)
            assessments_list = self._get_assessments(lead_id)
            classification = classifications[0] if classifications else None
            assessment_for_brief = assessments_list[0] if assessments_list else None

            brief_result = brief_svc.generate_brief(
                lead_data=lead_data,
                osint_data=osint_data,
                classification=classification,
                assessment=assessment_for_brief,
            )

            # Store brief in audit log for caching
            self._create_audit_record(
                lead_id=lead_id,
                action_type="brief_generated",
                actor="system",
                action_detail={"pipeline_run_id": pipeline_run_id, "brief": brief_result},
            )
            steps["brief"] = {"status": "completed", "result": brief_result}
        except Exception as e:
            logger.warning(f"Brief generation failed (non-blocking) for {lead_id}: {e}")
            steps["brief"] = {"status": "failed", "error": str(e)}

        self._create_audit_record(
            lead_id=lead_id,
            action_type="pipeline_completed",
            actor="system",
            action_detail={"pipeline_run_id": pipeline_run_id},
        )

        return {
            "pipeline_run_id": pipeline_run_id,
            "status": "completed",
            "current_step": "completed",
            "steps": steps,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Pipeline Status (Task 6.2)
    # ------------------------------------------------------------------

    def get_pipeline_status(self, lead_id: str) -> dict:
        """Get current pipeline execution status from audit log.

        Reconstructs pipeline state from audit records for the lead.

        Args:
            lead_id: UUID of the lead.

        Returns:
            Dict with current_step, status, and results for completed steps.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise KeyError(f"Lead {lead_id} not found")

        # Get pipeline-related audit records
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT action_type, action_detail, created_at
                    FROM pre_case_audit_log
                    WHERE lead_id = %s
                      AND action_type IN ('pipeline_started', 'pipeline_completed',
                                          'pipeline_failed', 'lead_classified',
                                          'osint_gathered', 'lead_assessed')
                    ORDER BY created_at ASC
                    """,
                    (lead_id,),
                )
                rows = cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to get pipeline status for {lead_id}: {e}")
            return {"lead_id": lead_id, "status": "unknown", "current_step": "unknown"}

        # Reconstruct state
        pipeline_started = False
        pipeline_run_id = None
        steps_completed = []
        failed_step = None
        error = None

        for row in rows:
            action_type = row[0]
            detail = row[1] if isinstance(row[1], dict) else (json.loads(row[1]) if row[1] else {})

            if action_type == "pipeline_started":
                pipeline_started = True
                pipeline_run_id = detail.get("pipeline_run_id")
            elif action_type == "lead_classified":
                steps_completed.append("classify")
            elif action_type == "osint_gathered":
                steps_completed.append("gather")
            elif action_type == "lead_assessed":
                steps_completed.append("assess")
            elif action_type == "pipeline_failed":
                failed_step = detail.get("failed_step")
                error = detail.get("error")
            elif action_type == "pipeline_completed":
                pass

        # Determine current state
        if not pipeline_started:
            status = "not_started"
            current_step = None
        elif failed_step:
            status = "failed"
            current_step = failed_step
        elif "assess" in steps_completed:
            status = "completed"
            current_step = "completed"
        elif "gather" in steps_completed:
            status = "running"
            current_step = "assess"
        elif "classify" in steps_completed:
            status = "running"
            current_step = "gather"
        else:
            status = "running"
            current_step = "classify"

        return {
            "lead_id": lead_id,
            "pipeline_run_id": pipeline_run_id,
            "status": status,
            "current_step": current_step,
            "steps_completed": steps_completed,
            "error": error,
            "lead_status": lead.get("status"),
        }

    # ------------------------------------------------------------------
    # Workflow Report
    # ------------------------------------------------------------------

    def get_workflow_report(self, lead_id: str) -> dict:
        """Generate a complete Pre-Case Workflow Report for a lead.

        Args:
            lead_id: UUID of the lead.

        Returns:
            Dict with complete workflow report including all stages.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise KeyError(f"Lead {lead_id} not found")

        classifications = self._get_classifications(lead_id)
        osint_data = self._get_osint_summary(lead_id)
        assessments = self._get_assessments(lead_id)
        audit_trail = self._get_audit_trail(lead_id)
        alerts = self._get_alerts(lead_id)

        # Try to get Redshift analytics (graceful degradation)
        redshift_analytics = None
        redshift_status = "available"
        try:
            if self.redshift_client and lead.get("case_type"):
                redshift_analytics = self._get_redshift_analytics(lead_id, lead["case_type"])
        except Exception as e:
            logger.warning(f"Redshift unavailable for report: {e}")
            redshift_status = "unavailable"
            redshift_analytics = None

        return {
            "lead_id": lead_id,
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "lead_summary": {
                "title": lead.get("title"),
                "source_type": lead.get("source_type"),
                "case_type": lead.get("case_type"),
                "status": lead.get("status"),
                "priority": lead.get("priority"),
                "pre_assessment_score": lead.get("pre_assessment_score"),
                "created_at": lead.get("created_at").isoformat() if lead.get("created_at") else None,
            },
            "classification_history": classifications,
            "osint_data_summary": osint_data,
            "assessment_history": assessments,
            "trawler_alerts": alerts,
            "audit_trail": audit_trail,
            "redshift_analytics": redshift_analytics,
            "redshift_status": redshift_status,
        }

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _get_lead(self, lead_id: str) -> Optional[dict]:
        """Retrieve a lead record from Aurora."""
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT lead_id, title, summary, source_type, source_content,
                           case_type, classification_confidence, pre_assessment_score,
                           status, priority, assigned_analyst, monitoring_frequency,
                           promoted_case_id, closure_reason, created_at, updated_at
                    FROM pre_case_leads
                    WHERE lead_id = %s
                    """,
                    (lead_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "lead_id": str(row[0]),
                    "title": row[1],
                    "summary": row[2],
                    "source_type": row[3],
                    "source_content": row[4],
                    "case_type": row[5],
                    "classification_confidence": row[6],
                    "pre_assessment_score": row[7],
                    "status": row[8],
                    "priority": row[9],
                    "assigned_analyst": row[10],
                    "monitoring_frequency": row[11],
                    "promoted_case_id": str(row[12]) if row[12] else None,
                    "closure_reason": row[13],
                    "created_at": row[14],
                    "updated_at": row[15],
                }
        except Exception as e:
            logger.error(f"Failed to get lead {lead_id}: {e}")
            return None

    def _transition_status(self, lead_id: str, current_status: str, new_status: str) -> None:
        """Enforce and execute a valid workflow status transition."""
        valid_next = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in valid_next:
            raise ValueError(
                f"Invalid status transition: {current_status} -> {new_status}. "
                f"Valid transitions: {valid_next}"
            )

        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pre_case_leads
                    SET status = %s, updated_at = %s
                    WHERE lead_id = %s AND status = %s
                    """,
                    (new_status, datetime.now(timezone.utc), lead_id, current_status),
                )
        except Exception as e:
            logger.error(f"Failed to transition lead {lead_id} status: {e}")
            raise

    def _create_audit_record(
        self,
        lead_id: str,
        action_type: str,
        actor: str,
        action_detail: dict,
        previous_state: Optional[dict] = None,
    ) -> None:
        """Create an immutable audit record for a lead action."""
        audit_id = str(uuid.uuid4())
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pre_case_audit_log
                        (audit_id, lead_id, action_type, actor, action_detail, previous_state, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        audit_id,
                        lead_id,
                        action_type,
                        actor,
                        json.dumps(action_detail, default=str),
                        json.dumps(previous_state, default=str) if previous_state else None,
                        datetime.now(timezone.utc),
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to create audit record for {lead_id}: {e}")

    def _get_lead_evidence(self, lead_id: str) -> list:
        """Retrieve gathered OSINT evidence for a lead."""
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT osint_id, source_name, data_format, reliability_rating,
                           extracted_entities, retrieval_timestamp
                    FROM pre_case_osint_data
                    WHERE lead_id = %s
                    ORDER BY retrieval_timestamp
                    """,
                    (lead_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "osint_id": str(row[0]),
                        "source_name": row[1],
                        "data_format": row[2],
                        "reliability_rating": row[3],
                        "extracted_entities": row[4],
                        "retrieval_timestamp": row[5].isoformat() if row[5] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get evidence for {lead_id}: {e}")
            return []

    def _get_classifications(self, lead_id: str) -> list:
        """Retrieve classification history for a lead."""
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT classification_id, case_type, confidence, reasoning,
                           alternatives, model_version, decision_status, created_at
                    FROM pre_case_classifications
                    WHERE lead_id = %s
                    ORDER BY created_at DESC
                    """,
                    (lead_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "classification_id": str(row[0]),
                        "case_type": row[1],
                        "confidence": row[2],
                        "reasoning": row[3],
                        "alternatives": row[4],
                        "model_version": row[5],
                        "decision_status": row[6],
                        "created_at": row[7].isoformat() if row[7] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get classifications for {lead_id}: {e}")
            return []

    def _get_osint_summary(self, lead_id: str) -> list:
        """Retrieve OSINT data summary for a lead."""
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT osint_id, source_name, source_url, retrieval_timestamp,
                           data_format, reliability_rating, extracted_entities
                    FROM pre_case_osint_data
                    WHERE lead_id = %s
                    ORDER BY retrieval_timestamp DESC
                    """,
                    (lead_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "osint_id": str(row[0]),
                        "source_name": row[1],
                        "source_url": row[2],
                        "retrieval_timestamp": row[3].isoformat() if row[3] else None,
                        "data_format": row[4],
                        "reliability_rating": row[5],
                        "extracted_entities": row[6],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get OSINT summary for {lead_id}: {e}")
            return []

    def _get_assessments(self, lead_id: str) -> list:
        """Retrieve assessment history for a lead."""
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT assessment_id, score, recommendation, evidence_matrix,
                           evidence_gaps, legal_reasoning, scoring_framework,
                           decision_status, created_at
                    FROM pre_case_assessments
                    WHERE lead_id = %s
                    ORDER BY created_at DESC
                    """,
                    (lead_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "assessment_id": str(row[0]),
                        "score": row[1],
                        "recommendation": row[2],
                        "evidence_matrix": row[3],
                        "evidence_gaps": row[4],
                        "legal_reasoning": row[5],
                        "scoring_framework": row[6],
                        "decision_status": row[7],
                        "created_at": row[8].isoformat() if row[8] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get assessments for {lead_id}: {e}")
            return []

    def _get_audit_trail(self, lead_id: str) -> list:
        """Retrieve audit trail for a lead."""
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT audit_id, action_type, actor, action_detail,
                           previous_state, created_at
                    FROM pre_case_audit_log
                    WHERE lead_id = %s
                    ORDER BY created_at ASC
                    """,
                    (lead_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "audit_id": str(row[0]),
                        "action_type": row[1],
                        "actor": row[2],
                        "action_detail": row[3],
                        "previous_state": row[4],
                        "created_at": row[5].isoformat() if row[5] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get audit trail for {lead_id}: {e}")
            return []

    def _get_alerts(self, lead_id: str) -> list:
        """Retrieve trawler alerts for a lead."""
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT alert_id, alert_type, severity, message, created_at
                    FROM trawler_alerts
                    WHERE lead_id = %s
                    ORDER BY created_at DESC
                    """,
                    (lead_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "alert_id": str(row[0]),
                        "alert_type": row[1],
                        "severity": row[2],
                        "message": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            # Table may not exist yet or no alerts
            logger.debug(f"No alerts found for {lead_id}: {e}")
            return []

    def _get_redshift_analytics(self, lead_id: str, case_type: str) -> Optional[dict]:
        """Retrieve Redshift analytics for a lead. Handles unavailability gracefully."""
        if not self.redshift_client:
            return None

        try:
            workgroup = "pre-case-analytics"
            database = "dev"

            response = self.redshift_client.execute_statement(
                WorkgroupName=workgroup,
                Database=database,
                Sql="""
                    SELECT vendor_id, state, total_bids, wins, win_rate_pct
                    FROM mv_vendor_win_rates
                    WHERE win_rate_pct > 80
                    ORDER BY win_rate_pct DESC
                    LIMIT 20
                """,
            )
            return {
                "query_id": response.get("Id"),
                "status": "submitted",
                "description": "High win-rate vendors analysis",
            }
        except Exception as e:
            logger.warning(f"Redshift analytics unavailable: {e}")
            return None
