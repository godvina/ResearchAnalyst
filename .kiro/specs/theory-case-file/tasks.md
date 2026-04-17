# Implementation Plan: Theory Case File

## Overview

Extend the existing Theory-Driven Investigation Engine with AI-generated 12-section case files. Backend: Aurora migration 017 for `theory_case_files` table + `promoted_sub_case_id` column, TheoryEngineService extensions (generate, get-or-generate, update section, regenerate, promote, entity resolution, gap detection, fallback), 4 new API routes in theory_handler.py dispatch table. Frontend: 12-section layout in Theory Deep Dive with section renderers, inline editing, regeneration, and promote-to-sub-case button. All changes EXTEND existing code — nothing is replaced.

## Tasks

- [x] 1. Aurora database migration 017 for theory case files
  - [x] 1.1 Create `src/db/migrations/017_theory_case_files.sql`
    - Create `theory_case_files` table with columns: `case_file_content_id` (UUID PK DEFAULT gen_random_uuid()), `theory_id` (UUID NOT NULL FK to theories ON DELETE CASCADE), `case_file_id` (UUID NOT NULL FK to case_files ON DELETE CASCADE), `content` (JSONB NOT NULL DEFAULT '{}'), `generated_at` (TIMESTAMPTZ NOT NULL DEFAULT NOW()), `last_edited_at` (TIMESTAMPTZ nullable), `version` (INTEGER NOT NULL DEFAULT 1)
    - Add UNIQUE constraint on `theory_id`
    - Create index `idx_tcf_theory` on `theory_id`
    - Create index `idx_tcf_case` on `case_file_id`
    - ALTER TABLE theories ADD COLUMN IF NOT EXISTS `promoted_sub_case_id` UUID REFERENCES case_files(case_id)
    - _Requirements: 3.1, 3.2, 3.5, 11.4_

