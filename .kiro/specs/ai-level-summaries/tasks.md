# Implementation Plan: AI Level Summaries

## Overview

This plan implements AI-generated insight summaries at each level of the Pattern Library's 5-level drill-down. The implementation proceeds from data layer (Aurora table + cache manager), through service components (rate limiter, prompt builder), to the Lambda handler, API wiring, frontend panel, and finally cache invalidation integration with the indexing script. Python with pytest and Hypothesis for testing.

## Tasks

- [x] 1. Set up database schema and cache manager
  - [x] 1.1 Create Aurora migration script for `ai_level_summaries` table
    - Create `migrations/ai_level_summaries.sql` with CREATE TABLE, indexes, and CHECK constraint for taxonomy_level
    - Include UUID primary key, context_key (VARCHAR 512, UNIQUE), taxonomy_level, summary_text (TEXT), model_id, prompt_token_count, completion_token_count, generated_at, expires_at, created_at
    - Add indexes on context_key, expires_at, and taxonomy_level
    - _Requirements: 2.4_

  - [x] 1.2 Implement `SummaryCacheManager` in `src/services/summary_cache_manager.py`
    - Create class with `__init__(connection_manager, ttl_seconds=604800)`
    - Implement `get_cached(context_key)` — SELECT with expires_at comparison, return `CachedSummary` namedtuple with `is_stale` flag for expired-but-existing entries
    - Implement `store_summary(context_key, level, summary_text, model_id, prompt_tokens, completion_tokens)` — UPSERT with expires_at = now + TTL
    - Implement `invalidate_by_path(context_key)` — UPDATE expires_at = now() WHERE context_key LIKE prefix%, return count
    - Implement `invalidate_all()` — UPDATE expires_at = now() for all rows, return count
    - Use existing `ConnectionManager` for database connections
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7, 6.3, 6.4_

  - [ ]* 1.3 Write unit tests for `SummaryCacheManager`
    - Test cache hit returns summary without staleness
    - Test expired entry returns with `is_stale: true`
    - Test store_summary UPSERT correctly sets expires_at = generated_at + 7 days
    - Test `invalidate_by_path` only affects matching prefix keys
    - Test `invalidate_all` sets all entries to expired
    - Test cache write failure is handled gracefully
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7_

- [x] 2. Implement rate limiter
  - [x] 2.1 Implement `SummaryRateLimiter` in `src/services/summary_rate_limiter.py`
    - Create class with module-level counter dict and `MAX_INVOCATIONS_PER_HOUR = 60`
    - Implement `check_and_increment()` returning `(allowed: bool, remaining_or_retry_after: int)`
    - Implement `_current_hour_start()` to compute clock-hour boundary
    - Reset counter when current time crosses hour boundary
    - _Requirements: 7.1, 7.5_

  - [ ]* 2.2 Write unit tests for `SummaryRateLimiter`
    - Test counter increments correctly up to 60
    - Test 61st call returns (False, seconds_until_next_hour)
    - Test hour boundary crossing resets counter to 0
    - Test edge case at exactly :00 boundary
    - _Requirements: 7.1, 7.5_

