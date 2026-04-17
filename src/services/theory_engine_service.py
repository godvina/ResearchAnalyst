"""Theory-Driven Investigation Engine Service.

Generates, scores, stores, and retrieves investigative theories using the
Analysis of Competing Hypotheses (ACH) framework.  Delegates evidence
decomposition, search, and classification to the existing
HypothesisTestingService, then layers 5-dimension ACH scoring on top.

Bedrock Claude Haiku is used for theory generation, classification, and
scoring.  Neptune is optional — the service degrades gracefully when the
graph database is unavailable.
"""

import json
import logging
import os
import ssl
import urllib.request
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_NEPTUNE_ENABLED = os.environ.get("NEPTUNE_ENABLED", "true") == "true"


class TheoryEngineService:
    """Generates, scores, stores, and retrieves investigative theories using ACH framework."""

    ACH_WEIGHTS = {
        "evidence_consistency": 0.25,
        "evidence_diversity": 0.20,
        "predictive_power": 0.20,
        "contradiction_strength": 0.20,
        "evidence_gaps": 0.15,
    }

    VALID_THEORY_TYPES = {"financial", "temporal", "relational", "behavioral", "structural"}
    VALID_VERDICTS = {"confirmed", "refuted", "inconclusive"}

    # --- Case File Section Constants ---
    SECTION_NAMES = [
        "theory_statement",         # 0
        "classification",           # 1
        "ach_scorecard",            # 2
        "evidence_for",             # 3
        "evidence_against",         # 4
        "evidence_gaps",            # 5
        "key_entities",             # 6
        "timeline",                 # 7
        "competing_theories",       # 8
        "investigator_assessment",  # 9
        "recommended_actions",      # 10
        "legal_analysis",           # 11
        "confidence_level",         # 12
    ]

    SECTION_DISPLAY_NAMES = [
        "Theory Statement", "Classification", "ACH Scorecard",
        "Evidence For", "Evidence Against", "Evidence Gaps",
        "Key Entities", "Timeline", "Competing Theories",
        "Investigator Assessment", "Recommended Actions",
        "Legal Analysis", "Confidence Level",
    ]

    def __init__(self, aurora_cm, bedrock_client, hypothesis_svc,
                 neptune_endpoint: str = "", neptune_port: str = "8182"):
        self._db = aurora_cm
        self._bedrock = bedrock_client
        self._hypothesis_svc = hypothesis_svc
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    _table_ensured = False

    def _ensure_table(self):
        """Create the theories table if it doesn't exist (idempotent)."""
        if TheoryEngineService._table_ensured:
            return
        try:
            with self._db.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS theories (
                        theory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
                        title VARCHAR(255) NOT NULL,
                        description TEXT NOT NULL,
                        theory_type VARCHAR(20) NOT NULL CHECK (theory_type IN ('financial','temporal','relational','behavioral','structural')),
                        overall_score INTEGER NOT NULL DEFAULT 50 CHECK (overall_score >= 0 AND overall_score <= 100),
                        evidence_consistency INTEGER NOT NULL DEFAULT 50 CHECK (evidence_consistency >= 0 AND evidence_consistency <= 100),
                        evidence_diversity INTEGER NOT NULL DEFAULT 50 CHECK (evidence_diversity >= 0 AND evidence_diversity <= 100),
                        predictive_power INTEGER NOT NULL DEFAULT 50 CHECK (predictive_power >= 0 AND predictive_power <= 100),
                        contradiction_strength INTEGER NOT NULL DEFAULT 50 CHECK (contradiction_strength >= 0 AND contradiction_strength <= 100),
                        evidence_gaps INTEGER NOT NULL DEFAULT 50 CHECK (evidence_gaps >= 0 AND evidence_gaps <= 100),
                        supporting_entities JSONB NOT NULL DEFAULT '[]',
                        evidence_count INTEGER NOT NULL DEFAULT 0,
                        verdict VARCHAR(20) CHECK (verdict IS NULL OR verdict IN ('confirmed','refuted','inconclusive')),
                        created_by VARCHAR(50) NOT NULL DEFAULT 'ai',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        scored_at TIMESTAMP WITH TIME ZONE
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_theories_case ON theories(case_file_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_theories_score ON theories(overall_score)")
            TheoryEngineService._table_ensured = True
        except Exception as e:
            logger.warning("Failed to ensure theories table: %s", e)

    def _invoke_bedrock(self, prompt: str, max_tokens: int = 2048) -> str:
        """Shared Bedrock invocation helper. Returns text or empty string on failure."""
        if not self._bedrock:
            return ""
        model_id = os.environ.get(
            "BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
        )
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = self._bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(resp["body"].read())
        return result.get("content", [{}])[0].get("text", "")

    # ------------------------------------------------------------------
    # Titan Embed helper (Task 5.7)
    # ------------------------------------------------------------------

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector via Bedrock Titan Embed.

        Uses the same self._bedrock client (bedrock-runtime) used for Haiku LLM calls.
        Returns list[float] or empty list on failure.
        """
        if not self._bedrock or not text:
            return []
        embedding_model_id = os.environ.get(
            "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v1"
        )
        try:
            body = json.dumps({"inputText": text[:8000]})  # Titan Embed max ~8K chars
            resp = self._bedrock.invoke_model(
                modelId=embedding_model_id,
                body=body,
            )
            result = json.loads(resp["body"].read())
            embedding = result.get("embedding", [])
            if isinstance(embedding, list) and len(embedding) > 0:
                logger.info("Generated embedding with %d dimensions", len(embedding))
                return embedding
            logger.warning("Titan Embed returned empty embedding")
            return []
        except Exception as e:
            logger.warning("Titan Embed invocation failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # KNN evidence retrieval (Task 5.1)
    # ------------------------------------------------------------------

    def _fetch_knn_evidence(self, case_id: str, theory_title: str,
                            theory_description: str) -> list[dict]:
        """Fetch the 30 most relevant documents via pgvector KNN cosine similarity.

        Falls back to recency query when:
        - Embedding generation fails (Bedrock unavailable)
        - No documents have embeddings in the case

        Returns list of {"filename": str, "text": str, "document_id": str}.
        """
        # Generate embedding for the theory
        query_text = f"{theory_title} {theory_description}"
        embedding = self._generate_embedding(query_text)

        try:
            with self._db.cursor() as cur:
                if not embedding:
                    # Fallback: no embedding available, use recency
                    logger.info("No embedding available for KNN — falling back to recency query for case %s", case_id)
                    cur.execute(
                        "SELECT source_filename, LEFT(raw_text, 300), document_id "
                        "FROM documents WHERE case_file_id = %s "
                        "ORDER BY indexed_at DESC LIMIT 30",
                        (case_id,),
                    )
                else:
                    # Check if any documents have embeddings
                    cur.execute(
                        "SELECT COUNT(*) FROM documents WHERE case_file_id = %s AND embedding IS NOT NULL",
                        (case_id,),
                    )
                    embed_count = cur.fetchone()[0]

                    if embed_count == 0:
                        # No embeddings in case — fall back to recency
                        logger.info("No document embeddings found for case %s — falling back to recency query", case_id)
                        cur.execute(
                            "SELECT source_filename, LEFT(raw_text, 300), document_id "
                            "FROM documents WHERE case_file_id = %s "
                            "ORDER BY indexed_at DESC LIMIT 30",
                            (case_id,),
                        )
                    else:
                        # KNN cosine similarity search
                        logger.info("Performing KNN search for case %s with %d embedded docs", case_id, embed_count)
                        cur.execute(
                            "SELECT source_filename, LEFT(raw_text, 300), document_id "
                            "FROM documents WHERE case_file_id = %s "
                            "ORDER BY embedding <=> %s::vector LIMIT 30",
                            (case_id, str(embedding)),
                        )

                results = []
                for r in cur.fetchall():
                    results.append({
                        "filename": r[0] or "",
                        "text": r[1] or "",
                        "document_id": str(r[2]) if r[2] else "",
                    })
                logger.info("Fetched %d evidence documents for case %s", len(results), case_id)
                return results
        except Exception as e:
            logger.warning("KNN evidence fetch failed for case %s: %s", case_id, e)
            return []

    # ------------------------------------------------------------------
    # KNN entity extraction (Task 5.2)
    # ------------------------------------------------------------------

    def _fetch_knn_entities(self, case_id: str, document_ids: list[str]) -> list[str]:
        """Extract entity names co-occurring in KNN-retrieved documents.

        Queries the entities table directly (entities.document_id column).
        Returns up to 40 entity names, ordered by occurrence_count DESC.
        On any failure, returns empty list (graceful degradation).
        """
        if not self._db or not document_ids:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT e.canonical_name, e.entity_type, e.occurrence_count "
                    "FROM entities e "
                    "WHERE e.case_file_id = %s AND e.document_id = ANY(%s) "
                    "ORDER BY e.occurrence_count DESC LIMIT 40",
                    (case_id, document_ids),
                )
                entity_names = [r[0] for r in cur.fetchall()]
                logger.info("Fetched %d KNN entities for case %s from %d documents",
                            len(entity_names), case_id, len(document_ids))
                return entity_names
        except Exception as e:
            logger.warning("KNN entity fetch failed for case %s: %s", case_id, e)
            return []

    def _gather_case_context(self, case_id: str) -> dict:
        """Query Aurora for documents, entities, findings, and pattern_reports."""
        context: dict = {"documents": [], "entities": [], "findings": [], "patterns": [], "neptune": {}}
        if not self._db:
            return context
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT document_id, source_filename, LEFT(raw_text, 100) "
                    "FROM documents WHERE case_file_id = %s "
                    "ORDER BY indexed_at DESC LIMIT 50",
                    (case_id,),
                )
                context["documents"] = [
                    {"filename": r[1] or str(r[0]), "content": r[2] or ""}
                    for r in cur.fetchall()
                ]

                cur.execute(
                    "SELECT canonical_name, entity_type, occurrence_count "
                    "FROM entities WHERE case_file_id = %s "
                    "ORDER BY occurrence_count DESC LIMIT 500",
                    (case_id,),
                )
                context["entities"] = [{"name": r[0], "type": r[1], "count": r[2]} for r in cur.fetchall()]

                cur.execute(
                    "SELECT content, tagged_entities FROM findings WHERE case_file_id = %s LIMIT 100",
                    (case_id,),
                )
                context["findings"] = [{"text": r[0], "entities": r[1]} for r in cur.fetchall()]

                cur.execute(
                    "SELECT patterns FROM pattern_reports WHERE case_file_id = %s ORDER BY created_at DESC LIMIT 5",
                    (case_id,),
                )
                context["patterns"] = [r[0] for r in cur.fetchall()]
        except Exception as e:
            logger.warning("Failed to gather case context for %s: %s", case_id, str(e)[:300])

        logger.info("Theory context for %s: %d docs, %d entities, %d findings, %d patterns",
                     case_id, len(context["documents"]), len(context["entities"]),
                     len(context["findings"]), len(context["patterns"]))

        # Optionally enrich with Neptune
        if _NEPTUNE_ENABLED and self._neptune_endpoint:
            context["neptune"] = self._query_neptune(case_id)

        return context

    def _query_neptune(self, case_id: str) -> dict:
        """Query Neptune for entity relationships, clusters, and bridges. Returns empty dict on failure."""
        if not self._neptune_endpoint:
            return {}
        try:
            url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
            query = (
                f"g.V().has('case_id', '{case_id}')"
                f".bothE().otherV().path().by(valueMap(true)).limit(200)"
            )
            data = json.dumps({"gremlin": query}).encode("utf-8")
            ctx = ssl.create_default_context()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                body = json.loads(resp.read())
                result = body.get("result", {}).get("data", {})
                return {"relationships": result} if result else {}
        except Exception as e:
            logger.warning("Neptune query failed (proceeding without graph data): %s", e)
            return {}

    def _extract_entities(self, case_id: str, text: str) -> list:
        """Match entity names from text against the case's entity set in Aurora."""
        if not self._db or not text:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT canonical_name FROM entities WHERE case_file_id = %s",
                    (case_id,),
                )
                entity_names = {r[0] for r in cur.fetchall()}
            text_lower = text.lower()
            return [name for name in entity_names if name.lower() in text_lower]
        except Exception as e:
            logger.warning("Entity extraction failed: %s", e)
            return []

    def _classify_theory_type(self, description: str) -> str:
        """Use Bedrock to classify a theory description into a Theory_Type."""
        prompt = (
            f"Classify this investigative theory into exactly one category.\n"
            f"Categories: financial, temporal, relational, behavioral, structural\n\n"
            f"Theory: \"{description[:500]}\"\n\n"
            f"Return ONLY the category name, nothing else."
        )
        try:
            result = self._invoke_bedrock(prompt, max_tokens=20).strip().lower()
            if result in self.VALID_THEORY_TYPES:
                return result
        except Exception as e:
            logger.warning("Theory type classification failed: %s", e)
        return "behavioral"

    def _score_dimension(self, theory: dict, evidence: list, dimension: str) -> int:
        """Prompt Bedrock for a single ACH dimension score 0-100."""
        dim_descriptions = {
            "evidence_consistency": "how much case evidence directly supports this theory",
            "evidence_diversity": "whether supporting evidence comes from multiple independent sources",
            "predictive_power": "whether this theory explains observations that other theories cannot",
            "contradiction_strength": "the strength of contradicting evidence (high score = weak contradictions, favorable)",
            "evidence_gaps": "evidence completeness (high score = few gaps, favorable)",
        }
        evidence_summary = "\n".join(
            f"- {e.get('filename', 'doc')}: {e.get('text', str(e))[:150]}"
            for e in evidence[:20]
        )
        prompt = (
            f"Score this investigative theory on the dimension: {dimension}\n"
            f"Dimension meaning: {dim_descriptions.get(dimension, dimension)}\n\n"
            f"Theory: \"{theory.get('title', '')}: {theory.get('description', '')[:300]}\"\n\n"
            f"Case evidence:\n{evidence_summary}\n\n"
            f"Return ONLY an integer score from 0 to 100."
        )
        try:
            text = self._invoke_bedrock(prompt, max_tokens=20).strip()
            digits = "".join(c for c in text if c.isdigit())
            if digits:
                return max(0, min(100, int(digits)))
        except Exception as e:
            logger.warning("Dimension scoring failed for %s: %s", dimension, e)
        return 50

    def _compute_overall_score(self, dimensions: dict) -> int:
        """Weighted average of 5 ACH dimensions, clamped to int 0-100."""
        total = sum(
            dimensions.get(dim, 50) * weight
            for dim, weight in self.ACH_WEIGHTS.items()
        )
        return max(0, min(100, int(round(total))))

    def _generate_evidence_gaps(self, theory: dict, evidence: list) -> list:
        """Prompt Bedrock to identify missing evidence with suggested search queries."""
        evidence_summary = "\n".join(
            f"- {e.get('filename', 'doc')}: {e.get('text', str(e))[:150]}"
            for e in evidence[:15]
        )
        prompt = (
            f"Identify 3-5 specific evidence gaps for this investigative theory.\n\n"
            f"Theory: \"{theory.get('title', '')}: {theory.get('description', '')[:300]}\"\n\n"
            f"Current evidence:\n{evidence_summary}\n\n"
            f"For each gap, provide a description and a search query to find the missing evidence.\n"
            f"Return a JSON array: [{{\"description\": \"...\", \"search_query\": \"...\"}}]\n"
            f"Return ONLY the JSON array."
        )
        try:
            text = self._invoke_bedrock(prompt, max_tokens=1024)
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            logger.warning("Evidence gap generation failed: %s", e)
        return []

    # ------------------------------------------------------------------
    # Case-file internal helpers
    # ------------------------------------------------------------------

    _case_file_table_ensured = False

    def _ensure_case_file_table(self):
        """Create the theory_case_files table if it doesn't exist (idempotent)."""
        if TheoryEngineService._case_file_table_ensured:
            return
        try:
            with self._db.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS theory_case_files (
                        case_file_content_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        theory_id UUID NOT NULL REFERENCES theories(theory_id) ON DELETE CASCADE,
                        case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
                        content JSONB NOT NULL DEFAULT '{}'::jsonb,
                        generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        last_edited_at TIMESTAMP WITH TIME ZONE,
                        version INTEGER NOT NULL DEFAULT 1,
                        UNIQUE (theory_id)
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_tcf_theory ON theory_case_files(theory_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_tcf_case ON theory_case_files(case_file_id)")
            TheoryEngineService._case_file_table_ensured = True
        except Exception as e:
            logger.warning("Failed to ensure theory_case_files table: %s", e)

    def _resolve_entities(self, case_id: str, entity_names: list) -> list:
        """Query entities table for canonical records matching *entity_names*.

        Uses case-insensitive matching via LOWER().
        Returns list of {canonical_name, entity_type, occurrence_count}.
        Names with no match in the entities table are excluded.
        """
        if not self._db or not entity_names:
            return []
        try:
            lower_names = [n.lower() for n in entity_names]
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT canonical_name, entity_type, occurrence_count "
                    "FROM entities "
                    "WHERE case_file_id = %s AND LOWER(canonical_name) = ANY(%s)",
                    (case_id, lower_names),
                )
                return [
                    {"canonical_name": r[0], "entity_type": r[1], "occurrence_count": r[2]}
                    for r in cur.fetchall()
                ]
        except Exception as e:
            logger.warning("Entity resolution failed for case %s: %s", case_id, e)
            return []

    def _build_case_file_prompt(self, theory: dict, evidence: list,
                                 entities: list, competing: list) -> str:
        """Build the Bedrock prompt for Pass 1: sections 1–11 case file generation.

        (Task 5.5) Expanded to 30 evidence docs at 300 chars, 40 entities.
        Legal analysis (section 12) is generated separately in Pass 2.
        """
        # Evidence summaries — up to 30 docs, 300 chars each (KNN-retrieved)
        evidence_lines = "\n".join(
            f"- {e.get('filename', 'doc')}: {str(e.get('text', ''))[:300]}"
            for e in evidence[:30]
        )

        # Entity lines — up to 40 (KNN-enriched)
        entity_lines = "\n".join(
            f"- {ent.get('canonical_name', ent.get('name', '?'))} "
            f"({ent.get('entity_type', ent.get('type', 'unknown'))}, "
            f"{ent.get('occurrence_count', ent.get('count', 0))} occurrences)"
            for ent in entities[:40]
        )

        # Competing theories — up to 5
        competing_lines = "\n".join(
            f"- {ct.get('title', '?')}: score {ct.get('overall_score', ct.get('score', '?'))}"
            for ct in competing[:5]
        )

        prompt = (
            "You are an expert investigative analyst. Generate a structured 12-section case file\n"
            "(sections 1-11 plus confidence level) for the following theory.\n"
            "NOTE: Legal analysis will be generated separately — do NOT include it.\n\n"
            f"THEORY:\n"
            f"Title: {theory.get('title', '')}\n"
            f"Description: {theory.get('description', '')}\n"
            f"Type: {theory.get('theory_type', '')}\n"
            f"ACH Scores: evidence_consistency={theory.get('evidence_consistency', 50)}, "
            f"evidence_diversity={theory.get('evidence_diversity', 50)}, "
            f"predictive_power={theory.get('predictive_power', 50)}, "
            f"contradiction_strength={theory.get('contradiction_strength', 50)}, "
            f"evidence_gaps={theory.get('evidence_gaps', 50)}\n"
            f"Overall Score: {theory.get('overall_score', 50)}\n\n"
            f"CASE EVIDENCE ({len(evidence)} documents):\n{evidence_lines}\n\n"
            f"KEY ENTITIES ({len(entities)} resolved):\n{entity_lines}\n\n"
            f"COMPETING THEORIES:\n{competing_lines}\n\n"
            "Return a JSON object with exactly these 12 keys. Each section follows its specified structure:\n\n"
            '{\n'
            '  "theory_statement": {"title": "...", "description": "..."},\n'
            '  "classification": {"theory_type": "...", "rationale": "..."},\n'
            '  "ach_scorecard": {"dimensions": [{"name": "...", "score": N, "interpretation": "..."}]},\n'
            '  "evidence_for": {"citations": [{"source": "...", "excerpt": "...", "relevance": N, "entities": [...]}]},\n'
            '  "evidence_against": {"citations": [{"source": "...", "excerpt": "...", "relevance": N, "explanation": "..."}]},\n'
            '  "evidence_gaps": {"gaps": [{"description": "...", "search_query": "..."}]},\n'
            '  "key_entities": {"entities": [{"name": "...", "type": "...", "count": N, "role": "..."}]},\n'
            '  "timeline": {"events": [{"date": "...", "description": "...", "source": "...", "classification": "supporting|contradicting"}]},\n'
            '  "competing_theories": {"theories": [{"title": "...", "score": N, "comparison": "..."}]},\n'
            '  "investigator_assessment": {"verdict": "...", "notes": ""},\n'
            '  "recommended_actions": {"actions": [{"type": "subpoena|interview|document_search|field_investigation", "target": "...", "priority": "high|medium|low"}]},\n'
            '  "confidence_level": {"overall_score": N, "justification": "..."}\n'
            '}\n\n'
            "Return ONLY the JSON object. No markdown, no explanation."
        )
        return prompt

    def _parse_case_file_response(self, response_text: str) -> dict:
        """Parse Bedrock JSON response into validated 12-section structure.

        Adds ``is_gap`` boolean to each section (default ``False``).
        Returns dict keyed by section name, or empty dict on parse failure.
        """
        if not response_text:
            return {}
        try:
            # Strip markdown fences if present
            text = response_text.strip()
            if text.startswith("```"):
                first_nl = text.find("\n")
                last_fence = text.rfind("```")
                if last_fence > first_nl:
                    text = text[first_nl + 1:last_fence].strip()

            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                return {}
            parsed = json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse Bedrock case-file JSON")
            return {}

        # Validate all 12 section keys are present
        sections: dict = {}
        for name in self.SECTION_NAMES:
            section_data = parsed.get(name, {})
            if not isinstance(section_data, dict):
                section_data = {}
            section_data.setdefault("is_gap", False)
            sections[name] = section_data

        return sections

    def _detect_section_gaps(self, sections: dict) -> dict:
        """Mark sections with insufficient content as gaps.

        Gap conditions:
        - evidence_for: zero citations
        - evidence_against: zero citations
        - timeline: fewer than 2 events
        - key_entities: zero resolved entities
        """
        gap_rules = {
            "evidence_for": lambda s: len(s.get("citations", [])) == 0,
            "evidence_against": lambda s: len(s.get("citations", [])) == 0,
            "timeline": lambda s: len(s.get("events", [])) < 2,
            "key_entities": lambda s: len(s.get("entities", [])) == 0,
            "legal_analysis": lambda s: (
                # For legal/civil: check primary_statute
                (s.get("analysis_type", "legal") in ("legal", "civil", "") and (
                    not s.get("primary_statute") or not isinstance(s.get("primary_statute"), dict) or not s.get("primary_statute", {}).get("citation")
                )) or
                # For research: check hypothesis_assessment
                (s.get("analysis_type") == "research" and not s.get("hypothesis_assessment")) or
                # For intelligence: check source_assessment
                (s.get("analysis_type") == "intelligence" and not s.get("source_assessment"))
            ),
        }
        for name in self.SECTION_NAMES:
            section = sections.get(name, {})
            checker = gap_rules.get(name)
            if checker and checker(section):
                section["is_gap"] = True
            else:
                section.setdefault("is_gap", False)
            sections[name] = section
        return sections

    def _build_fallback_case_file(self, theory: dict, entities: list) -> dict:
        """Build partial case file from Aurora data when Bedrock fails.

        Populates sections 0 (theory_statement), 1 (classification),
        2 (ach_scorecard), and 6 (key_entities) with ``is_gap=False``.
        Marks the remaining 8 sections with ``is_gap=True``.
        """
        # Sections derivable from Aurora data
        populated_indices = {0, 1, 2, 6}

        sections: dict = {}
        for idx, name in enumerate(self.SECTION_NAMES):
            if idx in populated_indices:
                sections[name] = self._build_fallback_section(name, theory, entities)
                sections[name]["is_gap"] = False
            else:
                sections[name] = {"is_gap": True}
        return sections

    def _build_fallback_section(self, name: str, theory: dict, entities: list) -> dict:
        """Return Aurora-derived content for a single fallback section."""
        if name == "theory_statement":
            return {
                "title": theory.get("title", ""),
                "description": theory.get("description", ""),
            }
        if name == "classification":
            return {
                "theory_type": theory.get("theory_type", ""),
                "rationale": f"Classified as {theory.get('theory_type', 'unknown')} based on theory content.",
            }
        if name == "ach_scorecard":
            dims = []
            for dim_name in [
                "evidence_consistency", "evidence_diversity",
                "predictive_power", "contradiction_strength", "evidence_gaps",
            ]:
                dims.append({
                    "name": dim_name,
                    "score": theory.get(dim_name, 50),
                    "interpretation": f"Score from ACH analysis.",
                })
            return {"dimensions": dims}
        if name == "key_entities":
            return {
                "entities": [
                    {
                        "name": ent.get("canonical_name", ent.get("name", "")),
                        "type": ent.get("entity_type", ent.get("type", "unknown")),
                        "count": ent.get("occurrence_count", ent.get("count", 0)),
                        "role": "Entity associated with this theory.",
                    }
                    for ent in entities
                ]
            }
        return {}

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def generate_theories(self, case_id: str) -> list:
        """Scan all case evidence and generate 10-20 ranked theories."""
        # Ensure theories table exists
        self._ensure_table()

        context = self._gather_case_context(case_id)

        if not context["documents"] and not context["entities"]:
            logger.warning("No documents or entities found for case %s — cannot generate theories", case_id)
            return []

        # Build prompt
        doc_summary = "\n".join(
            f"- {d['filename']}" for d in context["documents"][:50]
        )
        entity_summary = "\n".join(
            f"- {e['name']} ({e['type']})" for e in context["entities"][:100]
        )
        finding_summary = "\n".join(
            f"- {f['text'][:150]}" for f in context["findings"][:30]
        )
        neptune_summary = ""
        if context.get("neptune"):
            neptune_summary = f"\nGraph relationships:\n{json.dumps(context['neptune'])[:1000]}"

        prompt = (
            f"You are an expert investigative analyst. Based on the following case evidence, "
            f"generate 10-20 ranked investigative theories.\n\n"
            f"Documents ({len(context['documents'])}):\n{doc_summary}\n\n"
            f"Entities ({len(context['entities'])}):\n{entity_summary}\n\n"
            f"Findings:\n{finding_summary}\n"
            f"{neptune_summary}\n\n"
            f"For each theory, provide:\n"
            f"- title: concise title under 120 characters\n"
            f"- description: one paragraph explaining the theory\n"
            f"- theory_type: one of financial, temporal, relational, behavioral, structural\n"
            f"- initial_score: 0-100 based on evidence strength\n\n"
            f"Return a JSON array of theory objects. Return ONLY the JSON array."
        )

        text = self._invoke_bedrock(prompt, max_tokens=2048)
        if not text:
            raise RuntimeError("Bedrock invocation failed during theory generation")

        # Parse theories from response
        start = text.find("[")
        end = text.rfind("]") + 1
        theories_raw = []
        if start >= 0 and end > start:
            try:
                theories_raw = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.warning("Failed to parse Bedrock theory response")
                raise RuntimeError("Failed to parse theory generation response")

        if not theories_raw:
            raise RuntimeError("Bedrock returned no theories")

        # Decompose first theory for claim structure (delegate to HypothesisTestingService)
        if self._hypothesis_svc and theories_raw:
            try:
                self._hypothesis_svc._decompose(theories_raw[0].get("description", ""))
            except Exception:
                pass  # Non-critical

        # Store each theory in Aurora
        stored_theories = []
        for t in theories_raw[:20]:
            title = str(t.get("title", "Untitled Theory"))[:255]
            description = str(t.get("description", ""))
            theory_type = str(t.get("theory_type", "")).lower()
            if theory_type not in self.VALID_THEORY_TYPES:
                theory_type = self._classify_theory_type(description)
            initial_score = max(0, min(100, int(t.get("initial_score", 50))))
            entities = self._extract_entities(case_id, description)

            try:
                with self._db.cursor() as cur:
                    cur.execute(
                        """INSERT INTO theories
                           (case_file_id, title, description, theory_type, overall_score,
                            supporting_entities, evidence_count, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s, 0, 'ai')
                           RETURNING theory_id, created_at""",
                        (case_id, title, description, theory_type, initial_score,
                         json.dumps(entities)),
                    )
                    row = cur.fetchone()
                    theory = {
                        "theory_id": str(row[0]),
                        "case_file_id": case_id,
                        "title": title,
                        "description": description,
                        "theory_type": theory_type,
                        "overall_score": initial_score,
                        "evidence_consistency": 50,
                        "evidence_diversity": 50,
                        "predictive_power": 50,
                        "contradiction_strength": 50,
                        "evidence_gaps": 50,
                        "supporting_entities": entities,
                        "evidence_count": 0,
                        "verdict": None,
                        "created_by": "ai",
                        "created_at": row[1].isoformat() if row[1] else datetime.now(timezone.utc).isoformat(),
                        "scored_at": None,
                    }
                    stored_theories.append(theory)
            except Exception as e:
                logger.warning("Failed to store theory '%s': %s", title, e)

        return stored_theories

    def create_manual_theory(self, case_id: str, title: str, description: str,
                              theory_type: str = None, supporting_entities: list = None) -> dict:
        """Create an investigator-submitted theory with default scores of 50."""
        if theory_type and theory_type.lower() in self.VALID_THEORY_TYPES:
            theory_type = theory_type.lower()
        else:
            theory_type = self._classify_theory_type(description)

        entities = supporting_entities or []
        extracted = self._extract_entities(case_id, description)
        # Merge provided entities with extracted ones (deduplicated)
        all_entities = list(dict.fromkeys(entities + extracted))

        with self._db.cursor() as cur:
            cur.execute(
                """INSERT INTO theories
                   (case_file_id, title, description, theory_type, overall_score,
                    evidence_consistency, evidence_diversity, predictive_power,
                    contradiction_strength, evidence_gaps,
                    supporting_entities, evidence_count, created_by)
                   VALUES (%s, %s, %s, %s, 50, 50, 50, 50, 50, 50, %s, 0, 'investigator')
                   RETURNING theory_id, created_at""",
                (case_id, title[:255], description, theory_type, json.dumps(all_entities)),
            )
            row = cur.fetchone()

        return {
            "theory_id": str(row[0]),
            "case_file_id": case_id,
            "title": title[:255],
            "description": description,
            "theory_type": theory_type,
            "overall_score": 50,
            "evidence_consistency": 50,
            "evidence_diversity": 50,
            "predictive_power": 50,
            "contradiction_strength": 50,
            "evidence_gaps": 50,
            "supporting_entities": all_entities,
            "evidence_count": 0,
            "verdict": None,
            "created_by": "investigator",
            "created_at": row[1].isoformat() if row[1] else datetime.now(timezone.utc).isoformat(),
            "scored_at": None,
        }

    def score_theory(self, case_id: str, theory_id: str) -> dict:
        """Score/re-score a theory using ACH 5-dimension framework.

        1. Retrieve theory from Aurora
        2. Retrieve case evidence
        3. Classify evidence via HypothesisTestingService
        4. Score each ACH dimension via Bedrock
        5. Compute overall_score, update Aurora
        6. Return updated theory with evidence classifications
        """
        # 1. Retrieve theory
        theory = None
        with self._db.cursor() as cur:
            cur.execute(
                """SELECT theory_id, case_file_id, title, description, theory_type,
                          overall_score, supporting_entities, evidence_count, verdict,
                          created_by, created_at, scored_at
                   FROM theories WHERE theory_id = %s AND case_file_id = %s""",
                (theory_id, case_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            theory = {
                "theory_id": str(row[0]),
                "case_file_id": str(row[1]),
                "title": row[2],
                "description": row[3],
                "theory_type": row[4],
                "overall_score": row[5],
                "supporting_entities": row[6] if isinstance(row[6], list) else json.loads(row[6] or "[]"),
                "evidence_count": row[7],
                "verdict": row[8],
                "created_by": row[9],
                "created_at": row[10].isoformat() if row[10] else None,
                "scored_at": row[11].isoformat() if row[11] else None,
            }

        # 2. Retrieve case evidence (documents + findings)
        evidence = []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT source_filename, LEFT(raw_text, 300) FROM documents "
                    "WHERE case_file_id = %s LIMIT 100",
                    (case_id,),
                )
                for r in cur.fetchall():
                    evidence.append({"filename": r[0] or "", "text": r[1] or ""})

                cur.execute(
                    "SELECT content, tagged_entities FROM findings WHERE case_file_id = %s LIMIT 50",
                    (case_id,),
                )
                for r in cur.fetchall():
                    evidence.append({"filename": "finding", "text": r[0] or ""})
        except Exception as e:
            logger.warning("Failed to retrieve evidence for scoring: %s", e)

        # 3. Classify evidence via HypothesisTestingService
        classifications = {"supporting": [], "contradicting": [], "neutral": []}
        if self._hypothesis_svc and evidence:
            for ev in evidence[:50]:
                try:
                    result = self._hypothesis_svc._classify_evidence(
                        theory["description"], [ev]
                    )
                    status = result.get("status", "UNVERIFIED").upper()
                    entry = {
                        "text": ev.get("text", "")[:300],
                        "filename": ev.get("filename", ""),
                        "relevance": result.get("confidence", 50),
                    }
                    if status == "SUPPORTED":
                        entry["entities"] = self._extract_entities(case_id, ev.get("text", ""))
                        classifications["supporting"].append(entry)
                    elif status == "CONTRADICTED":
                        entry["explanation"] = result.get("reasoning", "")
                        classifications["contradicting"].append(entry)
                    else:
                        classifications["neutral"].append(entry)
                except Exception as e:
                    logger.warning("Evidence classification failed: %s", e)

        # 4. Score each ACH dimension via Bedrock
        dimensions = {}
        for dim in self.ACH_WEIGHTS:
            dimensions[dim] = self._score_dimension(theory, evidence, dim)

        # 5. Compute overall score
        overall = self._compute_overall_score(dimensions)
        evidence_count = len(classifications["supporting"]) + len(classifications["contradicting"])

        # 6. Update Aurora
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """UPDATE theories SET
                       overall_score = %s,
                       evidence_consistency = %s,
                       evidence_diversity = %s,
                       predictive_power = %s,
                       contradiction_strength = %s,
                       evidence_gaps = %s,
                       evidence_count = %s,
                       scored_at = NOW()
                       WHERE theory_id = %s AND case_file_id = %s""",
                    (overall, dimensions["evidence_consistency"], dimensions["evidence_diversity"],
                     dimensions["predictive_power"], dimensions["contradiction_strength"],
                     dimensions["evidence_gaps"], evidence_count, theory_id, case_id),
                )
        except Exception as e:
            logger.warning("Failed to update theory scores: %s", e)

        theory.update({
            "overall_score": overall,
            "evidence_consistency": dimensions["evidence_consistency"],
            "evidence_diversity": dimensions["evidence_diversity"],
            "predictive_power": dimensions["predictive_power"],
            "contradiction_strength": dimensions["contradiction_strength"],
            "evidence_gaps": dimensions["evidence_gaps"],
            "evidence_count": evidence_count,
            "scored_at": datetime.now(timezone.utc).isoformat(),
            "evidence": classifications,
        })
        return theory

    def get_theories(self, case_id: str) -> list:
        """List all theories for a case, sorted by overall_score descending."""
        self._ensure_table()
        theories = []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT theory_id, case_file_id, title, description, theory_type,
                              overall_score, evidence_consistency, evidence_diversity,
                              predictive_power, contradiction_strength, evidence_gaps,
                              supporting_entities, evidence_count, verdict,
                              created_by, created_at, scored_at
                       FROM theories
                       WHERE case_file_id = %s
                       ORDER BY overall_score DESC""",
                    (case_id,),
                )
                for row in cur.fetchall():
                    theories.append({
                        "theory_id": str(row[0]),
                        "case_file_id": str(row[1]),
                        "title": row[2],
                        "description": row[3],
                        "theory_type": row[4],
                        "overall_score": row[5],
                        "evidence_consistency": row[6],
                        "evidence_diversity": row[7],
                        "predictive_power": row[8],
                        "contradiction_strength": row[9],
                        "evidence_gaps": row[10],
                        "supporting_entities": row[11] if isinstance(row[11], list) else json.loads(row[11] or "[]"),
                        "evidence_count": row[12],
                        "verdict": row[13],
                        "created_by": row[14],
                        "created_at": row[15].isoformat() if row[15] else None,
                        "scored_at": row[16].isoformat() if row[16] else None,
                    })
        except Exception as e:
            logger.warning("Failed to list theories: %s", e)
        return theories

    def get_theory_detail(self, case_id: str, theory_id: str) -> dict:
        """Get full theory detail including classified evidence passages and evidence gaps."""
        # Fetch base theory
        theory = None
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT theory_id, case_file_id, title, description, theory_type,
                              overall_score, evidence_consistency, evidence_diversity,
                              predictive_power, contradiction_strength, evidence_gaps,
                              supporting_entities, evidence_count, verdict,
                              created_by, created_at, scored_at
                       FROM theories
                       WHERE theory_id = %s AND case_file_id = %s""",
                    (theory_id, case_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                theory = {
                    "theory_id": str(row[0]),
                    "case_file_id": str(row[1]),
                    "title": row[2],
                    "description": row[3],
                    "theory_type": row[4],
                    "overall_score": row[5],
                    "evidence_consistency": row[6],
                    "evidence_diversity": row[7],
                    "predictive_power": row[8],
                    "contradiction_strength": row[9],
                    "evidence_gaps": row[10],
                    "supporting_entities": row[11] if isinstance(row[11], list) else json.loads(row[11] or "[]"),
                    "evidence_count": row[12],
                    "verdict": row[13],
                    "created_by": row[14],
                    "created_at": row[15].isoformat() if row[15] else None,
                    "scored_at": row[16].isoformat() if row[16] else None,
                }
        except Exception as e:
            logger.warning("Failed to fetch theory detail: %s", e)
            return None

        # Classify evidence for the detail view
        # Limit to 10 docs to avoid Lambda timeout (each doc = 1 Bedrock call)
        evidence = []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT source_filename, LEFT(raw_text, 300) FROM documents WHERE case_file_id = %s LIMIT 10",
                    (case_id,),
                )
                for r in cur.fetchall():
                    evidence.append({"filename": r[0] or "", "text": r[1] or ""})
        except Exception as e:
            logger.warning("Failed to retrieve evidence for detail: %s", e)

        classifications = {"supporting": [], "contradicting": [], "neutral": []}
        if self._hypothesis_svc and evidence:
            for ev in evidence[:5]:
                try:
                    result = self._hypothesis_svc._classify_evidence(
                        theory["description"], [ev]
                    )
                    status = result.get("status", "UNVERIFIED").upper()
                    entry = {
                        "text": ev.get("text", "")[:300],
                        "filename": ev.get("filename", ""),
                        "relevance": result.get("confidence", 50),
                    }
                    if status == "SUPPORTED":
                        entry["entities"] = self._extract_entities(case_id, ev.get("text", ""))
                        classifications["supporting"].append(entry)
                    elif status == "CONTRADICTED":
                        entry["explanation"] = result.get("reasoning", "")
                        classifications["contradicting"].append(entry)
                    else:
                        classifications["neutral"].append(entry)
                except Exception:
                    pass

        # Sort by relevance descending
        classifications["supporting"].sort(key=lambda x: x.get("relevance", 0), reverse=True)
        classifications["contradicting"].sort(key=lambda x: x.get("relevance", 0), reverse=True)

        theory["evidence"] = classifications
        theory["evidence_gaps"] = self._generate_evidence_gaps(theory, evidence)

        # Competing theories (other theories for same case)
        competing = []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT theory_id, title, overall_score FROM theories
                       WHERE case_file_id = %s AND theory_id != %s
                       ORDER BY overall_score DESC LIMIT 5""",
                    (case_id, theory_id),
                )
                for r in cur.fetchall():
                    competing.append({"theory_id": str(r[0]), "title": r[1], "overall_score": r[2]})
        except Exception:
            pass
        theory["competing_theories"] = competing

        # --- Case file status (task 2.13) ---
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT content, generated_at, last_edited_at, version "
                    "FROM theory_case_files WHERE theory_id = %s",
                    (theory_id,),
                )
                cf_row = cur.fetchone()
                if cf_row:
                    theory["case_file_status"] = "available"
                    theory["case_file"] = {
                        "sections": cf_row[0] if isinstance(cf_row[0], dict) else json.loads(cf_row[0] or "{}"),
                        "generated_at": cf_row[1].isoformat() if cf_row[1] else None,
                        "last_edited_at": cf_row[2].isoformat() if cf_row[2] else None,
                        "version": cf_row[3],
                    }
                else:
                    theory["case_file_status"] = "not_generated"
        except Exception:
            theory["case_file_status"] = "not_generated"

        # Include promoted_sub_case_id from theories table
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT promoted_sub_case_id FROM theories WHERE theory_id = %s",
                    (theory_id,),
                )
                promo_row = cur.fetchone()
                theory["promoted_sub_case_id"] = str(promo_row[0]) if promo_row and promo_row[0] else None
        except Exception:
            theory["promoted_sub_case_id"] = None

        return theory

    def set_verdict(self, case_id: str, theory_id: str, verdict: str) -> dict:
        """Set investigator verdict (confirmed/refuted/inconclusive) on a theory."""
        if verdict not in self.VALID_VERDICTS:
            raise ValueError(f"Verdict must be one of: {', '.join(self.VALID_VERDICTS)}")

        with self._db.cursor() as cur:
            cur.execute(
                """UPDATE theories SET verdict = %s
                   WHERE theory_id = %s AND case_file_id = %s
                   RETURNING theory_id, title, overall_score, verdict""",
                (verdict, theory_id, case_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "theory_id": str(row[0]),
                "title": row[1],
                "overall_score": row[2],
                "verdict": row[3],
            }

    def mark_theories_stale(self, case_id: str) -> int:
        """Mark all theories for a case as stale (scored_at = NULL).

        Called when new evidence is ingested so scores are re-evaluated.
        Returns the number of theories marked stale.
        """
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "UPDATE theories SET scored_at = NULL WHERE case_file_id = %s",
                    (case_id,),
                )
                return cur.rowcount
        except Exception as e:
            logger.warning("Failed to mark theories stale: %s", e)
            return 0

    def compute_theory_maturity(self, case_id: str) -> int:
        """Compute theory maturity: (theories with verdict / total) * 100.

        Returns 0 if no theories exist.
        """
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*), COUNT(verdict) FROM theories WHERE case_file_id = %s",
                    (case_id,),
                )
                row = cur.fetchone()
                total = row[0] or 0
                with_verdict = row[1] or 0
                if total == 0:
                    return 0
                return int((with_verdict / total) * 100)
        except Exception as e:
            logger.warning("Failed to compute theory maturity: %s", e)
            return 0

    # ------------------------------------------------------------------
    # Legal Analysis generation
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Theory category classification for adaptive analysis
    # ------------------------------------------------------------------

    _CATEGORY_KEYWORDS = {
        "criminal_financial": [
            "fraud", "money laundering", "embezzlement", "tax evasion",
            "wire fraud", "bank", "account", "transaction",
        ],
        "criminal": [
            "trafficking", "conspiracy", "murder", "assault", "drug",
            "weapon", "kidnap", "extortion", "bribery", "obstruction",
        ],
        "civil": [
            "breach", "contract", "damages", "negligence", "liability",
            "tort", "civil",
        ],
        "research": [
            "alien", "ufo", "ancient", "paranormal", "conspiracy theory",
            "mythology", "archaeological", "historical",
        ],
        "intelligence": [
            "intelligence", "surveillance", "osint", "counterintelligence",
            "espionage",
        ],
    }

    def _classify_theory_category(self, theory: dict) -> str:
        """Classify a theory into an analysis category using simple heuristics.

        Checks theory_type and description against keyword lists.
        Returns one of: criminal_financial, criminal, civil, research, intelligence.
        Default is 'criminal'.
        """
        theory_type = (theory.get("theory_type") or "").lower()
        description = (theory.get("description") or "").lower()
        combined = theory_type + " " + description

        # Check financial type first
        if theory_type == "financial":
            return "criminal_financial"

        # Check keyword categories in priority order
        for category in ["criminal_financial", "research", "intelligence", "civil", "criminal"]:
            for keyword in self._CATEGORY_KEYWORDS.get(category, []):
                if keyword in combined:
                    return category

        return "criminal"

    def _generate_legal_analysis(self, case_id: str, theory: dict) -> dict:
        """Generate adaptive analysis section for a theory via Bedrock.

        Classifies the theory into a category (criminal, criminal_financial,
        civil, research, intelligence) and uses a category-appropriate prompt.

        Returns a dict with analysis_type and category-specific fields.
        On failure, returns a gap section with is_gap=true.
        """
        category = self._classify_theory_category(theory)
        title = theory.get("title", "")
        description = theory.get("description", "")
        theory_type = theory.get("theory_type", "")
        overall_score = theory.get("overall_score", 50)

        if category in ("criminal", "criminal_financial"):
            prompt = self._build_legal_prompt(title, description, theory_type, overall_score)
        elif category == "research":
            prompt = self._build_research_prompt(title, description)
        elif category == "intelligence":
            prompt = self._build_intelligence_prompt(title, description)
        elif category == "civil":
            prompt = self._build_civil_prompt(title, description, theory_type, overall_score)
        else:
            prompt = self._build_legal_prompt(title, description, theory_type, overall_score)

        try:
            text = self._invoke_bedrock(prompt, max_tokens=4096)
            if not text:
                raise RuntimeError("Empty Bedrock response for analysis")
            # Parse JSON from response
            clean = text.strip()
            if clean.startswith("```"):
                first_nl = clean.find("\n")
                last_fence = clean.rfind("```")
                if last_fence > first_nl:
                    clean = clean[first_nl + 1:last_fence].strip()
            start = clean.find("{")
            end = clean.rfind("}") + 1
            if start < 0 or end <= start:
                raise RuntimeError("No JSON object found in analysis response")
            parsed = json.loads(clean[start:end])
            parsed.setdefault("is_gap", False)
            # Ensure analysis_type is set based on category
            if "analysis_type" not in parsed:
                if category in ("criminal", "criminal_financial"):
                    parsed["analysis_type"] = "legal"
                elif category == "civil":
                    parsed["analysis_type"] = "civil"
                else:
                    parsed["analysis_type"] = category
            return parsed
        except Exception as e:
            logger.warning("Analysis generation failed for case %s: %s", case_id, e)
            return {"is_gap": True}

    def _build_legal_prompt(self, title: str, description: str,
                            theory_type: str, overall_score: int) -> str:
        """Build the formal AUSA legal analysis prompt for criminal/financial cases."""
        return (
            "You are a senior federal prosecutor (AUSA) with 20+ years of experience. "
            "Analyze the following investigative theory and provide a comprehensive legal analysis.\n\n"
            f"Theory Title: {title}\n"
            f"Theory Description: {description}\n"
            f"Theory Type: {theory_type}\n"
            f"Overall Score: {overall_score}\n\n"
            "Return a JSON object with these keys:\n"
            '{\n'
            '  "analysis_type": "legal",\n'
            '  "primary_statute": {"citation": "...", "title": "...", "match_strength": N (0-100), '
            '"confidence": "high|medium|low", "justification": "...", '
            '"rejected_alternatives": [{"citation": "...", "reason_rejected": "..."}]},\n'
            '  "element_readiness": {"elements": [{"element_name": "...", "status": "met|partial|unmet", '
            '"evidence_strength": N (0-100), "evidence_summary": "..."}], "readiness_score": N (0-100)},\n'
            '  "sentencing_advisory": {"likely_sentence": "...", "fine_or_penalty": "...", '
            '"supervised_release": "...", "ussg_references": ["..."], "precedent_cases": ["..."]},\n'
            '  "alternative_charges": [{"citation": "...", "title": "...", '
            '"conviction_likelihood": N (0-100), "reasoning": "..."}],\n'
            '  "charging_recommendation": {"recommendation_text": "...", "legal_reasoning": "...", '
            '"evidence_gaps": ["..."], "confidence": "high|medium|low", "ussg_references": ["..."]},\n'
            '  "summary_line": "§ XXXX Title (XX% match) · Readiness XX% · Sentence XX-XX mo"\n'
            '}\n\n'
            "Return ONLY the JSON object. No markdown, no explanation."
        )

    def _build_research_prompt(self, title: str, description: str) -> str:
        """Build the research analysis prompt for research/historical/paranormal theories."""
        return (
            "You are a senior research analyst. Analyze the following theory and provide a research assessment.\n\n"
            f"Theory Title: {title}\n"
            f"Theory Description: {description}\n\n"
            "Return a JSON object:\n"
            '{\n'
            '  "analysis_type": "research",\n'
            '  "summary_line": "Research Assessment: [one-line summary of hypothesis strength and key findings]",\n'
            '  "hypothesis_assessment": {"strength": "strong|moderate|weak", "basis": "...", "methodology_notes": "..."},\n'
            '  "source_credibility": {"overall_rating": "high|medium|low", "primary_sources": [{"source": "...", "credibility": "high|medium|low", "notes": "..."}]},\n'
            '  "corroboration_status": {"corroborated_claims": ["..."], "uncorroborated_claims": ["..."], "contradicted_claims": ["..."]},\n'
            '  "open_questions": [{"question": "...", "research_approach": "...", "priority": "high|medium|low"}],\n'
            '  "research_recommendation": {"summary": "...", "next_steps": ["..."], "confidence": "high|medium|low"}\n'
            '}\n'
            "Return ONLY the JSON object."
        )

    def _build_intelligence_prompt(self, title: str, description: str) -> str:
        """Build the intelligence assessment prompt for intel/surveillance theories."""
        return (
            "You are a senior intelligence analyst. Provide an intelligence assessment for this theory.\n\n"
            f"Theory Title: {title}\n"
            f"Theory Description: {description}\n\n"
            "Return a JSON object:\n"
            '{\n'
            '  "analysis_type": "intelligence",\n'
            '  "summary_line": "Intel Assessment: [one-line summary of reliability and key intelligence]",\n'
            '  "source_assessment": {"reliability": "A|B|C|D|E|F", "information_credibility": "1|2|3|4|5|6", "rating_explanation": "..."},\n'
            '  "corroboration_matrix": {"confirmed": ["..."], "probable": ["..."], "possible": ["..."], "doubtful": ["..."]},\n'
            '  "collection_gaps": [{"gap": "...", "collection_method": "HUMINT|SIGINT|OSINT|IMINT", "priority": "high|medium|low"}],\n'
            '  "threat_indicators": [{"indicator": "...", "severity": "high|medium|low", "confidence": "high|medium|low"}],\n'
            '  "intelligence_recommendation": {"summary": "...", "collection_priorities": ["..."], "confidence": "high|medium|low"}\n'
            '}\n'
            "Return ONLY the JSON object."
        )

    def _build_civil_prompt(self, title: str, description: str,
                            theory_type: str, overall_score: int) -> str:
        """Build the civil analysis prompt — same structure as AUSA but with civil terminology."""
        return (
            "You are a senior civil litigation attorney with 20+ years of experience. "
            "Analyze the following theory and provide a comprehensive civil legal analysis.\n\n"
            f"Theory Title: {title}\n"
            f"Theory Description: {description}\n"
            f"Theory Type: {theory_type}\n"
            f"Overall Score: {overall_score}\n\n"
            "Return a JSON object with these keys:\n"
            '{\n'
            '  "analysis_type": "civil",\n'
            '  "primary_statute": {"citation": "...", "title": "...", "match_strength": N (0-100), '
            '"confidence": "high|medium|low", "justification": "...", '
            '"rejected_alternatives": [{"citation": "...", "reason_rejected": "..."}]},\n'
            '  "element_readiness": {"elements": [{"element_name": "...", "status": "met|partial|unmet", '
            '"evidence_strength": N (0-100), "evidence_summary": "..."}], "readiness_score": N (0-100)},\n'
            '  "sentencing_advisory": {"likely_sentence": "...", "fine_or_penalty": "...", '
            '"supervised_release": "...", "ussg_references": ["..."], "precedent_cases": ["..."]},\n'
            '  "alternative_charges": [{"citation": "...", "title": "...", '
            '"conviction_likelihood": N (0-100), "reasoning": "..."}],\n'
            '  "charging_recommendation": {"recommendation_text": "...", "legal_reasoning": "...", '
            '"evidence_gaps": ["..."], "confidence": "high|medium|low", "ussg_references": ["..."]},\n'
            '  "summary_line": "Civil: [statute/cause of action] (XX% match) · Readiness XX% · Likely outcome: ..."\n'
            '}\n\n'
            "Return ONLY the JSON object. No markdown, no explanation."
        )

    # ------------------------------------------------------------------
    # Two-pass legal prompt builder (Task 5.3)
    # ------------------------------------------------------------------

    def _build_legal_pass2_prompt(self, theory: dict, entities: list,
                                   sections_1_to_11: dict,
                                   evidence: list = None) -> str:
        """Build a focused prompt for Pass 2: legal_analysis section only.

        Reuses the evidence already fetched in Pass 1 (no second KNN query)
        to stay within the 29s API Gateway timeout.
        """
        # Reuse Pass 1 evidence — no second KNN query needed
        legal_evidence = evidence or []

        # Build evidence lines
        legal_evidence_lines = "\n".join(
            f"- {e.get('filename', 'doc')}: {str(e.get('text', ''))[:300]}"
            for e in legal_evidence[:30]
        )

        # Build entity lines
        entity_lines = "\n".join(
            f"- {ent.get('canonical_name', ent.get('name', '?'))} "
            f"({ent.get('entity_type', ent.get('type', 'unknown'))})"
            for ent in entities[:40]
        )

        # Summarize Pass 1 findings for context
        evidence_for_count = len(sections_1_to_11.get("evidence_for", {}).get("citations", []))
        evidence_against_count = len(sections_1_to_11.get("evidence_against", {}).get("citations", []))
        timeline_count = len(sections_1_to_11.get("timeline", {}).get("events", []))
        key_entity_names = [
            e.get("name", "") for e in sections_1_to_11.get("key_entities", {}).get("entities", [])[:10]
        ]
        verdict = sections_1_to_11.get("investigator_assessment", {}).get("verdict", "unknown")

        prompt = (
            "You are a senior federal prosecutor (AUSA) with 20+ years of experience. "
            "Generate ONLY the legal_analysis section for the following investigative theory case file.\n\n"
            f"THEORY:\n"
            f"Title: {theory.get('title', '')}\n"
            f"Description: {theory.get('description', '')}\n"
            f"Type: {theory.get('theory_type', '')}\n"
            f"ACH Scores: evidence_consistency={theory.get('evidence_consistency', 50)}, "
            f"evidence_diversity={theory.get('evidence_diversity', 50)}, "
            f"predictive_power={theory.get('predictive_power', 50)}, "
            f"contradiction_strength={theory.get('contradiction_strength', 50)}, "
            f"evidence_gaps={theory.get('evidence_gaps', 50)}\n"
            f"Overall Score: {theory.get('overall_score', 50)}\n\n"
            f"CASE FILE SUMMARY (from sections 1-11):\n"
            f"- Evidence For: {evidence_for_count} citations\n"
            f"- Evidence Against: {evidence_against_count} citations\n"
            f"- Timeline Events: {timeline_count}\n"
            f"- Key Entities: {', '.join(key_entity_names) if key_entity_names else 'none'}\n"
            f"- Investigator Verdict: {verdict}\n\n"
            f"LEGAL-RELEVANT EVIDENCE ({len(legal_evidence)} documents):\n{legal_evidence_lines}\n\n"
            f"KEY ENTITIES ({len(entities)} resolved):\n{entity_lines}\n\n"
            "Return a JSON object with ONLY the legal_analysis section:\n\n"
            '{\n'
            '  "legal_analysis": {\n'
            '    "primary_statute": {"citation": "...", "title": "...", "match_strength": N (0-100), '
            '"confidence": "high|medium|low", "justification": "...", '
            '"rejected_alternatives": [{"citation": "...", "reason_rejected": "..."}]},\n'
            '    "element_readiness": {"elements": [{"element_name": "...", "status": "met|partial|unmet", '
            '"evidence_strength": N (0-100), "evidence_summary": "..."}], "readiness_score": N (0-100)},\n'
            '    "sentencing_advisory": {"likely_sentence": "...", "fine_or_penalty": "...", '
            '"supervised_release": "...", "ussg_references": ["..."], "precedent_cases": ["..."]},\n'
            '    "alternative_charges": [{"citation": "...", "title": "...", '
            '"conviction_likelihood": N (0-100), "reasoning": "..."}],\n'
            '    "charging_recommendation": {"recommendation_text": "...", "legal_reasoning": "...", '
            '"evidence_gaps": ["..."], "confidence": "high|medium|low", "ussg_references": ["..."]},\n'
            '    "summary_line": "§ XXXX Title (XX% match) · Readiness XX% · Sentence XX-XX mo"\n'
            '  }\n'
            '}\n\n'
            "Return ONLY the JSON object. No markdown, no explanation."
        )
        return prompt

    # ------------------------------------------------------------------
    # Case File public methods (tasks 2.8 – 2.13)
    # ------------------------------------------------------------------

    def generate_case_file(self, case_id: str, theory_id: str) -> dict:
        """Generate a 13-section case file via two-pass Bedrock generation.

        1. Fetch theory record from theories table
        2. Fetch evidence via KNN cosine similarity (Task 5.4)
        3. Resolve entities + KNN entity enrichment (Task 5.4)
        4. Fetch competing theories for the same case
        5. Build prompt via _build_case_file_prompt(), invoke Bedrock Pass 1 with max_tokens=6144 (Task 5.6)
        6. Parse Pass 1 response via _parse_case_file_response()
        7. Enrich Key Entities section with Aurora entity data
        7b. Pass 2: Generate legal_analysis via _build_legal_pass2_prompt() (Task 5.6)
        8. Detect section gaps via _detect_section_gaps()
        9. On Bedrock failure: return _build_fallback_case_file() result
        10. Return the 13-section dict
        """
        # 1. Fetch theory record
        theory = None
        with self._db.cursor() as cur:
            cur.execute(
                """SELECT theory_id, case_file_id, title, description, theory_type,
                          overall_score, evidence_consistency, evidence_diversity,
                          predictive_power, contradiction_strength, evidence_gaps,
                          supporting_entities, evidence_count, verdict,
                          created_by, created_at, scored_at
                   FROM theories WHERE theory_id = %s AND case_file_id = %s""",
                (theory_id, case_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            theory = {
                "theory_id": str(row[0]),
                "case_file_id": str(row[1]),
                "title": row[2],
                "description": row[3],
                "theory_type": row[4],
                "overall_score": row[5],
                "evidence_consistency": row[6],
                "evidence_diversity": row[7],
                "predictive_power": row[8],
                "contradiction_strength": row[9],
                "evidence_gaps": row[10],
                "supporting_entities": row[11] if isinstance(row[11], list) else json.loads(row[11] or "[]"),
                "evidence_count": row[12],
                "verdict": row[13],
                "created_by": row[14],
                "created_at": row[15].isoformat() if row[15] else None,
                "scored_at": row[16].isoformat() if row[16] else None,
            }

        # 2. Fetch evidence via KNN cosine similarity (Task 5.4)
        # Original blind recency query (kept as reference):
        #   cur.execute(
        #       "SELECT source_filename, LEFT(raw_text, 150) "
        #       "FROM documents WHERE case_file_id = %s "
        #       "ORDER BY indexed_at DESC LIMIT 15",
        #       (case_id,),
        #   )
        evidence = self._fetch_knn_evidence(case_id, theory["title"], theory["description"])

        # 3. Resolve entities + KNN entity enrichment (Task 5.4)
        entity_names = theory.get("supporting_entities", [])

        # Extract document IDs from KNN results for entity enrichment
        knn_doc_ids = [e["document_id"] for e in evidence if e.get("document_id")]
        knn_entity_names = self._fetch_knn_entities(case_id, knn_doc_ids)

        # Merge KNN entity names into entity_names (deduplicated)
        combined_entity_names = list(dict.fromkeys(entity_names + knn_entity_names))
        logger.info("Entity enrichment: %d original + %d KNN = %d combined (deduplicated) for case %s",
                     len(entity_names), len(knn_entity_names), len(combined_entity_names), case_id)

        # Re-resolve the combined entity list
        entities = self._resolve_entities(case_id, combined_entity_names)

        # 4. Fetch competing theories
        competing = []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT theory_id, title, overall_score FROM theories
                       WHERE case_file_id = %s AND theory_id != %s
                       ORDER BY overall_score DESC LIMIT 5""",
                    (case_id, theory_id),
                )
                for r in cur.fetchall():
                    competing.append({"theory_id": str(r[0]), "title": r[1], "overall_score": r[2]})
        except Exception as e:
            logger.warning("Failed to fetch competing theories: %s", e)

        # 5. Build prompt and invoke Bedrock — Pass 1 (sections 1–11 + confidence, max_tokens=4096)
        prompt = self._build_case_file_prompt(theory, evidence, entities, competing)
        try:
            response_text = self._invoke_bedrock(prompt, max_tokens=4096)
            if not response_text:
                raise RuntimeError("Empty Bedrock response")
        except Exception as e:
            logger.warning("Bedrock case file generation (Pass 1) failed: %s", e)
            # 9. Fallback on Bedrock failure
            return self._build_fallback_case_file(theory, entities)

        # 6. Parse Pass 1 response
        sections = self._parse_case_file_response(response_text)
        if not sections:
            return self._build_fallback_case_file(theory, entities)

        # 7. Enrich Key Entities section with Aurora entity data
        if entities:
            entity_lookup = {
                ent["canonical_name"].lower(): ent for ent in entities
            }
            enriched_entities = []
            # Start with entities from Bedrock response
            for be_ent in sections.get("key_entities", {}).get("entities", []):
                name_lower = be_ent.get("name", "").lower()
                if name_lower in entity_lookup:
                    aurora_ent = entity_lookup.pop(name_lower)
                    enriched_entities.append({
                        "name": aurora_ent["canonical_name"],
                        "type": aurora_ent["entity_type"],
                        "count": aurora_ent["occurrence_count"],
                        "role": be_ent.get("role", "Entity associated with this theory."),
                    })
            # Add remaining Aurora entities not in Bedrock response
            for aurora_ent in entity_lookup.values():
                enriched_entities.append({
                    "name": aurora_ent["canonical_name"],
                    "type": aurora_ent["entity_type"],
                    "count": aurora_ent["occurrence_count"],
                    "role": "Entity associated with this theory.",
                })
            sections["key_entities"]["entities"] = enriched_entities

        # 7b. Pass 2: Generate legal_analysis via dedicated Bedrock call (Task 5.6)
        try:
            legal_prompt = self._build_legal_pass2_prompt(theory, entities, sections, evidence=evidence)
            logger.info("Invoking Bedrock Pass 2 for legal_analysis section")
            legal_response_text = self._invoke_bedrock(legal_prompt, max_tokens=2048)
            if not legal_response_text:
                raise RuntimeError("Empty Bedrock response for Pass 2 legal analysis")

            # Parse Pass 2 response
            legal_text = legal_response_text.strip()
            if legal_text.startswith("```"):
                first_nl = legal_text.find("\n")
                last_fence = legal_text.rfind("```")
                if last_fence > first_nl:
                    legal_text = legal_text[first_nl + 1:last_fence].strip()
            start = legal_text.find("{")
            end = legal_text.rfind("}") + 1
            if start < 0 or end <= start:
                raise RuntimeError("No JSON object found in Pass 2 response")
            parsed_legal = json.loads(legal_text[start:end])

            # Extract legal_analysis from the parsed response
            if "legal_analysis" in parsed_legal:
                legal_section = parsed_legal["legal_analysis"]
            else:
                # Response might be the legal_analysis content directly
                legal_section = parsed_legal
            legal_section.setdefault("is_gap", False)
            sections["legal_analysis"] = legal_section
            logger.info("Pass 2 legal_analysis section populated successfully")
        except Exception as e:
            logger.warning("Bedrock Pass 2 (legal_analysis) failed: %s — using gap placeholder", e)
            sections["legal_analysis"] = {"is_gap": True}

        # 8. Detect section gaps
        sections = self._detect_section_gaps(sections)

        # Apply confidence penalty for detected gaps (Task 6.1)
        gap_count = sum(1 for name in self.SECTION_NAMES if sections.get(name, {}).get("is_gap", False))
        if gap_count > 0:
            conf = sections.get("confidence_level", {})
            raw_score = conf.get("overall_score", 50)
            penalty = 5 * gap_count
            penalized_score = max(0, raw_score - penalty)
            conf["overall_score"] = penalized_score
            sections["confidence_level"] = conf
            logger.info("Confidence penalty: %d gaps detected, score %d → %d (-%d)", gap_count, raw_score, penalized_score, penalty)

        return sections

    def get_or_generate_case_file(self, case_id: str, theory_id: str) -> dict:
        """Return persisted case file or generate + persist a new one.

        1. Ensure theory_case_files table exists
        2. Query for existing content by theory_id
        3. If found, return {sections, generated_at, last_edited_at, version}
        4. If not found, generate, INSERT, and return with metadata
        """
        self._ensure_case_file_table()

        # Check for existing case file
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT content, generated_at, last_edited_at, version "
                    "FROM theory_case_files WHERE theory_id = %s",
                    (theory_id,),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "sections": row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}"),
                        "generated_at": row[1].isoformat() if row[1] else None,
                        "last_edited_at": row[2].isoformat() if row[2] else None,
                        "version": row[3],
                    }
        except Exception as e:
            logger.warning("Failed to query theory_case_files: %s", e)

        # Not found — generate
        sections = self.generate_case_file(case_id, theory_id)
        if sections is None:
            return None

        # Persist
        generated_at = datetime.now(timezone.utc)
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """INSERT INTO theory_case_files (theory_id, case_file_id, content, generated_at)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (theory_id) DO UPDATE
                       SET content = EXCLUDED.content, generated_at = EXCLUDED.generated_at, version = theory_case_files.version + 1
                       RETURNING version""",
                    (theory_id, case_id, json.dumps(sections), generated_at),
                )
                version_row = cur.fetchone()
                version = version_row[0] if version_row else 1
        except Exception as e:
            logger.warning("Failed to persist theory case file: %s", e)
            version = 1

        return {
            "sections": sections,
            "generated_at": generated_at.isoformat(),
            "last_edited_at": None,
            "version": version,
        }

    def update_section(self, case_id: str, theory_id: str,
                       section_index: int, content: dict) -> dict:
        """Update a single section in the persisted case file.

        1. Validate section_index is 0-11
        2. Use PostgreSQL jsonb_set() to update only the target section
        3. Update last_edited_at and increment version
        4. Return updated case file content
        """
        if not isinstance(section_index, int) or section_index < 0 or section_index > 12:
            raise ValueError(f"Section index must be 0-12, got {section_index}")

        section_key = self.SECTION_NAMES[section_index]

        # Ensure is_gap is set in the content
        if isinstance(content, dict):
            content.setdefault("is_gap", False)

        with self._db.cursor() as cur:
            cur.execute(
                """UPDATE theory_case_files
                   SET content = jsonb_set(content, %s, %s::jsonb),
                       last_edited_at = NOW(),
                       version = version + 1
                   WHERE theory_id = %s
                   RETURNING content, generated_at, last_edited_at, version""",
                ('{' + section_key + '}', json.dumps(content), theory_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "sections": row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}"),
                "generated_at": row[1].isoformat() if row[1] else None,
                "last_edited_at": row[2].isoformat() if row[2] else None,
                "version": row[3],
            }

    def regenerate_case_file(self, case_id: str, theory_id: str) -> dict:
        """Regenerate the entire case file, preserving investigator notes.

        1. Fetch existing case file to extract section 9 (investigator_assessment) notes
        2. Call generate_case_file() for fresh content
        3. Merge preserved investigator notes into section 9
        4. UPDATE existing theory_case_files record
        5. Increment version, update generated_at
        6. Return new content with metadata
        """
        # 1. Fetch existing investigator notes
        existing_notes = ""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT content FROM theory_case_files WHERE theory_id = %s",
                    (theory_id,),
                )
                row = cur.fetchone()
                if row:
                    existing_content = row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
                    inv_section = existing_content.get("investigator_assessment", {})
                    existing_notes = inv_section.get("notes", "")
        except Exception as e:
            logger.warning("Failed to fetch existing case file for regeneration: %s", e)

        # 2. Generate fresh content
        sections = self.generate_case_file(case_id, theory_id)
        if sections is None:
            return None

        # 3. Merge preserved investigator notes
        if existing_notes:
            inv = sections.get("investigator_assessment", {})
            inv["notes"] = existing_notes
            sections["investigator_assessment"] = inv

        # 4-5. UPDATE existing record
        generated_at = datetime.now(timezone.utc)
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """UPDATE theory_case_files
                       SET content = %s, generated_at = %s, version = version + 1
                       WHERE theory_id = %s
                       RETURNING version, last_edited_at""",
                    (json.dumps(sections), generated_at, theory_id),
                )
                row = cur.fetchone()
                if row:
                    version = row[0]
                    last_edited_at = row[1].isoformat() if row[1] else None
                else:
                    version = 1
                    last_edited_at = None
        except Exception as e:
            logger.warning("Failed to update regenerated case file: %s", e)
            version = 1
            last_edited_at = None

        return {
            "sections": sections,
            "generated_at": generated_at.isoformat(),
            "last_edited_at": last_edited_at,
            "version": version,
        }

    def promote_to_sub_case(self, case_id: str, theory_id: str) -> dict:
        """Promote a confirmed theory to a sub-case.

        1. Fetch theory, verify verdict == 'confirmed'
        2. Verify promoted_sub_case_id is NULL (not already promoted)
        3. Import CaseFileService, create sub-case
        4. UPDATE theories SET promoted_sub_case_id = new sub_case_id
        5. Return {sub_case_id, theory_id}
        """
        # 1. Fetch theory and verify verdict
        with self._db.cursor() as cur:
            cur.execute(
                """SELECT theory_id, title, description, supporting_entities,
                          verdict, promoted_sub_case_id
                   FROM theories WHERE theory_id = %s AND case_file_id = %s""",
                (theory_id, case_id),
            )
            row = cur.fetchone()
            if not row:
                return None

            title = row[1]
            description = row[2]
            supporting_entities = row[3] if isinstance(row[3], list) else json.loads(row[3] or "[]")
            verdict = row[4]
            promoted_sub_case_id = row[5]

        if verdict != "confirmed":
            raise ValueError("Only confirmed theories can be promoted to sub-cases")

        # 2. Verify not already promoted
        if promoted_sub_case_id is not None:
            raise ValueError(f"Theory already promoted to sub-case {promoted_sub_case_id}")

        # 3. Create sub-case via CaseFileService
        from services.case_file_service import CaseFileService
        from db.connection import ConnectionManager
        from db.neptune import NeptuneConnectionManager

        case_file_svc = CaseFileService(self._db, NeptuneConnectionManager())
        sub_case = case_file_svc.create_sub_case_file(
            parent_case_id=case_id,
            topic_name=title,
            description=description,
            entity_names=supporting_entities,
        )
        new_sub_case_id = sub_case.case_id

        # 4. Update theory with promoted_sub_case_id
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE theories SET promoted_sub_case_id = %s WHERE theory_id = %s",
                (new_sub_case_id, theory_id),
            )

        return {"sub_case_id": new_sub_case_id, "theory_id": theory_id}