- [x] 2. Implement TheoryEngineService case file extensions
  - [x] 2.1 Add section constants and internal helpers to `src/services/theory_engine_service.py`
    - Add `SECTION_NAMES` list (12 section keys) and `SECTION_DISPLAY_NAMES` list as class constants
    - Implement `_ensure_case_file_table()` — idempotent CREATE TABLE IF NOT EXISTS for theory_case_files
    - Implement `_resolve_entities(case_id, entity_names)` — case-insensitive ILIKE query against entities table, returns list of {canonical_name, entity_type, occurrence_count}
    - Implement `_build_case_file_prompt(theory, evidence, entities, competing)` — structured prompt requesting all 12 sections as JSON, includes theory title/description/type/ACH scores, up to 20 evidence summaries (200 chars each), up to 30 entities, up to 5 competing theories
    - Implement `_parse_case_file_response(response_text)` — parse Bedrock JSON, validate 12-section structure, add `is_gap` boolean to each section
    - Implement `_detect_section_gaps(sections)` — mark `is_gap=true` when: evidence_for has zero citations, evidence_against has zero citations, timeline has <2 events, key_entities has zero entities
    - Implement `_build_fallback_case_file(theory, entities)` — populate sections 0,1,2,6 from Aurora data with `is_gap=false`, mark remaining 8 sections with `is_gap=true`
    - _Requirements: 1.2, 1.5, 2.1, 5.1, 5.2, 6.1, 6.2, 6.3, 6.5_

  - [ ]* 2.2 Write property test: 12-section structural invariant (Property 1)
    - **Property 1: Case File 12-Section Structural Invariant**
    - Generate random theory dicts, mock Bedrock returning valid 12-section JSON, verify output has exactly 12 keys matching SECTION_NAMES and each has `is_gap` boolean
    - **Validates: Requirements 2.1**

  - [ ]* 2.3 Write property test: section content field validation (Property 2)
    - **Property 2: Section Content Field Validation**
    - Generate random case file content dicts using composite strategy, verify each section contains its required fields per the design spec
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13**

  - [ ]* 2.4 Write property test: prompt contains all required context (Property 3)
    - **Property 3: Prompt Contains All Required Context**
    - Generate random theory dicts with non-empty fields, evidence lists, entity lists; call `_build_case_file_prompt()` and assert string containment of title, description, type, ACH scores, evidence, entities
    - **Validates: Requirements 1.2**

  - [ ]* 2.5 Write property test: section gap detection (Property 4)
    - **Property 4: Section Gap Detection**
    - Generate random case file content with varying citation/event/entity counts; verify `_detect_section_gaps()` sets `is_gap=true` per threshold rules
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 2.6 Write property test: entity resolution subset (Property 7)
    - **Property 7: Entity Resolution Subset with Case-Insensitive Matching**
    - Generate random entity name sets (known + unknown) with case transforms; mock entities table; verify result is subset of known set and matching is case-insensitive
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.5**

  - [ ]* 2.7 Write property test: fallback case file structure (Property 12)
    - **Property 12: Fallback Case File on Bedrock Failure**
    - Generate random theory dicts, call `_build_fallback_case_file()`, verify sections 0,1,2,6 have `is_gap=false` and remaining 8 have `is_gap=true`
    - **Validates: Requirements 1.5**

  - [x] 2.8 Implement `generate_case_file(case_id, theory_id)` method
    - Fetch theory record from theories table
    - Fetch evidence (documents, findings) from Aurora
    - Resolve entities via `_resolve_entities()`
    - Fetch competing theories for the same case
    - Build prompt via `_build_case_file_prompt()`, invoke Bedrock with max_tokens=4096
    - Parse response via `_parse_case_file_response()`
    - Enrich Key Entities section with Aurora entity data
    - Detect section gaps via `_detect_section_gaps()`
    - On Bedrock failure: return `_build_fallback_case_file()` result
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 2.1 through 2.13_

  - [x] 2.9 Implement `get_or_generate_case_file(case_id, theory_id)` method
    - Query theory_case_files for existing content by theory_id
    - If found, return persisted content with metadata
    - If not found, call `generate_case_file()`, INSERT into theory_case_files, return content
    - _Requirements: 1.1, 1.4, 3.3, 3.4_

  - [x] 2.10 Implement `update_section(case_id, theory_id, section_index, content)` method
    - Validate section_index is 0-11 (raise ValueError otherwise)
    - Use PostgreSQL `jsonb_set()` to update only the target section key
    - Update `last_edited_at = NOW()` and `version = version + 1`
    - Return updated case file content
    - _Requirements: 4.2, 4.3, 4.4, 7.3, 7.4, 7.6_

  - [x] 2.11 Implement `regenerate_case_file(case_id, theory_id)` method
    - Fetch existing case file to extract section 9 (investigator_assessment) notes
    - Call `generate_case_file()` for fresh content
    - Merge preserved investigator notes into section 9
    - UPDATE existing theory_case_files record with new content, update `generated_at`, increment `version`
    - _Requirements: 7.7, 8.1, 8.2, 8.3, 8.4_

  - [x] 2.12 Implement `promote_to_sub_case(case_id, theory_id)` method
    - Fetch theory, verify verdict == 'confirmed' (raise ValueError if not)
    - Verify promoted_sub_case_id is NULL (raise ValueError with 409 semantics if already promoted)
    - Call `CaseFileService.create_sub_case_file()` with parent_case_id, theory title, description, supporting_entities
    - UPDATE theories SET promoted_sub_case_id = new sub_case_id
    - Return {sub_case_id, theory_id}
    - _Requirements: 11.1, 11.3, 11.4, 11.6, 11.7_

  - [x] 2.13 Enhance existing `get_theory_detail()` to include case file status
    - After fetching theory, query theory_case_files for existing content
    - If found: set `case_file_status = "available"` and include `case_file` object with sections, generated_at, last_edited_at, version
    - If not found: set `case_file_status = "not_generated"`
    - _Requirements: 10.1, 10.2, 10.3_