- [x] 3. Implement prompt builder
  - [x] 3.1 Implement `SummaryPromptBuilder` in `src/services/summary_prompt_builder.py`
    - Define `SYSTEM_PROMPT` as investigative intelligence analyst persona
    - Implement `build_prompt(level, context_key, taxonomy_data)` returning dict with system, messages, max_tokens=300
    - Implement `_gather_context(level, context_key, taxonomy_data)` with level-specific extraction:
      - Domain: typology count, signature count, cross-typology highlights
      - Typology: method names, per-method signature counts, severity distribution, precedent cases
      - Method: all signature descriptions, indicator lists, precedent cases
      - Signature: vector text, all indicators, precedent case details, severity
      - Precedent Case: case name, referencing signatures, evidentiary pattern
    - Include data from current level + one level below only (no grandchildren)
    - Implement `_estimate_tokens(text)` using `len(text.split()) * 1.3`
    - Implement `_truncate_context(context, signatures, cases)` — remove signatures by ascending severity (Low→Medium→High→Critical), then oldest cases first, until ≤4000 tokens
    - User message instructs model to produce 2–5 sentence summary
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 3.2 Write property test for prompt content completeness
    - **Property 1: Level-specific prompt content completeness**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6**

  - [ ]* 3.3 Write property test for system role and sentence instruction
    - **Property 2: Prompt contains system role and sentence instruction**
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 3.4 Write property test for prompt scoping to current level plus one below
    - **Property 3: Prompt scoping to current level plus one below**
    - **Validates: Requirements 5.3**

  - [ ]* 3.5 Write property test for token-based truncation ordering
    - **Property 4: Token-based truncation ordering**
    - **Validates: Requirements 5.5, 5.6**

  - [ ]* 3.6 Write unit tests for `SummaryPromptBuilder`
    - Test specific prompt construction for each taxonomy level with known input
    - Test token estimation returns expected approximations
    - Test truncation removes low-severity signatures first
    - Test max_tokens is set to 300 in output
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Lambda handler and API wiring
  - [x] 5.1 Implement `get_summary_handler` in `src/lambdas/api/level_summary.py`
    - Parse path parameters: level (validate against 5 allowed values), context_key (validate non-empty, ≤256 chars)
    - Call `CacheManager.get_cached(context_key)` — if hit and not expired, return cached response
    - If cache miss or expired: call `RateLimiter.check_and_increment()`
      - If rate limited + stale cache ≤24h: return stale with `is_throttled: true`
      - If rate limited + no usable cache: return 429 with retry-after header
      - If under limit: call `PromptBuilder.build_prompt()`, invoke Bedrock, truncate to ≤5 sentences, store in cache, return fresh summary
    - Handle Bedrock timeout/failure → 503 GENERATION_FAILED
    - Handle empty taxonomy context → 200 with insufficient data message
    - Handle cache write failure → log error, still return summary
    - Use existing `response_helper` for consistent response formatting
    - Log Bedrock invocations with context_key, token counts, latency to CloudWatch
    - _Requirements: 1.1, 1.7, 1.8, 1.9, 2.2, 2.3, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.7, 7.1, 7.2, 7.3, 7.4_

  - [x] 5.2 Implement `invalidate_handler` in `src/lambdas/api/level_summary.py`
    - Parse optional `context_key` from request body
    - If context_key provided: call `CacheManager.invalidate_by_path(context_key)`
    - If no context_key: call `CacheManager.invalidate_all()`
    - Return 200 with `{"invalidated_count": N, "requestId": "..."}`
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [x] 5.3 Register routes in API Gateway / Lambda router configuration
    - Add GET `/pattern-library/summary/{level}/{context_key}` → `get_summary_handler`
    - Add POST `/pattern-library/summary/invalidate` → `invalidate_handler`
    - Configure Bedrock client with `read_timeout=10`, `connect_timeout=5`, `retries={"max_attempts": 1}`
    - _Requirements: 3.1, 6.3_

  - [ ]* 5.4 Write property test for output sentence truncation
    - **Property 5: Output sentence truncation**
    - **Validates: Requirements 5.7**

  - [ ]* 5.5 Write property test for cache write with correct TTL
    - **Property 6: Cache write with correct TTL**
    - **Validates: Requirements 2.1, 2.6**

  - [ ]* 5.6 Write property test for cache hit bypasses Bedrock
    - **Property 7: Cache hit bypasses Bedrock**
    - **Validates: Requirements 2.2**

  - [ ]* 5.7 Write property test for expired cache triggers regeneration
    - **Property 8: Expired cache triggers regeneration**
    - **Validates: Requirements 2.3**

  - [ ]* 5.8 Write property test for rate limiter caps invocations
    - **Property 12: Rate limiter caps Bedrock invocations at 60 per hour**
    - **Validates: Requirements 7.1**

  - [ ]* 5.9 Write property test for rate-limited with recent cache returns is_throttled
    - **Property 13: Rate-limited with recent cache returns is_throttled**
    - **Validates: Requirements 7.2**

  - [ ]* 5.10 Write property test for rate-limited without recent cache returns 429
    - **Property 14: Rate-limited without recent cache returns 429**
    - **Validates: Requirements 7.3**

  - [ ]* 5.11 Write property test for rate counter resets at clock-hour boundary
    - **Property 15: Rate counter resets at clock-hour boundary**
    - **Validates: Requirements 7.5**

  - [ ]* 5.12 Write property test for API response required fields
    - **Property 16: API response contains all required fields**
    - **Validates: Requirements 3.2**

  - [ ]* 5.13 Write unit tests for Lambda handler
    - Test valid GET returns 200 with correct JSON structure
    - Test invalid taxonomy level returns 400
    - Test unknown context_key returns 404
    - Test Bedrock failure returns 503
    - Test rate-limited returns 429 with retry-after header
    - Test cached response includes `is_cached: true`
    - Test invalidation endpoint returns correct count
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement cache invalidation integration
  - [x] 7.1 Add invalidation call to `index_pattern_library.py`
    - After successful re-seed of `typology-patterns` OpenSearch index, POST to `/pattern-library/summary/invalidate` (no context_key → invalidate all)
    - Ensure invalidation completes within 5 seconds of re-seed
    - _Requirements: 6.1_

  - [x] 7.2 Implement path-based invalidation for single-signature updates
    - When a signature is added or modified, compute the ancestor chain context_keys (parent method, parent typology, parent domain)
    - POST to `/pattern-library/summary/invalidate` with the signature's context_key prefix
    - _Requirements: 6.2_

  - [ ]* 7.3 Write property test for path-based invalidation marks ancestor chain
    - **Property 9: Path-based invalidation marks ancestor chain**
    - **Validates: Requirements 2.5, 6.2**

  - [ ]* 7.4 Write property test for stale summaries served with is_stale flag
    - **Property 10: Stale summaries served with is_stale flag**
    - **Validates: Requirements 6.4**

  - [ ]* 7.5 Write property test for invalidation endpoint returns correct count
    - **Property 11: Invalidation endpoint returns correct count**
    - **Validates: Requirements 6.3, 6.5**

