# Implementation Plan: Investigative Patterns (Top 5)

## Overview

Extend the existing pattern discovery pipeline to combine multi-modal intelligence (text entities, visual labels, face matches, document co-occurrence) into ranked investigative questions. Implementation extends `pattern_discovery_service.py`, `patterns.py`, `case_files.py`, and `investigator.html` — never overwrites. All code is Python (backend) and HTML/JS (frontend).

## Tasks

- [x] 1. Add data models and scoring logic
  - [x] 1.1 Add new models to `src/models/pattern.py`
    - Add `EvidenceModality` enum (text, visual, face, cooccurrence)
    - Add `RawPattern`, `PatternQuestion`, `EvidenceBundle`, `TopPatternReport` Pydantic models
    - Keep existing `Pattern`, `PatternReport`, `CrossCaseMatch`, `CrossReferenceReport` unchanged
    - _Requirements: 1.2, 1.3, 1.4, 2.3, 4.2_

  - [x] 1.2 Implement `_score_pattern` method in `PatternDiscoveryService`
    - Add `_score_pattern(self, pattern: RawPattern) -> float` to `pattern_discovery_service.py`
    - Composite formula: `evidence_strength × cross_modal_bonus × novelty_score`
    - Cross-modal bonus: {1 modality: 0.5, 2: 0.75, 3: 0.9, 4: 1.0}
    - _Requirements: 1.2, 1.3_

  - [ ]* 1.3 Write property test: Composite score computation (Property 2)
    - **Property 2: Composite score computation**
    - Generate random evidence_strength, cross_modal_score, novelty_score floats in [0,1], verify composite_score = product
    - Test file: `tests/unit/test_top_patterns_service.py`
    - **Validates: Requirements 1.2**

  - [ ]* 1.4 Write property test: Corroboration classification (Property 9)
    - **Property 9: Corroboration classification**
    - Generate random modality lists of length 1-4, verify classification: 1=single_source, 2=moderate, 3+=strong
    - Test file: `tests/unit/test_top_patterns_service.py`
    - **Validates: Requirements 6.2, 6.3**

- [x] 2. Implement multi-modal Neptune query methods
  - [x] 2.1 Add `_query_text_entity_patterns` to `PatternDiscoveryService`
    - Query RELATED_TO edges for text entity centrality and clusters
    - Return `list[RawPattern]` with modality=TEXT
    - Use existing `_gremlin_query` and `_entity_label` helpers
    - _Requirements: 1.1_

  - [x] 2.2 Add `_query_visual_entity_patterns` to `PatternDiscoveryService`
    - Query DETECTED_IN edges for visual label co-occurrence patterns
    - Use `VisualEntity_{case_id}` label
    - Return `list[RawPattern]` with modality=VISUAL
    - _Requirements: 1.1_

  - [x] 2.3 Add `_query_face_match_patterns` to `PatternDiscoveryService`
    - Query HAS_FACE_MATCH edges for person-face connections
    - Use `FaceCrop_{case_id}` label
    - Return `list[RawPattern]` with modality=FACE
    - _Requirements: 1.1_

  - [x] 2.4 Add `_query_cooccurrence_patterns` to `PatternDiscoveryService`
    - Query CO_OCCURS_WITH edges for cross-document entity co-occurrence
    - Return `list[RawPattern]` with modality=COOCCURRENCE
    - _Requirements: 1.1_

  - [ ]* 2.5 Write unit tests for Neptune query methods
    - Mock `_gremlin_query` to return sample graph data for each modality
    - Test each query method returns correctly typed RawPatterns
    - Test empty graph returns empty list
    - Test file: `tests/unit/test_top_patterns_service.py`
    - _Requirements: 1.1_

- [x] 3. Implement `discover_top_patterns` orchestrator
  - [x] 3.1 Add `discover_top_patterns(self, case_id: str) -> TopPatternReport` to `PatternDiscoveryService`
    - Call all four `_query_*` methods, merge results
    - Score each pattern with `_score_pattern`, sort descending
    - Take top 5 (or fewer with explanation)
    - Call `_synthesize_questions` for AI question generation
    - Return `TopPatternReport` with patterns indexed 1-5
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 3.2 Write property test: Ranking order invariant (Property 3)
    - **Property 3: Ranking order invariant**
    - Generate random lists of PatternQuestions with random composite scores, verify descending order and correct index assignment
    - Test file: `tests/unit/test_top_patterns_service.py`
    - **Validates: Requirements 1.3, 1.4**

  - [ ]* 3.3 Write property test: Output size constraint (Property 4)
    - **Property 4: Output size constraint**
    - Generate random numbers of discoverable patterns (0-20), verify output size is min(5, N) and explanation set when N < 5
    - Test file: `tests/unit/test_top_patterns_service.py`
    - **Validates: Requirements 1.4, 1.5**

