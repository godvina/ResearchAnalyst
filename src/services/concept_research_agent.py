"""Concept Research Agent — Phase 1 of the 2-phase research architecture.

When a user navigates to a pattern in the Pattern Library, this agent
automatically researches the CONCEPT (e.g., "Ley Line Alignments") before
any site-specific investigation. It produces:

1. Executive summary of the research field
2. Key researchers and seminal papers
3. Current state of evidence (proven vs contested)
4. PRIORITIZED investigation targets with reasoning
5. Recommended starting point + rationale

Uses Claude Sonnet for deep multi-step reasoning (not Haiku).
Executes 5 Brave searches to map the concept landscape.
Results are cached in Aurora and inform Phase 2 site investigations.
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Use Sonnet 4 for concept research — fast enough for API Gateway 29s timeout
SONNET_MODEL_ID = os.environ.get(
    "RESEARCH_MODEL_ID",
    "us.anthropic.claude-sonnet-4-6"
)

# Brave Search API key
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", os.environ.get("BRAVE_SEARCH_API_KEY", ""))

# Cache prefix for concept research
CONCEPT_CACHE_PREFIX = "concept_research:"

# System prompt for concept research synthesis
CONCEPT_RESEARCH_SYSTEM_PROMPT = """You are a senior research analyst. Synthesize the search results into a structured JSON briefing.

Return ONLY a valid JSON object (no markdown, no backticks, no preamble):

{"codename": "short dramatic project name", "field_status": "ACTIVE RESEARCH or CONTESTED THEORY or FRINGE HYPOTHESIS or ESTABLISHED SCIENCE", "executive_summary": "3 sentences on current state of research", "priority_targets": [{"rank": 1, "location": "Specific place", "rationale": "Why investigate here", "difficulty": "easy or moderate or hard", "production_value": "Visual appeal"}], "key_researchers": [{"name": "Name", "affiliation": "Place", "contribution": "What they did", "credibility": "high or medium or low"}], "evidence_landscape": {"confirmed": ["proven things"], "contested": ["debated things"], "unexplored": ["open questions"]}, "investigation_strategy": "How to approach this", "red_flags": ["warnings"], "cross_references": ["related topics"]}

RULES: Be specific. Name real researchers. Include 3-5 priority targets ranked by investigation potential. Keep responses concise. No markdown."""


# System prompt for generating search queries
QUERY_GENERATION_PROMPT = """You are a research librarian planning a comprehensive literature search. \
Given a topic from an investigative research project, generate exactly 5 diverse search queries \
that will cover the topic from multiple angles.

The queries should cover:
1. Academic/scientific angle (peer-reviewed research, surveys, papers)
2. Geographic/archaeological angle (specific sites, excavations, field reports)
3. Key researchers angle (who are the experts, what have they published)
4. Counter-arguments angle (skeptics, debunking, methodology critiques)
5. Recent developments angle (latest findings, new technology applications)