- [x] 8. Implement frontend AI insight panel
  - [x] 8.1 Add AI insight panel HTML and CSS to `pattern-library.html`
    - Add `.ai-insight-panel` container with header (🤖 AI Insight label, status indicator, refresh button) and body area
    - Add loading skeleton animation CSS
    - Add expand/collapse toggle styles
    - Position panel above main content area at each drill-down level
    - _Requirements: 4.1, 4.2, 4.4_

  - [x] 8.2 Implement `fetchSummary(level, contextKey, bypassCache)` JavaScript function
    - Call GET `/pattern-library/summary/{level}/{context_key}` with optional cache bypass query param
    - Manage loading skeleton display during fetch
    - Handle error responses: show dismissible error message, preserve taxonomy content
    - _Requirements: 4.2, 4.5_

  - [x] 8.3 Implement `renderInsightPanel(response)` and UI interactions
    - Render summary text with 500-character truncation and expand/collapse toggle
    - Display "Cached", "Generated", or "Throttled" status based on response flags
    - Implement refresh button: disable on click, bypass cache, re-enable on response/error
    - Wire `fetchSummary` into existing drill-down navigation handlers so panel loads on each level change
    - _Requirements: 4.3, 4.4, 4.5, 4.6_

  - [ ]* 8.4 Write property test for frontend text truncation at 500 characters
    - **Property 17: Frontend text truncation at 500 characters**
    - **Validates: Requirements 4.3**

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases using pytest
- The project uses Python (pytest + Hypothesis) for all backend testing
- Frontend property test (8.4) can be implemented as a pure-function test on the truncation logic extracted to a helper

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.2", "3.3", "3.4", "3.5", "3.6"] },
    { "id": 2, "tasks": ["1.3", "5.1", "5.2", "5.3"] },
    { "id": 3, "tasks": ["5.4", "5.5", "5.6", "5.7", "5.8", "5.9", "5.10", "5.11", "5.12", "5.13"] },
    { "id": 4, "tasks": ["7.1", "7.2", "8.1"] },
    { "id": 5, "tasks": ["7.3", "7.4", "7.5", "8.2"] },
    { "id": 6, "tasks": ["8.3", "8.4"] }
  ]
}
```
