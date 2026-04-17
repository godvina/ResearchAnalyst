# Implementation Plan

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Evidence Starvation and Single-Pass Token Exhaustion
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate evidence starvation, token exhaustion, and missing confidence penalty
  - **Scoped PBT Approach**: Scope the property to concrete failing cases:
    - Mock `generate_case_file()` with a case containing 100+ documents with embeddings
    - Assert evidence query uses `ORDER BY embedding <=> vector LIMIT 30` (will fail — unfixed uses `ORDER BY indexed_at DESC LIMIT 15`)
    - Assert evidence text length is 300 chars per doc (will fail — unfixed uses 150)
    - Assert Bedrock is called twice (Pass 1 sections 1–11, Pass 2 section 12) (will fail — unfixed calls once)
    - Assert `max_tokens >= 6144` for Pass 1 (will fail — unfixed uses 4096)
    - Assert `legal_analysis` section is populated (will fail — unfixed returns empty)
    - Assert `confidence_level.overall_score` is reduced by `5 * gap_count` when gaps detected (will fail — unfixed applies no penalty)
  - Test file: `tests/test_evidence_starvation_bug.py`
  - Mock DB to return documents with embeddings, mock Bedrock to return valid JSON
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (proves the bug exists — blind recency query, single Bedrock call, no confidence penalty)
  - Document counterexamples: evidence query is recency-based, legal_analysis is empty, confidence unpenalized
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.5, 1.6, 1.7, 1.8, 2.5, 2.7, 2.8_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Fallback, Cached Load, Entity Enrichment, Competing Theories
  - **IMPORTANT**: Follow observation-first methodology
  - Observe on UNFIXED code:
    - `_build_fallback_case_file()` returns a partial case file when Bedrock raises an exception
    - Persisted case files load from `theory_case_files` table without re-generation
    - Up to 5 competing theories are fetched and included in the prompt
    - Aurora entity data is merged into `key_entities` after Bedrock response parsing
    - Cases with fewer than 30 docs generate case files without error
  - Write property-based tests capturing observed behavior:
    - For all Bedrock failure inputs, `_build_fallback_case_file()` is called and returns valid structure
    - For all persisted case file inputs, no Bedrock call is made
    - For all inputs with competing theories, up to 5 are included in prompt
    - For all inputs with entity data, Aurora entities are merged into key_entities section
    - For all small cases (< 30 docs, no embeddings), recency fallback generates a valid case file
  - Test file: `tests/test_evidence_starvation_preservation.py`
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7, 3.8_

- [x] 3. PRIORITY 1: Fix Stale Case Statistics (Quick Win)

  - [x] 3.1 Add `refresh_case_stats` action to Lambda handler
    - Add new action `refresh_case_stats` in the Lambda handler's action router
    - Run `COUNT(*)` on `documents`, `entities`, and `relationships` tables for the given `case_id`
    - UPDATE `case_files SET document_count=%, entity_count=%, relationship_count=%` WHERE `case_id=%`
    - Return the refreshed counts as JSON response
    - Expose as API endpoint so frontend can call `POST /cases/{case_id}/refresh-stats`
    - _Bug_Condition: case_files table has stale counts after Neptune-to-Aurora sync_
    - _Expected_Behavior: COUNT(*) queries update case_files with accurate counts_
    - _Preservation: Existing _get_case_stats() corrective logic remains unchanged_
    - _Requirements: 1.1, 1.2, 2.1, 2.2_

  - [x] 3.2 Call `refresh_case_stats` from `sync_neptune_to_aurora.py` after sync completes
    - At the end of the sync script, invoke the new `refresh_case_stats` action (direct DB call or Lambda invoke)
    - Ensure counts are persisted so sidebar displays correct values immediately after sync
    - _Requirements: 2.1_

  - [x] 3.3 Verify stale stats fix — sidebar shows correct counts after sync
    - Confirm `case_files` table has updated `document_count`, `entity_count`, `relationship_count`
    - Confirm sidebar and case header display accurate counts (e.g., "345,898 docs · 77,900 entities")
    - _Requirements: 2.1, 2.2_

