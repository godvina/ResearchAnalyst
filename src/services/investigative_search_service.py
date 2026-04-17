"""Investigative Search Service — thin orchestrator for intelligence-grade search."""
import json, logging, os, re, ssl, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import combinations
from typing import Any, Optional

from models.investigative_search import ConfidenceLevel

logger = logging.getLogger(__name__)
HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"
SONNET = "anthropic.claude-3-sonnet-20240229-v1:0"

ENTITY_PROMPT = (
    "Extract all person, organization, location, and event entity names from "
    "this investigative query. Return ONLY a JSON array of objects with "
    '"name", "type", and "aliases" fields. Types: person|organization|location|event.\n'
    "Query: {query}\nReturn JSON array only."
)
SYNTHESIS_PROMPT = (
    "You are a senior federal investigative analyst. Synthesize evidence into "
    "a structured intelligence brief.\n\nQUERY: {query}\n\n"
    "DOCUMENT EVIDENCE:\n{doc_evidence}\n\nGRAPH CONNECTIONS:\n{graph_evidence}\n\n"
    "{prior}\nProduce JSON with: executive_summary, ai_analysis, "
    'evidence_gaps (array of {{area, suggestion}}), recommended_next_steps '
    "(array of {{action, priority, rationale}}). JSON only."
)
XREF_PROMPT = (
    "Compare internal findings vs external research. Categorize each as "
    "confirmed_internally, external_only, or needs_research.\n\n"
    "INTERNAL:\n{internal}\n\nEXTERNAL:\n{external}\n\n"
    'Return JSON array of {{finding, category, internal_evidence, external_source}}.'
)
_STOP = set("what was the is are were a an of to in for and or on at by with from about "
    "between how who where when why do does did has have had be been being that this "
    "those these it its all any each every both few more most other some such no not "
    "only same so than too very can will just should now based data files produce "
    "possible list show find search tell me give get relationship".split())


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _safe_float(val, default: float = 0.0) -> float:
    """Safely convert to float, returning default on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _parse_json(raw: str) -> Any:
    """Strip markdown fences and parse JSON."""
    c = raw.strip()
    if c.startswith("```"):
        c = re.sub(r"^```(?:json)?\s*", "", c)
        c = re.sub(r"\s*```$", "", c)
    return json.loads(c)


class InvestigativeSearchService:
    """Orchestrates investigative search across existing services."""
    def __init__(self, semantic_search: Any, question_answer: Any, ai_engine: Any,
                 research_agent: Any, bedrock_client: Any, neptune_endpoint: str = "",
                 neptune_port: str = "8182", findings_service: Optional[Any] = None) -> None:
        self._search_svc = semantic_search
        self._qa_svc = question_answer
        self._ai_engine = ai_engine
        self._research_agent = research_agent
        self._bedrock = bedrock_client
        self._neptune_ep = neptune_endpoint or os.environ.get("NEPTUNE_ENDPOINT", "")
        self._neptune_port = neptune_port or os.environ.get("NEPTUNE_PORT", "8182")
        self._findings_svc = findings_service

    # --- Bedrock helper ---
    def _invoke_bedrock(self, prompt: str, model: str = HAIKU, max_tok: int = 2000) -> str:
        try:
            r = self._bedrock.invoke_model(
                modelId=model, contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tok,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(r["body"].read())
            return body.get("content", [{}])[0].get("text", "")
        except Exception as e:
            logger.error("Bedrock call failed (%s): %s", model, str(e)[:300])
            return ""

    # --- Neptune helper ---
    def _gremlin(self, query: str, timeout: int = 12) -> list:
        if not self._neptune_ep:
            return []
        url = f"https://{self._neptune_ep}:{self._neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode()
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
        raw = body.get("result", {}).get("data", {})
        if isinstance(raw, dict) and "@value" in raw:
            raw = raw["@value"]
        return raw if isinstance(raw, list) else []

    # 2.2 — Entity extraction
    def _extract_entities_from_query(self, query: str) -> list:
        raw = self._invoke_bedrock(ENTITY_PROMPT.format(query=query), model=HAIKU, max_tok=1000)
        if raw:
            try:
                entities = _parse_json(raw)
                if isinstance(entities, list):
                    out = [
                        {"name": e["name"], "type": e.get("type", "person"),
                         "aliases": e.get("aliases", [])}
                        for e in entities if isinstance(e, dict) and e.get("name")
                    ]
                    if out:
                        return out
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.error("Entity extraction parse failed: %s", str(exc)[:200])
        # Fallback: keyword tokenization
        tokens = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", query)
        if not tokens:
            tokens = [w for w in query.split() if w.lower() not in _STOP and len(w) > 2]
        return [{"name": t.strip(), "type": "person", "aliases": []} for t in tokens if t.strip()]

    # 2.4 — Document search
    def _search_documents(self, case_id: str, query: str, top_k: int = 10) -> list:
        try:
            # Try hybrid first, fall back to semantic if hybrid not supported
            try:
                results = self._search_svc.search(case_id, query, mode="hybrid", top_k=top_k)
            except Exception:
                results = self._search_svc.search(case_id, query, mode="semantic", top_k=top_k)
            out = []
            for r in results:
                if hasattr(r, "model_dump"):
                    out.append(r.model_dump())
                elif hasattr(r, "dict"):
                    out.append(r.dict())
                elif isinstance(r, dict):
                    out.append(r)
                else:
                    out.append({"text": str(r)})
            return out
        except Exception as e:
            logger.error("Document search failed: %s", str(e)[:300])
            return []

    # 2.5 — Graph context
    def _get_graph_context(self, case_id: str, entities: list, hops: int = 2) -> dict:
        merged: dict = {"nodes": [], "edges": [], "entity_neighborhoods": {}}
        seen: set = set()
        for ent in entities:
            name = ent.get("name", "") if isinstance(ent, dict) else str(ent)
            if not name:
                continue
            try:
                nb = self._ai_engine.get_entity_neighborhood(case_id, name, hops=hops)
                merged["entity_neighborhoods"][name] = nb
                for node in nb.get("nodes", []):
                    n = node.get("name", "")
                    if n and n not in seen:
                        seen.add(n)
                        merged["nodes"].append(node)
                merged["edges"].extend(nb.get("edges", []))
            except Exception as e:
                logger.error("Graph context failed for '%s': %s", name, str(e)[:300])
        return merged

    # 2.6 — Entity path queries
    def _find_entity_paths(
        self, case_id: str, entity_a: str, entity_b: str, max_hops: int = 3
    ) -> list:
        if not self._neptune_ep:
            return []
        label = f"Entity_{case_id}"
        ea, eb = _escape(entity_a), _escape(entity_b)
        try:
            q = (
                f"g.V().hasLabel('{label}').has('canonical_name','{ea}')"
                f".repeat(bothE().limit(200).otherV().hasLabel('{label}').simplePath())"
                f".until(has('canonical_name','{eb}').or().loops().is({max_hops}))"
                f".has('canonical_name','{eb}').path().limit(5)"
            )
            raw = self._gremlin(q)
            return [
                {"source": entity_a, "target": entity_b,
                 "path": (item.get("@value") if isinstance(item, dict) and "@value" in item else item),
                 "hops": max_hops}
                for item in raw
            ]
        except Exception as e:
            logger.error("Path query '%s'->'%s' failed: %s", entity_a, entity_b, str(e)[:300])
            return []

    # 2.9 — Intelligence brief synthesis
    def _synthesize_intelligence_brief(
        self, query: str, search_results: list, graph_context: dict,
        output_format: str = "full", prior_findings: Optional[list] = None,
    ) -> dict:
        doc_ev = "\n".join(
            f"[{i}] {d.get('source_filename', d.get('source', '?'))}: "
            f"{(d.get('text_excerpt') or d.get('text') or d.get('content', ''))[:500]}"
            for i, d in enumerate(search_results[:15], 1)
        ) or "(No document evidence)"
        graph_ev = "\n".join(
            f"  {e.get('source','?')} --[{e.get('relationship', e.get('relationship_type','RELATED_TO'))}]--> {e.get('target','?')}"
            for e in graph_context.get("edges", [])[:20]
        ) or "(No graph connections)"
        prior = ""
        if prior_findings:
            prior = "PRIOR RESEARCH:\n" + "\n".join(
                f"  - {p.get('title','')}: {str(p.get('summary',''))[:300]}"
                for p in prior_findings[:5]
            )
        prompt = SYNTHESIS_PROMPT.format(
            query=query, doc_evidence=doc_ev, graph_evidence=graph_ev, prior=prior,
        )
        model = HAIKU  # Always use Haiku for speed (29s API Gateway budget)
        max_t = 1500 if output_format == "brief" else 3000
        raw = self._invoke_bedrock(prompt, model=model, max_tok=max_t)
        if not raw and model == SONNET:
            raw = self._invoke_bedrock(prompt, model=HAIKU, max_tok=max_t)
        if raw:
            try:
                return _parse_json(raw)
            except (json.JSONDecodeError, TypeError):
                return {"executive_summary": raw[:500], "ai_analysis": raw,
                        "evidence_gaps": [], "recommended_next_steps": []}
        logger.error("Synthesis failed for: %s", query[:100])
        return {"executive_summary": "", "ai_analysis": "",
                "evidence_gaps": [], "recommended_next_steps": []}

    # 2.10 — Cross-reference report
    def _generate_cross_reference_report(self, internal_brief: dict, external_research: list) -> list:
        if not external_research:
            return []
        prompt = XREF_PROMPT.format(
            internal=json.dumps(internal_brief, default=str)[:3000],
            external=json.dumps(external_research, default=str)[:3000],
        )
        raw = self._invoke_bedrock(prompt, model=HAIKU, max_tok=2000)
        valid_cats = {"confirmed_internally", "external_only", "needs_research"}
        if raw:
            try:
                entries = _parse_json(raw)
                if isinstance(entries, list):
                    return [
                        {"finding": e.get("finding", ""),
                         "category": e.get("category", "needs_research") if e.get("category") in valid_cats else "needs_research",
                         "internal_evidence": e.get("internal_evidence", []),
                         "external_source": e.get("external_source")}
                        for e in entries if isinstance(e, dict)
                    ]
            except (json.JSONDecodeError, TypeError) as exc:
                logger.error("Cross-ref parse failed: %s", str(exc)[:200])
        return [
            {"finding": str(r.get("title", r.get("subject", r.get("subject_name", ""))))[:200],
             "category": "needs_research", "internal_evidence": [],
             "external_source": str(r.get("source", r.get("research_text", "external")))[:200]}
            for r in external_research[:10]
        ]

    # 2.11 — Confidence level
    def _compute_confidence_level(self, search_results: list, graph_context: dict) -> str:
        unique_docs: set = set()
        for d in search_results:
            did = d.get("document_id") or d.get("source_filename") or d.get("source", "")
            if did:
                unique_docs.add(did)
        n_docs = len(unique_docs)
        n_edges = len(graph_context.get("edges", []))
        if n_docs < 2:
            return ConfidenceLevel.INSUFFICIENT.value
        if n_docs >= 3 and n_edges > 0:
            return ConfidenceLevel.STRONG_CASE.value
        return ConfidenceLevel.NEEDS_MORE_EVIDENCE.value

    # 2.13 — Assessment assembly
    def _assemble_assessment(
        self, query: str, case_id: str, search_scope: str,
        search_results: list, graph_context: dict, intelligence_brief: dict,
        cross_reference: Optional[list], confidence: str,
        entities_extracted: list, synthesis_error: Optional[str] = None,
    ) -> dict:
        evidence = [
            {"document_id": d.get("document_id", d.get("id", "")),
             "source_filename": d.get("source_filename", d.get("source", "")),
             "page_number": d.get("page_number"),
             "chunk_index": d.get("chunk_index"),
             "text_excerpt": (d.get("text_excerpt") or d.get("text") or d.get("content", ""))[:1000],
             "relevance_score": _safe_float(d.get("relevance_score", d.get("score", 0.0)))}
            for d in search_results
        ]
        connections = [
            {"source_entity": e.get("source", ""), "target_entity": e.get("target", ""),
             "relationship_type": e.get("relationship", e.get("relationship_type", "RELATED_TO")),
             "properties": e.get("properties", {}),
             "source_documents": e.get("source_documents", [])}
            for e in graph_context.get("edges", [])
        ]
        gaps = [
            ({"area": g.get("area", ""), "suggestion": g.get("suggestion", "")}
             if isinstance(g, dict) else {"area": str(g), "suggestion": ""})
            for g in intelligence_brief.get("evidence_gaps", [])
        ]
        def _safe_priority(val):
            """Convert priority to int, handling string values like 'High'."""
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                low = val.strip().lower()
                if low in ("high", "critical", "urgent"):
                    return 1
                if low in ("medium", "moderate", "normal"):
                    return 2
                if low in ("low", "minor"):
                    return 3
                try:
                    return int(low)
                except (ValueError, TypeError):
                    return 99
            return 99

        steps = [
            ({"action": s.get("action", ""), "priority": _safe_priority(s.get("priority", 99)),
              "rationale": s.get("rationale", "")}
             if isinstance(s, dict) else {"action": str(s), "priority": 99, "rationale": ""})
            for s in intelligence_brief.get("recommended_next_steps", [])
        ]
        return {
            "query": query, "case_id": case_id, "search_scope": search_scope,
            "confidence_level": confidence,
            "executive_summary": intelligence_brief.get("executive_summary", ""),
            "internal_evidence": evidence, "graph_connections": connections,
            "ai_analysis": intelligence_brief.get("ai_analysis", ""),
            "evidence_gaps": gaps, "recommended_next_steps": steps,
            "cross_reference_report": cross_reference,
            "raw_search_results": search_results,
            "entities_extracted": entities_extracted,
            "synthesis_error": synthesis_error,
        }

    # 2.14 — Main orchestration
    def investigative_search(
        self, case_id: str, query: str, search_scope: str = "internal",
        top_k: int = 10, output_format: str = "full",
        graph_case_id: str = "",
    ) -> dict:
        """Execute investigative search with time-budgeted parallel fan-out.

        Runs entity extraction first, then fans out doc search + graph in
        parallel.  Tracks wall-clock time and returns partial results if
        approaching the 29-second API Gateway timeout.

        Args:
            case_id: Case ID for document search (OpenSearch index).
            graph_case_id: Optional separate case ID for Neptune graph queries.
                           Falls back to case_id if not provided.
        """
        T0 = time.time()
        BUDGET = 25  # seconds — leave 4s headroom for serialization + network
        synthesis_error: Optional[str] = None
        g_case_id = graph_case_id or case_id  # Neptune may use a different case ID

        def _remaining():
            return max(0, BUDGET - (time.time() - T0))

        # 1. Entity extraction (fast — Haiku, ~2-3s)
        entities: list = []
        try:
            entities = self._extract_entities_from_query(query)
        except Exception as e:
            logger.error("Entity extraction failed: %s", str(e)[:300])

        # 2. Parallel fan-out: doc search + graph context
        search_results: list = []
        graph_context: dict = {"nodes": [], "edges": []}

        if _remaining() > 3:
            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_search = pool.submit(self._search_documents, case_id, query, top_k)
                fut_graph = pool.submit(self._get_graph_context, g_case_id, entities, 2) if entities else None

                try:
                    search_results = fut_search.result(timeout=min(15, _remaining()))
                except Exception as e:
                    logger.error("Doc search timed out or failed: %s", str(e)[:300])

                if fut_graph and _remaining() > 1:
                    try:
                        graph_context = fut_graph.result(timeout=min(12, _remaining()))
                    except Exception as e:
                        logger.error("Graph context timed out or failed: %s", str(e)[:300])

        # 3. Path queries — only if we have 2+ entities AND time left
        if len(entities) >= 2 and _remaining() > 5:
            try:
                for ea, eb in list(combinations(entities, 2))[:3]:
                    if _remaining() < 3:
                        break
                    na = ea.get("name", "") if isinstance(ea, dict) else str(ea)
                    nb = eb.get("name", "") if isinstance(eb, dict) else str(eb)
                    if na and nb:
                        for p in self._find_entity_paths(g_case_id, na, nb):
                            graph_context["edges"].append(
                                {"source": na, "target": nb, "relationship": "PATH",
                                 "path": p.get("path")})
            except Exception as e:
                logger.error("Path queries failed: %s", str(e)[:300])

        # 4. Prior findings (fast — Aurora query)
        prior: Optional[list] = None
        if self._findings_svc and entities and _remaining() > 3:
            try:
                names = [e.get("name", "") if isinstance(e, dict) else str(e) for e in entities]
                prior = self._findings_svc.get_findings_for_entities(case_id, names)
            except Exception as e:
                logger.error("Prior findings failed: %s", str(e)[:200])

        # 5. Synthesis — use Haiku for speed (Sonnet too slow for 29s budget)
        brief: dict = {}
        if _remaining() > 4:
            try:
                brief = self._synthesize_intelligence_brief(
                    query, search_results, graph_context, output_format, prior_findings=prior)
            except Exception as e:
                synthesis_error = f"Synthesis failed: {str(e)[:200]}"
                logger.error(synthesis_error)
        else:
            synthesis_error = "Synthesis skipped — time budget exceeded"

        # 6. External research — only if scope requires it AND time left
        xref: Optional[list] = None
        if search_scope == "internal_external" and _remaining() > 5:
            try:
                subjects = [{"name": e.get("name", ""), "type": e.get("type", "person")}
                            for e in entities if isinstance(e, dict) and e.get("name")]
                ext = []
                if subjects and hasattr(self._research_agent, "research_all_subjects"):
                    ext = self._research_agent.research_all_subjects(
                        subjects=subjects, osint_directives=[], evidence_hints=[])
                elif subjects:
                    for s in subjects[:3]:
                        if _remaining() < 3:
                            break
                        try:
                            t = self._research_agent._call_bedrock(
                                f"Research background on {s['name']}.")
                            if t:
                                ext.append({"subject": s["name"], "research": t[:2000]})
                        except Exception:
                            pass
                xref = self._generate_cross_reference_report(brief, ext) if ext else []
            except Exception as e:
                logger.error("External research failed: %s", str(e)[:300])
                xref = []

        # 7. Confidence + assembly
        confidence = self._compute_confidence_level(search_results, graph_context)
        assessment = self._assemble_assessment(
            query, case_id, search_scope, search_results, graph_context,
            brief, xref, confidence, entities, synthesis_error)

        # 8. Brief truncation
        if output_format == "brief":
            assessment = {
                "query": assessment["query"], "case_id": assessment["case_id"],
                "search_scope": assessment["search_scope"],
                "confidence_level": assessment["confidence_level"],
                "executive_summary": assessment["executive_summary"],
                "internal_evidence": assessment["internal_evidence"][:3],
                "entities_extracted": assessment["entities_extracted"],
                "synthesis_error": assessment.get("synthesis_error"),
            }

        elapsed = time.time() - T0
        logger.info("Investigative search completed in %.1fs (budget=%.0fs)", elapsed, BUDGET)
        return assessment


    # ------------------------------------------------------------------
    # Lead Assessment (Task 3)
    # ------------------------------------------------------------------

    def lead_assessment(self, case_id: str, lead_payload: dict) -> dict:
        """Run deep-dive assessment for a lead across all subjects."""
        lead_id = lead_payload.get("lead_id", "unknown")
        subjects = lead_payload.get("subjects", [])
        osint = lead_payload.get("osint_directives", [])
        hints = lead_payload.get("evidence_hints", [])

        subject_assessments = []
        for subj in subjects[:20]:
            name = subj.get("name", "") if isinstance(subj, dict) else str(subj)
            if not name:
                continue
            query = f"Investigate {name} in the context of this case"
            try:
                assessment = self.investigative_search(
                    case_id, query, search_scope="internal_external",
                    top_k=10, output_format="full")
                subject_assessments.append(assessment)
            except Exception as e:
                logger.error("Lead assessment failed for '%s': %s", name, str(e)[:200])
                subject_assessments.append({
                    "query": query, "case_id": case_id,
                    "confidence_level": ConfidenceLevel.INSUFFICIENT.value,
                    "executive_summary": f"Assessment failed for {name}: {str(e)[:100]}",
                    "synthesis_error": str(e)[:200],
                })

        # Cross-subject connections
        cross_connections = []
        all_entities = set()
        for sa in subject_assessments:
            for conn in sa.get("graph_connections", []):
                src = conn.get("source_entity", "")
                tgt = conn.get("target_entity", "")
                if src:
                    all_entities.add(src)
                if tgt:
                    all_entities.add(tgt)
        subject_names = {
            (s.get("name", "") if isinstance(s, dict) else str(s)).lower()
            for s in subjects
        }
        for sa in subject_assessments:
            for conn in sa.get("graph_connections", []):
                src_l = conn.get("source_entity", "").lower()
                tgt_l = conn.get("target_entity", "").lower()
                if src_l in subject_names and tgt_l in subject_names and src_l != tgt_l:
                    cross_connections.append(conn)

        # Case viability
        strong = sum(1 for sa in subject_assessments
                     if sa.get("confidence_level") == ConfidenceLevel.STRONG_CASE.value)
        partial = sum(1 for sa in subject_assessments
                      if sa.get("confidence_level") == ConfidenceLevel.NEEDS_MORE_EVIDENCE.value)
        if strong >= 2 or (strong >= 1 and cross_connections):
            viability = "viable"
        elif strong >= 1 or partial >= 2:
            viability = "promising"
        else:
            viability = "insufficient"

        # Consolidated summary
        summary_parts = []
        for sa in subject_assessments:
            es = sa.get("executive_summary", "")
            if es:
                summary_parts.append(es[:300])
        consolidated = " | ".join(summary_parts) if summary_parts else "No assessments completed."

        return {
            "lead_id": lead_id, "case_id": case_id,
            "case_viability": viability,
            "subjects_assessed": len(subject_assessments),
            "subject_assessments": subject_assessments,
            "cross_subject_connections": cross_connections,
            "consolidated_summary": consolidated[:2000],
            "status": "complete",
        }
