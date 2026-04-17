"""Investigator AI Engine — AI-first case analysis for investigators.

Orchestrates case analysis: case briefing, lead prioritization, evidence triage,
hypothesis generation, and subpoena recommendations. All findings flow through
the three-state Decision Workflow (AI_Proposed → Human_Confirmed → Human_Overridden).
"""

import json
import logging
import os
import ssl
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from models.investigator import (
    CaseAnalysisResult,
    CaseBriefing,
    ConfidenceLevel,
    DocumentTypeClassification,
    EvidenceTriageResult,
    InvestigativeHypothesis,
    InvestigativeLead,
    ProsecutionReadinessImpact,
    SessionBriefing,
    SubpoenaRecommendation,
)

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
ASYNC_THRESHOLD = 100_000
PAGE_SIZE = 1000
MAX_BEDROCK_TOKENS = 100_000
# Per-service call timeout (seconds) to prevent one slow service from consuming
# the entire async Lambda budget (900s). Applied when doc_count > LARGE_CASE_THRESHOLD.
SERVICE_CALL_TIMEOUT = 60
LARGE_CASE_THRESHOLD = 10_000


class InvestigatorAIEngine:
    """Orchestrates AI-first investigative case analysis."""

    SENIOR_LEGAL_ANALYST_PERSONA = (
        "You are a senior federal investigative analyst with 20+ years of experience "
        "in complex multi-jurisdictional investigations. Reason using proper investigative "
        "methodology and legal terminology. Cite specific evidence documents and entity "
        "connections by name. Prioritize leads by evidentiary strength and connection density. "
        "Recommend specific investigative actions for each finding."
    )

    LEAD_WEIGHTS = {
        "evidence_strength": 0.30,
        "connection_density": 0.25,
        "novelty": 0.25,
        "prosecution_readiness": 0.20,
    }

    def __init__(
        self,
        aurora_cm: Any,
        bedrock_client: Any,
        neptune_endpoint: str = "",
        neptune_port: str = "8182",
        opensearch_endpoint: str = "",
        case_assessment_svc: Any = None,
        hypothesis_testing_svc: Any = None,
        pattern_discovery_svc: Any = None,
        decision_workflow_svc: Any = None,
    ) -> None:
        self._aurora = aurora_cm
        self._bedrock = bedrock_client
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port
        self._opensearch_endpoint = opensearch_endpoint
        self._case_assessment_svc = case_assessment_svc
        self._hypothesis_svc = hypothesis_testing_svc
        self._pattern_svc = pattern_discovery_svc
        self._decision_svc = decision_workflow_svc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _invoke_bedrock(self, prompt: str, max_tokens: int = 2000) -> str:
        try:
            response = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "system": self.SENIOR_LEGAL_ANALYST_PERSONA,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(response["body"].read())
            return body.get("content", [{}])[0].get("text", "")
        except Exception as e:
            logger.error("Bedrock invocation failed: %s", str(e)[:200])
            return ""

    def _get_case_stats(self, case_id: str) -> dict:
        stats = {"doc_count": 0, "entity_count": 0, "relationship_count": 0}
        try:
            with self._aurora.cursor() as cur:
                # Try matters table first (post-migration), fall back to case_files
                cur.execute(
                    "SELECT total_documents, total_entities, total_relationships FROM matters WHERE matter_id = %s",
                    (case_id,),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        "SELECT document_count, entity_count, relationship_count FROM case_files WHERE case_id = %s",
                        (case_id,),
                    )
                    row = cur.fetchone()
                if row:
                    stats["doc_count"] = row[0] or 0
                    stats["entity_count"] = row[1] or 0
                    stats["relationship_count"] = row[2] or 0
                # If counts are 0 or suspiciously low, query actual counts from source tables
                if stats["doc_count"] < 100:
                    cur.execute(
                        "SELECT COUNT(*) FROM documents WHERE case_file_id = %s",
                        (case_id,),
                    )
                    count_row = cur.fetchone()
                    if count_row and count_row[0] > stats["doc_count"]:
                        stats["doc_count"] = count_row[0]
                        logger.info("Corrected doc_count to %d from documents table", stats["doc_count"])
                if stats["entity_count"] < 10:
                    try:
                        cur.execute("SELECT COUNT(*) FROM entities WHERE case_file_id = %s", (case_id,))
                        erow = cur.fetchone()
                        if erow and erow[0] > stats["entity_count"]:
                            stats["entity_count"] = erow[0]
                            logger.info("Corrected entity_count to %d from entities table", stats["entity_count"])
                    except Exception:
                        pass  # entities table may not exist in older deployments
                if stats["relationship_count"] < 10:
                    try:
                        cur.execute("SELECT COUNT(*) FROM relationships WHERE case_file_id = %s", (case_id,))
                        rrow = cur.fetchone()
                        if rrow and rrow[0] > stats["relationship_count"]:
                            stats["relationship_count"] = rrow[0]
                            logger.info("Corrected relationship_count to %d from relationships table", stats["relationship_count"])
                    except Exception:
                        pass  # relationships table may not exist in older deployments
        except Exception as e:
            logger.error("Failed to get case stats: %s", str(e)[:200])
        return stats

    # ------------------------------------------------------------------
    # Core: analyze_case (Task 3.1)
    # ------------------------------------------------------------------

    def analyze_case(self, case_id: str) -> CaseAnalysisResult:
        now = datetime.now(timezone.utc).isoformat()

        # Check cache
        cached = self.get_cached_analysis(case_id)
        if cached:
            return cached

        stats = self._get_case_stats(case_id)

        # Async for large cases
        if stats["doc_count"] > ASYNC_THRESHOLD:
            result = CaseAnalysisResult(case_id=case_id, status="processing", created_at=now)
            self._cache_analysis(case_id, result, stats["doc_count"])
            return result

        # Gather data from existing services
        patterns = []
        is_large_case = stats["doc_count"] > LARGE_CASE_THRESHOLD
        if self._pattern_svc:
            try:
                if is_large_case:
                    # Wrap with timeout to prevent one slow service from consuming
                    # the entire async Lambda budget (900s) on large cases
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(self._pattern_svc.generate_pattern_report, case_id)
                        try:
                            report = future.result(timeout=SERVICE_CALL_TIMEOUT)
                            patterns = report.patterns if report else []
                        except FuturesTimeoutError:
                            logger.warning(
                                "pattern_discovery timed out after %ds for case %s (doc_count=%d) — continuing with empty patterns",
                                SERVICE_CALL_TIMEOUT, case_id, stats["doc_count"],
                            )
                else:
                    report = self._pattern_svc.generate_pattern_report(case_id)
                    patterns = report.patterns if report else []
            except Exception:
                pass

        hypotheses = []
        if self._hypothesis_svc and hasattr(self._hypothesis_svc, 'generate_hypotheses'):
            try:
                if is_large_case:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(self._hypothesis_svc.generate_hypotheses, case_id, patterns)
                        try:
                            hypotheses = future.result(timeout=SERVICE_CALL_TIMEOUT)
                        except FuturesTimeoutError:
                            logger.warning(
                                "hypothesis_generation timed out after %ds for case %s (doc_count=%d) — continuing with empty hypotheses",
                                SERVICE_CALL_TIMEOUT, case_id, stats["doc_count"],
                            )
                else:
                    hypotheses = self._hypothesis_svc.generate_hypotheses(case_id, patterns)
            except Exception:
                pass

        # Generate leads from entity data (bounded by LIMIT 30 in queries,
        # but add timeout for large cases in case Neptune graph traversal is slow)
        if is_large_case:
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._generate_leads, case_id, stats)
                    try:
                        leads = future.result(timeout=SERVICE_CALL_TIMEOUT)
                    except FuturesTimeoutError:
                        logger.warning(
                            "_generate_leads timed out after %ds for case %s (doc_count=%d) — continuing with empty leads",
                            SERVICE_CALL_TIMEOUT, case_id, stats["doc_count"],
                        )
                        leads = []
            except Exception:
                leads = []
        else:
            leads = self._generate_leads(case_id, stats)

        # Generate subpoena recommendations
        subpoenas = self.generate_subpoena_recommendations(case_id, leads)

        # Generate briefing narrative via Bedrock
        briefing = self._generate_briefing(case_id, stats, leads, hypotheses, patterns)

        # Create AI_Proposed decisions for each finding
        for lead in leads:
            try:
                decision = self._decision_svc.create_decision(
                    case_id=case_id, decision_type="investigative_lead",
                    recommendation_text=f"Lead: {lead.entity_name} (score: {lead.lead_priority_score})",
                    legal_reasoning=lead.ai_justification,
                    confidence="high" if lead.lead_priority_score > 70 else "medium",
                    source_service="investigator_ai_engine",
                )
                lead.decision_id = decision.decision_id
                lead.decision_state = decision.state.value
            except Exception:
                pass

        hyp_models = []
        for h in hypotheses:
            hm = InvestigativeHypothesis(
                hypothesis_id=str(uuid.uuid4()), case_id=case_id,
                hypothesis_text=h.get("hypothesis_text", ""),
                confidence=ConfidenceLevel(h.get("confidence", "medium").lower()),
                supporting_evidence=[{"text": e} if isinstance(e, str) else e for e in h.get("supporting_evidence", [])],
                recommended_actions=h.get("recommended_actions", []),
            )
            try:
                decision = self._decision_svc.create_decision(
                    case_id=case_id, decision_type="investigative_hypothesis",
                    recommendation_text=hm.hypothesis_text[:200],
                    legal_reasoning=hm.hypothesis_text,
                    confidence=hm.confidence.value,
                    source_service="investigator_ai_engine",
                )
                hm.decision_id = decision.decision_id
                hm.decision_state = decision.state.value
            except Exception:
                pass
            hyp_models.append(hm)

        result = CaseAnalysisResult(
            case_id=case_id, status="completed",
            briefing=briefing, leads=leads,
            hypotheses=hyp_models,
            subpoena_recommendations=subpoenas,
            created_at=now,
        )
        self._cache_analysis(case_id, result, stats["doc_count"])
        self._store_leads(leads)
        return result

    # ------------------------------------------------------------------
    # Lead Priority Score (Task 3.2)
    # ------------------------------------------------------------------

    def compute_lead_priority_score(
        self, doc_count: int, total_docs: int,
        degree_centrality: float, previously_flagged_ratio: float,
        prosecution_readiness: float,
    ) -> int:
        evidence_strength = min(doc_count / max(total_docs, 1), 1.0)
        connection_density = min(degree_centrality, 1.0)
        novelty = 1.0 - min(previously_flagged_ratio, 1.0)
        pr = min(prosecution_readiness, 1.0)
        score = round((
            self.LEAD_WEIGHTS["evidence_strength"] * evidence_strength
            + self.LEAD_WEIGHTS["connection_density"] * connection_density
            + self.LEAD_WEIGHTS["novelty"] * novelty
            + self.LEAD_WEIGHTS["prosecution_readiness"] * pr
        ) * 100)
        return max(0, min(100, score))

    def _generate_leads(self, case_id: str, stats: dict) -> list[InvestigativeLead]:
        leads = []
        # Try Neptune first for entity data
        try:
            import ssl, urllib.request
            label = f"Entity_{case_id}"
            url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
            query = (
                f"g.V().hasLabel('{label}')"
                f".has('entity_type',within('person','organization','location','event'))"
                f".project('n','t','d').by('canonical_name').by('entity_type').by(bothE().count())"
                f".order().by('d',desc).limit(30)"
            )
            data = json.dumps({"gremlin": query}).encode("utf-8")
            ctx = ssl.create_default_context()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                result = body.get("result", {}).get("data", {})
                if isinstance(result, dict) and "@value" in result:
                    result = result["@value"]
                if not isinstance(result, list):
                    result = []

            for r in result:
                if not isinstance(r, dict):
                    continue
                name = r.get("n", "")
                etype = r.get("t", "")
                degree = r.get("d", 0)
                if isinstance(degree, dict):
                    degree = degree.get("@value", 0)
                degree = int(degree)
                if not name or degree < 2:
                    continue

                score = self.compute_lead_priority_score(
                    degree, max(stats.get("entity_count", 1), 1), min(degree / 100, 1.0), 0.0, 0.5)
                justification = f"{name} ({etype}) has {degree} connections in the knowledge graph, indicating significant involvement in the case."

                leads.append(InvestigativeLead(
                    lead_id=str(uuid.uuid4()), case_id=case_id,
                    entity_name=name, entity_type=etype,
                    lead_priority_score=score,
                    evidence_strength=min(degree / max(stats.get("entity_count", 1), 1), 1.0),
                    connection_density=min(degree / 100, 1.0), novelty=1.0, prosecution_readiness=0.5,
                    ai_justification=justification,
                    recommended_actions=["Review linked documents", "Analyze connections", "Cross-reference with other cases"],
                ))
        except Exception as e:
            logger.error("Neptune lead generation failed: %s", str(e)[:200])

        # Aurora fallback: if Neptune returned 0 leads, query entities table directly
        if not leads:
            logger.info("Neptune returned 0 leads, falling back to Aurora entities table")
            try:
                with self._aurora.cursor() as cur:
                    cur.execute(
                        "SELECT canonical_name, entity_type, occurrence_count "
                        "FROM entities WHERE case_file_id = %s "
                        "AND entity_type IN ('person','organization','location','event') "
                        "ORDER BY occurrence_count DESC LIMIT 30",
                        (case_id,),
                    )
                    rows = cur.fetchall()
                    # Also get relationship counts per entity
                    rel_counts = {}
                    try:
                        cur.execute(
                            "SELECT source_entity, COUNT(*) FROM relationships WHERE case_file_id = %s GROUP BY source_entity "
                            "UNION ALL "
                            "SELECT target_entity, COUNT(*) FROM relationships WHERE case_file_id = %s GROUP BY target_entity",
                            (case_id, case_id),
                        )
                        for rrow in cur.fetchall():
                            rel_counts[rrow[0]] = rel_counts.get(rrow[0], 0) + rrow[1]
                    except Exception:
                        pass

                    for row in rows:
                        name, etype, mention_count = row[0], row[1], row[2]
                        if not name or mention_count < 1:
                            continue
                        degree = rel_counts.get(name, 0) + mention_count
                        score = self.compute_lead_priority_score(
                            mention_count, max(stats.get("entity_count", 1), 1),
                            min(degree / 100, 1.0), 0.0, 0.5)
                        justification = (
                            f"{name} ({etype}) appears in {mention_count} documents"
                            f"{f' with {rel_counts.get(name, 0)} relationships' if rel_counts.get(name) else ''}"
                            f", indicating significant involvement in the case."
                        )
                        leads.append(InvestigativeLead(
                            lead_id=str(uuid.uuid4()), case_id=case_id,
                            entity_name=name, entity_type=etype,
                            lead_priority_score=score,
                            evidence_strength=min(mention_count / max(stats.get("entity_count", 1), 1), 1.0),
                            connection_density=min(degree / 100, 1.0), novelty=1.0, prosecution_readiness=0.5,
                            ai_justification=justification,
                            recommended_actions=["Review linked documents", "Analyze connections", "Cross-reference with other cases"],
                        ))
                    logger.info("Aurora fallback generated %d leads", len(leads))
            except Exception as e2:
                logger.error("Aurora lead fallback also failed: %s", str(e2)[:200])

        leads.sort(key=lambda l: l.lead_priority_score, reverse=True)
        return leads

    # ------------------------------------------------------------------
    # Evidence Triage (Task 3.3)
    # ------------------------------------------------------------------

    def triage_evidence(self, case_id: str, document_id: str) -> EvidenceTriageResult:
        # Classify document type via Bedrock
        classification = "other"
        findings = []
        try:
            resp = self._invoke_bedrock(
                f"Classify this document (ID: {document_id}) into one of: email, financial_record, "
                f"legal_filing, testimony, report, correspondence, other. "
                f"Also identify any high-priority findings (admissions, financial irregularities, contradictions). "
                f"Return JSON with 'classification' and 'findings' keys.")
            if resp:
                resp_lower = resp.lower()
                for dtype in ["email", "financial_record", "legal_filing", "testimony", "report", "correspondence"]:
                    if dtype in resp_lower:
                        classification = dtype
                        break
                if "admission" in resp_lower or "irregularit" in resp_lower or "contradiction" in resp_lower:
                    findings.append({"type": "high_priority", "description": resp[:200]})
        except Exception:
            pass

        # Assess prosecution readiness impact
        impact = "neutral"
        if findings:
            impact = "strengthens"

        result = EvidenceTriageResult(
            triage_id=str(uuid.uuid4()), case_id=case_id, document_id=document_id,
            doc_type_classification=DocumentTypeClassification(classification),
            high_priority_findings=findings,
            prosecution_readiness_impact=ProsecutionReadinessImpact(impact),
        )

        # Create AI_Proposed decision
        if self._decision_svc:
            try:
                decision = self._decision_svc.create_decision(
                    case_id=case_id, decision_type="evidence_triage",
                    recommendation_text=f"Document {document_id}: classified as {classification}",
                    legal_reasoning=f"AI classified document as {classification} with {len(findings)} findings",
                    confidence="medium", source_service="investigator_ai_engine",
                )
                result.decision_id = decision.decision_id
                result.decision_state = decision.state.value
            except Exception:
                pass

        self._store_triage_result(result)
        return result

    # ------------------------------------------------------------------
    # Subpoena Recommendations (Task 3.4)
    # ------------------------------------------------------------------

    def generate_subpoena_recommendations(self, case_id: str, leads: list[InvestigativeLead]) -> list[SubpoenaRecommendation]:
        recommendations = []
        lead_summary = "\n".join(f"- {l.entity_name} ({l.entity_type}): score {l.lead_priority_score}" for l in leads[:10])
        resp = self._invoke_bedrock(
            f"Based on these investigative leads for case {case_id}:\n{lead_summary}\n\n"
            f"Recommend up to 5 subpoenas. For each, provide: target, custodian, legal basis, "
            f"and expected evidentiary value (high/medium/low).")

        # Parse recommendations (simplified — in production would use structured output)
        for i, lead in enumerate(leads[:5], start=1):
            rec = SubpoenaRecommendation(
                recommendation_id=str(uuid.uuid4()), case_id=case_id,
                target=lead.entity_name, custodian=f"Records custodian for {lead.entity_name}",
                legal_basis=f"Based on {lead.lead_priority_score} priority score and {lead.entity_type} entity connections",
                expected_evidentiary_value=ConfidenceLevel.HIGH if lead.lead_priority_score > 70 else ConfidenceLevel.MEDIUM,
                priority_rank=i,
            )
            if self._decision_svc:
                try:
                    decision = self._decision_svc.create_decision(
                        case_id=case_id, decision_type="subpoena_recommendation",
                        recommendation_text=f"Subpoena: {rec.target}",
                        legal_reasoning=rec.legal_basis,
                        confidence=rec.expected_evidentiary_value.value,
                        source_service="investigator_ai_engine",
                    )
                    rec.decision_id = decision.decision_id
                    rec.decision_state = decision.state.value
                except Exception:
                    pass
            recommendations.append(rec)
        return recommendations

    # ------------------------------------------------------------------
    # Retrieval Methods (Task 3.5)
    # ------------------------------------------------------------------

    def get_investigative_leads(self, case_id: str, min_score: int = 0, state: str = None) -> list[InvestigativeLead]:
        try:
            with self._aurora.cursor() as cur:
                q = "SELECT lead_id,case_id,entity_name,entity_type,lead_priority_score,evidence_strength,connection_density,novelty,prosecution_readiness,ai_justification,recommended_actions,decision_id FROM investigator_leads WHERE case_id=%s"
                params: list = [case_id]
                if min_score > 0:
                    q += " AND lead_priority_score >= %s"
                    params.append(min_score)
                q += " ORDER BY lead_priority_score DESC"
                cur.execute(q, tuple(params))
                return [InvestigativeLead(
                    lead_id=str(r[0]), case_id=str(r[1]), entity_name=r[2], entity_type=r[3],
                    lead_priority_score=r[4], evidence_strength=r[5] or 0.0, connection_density=r[6] or 0.0,
                    novelty=r[7] or 0.0, prosecution_readiness=r[8] or 0.0,
                    ai_justification=r[9] or "", recommended_actions=r[10] if isinstance(r[10], list) else json.loads(r[10] or "[]"),
                    decision_id=str(r[11]) if r[11] else None,
                ) for r in cur.fetchall()]
        except Exception:
            return []

    def get_evidence_triage_results(self, case_id: str, doc_type: str = None) -> list[EvidenceTriageResult]:
        try:
            with self._aurora.cursor() as cur:
                q = "SELECT triage_id,case_id,document_id,doc_type_classification,identified_entities,high_priority_findings,linked_leads,prosecution_readiness_impact,decision_id FROM evidence_triage_results WHERE case_id=%s"
                params: list = [case_id]
                if doc_type:
                    q += " AND doc_type_classification=%s"
                    params.append(doc_type)
                cur.execute(q, tuple(params))
                return [EvidenceTriageResult(
                    triage_id=str(r[0]), case_id=str(r[1]), document_id=str(r[2]),
                    doc_type_classification=DocumentTypeClassification(r[3]),
                    identified_entities=r[4] if isinstance(r[4], list) else json.loads(r[4] or "[]"),
                    high_priority_findings=r[5] if isinstance(r[5], list) else json.loads(r[5] or "[]"),
                    linked_leads=r[6] if isinstance(r[6], list) else json.loads(r[6] or "[]"),
                    prosecution_readiness_impact=ProsecutionReadinessImpact(r[7]),
                    decision_id=str(r[8]) if r[8] else None,
                ) for r in cur.fetchall()]
        except Exception:
            return []

    def get_session_briefing(self, case_id: str, user_id: str = "investigator") -> SessionBriefing:
        # Get last session time
        last_session = None
        try:
            with self._aurora.cursor() as cur:
                cur.execute("SELECT last_session_at FROM investigator_sessions WHERE case_id=%s AND user_id=%s", (case_id, user_id))
                row = cur.fetchone()
                if row:
                    last_session = row[0]
                # Update session
                cur.execute(
                    "INSERT INTO investigator_sessions (session_id,case_id,user_id,last_session_at) VALUES (%s,%s,%s,NOW()) "
                    "ON CONFLICT (case_id,user_id) DO UPDATE SET last_session_at=NOW()",
                    (str(uuid.uuid4()), case_id, user_id))
        except Exception:
            pass

        briefing = SessionBriefing()
        if last_session:
            try:
                with self._aurora.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM documents WHERE case_file_id=%s AND created_at > %s", (case_id, last_session))
                    briefing.new_documents = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM entities WHERE case_file_id=%s AND created_at > %s", (case_id, last_session))
                    briefing.new_entities = cur.fetchone()[0]
            except Exception:
                pass
        narrative = self._invoke_bedrock(
            f"Generate a brief session briefing for case {case_id}. "
            f"New documents: {briefing.new_documents}, new entities: {briefing.new_entities}.")
        briefing.narrative = narrative or f"Welcome back. {briefing.new_documents} new documents and {briefing.new_entities} new entities since your last session."
        return briefing

    # ------------------------------------------------------------------
    # Cache and Storage
    # ------------------------------------------------------------------

    def get_cached_analysis(self, case_id: str) -> Optional[CaseAnalysisResult]:
        try:
            with self._aurora.cursor() as cur:
                cur.execute("SELECT analysis_result, evidence_count_at_analysis, status FROM investigator_analysis_cache WHERE case_id=%s", (case_id,))
                row = cur.fetchone()
                if not row:
                    return None
                # Check if stale (new evidence added)
                cur.execute("SELECT COUNT(*) FROM documents WHERE case_file_id=%s", (case_id,))
                current_count = cur.fetchone()[0]
                if current_count > row[1]:
                    return None  # Cache stale
                data = row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
                return CaseAnalysisResult(**data)
        except Exception:
            return None

    def _cache_analysis(self, case_id: str, result: CaseAnalysisResult, evidence_count: int) -> None:
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "INSERT INTO investigator_analysis_cache (cache_id,case_id,analysis_result,evidence_count_at_analysis,status) "
                    "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (case_id) DO UPDATE SET analysis_result=EXCLUDED.analysis_result, "
                    "evidence_count_at_analysis=EXCLUDED.evidence_count_at_analysis, status=EXCLUDED.status, updated_at=NOW()",
                    (str(uuid.uuid4()), case_id, json.dumps(result.model_dump(mode="json")), evidence_count, result.status))
        except Exception as e:
            logger.error("Cache failed: %s", str(e)[:200])

    # ------------------------------------------------------------------
    # Async Analysis (AI Briefing Experience)
    # ------------------------------------------------------------------

    def trigger_async_analysis(self, case_id: str) -> CaseAnalysisResult:
        """Trigger async analysis: return cache if fresh, else start async Lambda invoke."""
        cached = self.get_cached_analysis(case_id)
        if cached:
            return cached

        now = datetime.now(timezone.utc).isoformat()
        processing_result = CaseAnalysisResult(case_id=case_id, status="processing", created_at=now)
        stats = self._get_case_stats(case_id)
        self._cache_analysis(case_id, processing_result, stats.get("doc_count", 0))

        try:
            import boto3
            lam = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "us-east-1"))
            lam.invoke(
                FunctionName=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", ""),
                InvocationType="Event",
                Payload=json.dumps({"action": "async_analysis", "case_id": case_id}),
            )
        except Exception as e:
            logger.error("Async Lambda invoke failed: %s", str(e)[:200])

        return processing_result

    # Stale processing rows older than this threshold are auto-expired
    ANALYSIS_PROCESSING_EXPIRY = timedelta(minutes=15)

    def get_analysis_status(self, case_id: str) -> Optional[CaseAnalysisResult]:
        """Read-only status check from cache. Returns None if no row exists.

        Processing rows older than 15 minutes are treated as stale — the row is
        deleted so a fresh analysis can be triggered on the next request.
        """
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT analysis_result, status, updated_at FROM investigator_analysis_cache WHERE case_id=%s",
                    (case_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                status = row[1] or "processing"
                if status == "completed":
                    data = row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
                    return CaseAnalysisResult(**data)
                if status == "error":
                    data = row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
                    error_msg = data.get("error_message", "Unknown error")
                    return CaseAnalysisResult(case_id=case_id, status="error", error_message=error_msg)

                # --- Expiry check for stuck "processing" rows ---
                updated_at = row[2]
                if updated_at is not None:
                    if not updated_at.tzinfo:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    age = datetime.now(timezone.utc) - updated_at
                    if age > self.ANALYSIS_PROCESSING_EXPIRY:
                        logger.warning(
                            "Expiring stale processing cache for case %s (age=%s, updated_at=%s)",
                            case_id, age, updated_at,
                        )
                        cur.execute(
                            "DELETE FROM investigator_analysis_cache WHERE case_id=%s AND status='processing'",
                            (case_id,),
                        )
                        return None

                return CaseAnalysisResult(case_id=case_id, status="processing")
        except Exception as e:
            logger.error("get_analysis_status failed: %s", str(e)[:200])
            return None

    def run_async_analysis(self, case_id: str) -> dict:
        """Run the full analysis synchronously (called from async Lambda invoke). Writes result or error to cache."""
        try:
            result = self.analyze_case(case_id)
            return {"status": "completed", "case_id": case_id}
        except Exception as e:
            logger.exception("Async analysis failed for case %s", case_id)
            error_msg = str(e)[:500]
            try:
                with self._aurora.cursor() as cur:
                    cur.execute(
                        "INSERT INTO investigator_analysis_cache (cache_id,case_id,analysis_result,evidence_count_at_analysis,status) "
                        "VALUES (%s,%s,%s,0,%s) ON CONFLICT (case_id) DO UPDATE SET "
                        "analysis_result=EXCLUDED.analysis_result, status=EXCLUDED.status, updated_at=NOW()",
                        (str(uuid.uuid4()), case_id,
                         json.dumps({"error_message": error_msg, "case_id": case_id, "status": "error"}),
                         "error"))
            except Exception as cache_err:
                logger.error("Failed to write error to cache: %s", str(cache_err)[:200])
            return {"status": "error", "case_id": case_id, "error_message": error_msg}

    def get_entity_neighborhood(self, case_id: str, entity_name: str, hops: int = 2) -> dict:
        """Query Neptune for N-hop entity neighborhood around a given entity.

        Uses a simple project-based query (not path traversal) to handle
        high-degree nodes efficiently. Limits to top 50 neighbors by degree.
        """
        result = {"entity_name": entity_name, "case_id": case_id, "hops": hops, "nodes": [], "edges": []}
        if not self._neptune_endpoint:
            logger.error("GRAPH_DEBUG: No neptune endpoint configured")
            return result

        label = f"Entity_{case_id}"
        url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
        ctx = ssl.create_default_context()
        logger.error("GRAPH_DEBUG: endpoint=%s label=%s entity=%s", self._neptune_endpoint, label, entity_name)

        def _gremlin(query: str, timeout: int = 30) -> list:
            """Execute a Gremlin query and return the result list."""
            data = json.dumps({"gremlin": query}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            raw = body.get("result", {}).get("data", {})
            if isinstance(raw, dict) and "@value" in raw:
                raw = raw["@value"]
            return raw if isinstance(raw, list) else []

        def _unwrap(val):
            """Unwrap Neptune GraphSON @value wrappers, including g:Map."""
            if isinstance(val, dict):
                if val.get("@type") == "g:Map" and "@value" in val:
                    # g:Map @value is a flat list: [key1, val1, key2, val2, ...]
                    flat = val["@value"]
                    if isinstance(flat, list):
                        return {flat[i]: _unwrap(flat[i + 1]) for i in range(0, len(flat) - 1, 2)}
                if "@value" in val:
                    return _unwrap(val["@value"])
            return val

        def _query_neighbors(ename: str) -> tuple:
            """Get 1-hop neighbors with a simple, efficient query. Returns (nodes_dict, edges_list)."""
            esc = ename.replace("'", "\\'")
            # Ultra-simple: limit edges first, then get neighbor properties
            # No sorting by degree (too expensive for high-degree nodes)
            q = (
                f"g.V().hasLabel('{label}').has('canonical_name','{esc}')"
                f".bothE().limit(200).otherV().hasLabel('{label}').dedup().limit(50)"
                f".project('n','t').by('canonical_name').by('entity_type')"
            )
            raw = _gremlin(q, timeout=25)
            logger.error("GRAPH_DEBUG: query returned %d raw items for '%s'", len(raw), ename)
            if raw and len(raw) > 0:
                logger.error("GRAPH_DEBUG: first item type=%s val=%s", type(raw[0]).__name__, str(raw[0])[:300])

            nodes = {}
            for r in raw:
                parsed = _unwrap(r)
                if not isinstance(parsed, dict):
                    continue
                n = parsed.get("n", "")
                t = parsed.get("t", "unknown")
                if isinstance(n, dict):
                    n = _unwrap(n)
                if isinstance(t, dict):
                    t = _unwrap(t)
                if n:
                    nodes[n] = {"name": n, "type": t, "degree": 0}
            edges = [{"source": ename, "target": n, "relationship": "RELATED_TO"} for n in nodes]
            return nodes, edges

        try:
            # 1) Direct entity lookup in Neptune
            logger.error("GRAPH_DEBUG: Querying Neptune neighbors for entity '%s' in case %s", entity_name, case_id)
            seen_nodes, edge_list = _query_neighbors(entity_name)
            logger.error("GRAPH_DEBUG: Neptune returned %d neighbors for '%s'", len(seen_nodes), entity_name)

            # 2) If no results, treat entity_name as a document ID and resolve via Aurora
            if not seen_nodes:
                logger.info("No Neptune neighbors for '%s', trying document-to-entity lookup", entity_name)
                doc_entities = self._get_entities_for_document(case_id, entity_name)
                if doc_entities:
                    logger.info("Found %d entities for doc %s, querying Neptune", len(doc_entities), entity_name)
                    for ent_name, ent_type in doc_entities[:5]:
                        try:
                            sn, el = _query_neighbors(ent_name)
                            for k, v in sn.items():
                                if k not in seen_nodes:
                                    seen_nodes[k] = v
                            edge_list.extend(el)
                        except Exception:
                            pass

            # Also add the queried entity itself as a node
            if seen_nodes and entity_name not in seen_nodes:
                try:
                    esc_en = entity_name.replace("'", "\\'")
                    deg_raw = _gremlin(
                        f"g.V().hasLabel('{label}').has('canonical_name','{esc_en}')"
                        f".project('t','d').by('entity_type').by(bothE().count())",
                        timeout=10,
                    )
                    if deg_raw and isinstance(deg_raw[0], dict):
                        seen_nodes[entity_name] = {
                            "name": entity_name,
                            "type": _unwrap(deg_raw[0].get("t", "person")),
                            "degree": int(_unwrap(deg_raw[0].get("d", 0))),
                        }
                except Exception:
                    pass

            result["nodes"] = list(seen_nodes.values())
            result["edges"] = edge_list
        except Exception as e:
            logger.error("GRAPH_DEBUG: Entity neighborhood EXCEPTION: %s %s", type(e).__name__, str(e)[:500])
        return result

    def _get_entities_for_document(self, case_id: str, document_id: str) -> list:
        """Look up entities extracted from a specific document via Aurora.

        Returns list of (canonical_name, entity_type) tuples.
        """
        try:
            with self._aurora.cursor() as cur:
                # source_document_ids is a JSONB array; use @> containment operator
                cur.execute(
                    "SELECT canonical_name, entity_type FROM entities "
                    "WHERE case_file_id = %s AND source_document_ids @> %s::jsonb "
                    "ORDER BY occurrence_count DESC LIMIT 30",
                    (case_id, json.dumps([document_id])),
                )
                return [(r[0], r[1]) for r in cur.fetchall()]
        except Exception as e:
            logger.error("Document entity lookup failed for %s: %s", document_id, str(e)[:200])
            return []

    def _store_leads(self, leads: list[InvestigativeLead]) -> None:
        try:
            with self._aurora.cursor() as cur:
                for l in leads:
                    cur.execute(
                        "INSERT INTO investigator_leads (lead_id,case_id,entity_name,entity_type,lead_priority_score,"
                        "evidence_strength,connection_density,novelty,prosecution_readiness,ai_justification,recommended_actions,decision_id) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (lead_id) DO NOTHING",
                        (l.lead_id, l.case_id, l.entity_name, l.entity_type, l.lead_priority_score,
                         l.evidence_strength, l.connection_density, l.novelty, l.prosecution_readiness,
                         l.ai_justification, json.dumps(l.recommended_actions), l.decision_id))
        except Exception as e:
            logger.error("Lead storage failed: %s", str(e)[:200])

    def _store_triage_result(self, result: EvidenceTriageResult) -> None:
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "INSERT INTO evidence_triage_results (triage_id,case_id,document_id,doc_type_classification,"
                    "identified_entities,high_priority_findings,linked_leads,prosecution_readiness_impact,decision_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (result.triage_id, result.case_id, result.document_id, result.doc_type_classification.value,
                     json.dumps(result.identified_entities), json.dumps(result.high_priority_findings),
                     json.dumps(result.linked_leads), result.prosecution_readiness_impact.value, result.decision_id))
        except Exception as e:
            logger.error("Triage storage failed: %s", str(e)[:200])

    def _generate_briefing(self, case_id: str, stats: dict, leads, hypotheses, patterns) -> CaseBriefing:
        lead_summary = ", ".join(f"{l.entity_name} (score:{l.lead_priority_score})" for l in leads[:5])
        prompt = (
            f"Generate a comprehensive case briefing for case {case_id}.\n"
            f"Statistics: {stats['doc_count']} documents, {stats['entity_count']} entities.\n"
            f"Top leads: {lead_summary}\n"
            f"Patterns detected: {len(patterns)}\n"
            f"Hypotheses generated: {len(hypotheses)}\n"
            f"Provide: key findings, evidence coverage assessment, and recommended next steps.")
        narrative = self._invoke_bedrock(prompt, max_tokens=3000)
        if not narrative:
            narrative = (f"Case {case_id}: {stats['doc_count']} documents analyzed, "
                        f"{stats['entity_count']} entities identified, {len(leads)} leads prioritized. "
                        f"[AI narrative unavailable — manual review recommended]")
            warnings = ["Bedrock unavailable — partial briefing with statistics only"]
        else:
            warnings = []
        return CaseBriefing(
            narrative=narrative, statistics=stats,
            key_findings=[{"lead": l.entity_name, "score": l.lead_priority_score} for l in leads[:5]],
            evidence_coverage={"documents": stats["doc_count"], "entities": stats["entity_count"],
                              "leads": len(leads), "patterns": len(patterns), "hypotheses": len(hypotheses)},
            recommended_next_steps=[a for l in leads[:3] for a in l.recommended_actions[:2]],
            warnings=warnings,
        )

    # ── Geospatial Evidence Map methods ───────────────────────────────

    def get_location_detail(self, case_id: str, location_name: str) -> dict | None:
        """Return connected entities, relationships, and documents for a location.

        Queries Aurora entities/relationships/entity_document_links tables,
        then Neptune for 1-hop neighbors. Returns None if location not found.
        """
        try:
            with self._aurora.cursor() as cur:
                # Find the location entity
                cur.execute(
                    "SELECT entity_id, canonical_name, occurrence_count "
                    "FROM entities WHERE case_file_id = %s AND entity_type = 'location' "
                    "AND LOWER(canonical_name) = LOWER(%s) LIMIT 1",
                    (case_id, location_name),
                )
                loc_row = cur.fetchone()
                if not loc_row:
                    return None
                entity_id, canonical, occ_count = loc_row[0], loc_row[1], loc_row[2]

                # Get connected entities via relationships
                cur.execute(
                    "SELECT CASE WHEN r.source_entity = %s THEN r.target_entity ELSE r.source_entity END AS other, "
                    "e.entity_type, e.canonical_name, r.relationship_type, r.occurrence_count "
                    "FROM relationships r "
                    "JOIN entities e ON e.entity_id = CASE WHEN r.source_entity = %s THEN r.target_entity ELSE r.source_entity END "
                    "WHERE r.case_file_id = %s AND (r.source_entity = %s OR r.target_entity = %s)",
                    (entity_id, entity_id, case_id, entity_id, entity_id),
                )
                rel_rows = cur.fetchall()

                groups: dict[str, list] = {"persons": [], "organizations": [], "events": [], "other": []}
                type_map = {"person": "persons", "organization": "organizations", "event": "events"}
                seen = set()
                rel_count = 0
                for row in rel_rows:
                    other_id, etype, ename, rtype, rocc = row
                    rel_count += rocc or 1
                    if ename not in seen:
                        seen.add(ename)
                        bucket = type_map.get(etype, "other")
                        groups[bucket].append({"name": ename, "relationship_count": rocc or 1})

                # Get up to 10 documents mentioning this location
                cur.execute(
                    "SELECT edl.document_id, COALESCE(d.doc_name, edl.document_id::text) AS title, "
                    "edl.mention_count "
                    "FROM entity_document_links edl "
                    "LEFT JOIN documents d ON d.document_id = edl.document_id "
                    "WHERE edl.entity_id = %s AND edl.case_file_id = %s "
                    "ORDER BY edl.mention_count DESC LIMIT 10",
                    (entity_id, case_id),
                )
                doc_rows = cur.fetchall()
                documents = [
                    {"document_id": str(r[0]), "title": r[1], "mention_count": r[2] or 1}
                    for r in doc_rows
                ]

            # Neptune 1-hop neighbors (graceful degradation)
            neighbors = []
            try:
                nbr_result = self.get_entity_neighborhood(case_id, canonical, hops=1)
                neighbors = [
                    {"name": n["name"], "type": n["type"], "relationship": "connected"}
                    for n in nbr_result.get("nodes", [])
                    if n["name"] != canonical
                ]
            except Exception as ne:
                logger.warning("Neptune unavailable for location detail: %s", str(ne)[:200])

            return {
                "location": canonical,
                "connected_entities": groups,
                "relationship_count": rel_count,
                "documents": documents,
                "neighbors": neighbors,
            }
        except Exception as exc:
            logger.exception("get_location_detail failed for %s", location_name)
            raise

    def analyze_geography(self, case_id: str, locations_data: list[dict]) -> dict:
        """Send geocoded location data to Bedrock for geographic pattern analysis.

        Args:
            locations_data: list of dicts with name, lat, lng, connection_count, persons
        Returns:
            dict with clustering, travel_corridors, jurisdictional, anomalies sections
        """
        # Build a concise prompt with all location and person data
        loc_lines = []
        all_persons = set()
        for loc in locations_data:
            persons = loc.get("persons", [])
            all_persons.update(persons)
            loc_lines.append(
                f"- {loc['name']} ({loc.get('lat', '?')}, {loc.get('lng', '?')}): "
                f"{loc.get('connection_count', 0)} connections, persons: {', '.join(persons) or 'none'}"
            )

        prompt = (
            f"You are analyzing geographic patterns in an investigative case (ID: {case_id}).\n\n"
            f"LOCATIONS ({len(locations_data)} total):\n" + "\n".join(loc_lines) + "\n\n"
            f"ALL PERSONS INVOLVED: {', '.join(sorted(all_persons)) or 'none'}\n\n"
            "Provide a structured geographic analysis with exactly these four sections:\n"
            "1. CLUSTERING: Identify geographic clusters of activity and what they suggest.\n"
            "2. TRAVEL_CORRIDORS: Identify high-frequency travel corridors between locations.\n"
            "3. JURISDICTIONAL: Note jurisdictional observations (state/federal/international).\n"
            "4. ANOMALIES: Flag any unusual or anomalous geographic patterns.\n\n"
            "Reference specific location names and person names in your analysis. "
            "Format each section with the header followed by the analysis text."
        )

        raw = self._invoke_bedrock(prompt, max_tokens=2000)
        if not raw:
            return {
                "clustering": "AI analysis unavailable — please retry.",
                "travel_corridors": "",
                "jurisdictional": "",
                "anomalies": "",
                "raw_analysis": "",
            }

        # Parse sections from the response
        result = {"clustering": "", "travel_corridors": "", "jurisdictional": "", "anomalies": "", "raw_analysis": raw}
        section_keys = [
            ("CLUSTERING", "clustering"),
            ("TRAVEL_CORRIDORS", "travel_corridors"),
            ("TRAVEL CORRIDORS", "travel_corridors"),
            ("JURISDICTIONAL", "jurisdictional"),
            ("ANOMALIES", "anomalies"),
        ]
        lines = raw.split("\n")
        current_key = None
        current_lines: list[str] = []
        for line in lines:
            upper = line.strip().upper().lstrip("0123456789. ")
            matched = False
            for header, key in section_keys:
                if upper.startswith(header):
                    if current_key:
                        result[current_key] = "\n".join(current_lines).strip()
                    current_key = key
                    current_lines = []
                    # Include text after the header on the same line
                    remainder = line.split(":", 1)[1].strip() if ":" in line else ""
                    if remainder:
                        current_lines.append(remainder)
                    matched = True
                    break
            if not matched and current_key:
                current_lines.append(line)
        if current_key:
            result[current_key] = "\n".join(current_lines).strip()

        return result
