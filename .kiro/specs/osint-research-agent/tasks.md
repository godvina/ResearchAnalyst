# Implementation Plan: OSINT Research Agent

## Overview

Implement the OSINT Research Agent as a multi-component backend service that formulates search queries via Bedrock Claude, executes them against Brave Search API, extracts and synthesizes web content, detects contradictions against internal evidence, cross-references timelines, and returns Research Cards. Results are cached in Aurora PostgreSQL for 24 hours. The frontend gets Research Buttons on pattern cards, entity drill-down panels, and AI briefing questions, plus a Research Card renderer and Save to Case integration. All code extends existing services and UI without replacing anything.

## Tasks

- [x] 1. Database migration and WebSearchClient
  - [x] 1.1 Create Aurora migration `src/db/migrations/013_osint_research_cache.sql`
    - Create `osint_research_cache` table with fields: cache_key (VARCHAR(64) PRIMARY KEY), case_id (UUID NOT NULL), research_type (VARCHAR(20) NOT NULL), context_summary (TEXT NOT NULL), research_card (JSONB NOT NULL), created_at (TIMESTAMPTZ DEFAULT now()), updated_at (TIMESTAMPTZ DEFAULT now())
    - Create index `idx_osint_cache_case_id` on case_id
    - Create index `idx_osint_cache_updated` on updated_at
    - Wrap in BEGIN/COMMIT transaction
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 1.2 Implement `src/services/web_search_client.py` — WebSearchClient class
    - `__init__(self, api_key: str, timeout: int = 10)` storing API key and timeout
    - `search(self, query: str, count: int = 5) -> list` — GET `https://api.search.brave.com/res/v1/web/search` with `X-Subscription-Token` header, returns list of `{url, title, snippet}` dicts
    - `fetch_page(self, url: str) -> Optional[str]` — GET URL with User-Agent header, 10s timeout, returns raw HTML or None on error; skip blocked patterns (PDFs, videos, large files)
    - Define `WebSearchError` exception class for API failures
    - Use `urllib.request` only (no external HTTP libraries)
    - Use `Optional[str]` syntax for Python 3.10 compatibility
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 1.3 Write unit tests for WebSearchClient `tests/unit/test_web_search_client.py`
    - Test successful search returns list of result dicts with url, title, snippet
    - Test search API error raises WebSearchError
    - Test fetch_page returns HTML on success, None on timeout
    - Test fetch_page skips blocked URL patterns (PDF, video)
    - Mock `urllib.request.urlopen` for all tests
    - _Requirements: 3.1, 3.2, 3.3_

- [ ] 2. Checkpoint — Ensure migration and WebSearchClient tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. OsintResearchService core implementation
  - [x] 3.1 Implement `src/services/osint_research_service.py` — OsintResearchService class constructor and cache methods
    - `__init__(self, aurora_cm, bedrock_client, neptune_endpoint, neptune_port="8182", brave_api_key=None)` — store dependencies, instantiate WebSearchClient if brave_api_key provided
    - `_cache_key(self, case_id, research_type, context) -> str` — SHA-256 hash of normalized (case_id + research_type + sorted context keys/values)
    - `_check_cache(self, cache_key) -> Optional[dict]` — SELECT from osint_research_cache WHERE cache_key matches and updated_at < 24h ago, return research_card JSONB or None
    - `_store_cache(self, cache_key, case_id, research_type, context_summary, research_card)` — UPSERT into osint_research_cache with ON CONFLICT DO UPDATE
    - `get_cached_results(self, case_id, limit=50) -> list` — SELECT all cached results for case_id ordered by updated_at DESC
    - Use `Optional[dict]` syntax for Python 3.10 compatibility
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 11.5_

  - [x] 3.2 Implement query formulation and content extraction methods
    - `_formulate_queries(self, research_type, context) -> list` — call Bedrock Claude to generate 3-5 search queries from entity/pattern/question context; prompt covers different investigative angles (public records, news, regulatory filings, corporate associations)
    - `_extract_text(self, html) -> str` — HTMLParser subclass to strip `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>` blocks; collapse whitespace; truncate to 3000 chars
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.4_

  - [x] 3.3 Implement source classification and credibility assessment
    - `_classify_source(self, url, title) -> tuple` — parse domain, match against ordered rules: .gov/.mil→government(0.95), .edu/scholar.google/arxiv→academic(0.90), courtlistener/pacer/sec.gov filings→legal_filing(0.85), known news domains→news(0.80), sec.gov/opencorporates/dnb→corporate_record(0.70), social media domains→social_media(0.40), default→blog(0.30)
    - `_compute_credibility(self, sources) -> dict` — weighted average of reliability weights; rating HIGH if ≥0.75, MEDIUM if ≥0.50, LOW otherwise; return {rating, explanation, weighted_score}
    - _Requirements: 5.1, 5.2, 5.4_

  - [x] 3.4 Implement AI synthesis method
    - `_synthesize(self, context, sources) -> dict` — send extracted content + investigation context to Bedrock Claude; instruct model to produce summary (200-400 words), credibility assessment, corroborating evidence, contradicting evidence, information gaps; parse JSON response with fallback to text summary on parse error
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 3.5 Implement contradiction detection and timeline correlation
    - `_detect_contradictions(self, case_id, entity_names, external_summary) -> list` — query Aurora documents for entity mentions, query Neptune for entity relationships, send internal evidence + external summary to Bedrock Claude, parse contradiction list of {internal_claim, external_claim, internal_source, external_source}; return empty list if none found
    - `_correlate_timeline(self, case_id, entity_names, external_dates) -> dict` — query Aurora for internal date references, match external dates within 30-day window → correlations list, unmatched external dates → gaps list, sort both chronologically; return {correlations, gaps}
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4_

  - [x] 3.6 Implement main research orchestration method
    - `research(self, case_id, research_type, context, force_refresh=False) -> dict` — full pipeline: compute cache_key → check cache (unless force_refresh) → formulate queries → web search per query → deduplicate URLs → fetch+extract per URL → classify sources → synthesize → detect contradictions → correlate timeline → assemble Research Card → store cache → return
    - Graceful degradation: each component (search, extraction, synthesis, contradiction, timeline) can fail independently; Research Card always returns with fewer sections on failure
    - Time budget awareness: skip optional steps (contradictions, timeline) if approaching 25s elapsed
    - URL deduplication across all query results before content extraction
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.4, 6.1, 6.2, 7.1, 7.2, 9.1, 9.2, 9.3, 9.4, 11.2_

