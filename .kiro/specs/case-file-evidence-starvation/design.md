# Case File Evidence Starvation Bugfix Design

## Overview

The `generate_case_file()` method in `theory_engine_service.py` produces sparse, low-quality case files because it fetches only 15 documents via a blind recency query (`ORDER BY indexed_at DESC LIMIT 15`) with 150-char snippets, then attempts to generate all 13 sections in a single Bedrock call with `max_tokens=4096`. This starves the LLM of relevant evidence and exhausts the token budget before reaching the legal analysis section (section 12), which is consistently empty.

The fix introduces three changes that extend the existing code path:
1. Replace the blind evidence query with a pgvector KNN cosine similarity search using the existing `SemanticSearchService._generate_embedding()` and Aurora `embedding` column
2. Split generation into two Bedrock passes — sections 1–11 (Pass 1, `max_tokens=6144`) and section 12 legal analysis (Pass 2, legal-focused KNN query, `max_tokens=4096`)
3. Apply a confidence penalty of 5 points per gap detected by `_detect_section_gaps()`

All changes extend existing methods; no existing code is replaced.

## Glossary

- **Bug_Condition (C)**: The condition that triggers evidence starvation — `generate_case_file()` fetches documents via `ORDER BY indexed_at DESC LIMIT 15` with `LEFT(raw_text, 150)`, yielding irrelevant evidence and a single token-starved Bedrock call
- **Property (P)**: The desired behavior — KNN-retrieved semantically relevant evidence feeds a two-pass Bedrock generation that produces populated sections including legal analysis
- **Preservation**: Existing fallback behavior, persisted case file loading, entity enrichment, competing theory inclusion, and section editing must remain unchanged
- **generate_case_file()**: The method in `src/services/theory_engine_service.py` that orchestrates case file generation (steps 1–10)
- **_build_case_file_prompt()**: Builds the Bedrock prompt from theory, evidence, entities, and competing theories
- **_detect_section_gaps()**: Marks sections with insufficient content as gaps (evidence_for, evidence_against, timeline, key_entities, legal_analysis)
- **AuroraPgvectorBackend**: Existing backend in `src/services/aurora_pgvector_backend.py` that performs cosine similarity search via pgvector
- **SemanticSearchService._generate_embedding()**: Existing method that generates Titan Embed vectors via `amazon.titan-embed-text-v1`
- **KNN**: K-Nearest Neighbors — pgvector cosine similarity search using `<=>` operator
- **Pass 1**: Bedrock call generating sections 1–11 with `max_tokens=6144`
- **Pass 2**: Bedrock call generating section 12 (legal analysis) with `max_tokens=4096` using a legal-focused KNN query

## Bug Details

### Bug Condition

The bug manifests when `generate_case_file()` is called for any case. The evidence retrieval query (`ORDER BY indexed_at DESC LIMIT 15`) returns the 15 most recently indexed documents regardless of relevance to the theory. Only 10 of these are passed to the prompt at 150 chars each, providing ~1,500 chars of evidence context. The single Bedrock call with `max_tokens=4096` must generate all 13 sections, causing token exhaustion before reaching the complex legal analysis section.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {case_id: str, theory_id: str}
  OUTPUT: boolean

  theory := fetchTheory(input.theory_id, input.case_id)
  evidence := fetchEvidence(input.case_id)

  RETURN evidence.query == "ORDER BY indexed_at DESC LIMIT 15"
         AND evidence.text_length <= 150
         AND evidence.passed_to_prompt <= 10
         AND bedrock.max_tokens == 4096
         AND bedrock.call_count == 1
