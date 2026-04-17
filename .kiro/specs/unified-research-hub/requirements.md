# Requirements Document

## Introduction

The Unified Research Hub consolidates four investigative capabilities — embedded chatbot, internal-vs-external compare mode, narrative-driven pattern intelligence, and conversational external research — into a single "Research Hub" tab within the investigator view (investigator.html). The goal is to eliminate context-switching between separate pages and transform fire-and-forget tools into interactive, conversational workflows that help investigators build cases faster.

## Glossary

- **Research_Hub**: The new tab in the investigator view that hosts the embedded chatbot, compare mode, narrative patterns, and conversational research panels.
- **Investigator_View**: The main case investigation interface (investigator.html) containing the tab system, case sidebar, and case header.
- **Chatbot_Panel**: A slide-out panel embedded within the Investigator_View that provides conversational access to the ChatService for case-specific Q&A.
- **ChatService**: The existing backend service (chat_service.py) that provides RAG-based Q&A over OpenSearch documents and Neptune graph data with multi-turn conversation, intent classification, and citation extraction.
- **Compare_View**: A split-pane UI within the Research_Hub that displays internal evidence alongside external research findings with color-coded categorization.
- **InvestigativeSearchService**: The existing backend service (investigative_search_service.py) that orchestrates investigative search across document, graph, and external research sources, including the cross-reference report generator.
- **Cross_Reference_Report**: The output of InvestigativeSearchService._generate_cross_reference_report that categorizes findings as confirmed_internally, external_only, or needs_research.
- **Pattern_Narrative_Engine**: The upgraded component of PatternDiscoveryService that uses Bedrock Claude to synthesize investigative narratives explaining why a pattern matters, modeled after LeadGeneratorService narrative generation.
- **PatternDiscoveryService**: The existing backend service (pattern_discovery_service.py) that discovers multi-modal patterns via Neptune graph traversal and Aurora pgvector similarity.
- **LeadGeneratorService**: The existing backend service (lead_generator_service.py) that generates narrative-driven investigation leads for entity drilldown, used as the model for pattern narrative upgrades.
- **Research_Conversation**: A multi-turn chat session between the investigator and the AIResearchAgent for iterative external research refinement.
- **AIResearchAgent**: The existing backend service (ai_research_agent.py) that generates OSINT research documents per subject using Bedrock Claude and Brave Search API.
- **OSINT_Quick_Action**: The existing one-click button that triggers AIResearchAgent to generate a research report without follow-up interaction.
- **Brave_Search_API**: The external web search API used by AIResearchAgent for public information retrieval (not OpenSearch).
- **Bedrock_Claude**: Amazon Bedrock Claude models (Haiku for speed, Sonnet for depth) used for AI synthesis across all services.

## Requirements

### Requirement 1: Embedded Chatbot Panel in Investigator View

**User Story:** As an investigator, I want to ask questions about case evidence, entities, and connections without leaving the investigator view, so that I can maintain context while researching.

#### Acceptance Criteria

1. WHEN the investigator clicks the chatbot toggle button, THE Chatbot_Panel SHALL slide open from the right side of the Investigator_View as an overlay panel with a width of 400 pixels.
2. WHEN the Chatbot_Panel is open and the investigator clicks the close button, THE Chatbot_Panel SHALL slide closed and restore the full Investigator_View layout.
3. WHILE a case is selected in the Investigator_View sidebar, THE Chatbot_Panel SHALL automatically bind to that case ID for all chat API calls without requiring the investigator to re-select the case.
4. WHEN the investigator sends a message in the Chatbot_Panel, THE Chatbot_Panel SHALL call the existing ChatService endpoint (POST /case-files/{id}/chat) with the message, conversation_id, and case context.
5. WHEN the ChatService returns a response, THE Chatbot_Panel SHALL display the AI response with clickable citation links ([Source N]) that reference case documents.
6. WHILE a conversation is active, THE Chatbot_Panel SHALL maintain the conversation_id across messages to preserve multi-turn conversation history.
7. WHEN the ChatService returns suggested_actions in the response, THE Chatbot_Panel SHALL render each suggested action as a clickable button that populates the chat input and sends the message.
8. WHEN the investigator clicks the "Share Finding" button on a chat response, THE Chatbot_Panel SHALL call the existing share endpoint (POST /case-files/{id}/chat/share) to save the finding.
9. THE Chatbot_Panel SHALL display a command hint bar showing available commands: "summarize case", "who is [name]", "connections between A and B", "timeline", "what's missing", "draft subpoena list".
10. WHEN the Chatbot_Panel is open, THE Investigator_View SHALL remain fully interactive behind the panel, allowing the investigator to switch tabs, click graph nodes, and browse evidence.

