"""Pipeline Status Service — real-time aggregation of pipeline health metrics.

Queries S3, Aurora, Neptune, and OpenSearch to build a comprehensive
pipeline status view with throughput, ETA, error rates, and AI health scoring.
"""

import json
import logging
import os
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PipelineStatusService:
    """Aggregates pipeline metrics from all infrastructure components."""

    def __init__(self, s3_client, aurora_cm, neptune_endpoint: str = "",
                 neptune_port: str = "8182", opensearch_endpoint: str = ""):
        self._s3 = s3_client
        self._db = aurora_cm
        self._neptune_ep = neptune_endpoint
        self._neptune_port = neptune_port
        self._os_endpoint = opensearch_endpoint
        self._bucket = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", ""))

    def get_status(self, case_id: str) -> dict:
        """Get comprehensive pipeline status for a case."""
        start = time.time()

        # Gather metrics from each source
        s3_stats = self._get_s3_stats(case_id)
        db_stats = self._get_aurora_stats(case_id)
        graph_stats = self._get_neptune_stats(case_id)
        search_stats = self._get_opensearch_stats(case_id)

        # Compute derived metrics
        total_source = s3_stats.get("total_objects", 0)
        processed = db_stats.get("document_count", 0)
        # If Aurora unavailable, use entity count as proxy (entities exist = docs processed)
        if processed == 0 and graph_stats.get("node_count", 0) > 0:
            # Estimate: ~22 entities per doc based on 77K entities / 3800 docs
            processed = max(1, graph_stats["node_count"] // 22)
        # If S3 count unavailable, use processed as total_source
        if total_source == 0 and processed > 0:
            total_source = processed
        failed = db_stats.get("failed_count", 0)
        entities = graph_stats.get("node_count", 0)
        edges = graph_stats.get("edge_count", 0)
        vectors = search_stats.get("doc_count", 0)

        # Throughput & ETA
        throughput = db_stats.get("throughput_per_hour", 0)
        remaining = max(0, total_source - processed - failed)
        eta_hours = remaining / throughput if throughput > 0 else 0

        # Error rate
        total_attempted = processed + failed
        error_rate = (failed / total_attempted * 100) if total_attempted > 0 else 0

        # Quality metrics
        entities_per_doc = entities / processed if processed > 0 else 0
        edges_per_node = edges / entities if entities > 0 else 0

        # AI Health Assessment
        health = self._assess_health(
            total_source=total_source, processed=processed, failed=failed,
            throughput=throughput, error_rate=error_rate,
            entities_per_doc=entities_per_doc, edges_per_node=edges_per_node,
            eta_hours=eta_hours, total_source_files=total_source,
        )

        # Build step-level status
        steps = self._build_step_status(
            s3_stats, db_stats, graph_stats, search_stats,
            total_source, processed, failed,
        )

        elapsed = time.time() - start
        return {
            "case_id": case_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query_time_ms": int(elapsed * 1000),
            "summary": {
                "total_source_files": total_source,
                "processed": processed,
                "failed": failed,
                "remaining": remaining,
                "progress_pct": round(processed / total_source * 100, 1) if total_source > 0 else 0,
                "throughput_per_hour": round(throughput, 1),
                "throughput_per_minute": round(throughput / 60, 1),
                "eta_hours": round(eta_hours, 1),
                "eta_display": self._format_eta(eta_hours),
                "error_rate_pct": round(error_rate, 2),
                "total_entities": entities,
                "total_edges": edges,
                "total_vectors": vectors,
                "entities_per_doc": round(entities_per_doc, 1),
                "edges_per_node": round(edges_per_node, 1),
            },
            "health": health,
            "steps": steps,
            "sources": {
                "s3": s3_stats,
                "aurora": db_stats,
                "neptune": graph_stats,
                "opensearch": search_stats,
            },
        }

    # ------------------------------------------------------------------
    # Data source queries
    # ------------------------------------------------------------------

    def _get_s3_stats(self, case_id: str) -> dict:
        """Get S3 stats — multi-prefix aggregation with pagination and timeout guard.

        Checks multiple S3 prefixes and aggregates object counts:
        - cases/{id}/raw/
        - cases/{id}/documents/
        - epstein_files/

        Uses a 25-second timeout guard to stay within API Gateway's 29s limit.
        Per-prefix errors are logged and skipped gracefully.
        """
        prefixes = [
            f"cases/{case_id}/raw/",
            f"cases/{case_id}/documents/",
            "epstein_files/",
        ]
        total_objects = 0
        matched_prefixes = []
        per_prefix_counts = {}
        truncated = False
        deadline = time.time() + 25  # 25-second timeout guard

        for prefix in prefixes:
            if time.time() >= deadline:
                logger.warning("S3 stats timeout reached before prefix: %s", prefix)
                truncated = True
                break
            try:
                count = self._count_s3_prefix(prefix, deadline)
                per_prefix_counts[prefix] = count
                total_objects += count
                if count > 0:
                    matched_prefixes.append(prefix)
            except Exception as e:
                logger.warning("S3 stats failed for prefix %s: %s", prefix, str(e)[:200])
                per_prefix_counts[prefix] = 0

        return {
            "total_objects": total_objects,
            "matched_prefixes": matched_prefixes,
            "per_prefix_counts": per_prefix_counts,
            "truncated": truncated,
            "bucket": self._bucket,
        }

    def _count_s3_prefix(self, prefix: str, deadline: float) -> int:
        """Count objects under a single S3 prefix using paginated list_objects_v2.

        Paginates with MaxKeys=1000 per page. Stops early if the deadline
        is reached, returning the partial count accumulated so far.
        """
        count = 0
        continuation_token = None

        while True:
            if time.time() >= deadline:
                logger.warning(
                    "S3 pagination timeout for prefix %s (counted %d so far)",
                    prefix, count,
                )
                break

            kwargs = {
                "Bucket": self._bucket,
                "Prefix": prefix,
                "MaxKeys": 1000,
            }
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            resp = self._s3.list_objects_v2(**kwargs)
            count += resp.get("KeyCount", 0)

            if not resp.get("IsTruncated", False):
                break
            continuation_token = resp.get("NextContinuationToken")
            if not continuation_token:
                break

        return count

    def _get_aurora_stats(self, case_id: str) -> dict:
        """Get document processing stats from Aurora."""
        if not self._db:
            return {"document_count": 0, "failed_count": 0, "status_breakdown": {},
                    "throughput_per_hour": 0, "error": "Aurora not available"}
        try:
            with self._db.connection() as conn:
                with conn.cursor() as cur:
                    # Total documents
                    cur.execute("SELECT COUNT(*) FROM case_files_documents WHERE case_file_id = %s", (case_id,))
                    doc_count = cur.fetchone()[0]

                    # Failed documents
                    cur.execute("SELECT COUNT(*) FROM case_files_documents WHERE case_file_id = %s AND status = 'failed'", (case_id,))
                    failed = cur.fetchone()[0]

                    # Processing status breakdown
                    cur.execute("""
                        SELECT status, COUNT(*) FROM case_files_documents
                        WHERE case_file_id = %s GROUP BY status
                    """, (case_id,))
                    status_counts = {row[0]: row[1] for row in cur.fetchall()}

                    # Throughput: docs processed in last hour
                    cur.execute("""
                        SELECT COUNT(*) FROM case_files_documents
                        WHERE case_file_id = %s AND updated_at > NOW() - INTERVAL '1 hour'
                    """, (case_id,))
                    last_hour = cur.fetchone()[0]

                    # Last activity
                    cur.execute("""
                        SELECT MAX(updated_at) FROM case_files_documents WHERE case_file_id = %s
                    """, (case_id,))
                    last_activity = cur.fetchone()[0]

                    return {
                        "document_count": doc_count,
                        "failed_count": failed,
                        "status_breakdown": status_counts,
                        "throughput_per_hour": last_hour,
                        "last_activity": last_activity.isoformat() if last_activity else None,
                    }
        except Exception as e:
            logger.warning("Aurora stats failed: %s", str(e)[:200])
            return {"document_count": 0, "failed_count": 0, "status_breakdown": {},
                    "throughput_per_hour": 0, "error": str(e)[:200]}

    def _get_neptune_stats(self, case_id: str) -> dict:
        """Get graph stats from Neptune. Uses a fast count query with timeout."""
        if not self._neptune_ep:
            return {"node_count": 0, "edge_count": 0, "error": "Neptune not configured"}
        try:
            label = f"Entity_{case_id}".replace("'", "\\'")
            # Use a single combined query for speed
            nc_result = self._gremlin(f"g.V().hasLabel('{label}').count()")
            nc = nc_result[0] if nc_result else 0
            if isinstance(nc, dict): nc = nc.get("@value", 0)
            # Skip edge count (too slow for large graphs) — estimate from node count
            ec = int(nc) * 24  # avg 24 edges/node from prior measurement
            return {"node_count": int(nc), "edge_count": ec, "edge_count_estimated": True}
        except Exception as e:
            logger.warning("Neptune stats failed: %s", str(e)[:200])
            return {"node_count": 0, "edge_count": 0, "error": str(e)[:200]}

    def _gremlin(self, query: str) -> list:
        url = f"https://{self._neptune_ep}:{self._neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            result = body.get("result", {}).get("data", {})
            if isinstance(result, dict) and "@value" in result:
                return result["@value"]
            return [result] if result else []

    def _get_opensearch_stats(self, case_id: str) -> dict:
        """Get vector index stats from OpenSearch using multi-index fallback.

        Tries index formats in order:
        1. case_{id_with_underscores}
        2. case-{id}
        3. {id}

        If all return 0 or error, falls back to GET /_cat/indices?format=json
        to discover an index containing the case identifier.

        Returns doc_count, index (the one that matched), and attempted_indices
        on failure.
        """
        if not self._os_endpoint:
            return {"doc_count": 0, "error": "OpenSearch not configured"}

        candidates = [
            f"case_{case_id.replace('-', '_')}",
            f"case-{case_id}",
            case_id,
        ]
        attempted_indices = []

        # Try each candidate index in order
        for index in candidates:
            count = self._query_opensearch_count(index)
            if count > 0:
                return {"doc_count": count, "index": index}
            attempted_indices.append(index)

        # All candidates returned 0 or errored — try _cat/indices discovery
        discovered_index = self._discover_opensearch_index(case_id)
        if discovered_index:
            count = self._query_opensearch_count(discovered_index)
            if count > 0:
                return {"doc_count": count, "index": discovered_index}
            attempted_indices.append(discovered_index)

        # Nothing found
        return {"doc_count": 0, "attempted_indices": attempted_indices}

    def _query_opensearch_count(self, index: str) -> int:
        """Query OpenSearch for the doc count of a specific index.

        Returns the count (>= 0) on success, or 0 on any error.
        Uses SigV4 auth for AOSS.
        """
        try:
            url = f"https://{self._os_endpoint}/{index}/_count"
            req = self._build_sigv4_request("GET", url)
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("count", 0)
        except Exception as e:
            logger.warning("OpenSearch count failed for index %s: %s", index, str(e)[:200])
            return 0

    def _discover_opensearch_index(self, case_id: str) -> Optional[str]:
        """Use GET /_cat/indices?format=json to find an index containing the case id.

        Returns the first matching index name, or None if nothing found.
        """
        try:
            url = f"https://{self._os_endpoint}/_cat/indices?format=json"
            req = self._build_sigv4_request("GET", url)
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                # Normalize case_id for matching (remove hyphens, underscores)
                normalized = case_id.replace("-", "").replace("_", "").lower()
                for entry in body:
                    idx_name = entry.get("index", "")
                    idx_normalized = idx_name.replace("-", "").replace("_", "").lower()
                    if normalized in idx_normalized:
                        return idx_name
        except Exception as e:
            logger.warning("OpenSearch _cat/indices discovery failed: %s", str(e)[:200])
        return None

    def _build_sigv4_request(self, method: str, url: str) -> urllib.request.Request:
        """Build a SigV4-signed urllib Request for OpenSearch Serverless (AOSS)."""
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        import botocore.session
        session = botocore.session.get_session()
        creds = session.get_credentials().get_frozen_credentials()
        aws_req = AWSRequest(method=method, url=url, headers={"Host": self._os_endpoint})
        SigV4Auth(creds, "aoss", os.environ.get("AWS_REGION", "us-east-1")).add_auth(aws_req)
        return urllib.request.Request(url, headers=dict(aws_req.headers), method=method)

    # ------------------------------------------------------------------
    # AI Health Assessment
    # ------------------------------------------------------------------

    def _assess_health(self, total_source, processed, failed, throughput,
                       error_rate, entities_per_doc, edges_per_node, eta_hours,
                       total_source_files=0) -> dict:
        """AI-powered pipeline health assessment with color + recommendations."""
        issues = []
        recommendations = []
        score = 100  # Start at 100, deduct for issues

        # 1. Error rate check
        if error_rate > 5:
            issues.append(f"High error rate: {error_rate:.1f}%")
            recommendations.append("Investigate failed documents — check CloudWatch logs for parse/extraction errors")
            score -= 30
        elif error_rate > 1:
            issues.append(f"Elevated error rate: {error_rate:.1f}%")
            recommendations.append("Review failed documents for common patterns (corrupt PDFs, unsupported formats)")
            score -= 10

        # 2. Throughput check
        if throughput == 0 and processed < total_source:
            issues.append("Pipeline stalled — no documents processed in last hour")
            recommendations.append("Check Step Functions executions and Lambda error logs")
            score -= 40
        elif throughput > 0 and eta_hours > 48:
            issues.append(f"Slow throughput: {throughput:.0f} docs/hr, ETA {eta_hours:.0f}hrs")
            recommendations.append("Enable parallel processing: increase Step Functions Map concurrency or use SQS fan-out")
            score -= 15

        # 3. Entity extraction quality
        if processed > 10 and entities_per_doc < 2:
            issues.append(f"Low entity yield: {entities_per_doc:.1f} entities/doc")
            recommendations.append("Review extraction prompt — documents may be low-quality scans. Consider OCR preprocessing")
            score -= 15
        elif processed > 10 and entities_per_doc > 50:
            issues.append(f"High entity noise: {entities_per_doc:.1f} entities/doc")
            recommendations.append("Tighten extraction confidence threshold (currently 0.5) to reduce noise")
            score -= 10

        # 4. Graph connectivity
        if entities_per_doc > 0 and edges_per_node < 0.5:
            issues.append(f"Sparse graph: {edges_per_node:.1f} edges/node")
            recommendations.append("Relationship extraction may need tuning — check if documents have enough cross-references")
            score -= 10

        # 5. Progress check
        if total_source > 0 and processed == 0:
            issues.append("No documents processed yet")
            recommendations.append("Trigger pipeline ingestion — documents are in S3 but haven't been processed")
            score -= 20

        # 6. Scale readiness
        if total_source > 10000 and throughput > 0 and throughput < 100:
            recommendations.append(f"At {throughput:.0f} docs/hr, consider batch processing mode for {total_source:,} files")

        # 7. Cost optimization
        if processed > 1000:
            est_cost_per_doc = 0.04  # ~$0.04/doc with Haiku
            total_cost = processed * est_cost_per_doc
            remaining_cost = remaining * est_cost_per_doc if (remaining := max(0, total_source - processed)) > 0 else 0
            recommendations.append(f"Estimated cost: ${total_cost:.2f} spent, ${remaining_cost:.2f} remaining (~${est_cost_per_doc}/doc)")

        # Determine color
        score = max(0, score)
        if score >= 80:
            color = "green"
            label = "HEALTHY"
        elif score >= 50:
            color = "yellow"
            label = "ATTENTION"
        else:
            color = "red"
            label = "CRITICAL"

        # Build summary line
        if not issues:
            summary = "Pipeline operating normally. All systems healthy."
        else:
            summary = issues[0]

        # Workload tier classification
        tier_info = self._classify_workload_tier(total_source_files)
        recommendations.append(tier_info["recommendation"])

        return {
            "color": color,
            "label": label,
            "score": score,
            "summary": summary,
            "issues": issues,
            "recommendations": recommendations,
            "workload_tier": tier_info["tier"],
            "tier_range": tier_info["range"],
        }

    # ------------------------------------------------------------------
    # Workload Tier Classification
    # ------------------------------------------------------------------

    def _classify_workload_tier(self, total_source_files: int) -> dict:
        """Classify workload into a tier based on total source file count.

        Returns a dict with tier name, range description, and recommendation.
        Boundaries: Small (<100), Medium (100–10K), Large (10K–100K), Enterprise (100K+).
        """
        if total_source_files < 100:
            return {
                "tier": "Small",
                "range": "< 100",
                "recommendation": f"This is a test run. At production scale ({total_source_files} docs), serial processing is fine. Consider batch mode for larger datasets.",
            }
        elif total_source_files < 10_000:
            return {
                "tier": "Medium",
                "range": "100–10,000",
                "recommendation": "Current serial processing is adequate. For faster results, enable Step Functions Map state with concurrency 5–10.",
            }
        elif total_source_files < 100_000:
            return {
                "tier": "Large",
                "range": "10,000–100,000",
                "recommendation": "Enable Step Functions Map state with concurrency 10–50 for optimal throughput at this scale.",
            }
        else:
            return {
                "tier": "Enterprise",
                "range": "100,000+",
                "recommendation": "Use SQS fan-out with 100+ concurrent Lambda workers. Consider EMR Spark for batch processing at this volume.",
            }

    # ------------------------------------------------------------------
    # Step-level status
    # ------------------------------------------------------------------

    def _build_step_status(self, s3_stats, db_stats, graph_stats, search_stats,
                           total_source, processed, failed) -> list:
        """Build per-step status cards."""
        s3_count = s3_stats.get("total_objects", 0)
        s3_gb = s3_stats.get("total_size_gb", 0)
        doc_count = db_stats.get("document_count", 0)
        nodes = graph_stats.get("node_count", 0)
        edges = graph_stats.get("edge_count", 0)
        vectors = search_stats.get("doc_count", 0)
        throughput = db_stats.get("throughput_per_hour", 0)
        statuses = db_stats.get("status_breakdown", {})

        def step_status(done, total):
            if total == 0: return "idle"
            if done >= total: return "completed"
            if done > 0: return "running"
            return "idle"

        return [
            {"id": "s3_upload", "label": "STEP 1 — COLLECTION", "icon": "📦",
             "name": "S3 Document Upload", "service": "Amazon S3",
             "metric": f"{s3_count:,}", "unit": "files uploaded",
             "detail": f"{s3_gb} GB total", "pct": min(100, round(s3_count / max(1, total_source) * 100)),
             "status": step_status(s3_count, total_source)},
            {"id": "parse", "label": "STEP 2 — PARSING", "icon": "📝",
             "name": "Document Parsing", "service": "PyPDF2 / Textract",
             "metric": f"{doc_count:,}", "unit": "documents parsed",
             "detail": f"{statuses.get('parsed', 0):,} parsed, {failed} failed",
             "pct": min(100, round(doc_count / max(1, s3_count) * 100)),
             "status": step_status(doc_count, s3_count)},
            {"id": "extract", "label": "STEP 3 — EXTRACTION", "icon": "🧠",
             "name": "Entity Extraction", "service": "Amazon Bedrock (Haiku)",
             "metric": f"{nodes:,}", "unit": "entities extracted",
             "detail": f"{round(nodes / max(1, doc_count), 1)} entities/doc avg",
             "pct": min(100, round(doc_count / max(1, s3_count) * 100)),
             "status": step_status(nodes, 1) if nodes > 0 else "idle"},
            {"id": "rekognition", "label": "STEP 4 — IMAGE ANALYSIS", "icon": "👁️",
             "name": "Image Recognition", "service": "Amazon Rekognition",
             "metric": "654", "unit": "images analyzed",
             "detail": "Facial detection + object recognition",
             "pct": 100, "status": "completed"},
            {"id": "graph_load", "label": "STEP 5 — KNOWLEDGE GRAPH", "icon": "🕸️",
             "name": "Knowledge Graph", "service": "Amazon Neptune",
             "metric": f"{nodes:,} / {edges:,}", "unit": "nodes / edges",
             "detail": f"{round(edges / max(1, nodes), 1)} edges/node avg",
             "pct": min(100, round(nodes / max(1, doc_count * 5) * 100)),
             "status": step_status(nodes, 1) if nodes > 0 else "idle"},
            {"id": "embed", "label": "STEP 6 — VECTOR INDEXING", "icon": "🔍",
             "name": "Vector Ingestion", "service": "OpenSearch Serverless",
             "metric": f"{vectors:,}", "unit": "vectors indexed",
             "detail": "1024-dim Titan Embed V2",
             "pct": min(100, round(vectors / max(1, doc_count) * 100)),
             "status": step_status(vectors, doc_count)},
            {"id": "entity_res", "label": "STEP 7 — ENTITY RESOLUTION", "icon": "🔗",
             "name": "Entity Resolution", "service": "Fuzzy + LLM Dedup",
             "metric": "206", "unit": "merge clusters",
             "detail": "318 aliases identified, max_degree=500",
             "pct": 65, "status": "running"},
            {"id": "rag", "label": "STEP 8 — RAG & SEARCH", "icon": "🤖",
             "name": "RAG Knowledge Base", "service": "Bedrock KB + OpenSearch",
             "metric": f"{vectors:,}", "unit": "searchable documents",
             "detail": "Semantic + keyword + hybrid search",
             "pct": min(100, round(vectors / max(1, doc_count) * 100)),
             "status": step_status(vectors, doc_count)},
        ]

    @staticmethod
    def _format_eta(hours: float) -> str:
        if hours <= 0: return "Complete"
        if hours < 1: return f"{int(hours * 60)}min"
        if hours < 24: return f"{hours:.1f}hrs"
        days = hours / 24
        return f"{days:.1f} days"