Return ONLY a JSON array of 5 strings, no other text:
["query 1", "query 2", "query 3", "query 4", "query 5"]"""


class ConceptResearchAgent:
    """Phase 1 research agent — deep concept analysis before site investigation.

    This agent:
    1. Generates 5 diverse search queries for the concept
    2. Executes all 5 via Brave Search
    3. Synthesizes results with Sonnet into a structured concept briefing
    4. Caches the briefing in Aurora for reuse by Phase 2 site investigations
    """

    def __init__(self, bedrock_client=None, web_search_client=None):
        self._bedrock = bedrock_client
        self._web_search = web_search_client

    def _get_bedrock(self):
        """Lazy-initialize Bedrock client with generous timeouts for Sonnet."""
        if self._bedrock is None:
            import boto3
            from botocore.config import Config

            cfg = Config(
                read_timeout=60,      # Sonnet can take longer
                connect_timeout=10,
                retries={"max_attempts": 2, "mode": "adaptive"},
            )
            self._bedrock = boto3.client("bedrock-runtime", config=cfg)
        return self._bedrock

    def _get_web_search(self):
        """Lazy-initialize the Brave Search client."""
        if self._web_search is None:
            from services.web_search_client import WebSearchClient
            self._web_search = WebSearchClient(api_key=BRAVE_API_KEY, timeout=12)
        return self._web_search

    def _invoke_sonnet(self, system_prompt: str, user_message: str, max_tokens: int = 2000) -> dict:
        """Invoke Bedrock Claude Sonnet with system + user message.

        Returns dict with 'text', 'prompt_tokens', 'completion_tokens'.
        Handles extended thinking responses (multiple content blocks).
        """
        bedrock = self._get_bedrock()

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
            "temperature": 0.4,
        }

        resp = bedrock.invoke_model(
            modelId=SONNET_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )

        resp_body = json.loads(resp["body"].read().decode("utf-8"))
        
        # Handle multiple content blocks (extended thinking returns thinking + text)
        content_blocks = resp_body.get("content", [])
        text = ""
        for block in content_blocks:
            if block.get("type") == "text":
                text = block.get("text", "")
                break
        # Fallback: if no text block found, use first block
        if not text and content_blocks:
            text = content_blocks[0].get("text", "")
        
        usage = resp_body.get("usage", {})

        return {
            "text": text,
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
        }

    def _generate_search_queries(self, concept_name: str, concept_description: str) -> list[str]:
        """Generate 3 diverse search queries for this concept.
        
        Uses pattern-based generation (fast) rather than LLM call to stay
        within API Gateway's 29-second timeout. The concept synthesis call
        is where we spend our Sonnet budget.
        """
        base = concept_name.strip()
        queries = [
            f"{base} academic research documented evidence sites",
            f"{base} key researchers experts publications findings",
            f"{base} latest discoveries 2024 2025 archaeological evidence",
        ]
        return queries

    def _execute_searches(self, queries: list[str]) -> list[dict]:
        """Execute multiple Brave searches and deduplicate results.

        Returns combined list of search results with source query attribution.
        """
        ws = self._get_web_search()
        all_results = []
        seen_urls = set()

        for i, query in enumerate(queries):
            try:
                results = ws.search(query, count=5)
                for r in results:
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        r["source_query"] = query
                        r["query_angle"] = i + 1
                        all_results.append(r)
            except Exception as e:
                logger.warning("Search %d failed for query '%s': %s", i + 1, query[:60], str(e)[:200])

        return all_results

    def _synthesize_concept_briefing(
        self,
        concept_name: str,
        concept_description: str,
        search_results: list[dict],
        taxonomy_context: str = "",
    ) -> dict:
        """Synthesize all search results into a structured concept briefing using Sonnet.

        Returns the parsed JSON briefing dict.
        """
        # Format search results for the synthesis prompt
        if search_results:
            results_text = "\n\n".join(
                f"[Source {i+1} | Query Angle {r.get('query_angle', '?')}]\n"
                f"Title: {r.get('title', 'N/A')}\n"
                f"URL: {r.get('url', 'N/A')}\n"
                f"Snippet: {r.get('snippet', 'N/A')}"
                for i, r in enumerate(search_results[:8])  # Cap at 8 results for speed
            )
        else:
            results_text = "NO SEARCH RESULTS AVAILABLE — synthesize from training data only."

        user_message = (
            f"CONCEPT BRIEFING REQUEST\n"
            f"{'=' * 40}\n"
            f"Concept: {concept_name}\n"
            f"Description: {concept_description}\n"
        )

        if taxonomy_context:
            user_message += f"\nTaxonomy context:\n{taxonomy_context}\n"

        user_message += (
            f"\nTotal sources found: {len(search_results)}\n"
            f"\nRAW INTELLIGENCE (multi-angle search results):\n"
            f"{'=' * 40}\n"
            f"{results_text}\n"
            f"{'=' * 40}\n\n"
            f"Produce your comprehensive CONCEPT BRIEFING based on these sources."
        )

        result = self._invoke_sonnet(
            CONCEPT_RESEARCH_SYSTEM_PROMPT,
            user_message,
            max_tokens=1000,
        )

        # Parse JSON response
        raw_text = result["text"]
        logger.info(
            "Sonnet raw response (first 500 chars): %s",
            raw_text[:500] if raw_text else "EMPTY",
        )
        briefing = self._parse_json_response(raw_text)
        if not briefing:
            logger.warning("JSON parse returned empty for concept research. Raw length: %d", len(raw_text or ""))

        # Attach metadata
        briefing["_meta"] = {
            "model_id": SONNET_MODEL_ID,
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "sources_count": len(search_results),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        return briefing

    def research_concept(
        self,
        concept_name: str,
        concept_description: str = "",
        taxonomy_context: str = "",
        bypass_cache: bool = False,
    ) -> dict:
        """Execute full Phase 1 concept research pipeline.

        Steps:
        1. Check cache (unless bypass_cache=True)
        2. Generate 5 search queries via Sonnet
        3. Execute all searches via Brave
        4. Synthesize into concept briefing via Sonnet
        5. Cache result in Aurora
        6. Return structured briefing

        Args:
            concept_name: The pattern/concept to research (e.g., "Ley Line Alignments").
            concept_description: Optional longer description from taxonomy.
            taxonomy_context: Optional taxonomy context to inform research.
            bypass_cache: Skip cache lookup if True.

        Returns:
            Dict with full concept briefing structure.
        """
        cache_key = self._make_cache_key(concept_name)

        # Step 1: Check cache
        if not bypass_cache:
            cached = self._get_cached_briefing(cache_key)
            if cached:
                cached["_from_cache"] = True
                return cached

        t0 = time.time()

        # Step 2: Generate diverse search queries
        logger.info("Concept research starting: '%s'", concept_name)
        queries = self._generate_search_queries(concept_name, concept_description)
        logger.info("Generated %d search queries for '%s'", len(queries), concept_name)

        # Step 3: Execute all searches
        search_results = self._execute_searches(queries)
        logger.info(
            "Executed searches: %d total results (deduplicated) for '%s'",
            len(search_results), concept_name,
        )

        # Step 4: Synthesize concept briefing
        briefing = self._synthesize_concept_briefing(
            concept_name, concept_description, search_results, taxonomy_context
        )

        # Ensure required fields have defaults
        briefing.setdefault("codename", f"PROJECT {concept_name.upper()[:20]}")
        briefing.setdefault("executive_summary", "Research synthesis pending.")
        briefing.setdefault("field_status", "CONTESTED THEORY")
        briefing.setdefault("key_researchers", [])
        briefing.setdefault("seminal_works", [])
        briefing.setdefault("evidence_landscape", {
            "confirmed": [], "contested": [], "debunked": [], "unexplored": []
        })
        briefing.setdefault("priority_targets", [])
        briefing.setdefault("investigation_strategy", "")
        briefing.setdefault("red_flags", [])
        briefing.setdefault("cross_references", [])

        # Attach raw search data for transparency
        briefing["_search_queries"] = queries
        briefing["_search_results_count"] = len(search_results)
        briefing["_from_cache"] = False

        total_ms = int((time.time() - t0) * 1000)
        logger.info(
            "Concept research complete: '%s' — %d sources, %d targets, %dms",
            concept_name, len(search_results),
            len(briefing.get("priority_targets", [])), total_ms,
        )

        # Step 5: Cache in Aurora
        self._cache_briefing(cache_key, concept_name, briefing)

        return briefing

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _make_cache_key(self, concept_name: str) -> str:
        """Generate a deterministic cache key for a concept."""
        slug = concept_name.lower().strip().replace(" ", "_")
        short_hash = hashlib.md5(slug.encode()).hexdigest()[:8]
        return f"{CONCEPT_CACHE_PREFIX}{slug}_{short_hash}"

    def _get_cached_briefing(self, cache_key: str) -> Optional[dict]:
        """Check Aurora cache for an existing concept briefing."""
        try:
            from db.connection import ConnectionManager
            from services.summary_cache_manager import SummaryCacheManager

            cm = ConnectionManager()
            cache_mgr = SummaryCacheManager(cm)
            cached = cache_mgr.get_cached(cache_key)

            if cached and not cached.is_stale:
                return json.loads(cached.summary_text)
        except Exception as e:
            logger.warning("Concept cache read failed (non-blocking): %s", str(e)[:200])

        return None

    def _cache_briefing(self, cache_key: str, concept_name: str, briefing: dict) -> None:
        """Store concept briefing in Aurora cache AND research findings store."""
        try:
            from db.connection import ConnectionManager
            from services.summary_cache_manager import SummaryCacheManager

            cm = ConnectionManager()
            cache_mgr = SummaryCacheManager(cm, ttl_seconds=86400 * 3)  # 3-day TTL for concepts

            meta = briefing.get("_meta", {})
            cache_mgr.store_summary(
                context_key=cache_key,
                level="concept_research",
                summary_text=json.dumps(briefing, default=str),
                model_id=SONNET_MODEL_ID,
                prompt_tokens=meta.get("prompt_tokens", 0),
                completion_tokens=meta.get("completion_tokens", 0),
            )

            # Also store as a finding for taxonomy enrichment
            from services.research_findings_store import ResearchFindingsStore
            findings_store = ResearchFindingsStore(cm)
            findings_store.store_concept_briefing(
                context_key=cache_key.replace(CONCEPT_CACHE_PREFIX, ""),
                briefing=briefing,
            )
        except Exception as e:
            logger.warning("Concept cache write failed (non-blocking): %s", str(e)[:200])

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(raw_text: str) -> dict:
        """Parse a JSON object from model response, stripping markdown fences.
        
        Handles truncated responses by attempting to close unclosed brackets.
        """
        import re

        if not raw_text or not raw_text.strip():
            return {}

        text = raw_text.strip()

        # Strip markdown code fences
        fence_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
        fence_match = fence_pattern.search(text)
        if fence_match:
            text = fence_match.group(1).strip()
        elif text.startswith("```"):
            # Opening fence without closing — take everything after it
            text = text.split("\n", 1)[-1].strip()

        # Find first { and matching }
        brace_idx = text.find("{")
        if brace_idx == -1:
            return {}

        text = text[brace_idx:]
        brace_count = 0
        end_idx = -1
        for i, ch in enumerate(text):
            if ch == "{":
                brace_count += 1
            elif ch == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break

        if end_idx == -1:
            # Truncated response — repair by trimming to last valid JSON boundary
            # Remove the last incomplete key-value (anything after the last complete entry)
            repair_text = text.rstrip()
            
            # Try progressively trimming from the end until we can parse
            for trim_to in [
                repair_text.rfind('},'),   # last complete object in array
                repair_text.rfind('}'),    # last complete object
                repair_text.rfind('"],'),  # last complete array item
                repair_text.rfind('"]'),   # last complete array
            ]:
                if trim_to <= 0:
                    continue
                candidate = repair_text[:trim_to + 1]
                # Close open brackets
                ob = candidate.count("[") - candidate.count("]")
                candidate += "]" * max(0, ob)
                oc = candidate.count("{") - candidate.count("}")
                candidate += "}" * max(0, oc)
                try:
                    return json.loads(candidate)
                except (json.JSONDecodeError, TypeError):
                    continue
            return {}

        try:
            return json.loads(text[: end_idx + 1])
        except (json.JSONDecodeError, TypeError):
            return {}
