"""Pre-Case Trawler — Continuous monitoring for pre-case leads.

Extends the existing TrawlerEngine via composition (not inheritance) to provide
continuous monitoring of OSINT sources for active pre-case leads. Schedules
periodic scans based on lead priority, generates alerts when new data is found,
and triggers re-assessment when the Pre_Assessment_Score changes significantly.

Key behaviors:
- Priority-based scheduling: high=daily, medium=weekly, low=monthly
- High-severity alert ONLY when Pre_Assessment_Score changes by >10 points
- NO alerts on source unavailability (log only, retry next scan)
- Transfer to case-level Trawler on promotion to formal investigation

Monitors up to 50 concurrent leads. Each scan processes one lead at a time.
No batch processing of 100+ items — individual Aurora row operations per scan.

Usage:
    trawler = PreCaseTrawler(
        trawler_engine=trawler_engine_instance,
        osint_gatherer=osint_gatherer_instance,
        prosecution_assessment=prosecution_assessment_instance,
        aurora_cm=connection_manager,
    )
    trawler.register_lead("lead-uuid", {"priority": "high", "subjects": [...]})
    result = trawler.run_monitoring_scan("lead-uuid")
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Priority to monitoring frequency mapping
PRIORITY_FREQUENCY_MAP = {
    "critical": "daily",
    "high": "daily",
    "medium": "weekly",
    "low": "monthly",
}

# Score change threshold for high-severity alerts
SCORE_CHANGE_THRESHOLD = 10

# Alert severity levels
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"


class PreCaseTrawler:
    """Extends TrawlerEngine for continuous pre-case lead monitoring.

    Uses composition (wraps TrawlerEngine) rather than inheritance.
    Schedules periodic OSINT scans, generates alerts on new data,
    and triggers re-assessment when scores change significantly.

    Follows Protocol/constructor-injection pattern for testability.
    """

    def __init__(
        self,
        trawler_engine: Any,
        osint_gatherer: Any,
        prosecution_assessment: Any,
        aurora_cm: Any,
    ) -> None:
        """Initialize with dependencies.

        Args:
            trawler_engine: Existing TrawlerEngine instance for scan infrastructure.
            osint_gatherer: OsintDataGatherer for querying OSINT sources.
            prosecution_assessment: ProsecutionReadinessAssessment for re-scoring.
            aurora_cm: Aurora PostgreSQL connection manager with cursor() context.
        """
        self.trawler_engine = trawler_engine
        self.osint_gatherer = osint_gatherer
        self.prosecution_assessment = prosecution_assessment
        self.aurora_cm = aurora_cm

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_lead(self, lead_id: str, config: dict) -> None:
        """Register a pre-case lead for continuous monitoring.

        Schedules monitoring based on priority:
        - high/critical → daily
        - medium → weekly
        - low → monthly

        Args:
            lead_id: UUID of the pre-case lead to monitor.
            config: Monitoring configuration containing:
                - priority: Lead priority (critical, high, medium, low).
                - subjects: List of entity names to monitor.
                - case_type: Classified antitrust case type.
                - sources: Optional list of specific OSINT sources to monitor.
        """
        priority = config.get("priority", "medium")
        frequency = PRIORITY_FREQUENCY_MAP.get(priority, "weekly")
        subjects = config.get("subjects", [])
        case_type = config.get("case_type", "")
        sources = config.get("sources", None)

        try:
            with self.aurora_cm.cursor() as cur:
                # Update lead monitoring frequency
                cur.execute(
                    """UPDATE pre_case_leads
                       SET monitoring_frequency = %s,
                           status = CASE WHEN status = 'assessing' THEN 'monitoring'
                                         ELSE status END,
                           updated_at = NOW()
                       WHERE lead_id = %s""",
                    (frequency, lead_id),
                )

                # Store monitoring config in audit log
                cur.execute(
                    """INSERT INTO pre_case_audit_log
                       (audit_id, lead_id, action_type, actor, action_detail)
                       VALUES (%s, %s, 'trawler_registered', 'system', %s)""",
                    (
                        str(uuid.uuid4()),
                        lead_id,
                        json.dumps({
                            "frequency": frequency,
                            "priority": priority,
                            "subjects": subjects,
                            "case_type": case_type,
                            "sources": sources,
                        }),
                    ),
                )

            logger.info(
                "Registered lead %s for %s monitoring (priority=%s)",
                lead_id, frequency, priority,
            )
        except Exception as e:
            logger.error("Failed to register lead %s for monitoring: %s", lead_id, e)
            raise

    def run_monitoring_scan(self, lead_id: str) -> dict:
        """Execute a monitoring scan for a pre-case lead.

        Queries OSINT sources for new data relevant to the lead. If new data
        is found, triggers re-assessment and generates alerts based on score
        changes.

        Does NOT generate alerts when sources are temporarily unavailable
        (logs the failure and retries on next scheduled scan).

        Args:
            lead_id: UUID of the pre-case lead to scan.

        Returns:
            Dict with scan results:
                - scan_id: UUID of this scan.
                - lead_id: The scanned lead.
                - new_data_found: Whether new data was discovered.
                - sources_queried: List of sources checked.
                - sources_failed: List of sources that were unavailable.
                - score_before: Pre_Assessment_Score before scan.
                - score_after: Pre_Assessment_Score after re-assessment (if triggered).
                - alerts_generated: List of alerts created.
                - scan_timestamp: When the scan was executed.
        """
        scan_id = str(uuid.uuid4())
        scan_timestamp = datetime.now(timezone.utc).isoformat()
        alerts_generated = []

        # Get lead details for scan context
        lead = self._get_lead(lead_id)
        if not lead:
            logger.warning("Lead %s not found for monitoring scan", lead_id)
            return {
                "scan_id": scan_id,
                "lead_id": lead_id,
                "new_data_found": False,
                "error": "lead_not_found",
                "scan_timestamp": scan_timestamp,
            }

        case_type = lead.get("case_type", "")
        subjects = self._get_lead_subjects(lead_id)
        score_before = lead.get("pre_assessment_score") or 0

        # Run OSINT gathering for new data
        gather_result = None
        try:
            gather_result = self.osint_gatherer.gather(
                lead_id=lead_id,
                case_type=case_type,
                subjects=subjects,
            )
        except Exception as e:
            logger.error("OSINT gathering failed for lead %s: %s", lead_id, e)

        sources_queried = []
        sources_failed = []
        new_data_found = False

        if gather_result:
            sources_queried = getattr(gather_result, "sources_queried", [])
            sources_failed = getattr(gather_result, "sources_failed", [])
            records_gathered = getattr(gather_result, "records_gathered", 0)
            new_data_found = records_gathered > 0

            # Log source unavailability without generating alerts
            for source in sources_failed:
                logger.warning(
                    "Source %s unavailable during scan for lead %s — "
                    "will retry on next scheduled scan",
                    source, lead_id,
                )

        # Re-assess if new data was found
        score_after = score_before
        if new_data_found:
            try:
                assessment_result = self.prosecution_assessment.assess(
                    lead_id=lead_id,
                    evidence=[],  # Assessment fetches evidence from DB
                    case_type=case_type,
                )
                score_after = getattr(assessment_result, "score", score_before)

                # Update lead score in Aurora
                self._update_lead_score(lead_id, score_after)

            except Exception as e:
                logger.error(
                    "Re-assessment failed for lead %s: %s", lead_id, e
                )

            # Generate high-severity alert if score changed by >10 points
            score_change = abs(score_after - score_before)
            if score_change > SCORE_CHANGE_THRESHOLD:
                direction = "increased" if score_after > score_before else "decreased"
                alert = self._create_alert(
                    lead_id=lead_id,
                    severity=SEVERITY_HIGH,
                    alert_type="score_change",
                    message=(
                        f"Pre_Assessment_Score {direction} by {score_change} points "
                        f"(from {score_before} to {score_after}) due to new OSINT data"
                    ),
                    details={
                        "score_before": score_before,
                        "score_after": score_after,
                        "score_change": score_change,
                        "direction": direction,
                        "sources_with_new_data": [
                            s for s in sources_queried if s not in sources_failed
                        ],
                    },
                )
                alerts_generated.append(alert)
            elif new_data_found:
                # Medium-severity alert for new data without major score change
                alert = self._create_alert(
                    lead_id=lead_id,
                    severity=SEVERITY_MEDIUM,
                    alert_type="new_data",
                    message="New OSINT data detected during monitoring scan",
                    details={
                        "sources_with_new_data": [
                            s for s in sources_queried if s not in sources_failed
                        ],
                        "records_gathered": getattr(
                            gather_result, "records_gathered", 0
                        ),
                    },
                )
                alerts_generated.append(alert)

        # Record scan in audit log
        self._record_scan(lead_id, scan_id, {
            "sources_queried": sources_queried,
            "sources_failed": sources_failed,
            "new_data_found": new_data_found,
            "score_before": score_before,
            "score_after": score_after,
            "alerts_count": len(alerts_generated),
        })

        return {
            "scan_id": scan_id,
            "lead_id": lead_id,
            "new_data_found": new_data_found,
            "sources_queried": sources_queried,
            "sources_failed": sources_failed,
            "score_before": score_before,
            "score_after": score_after,
            "alerts_generated": alerts_generated,
            "scan_timestamp": scan_timestamp,
        }

    def transfer_to_case_trawler(self, lead_id: str, case_id: str) -> None:
        """Transfer monitoring configuration to case-level Trawler.

        Archives pre-case monitoring history and configures the existing
        case-level TrawlerEngine for the newly opened investigation.

        Args:
            lead_id: UUID of the pre-case lead being promoted.
            case_id: UUID of the newly created formal investigation case.
        """
        # Get current monitoring config
        lead = self._get_lead(lead_id)
        if not lead:
            logger.warning("Lead %s not found for transfer", lead_id)
            return

        subjects = self._get_lead_subjects(lead_id)
        case_type = lead.get("case_type", "")
        frequency = lead.get("monitoring_frequency", "weekly")

        # Build case-level trawl config from pre-case monitoring
        trawl_config = {
            "scan_frequency": frequency,
            "subjects": subjects,
            "case_type": case_type,
            "source_from_pre_case": lead_id,
            "external_sources": True,
            "min_alert_severity": "medium",
        }

        # Save config to case-level Trawler
        try:
            self.trawler_engine.save_trawl_config(case_id, trawl_config)
        except Exception as e:
            logger.error(
                "Failed to save trawl config for case %s: %s", case_id, e
            )

        # Archive pre-case monitoring history
        try:
            with self.aurora_cm.cursor() as cur:
                # Record transfer in audit log
                cur.execute(
                    """INSERT INTO pre_case_audit_log
                       (audit_id, lead_id, action_type, actor, action_detail)
                       VALUES (%s, %s, 'trawler_transferred', 'system', %s)""",
                    (
                        str(uuid.uuid4()),
                        lead_id,
                        json.dumps({
                            "case_id": case_id,
                            "trawl_config": trawl_config,
                            "transfer_timestamp": datetime.now(
                                timezone.utc
                            ).isoformat(),
                        }),
                    ),
                )

                # Update lead status
                cur.execute(
                    """UPDATE pre_case_leads
                       SET status = 'promoted',
                           promoted_case_id = %s,
                           updated_at = NOW()
                       WHERE lead_id = %s""",
                    (case_id, lead_id),
                )

            logger.info(
                "Transferred monitoring from lead %s to case %s",
                lead_id, case_id,
            )
        except Exception as e:
            logger.error(
                "Failed to archive monitoring for lead %s: %s", lead_id, e
            )

    def get_scan_schedule(self) -> list:
        """Return all scheduled monitoring scans.

        Queries Aurora for all active leads with their monitoring frequency
        and last scan timestamp.

        Returns:
            List of schedule dicts with: lead_id, title, case_type, priority,
            monitoring_frequency, last_scan_at, next_scan_due.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """SELECT
                        l.lead_id, l.title, l.case_type, l.priority,
                        l.monitoring_frequency, l.assigned_analyst,
                        l.pre_assessment_score,
                        (SELECT MAX(a.created_at)
                         FROM pre_case_audit_log a
                         WHERE a.lead_id = l.lead_id
                           AND a.action_type = 'monitoring_scan') AS last_scan_at
                    FROM pre_case_leads l
                    WHERE l.status = 'monitoring'
                    ORDER BY
                        CASE l.priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END,
                        l.created_at ASC"""
                )
                rows = cur.fetchall()

            schedule = []
            for row in rows:
                lead_id = str(row[0])
                frequency = row[4] or "weekly"
                last_scan = row[7]

                schedule.append({
                    "lead_id": lead_id,
                    "title": row[1] or "",
                    "case_type": row[2] or "",
                    "priority": row[3] or "medium",
                    "monitoring_frequency": frequency,
                    "assigned_analyst": row[5] or "",
                    "pre_assessment_score": row[6] or 0,
                    "last_scan_at": last_scan.isoformat() if last_scan else None,
                })

            return schedule

        except Exception as e:
            logger.error("Failed to get scan schedule: %s", e)
            return []

    def update_monitoring_config(self, lead_id: str, config: dict) -> None:
        """Allow analyst customization of monitoring configuration.

        Supports updating: frequency, sources, subjects, priority.

        Args:
            lead_id: UUID of the pre-case lead.
            config: Updated configuration fields. Supported keys:
                - frequency: New monitoring frequency (daily, weekly, monthly).
                - priority: New priority level.
                - sources: Updated list of OSINT sources to monitor.
                - subjects: Updated list of subjects to track.
        """
        updates = {}
        sql_parts = []
        params = []

        if "frequency" in config:
            frequency = config["frequency"]
            if frequency in ("daily", "weekly", "monthly"):
                sql_parts.append("monitoring_frequency = %s")
                params.append(frequency)
                updates["monitoring_frequency"] = frequency

        if "priority" in config:
            priority = config["priority"]
            if priority in ("critical", "high", "medium", "low"):
                sql_parts.append("priority = %s")
                params.append(priority)
                updates["priority"] = priority
                # Also update frequency based on new priority
                new_freq = PRIORITY_FREQUENCY_MAP.get(priority, "weekly")
                if "frequency" not in config:
                    sql_parts.append("monitoring_frequency = %s")
                    params.append(new_freq)
                    updates["monitoring_frequency"] = new_freq

        if not sql_parts:
            # Only sources/subjects changed — store in audit log
            if "sources" in config or "subjects" in config:
                updates["sources"] = config.get("sources")
                updates["subjects"] = config.get("subjects")
            else:
                return

        try:
            with self.aurora_cm.cursor() as cur:
                if sql_parts:
                    sql_parts.append("updated_at = NOW()")
                    params.append(lead_id)
                    cur.execute(
                        f"""UPDATE pre_case_leads
                            SET {', '.join(sql_parts)}
                            WHERE lead_id = %s""",
                        params,
                    )

                # Record config change in audit log
                cur.execute(
                    """INSERT INTO pre_case_audit_log
                       (audit_id, lead_id, action_type, actor, action_detail)
                       VALUES (%s, %s, 'monitoring_config_updated', 'analyst', %s)""",
                    (
                        str(uuid.uuid4()),
                        lead_id,
                        json.dumps({"updates": updates, "full_config": config}),
                    ),
                )

            logger.info("Updated monitoring config for lead %s: %s", lead_id, updates)
        except Exception as e:
            logger.error(
                "Failed to update monitoring config for lead %s: %s", lead_id, e
            )
            raise

    # ------------------------------------------------------------------
    # Internal — Data Access
    # ------------------------------------------------------------------

    def _get_lead(self, lead_id: str) -> Optional[dict]:
        """Fetch lead details from Aurora.

        Args:
            lead_id: UUID of the lead.

        Returns:
            Dict with lead fields or None if not found.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """SELECT lead_id, title, case_type, status, priority,
                              monitoring_frequency, pre_assessment_score,
                              assigned_analyst
                       FROM pre_case_leads
                       WHERE lead_id = %s""",
                    (lead_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "lead_id": str(row[0]),
                    "title": row[1],
                    "case_type": row[2],
                    "status": row[3],
                    "priority": row[4],
                    "monitoring_frequency": row[5],
                    "pre_assessment_score": row[6],
                    "assigned_analyst": row[7],
                }
        except Exception as e:
            logger.error("Failed to fetch lead %s: %s", lead_id, e)
            return None

    def _get_lead_subjects(self, lead_id: str) -> list:
        """Extract monitored subjects for a lead from its source content.

        Args:
            lead_id: UUID of the lead.

        Returns:
            List of subject name strings.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """SELECT source_content
                       FROM pre_case_leads
                       WHERE lead_id = %s""",
                    (lead_id,),
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    return []
                content = row[0]
                if isinstance(content, str):
                    content = json.loads(content)
                return content.get("subjects", [])
        except Exception as e:
            logger.error("Failed to get subjects for lead %s: %s", lead_id, e)
            return []

    def _update_lead_score(self, lead_id: str, score: int) -> None:
        """Update the Pre_Assessment_Score for a lead.

        Args:
            lead_id: UUID of the lead.
            score: New score value.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """UPDATE pre_case_leads
                       SET pre_assessment_score = %s, updated_at = NOW()
                       WHERE lead_id = %s""",
                    (score, lead_id),
                )
        except Exception as e:
            logger.error("Failed to update score for lead %s: %s", lead_id, e)

    # ------------------------------------------------------------------
    # Internal — Alert Generation
    # ------------------------------------------------------------------

    def _create_alert(
        self,
        lead_id: str,
        severity: str,
        alert_type: str,
        message: str,
        details: dict,
    ) -> dict:
        """Create a Trawler alert for a pre-case lead.

        Stores the alert in the audit log (pre-case alerts use the audit
        trail rather than the case-level trawl_alerts table).

        Args:
            lead_id: UUID of the lead.
            severity: Alert severity (high, medium, low).
            alert_type: Type of alert (score_change, new_data).
            message: Human-readable alert message.
            details: Additional alert context.

        Returns:
            Alert dict with all fields.
        """
        alert_id = str(uuid.uuid4())
        alert = {
            "alert_id": alert_id,
            "lead_id": lead_id,
            "severity": severity,
            "alert_type": alert_type,
            "message": message,
            "details": details,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """INSERT INTO pre_case_audit_log
                       (audit_id, lead_id, action_type, actor, action_detail)
                       VALUES (%s, %s, 'trawler_alert', 'system', %s)""",
                    (alert_id, lead_id, json.dumps(alert)),
                )
        except Exception as e:
            logger.error("Failed to store alert for lead %s: %s", lead_id, e)

        logger.info(
            "Generated %s-severity alert for lead %s: %s",
            severity, lead_id, alert_type,
        )
        return alert

    def _record_scan(self, lead_id: str, scan_id: str, details: dict) -> None:
        """Record a monitoring scan in the audit log.

        Args:
            lead_id: UUID of the lead.
            scan_id: UUID of this scan.
            details: Scan result details.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """INSERT INTO pre_case_audit_log
                       (audit_id, lead_id, action_type, actor, action_detail)
                       VALUES (%s, %s, 'monitoring_scan', 'system', %s)""",
                    (scan_id, lead_id, json.dumps(details)),
                )
        except Exception as e:
            logger.error("Failed to record scan for lead %s: %s", lead_id, e)