- [ ] 4. OsintResearchService property-based tests
  - [ ]* 4.1 Write property test for query count invariant (Property 1)
    - **Property 1: Query count invariant**
    - For any valid research context (entity, pattern, or question type) with non-empty identifying fields, `_formulate_queries` returns between 3 and 5 queries inclusive
    - Mock Bedrock to return well-formed query lists
    - Use Hypothesis strategies for research_type and context fields
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [ ]* 4.2 Write property test for HTML text extraction (Property 2)
    - **Property 2: HTML text extraction strips forbidden elements**
    - For any HTML string containing `<script>`, `<style>`, `<nav>`, `<footer>`, or `<header>` elements, `_extract_text` returns a string containing none of those tag names or their content
    - Use Hypothesis `text()` strategy to generate arbitrary HTML content within forbidden tags
    - **Validates: Requirements 3.4**

  - [ ]* 4.3 Write property test for URL deduplication (Property 3)
    - **Property 3: URL deduplication invariant**
    - For any list of search result dicts with `url` fields, after deduplication the output contains no duplicate URLs and every output URL appeared in the input
    - Use Hypothesis `lists(fixed_dictionaries({...}))` strategy
    - **Validates: Requirements 3.5**

  - [ ]* 4.4 Write property test for Research Card structure (Property 4)
    - **Property 4: Research Card structural completeness**
    - For any non-empty set of classified sources and valid synthesis response, the Research Card contains: summary string, credibility object with rating in {HIGH, MEDIUM, LOW}, and sources list with required fields
    - **Validates: Requirements 4.2**

  - [ ]* 4.5 Write property test for source classification (Property 5)
    - **Property 5: Source classification correctness**
    - For any URL string, `_classify_source` returns exactly one source_type from the valid set and the corresponding reliability_weight matches the defined mapping
    - Use Hypothesis `from_regex` and `sampled_from` strategies for URLs
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 4.6 Write property test for credibility computation (Property 6)
    - **Property 6: Credibility weighted average computation**
    - For any non-empty list of sources with known reliability weights, `_compute_credibility` returns weighted_score equal to arithmetic mean of weights, and rating matches threshold rules (HIGH ≥0.75, MEDIUM ≥0.50, LOW <0.50)
    - Use Hypothesis `lists(sampled_from(weights), min_size=1)` strategy
    - **Validates: Requirements 5.4**

  - [ ]* 4.7 Write property test for contradiction alert structure (Property 7)
    - **Property 7: Contradiction alert structure**
    - For any detected contradiction, the dict contains all four fields: internal_claim, external_claim, internal_source, external_source, each as non-empty strings
    - **Validates: Requirements 6.2**

  - [ ]* 4.8 Write property test for timeline 30-day correlation (Property 8)
    - **Property 8: Timeline 30-day correlation matching**
    - For any pair of internal/external dates, if absolute difference ≤30 days → correlations list; if no internal date within 30 days → gaps list; no date pair in both lists
    - Use Hypothesis `dates()` strategy
    - **Validates: Requirements 7.2, 7.3**

  - [ ]* 4.9 Write property test for timeline chronological ordering (Property 9)
    - **Property 9: Timeline chronological ordering**
    - For any set of timeline entries, output correlations and gaps lists are sorted in ascending chronological order
    - **Validates: Requirements 7.4**

  - [ ]* 4.10 Write property test for cache key determinism (Property 10)
    - **Property 10: Cache key determinism**
    - For any research context, computing cache key twice with same inputs produces identical SHA-256 hex strings; two different contexts produce different keys
    - Use Hypothesis `text()` and `fixed_dictionaries()` strategies
    - **Validates: Requirements 9.1**

  - [ ]* 4.11 Write property test for cache TTL behavior (Property 11)
    - **Property 11: Cache TTL behavior**
    - For any cached entry, if updated_at < 24h ago and force_refresh=False → return cached; if ≥24h old → invoke fresh research
    - Mock datetime for deterministic testing
    - **Validates: Requirements 9.2, 9.3**

  - [ ]* 4.12 Write property test for finding tags preservation (Property 12)
    - **Property 12: Finding tags preservation**
    - For any Research Card saved as finding, persisted entity_names equals Research Card entity_names, and tags include all source_type values
    - **Validates: Requirements 10.3**

  - [ ]* 4.13 Write property test for request validation (Property 13)
    - **Property 13: Request validation returns 400**
    - For any POST body missing research_type or context, handler returns HTTP 400 with descriptive validation message
    - Use Hypothesis `fixed_dictionaries` with `none()` and `just({})` strategies
    - **Validates: Requirements 11.3**