END FUNCTION
```

### Examples

- **Epstein Main (345,898 docs)**: Theory "Financial Network Analysis" gets 15 most recent docs (random OCR pages) instead of financially relevant documents. Legal analysis section is empty. Evidence For section has generic citations unrelated to financial networks.
- **Epstein Main (77,900 entities)**: Theory with 3 supporting_entities gets only those 3 resolved, missing 40+ co-occurring entities in relevant documents that would enrich the case file.
- **Ancient Aliens (240 docs)**: Theory "Pyramid Construction Technology" gets 15 most recent docs. With only 240 docs the recency bias is less severe, but the 150-char snippets still starve the prompt of meaningful evidence context.
- **Edge case — empty embeddings**: A case where documents lack the `embedding` column populated should fall back to `ORDER BY indexed_at DESC LIMIT 30` with `LEFT(raw_text, 300)`.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Bedrock failure fallback via `_build_fallback_case_file()` must continue to return a partial case file
- Persisted case files in `theory_case_files` table must continue to load instantly without re-generation
- Competing theories (up to 5) must continue to be fetched and included in the prompt
- Entity enrichment after Bedrock response parsing must continue to merge Aurora entity data into key_entities
- Section editing and Regenerate Case File button must continue to function
- `AuroraPgvectorBackend` and `SemanticSearchService` used by other features (document search, pattern discovery, Q&A) must be unaffected
- Small cases (fewer than 30 docs) must continue to generate case files without error

**Scope:**
All inputs that do NOT involve the evidence retrieval or Bedrock generation steps should be completely unaffected by this fix. This includes:
- Case file loading from `theory_case_files` table (already persisted)
- Theory CRUD operations
- Entity resolution via `_resolve_entities()`
- Frontend rendering of case file sections
- Other Lambda endpoints and API routes

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Blind Recency Query**: `generate_case_file()` step 2 uses `ORDER BY indexed_at DESC LIMIT 15` which returns the 15 most recently indexed documents regardless of semantic relevance to the theory. For a case with 345,898 documents, this is effectively random selection.

2. **Insufficient Evidence Context**: Only 10 of the 15 fetched documents are passed to the prompt (`evidence[:10]`), each truncated to 150 chars (`str(e.get('text', ''))[:150]`). This yields ~1,500 chars of evidence — far too little for a 13-section analytical case file.

3. **Single-Call Token Exhaustion**: A single Bedrock call with `max_tokens=4096` must generate all 13 sections. The legal analysis section (section 12) is the most complex, requiring statutes, element readiness, sentencing advisory, alternative charges, and charging recommendation. By the time Bedrock reaches section 12, the token budget is exhausted.

4. **No Confidence Penalty**: `_detect_section_gaps()` correctly identifies empty/sparse sections but the `confidence_level.overall_score` is taken directly from the Bedrock response (or theory score) with no penalty applied for detected gaps. A case file with 5 empty sections reports the same confidence as one with all sections populated.

5. **Sparse Entity Context**: Entity resolution is limited to the theory's `supporting_entities` list, which may contain only 2–5 names. Documents retrieved via KNN would reveal additional co-occurring entities that could enrich the case file.

## Correctness Properties

Property 1: Bug Condition - KNN Evidence Retrieval and Two-Pass Generation

_For any_ input where `generate_case_file(case_id, theory_id)` is called on a case with documents that have embeddings, the fixed function SHALL embed the theory title + description via Titan Embed, perform a pgvector KNN cosine similarity search (`ORDER BY embedding <=> theory_vector LIMIT 30`) with `LEFT(raw_text, 300)`, and use the retrieved evidence in a two-pass Bedrock generation (Pass 1: sections 1–11 with `max_tokens=6144`, Pass 2: section 12 with legal-focused KNN query and `max_tokens=4096`).

**Validates: Requirements 2.1, 2.3, 2.5**

Property 2: Preservation - Non-Evidence-Retrieval Behavior

_For any_ input where `generate_case_file()` encounters a Bedrock failure, or where a persisted case file already exists, or where competing theories are fetched, or where entity enrichment is performed, the fixed function SHALL produce the same result as the original function, preserving fallback behavior, cached loading, competing theory inclusion, and entity merging.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.7**

Property 3: Bug Condition - Confidence Penalty for Section Gaps

_For any_ input where `_detect_section_gaps()` identifies N gaps (N > 0), the fixed function SHALL reduce `confidence_level.overall_score` by `5 * N` points compared to the raw Bedrock-returned score.

**Validates: Requirements 2.4**

Property 4: Bug Condition - Entity Enrichment from KNN Results

_For any_ input where KNN-retrieved documents contain co-occurring entities, the fixed function SHALL extract up to 40 entities from those documents and supplement the theory's `supporting_entities` list before entity resolution.

**Validates: Requirements 2.2**

Property 5: Preservation - Embedding Fallback for Un-embedded Documents

_For any_ input where the case's documents lack embeddings (embedding column is NULL), the fixed function SHALL fall back to `ORDER BY indexed_at DESC LIMIT 30` with `LEFT(raw_text, 300)`, ensuring small cases and un-embedded documents still generate case files.

**Validates: Requirements 2.6, 3.3**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/services/theory_engine_service.py`