- [x] 4. Implement Bedrock synthesis and fallback
  - [x] 4.1 Add `_synthesize_questions` method to `PatternDiscoveryService`
    - Call Bedrock Claude with multi-modal evidence context (entity names, types, visual labels, face match identities, co-occurring documents, relationship types)
    - Return `list[PatternQuestion]` with question text, confidence (0-100), modalities, and 2-3 sentence summary
    - On Bedrock failure, generate fallback using template: "Investigate the connection between [Entity A] and [Entity B] found in [N] documents with [modalities] evidence."
    - Set fallback confidence to 50
    - If Neptune queries exceed 15s total, skip Bedrock and use fallback templates for all 5
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 4.2 Write property test: PatternQuestion structural completeness (Property 5)
    - **Property 5: PatternQuestion structural completeness**
    - Generate random PatternQuestions, verify question non-empty, confidence in [0,100], modalities non-empty
    - Test file: `tests/unit/test_top_patterns_service.py`
    - **Validates: Requirements 2.1, 2.3**

  - [ ]* 4.3 Write property test: Fallback question on Bedrock failure (Property 7)
    - **Property 7: Fallback question on Bedrock failure**
    - Generate random RawPatterns, simulate Bedrock failure, verify fallback question matches template format
    - Test file: `tests/unit/test_top_patterns_service.py`
    - **Validates: Requirements 2.4**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement evidence bundle retrieval
  - [x] 6.1 Add `get_evidence_bundle` method to `PatternDiscoveryService`
    - Fetch document excerpts from Aurora with document IDs and filenames
    - Generate presigned S3 URLs for supporting images
    - Generate presigned S3 URLs for face crop thumbnails with matched entity names
    - Query Neptune for entity connection paths
    - Return `EvidenceBundle` with documents, images, face_crops, entity_paths, cooccurring_labels
    - _Requirements: 4.1, 4.2_

  - [ ]* 6.2 Write unit tests for `get_evidence_bundle`
    - Mock Aurora, S3, and Neptune responses
    - Verify presigned URLs generated for images and face crops
    - Verify document excerpts truncated to 200 characters
    - Test file: `tests/unit/test_top_patterns_service.py`
    - _Requirements: 4.2_

- [x] 7. Add Aurora cache layer
  - [x] 7.1 Create `top_pattern_cache` table migration
    - Add SQL migration file `src/db/migrations/008_top_pattern_cache.sql`
    - CREATE TABLE with case_file_id (UUID PK), cached_at (TIMESTAMPTZ), top_patterns (JSONB)
    - _Requirements: 7.3_

  - [x] 7.2 Add cache check/write logic to `discover_top_patterns`
    - Before querying Neptune, check Aurora cache for results < 15 minutes old
    - On cache hit, return cached TopPatternReport without Neptune/Bedrock calls
    - On cache miss or stale, regenerate and upsert into cache
    - On cache write failure, log error and return results without caching
    - _Requirements: 7.3, 7.4_

- [x] 8. Add API endpoints
  - [x] 8.1 Add `top_patterns_handler` to `src/lambdas/api/patterns.py`
    - Handle `GET /case-files/{id}/top-patterns` — return Top 5 PatternQuestions with summaries
    - Handle `GET /case-files/{id}/top-patterns/{pattern_index}/evidence` — return EvidenceBundle for pattern N (1-5)
    - Validate pattern_index is 1-5, return 400 if invalid
    - Complete within 25s budget (4s safety margin before API Gateway 29s timeout)
    - _Requirements: 7.1, 7.2, 7.5_

  - [x] 8.2 Add routing for new endpoints in `src/lambdas/api/case_files.py`
    - Add path matching for `/top-patterns` routes before existing `/patterns` catch-all
    - Extract `pattern_index` path parameter for evidence endpoint
    - Dispatch to `top_patterns_handler` in patterns.py
    - _Requirements: 7.1, 7.2_

  - [ ]* 8.3 Write unit tests for API handlers
    - Test GET top-patterns returns 200 with Top 5 structure
    - Test GET evidence returns 200 with EvidenceBundle structure
    - Test invalid pattern_index returns 400
    - Test case not found returns 404
    - Test routing in case_files.py dispatches correctly
    - Test file: `tests/unit/test_top_patterns_service.py`
    - _Requirements: 7.1, 7.2_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement frontend Top 5 Patterns panel
  - [x] 10.1 Add Top 5 Patterns section to `src/frontend/investigator.html`
    - Add CSS styles for patterns panel, modality icons, confidence badges, corroboration badges
    - Add HTML section above entity graph with numbered pattern list
    - Each pattern shows: question text, confidence badge (0-100%), modality icons (📄 text, 📷 visual, 👤 face, 🔗 co-occurrence)
    - "Strong Corroboration" badge (green) when 3+ modalities, "Single Source" indicator when 1 modality
    - _Requirements: 5.1, 6.1, 6.2, 6.3, 8.1_

  - [x] 10.2 Implement progressive disclosure interaction
    - Three states per pattern: collapsed → summary → detail
    - First click: expand inline summary panel (AI explanation, doc count, image count, modalities, confidence) — no API call, use data from initial fetch
    - Second click: expand to detail view, call `/top-patterns/{idx}/evidence` API
    - Third click: collapse back to initial state
    - Slide-down animation for state transitions
    - Only one pattern in detail state at a time — expanding new detail collapses previous
    - Loading indicator "Gathering evidence..." if evidence API takes > 10s
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 5.1, 5.2, 5.3, 5.4, 5.5, 4.6_

  - [x] 10.3 Implement detail view with evidence display
    - Source documents as clickable cards: filename, excerpt (200 chars), download link using existing download flow
    - Image thumbnail gallery with visual labels overlaid
    - Face crop thumbnails with matched entity name below each
    - Clickable entity names that scroll to and highlight entity in existing entity graph
    - _Requirements: 4.3, 4.4, 4.5, 8.3, 8.4_

  - [x] 10.4 Wire auto-fetch on case selection
    - When a case is selected in the sidebar, automatically call `GET /case-files/{id}/top-patterns`
    - Render the Top 5 patterns panel with results
    - Handle empty results gracefully (show "No patterns discovered yet" message)
    - _Requirements: 8.2_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using `hypothesis` library
- Unit tests validate specific examples and edge cases
- All backend changes EXTEND existing files — never overwrite
- Frontend changes add new sections to existing `investigator.html`
