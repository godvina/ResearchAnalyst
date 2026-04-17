# Implementation Plan: Unified Research Hub

## Overview

Consolidates four investigative capabilities — embedded chatbot, compare mode, narrative pattern intelligence, and conversational external research — into a single Research Hub tab within `investigator.html`. Backend-first approach: new service + migration + API handler, then pattern narrative upgrade, then frontend panels, then integration wiring.

## Tasks

- [x] 1. Backend: ConversationalResearchService + Aurora migration + API handler
  - [x] 1.1 Create Aurora migration `src/db/migrations/014_research_conversations.sql`
    - Create `research_conversations` table with columns: `conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `case_id UUID NOT NULL`, `subject_name VARCHAR(500) NOT NULL`, `subject_type VARCHAR(100) DEFAULT 'person'`, `messages JSONB NOT NULL DEFAULT '[]'`, `research_context JSONB DEFAULT '{}'`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
    - Create index `idx_research_conv_case` on `case_id`
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 1.2 Implement `src/services/conversational_research_service.py`
    - Create `ConversationalResearchService` class with `__init__(self, aurora_cm, bedrock_client, research_agent: AIResearchAgent)`
    - Implement `start_conversation(case_id, subject)` — calls `AIResearchAgent.research_subject()` for initial OSINT report, creates conversation record in Aurora, returns `{response, conversation_id, sources, suggested_followups}`
    - Implement `continue_conversation(case_id, conversation_id, message)` — loads conversation history from Aurora, detects intent (refine search / drill deeper / general), builds prompt with last 10 messages as context, invokes Bedrock Haiku, appends to Aurora, returns response dict
    - Implement intent detection: `refine|search for|look up` → new Brave query via AIResearchAgent; `drill deeper|more about|expand on` → focused deep-dive; default → contextual Bedrock response
    - Use Bedrock Haiku for speed (29s API Gateway budget)
    - Reuse existing `AIResearchAgent` — do NOT rebuild
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 6.2, 6.3, 6.6_

  - [ ]* 1.3 Write property tests for ConversationalResearchService
    - [ ]* 1.3.1 Property test: Property 9 — Conversation context window bound
      - **Property 9: Conversation context window bound**
      - Generate conversations with random lengths (1–50 messages), verify Bedrock invocation includes exactly the last 10 messages when N > 10
      - **Validates: Requirements 4.6**
    - [ ]* 1.3.2 Property test: Property 10 — Follow-up context inclusion
      - **Property 10: Follow-up context inclusion**
      - For any follow-up message in an active conversation, verify the Bedrock prompt includes content from the prior research report (first message) and the follow-up query text
      - **Validates: Requirements 4.4, 4.5**
    - [ ]* 1.3.3 Property test: Property 11 — Research conversation intent detection
      - **Property 11: Research conversation intent detection**
      - Generate random messages with/without intent keywords ("refine", "search for", "look up", "drill deeper", "more about"), verify correct action is triggered
      - **Validates: Requirements 4.7, 4.8**
    - [ ]* 1.3.4 Property test: Property 13 — New conversation initialization
      - **Property 13: New conversation initialization**
      - Generate random subjects with name and type, verify response contains a newly generated UUID conversation_id and non-empty response text
      - **Validates: Requirements 6.2**

  - [x] 1.4 Implement `src/lambdas/api/research_chat.py`
    - Create `research_chat_handler(event, context)` for `POST /case-files/{id}/research/chat`
    - Parse request body: `message` (required string), `conversation_id` (optional UUID), `subject` (required object with `name` and `type`)
    - Route to `ConversationalResearchService.start_conversation` when no `conversation_id`, or `continue_conversation` when present
    - Return JSON: `{response, conversation_id, sources, suggested_followups}`
    - Return 400 for missing `message` or `subject`, 404 for invalid `conversation_id`, 500 with `error_code: "RESEARCH_FAILED"` on Bedrock/agent failure
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 1.5 Write property test for research chat API response schema
    - **Property 12: Research chat API response schema**
    - Generate random valid requests (non-empty message, valid subject), verify response contains all four fields: `response` (string), `conversation_id` (UUID string), `sources` (array), `suggested_followups` (array)
    - **Validates: Requirements 6.1, 6.4**

  - [x] 1.6 Wire research chat route into `src/lambdas/api/case_files.py`
    - Add routing rule: if `"/research/chat" in path and "/case-files/" in path and method == "POST"`, import and call `research_chat_handler`
    - Place BEFORE the existing `/chat` catch-all route to avoid conflicts
    - _Requirements: 6.1_

  - [ ]* 1.7 Write unit tests for ConversationalResearchService and research_chat handler
    - Create `tests/unit/test_conversational_research_service.py` — test `start_conversation` and `continue_conversation` with mocked Aurora and Bedrock; verify conversation record creation, context loading, intent detection, response assembly
    - Create `tests/unit/test_research_chat_handler.py` — test request validation (missing message, missing subject, invalid conversation_id), successful routing, error response formatting
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 2. Checkpoint — Backend core
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Backend: PatternDiscoveryService narrative upgrade
  - [x] 3.1 Upgrade `_synthesize_questions` in `src/services/pattern_discovery_service.py`
    - Replace the existing Bedrock prompt in `_synthesize_questions` with the narrative-focused prompt from the design using the `LeadGeneratorService.INVESTIGATOR_PERSONA` style ("senior federal investigative analyst with 20+ years of experience")
    - Prompt must request both an investigative `question` and a `narrative` explanation (3-5 sentences) for each pattern
    - Prompt must instruct Bedrock to cite specific entity names, document counts, and relationship types
    - Prompt must instruct Bedrock to include a low-evidence caveat when `composite_score < 0.3`
    - Prompt must reference all modalities present in each pattern
    - Parse response to add `narrative` field to each pattern dict alongside existing `question`, `confidence`, `summary`, `modalities`, `entities`
    - Keep `_generate_fallback_questions` unchanged — frontend handles missing `narrative` gracefully
    - Do NOT modify scoring, merging, caching, or any other method
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 3.2 Write property tests for narrative synthesis
    - [ ]* 3.2.1 Property test: Property 6 — Narrative synthesis output structure
      - **Property 6: Narrative synthesis output structure**
      - Generate random pattern lists, verify each returned element contains non-empty `narrative` and `question` fields, and that `narrative` references at least one entity name from the pattern's `entities` list
      - **Validates: Requirements 3.1, 3.2, 3.6**
    - [ ]* 3.2.2 Property test: Property 7 — Multi-modal evidence in synthesis prompt
      - **Property 7: Multi-modal evidence in synthesis prompt**
      - For any pattern with K distinct modalities, verify the Bedrock synthesis prompt contains string references to all K modality types
      - **Validates: Requirements 3.4**
    - [ ]* 3.2.3 Property test: Property 8 — Low-score caveat inclusion
      - **Property 8: Low-score caveat inclusion**
      - Generate patterns with random composite_scores, verify that patterns with score < 0.3 produce a narrative or prompt containing a low-evidence caveat
      - **Validates: Requirements 3.5**

  - [ ]* 3.3 Update existing pattern tests in `tests/unit/test_pattern_discovery_service.py`
    - Add test cases verifying `_synthesize_questions` returns dicts with `narrative` field
    - Verify fallback questions still work when Bedrock fails (no `narrative` field expected)
    - _Requirements: 3.1_

- [x] 4. Checkpoint — Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Frontend: Research Hub tab shell + sub-panel switching
  - [x] 5.1 Add Research Hub tab to `src/frontend/investigator.html`
    - Add `<div class="tab" onclick="switchTab('researchhub')">🔬 Research Hub</div>` to the `.tabs` bar
    - Add `'researchhub'` to the `allTabs` array in `switchTab()`
    - Create `<div id="tab-researchhub" class="tab-content">` with sub-navigation buttons for Chat, Compare, Patterns, External Research
    - Create four sub-panel divs: `rh-chat`, `rh-compare`, `rh-patterns`, `rh-research`
    - Implement `switchResearchPanel(panel)` function to toggle sub-panel visibility
    - Preserve sub-panel state (don't re-fetch on sub-tab switch)
    - Lazy-load: defer data fetches until Research Hub tab is activated
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [x] 5.2 Implement empty state and case binding
    - Show empty state prompting case selection when no case is selected
    - Bind all sub-panels to `selectedCaseId` global variable
    - _Requirements: 5.4, 5.5_

- [x] 6. Frontend: Embedded chatbot slide-out panel
  - [x] 6.1 Wire chatbot panel in `src/frontend/investigator.html`
    - The CSS classes `.chatbot-toggle`, `.chatbot-panel`, `.chat-messages`, `.chat-input-row` already exist in investigator.html styles
    - Add the chatbot toggle button (fixed bottom-right, 56px circle) and the 400px slide-out panel HTML
    - Implement `toggleChatbot()` to add/remove `.open` class on `.chatbot-panel`
    - Auto-bind to `selectedCaseId` for all `POST /case-files/{id}/chat` calls
    - Maintain `chatbotConversationId` across messages for multi-turn history
    - Render AI responses with clickable `[Source N]` citation links from `citations` array
    - Render `suggested_actions` as clickable buttons that populate input and send
    - Add "Share Finding" button calling `POST /case-files/{id}/chat/share`
    - Add command hint bar: "summarize case", "who is [name]", "connections between A and B", "timeline", "what's missing", "draft subpoena list"
    - Ensure Investigator View remains fully interactive behind the panel
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

  - [ ]* 6.2 Write property tests for chatbot rendering
    - [ ]* 6.2.1 Property test: Property 1 — Chat API case binding
      - **Property 1: Chat API case binding**
      - For any selected case ID and non-empty message, verify the API call URL contains the case ID and body contains the message
      - **Validates: Requirements 1.3, 1.4**
    - [ ]* 6.2.2 Property test: Property 2 — Citation link rendering
      - **Property 2: Citation link rendering**
      - For any response with N `[Source K]` references, verify exactly N citation link elements are rendered with correct document names
      - **Validates: Requirements 1.5**
    - [ ]* 6.2.3 Property test: Property 3 — Suggested action button rendering
      - **Property 3: Suggested action button rendering**
      - For any response with `suggested_actions` array of length N, verify exactly N buttons are rendered with matching text
      - **Validates: Requirements 1.7**

- [x] 7. Frontend: Compare View
  - [x] 7.1 Implement Compare View in `rh-compare` sub-panel
    - Add search input + "Compare" button
    - Call `POST /case-files/{id}/investigative-search` with `search_scope: "internal_external"`
    - Render split-pane layout: "What We Have" (left) / "What's Public" (right)
    - Color-code findings from `cross_reference_report`: green `.xref-confirmed` for `confirmed_internally`, orange `.xref-external` for `external_only`, red `.xref-needs-research` for `needs_research`
    - Display `confidence_level` as summary badge (strong_case / needs_more_evidence / insufficient)
    - Display `executive_summary` banner at top
    - Add "Research Internally" button on `external_only` items
    - Add "Start Research" button on `needs_research` items → opens Research Conversation
    - Internal evidence excerpts clickable → open Evidence Library tab
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

  - [ ]* 7.2 Write property tests for Compare View
    - [ ]* 7.2.1 Property test: Property 4 — Cross-reference category color mapping
      - **Property 4: Cross-reference category color mapping**
      - Generate random findings with random categories, verify correct CSS class: `xref-confirmed` for `confirmed_internally`, `xref-external` for `external_only`, `xref-needs-research` for `needs_research`
      - **Validates: Requirements 2.3, 2.4, 2.5, 2.6**
    - [ ]* 7.2.2 Property test: Property 5 — Compare mode search scope
      - **Property 5: Compare mode search scope**
      - For any search query in Compare Mode, verify the API call includes `search_scope: "internal_external"` in the request body
      - **Validates: Requirements 2.2**

- [x] 8. Frontend: Narrative Pattern Cards
  - [x] 8.1 Implement pattern cards in `rh-patterns` sub-panel
    - Call `POST /case-files/{id}/top-patterns` on sub-panel activation
    - Render each pattern as a narrative card with: investigative question (headline), narrative explanation (body), confidence indicator (progress bar), supporting entities (tags), modality badges (text/visual/face/co-occurrence)
    - Handle missing `narrative` field gracefully (show only `question` and `summary`)
    - Click on card → open entity drill-down for primary entity
    - Show "No patterns discovered yet" empty state when no patterns returned
    - _Requirements: 3.7, 3.8_

- [x] 9. Frontend: Research Conversation panel
  - [x] 9.1 Implement Research Conversation in `rh-research` sub-panel
    - Add subject selector (entity name + type from case entities)
    - Add "Quick OSINT Report" button → calls existing `POST /case-files/{id}/osint-research`
    - Add "Start Research Conversation" button → calls `POST /case-files/{id}/research/chat` without `conversation_id`
    - Display initial OSINT report as first AI message
    - Add follow-up input field for multi-turn conversation
    - Send follow-ups to `POST /case-files/{id}/research/chat` with `conversation_id`
    - Add "Save to Case" button on each AI message → calls `POST /case-files/{id}/chat/share`
    - Display error message with retry button on Bedrock failures
    - Maintain full conversation history in UI
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.9, 4.10_

- [x] 10. Checkpoint — Frontend panels complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Integration: CSS styles, state management, case change reset
  - [x] 11.1 Add CSS styles for Research Hub components
    - Add styles for: `.rh-sub-nav`, `.rh-sub-btn`, `.rh-panel`, `.xref-confirmed`, `.xref-external`, `.xref-needs-research`, `.pattern-narrative-card`, `.research-chat-msg`, `.confidence-badge`, `.modality-badge`
    - Add split-pane layout styles for Compare View
    - Add pattern card styles with confidence progress bar
    - Add research conversation chat styles
    - _Requirements: 2.3, 3.7_

  - [x] 11.2 Implement case change reset
    - When `selectedCaseId` changes in the sidebar, reset all Research Hub sub-panel states: clear active conversations, search results, pattern views, chatbot conversation
    - Subsequent data fetches use the newly selected case ID
    - Reset chatbot panel conversation state as well
    - _Requirements: 5.5_

  - [ ]* 11.3 Write property test for case change reset
    - **Property 14: Sub-panel state reset on case change**
    - For any case selection change, verify all Research Hub sub-panel states are cleared and subsequent fetches use the new case ID
    - **Validates: Requirements 5.5**

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 14 correctness properties from the design document
- Existing services (ChatService, InvestigativeSearchService, AIResearchAgent, PatternDiscoveryService) are reused — not rebuilt
- Migration number is 014 (next available after 013_osint_research_cache.sql)