- [ ] 5. Checkpoint — Ensure OsintResearchService and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. API handler and route registration
  - [x] 6.1 Implement `src/lambdas/api/osint_handler.py` — API handler functions
    - `_build_osint_service() -> OsintResearchService` — construct service with Aurora CM, Bedrock client, Neptune endpoint, Brave API key from env/Secrets Manager
    - `research_handler(event, context) -> dict` — POST handler: extract case_id from path, parse JSON body, validate research_type and context fields (return 400 if missing/invalid), delegate to `OsintResearchService.research()`, return Research Card JSON; handle internal errors with 500 + error code
    - `list_cache_handler(event, context) -> dict` — GET handler: extract case_id from path, delegate to `get_cached_results()`, return JSON list
    - Follow existing handler patterns (see `investigator_analysis.py`, `findings.py`)
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 6.2 Register OSINT routes in `src/lambdas/api/case_files.py` dispatch_handler
    - Add routing block for `/osint-research` path before the trawler/alerts block
    - When path contains `/osint-research` and `/case-files/` in path: import `research_handler`, `list_cache_handler` from `osint_handler`; route POST to `research_handler`, GET to `list_cache_handler`
    - _Requirements: 11.1, 11.5_

  - [ ]* 6.3 Write unit tests for API handler `tests/unit/test_osint_handler.py`
    - Test POST /osint-research with valid body returns Research Card JSON
    - Test POST with missing research_type returns 400
    - Test POST with missing context returns 400
    - Test POST with invalid research_type returns 400
    - Test GET /osint-research/cache returns cached results list
    - Test internal error returns 500 with error code
    - Test force_refresh=true bypasses cache
    - Mock OsintResearchService for all tests
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 9.4_

- [ ] 7. Checkpoint — Ensure API handler and route tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Frontend Research Button, Research Card, and Entity Enrichment
  - [x] 8.1 Implement Research Button and OSINT API integration in `src/frontend/investigator.html`
    - Append self-contained HTML, CSS, and JS to end of investigator.html
    - `_renderResearchButton(context)` — renders 🔍 Research This button; appears on pattern detail cards, entity drill-down panel headers, and AI briefing investigative questions that recommend external research
    - `_triggerOsintResearch(caseId, researchType, context)` — calls POST `/case-files/{id}/osint-research` with research_type, context, and optional force_refresh; shows loading spinner during request
    - `_renderResearchCard(data, container)` — renders Research Card with: AI summary paragraph, credibility badge (HIGH=green, MEDIUM=yellow, LOW=red) with explanation, source links with colored source_type badges, contradiction alerts section (or consistency confirmation), timeline correlations and gaps section, source count and query count metadata
    - `_saveResearchToCase(caseId, researchCard)` — "Save to Case" button calls POST `/case-files/{id}/findings` with finding_type="osint_research", includes AI summary, source links, credibility, contradictions; shows confirmation on success
    - Refresh button on Research Card calls API with force_refresh=true
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.2, 5.3, 6.2, 6.3, 10.1, 10.2, 10.4_

  - [x] 8.2 Implement Entity Enrichment auto-trigger in `src/frontend/investigator.html`
    - `_renderEntityEnrichment(caseId, entityName, entityType)` — auto-triggers OSINT research with research_type="entity" when entity drill-down panel opens for PERSON or ORGANIZATION entities
    - Renders "External Intelligence" section below existing AI Investigative Questions in entity drill-down panel
    - Uses cached results (< 24h) served instantly; shows loading state for fresh lookups
    - Dark theme styling consistent with existing investigator.html (background #1a2332, borders #2d3748)
    - Use `.osint-research-*` CSS class prefix for scoping
    - Do not modify any existing HTML elements, CSS classes, or JS functions
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 10.3, 10.4_

- [ ] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- All Python code must use `Optional[type]` syntax (Python 3.10 compatible)
- All frontend code is appended to existing investigator.html — never modify existing elements
- Bedrock calls are mocked in all property and unit tests for speed and determinism
- WebSearchClient uses `urllib.request` only — no external HTTP library dependencies
