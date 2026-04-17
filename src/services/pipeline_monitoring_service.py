"""Pipeline Monitoring Service — real-time pipeline status, run metrics,
and per-step drill-down details.

Responsible for:
- Querying current pipeline execution status (step, docs processed/remaining, elapsed)
- Aggregating entity quality metrics, processing speed, error rates, cost estimates
- Listing recent pipeline runs for a case
- Per-step detail drill-down: step-specific metrics, config with origin annotations,
  recent runs, and error log
"""

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from db.connection import ConnectionManager
from models.pipeline_config import (
    PipelineRunMetrics,
    PipelineRunSummary,
    PipelineStatus,
    StepDetail,
)


# ---------------------------------------------------------------------------
# Bedrock pricing table (USD per token)
# ---------------------------------------------------------------------------

BEDROCK_PRICING = {
    "anthropic.claude-3-sonnet-20240229-v1:0": {
        "input": 3.0 / 1_000_000,
        "output": 15.0 / 1_000_000,
    },
    "anthropic.claude-3-haiku-20240307-v1:0": {
        "input": 0.25 / 1_000_000,
        "output": 1.25 / 1_000_000,
    },
    "amazon.titan-embed-text-v1": {
        "input": 0.1 / 1_000_000,
        "output": 0.0,
    },
}

DEFAULT_RATES = {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000}


def estimate_bedrock_cost(
    model_id: str, input_tokens: int, output_tokens: int
) -> float:
    """Estimate cost in USD based on Bedrock pricing.

    Uses known per-token rates for common models; falls back to
    Claude 3 Sonnet rates for unrecognised model IDs.
    """
    rates = BEDROCK_PRICING.get(model_id, DEFAULT_RATES)
    return input_tokens * rates["input"] + output_tokens * rates["output"]