**1. New method `_fetch_knn_evidence()`**:
- Accept `case_id`, `theory_title`, `theory_description`
- Embed `f"{theory_title} {theory_description}"` using `SemanticSearchService._generate_embedding()` (reuse existing Bedrock Runtime client)
- Execute: `SELECT source_filename, LEFT(raw_text, 300), document_id FROM documents WHERE case_file_id = %s ORDER BY embedding <=> %s::vector LIMIT 30`
- Count documents with non-NULL embeddings first; if zero, fall back to `ORDER BY indexed_at DESC LIMIT 30` with `LEFT(raw_text, 300)`
- Return list of `{filename, text, document_id}`

**2. New method `_fetch_knn_entities()`**:
- Accept `case_id` and list of `document_id` values from KNN results
- Query: `SELECT DISTINCT e.canonical_name, e.entity_type, e.occurrence_count FROM entities e JOIN document_entities de ON e.entity_id = de.entity_id WHERE de.document_id = ANY(%s) AND e.case_file_id = %s ORDER BY e.occurrence_count DESC LIMIT 40`
- If `document_entities` table doesn't exist or query fails, fall back to empty list (graceful degradation)
- Return list of entity names to supplement `supporting_entities`

**3. New method `_build_legal_prompt()`**:
- Accept `theory`, `legal_evidence` (from legal-focused KNN), `entities`, `sections_1_to_11` (for context)
- Embed `f"{theory_title} {theory_description} legal implications statutes criminal charges"` for legal-focused KNN query
- Fetch 30 legal-relevant documents via same KNN pattern
- Build a focused prompt requesting only the `legal_analysis` JSON section
- Include theory context and sections 1–11 summary for coherence

**4. Modify `generate_case_file()` step 2**:
- Replace blind `ORDER BY indexed_at DESC LIMIT 15` with call to `_fetch_knn_evidence()`
- Pass all 30 KNN results (not sliced to 10) to prompt builder

**5. Modify `generate_case_file()` step 3**:
- After `_resolve_entities()`, call `_fetch_knn_entities()` with KNN document IDs
- Merge KNN entity names into `entity_names` list (deduplicated)
- Re-resolve the combined entity list

**6. Modify `_build_case_file_prompt()`**:
- Increase evidence slice from `evidence[:10]` to `evidence[:30]`
- Increase text truncation from `[:150]` to `[:300]`
- Increase entity slice from `entities[:20]` to `entities[:40]`
- Update prompt to request sections 1–11 only (remove section 12 from schema)

**7. Modify `generate_case_file()` step 5**:
- Change `max_tokens=4096` to `max_tokens=6144` for Pass 1
- After parsing Pass 1 response, call `_build_legal_prompt()` and `_invoke_bedrock()` with `max_tokens=4096` for Pass 2
- Merge Pass 2 `legal_analysis` into sections dict

**8. Modify `_detect_section_gaps()` return path in `generate_case_file()`**:
- After `_detect_section_gaps()`, count sections where `is_gap == True`
- Reduce `sections["confidence_level"]["overall_score"]` by `5 * gap_count`
- Clamp to minimum of 0