- [x] 4. PRIORITY 2: Fix Stuck AI Intelligence Briefing (Recovery)

  - [x] 4.1 Add 15-minute expiry check to `get_analysis_status()`
    - In `src/services/investigator_ai_engine.py`, modify `get_analysis_status()`
    - When `status="processing"`, check `updated_at` (or `created_at`) timestamp
    - If row is older than 15 minutes, DELETE the stale cache row and return `None` (allows retry)
    - _Bug_Condition: investigator_analysis_cache has status="processing" with no expiry_
    - _Expected_Behavior: Stale processing rows older than 15 min are auto-expired_
    - _Preservation: Completed and error statuses are unaffected_
    - _Requirements: 1.3, 1.4, 2.3, 2.4_

  - [x] 4.2 Clear stuck cache for Epstein Main case
    - Delete the stuck `status="processing"` row for case_id `7f05e8d5-4492-4f19-8894-25367606db96`
    - Can be done via direct SQL or by triggering the expiry logic from 4.1
    - _Requirements: 2.3_

  - [x] 4.3 Add LIMIT/sampling to pattern_discovery and hypothesis_generation queries
    - In `analyze_case()` flow, add `LIMIT 5000` or random sampling to queries that scan all 345K docs
    - Specifically target `pattern_discovery` and `hypothesis_generation` steps that may cause Lambda timeout
    - Ensure async Lambda completes within 900s timeout for large cases
    - _Requirements: 1.3, 2.4, 3.6_

