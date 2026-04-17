"""Question Answer Service — progressive intelligence drilldown.

Generates Level 1 (quick), Level 2 (analytical brief), and Level 3
(structured intelligence report) answers for investigative questions
using Neptune graph context, Aurora pgvector semantic search, and
Bedrock Claude Haiku synthesis.

Graceful degradation:
  - Neptune fails → proceed with document context only
  - Semantic search fails → proceed with graph context only
  - Both fail → Bedrock with question + entity name only
"""

import json
import logging
import ssl
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

ANALYST_PERSONA = (
    "You are a senior federal investigative analyst at the U.S. Department of Justice. "
    "You provide precise, evidence-based analysis grounded in case documents and "
    "knowledge graph relationships. Cite specific sources for every factual claim."
)


def _escape(s: str) -> str:
    """Escape a string for Gremlin query embedding."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _parse_gs(items: list) -> list:
    """Parse GraphSON typed values into plain Python objects."""
    return [_parse_gs_val(item) for item in items]


def _parse_gs_val(val):
    """Recursively parse a single GraphSON value."""
    if not isinstance(val, dict):
        return val
    gt = val.get("@type", "")
    gv = val.get("@value")
    if gt == "g:Map" and isinstance(gv, list):
        d = {}
        for i in range(0, len(gv) - 1, 2):
            d[_parse_gs_val(gv[i])] = _parse_gs_val(gv[i + 1])
        return d
    if gt in ("g:Int64", "g:Int32", "g:Double", "g:Float"):
        return gv
    if gt == "g:List" and isinstance(gv, list):
        return [_parse_gs_val(v) for v in gv]
    if "@value" in val:
        return _parse_gs_val(gv)
    return val


class QuestionAnswerService:
    """Generates progressive intelligence answers for investigative questions.

    Combines Neptune graph context, Aurora pgvector semantic search, and
    Bedrock Claude Haiku to produce Level 1/2/3 answers with graceful
    degradation when data sources are unavailable.
    """

    def __init__(
        self,
        aurora_cm: Any,
        bedrock_client: Any,
        neptune_endpoint: str,
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

    def answer_question(
        self,
        case_id: str,
        entity_name: str,
        question: str,
        level: int,
        entity_type: Optional[str] = None,
        neighbors: Optional[list[dict]] = None,
    ) -> dict:
        """Generate an answer at the requested intelligence level.

        Args:
            case_id: Case file identifier.
            entity_name: Entity being investigated.
            question: The investigative question text.
            level: 1 (quick), 2 (analytical brief), or 3 (intelligence report).
            entity_type: Optional entity type for additional context.
            neighbors: Optional pre-fetched neighbor data.

        Returns:
            Dict with level-appropriate answer structure.
        """
        # Gather context with graceful degradation
        graph_ctx = self._get_graph_context(case_id, entity_name)
        doc_ctx = self._get_document_context(case_id, entity_name, question)

        if level == 1:
            return self._generate_level1(question, entity_name, graph_ctx, doc_ctx)
        elif level == 2:
            return self._generate_level2(question, entity_name, graph_ctx, doc_ctx)
        elif level == 3:
            return self._generate_level3(question, entity_name, graph_ctx, doc_ctx)
        else:
            return self._generate_level2(question, entity_name, graph_ctx, doc_ctx)

    # ------------------------------------------------------------------
    # Context retrieval — Neptune graph
    # ------------------------------------------------------------------

    def _get_graph_context(self, case_id: str, entity_name: str) -> list[dict]:
        """Query Neptune for 1-2 hop neighborhood context around the entity."""
        if not self._neptune_endpoint:
            return []

        try:
            label = f"Entity_{case_id}"
            esc_label = _escape(label)
            esc_name = _escape(entity_name)

            # 1-hop neighbors with relationship types
            query = (
                f"g.V().hasLabel('{esc_label}').has('canonical_name','{esc_name}')"
                f".bothE('RELATED_TO').project('rel','target','conf')"
                f".by('relationship_type')"
                f".by(otherV().values('canonical_name'))"
                f".by('confidence')"
                f".limit(20)"
            )
            results = self._neptune_query(query)
            return results
        except Exception:
            logger.exception("Neptune graph context failed for entity %s in case %s", entity_name, case_id)
            return []

    def _neptune_query(self, query: str) -> list:
        """Execute a Gremlin query via Neptune HTTP API."""
        url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            result = body.get("result", {}).get("data", {})
            if isinstance(result, dict) and "@value" in result:
                return _parse_gs(result["@value"])
            return result if isinstance(result, list) else [result] if result else []

    # ------------------------------------------------------------------
    # Context retrieval — Aurora pgvector semantic search
    # ------------------------------------------------------------------

    def _get_document_context(
        self, case_id: str, entity_name: str, question: str,
    ) -> list[dict]:
        """Use Aurora pgvector to find relevant document passages."""
        if not self._db:
            return []

        try:
            # Combine entity name and question for a richer search query
            search_query = f"{entity_name} {question}"

            # Generate embedding via Bedrock
            embedding = self._generate_embedding(search_query)
            if not embedding:
                return []

            with self._db.cursor() as cur:
                cur.execute(
                    """
                    SELECT document_id, raw_text, source_filename,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM documents
                    WHERE case_file_id = %s AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT 5
                    """,
                    (str(embedding), case_id, str(embedding)),
                )
                rows = cur.fetchall()

            results = []
            for row in rows:
                doc_id, raw_text, source_filename, similarity = row
                passage = raw_text[:500] if raw_text else ""
                results.append({
                    "document_id": str(doc_id),
                    "document_name": source_filename or "unknown",
                    "passage": passage,
                    "relevance_score": max(0.0, min(1.0, float(similarity))),
                })
            return results
        except Exception:
            logger.exception(
                "Semantic search failed for entity %s in case %s", entity_name, case_id,
            )
            return []

    def _generate_embedding(self, text: str) -> Optional[list[float]]:
        """Generate an embedding vector via Bedrock Titan."""
        try:
            resp = self._bedrock.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text}),
            )
            body = json.loads(resp["body"].read())
            return body.get("embedding")
        except Exception:
            logger.exception("Embedding generation failed")
            return None

    # ------------------------------------------------------------------
    # Level 1 — quick one-line answer
    # ------------------------------------------------------------------

    def _generate_level1(
        self, question: str, entity_name: str,
        graph_ctx: list[dict], doc_ctx: list[dict],
    ) -> dict:
        """Generate a quick one-line answer for a follow-up question."""
        context_text = self._build_context_text(entity_name, graph_ctx, doc_ctx)

        prompt = f"""{ANALYST_PERSONA}

