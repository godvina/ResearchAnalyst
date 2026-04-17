# Implementation Plan: Progressive Intelligence Drilldown

## Overview

Transform the static investigative questions in the entity intelligence panel into an interactive three-level progressive drill-down system. Level 1 quick answers are generated in the same Bedrock call as questions (zero latency). Level 2 analytical briefs and Level 3 intelligence reports are fetched on-demand via a new `question-answer` endpoint routed through the existing `{proxy+}` API Gateway via `case_files.py` dispatcher. A follow-up question bar allows custom questions scoped to the entity's graph neighborhood. All changes are additive — no existing code is overwritten.

## Tasks

- [x] 1. Extend Patterns API for Level 1 Quick Answers
  - [x] 1.1 Extend `_generate_entity_intelligence()` prompt in `src/lambdas/api/patterns.py`
    - Modify the Bedrock prompt's JSON schema to change `investigative_questions` from a list of strings to a list of objects with `question` and `quick_answer` fields
    - The `quick_answer` must be a single sentence of 150 characters or fewer
    - Keep the same Bedrock model ID, persona, and single invocation — no additional API calls
    - Handle Bedrock response parsing for the new object format with fallback to string format
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 1.2 Write property tests for Level 1 response structure
    - **Property 1: Level 1 response contains structured question objects**
    - **Property 2: Single Bedrock invocation for Level 1 generation**
    - **Property 3: Quick answer length constraint (≤150 chars)**
    - **Validates: Requirements 1.1, 1.2, 1.4, 5.1**

- [x] 2. Implement QuestionAnswerService
  - [x] 2.1 Create `src/services/question_answer_service.py` with `QuestionAnswerService` class
    - Constructor accepts `aurora_cm`, `bedrock_client`, `neptune_endpoint`, `neptune_port`, `opensearch_endpoint`
    - Implement `answer_question(case_id, entity_name, question, level, entity_type=None, neighbors=None)` → dict
    - Implement `_get_graph_context(case_id, entity_name)` using Neptune HTTP API (same `_neptune_query` pattern as `patterns.py`)
    - Implement `_get_document_context(case_id, entity_name, question)` using `SemanticSearchService` for Aurora pgvector retrieval
    - Implement `_generate_level2(question, entity_name, graph_ctx, doc_ctx)` — Bedrock call returning analytical brief + citations
    - Implement `_generate_level3(question, entity_name, graph_ctx, doc_ctx)` — Bedrock call returning structured intelligence report with executive_summary, evidence_analysis, source_citations, confidence_assessment, recommended_next_steps
    - Use same Bedrock model ID (`anthropic.claude-3-haiku-20240307-v1:0`) and senior investigative analyst persona as existing services
    - Graceful degradation: if Neptune fails → proceed with doc context only; if search fails → proceed with graph context only; if both fail → Bedrock with question+entity only
    - _Requirements: 2.2, 2.3, 2.4, 3.2, 3.6, 5.3, 5.4_

  - [ ]* 2.2 Write property tests for QuestionAnswerService
    - **Property 4: Level 2 response structure** — `analysis` (non-empty string) + `citations` list with `document_name` and `relevance`
    - **Property 5: Level 3 response structure** — all required sections present
    - **Property 6: Consistent Bedrock configuration** — model ID and persona match existing services
    - **Property 7: Semantic search and graph context used for all on-demand answers**
    - **Validates: Requirements 2.2, 2.3, 2.4, 3.2, 3.6, 5.4**

  - [ ]* 2.3 Write unit tests for QuestionAnswerService
    - Test Neptune timeout → continues with empty graph context
    - Test semantic search failure → continues with empty document context
    - Test both context sources fail → still produces response via Bedrock alone
    - Test Bedrock JSON parse error → graceful handling with partial response
    - Test Bedrock throttling (429) → returns AI_THROTTLED error
    - _Requirements: 2.3, 3.6_