- [-] 5. PRIORITY 3: KNN Evidence Retrieval (Main Fix)

  - [x] 5.1 Add `_fetch_knn_evidence()` method to `TheoryEngineService`
    - File: `src/services/theory_engine_service.py`
    - Accept `case_id`, `theory_title`, `theory_description`
    - Embed `f"{theory_title} {theory_description}"` using Bedrock Titan Embed (`amazon.titan-embed-text-v1`)
    - Execute: `SELECT source_filename, LEFT(raw_text, 300), document_id FROM documents WHERE case_file_id = %s ORDER BY embedding <=> %s::vector LIMIT 30`
    - First check `SELECT COUNT(*) FROM documents WHERE case_file_id = %s AND embedding IS NOT NULL`
    - If zero embeddings, fall back to `ORDER BY indexed_at DESC LIMIT 30` with `LEFT(raw_text, 300)`
    - Return list of `{filename, text, document_id}`
    - _Bug_Condition: isBugCondition — evidence.query == "ORDER BY indexed_at DESC LIMIT 15"_
    - _Expected_Behavior: KNN cosine similarity search retrieves 30 most relevant docs_
    - _Requirements: 1.5, 2.5, 2.10_

  - [x] 5.2 Add `_fetch_knn_entities()` method to `TheoryEngineService`
    - File: `src/services/theory_engine_service.py`
    - Accept `case_id` and list of `document_id` values from KNN results
    - Query: `SELECT DISTINCT e.canonical_name, e.entity_type, e.occurrence_count FROM entities e JOIN document_entities de ON e.entity_id = de.entity_id WHERE de.document_id = ANY(%s) AND e.case_file_id = %s ORDER BY e.occurrence_count DESC LIMIT 40`
    - If `document_entities` table doesn't exist or query fails, return empty list (graceful degradation)
    - Return list of entity names to supplement `supporting_entities`
    - _Requirements: 1.6, 2.6_

  - [x] 5.3 Add `_build_legal_prompt()` method to `TheoryEngineService`
    - File: `src/services/theory_engine_service.py`
    - Accept `theory`, `legal_evidence`, `entities`, `sections_1_to_11`
    - Embed `f"{theory_title} {theory_description} legal implications statutes criminal charges"` for legal-focused KNN
    - Fetch 30 legal-relevant documents via same KNN pattern as `_fetch_knn_evidence()`
    - Build focused prompt requesting ONLY the `legal_analysis` JSON section
    - Include theory context and sections 1–11 summary for coherence
    - _Requirements: 2.7, 2.9_

  - [x] 5.4 Modify `generate_case_file()` to use KNN evidence
    - File: `src/services/theory_engine_service.py`
    - Replace step 2 (blind recency query) with call to `_fetch_knn_evidence(case_id, theory["title"], theory["description"])`
    - After `_resolve_entities()` in step 3, call `_fetch_knn_entities()` with KNN document IDs
    - Merge KNN entity names into `entity_names` list (deduplicated), re-resolve combined list
    - All changes EXTEND existing code — do not remove the original query (keep as fallback path)
    - _Bug_Condition: evidence.query == "ORDER BY indexed_at DESC LIMIT 15" AND evidence.passed_to_prompt <= 10_
    - _Expected_Behavior: KNN retrieves 30 relevant docs, 40 entities supplement supporting_entities_
    - _Requirements: 1.5, 1.6, 2.5, 2.6_

  - [x] 5.5 Modify `_build_case_file_prompt()` to accept expanded evidence
    - File: `src/services/theory_engine_service.py`
    - Change evidence slice from `evidence[:10]` to `evidence[:30]`
    - Change text truncation from `[:150]` to `[:300]`
    - Change entity slice from `entities[:20]` to `entities[:40]`
    - Update prompt to request sections 1–11 only (remove section 12 legal_analysis from JSON schema)
    - _Requirements: 2.5, 2.6, 2.7_

  - [x] 5.6 Implement two-pass Bedrock generation in `generate_case_file()`
    - File: `src/services/theory_engine_service.py`
    - Change Pass 1 `max_tokens=4096` to `max_tokens=6144` for sections 1–11
    - After parsing Pass 1 response, call `_build_legal_prompt()` for legal-focused KNN evidence
    - Invoke Bedrock Pass 2 with `max_tokens=4096` for section 12 (legal analysis)
    - Merge Pass 2 `legal_analysis` into sections dict
    - On Pass 2 failure, set `legal_analysis` to gap placeholder (don't fail entire case file)
    - _Bug_Condition: bedrock.max_tokens == 4096 AND bedrock.call_count == 1_
    - _Expected_Behavior: Two Bedrock calls — Pass 1 (6144 tokens, sections 1–11), Pass 2 (4096 tokens, section 12)_
    - _Requirements: 1.7, 1.9, 2.7, 2.9_

  - [x] 5.7 Add constructor dependency for Bedrock Titan Embed client
    - File: `src/services/theory_engine_service.py`
    - Add optional `bedrock_client` parameter to `TheoryEngineService.__init__()`
    - Reuse the same Bedrock Runtime client already available in the Lambda handler
    - _Requirements: 2.5_

  - [ ] 5.8 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - KNN Evidence Retrieval and Two-Pass Generation
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 encodes the expected behavior (KNN query, two-pass Bedrock, confidence penalty)
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.5, 2.7, 2.8_

  - [ ] 5.9 Verify preservation tests still pass
    - **Property 2: Preservation** - Fallback, Cached Load, Entity Enrichment, Competing Theories
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm fallback, cached load, entity enrichment, competing theories all unchanged
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. PRIORITY 4: Confidence Penalty for Section Gaps

  - [x] 6.1 Modify `_detect_section_gaps()` return path to apply confidence penalty
    - File: `src/services/theory_engine_service.py`
    - After `_detect_section_gaps()` in `generate_case_file()`, count sections where `is_gap == True`
    - Reduce `sections["confidence_level"]["overall_score"]` by `5 * gap_count`
    - Clamp to minimum of 0
    - _Bug_Condition: confidence_level.overall_score is unaffected by detected gaps_
    - _Expected_Behavior: overall_score reduced by 5 per gap, clamped to 0_
    - _Requirements: 1.8, 2.8_

- [-] 7. PRIORITY 5: Deploy and Verify

  - [x] 7.1 Clean `__pycache__` and deploy Lambda
    - Run: `Get-ChildItem -Path src -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force`
    - Run: `Get-ChildItem -Path src -Recurse -Filter "*.pyc" | Remove-Item -Force`
    - Build zip: `Compress-Archive -Path src\* -DestinationPath deploy-clean.zip -Force`
    - Upload and update Lambda function code
    - Publish new Lambda version to force cold starts
    - _Requirements: 3.6_

  - [ ] 7.2 Test on Epstein Main case
    - Generate a case file for a theory on Epstein Main (`7f05e8d5-4492-4f19-8894-25367606db96`)
    - Verify evidence is KNN-retrieved (relevant to theory, not random recency docs)
    - Verify legal analysis section (section 12) is populated with statutes, element readiness, sentencing advisory
    - Verify confidence score reflects any section gaps
    - Verify sidebar shows correct doc/entity/relationship counts
    - Verify AI Intelligence Briefing is no longer stuck (can trigger fresh analysis)
    - _Requirements: 2.5, 2.7, 2.8, 2.9_

  - [ ] 7.3 Update `docs/lessons-learned.md` and `docs/session-context-transfer.md`
    - Document the evidence starvation bug and fix in lessons-learned.md
    - Update session-context-transfer.md with current state (bug resolved, KNN evidence active)
    - Note: all changes extended existing code, no replacements

- [ ] 8. Checkpoint — Ensure all tests pass
  - Run full test suite: `pytest tests/test_evidence_starvation_bug.py tests/test_evidence_starvation_preservation.py -v`
  - Ensure all property-based tests pass after fix
  - Ensure all preservation tests still pass after fix
  - Ask the user if questions arise