{context_text}

QUESTION about {entity_name}: {question}

Provide a single-sentence answer (max 150 characters) that directly addresses the question using the available context. Be specific and cite evidence where possible.

Return ONLY a JSON object:
{{"answer": "your one-sentence answer here"}}"""

        try:
            raw = self._invoke_bedrock(prompt)
            parsed = self._parse_json_response(raw)
            answer = parsed.get("answer", raw[:150])
            return {
                "level": 1,
                "entity_name": entity_name,
                "question": question,
                "answer": answer[:150],
            }
        except Exception:
            logger.exception("Level 1 generation failed for entity %s", entity_name)
            return {
                "level": 1,
                "entity_name": entity_name,
                "question": question,
                "answer": "Quick answer unavailable — expand for full analysis.",
            }

    # ------------------------------------------------------------------
    # Level 2 — analytical brief with citations
    # ------------------------------------------------------------------

    def _generate_level2(
        self, question: str, entity_name: str,
        graph_ctx: list[dict], doc_ctx: list[dict],
    ) -> dict:
        """Generate a 2-3 paragraph analytical brief with document citations."""
        context_text = self._build_context_text(entity_name, graph_ctx, doc_ctx)

        prompt = f"""{ANALYST_PERSONA}

{context_text}

QUESTION about {entity_name}: {question}

Provide a 2-3 paragraph analytical brief that:
1. Directly answers the question using evidence from the documents and graph relationships
2. Cites specific documents by name
3. Identifies gaps in the available evidence