- [ ] 3. Checkpoint — Verify service layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement API handler extensions
  - [x] 4.1 Add `get_case_file_handler` to `src/lambdas/api/theory_handler.py`
    - Extract case_id and theory_id from pathParameters
    - Call `svc.get_or_generate_case_file(case_id, theory_id)`
    - Return 200 with case_file content or 404 if theory not found
    - _Requirements: 7.1, 7.2_

  - [x] 4.2 Add `update_section_handler` to `src/lambdas/api/theory_handler.py`
    - Extract case_id, theory_id, section_index from pathParameters
    - Parse JSON body for content
    - Call `svc.update_section(case_id, theory_id, int(section_index), content)`
    - Return 200 with updated case_file, 400 for invalid index/body, 404 if not found
    - _Requirements: 7.3, 7.4, 7.5, 7.6_

  - [x] 4.3 Add `regenerate_case_file_handler` to `src/lambdas/api/theory_handler.py`
    - Extract case_id and theory_id from pathParameters
    - Call `svc.regenerate_case_file(case_id, theory_id)`
    - Return 200 with new case_file content, 404 if not found, 500 on Bedrock failure
    - _Requirements: 7.7, 8.1, 8.2_

  - [x] 4.4 Add `promote_theory_handler` to `src/lambdas/api/theory_handler.py`
    - Extract case_id and theory_id from pathParameters
    - Call `svc.promote_to_sub_case(case_id, theory_id)`
    - Return 200 with {sub_case_id, theory_id}, 400 if not confirmed, 409 if already promoted, 404 if not found
    - _Requirements: 11.3, 11.7_

  - [x] 4.5 Add 4 new routes to `dispatch_handler` routes dict
    - `("GET", "/case-files/{id}/theories/{theory_id}/case-file")`: get_case_file_handler
    - `("PUT", "/case-files/{id}/theories/{theory_id}/case-file/sections/{section_index}")`: update_section_handler
    - `("POST", "/case-files/{id}/theories/{theory_id}/case-file/regenerate")`: regenerate_case_file_handler
    - `("POST", "/case-files/{id}/theories/{theory_id}/promote")`: promote_theory_handler
    - _Requirements: 7.1, 7.3, 7.7, 11.7_

  - [x] 4.6 Add routing entries in `src/lambdas/api/case_files.py` if needed
    - Ensure the 4 new resource paths are routed to theory_handler.dispatch_handler
    - _Requirements: 7.1_

- [ ] 5. Checkpoint and remaining property tests — Verify API layer
  - Ensure all tests pass, ask the user if questions arise.
  - Clean __pycache__ before Lambda deploy.
  - Verify API endpoints work before telling user to test UI.

  - [ ]* 5.1 Write property test: section update preserves unmodified sections (Property 5)
    - **Property 5: Section Update Preserves Unmodified Sections**
    - Generate random 12-section content, random section index 0-11, random new content; mock DB; verify 11 unchanged sections are byte-identical
    - **Validates: Requirements 4.4**

  - [ ]* 5.2 Write property test: version increment on mutation (Property 6)
    - **Property 6: Version Increment on Mutation**
    - Generate random initial version, call update/regenerate, verify version = initial + 1 and timestamp updated
    - **Validates: Requirements 4.3, 8.4**

  - [ ]* 5.3 Write property test: regeneration preserves investigator notes (Property 8)
    - **Property 8: Regeneration Preserves Investigator Assessment Notes**
    - Generate random notes text, mock existing case file with notes, regenerate, verify notes preserved in section 9
    - **Validates: Requirements 8.3**

  - [ ]* 5.4 Write property test: invalid section index rejection (Property 9)
    - **Property 9: Invalid Section Index Rejection**
    - Generate random integers outside 0-11, verify update_section raises ValueError or handler returns 400
    - **Validates: Requirements 7.6**

  - [ ]* 5.5 Write property test: timeline chronological ordering (Property 10)
    - **Property 10: Timeline Chronological Ordering**
    - Generate random date lists, build timeline events, verify ascending chronological order after processing
    - **Validates: Requirements 2.9**

  - [ ]* 5.6 Write property test: promote requires confirmed verdict (Property 11)
    - **Property 11: Promote Requires Confirmed Verdict**
    - Generate random verdicts from [None, "refuted", "inconclusive"], verify promote raises error and does not create sub-case
    - **Validates: Requirements 11.6**

