"""Conspiracy Theory Validation Pipeline.

Processes complete theory datasets in sequence, gating progression
on a 50% signature match rate. Produces validation reports and gap
analysis when failures occur.

Processing Order: Bermuda Triangle → Princess Diana → Flat Earth → UFO → JFK
(then remaining 5 theories in any order)
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ValidationResult:
    """Result of validating a single theory dataset against the taxonomy."""
    theory_name: str
    status: str = "pending"              # pending | processing | validated | failed
    documents_processed: int = 0
    signatures_matched: int = 0
    signatures_with_zero_matches: int = 0
    cross_connections_found: int = 0
    average_confidence: float = 0.0
    match_rate: float = 0.0              # Proportion of signatures that got at least 1 match
    gap_analysis: dict = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""

    @property
    def passed(self) -> bool:
        return self.match_rate >= 0.50


class ConspiracyValidationPipeline:
    """Sequential theory validation with gating.
    
    Each theory must achieve ≥50% signature match rate before the next
    theory is unlocked. Failures produce gap analysis identifying which
    Domains lack coverage for the failing theory.
    """

    PROCESSING_ORDER = [
        "bermuda_triangle",     # Small, diverse, solved — ideal validator
        "princess_diana",       # Single dense document — tests depth
        "flat_earth",           # Massive scale — tests throughput
        "ufos_uaps",            # Multi-format, large — tests format handling
        "jfk_assassination",    # 6M pages — tests at full scale
    ]

    UNGATED_THEORIES = [        # Processable in any order after first 5
        "nine_eleven",
        "covid_lab_leak",
        "moon_landing",
        "vaccine_conspiracies",
        "new_world_order",
    ]

    def __init__(self, taxonomy_service=None, bedrock_client=None,
                 connection_manager=None, opensearch_client=None):
        self.taxonomy = taxonomy_service
        self.bedrock = bedrock_client
        self.db = connection_manager
        self.os_client = opensearch_client

    def start_validation(self, theory_name: str) -> ValidationResult:
        """Start validation for a specific theory.
        
        Checks that the predecessor theory (if any) has passed before allowing.
        """
        # Check gate
        gate_result = self.check_gate(theory_name)
        if gate_result and not gate_result.passed:
            return ValidationResult(
                theory_name=theory_name,
                status="blocked",
                gap_analysis={"reason": f"Predecessor has not passed validation"}
            )

        # Mark as processing
        result = ValidationResult(
            theory_name=theory_name,
            status="processing",
            started_at=datetime.now(timezone.utc).isoformat()
        )

        if self.db:
            self.db.execute(
                """UPDATE conspiracy.processing_status 
                   SET status = 'processing', started_at = NOW()
                   WHERE theory_name = %s""",
                (theory_name,)
            )

        # Process the theory dataset
        # (In production, this would invoke the full agent chain)
        # For now, we simulate the validation metrics
        result = self._run_validation(theory_name, result)

        # Store final result
        if self.db:
            self.db.execute(
                """UPDATE conspiracy.processing_status 
                   SET status = %s, documents_processed = %s, signatures_matched = %s,
                       cross_connections = %s, match_rate = %s, completed_at = NOW(),
                       gap_analysis = %s
                   WHERE theory_name = %s""",
                (result.status, result.documents_processed, result.signatures_matched,
                 result.cross_connections_found, result.match_rate,
                 json.dumps(result.gap_analysis) if result.gap_analysis else None,
                 theory_name)
            )

        return result

    def check_gate(self, theory_name: str) -> Optional[ValidationResult]:
        """Check if this theory's predecessor has passed (sequential gating).
        
        Returns None if no gate exists (theory is first or ungated).
        Returns the predecessor's result if a gate exists.
        """
        if theory_name in self.UNGATED_THEORIES:
            # Check that ALL ordered theories have passed first
            if self.db:
                row = self.db.fetch_one(
                    """SELECT COUNT(*) as validated FROM conspiracy.processing_status
                       WHERE theory_name = ANY(%s) AND status = 'validated'""",
                    (self.PROCESSING_ORDER,)
                )
                if row and row['validated'] < len(self.PROCESSING_ORDER):
                    return ValidationResult(
                        theory_name="gate_check",
                        status="failed",
                        gap_analysis={"reason": "Not all ordered theories validated yet"}
                    )
            return None

        if theory_name not in self.PROCESSING_ORDER:
            return None

        idx = self.PROCESSING_ORDER.index(theory_name)
        if idx == 0:
            return None  # First theory has no predecessor

        predecessor = self.PROCESSING_ORDER[idx - 1]

        if self.db:
            row = self.db.fetch_one(
                "SELECT status, match_rate FROM conspiracy.processing_status WHERE theory_name = %s",
                (predecessor,)
            )
            if row:
                return ValidationResult(
                    theory_name=predecessor,
                    status=row['status'],
                    match_rate=row['match_rate'] or 0.0,
                )

        return None

    def _run_validation(self, theory_name: str, result: ValidationResult) -> ValidationResult:
        """Run the actual validation processing.
        
        In production, this invokes the full agent chain on all documents
        in the theory dataset. Here we outline the logic.
        """
        # Count total signatures in taxonomy
        total_signatures = 0
        if self.db:
            row = self.db.fetch_one(
                "SELECT COUNT(*) as c FROM conspiracy.signatures WHERE status != 'deprecated'"
            )
            total_signatures = row['c'] if row else 0

        # Count documents for this theory
        if self.db:
            row = self.db.fetch_one(
                "SELECT COUNT(*) as c FROM conspiracy.documents WHERE theory_name = %s",
                (theory_name,)
            )
            result.documents_processed = row['c'] if row else 0

        # Count signatures that got at least one match from this theory
        if self.db:
            row = self.db.fetch_one(
                """SELECT COUNT(DISTINCT signature_id) as c FROM conspiracy.signature_matches 
                   WHERE theory_name = %s""",
                (theory_name,)
            )
            result.signatures_matched = row['c'] if row else 0

        # Count cross-theory connections
        if self.db:
            row = self.db.fetch_one(
                """SELECT COUNT(*) as c FROM conspiracy.signature_matches sm1
                   JOIN conspiracy.signature_matches sm2 ON sm1.signature_id = sm2.signature_id
                   WHERE sm1.theory_name = %s AND sm2.theory_name != %s""",
                (theory_name, theory_name)
            )
            result.cross_connections_found = row['c'] if row else 0

        # Calculate match rate
        if total_signatures > 0:
            result.match_rate = result.signatures_matched / total_signatures
        else:
            result.match_rate = 0.0

        # Determine pass/fail
        if result.match_rate >= 0.50:
            result.status = "validated"
        else:
            result.status = "failed"
            result.gap_analysis = self.produce_gap_analysis(theory_name)

        result.completed_at = datetime.now(timezone.utc).isoformat()
        return result

    def produce_validation_report(self, theory_name: str) -> dict:
        """Produce the validation report for a completed theory."""
        if not self.db:
            return {"error": "No database connection"}

        row = self.db.fetch_one(
            "SELECT * FROM conspiracy.processing_status WHERE theory_name = %s",
            (theory_name,)
        )

        if not row:
            return {"error": f"No processing status for {theory_name}"}

        return {
            "theory_name": theory_name,
            "status": row['status'],
            "documents_processed": row['documents_processed'],
            "signatures_matched": row['signatures_matched'],
            "cross_connections_found": row['cross_connections'],
            "match_rate": row['match_rate'],
            "started_at": str(row['started_at']) if row['started_at'] else None,
            "completed_at": str(row['completed_at']) if row['completed_at'] else None,
            "gap_analysis": row['gap_analysis'],
            "passed": (row['match_rate'] or 0) >= 0.50,
        }

    def produce_gap_analysis(self, theory_name: str) -> dict:
        """Identify which Domains lack coverage for a failing theory.
        
        Called when match_rate < 50%. Identifies specific gaps to address.
        """
        if not self.db:
            return {"error": "No database connection"}

        # Find domains with zero matches for this theory
        rows = self.db.fetch_all("""
            SELECT d.name as domain_name, COUNT(sm.match_id) as match_count
            FROM conspiracy.domains d
            LEFT JOIN conspiracy.typologies t ON d.domain_id = t.domain_id
            LEFT JOIN conspiracy.methods m ON t.typology_id = m.typology_id
            LEFT JOIN conspiracy.signatures s ON m.method_id = s.method_id
            LEFT JOIN conspiracy.signature_matches sm ON s.signature_id = sm.signature_id
                AND sm.theory_name = %s
            GROUP BY d.name
            ORDER BY match_count ASC
        """, (theory_name,))

        zero_match_domains = [r['domain_name'] for r in rows if r['match_count'] == 0]
        low_match_domains = [r['domain_name'] for r in rows if 0 < r['match_count'] < 3]

        return {
            "theory_name": theory_name,
            "domains_with_zero_matches": zero_match_domains,
            "domains_with_few_matches": low_match_domains,
            "recommendation": (
                f"Expand signatures in: {', '.join(zero_match_domains[:5])}. "
                f"Consider adding theory-specific indicators for {theory_name}."
            ),
        }

    def get_processing_status_all(self) -> list[dict]:
        """Get processing status for all 10 theories."""
        if not self.db:
            return []

        rows = self.db.fetch_all(
            "SELECT * FROM conspiracy.processing_status ORDER BY theory_name"
        )
        return [dict(row) for row in rows]