**9. Constructor dependency**:
- Add optional `bedrock_client` parameter to `TheoryEngineService.__init__()` for Titan Embed access
- Reuse the same Bedrock Runtime client already available in the Lambda handler

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that call `generate_case_file()` with mocked database and Bedrock responses, verifying the evidence query, prompt construction, and section completeness. Run these tests on the UNFIXED code to observe failures.

**Test Cases**:
1. **Evidence Relevance Test**: Mock a case with 100 documents, call `generate_case_file()`, verify the SQL query uses `ORDER BY indexed_at DESC LIMIT 15` (will confirm blind query on unfixed code)
2. **Token Exhaustion Test**: Mock Bedrock to return a response where legal_analysis is empty/truncated when `max_tokens=4096` (will confirm token starvation on unfixed code)
3. **Entity Sparsity Test**: Mock a theory with 2 supporting_entities, verify only 2 entities are resolved (will confirm sparse entity context on unfixed code)
4. **Confidence Score Test**: Mock `_detect_section_gaps()` returning 3 gaps, verify `confidence_level.overall_score` is unchanged (will confirm no penalty on unfixed code)

**Expected Counterexamples**:
- Evidence query returns recency-ordered documents with no relevance to theory
- Legal analysis section is empty or has `is_gap: true`
- Confidence score does not reflect section gaps
- Possible causes: blind recency query, single-call token exhaustion, no confidence penalty

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := generate_case_file_fixed(input.case_id, input.theory_id)
  ASSERT result.evidence_query USES "ORDER BY embedding <=> vector LIMIT 30"
  ASSERT result.evidence_text_length == 300
  ASSERT result.bedrock_calls == 2
  ASSERT result.legal_analysis IS NOT EMPTY
  ASSERT result.confidence_level.overall_score == raw_score - (5 * gap_count)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT generate_case_file_original(input) = generate_case_file_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for Bedrock failures, persisted case file loads, and entity enrichment, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Fallback Preservation**: Verify that when Bedrock raises an exception, `_build_fallback_case_file()` is still called and returns the same structure
2. **Persisted Load Preservation**: Verify that already-persisted case files load from `theory_case_files` without triggering re-generation
3. **Competing Theory Preservation**: Verify that up to 5 competing theories are still fetched and included
4. **Entity Enrichment Preservation**: Verify that Aurora entity data is still merged into key_entities after Bedrock response parsing
5. **Small Case Preservation**: Verify that a case with fewer than 30 docs (and no embeddings) falls back to recency query and generates successfully

### Unit Tests

- Test `_fetch_knn_evidence()` with mocked DB: verify KNN query, fallback to recency when no embeddings
- Test `_fetch_knn_entities()` with mocked DB: verify entity extraction from KNN document IDs
- Test `_build_legal_prompt()`: verify legal-focused prompt structure and KNN query text
- Test confidence penalty: verify `overall_score` reduced by `5 * gap_count`, clamped to 0
- Test `_build_case_file_prompt()` with 30 evidence items at 300 chars and 40 entities

### Property-Based Tests

- Generate random theory titles/descriptions and verify `_fetch_knn_evidence()` always returns ≤30 documents with text ≤300 chars
- Generate random gap counts (0–13) and verify confidence penalty is correctly applied and clamped
- Generate random entity lists and verify deduplication between theory supporting_entities and KNN entities
- Generate random case sizes (0–1000 docs) and verify fallback logic triggers correctly when embeddings are absent

### Integration Tests

- Test full `generate_case_file()` flow with mocked Bedrock returning valid JSON for both passes
- Test that Pass 1 + Pass 2 combined output contains all 13 sections
- Test that both Bedrock calls + two Titan Embed calls complete within simulated Lambda timeout constraints
- Test end-to-end with a small embedded dataset to verify KNN retrieval produces more relevant evidence than recency ordering