Return a JSON object:
{{
  "analysis": "Your 2-3 paragraph analytical brief here.",
  "citations": [
    {{"document_name": "source document name", "relevance": "high|medium|low", "excerpt": "relevant excerpt"}}
  ]
}}"""

        try:
            raw = self._invoke_bedrock(prompt, max_tokens=2048)
            parsed = self._parse_json_response(raw)
            analysis = parsed.get("analysis", raw)
            # Guard: if analysis is still JSON (parse failed or Bedrock double-wrapped), extract text
            analysis = self._extract_text_from_analysis(analysis)
            citations = parsed.get("citations", [])

            # Ensure citations have required fields
            valid_citations = []
            for c in citations:
                if isinstance(c, dict) and "document_name" in c:
                    valid_citations.append({
                        "document_name": c.get("document_name", "unknown"),
                        "relevance": c.get("relevance", "medium") if c.get("relevance") in ("high", "medium", "low") else "medium",
                        "excerpt": c.get("excerpt", ""),
                    })

            # Supplement with doc_ctx citations if Bedrock didn't produce enough
            if not valid_citations and doc_ctx:
                for d in doc_ctx[:3]:
                    valid_citations.append({
                        "document_name": d.get("document_name", "unknown"),
                        "relevance": "high" if d.get("relevance_score", 0) > 0.7 else "medium",
                        "excerpt": d.get("passage", "")[:200],
                    })

            return {
                "level": 2,
                "entity_name": entity_name,
                "question": question,
                "analysis": analysis if analysis else "Analysis could not be generated.",
                "citations": valid_citations,
            }
        except Exception:
            logger.exception("Level 2 generation failed for entity %s", entity_name)
            return {
                "level": 2,
                "entity_name": entity_name,
                "question": question,
                "analysis": "AI analysis unavailable. Please retry.",
                "citations": [],
            }

    # ------------------------------------------------------------------
    # Level 3 — structured intelligence report
    # ------------------------------------------------------------------

    def _generate_level3(
        self, question: str, entity_name: str,
        graph_ctx: list[dict], doc_ctx: list[dict],
    ) -> dict:
        """Generate a full structured intelligence report."""
        context_text = self._build_context_text(entity_name, graph_ctx, doc_ctx)

        prompt = f"""{ANALYST_PERSONA}

{context_text}

QUESTION about {entity_name}: {question}