class PipelineMonitoringService:
    """Real-time pipeline monitoring, run metrics, and step drill-down."""

    def __init__(self, aurora_cm: ConnectionManager) -> None:
        self.aurora_cm = aurora_cm

    # ------------------------------------------------------------------
    # get_pipeline_status
    # ------------------------------------------------------------------

    def get_pipeline_status(self, case_id: str) -> PipelineStatus:
        """Current execution status for a case.

        Queries the most recent pipeline_runs row and its
        pipeline_step_results to determine the active step,
        documents processed / remaining, and elapsed time.
        """
        with self.aurora_cm.cursor() as cur:
            # Most recent run for this case
            cur.execute(
                """
                SELECT run_id, status, document_count, step_statuses,
                       started_at, completed_at
                FROM pipeline_runs
                WHERE case_id = %s
                ORDER BY started_at DESC NULLS LAST
                LIMIT 1
                """,
                (case_id,),
            )
            run_row = cur.fetchone()

        if run_row is None:
            return PipelineStatus(
                case_id=UUID(case_id) if isinstance(case_id, str) else case_id,
                status="idle",
            )

        run_id = run_row[0]
        run_status = run_row[1]
        document_count = run_row[2] or 0
        step_statuses = (
            run_row[3]
            if isinstance(run_row[3], dict)
            else json.loads(run_row[3] or "{}")
        )
        started_at = run_row[4]
        completed_at = run_row[5]

        # Compute elapsed seconds
        elapsed_seconds: Optional[float] = None
        if started_at is not None:
            end = completed_at or datetime.now(timezone.utc)
            elapsed_seconds = (end - started_at).total_seconds()

        # Count completed docs from step results
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(DISTINCT document_id)
                FROM pipeline_step_results
                WHERE run_id = %s AND status = 'completed'
                """,
                (str(run_id),),
            )
            docs_processed = cur.fetchone()[0] or 0

        docs_remaining = max(document_count - docs_processed, 0)

        # Determine current step from step_statuses or step results
        current_step = self._determine_current_step(step_statuses)

        return PipelineStatus(
            case_id=UUID(case_id) if isinstance(case_id, str) else case_id,
            current_step=current_step,
            docs_processed=docs_processed,
            docs_remaining=docs_remaining,
            elapsed_seconds=elapsed_seconds,
            status=run_status,
            step_statuses=step_statuses,
        )

    # ------------------------------------------------------------------
    # get_run_metrics
    # ------------------------------------------------------------------

    def get_run_metrics(self, run_id: str) -> PipelineRunMetrics:
        """Aggregate entity quality metrics, processing speed, error rates,
        and cost estimate for a pipeline run.
        """
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, total_entities, total_relationships,
                       entity_type_counts, avg_confidence, noise_ratio,
                       docs_per_minute, avg_entities_per_doc,
                       failed_doc_count, failure_rate,
                       estimated_cost_usd, total_input_tokens,
                       total_output_tokens, quality_score,
                       quality_breakdown,
                       document_count, started_at, completed_at,
                       effective_config
                FROM pipeline_runs
                WHERE run_id = %s
                """,
                (run_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise ValueError(f"Pipeline run {run_id} not found")

        entity_type_counts = (
            row[3] if isinstance(row[3], dict)
            else json.loads(row[3]) if row[3] else None
        )
        quality_breakdown = (
            row[14] if isinstance(row[14], dict)
            else json.loads(row[14]) if row[14] else None
        )

        # Compute cost estimate if tokens are available but cost is not yet stored
        estimated_cost = row[10]
        if estimated_cost is None and row[11] is not None:
            effective_config = (
                row[18] if isinstance(row[18], dict)
                else json.loads(row[18]) if row[18] else {}
            )
            model_id = (
                effective_config.get("extract", {})
                .get("llm_model_id", "anthropic.claude-3-sonnet-20240229-v1:0")
            )
            estimated_cost = estimate_bedrock_cost(
                model_id, row[11] or 0, row[12] or 0
            )

        # Compute docs_per_minute if not stored
        docs_per_minute = row[6]
        if docs_per_minute is None and row[15] and row[16] and row[17]:
            duration_minutes = (row[17] - row[16]).total_seconds() / 60.0
            if duration_minutes > 0:
                docs_per_minute = row[15] / duration_minutes

        return PipelineRunMetrics(
            run_id=UUID(str(row[0])),
            total_entities=row[1],
            total_relationships=row[2],
            entity_type_counts=entity_type_counts,
            avg_confidence=row[4],
            noise_ratio=row[5],
            docs_per_minute=round(docs_per_minute, 2) if docs_per_minute else None,
            avg_entities_per_doc=row[7],
            failed_doc_count=row[8] or 0,
            failure_rate=row[9],
            estimated_cost_usd=(
                round(estimated_cost, 6) if estimated_cost is not None else None
            ),
            total_input_tokens=row[11],
            total_output_tokens=row[12],
            quality_score=row[13],
            quality_breakdown=quality_breakdown,
        )

    # ------------------------------------------------------------------
    # list_runs
    # ------------------------------------------------------------------

    def list_runs(
        self, case_id: str, limit: int = 20
    ) -> list[PipelineRunSummary]:
        """List recent pipeline runs for a case, ordered by started_at desc."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, case_id, config_version, is_sample_run,
                       document_count, status, started_at, completed_at,
                       quality_score
                FROM pipeline_runs
                WHERE case_id = %s
                ORDER BY started_at DESC NULLS LAST
                LIMIT %s
                """,
                (case_id, limit),
            )
            rows = cur.fetchall()

        return [self._row_to_run_summary(row) for row in rows]

    # ------------------------------------------------------------------
    # get_step_details
    # ------------------------------------------------------------------

    def get_step_details(self, run_id: str, step_name: str) -> StepDetail:
        """Per-step drill-down: metrics, config values with origin
        annotations, recent runs, and error log.
        """
        # Fetch step results for this run + step
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT status, duration_ms, metrics_json, error_message,
                       document_id, started_at, completed_at
                FROM pipeline_step_results
                WHERE run_id = %s AND step_name = %s
                ORDER BY started_at DESC NULLS LAST
                """,
                (run_id, step_name),
            )
            step_rows = cur.fetchall()

        # Aggregate step-specific metrics
        metrics = self._aggregate_step_metrics(step_name, step_rows)

        # Determine service status
        statuses = [r[0] for r in step_rows]
        if "running" in statuses:
            service_status = "Active"
        elif step_rows:
            service_status = "Active"
        else:
            service_status = "Inactive"

        item_count = len(step_rows)

        # Fetch effective config + origins for this run
        config_values, config_origins = self._get_step_config(run_id, step_name)

        # Recent runs for this step (last 5 across all runs for the same case)
        recent_runs = self._get_recent_step_runs(run_id, step_name)

        # Recent errors (last 10)
        recent_errors = self._get_recent_errors(run_id, step_name)

        return StepDetail(
            step_name=step_name,
            service_status=service_status,
            item_count=item_count,
            metrics=metrics,
            config_values=config_values,
            config_origins=config_origins,
            recent_runs=recent_runs,
            recent_errors=recent_errors,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_current_step(step_statuses: dict) -> Optional[str]:
        """Return the name of the currently running step, or None."""
        step_order = ["parse", "extract", "embed", "graph_load", "store_artifact"]
        for step in step_order:
            status = step_statuses.get(step)
            if status == "running":
                return step
        # If nothing is running, return the last completed step
        for step in reversed(step_order):
            if step_statuses.get(step) == "completed":
                return step
        return None

    @staticmethod
    def _aggregate_step_metrics(step_name: str, step_rows: list) -> dict:
        """Compute step-specific aggregate metrics from step result rows.

        Each row: (status, duration_ms, metrics_json, error_message,
                   document_id, started_at, completed_at)
        """
        if not step_rows:
            return {}

        completed = [r for r in step_rows if r[0] == "completed"]
        failed = [r for r in step_rows if r[0] == "failed"]
        durations = [r[1] for r in completed if r[1] is not None]
        avg_duration_ms = (
            sum(durations) / len(durations) if durations else None
        )

        # Merge all per-document metrics_json blobs
        all_metrics = []
        for r in step_rows:
            m = r[2] if isinstance(r[2], dict) else json.loads(r[2] or "{}")
            all_metrics.append(m)

        base = {
            "total_documents": len(step_rows),
            "completed": len(completed),
            "failed": len(failed),
            "avg_duration_ms": round(avg_duration_ms, 1) if avg_duration_ms else None,
        }

        if step_name == "parse":
            ocr_count = sum(1 for m in all_metrics if m.get("ocr_used"))
            table_count = sum(1 for m in all_metrics if m.get("tables_extracted", 0) > 0)
            base.update({"ocr_usage_count": ocr_count, "table_extraction_count": table_count})

        elif step_name == "extract":
            total_entities = sum(m.get("entity_count", 0) for m in all_metrics)
            total_input = sum(m.get("input_tokens", 0) for m in all_metrics)
            total_output = sum(m.get("output_tokens", 0) for m in all_metrics)
            confidences = [
                c for m in all_metrics for c in (m.get("confidences") or [])
            ]
            avg_conf = (
                sum(confidences) / len(confidences) if confidences else None
            )
            # Entity type distribution
            type_counts: dict[str, int] = {}
            for m in all_metrics:
                for t, cnt in (m.get("entity_type_counts") or {}).items():
                    type_counts[t] = type_counts.get(t, 0) + cnt

            base.update({
                "entities_extracted": total_entities,
                "entity_type_distribution": type_counts,
                "avg_confidence": round(avg_conf, 4) if avg_conf is not None else None,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "estimated_cost_usd": round(
                    estimate_bedrock_cost(
                        "anthropic.claude-3-sonnet-20240229-v1:0",
                        total_input,
                        total_output,
                    ),
                    6,
                ),
            })

        elif step_name == "embed":
            total_embeddings = sum(m.get("embeddings_generated", 0) for m in all_metrics)
            dimensions = next(
                (m.get("dimensions") for m in all_metrics if m.get("dimensions")),
                None,
            )
            base.update({
                "embeddings_generated": total_embeddings,
                "dimensions": dimensions,
            })

        elif step_name == "graph_load":
            total_nodes = sum(m.get("nodes_loaded", 0) for m in all_metrics)
            total_edges = sum(m.get("edges_loaded", 0) for m in all_metrics)
            strategy = next(
                (m.get("load_strategy") for m in all_metrics if m.get("load_strategy")),
                None,
            )
            base.update({
                "nodes_loaded": total_nodes,
                "edges_loaded": total_edges,
                "load_strategy": strategy,
            })

        elif step_name == "store_artifact":
            total_artifacts = sum(m.get("artifacts_stored", 0) for m in all_metrics)
            base.update({"artifacts_stored": total_artifacts})

        return base

    def _get_step_config(
        self, run_id: str, step_name: str
    ) -> tuple[dict, dict]:
        """Return (config_values, config_origins) for a step from the run's
        effective_config stored in pipeline_runs.
        """
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                "SELECT effective_config FROM pipeline_runs WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()

        if row is None:
            return {}, {}

        effective_config = (
            row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
        )
        config_values = effective_config.get(step_name, {})

        # Build origin annotations — we don't have the original system default
        # at this point, so mark all values as "effective" (the API layer can
        # enrich with full origin data via ConfigResolutionService if needed).
        config_origins = {
            f"{step_name}.{k}": "effective"
            for k in config_values
            if not isinstance(config_values[k], dict)
        }
        # Flatten nested dicts one level
        for k, v in config_values.items():
            if isinstance(v, dict):
                for sub_k in v:
                    config_origins[f"{step_name}.{k}.{sub_k}"] = "effective"

        return config_values, config_origins

    def _get_recent_step_runs(
        self, run_id: str, step_name: str, limit: int = 5
    ) -> list[dict]:
        """Last N runs for this step across the same case."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT pr.run_id, pr.document_count,
                       psr.status,
                       COUNT(*) AS doc_count,
                       SUM(CASE WHEN psr.status = 'completed' THEN 1 ELSE 0 END) AS success,
                       SUM(CASE WHEN psr.status = 'failed' THEN 1 ELSE 0 END) AS failures,
                       AVG(psr.duration_ms) AS avg_duration_ms
                FROM pipeline_runs pr
                JOIN pipeline_step_results psr ON psr.run_id = pr.run_id
                WHERE pr.case_id = (
                    SELECT case_id FROM pipeline_runs WHERE run_id = %s
                )
                AND psr.step_name = %s
                GROUP BY pr.run_id, pr.document_count, psr.status
                ORDER BY pr.started_at DESC NULLS LAST
                LIMIT %s
                """,
                (run_id, step_name, limit),
            )
            rows = cur.fetchall()

        return [
            {
                "run_id": str(r[0]),
                "document_count": r[1],
                "status": r[2],
                "doc_count": r[3],
                "success_count": r[4],
                "failure_count": r[5],
                "avg_duration_ms": round(r[6], 1) if r[6] else None,
            }
            for r in rows
        ]

    def _get_recent_errors(
        self, run_id: str, step_name: str, limit: int = 10
    ) -> list[dict]:
        """Last N errors for this step in this run."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT document_id, error_message, started_at
                FROM pipeline_step_results
                WHERE run_id = %s AND step_name = %s AND status = 'failed'
                ORDER BY started_at DESC NULLS LAST
                LIMIT %s
                """,
                (run_id, step_name, limit),
            )
            rows = cur.fetchall()

        return [
            {
                "document_id": r[0],
                "error_message": r[1],
                "timestamp": r[2].isoformat() if r[2] else None,
            }
            for r in rows
        ]

    @staticmethod
    def _row_to_run_summary(row) -> PipelineRunSummary:
        """Convert a database row tuple to a PipelineRunSummary model."""
        return PipelineRunSummary(
            run_id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
            case_id=row[1] if isinstance(row[1], UUID) else UUID(str(row[1])),
            config_version=row[2],
            is_sample_run=row[3],
            document_count=row[4] or 0,
            status=row[5],
            started_at=row[6],
            completed_at=row[7],
            quality_score=row[8],
        )