- [x] 6. Implement frontend 12-section layout
  - [x] 6.1 Enhance `openTheoryDeepDive()` in `src/frontend/investigator.html`
    - When theory detail response includes `case_file_status: "available"`, call `renderCaseFile(theory, caseFile)` instead of current raw OCR rendering
    - When `case_file_status: "not_generated"`, call GET case-file endpoint to trigger generation, show skeleton loader while waiting
    - _Requirements: 1.1, 9.1, 9.8, 10.1, 10.2, 10.3_

  - [x] 6.2 Implement `renderCaseFile(theory, caseFile)` and section dispatcher
    - Render all 12 sections in vertical scrollable layout with section headers and dividers
    - Each section: header with display name + edit button + gap indicator
    - Dispatch to section-specific renderer based on index
    - _Requirements: 9.1_

  - [x] 6.3 Implement section-specific renderers
    - `renderACHScorecard(section)` — reuse existing `_renderRadarChart()` + numeric labels per dimension
    - `renderEvidenceFor(section)` — expandable citation cards: source, excerpt, relevance bar, entity badges
    - `renderEvidenceAgainst(section)` — red-tinted left border (#fc8181), contradiction explanation
    - `renderKeyEntities(section)` — clickable entity badges → existing DrillDown, entity_type icon + occurrence_count
    - `renderTimeline(section)` — horizontal SVG timeline with color-coded markers (green=supporting, red=contradicting)
    - `renderRecommendedActions(section)` — action cards: type icon, target description, priority badge
    - `renderSectionGap(sectionName, theory)` — muted placeholder + Research Further button triggering Intelligence Search
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 5.3, 5.4_

  - [x] 6.4 Implement section editing UI
    - `openSectionEditor(theoryId, sectionIndex, currentContent)` — inline textarea replacing section content
    - `saveSectionEdit(theoryId, sectionIndex)` — PUT to section update endpoint, re-render section on success
    - Investigator Assessment section: structured form with verdict selector + free-text notes field
    - _Requirements: 4.1, 4.2, 4.5_

  - [x] 6.5 Implement regeneration UI
    - `regenerateCaseFile(theoryId)` — confirmation dialog ("Your notes in Investigator Assessment will be preserved. Continue?") → POST regenerate → re-render all sections
    - _Requirements: 8.1, 8.5_

  - [x] 6.6 Implement promote-to-sub-case UI
    - `renderPromoteButton(theory)` — only visible when verdict === 'confirmed' && !promoted_sub_case_id
    - Show "View Sub-Case" link when already promoted
    - `promoteToSubCase(theoryId)` — confirmation dialog with theory title, entity count, warning text → POST promote → show sub-case link
    - _Requirements: 11.1, 11.2, 11.5, 11.6_

- [ ] 7. Checkpoint — Verify full stack
  - Ensure all tests pass, ask the user if questions arise.
  - Clean __pycache__ before Lambda deploy.
  - Verify API endpoint works before telling user to test UI.

- [x] 8. Deploy and verify
  - [x] 8.1 Run Aurora migration 017 against the database
    - Execute `017_theory_case_files.sql` to create table and add column
    - Verify table exists and column added with `\d theory_case_files` and `\d theories`
    - _Requirements: 3.1, 3.2, 3.5_

  - [x] 8.2 Deploy Lambda with updated code
    - Clean __pycache__ directories before packaging
    - Deploy Lambda with updated theory_engine_service.py, theory_handler.py, case_files.py
    - Verify all 4 new API endpoints respond (not 404) before telling user to test UI
    - _Requirements: 7.1, 7.3, 7.7, 11.7_

  - [x] 8.3 Deploy updated frontend
    - Upload updated investigator.html to S3
    - Invalidate CloudFront cache if applicable
    - _Requirements: 9.1_

- [ ] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All changes EXTEND existing code — nothing is replaced
- Always clean __pycache__ before Lambda deploy
- Always verify API endpoints work before telling user to test UI
- Property tests use Python `hypothesis` library, targeting `tests/test_theory_case_file_properties.py`
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