Generate a comprehensive intelligence report. Return a JSON object with these exact fields:
{{
  "executive_summary": "A concise executive summary paragraph.",
  "evidence_analysis": "Detailed multi-paragraph evidence analysis citing specific documents and graph relationships.",
  "source_citations": [
    {{"document_name": "name", "relevance": "high|medium|low", "excerpt": "key excerpt", "document_id": "id if available"}}
  ],
  "confidence_assessment": {{
    "level": "high|medium|low",
    "justification": "Explanation of confidence level based on evidence quality and coverage."
  }},
  "recommended_next_steps": [
    "Specific actionable next step 1",
    "Specific actionable next step 2"
  ]
}}"""

        try:
            raw = self._invoke_bedrock(prompt, max_tokens=4096)
            parsed = self._parse_json_response(raw)

            # Validate and normalize all required sections
            executive_summary = parsed.get("executive_summary", "")
            evidence_analysis = parsed.get("evidence_analysis", "")
            # Guard: if the whole raw response ended up in a field, extract text
            executive_summary = self._extract_text_from_analysis(executive_summary)
            evidence_analysis = self._extract_text_from_analysis(evidence_analysis)
            source_citations = parsed.get("source_citations", [])
            confidence_assessment = parsed.get("confidence_assessment", {})
            recommended_next_steps = parsed.get("recommended_next_steps", [])

            # Ensure source_citations have required fields
            valid_citations = []
            for c in source_citations:
                if isinstance(c, dict):
                    valid_citations.append({
                        "document_name": c.get("document_name", "unknown"),
                        "relevance": c.get("relevance", "medium") if c.get("relevance") in ("high", "medium", "low") else "medium",
                        "excerpt": c.get("excerpt", ""),
                        "document_id": c.get("document_id", ""),
                    })

            # Supplement citations from doc_ctx if needed
            if not valid_citations and doc_ctx:
                for d in doc_ctx[:3]:
                    valid_citations.append({
                        "document_name": d.get("document_name", "unknown"),
                        "relevance": "high" if d.get("relevance_score", 0) > 0.7 else "medium",
                        "excerpt": d.get("passage", "")[:200],
                        "document_id": d.get("document_id", ""),
                    })

            # Normalize confidence_assessment
            if not isinstance(confidence_assessment, dict):
                confidence_assessment = {}
            conf_level = confidence_assessment.get("level", "medium")
            if conf_level not in ("high", "medium", "low"):
                conf_level = "medium"
            confidence_assessment = {
                "level": conf_level,
                "justification": confidence_assessment.get("justification", "Assessment based on available evidence."),
            }

            # Ensure recommended_next_steps is a list of strings
            if not isinstance(recommended_next_steps, list):
                recommended_next_steps = []
            recommended_next_steps = [str(s) for s in recommended_next_steps if s]

            return {
                "level": 3,
                "entity_name": entity_name,
                "question": question,
                "executive_summary": executive_summary if executive_summary else "Executive summary unavailable.",
                "evidence_analysis": evidence_analysis if evidence_analysis else "Evidence analysis unavailable.",
                "source_citations": valid_citations,
                "confidence_assessment": confidence_assessment,
                "recommended_next_steps": recommended_next_steps if recommended_next_steps else ["Review available evidence manually."],
            }
        except Exception:
            logger.exception("Level 3 generation failed for entity %s", entity_name)
            return {
                "level": 3,
                "entity_name": entity_name,
                "question": question,
                "executive_summary": "AI analysis unavailable. Please retry.",
                "evidence_analysis": "",
                "source_citations": [],
                "confidence_assessment": {"level": "low", "justification": "Generation failed."},
                "recommended_next_steps": ["Retry the intelligence report generation."],
            }

    # ------------------------------------------------------------------
    # Bedrock invocation
    # ------------------------------------------------------------------

    def _invoke_bedrock(self, prompt: str, max_tokens: int = 1024) -> str:
        """Call Bedrock Claude Haiku with the assembled prompt."""
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        resp = self._bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        resp_body = json.loads(resp["body"].read())
        content_blocks = resp_body.get("content", [])
        return "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_context_text(
        self, entity_name: str,
        graph_ctx: list[dict], doc_ctx: list[dict],
    ) -> str:
        """Assemble context from graph and document sources for the prompt."""
        parts = []

        if graph_ctx:
            parts.append("KNOWLEDGE GRAPH CONTEXT:")
            for item in graph_ctx[:15]:
                if isinstance(item, dict):
                    target = item.get("target", "unknown")
                    rel = item.get("rel", "related_to")
                    conf = item.get("conf", "")
                    parts.append(f"  - {entity_name} --[{rel}]--> {target} (confidence: {conf})")
                else:
                    parts.append(f"  - {item}")
        else:
            parts.append("KNOWLEDGE GRAPH CONTEXT: No graph data available.")

        if doc_ctx:
            parts.append("\nDOCUMENT CONTEXT:")
            for i, doc in enumerate(doc_ctx[:5], 1):
                name = doc.get("document_name", "unknown")
                passage = doc.get("passage", "")[:300]
                parts.append(f"  [{i}] {name}: {passage}")
        else:
            parts.append("\nDOCUMENT CONTEXT: No document references available.")

        return "\n".join(parts)

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Parse JSON from Bedrock response, handling markdown fences and edge cases."""
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try to find JSON object in the text (Bedrock sometimes adds preamble)
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        # Try fixing common issues: trailing commas, unescaped newlines
        if start != -1 and end > start:
            candidate = text[start:end + 1]
            # Remove trailing commas before } or ]
            import re as _re
            candidate = _re.sub(r',\s*([}\]])', r'\1', candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse Bedrock JSON response: %s", text[:200])
        return {}

    @staticmethod
    def _extract_text_from_analysis(value: str) -> str:
        """If analysis value looks like JSON, extract the inner 'analysis' text."""
        if not isinstance(value, str):
            return str(value) if value else ""
        stripped = value.strip()
        if stripped.startswith("{"):
            try:
                inner = json.loads(stripped)
                if isinstance(inner, dict) and "analysis" in inner:
                    return inner["analysis"]
            except (json.JSONDecodeError, ValueError):
                # Try extracting between first "analysis": " and the next unescaped "
                import re as _re
                m = _re.search(r'"analysis"\s*:\s*"((?:[^"\\]|\\.)*)"', stripped)
                if m:
                    return m.group(1).replace('\\"', '"').replace('\\n', '\n')
        return value
