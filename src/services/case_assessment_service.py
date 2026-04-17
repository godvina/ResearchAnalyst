"""Case Assessment Service — computes case health metrics and AI-generated briefs.

Aggregates data from Neptune (graph metrics), OpenSearch (document counts),
and Aurora (case metadata) to produce case strength scores, evidence coverage,
key subjects, critical leads, and resource recommendations.

Provides:
- get_assessment: full CaseAssessment with all metrics
- generate_brief: AI-generated comprehensive case brief via Bedrock
- _compute_strength_score: deterministic 0-100 from case metrics
- _identify_critical_leads: high-connectivity entities with low doc coverage
- _generate_resource_recommendations: AI-generated actionable bullet points
"""

import json
import logging
import ssl
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)


class CaseAssessmentService:
    """Computes case assessment metrics from Neptune, OpenSearch, and Aurora."""

    def __init__(
        self,
        aurora_cm,
        bedrock_client=None,
        neptune_endpoint: str = "",
        neptune_port: str = "8182",
        opensearch_endpoint: str = "",
    ) -> None:
        self._db = aurora_cm
        self._bedrock = bedrock_client
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port
        self._os_endpoint = opensearch_endpoint

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_assessment(self, case_id: str) -> dict:
        """Aggregate metrics and compute full case assessment."""
        metrics = self._gather_metrics(case_id)
        strength = self._compute_strength_score(metrics)
        coverage = self._compute_evidence_coverage(case_id, metrics)
        subjects = self._get_key_subjects(case_id)
        leads = self._identify_critical_leads(case_id)
        recommendations = self._generate_resource_recommendations(case_id, metrics)
        timeline = self._get_timeline(case_id)

        return {
            "case_id": case_id,
            "strength_score": strength,
            "evidence_coverage": coverage,
            "key_subjects": subjects,
            "critical_leads": leads,
            "resource_recommendations": recommendations,
            "timeline": timeline,
        }

    def generate_brief(self, case_id: str) -> str:
        """Use Bedrock to generate a comprehensive case brief."""
        assessment = self.get_assessment(case_id)

        # Gather document summaries from Aurora
        doc_summaries = []
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT title, source_filename
                FROM documents
                WHERE case_file_id = %s
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (case_id,),
            )
            for row in cur.fetchall():
                doc_summaries.append({"title": row[0], "filename": row[1]})

        prompt = f"""Generate a comprehensive investigative case brief based on the following assessment data.

Case Strength Score: {assessment['strength_score']}/100
Evidence Coverage: {json.dumps(assessment['evidence_coverage'])}
Key Subjects: {json.dumps(assessment['key_subjects'][:5])}
Critical Leads: {json.dumps(assessment['critical_leads'][:5])}
Documents ({len(doc_summaries)} total): {json.dumps(doc_summaries[:10])}

Write a professional case brief suitable for a supervising attorney, covering:
1. Case overview and current status
2. Key findings and evidence summary
3. Persons of interest and their connections
4. Evidence gaps and recommended next steps
5. Resource allocation recommendations"""

        if not self._bedrock:
            return f"Case brief for {case_id} — strength score: {assessment['strength_score']}/100"

        try:
            response = self._bedrock.invoke_model(
                modelId="anthropic.claude-3-sonnet-20240229-v1:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            result = json.loads(response["body"].read())
            return result.get("content", [{}])[0].get("text", "Brief generation failed")
        except Exception as exc:
            logger.exception("Bedrock brief generation failed")
            return f"Brief generation failed: {exc}"

    # ------------------------------------------------------------------
    # Strength Score
    # ------------------------------------------------------------------

    def _compute_strength_score(self, metrics: dict) -> int:
        """Deterministic 0-100 score from case metrics.

        Components (20 points each):
        - Evidence volume: min(doc_count / 100, 1.0) * 20
        - Entity density: min(entity_count / max(doc_count,1) / 5.0, 1.0) * 20
        - Relationship density: min(edge_count / max(node_count,1) / 3.0, 1.0) * 20
        - Document corroboration: min(multi_doc_entities / max(total_entities,1) / 0.5, 1.0) * 20
        - Cross-case connections: min(cross_case_matches / 10, 1.0) * 20
        """
        doc_count = metrics.get("doc_count", 0)
        entity_count = metrics.get("entity_count", 0)
        edge_count = metrics.get("edge_count", 0)
        node_count = metrics.get("node_count", 0)
        multi_doc = metrics.get("multi_doc_entities", 0)
        cross_case = metrics.get("cross_case_matches", 0)

        evidence_vol = min(doc_count / 100, 1.0) * 20
        entity_dens = min(entity_count / max(doc_count, 1) / 5.0, 1.0) * 20
        rel_dens = min(edge_count / max(node_count, 1) / 3.0, 1.0) * 20
        corroboration = min(multi_doc / max(entity_count, 1) / 0.5, 1.0) * 20
        cross = min(cross_case / 10, 1.0) * 20

        return int(round(evidence_vol + entity_dens + rel_dens + corroboration + cross))

    # ------------------------------------------------------------------
    # Evidence Coverage
    # ------------------------------------------------------------------

    def _compute_evidence_coverage(self, case_id: str, metrics: dict) -> dict:
        """Check which investigative elements have supporting evidence."""
        entity_types = metrics.get("entity_type_counts", {})
        return {
            "people": {
                "count": entity_types.get("person", 0),
                "status": "covered" if entity_types.get("person", 0) > 0 else "gap",
            },
            "organizations": {
                "count": entity_types.get("organization", 0),
                "status": "covered" if entity_types.get("organization", 0) > 0 else "gap",
            },
            "financial_connections": {
                "count": entity_types.get("financial_amount", 0) + entity_types.get("account_number", 0),
                "status": "covered" if (entity_types.get("financial_amount", 0) + entity_types.get("account_number", 0)) > 0 else "gap",
            },
            "communication_patterns": {
                "count": entity_types.get("phone_number", 0) + entity_types.get("email", 0),
                "status": "covered" if (entity_types.get("phone_number", 0) + entity_types.get("email", 0)) > 0 else "gap",
            },
            "physical_evidence": {
                "count": entity_types.get("vehicle", 0) + entity_types.get("address", 0),
                "status": "covered" if (entity_types.get("vehicle", 0) + entity_types.get("address", 0)) > 0 else "gap",
            },
            "timeline": {
                "count": entity_types.get("date", 0),
                "status": "covered" if entity_types.get("date", 0) > 0 else "gap",
            },
            "geographic_scope": {
                "count": entity_types.get("location", 0),
                "status": "covered" if entity_types.get("location", 0) > 0 else "gap",
            },
        }

    # ------------------------------------------------------------------
    # Metrics Gathering
    # ------------------------------------------------------------------

    def _gather_metrics(self, case_id: str) -> dict:
        """Gather metrics from Aurora, Neptune, and OpenSearch."""
        metrics: dict = {
            "doc_count": 0,
            "entity_count": 0,
            "edge_count": 0,
            "node_count": 0,
            "multi_doc_entities": 0,
            "cross_case_matches": 0,
            "entity_type_counts": {},
        }

        # Aurora: document count and entity counts
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM documents WHERE case_file_id = %s",
                    (case_id,),
                )
                metrics["doc_count"] = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT entity_type, COUNT(*)
                    FROM entities
                    WHERE case_file_id = %s
                    GROUP BY entity_type
                    """,
                    (case_id,),
                )
                type_counts = {}
                total = 0
                for row in cur.fetchall():
                    type_counts[row[0]] = row[1]
                    total += row[1]
                metrics["entity_type_counts"] = type_counts
                metrics["entity_count"] = total
                metrics["node_count"] = total
        except Exception as exc:
            logger.warning("Failed to gather Aurora metrics: %s", exc)

        # Neptune: edge count and multi-doc entities
        if self._neptune_endpoint:
            try:
                metrics["edge_count"] = self._neptune_count_edges(case_id)
                metrics["multi_doc_entities"] = self._neptune_multi_doc_entities(case_id)
            except Exception as exc:
                logger.warning("Failed to gather Neptune metrics: %s", exc)

        return metrics

    def _neptune_query(self, gremlin: str) -> dict:
        """Execute a Gremlin query against Neptune."""
        url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
        payload = json.dumps({"gremlin": gremlin}).encode()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            return json.loads(resp.read())

    def _neptune_count_edges(self, case_id: str) -> int:
        """Count edges for a case in Neptune."""
        try:
            result = self._neptune_query(
                f"g.E().has('case_id', '{case_id}').count()"
            )
            data = result.get("result", {}).get("data", {})
            values = data.get("@value", [{}])
            if values:
                val = values[0]
                return val.get("@value", val) if isinstance(val, dict) else int(val)
        except Exception:
            pass
        return 0

    def _neptune_multi_doc_entities(self, case_id: str) -> int:
        """Count entities appearing in multiple documents."""
        try:
            result = self._neptune_query(
                f"g.V().has('case_id', '{case_id}').where(outE('mentioned_in').count().is(gt(1))).count()"
            )
            data = result.get("result", {}).get("data", {})
            values = data.get("@value", [{}])
            if values:
                val = values[0]
                return val.get("@value", val) if isinstance(val, dict) else int(val)
        except Exception:
            pass
        return 0

    # ------------------------------------------------------------------
    # Key Subjects
    # ------------------------------------------------------------------

    def _get_key_subjects(self, case_id: str) -> list[dict]:
        """Top 10 persons by connection count from Aurora."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.entity_name, e.entity_type, COUNT(DISTINCT d.document_id) as doc_count
                    FROM entities e
                    LEFT JOIN entity_document_links edl ON e.entity_id = edl.entity_id
                    LEFT JOIN documents d ON edl.document_id = d.document_id
                    WHERE e.case_file_id = %s AND e.entity_type = 'person'
                    GROUP BY e.entity_name, e.entity_type
                    ORDER BY doc_count DESC
                    LIMIT 10
                    """,
                    (case_id,),
                )
                return [
                    {
                        "name": row[0],
                        "entity_type": row[1],
                        "document_count": row[2],
                    }
                    for row in cur.fetchall()
                ]
        except Exception as exc:
            logger.warning("Failed to get key subjects: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Critical Leads
    # ------------------------------------------------------------------

    def _identify_critical_leads(self, case_id: str) -> list[dict]:
        """Find high-connectivity entities with low document coverage."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.entity_name, e.entity_type,
                           COUNT(DISTINCT r.relationship_id) as rel_count,
                           COUNT(DISTINCT d.document_id) as doc_count
                    FROM entities e
                    LEFT JOIN relationships r ON (e.entity_id = r.source_entity_id OR e.entity_id = r.target_entity_id)
                    LEFT JOIN entity_document_links edl ON e.entity_id = edl.entity_id
                    LEFT JOIN documents d ON edl.document_id = d.document_id
                    WHERE e.case_file_id = %s
                    GROUP BY e.entity_name, e.entity_type
                    HAVING COUNT(DISTINCT r.relationship_id) > 3
                       AND COUNT(DISTINCT d.document_id) <= 2
                    ORDER BY rel_count DESC
                    LIMIT 10
                    """,
                    (case_id,),
                )
                return [
                    {
                        "name": row[0],
                        "entity_type": row[1],
                        "connection_count": row[2],
                        "document_count": row[3],
                        "reason": f"High connectivity ({row[2]} connections) but low documentation ({row[3]} docs)",
                    }
                    for row in cur.fetchall()
                ]
        except Exception as exc:
            logger.warning("Failed to identify critical leads: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Resource Recommendations
    # ------------------------------------------------------------------

    def _generate_resource_recommendations(self, case_id: str, metrics: dict) -> list[str]:
        """Generate actionable recommendations from case data."""
        recommendations: list[str] = []
        coverage = self._compute_evidence_coverage(case_id, metrics)

        for element, info in coverage.items():
            if info["status"] == "gap":
                label = element.replace("_", " ").title()
                recommendations.append(
                    f"Evidence gap: {label} — no supporting evidence found. "
                    f"Consider targeted document collection."
                )

        if metrics.get("doc_count", 0) > 100 and metrics.get("entity_count", 0) < 50:
            recommendations.append(
                "Low entity extraction rate — consider adjusting confidence threshold "
                "or reviewing extraction prompt template."
            )

        if metrics.get("cross_case_matches", 0) > 0:
            recommendations.append(
                f"Found {metrics['cross_case_matches']} cross-case connections — "
                f"review for potential case consolidation."
            )

        if not recommendations:
            recommendations.append("Case evidence appears comprehensive. Continue monitoring.")

        return recommendations

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def _get_timeline(self, case_id: str) -> list[dict]:
        """Get date entities sorted chronologically."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.entity_name, COUNT(DISTINCT d.document_id) as doc_count
                    FROM entities e
                    LEFT JOIN entity_document_links edl ON e.entity_id = edl.entity_id
                    LEFT JOIN documents d ON edl.document_id = d.document_id
                    WHERE e.case_file_id = %s AND e.entity_type = 'date'
                    GROUP BY e.entity_name
                    ORDER BY e.entity_name
                    LIMIT 50
                    """,
                    (case_id,),
                )
                return [
                    {"date": row[0], "document_count": row[1]}
                    for row in cur.fetchall()
                ]
        except Exception as exc:
            logger.warning("Failed to get timeline: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Investigator AI-First extensions
    # ------------------------------------------------------------------

    def generate_strength_narrative(self, case_id: str, assessment: dict) -> str:
        """Generate AI narrative explaining case strength score."""
        if not self._bedrock:
            score = assessment.get("strength_score", 0)
            return f"Case strength score: {score}. Manual review recommended."
        try:
            import json as _json
            prompt = (
                f"Explain the case strength assessment for case {case_id}.\n"
                f"Strength score: {assessment.get('strength_score', 0)}\n"
                f"Evidence coverage: {_json.dumps(assessment.get('evidence_coverage', {}))}\n"
                f"Provide a concise narrative explaining the score basis, citing specific strengths and weaknesses."
            )
            body = _json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]})
            resp = self._bedrock.invoke_model(modelId="anthropic.claude-3-sonnet-20240229-v1:0", body=body)
            text = _json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "")
            return text or f"Case strength score: {assessment.get('strength_score', 0)}."
        except Exception as e:
            logger.warning("Strength narrative generation failed: %s", e)
            return f"Case strength score: {assessment.get('strength_score', 0)}. AI narrative unavailable."

    def get_session_changes(self, case_id: str, since) -> dict:
        """Query Aurora for changes since a timestamp."""
        changes = {"new_documents": 0, "new_entities": 0, "updated_scores": 0, "new_findings": 0}
        try:
            with self._db.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM documents WHERE case_file_id=%s AND created_at > %s", (case_id, since))
                changes["new_documents"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM entities WHERE case_file_id=%s AND created_at > %s", (case_id, since))
                changes["new_entities"] = cur.fetchone()[0]
        except Exception as e:
            logger.warning("Session changes query failed: %s", e)
        return changes