- [x] 3. Checkpoint — Verify service layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Create Question Answer Lambda Handler and Wire Dispatcher
  - [x] 4.1 Create `src/lambdas/api/question_answer.py` handler
    - Implement `question_answer_handler(event, context)` following existing handler patterns (like `chat.py`, `drill_down.py`)
    - Extract `case_id` from `pathParameters["id"]`, parse body for `entity_name`, `question`, `level`, optional `entity_type` and `neighbors`
    - Validate: reject empty/whitespace-only `question` with 400 VALIDATION_ERROR; reject invalid `level` (not 1, 2, 3) with 400; reject missing `entity_name` with 400
    - Build `QuestionAnswerService` with dependencies from environment (same pattern as `_build_chat_service()` in `chat.py`)
    - Call `service.answer_question()` and return via `success_response()`
    - Use `@with_access_control` decorator and CORS handling consistent with other handlers
    - _Requirements: 2.1, 2.2, 4.2, 4.6, 5.2_

  - [x] 4.2 Add dispatcher route in `src/lambdas/api/case_files.py`
    - Add route for `POST /case-files/{id}/question-answer` before the catch-all case file CRUD routes
    - Pattern: `if resource == "/case-files/{id}/question-answer" or (path.endswith("/question-answer") and "/case-files/" in path):`
    - Import and call `question_answer_handler` from `lambdas.api.question_answer`
    - _Requirements: 5.2_

  - [ ]* 4.3 Write unit tests for question_answer handler
    - **Property 8: Empty question rejection** — whitespace-only strings return 400, Bedrock not called
    - Test dispatcher routing: verify `/case-files/{id}/question-answer` POST routes to correct handler
    - Test missing entity_name returns 400
    - Test invalid level returns 400
    - Test CORS headers present in response
    - **Validates: Requirements 4.6, 5.2**

- [x] 5. Checkpoint — Verify backend end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Frontend Progressive Disclosure UI
  - [x] 6.1 Add progressive question card CSS and rendering in `src/frontend/investigator.html`
    - Add CSS classes for `.question-card`, `.question-header`, `.quick-answer`, `.level2-content`, `.level3-modal`, `.follow-up-bar`
    - Implement `_renderProgressiveQuestion(questionObj, index)` — renders a question card with collapse/expand states
    - Modify `_loadAIIntelligence()` to handle new object format for `investigative_questions` (list of `{question, quick_answer}` objects)
    - Backward compatibility: if `investigative_questions` is a list of strings (legacy format), render without quick_answer and show "Click to analyze" fallback
    - Modify `_generateEntityQuestions()` to add static `quick_answer` fallback text for client-generated questions
    - _Requirements: 1.3, 1.5, 5.5, 6.1, 6.2_

  - [x] 6.2 Implement Level 2 expand and Level 3 report modal in `src/frontend/investigator.html`
    - Implement `_expandToLevel2(el, entityName, question)` — calls `POST /case-files/{id}/question-answer` with `level: 2`, renders analytical brief + citations inline
    - Implement `_openLevel3Report(entityName, question)` — calls `POST /case-files/{id}/question-answer` with `level: 3`, renders structured report in modal overlay
    - Implement `_renderLevel3Modal(data)` — modal with executive summary, evidence analysis, citations, confidence assessment, next steps
    - Show loading indicators: "Generating analytical brief..." for L2, "Generating intelligence report..." for L3
    - Show error states with "Retry" button on API failure
    - Collapse/expand toggle: clicking an expanded question collapses it back
    - _Requirements: 2.1, 2.5, 2.7, 3.1, 3.3, 3.4, 3.7, 6.2, 6.3, 6.4, 6.5_

  - [x] 6.3 Implement follow-up question bar and client-side cache in `src/frontend/investigator.html`
    - Implement `_renderFollowUpBar(entityName)` — text input below investigative questions section
    - Implement `_submitFollowUp(entityName)` — calls `/question-answer` with custom question, renders result in progressive format
    - Validate empty input client-side: show "Please enter a question" without API call
    - Retain question text in input after submission
    - Implement `_qaCache` object with `_cacheKey(entity, question, level)` — cache L2/L3 responses in memory
    - Re-expanding a previously fetched question uses cache instead of new API call
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 6.6_

  - [ ]* 6.4 Write unit tests for frontend parsing logic
    - **Property 9: Legacy format backward compatibility** — list of plain strings renders without errors
    - **Property 10: Client-side answer cache idempotence** — cached response returned without new API call
    - _Requirements: 5.5, 6.6_

- [x] 7. Final checkpoint — Verify all progressive drilldown levels work end-to-end
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- No CDK changes needed — the question-answer endpoint routes through the existing `{proxy+}` API Gateway via `case_files.py` dispatcher
- No new database tables — all answers are generated on-demand and cached client-side only
- All backend changes are additive: existing `patterns.py`, `case_files.py`, and `investigator.html` are extended, not replaced
- Property tests use `hypothesis` library with `@settings(max_examples=100)`
- Each property test references its design document property number
