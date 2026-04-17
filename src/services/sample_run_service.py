"""Sample Run Service — manages sample pipeline runs and quality scoring.

Responsible for:
- Starting sample pipeline runs against a subset of documents (1-50)
- Retrieving and listing sample runs
- Comparing two sample run snapshots (entity diff + quality deltas)
- Computing the Pipeline Quality Score from snapshot metrics
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from db.connection import ConnectionManager
from models.entity import EntityType
from models.pipeline_config import (
    QualityScore,
    SampleRun,
    SampleRunComparison,
    SampleRunSnapshot,
)
from services.config_resolution_service import ConfigResolutionService

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")

MIN_DOCUMENTS = 1
MAX_DOCUMENTS = 50


class SampleRunService:
    """Manages sample pipeline runs and quality scoring."""

    def __init__(
        self,
        aurora_cm: ConnectionManager,
        sf_client,
        config_resolution: ConfigResolutionService,
    ) -> None:
        self.aurora_cm = aurora_cm
        self.sf_client = sf_client
        self.config_resolution = config_resolution

    def start_sample_run(
        self, case_id: str, document_ids: list[str], created_by: str
    ) -> SampleRun:
        """Start a Step Functions execution in sample mode.

        Validates 1-50 document IDs, resolves effective config, starts
        the pipeline with sample_mode=true, and inserts a pipeline_runs record.

        Raises ValueError if document_ids is empty or exceeds 50.
        """
        if not document_ids or len(document_ids) < MIN_DOCUMENTS:
            raise ValueError("At least 1 document ID is required for a sample run")
        if len(document_ids) > MAX_DOCUMENTS:
            raise ValueError(
                f"Sample runs support at most {MAX_DOCUMENTS} documents, "
                f"got {len(document_ids)}"
            )

        # Resolve effective config for this case
        effective_config = self.config_resolution.resolve_effective_config(case_id)

        run_id = uuid.uuid4()
        execution_name = f"sample-{case_id[:8]}-{uuid.uuid4().hex[:8]}"

        # Start Step Functions execution with sample_mode flag
        sfn_input = {
            "case_id": case_id,
            "sample_mode": True,
            "document_ids": document_ids,
            "upload_result": {
                "document_ids": document_ids,
                "document_count": len(document_ids),
            },
            "effective_config": effective_config.effective_json,
        }

        execution = self.sf_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(sfn_input, default=str),
        )

        now = datetime.now(timezone.utc)

        # Insert pipeline_runs record
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline_runs
                    (run_id, case_id, config_version, effective_config,
                     is_sample_run, document_ids, document_count,
                     status, started_at, created_by, sf_execution_arn)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(run_id),
                    case_id,
                    effective_config.config_version or 0,
                    json.dumps(effective_config.effective_json),
                    True,
                    document_ids,
                    len(document_ids),
                    "running",
                    now,
                    created_by,
                    execution.get("executionArn", ""),
                ),
            )

        return SampleRun(
            run_id=run_id,
            case_id=uuid.UUID(case_id) if isinstance(case_id, str) else case_id,
            config_version=effective_config.config_version or 0,
            document_ids=document_ids,
            status="running",
            started_at=now,
            completed_at=None,
            created_by=created_by,
        )

    def get_sample_run(self, run_id: str) -> SampleRun:
        """Get sample run details by run_id.

        Raises ValueError if not found.
        """
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, case_id, config_version, document_ids,
                       status, started_at, completed_at, created_by
                FROM pipeline_runs
                WHERE run_id = %s AND is_sample_run = TRUE
                """,
                (run_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise ValueError(f"Sample run {run_id} not found")

        return self._row_to_sample_run(row)

    def list_sample_runs(self, case_id: str) -> list[SampleRun]:
        """List all sample runs for a case, ordered by started_at desc."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, case_id, config_version, document_ids,
                       status, started_at, completed_at, created_by
                FROM pipeline_runs
                WHERE case_id = %s AND is_sample_run = TRUE
                ORDER BY started_at DESC
                """,
                (case_id,),
            )
            rows = cur.fetchall()

        return [self._row_to_sample_run(row) for row in rows]

    def compare_runs(
        self, run_id_a: str, run_id_b: str
    ) -> SampleRunComparison:
        """Compute diff between two sample run snapshots.

        Loads snapshots for both runs, computes entity diffs
        (added/removed/changed), relationship changes, and quality deltas.

        Raises ValueError if either snapshot is not found.
        """
        snapshot_a = self._load_snapshot(run_id_a)
        snapshot_b = self._load_snapshot(run_id_b)

        # Build entity lookup by canonical name for diffing
        entities_a = {
            e.get("canonical_name", e.get("name", "")): e
            for e in snapshot_a.entities
        }
        entities_b = {
            e.get("canonical_name", e.get("name", "")): e
            for e in snapshot_b.entities
        }

        names_a = set(entities_a.keys())
        names_b = set(entities_b.keys())

        entities_added = [entities_b[n] for n in sorted(names_b - names_a)]
        entities_removed = [entities_a[n] for n in sorted(names_a - names_b)]

        # Entities present in both but with changes
        entities_changed = []
        for name in sorted(names_a & names_b):
            ea = entities_a[name]
            eb = entities_b[name]
            if (
                ea.get("confidence") != eb.get("confidence")
                or ea.get("entity_type") != eb.get("entity_type")
            ):
                entities_changed.append({
                    "name": name,
                    "before": ea,
                    "after": eb,
                })

        # Relationship changes
        rels_a = {self._rel_key(r): r for r in snapshot_a.relationships}
        rels_b = {self._rel_key(r): r for r in snapshot_b.relationships}
        rel_keys_a = set(rels_a.keys())
        rel_keys_b = set(rels_b.keys())

        relationship_changes = []
        for key in sorted(rel_keys_b - rel_keys_a):
            relationship_changes.append({"change": "added", **rels_b[key]})
        for key in sorted(rel_keys_a - rel_keys_b):
            relationship_changes.append({"change": "removed", **rels_a[key]})
        for key in sorted(rel_keys_a & rel_keys_b):
            if rels_a[key] != rels_b[key]:
                relationship_changes.append({
                    "change": "modified",
                    "before": rels_a[key],
                    "after": rels_b[key],
                })

        # Compute quality scores
        quality_a = self.compute_quality_score(snapshot_a)
        quality_b = self.compute_quality_score(snapshot_b)

        quality_delta = {
            "overall": round(quality_b.overall - quality_a.overall, 1),
            "confidence_avg": round(
                quality_b.confidence_avg - quality_a.confidence_avg, 1
            ),
            "type_diversity": round(
                quality_b.type_diversity - quality_a.type_diversity, 1
            ),
            "relationship_density": round(
                quality_b.relationship_density - quality_a.relationship_density, 1
            ),
            "noise_ratio_score": round(
                quality_b.noise_ratio_score - quality_a.noise_ratio_score, 1
            ),
        }

        return SampleRunComparison(
            run_a=snapshot_a,
            run_b=snapshot_b,
            entities_added=entities_added,
            entities_removed=entities_removed,
            entities_changed=entities_changed,
            relationship_changes=relationship_changes,
            quality_a=quality_a,
            quality_b=quality_b,
            quality_delta=quality_delta,
        )

    @staticmethod
    def compute_quality_score(snapshot: SampleRunSnapshot) -> QualityScore:
        """Compute Pipeline Quality Score from snapshot metrics.

        Weighted formula:
        - confidence_avg:       0.35
        - type_diversity:       0.20
        - relationship_density: 0.25
        - noise_ratio_score:    0.20
        """
        entities = snapshot.entities
        relationships = snapshot.relationships

        # 1. Confidence Average (weight: 0.35)
        confidences = [e["confidence"] for e in entities if "confidence" in e]
        confidence_avg = (
            (sum(confidences) / len(confidences)) * 100 if confidences else 0
        )

        # 2. Type Diversity (weight: 0.20)
        # Ratio of distinct entity types present vs total supported types
        distinct_types = len(set(e.get("entity_type", "") for e in entities))
        total_supported = len(EntityType)  # 14 types
        type_diversity = (distinct_types / total_supported) * 100 if total_supported else 0

        # 3. Relationship Density (weight: 0.25)
        # edges per node, capped at 3.0 for normalization
        node_count = len(entities) if entities else 1
        edge_count = len(relationships)
        raw_density = edge_count / node_count
        relationship_density = min(raw_density / 3.0, 1.0) * 100

        # 4. Noise Ratio Score (weight: 0.20)
        # Inverted: lower noise = higher score
        config = snapshot.quality_metrics.get("config", {})
        threshold = config.get("extract", {}).get("confidence_threshold", 0.5)
        below_threshold = sum(
            1 for e in entities if e.get("confidence", 0) < threshold
        )
        noise_ratio = below_threshold / len(entities) if entities else 0
        noise_ratio_score = (1.0 - noise_ratio) * 100

        overall = (
            confidence_avg * 0.35
            + type_diversity * 0.20
            + relationship_density * 0.25
            + noise_ratio_score * 0.20
        )

        return QualityScore(
            overall=round(overall, 1),
            confidence_avg=round(confidence_avg, 1),
            type_diversity=round(type_diversity, 1),
            relationship_density=round(relationship_density, 1),
            noise_ratio_score=round(noise_ratio_score, 1),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_snapshot(self, run_id: str) -> SampleRunSnapshot:
        """Load a sample run snapshot from Aurora.

        Raises ValueError if not found.
        """
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT snapshot_id, run_id, case_id, config_version,
                       snapshot_name, entities, relationships,
                       quality_metrics, created_at
                FROM sample_run_snapshots
                WHERE run_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (run_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise ValueError(f"Snapshot not found for run {run_id}")

        return SampleRunSnapshot(
            snapshot_id=(
                row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(str(row[0]))
            ),
            run_id=(
                row[1] if isinstance(row[1], uuid.UUID) else uuid.UUID(str(row[1]))
            ),
            case_id=(
                row[2] if isinstance(row[2], uuid.UUID) else uuid.UUID(str(row[2]))
            ),
            config_version=row[3],
            snapshot_name=row[4],
            entities=row[5] if isinstance(row[5], list) else json.loads(row[5]),
            relationships=row[6] if isinstance(row[6], list) else json.loads(row[6]),
            quality_metrics=(
                row[7] if isinstance(row[7], dict) else json.loads(row[7])
            ),
            created_at=row[8],
        )

    @staticmethod
    def _row_to_sample_run(row) -> SampleRun:
        """Convert a database row tuple to a SampleRun model."""
        return SampleRun(
            run_id=(
                row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(str(row[0]))
            ),
            case_id=(
                row[1] if isinstance(row[1], uuid.UUID) else uuid.UUID(str(row[1]))
            ),
            config_version=row[2],
            document_ids=row[3] if isinstance(row[3], list) else list(row[3]),
            status=row[4],
            started_at=row[5],
            completed_at=row[6],
            created_by=row[7],
        )

    @staticmethod
    def _rel_key(rel: dict) -> str:
        """Create a hashable key for a relationship dict."""
        return (
            f"{rel.get('source_entity', '')}|"
            f"{rel.get('relationship_type', '')}|"
            f"{rel.get('target_entity', '')}"
        )