### Requirement 2: Compare Mode — Internal Evidence vs External Research

**User Story:** As an investigator, I want to see internal case evidence side-by-side with external public research findings, so that I can identify what is confirmed, what is external-only, and what needs further research.

#### Acceptance Criteria

1. WHEN the investigator activates Compare Mode within the Research_Hub tab, THE Compare_View SHALL display a split-pane layout with "What We Have" (internal evidence) on the left and "What's Public" (external research) on the right.
2. WHEN the investigator submits a search query in Compare Mode, THE Compare_View SHALL call the InvestigativeSearchService endpoint with search_scope set to "internal_external" to retrieve both internal and external results.
3. WHEN the InvestigativeSearchService returns a Cross_Reference_Report, THE Compare_View SHALL color-code each finding: green for confirmed_internally, orange for external_only, and red for needs_research.
4. WHEN a finding is categorized as confirmed_internally, THE Compare_View SHALL display the matching internal evidence excerpts alongside the external source reference.
5. WHEN a finding is categorized as external_only, THE Compare_View SHALL display the external source in the right pane and show an empty placeholder with a "Research Internally" action button in the left pane.
6. WHEN a finding is categorized as needs_research, THE Compare_View SHALL display the finding with a red indicator and a "Start Research" action button that initiates a Research_Conversation for that topic.
7. THE Compare_View SHALL display the confidence_level returned by InvestigativeSearchService (strong_case, needs_more_evidence, or insufficient) as a summary badge above the split pane.
8. WHEN the investigator clicks on an internal evidence excerpt in the Compare_View, THE Compare_View SHALL open the document in the Evidence Library tab or drill-down panel with the relevant passage highlighted.
9. THE Compare_View SHALL display the executive_summary from the intelligence brief at the top of the view as a synthesis of both internal and external findings.

### Requirement 3: Narrative-Driven Pattern Intelligence

**User Story:** As an investigator, I want pattern discoveries to explain why a pattern matters investigatively rather than just reporting graph metrics, so that I can act on patterns without manually interpreting statistics.

#### Acceptance Criteria

1. WHEN the PatternDiscoveryService synthesizes investigative questions for top patterns, THE Pattern_Narrative_Engine SHALL generate narrative explanations that describe the investigative significance of each pattern, not graph statistics alone.
2. WHEN generating a narrative for a co-occurrence pattern, THE Pattern_Narrative_Engine SHALL explain the relationship context (e.g., "A and B appear together in 12 documents but never with C, despite C being mentioned in the same time period — this gap may indicate deliberate separation") rather than listing entity names and counts.
3. THE Pattern_Narrative_Engine SHALL use Bedrock_Claude to synthesize pattern narratives using a prompt that includes the investigator persona from LeadGeneratorService ("senior federal investigative analyst with 20+ years of experience").
4. WHEN generating a narrative, THE Pattern_Narrative_Engine SHALL incorporate evidence from all available modalities (text, visual, face, co-occurrence) referenced in the pattern to produce cross-modal investigative insights.
5. WHEN a pattern has a composite_score below 0.3, THE Pattern_Narrative_Engine SHALL include a caveat in the narrative indicating low evidence strength and recommending further corroboration.
6. THE Pattern_Narrative_Engine SHALL produce narratives that cite specific entity names, document counts, and relationship types from the pattern data rather than using generic placeholders.
7. WHEN the PatternDiscoveryService returns top patterns to the Research_Hub, THE Research_Hub SHALL display each pattern as a narrative card with the investigative question, the narrative explanation, a confidence indicator, and a list of supporting entities.
8. WHEN the investigator clicks on a pattern narrative card, THE Research_Hub SHALL open the entity drill-down panel for the primary entity in that pattern.

### Requirement 4: Conversational External Research

**User Story:** As an investigator, I want to have a back-and-forth conversation with the external research agent after the initial OSINT report, so that I can refine searches, ask follow-up questions, and drill deeper into specific findings.

#### Acceptance Criteria

