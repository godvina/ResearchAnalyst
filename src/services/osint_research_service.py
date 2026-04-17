"""OSINT Research Service — external intelligence gathering via web search + AI synthesis.

Orchestrates: query formulation (Bedrock), web search (Brave), content extraction,
source classification, AI synthesis, contradiction detection, timeline correlation.
Results cached in Aurora PostgreSQL for 24 hours.
"""

import hashlib
import json
import logging
import re
import ssl
import time
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from typing import Any, Optional

from services.web_search_client import WebSearchClient, WebSearchError

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "us.anthropic.claude-3-haiku-20240307-v1:0"
CACHE_TTL_HOURS = 24
MAX_TEXT_PER_PAGE = 3000
TIME_BUDGET_SECONDS = 20


# ---------------------------------------------------------------------------
# Source classification rules
# ---------------------------------------------------------------------------

SOURCE_WEIGHTS = {
    "government": 0.95,
    "academic": 0.90,
    "legal_filing": 0.85,
    "news": 0.80,
    "corporate_record": 0.70,
    "social_media": 0.40,
    "blog": 0.30,
}

_GOV_DOMAINS = re.compile(r"\.(gov|mil)(/|$)", re.IGNORECASE)
_EDU_DOMAINS = re.compile(r"\.(edu)(/|$)|scholar\.google\.|arxiv\.org", re.IGNORECASE)
_LEGAL_DOMAINS = re.compile(
    r"courtlistener\.com|pacer\.gov|sec\.gov/cgi-bin|law\.cornell\.edu",
    re.IGNORECASE,
)
_NEWS_DOMAINS = {
    "reuters.com", "apnews.com", "nytimes.com", "bbc.com", "bbc.co.uk",
    "washingtonpost.com", "theguardian.com", "cnn.com", "npr.org",
    "wsj.com", "bloomberg.com", "ft.com", "politico.com", "thehill.com",
    "usatoday.com", "abcnews.go.com", "nbcnews.com", "cbsnews.com",
    "foxnews.com", "aljazeera.com", "france24.com", "dw.com",
}
_CORP_DOMAINS = re.compile(
    r"sec\.gov(?!/cgi-bin)|opencorporates\.com|dnb\.com|crunchbase\.com",
    re.IGNORECASE,
)
_SOCIAL_DOMAINS = re.compile(
    r"twitter\.com|x\.com|facebook\.com|reddit\.com|linkedin\.com|instagram\.com|tiktok\.com",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# HTML text extractor
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Strip HTML to plain text, removing script/style/nav/footer/header."""

    _SKIP_TAGS = frozenset({"script", "style", "nav", "footer", "header", "noscript"})

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._pieces.append(data)

    def get_text(self) -> str:
        raw = " ".join(self._pieces)
        # Collapse whitespace
        return re.sub(r"\s+", " ", raw).strip()


def extract_text(html: str) -> str:
    """Extract clean text from HTML, stripping forbidden elements.
    Truncates to MAX_TEXT_PER_PAGE chars."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    text = parser.get_text()
    return text[:MAX_TEXT_PER_PAGE]


def classify_source(url: str, title: str = "") -> tuple:
    """Classify a URL into (source_type, reliability_weight)."""
    if _GOV_DOMAINS.search(url):
        return ("government", SOURCE_WEIGHTS["government"])
    if _EDU_DOMAINS.search(url):
        return ("academic", SOURCE_WEIGHTS["academic"])
    if _LEGAL_DOMAINS.search(url):
        return ("legal_filing", SOURCE_WEIGHTS["legal_filing"])
    # Check known news domains
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower().lstrip("www.")
        if domain in _NEWS_DOMAINS:
            return ("news", SOURCE_WEIGHTS["news"])
    except Exception:
        pass
    if _CORP_DOMAINS.search(url):
        return ("corporate_record", SOURCE_WEIGHTS["corporate_record"])
    if _SOCIAL_DOMAINS.search(url):
        return ("social_media", SOURCE_WEIGHTS["social_media"])
    return ("blog", SOURCE_WEIGHTS["blog"])


def compute_credibility(sources: list) -> dict:
    """Compute credibility rating from source weights.

    Returns: {rating: HIGH|MEDIUM|LOW, explanation: str, weighted_score: float}
    """
    if not sources:
        return {"rating": "LOW", "explanation": "No sources available.", "weighted_score": 0.0}

    weights = [s.get("reliability_weight", 0.3) for s in sources]
    avg = sum(weights) / len(weights)

    # Count by type
    type_counts = {}
    for s in sources:
        st = s.get("source_type", "blog")
        type_counts[st] = type_counts.get(st, 0) + 1
    type_desc = ", ".join(f"{v} {k}" for k, v in sorted(type_counts.items(), key=lambda x: -x[1]))

    if avg >= 0.75:
        rating = "HIGH"
    elif avg >= 0.50:
        rating = "MEDIUM"
    else:
        rating = "LOW"

    return {
        "rating": rating,
        "explanation": f"Based on {type_desc} across {len(sources)} sources.",
        "weighted_score": round(avg, 3),
    }


def deduplicate_results(results: list) -> list:
    """Deduplicate search results by URL, preserving first occurrence."""
    seen = set()
    deduped = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduped.append(r)
    return deduped


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------

class OsintResearchService:
    """Orchestrates the full OSINT research pipeline."""

    def __init__(
        self,
        aurora_cm: Any,
        bedrock_client: Any,
        neptune_endpoint: str = "",
        neptune_port: str = "8182",
        brave_api_key: Optional[str] = None,
    ) -> None:
        self._db = aurora_cm
        self._bedrock = bedrock_client
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port
        self._web: Optional[WebSearchClient] = None
        if brave_api_key:
            self._web = WebSearchClient(brave_api_key, timeout=10)

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    @staticmethod
    def cache_key(case_id: str, research_type: str, context: dict) -> str:
        """Generate SHA-256 cache key from normalized inputs."""
        # Sort context keys for determinism
        normalized = json.dumps(
            {"case_id": case_id, "research_type": research_type, "context": context},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _check_cache(self, key: str) -> Optional[dict]:
        """Return cached Research Card if < 24h old, else None."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT research_card, updated_at FROM osint_research_cache WHERE cache_key = %s",
                    (key,),
                )
                row = cur.fetchone()
                if row:
                    card, updated = row
                    age = (datetime.now(timezone.utc) - updated).total_seconds()
                    if age < CACHE_TTL_HOURS * 3600:
                        if isinstance(card, str):
                            card = json.loads(card)
                        card["cached"] = True
                        return card
        except Exception as exc:
            logger.warning("Cache check failed: %s", str(exc)[:200])
        return None

    def _store_cache(
        self, key: str, case_id: str, research_type: str,
        context_summary: str, research_card: dict,
    ) -> None:
        """Upsert Research Card into cache."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """INSERT INTO osint_research_cache
                       (cache_key, case_id, research_type, context_summary, research_card, updated_at)
                       VALUES (%s, %s, %s, %s, %s, now())
                       ON CONFLICT (cache_key) DO UPDATE
                       SET research_card = EXCLUDED.research_card,
                           updated_at = now()""",
                    (key, case_id, research_type, context_summary,
                     json.dumps(research_card, default=str)),
                )
        except Exception as exc:
            logger.error("Cache write failed: %s", str(exc)[:200])

    def get_cached_results(self, case_id: str, limit: int = 50) -> list:
        """List all cached research results for a case."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT cache_key, research_type, context_summary, research_card, updated_at
                       FROM osint_research_cache
                       WHERE case_id = %s
                       ORDER BY updated_at DESC LIMIT %s""",
                    (case_id, limit),
                )
                results = []
                for row in cur.fetchall():
                    card = row[3]
                    if isinstance(card, str):
                        card = json.loads(card)
                    results.append({
                        "cache_key": row[0],
                        "research_type": row[1],
                        "context_summary": row[2],
                        "research_card": card,
                        "updated_at": row[4].isoformat() if row[4] else None,
                    })
                return results
        except Exception as exc:
            logger.warning("Cache list failed: %s", str(exc)[:200])
            return []

    # ------------------------------------------------------------------
    # Query formulation
    # ------------------------------------------------------------------

    def _formulate_queries(self, research_type: str, context: dict) -> list:
        """Use Bedrock Claude to generate 3-5 search queries."""
        if research_type == "entity":
            ctx_desc = (
                f"Entity: {context.get('entity_name', '')} "
                f"(type: {context.get('entity_type', 'unknown')}). "
                f"Aliases: {', '.join(context.get('aliases', []))}. "
                f"Connected entities: {', '.join(context.get('connected_entities', [])[:5])}."
            )
        elif research_type == "pattern":
            ctx_desc = f"Pattern: {context.get('pattern_summary', '')}. Entities: {', '.join(e.get('name', '') for e in context.get('entities', [])[:5])}."
        else:  # question
            ctx_desc = f"Investigative question: {context.get('question_text', '')}. Entities: {', '.join(context.get('entity_names', [])[:5])}."

        prompt = (
            "You are an investigative intelligence analyst. Generate exactly 4 targeted web search queries "
            "to research the following topic. Cover different angles: public records, news coverage, "
            "regulatory filings, corporate associations, and legal proceedings.\n\n"
            f"Context: {ctx_desc}\n\n"
            "Respond with a JSON array of 4 query strings. No other text."
        )

        try:
            resp = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "[]")
            # Parse JSON array from response
            queries = json.loads(text)
            if isinstance(queries, list) and 3 <= len(queries) <= 5:
                return [str(q) for q in queries]
            # Fallback: take first 4 if too many
            if isinstance(queries, list) and len(queries) > 5:
                return [str(q) for q in queries[:5]]
        except Exception as exc:
            logger.warning("Query formulation via Bedrock failed: %s", str(exc)[:200])

        # Fallback: generate simple queries from context
        name = context.get("entity_name", "") or context.get("question_text", "") or context.get("pattern_summary", "")
        return [
            f"{name} investigation",
            f"{name} news reports",
            f"{name} public records",
            f"{name} legal proceedings",
        ]

    # ------------------------------------------------------------------
    # AI Synthesis
    # ------------------------------------------------------------------

    def _synthesize(self, context: dict, sources: list) -> dict:
        """Call Bedrock Claude to synthesize external findings."""
        source_text = ""
        for i, s in enumerate(sources[:15], 1):
            source_text += f"\n[Source {i}] {s.get('title', '')} ({s.get('source_type', 'unknown')}, reliability: {s.get('reliability_weight', 0.3)})\nURL: {s.get('url', '')}\nContent: {s.get('text', '')[:1500]}\n"

        ctx_summary = context.get("entity_name", "") or context.get("pattern_summary", "") or context.get("question_text", "")

        prompt = (
            "You are a senior investigative journalist research analyst. Synthesize the following web sources "
            "about the topic below into a professional research dossier. Produce a JSON object with these fields:\n"
            '- "summary": A 300-500 word investigative synthesis. Write like a journalist briefing an editor — '
            'lead with the most significant finding, explain WHY it matters, identify patterns across sources, '
            'note what is established fact vs speculation, and end with recommended next steps for investigation.\n'
            '- "corroborating_evidence": Array of 3-7 strings — specific facts that multiple independent sources confirm. '
            'Each should cite which sources agree and why this corroboration matters.\n'
            '- "contradicting_evidence": Array of strings — specific facts where sources disagree or conflict with each other. '
            'Note which sources conflict and the significance of the discrepancy.\n'
            '- "information_gaps": Array of 3-5 strings — critical questions a journalist would want answered that '
            'these sources do NOT address. Frame as actionable research leads.\n'
            '- "key_dates": Array of objects {date, description} — significant dates mentioned across sources, '
            'useful for building a timeline.\n\n'
            f"Topic: {ctx_summary}\n\n"
            f"Sources:\n{source_text}\n\n"
            "Respond ONLY with the JSON object."
        )

        try:
            resp = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 3000,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "{}")
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except Exception as exc:
            logger.warning("AI synthesis failed: %s", str(exc)[:200])

        # Fallback
        return {
            "summary": f"External research found {len(sources)} sources about {ctx_summary}. AI synthesis unavailable.",
            "corroborating_evidence": [],
            "contradicting_evidence": [],
            "information_gaps": ["AI synthesis failed — manual review of sources recommended."],
            "key_dates": [],
        }

    # ------------------------------------------------------------------
    # Contradiction detection
    # ------------------------------------------------------------------

    def _detect_contradictions(self, case_id: str, entity_names: list, external_summary: str) -> list:
        """Compare external findings against internal case evidence."""
        if not entity_names or not external_summary:
            return []

        # Gather internal evidence from Aurora
        internal_evidence = ""
        try:
            with self._db.cursor() as cur:
                placeholders = ",".join(["%s"] * len(entity_names))
                cur.execute(
                    f"""SELECT title, source_filename
                        FROM documents d
                        JOIN entities e ON e.case_file_id = d.case_file_id
                        WHERE d.case_file_id = %s
                          AND e.entity_name IN ({placeholders})
                        LIMIT 10""",
                    [case_id] + entity_names,
                )
                docs = cur.fetchall()
                if docs:
                    internal_evidence = "Internal documents: " + "; ".join(
                        f"{r[0] or r[1]}" for r in docs
                    )
        except Exception as exc:
            logger.warning("Internal evidence query failed: %s", str(exc)[:200])

        if not internal_evidence:
            return []

        prompt = (
            "Compare the internal case evidence with external public source findings. "
            "Identify specific factual contradictions. Return a JSON array where each element has: "
            '"internal_claim", "external_claim", "internal_source", "external_source". '
            "If no contradictions, return an empty array.\n\n"
            f"Internal evidence:\n{internal_evidence[:2000]}\n\n"
            f"External findings:\n{external_summary[:2000]}\n\n"
            "Respond ONLY with the JSON array."
        )

        try:
            resp = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "[]")
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except Exception as exc:
            logger.warning("Contradiction detection failed: %s", str(exc)[:200])
        return []

    # ------------------------------------------------------------------
    # Timeline correlation
    # ------------------------------------------------------------------

    def _correlate_timeline(self, case_id: str, entity_names: list, external_dates: list) -> dict:
        """Cross-reference external dates against internal document timeline."""
        correlations = []
        gaps = []

        if not external_dates:
            return {"correlations": correlations, "gaps": gaps}

        # Get internal dates from Aurora
        internal_dates = []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT entity_name, entity_type FROM entities
                       WHERE case_file_id = %s AND entity_type = 'date'
                       ORDER BY entity_name LIMIT 100""",
                    (case_id,),
                )
                for row in cur.fetchall():
                    internal_dates.append(row[0])
        except Exception as exc:
            logger.warning("Timeline query failed: %s", str(exc)[:200])

        # Simple date matching — find external dates within 30 days of internal dates
        for ext in external_dates:
            ext_date_str = ext.get("date", "")
            ext_desc = ext.get("description", "")
            matched = False
            for int_date_str in internal_dates:
                try:
                    # Try parsing both dates
                    ext_d = _parse_date(ext_date_str)
                    int_d = _parse_date(int_date_str)
                    if ext_d and int_d:
                        gap = abs((ext_d - int_d).days)
                        if gap <= 30:
                            correlations.append({
                                "internal_date": int_date_str,
                                "external_date": ext_date_str,
                                "description": ext_desc,
                                "gap_days": gap,
                            })
                            matched = True
                            break
                except Exception:
                    continue
            if not matched:
                gaps.append({
                    "external_date": ext_date_str,
                    "description": ext_desc,
                    "note": "No matching internal document within 30 days.",
                })

        # Sort chronologically
        correlations.sort(key=lambda x: x.get("external_date", ""))
        gaps.sort(key=lambda x: x.get("external_date", ""))
        return {"correlations": correlations, "gaps": gaps}

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def research(self, case_id: str, research_type: str, context: dict,
                 force_refresh: bool = False) -> dict:
        """Full OSINT research pipeline. Returns a Research Card dict."""
        t0 = time.time()

        # 1. Cache check
        key = self.cache_key(case_id, research_type, context)
        if not force_refresh:
            cached = self._check_cache(key)
            if cached:
                logger.info("OSINT cache hit for %s", key[:16])
                return cached

        # 2. Build context summary
        ctx_summary = (
            context.get("entity_name", "")
            or context.get("pattern_summary", "")
            or context.get("question_text", "")
            or "Unknown"
        )

        # 3. Formulate queries (limit to 2 for speed within API Gateway 29s timeout)
        queries = self._formulate_queries(research_type, context)[:2]
        logger.info("Formulated %d queries in %.1fs", len(queries), time.time() - t0)

        # 4. Web search
        all_results = []
        if self._web:
            for q in queries:
                try:
                    results = self._web.search(q, count=10)
                    all_results.extend(results)
                except WebSearchError as exc:
                    logger.warning("Search failed for query '%s': %s", q[:60], str(exc)[:200])
        else:
            logger.warning("No Brave API key — skipping web search")

        # 5. Deduplicate
        unique_results = deduplicate_results(all_results)
        logger.info("Search: %d total → %d unique results in %.1fs",
                     len(all_results), len(unique_results), time.time() - t0)

        # 6. Use search snippets directly (skip page fetching — too slow from VPC)
        sources = []
        for r in unique_results[:10]:
            source_type, weight = classify_source(r.get("url", ""), r.get("title", ""))
            sources.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "text": r.get("snippet", ""),  # Use snippet as text
                "source_type": source_type,
                "reliability_weight": weight,
            })

        # 7. AI synthesis
        synthesis = self._synthesize(context, sources)
        logger.info("Synthesis complete in %.1fs", time.time() - t0)

        # 8. Credibility
        credibility = compute_credibility(sources)

        # 9. Build source list for response (strip raw text)
        response_sources = []
        for s in sources[:10]:  # Top 10 for the dossier
            response_sources.append({
                "url": s["url"],
                "title": s["title"],
                "description": s.get("snippet", "")[:300],
                "source_type": s["source_type"],
                "reliability_weight": s["reliability_weight"],
            })

        # 10. Contradiction detection (skip if tight on time — API GW 29s limit)
        contradictions = []
        entity_names = _extract_entity_names(context)
        if time.time() - t0 < TIME_BUDGET_SECONDS - 8:
            contradictions = self._detect_contradictions(
                case_id, entity_names, synthesis.get("summary", "")
            )

        # 11. Timeline correlation (skip if tight on time)
        timeline = {"correlations": [], "gaps": []}
        if time.time() - t0 < TIME_BUDGET_SECONDS - 5:
            external_dates = synthesis.get("key_dates", [])
            timeline = self._correlate_timeline(case_id, entity_names, external_dates)

        # 12. Assemble Research Card
        # Include all discovered URLs (even ones we didn't fetch content from)
        all_discovered = []
        for r in unique_results[:30]:
            all_discovered.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("snippet", "")[:200],
            })

        research_card = {
            "research_id": str(uuid.uuid4()),
            "case_id": case_id,
            "research_type": research_type,
            "context_summary": ctx_summary,
            "summary": synthesis.get("summary", ""),
            "credibility": credibility,
            "sources": response_sources,
            "all_discovered_urls": all_discovered,
            "contradictions": contradictions,
            "corroborating_evidence": synthesis.get("corroborating_evidence", []),
            "contradicting_evidence": synthesis.get("contradicting_evidence", []),
            "information_gaps": synthesis.get("information_gaps", []),
            "timeline_correlations": timeline,
            "entity_names": entity_names,
            "query_count": len(queries),
            "source_count": len(sources),
            "total_urls_found": len(unique_results),
            "cached": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # 13. Cache store
        self._store_cache(key, case_id, research_type, ctx_summary, research_card)
        logger.info("OSINT research complete for %s in %.1fs", ctx_summary[:40], time.time() - t0)

        return research_card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_entity_names(context: dict) -> list:
    """Extract entity names from any context type."""
    names = []
    if context.get("entity_name"):
        names.append(context["entity_name"])
    for e in context.get("entities", []):
        if e.get("name"):
            names.append(e["name"])
    names.extend(context.get("entity_names", []))
    names.extend(context.get("connected_entities", [])[:3])
    return list(dict.fromkeys(names))  # dedupe preserving order


def _parse_date(s: str) -> Optional[datetime]:
    """Try to parse a date string in common formats."""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None