1. THE Research_Hub SHALL retain the existing OSINT_Quick_Action button that triggers AIResearchAgent to generate a one-shot research report for the selected entity or subject.
2. WHEN the investigator clicks "Start Research Conversation" for a subject, THE Research_Hub SHALL open a Research_Conversation chat interface within the Research_Hub tab.
3. WHEN a Research_Conversation starts, THE Research_Hub SHALL call AIResearchAgent to generate the initial OSINT report and display the report as the first AI message in the conversation.
4. WHEN the investigator sends a follow-up message in a Research_Conversation, THE Research_Hub SHALL send the message to a new conversational research endpoint that includes the prior research context and the follow-up query.
5. WHEN the conversational research endpoint receives a follow-up query, THE AIResearchAgent SHALL use the prior research report as context and invoke Bedrock_Claude to generate a targeted response addressing the follow-up question.
6. WHILE a Research_Conversation is active, THE Research_Hub SHALL maintain the full conversation history (prior research report and all follow-up exchanges) and include the last 10 messages as context for each new Bedrock_Claude invocation.
7. WHEN the investigator asks to "refine the search" or "search for [specific topic]" in a Research_Conversation, THE AIResearchAgent SHALL execute a new Brave_Search_API query with the refined terms and synthesize the results into the conversation.
8. WHEN the investigator asks to "drill deeper into [finding]" in a Research_Conversation, THE AIResearchAgent SHALL extract the referenced finding from the prior research context and generate a focused deep-dive report on that specific finding.
9. WHEN the investigator clicks "Save to Case" on a Research_Conversation message, THE Research_Hub SHALL save the message content as an investigator finding attached to the current case using the existing share_finding mechanism.
10. IF the Bedrock_Claude invocation fails during a Research_Conversation, THEN THE Research_Hub SHALL display an error message indicating the failure and allow the investigator to retry the last message.

### Requirement 5: Research Hub Tab Integration

**User Story:** As an investigator, I want all research capabilities accessible from a single tab in the investigator view, so that I do not need to navigate between separate pages for search, chat, patterns, and external research.

#### Acceptance Criteria

1. THE Investigator_View SHALL include a "Research Hub" tab in the tab bar alongside existing tabs (Graph, Timeline, Patterns, Evidence Library, etc.).
2. WHEN the investigator selects the Research Hub tab, THE Research_Hub SHALL display sub-navigation for four panels: Chat, Compare, Patterns, and External Research.
3. WHEN the investigator switches between Research_Hub sub-panels, THE Research_Hub SHALL preserve the state of each sub-panel (active conversations, search results, pattern views) so that returning to a sub-panel restores the previous state.
4. WHILE no case is selected in the Investigator_View sidebar, THE Research_Hub SHALL display an empty state prompting the investigator to select a case.
5. WHEN the investigator selects a different case in the sidebar, THE Research_Hub SHALL reset all sub-panel states and rebind to the new case ID.
6. THE Research_Hub SHALL load without blocking the initial render of the Investigator_View, deferring data fetches until the Research Hub tab is activated or the Chatbot_Panel is opened.

### Requirement 6: Conversational Research API Endpoint

**User Story:** As a backend developer, I want a new API endpoint that supports multi-turn conversational research with the AIResearchAgent, so that the frontend can send follow-up queries with prior context.

#### Acceptance Criteria

1. THE API SHALL expose a POST /case-files/{id}/research/chat endpoint that accepts a JSON body with fields: message (string), conversation_id (optional string), research_context (optional object containing prior research results), and subject (object with name and type).
2. WHEN the endpoint receives a request without a conversation_id, THE API SHALL generate a new conversation_id, call AIResearchAgent to produce the initial research report, and return the report with the new conversation_id.
3. WHEN the endpoint receives a request with an existing conversation_id, THE API SHALL load the prior conversation context and pass the follow-up message along with prior research context to Bedrock_Claude for a contextual response.
4. THE API SHALL return a JSON response containing: response (string), conversation_id (string), sources (array of external source references), and suggested_followups (array of suggested follow-up questions).
5. IF the AIResearchAgent or Bedrock_Claude invocation fails, THEN THE API SHALL return a 500 status code with an error_code of "RESEARCH_FAILED" and a descriptive error message.
6. THE API SHALL complete each request within 29 seconds to stay within the API Gateway timeout budget, using Bedrock_Claude Haiku for speed-critical synthesis.
