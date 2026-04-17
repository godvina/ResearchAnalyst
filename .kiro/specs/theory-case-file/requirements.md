# Requirements Document

## Introduction

The Theory Case File feature enhances the existing Theory-Driven Investigation Engine's deep dive panel. Currently, clicking a theory shows raw OCR text fragments as evidence and broken entity tags. This feature replaces that with a professional, AI-generated 12-section investigative case file for each theory.

When an investigator first views a theory in detail, Bedrock Claude generates a structured case file covering all 12 sections — from Theory Statement through Confidence Level. The generated content is persisted to Aurora PostgreSQL so it loads instantly on subsequent views without regeneration. Investigators can add to and edit individual sections over time as new evidence is loaded. Sections lacking sufficient evidence are marked as "gaps" with a "Research Further" button. Entity extraction uses the Aurora entities table (21,488+ entities) instead of the current broken regex fragments.

This feature extends the existing `TheoryEngineService`, `theory_handler.py`, and `investigator.html` — no existing code is replaced.

## Glossary

- **Case_File_Content**: The AI-generated 12-section investigative case file for a single Theory, stored as a JSONB column in the `theory_case_files` table in Aurora_DB
- **Theory_Case_File**: A persisted record in Aurora_DB linking a Theory to its generated Case_File_Content, with metadata for generation timestamp and version
- **Section**: One of the 12 named divisions of a Theory_Case_File, each containing structured content specific to its purpose (e.g., Evidence For, Key Entities, Timeline)
- **Section_Gap**: A Section within a Theory_Case_File where the AI determined insufficient evidence exists to populate meaningful content, marked with a gap indicator and suggested research actions
- **Research_Further_Button**: A UI button displayed on Section_Gap sections that triggers a targeted search query in Intelligence Search to help the investigator find missing evidence
- **TheoryEngineService**: The existing Python backend service (`src/services/theory_engine_service.py`) extended with case file generation, persistence, and section editing methods
- **Theory_Handler**: The existing Lambda API handler (`src/lambdas/api/theory_handler.py`) extended with case file endpoints
- **Aurora_DB**: The Aurora PostgreSQL database storing case data, documents, entities, findings, theories, and the new `theory_case_files` table
- **Bedrock_LLM**: Amazon Bedrock Claude Haiku used for generating the 12-section case file content
- **Entity_Table**: The existing `entities` table in Aurora_DB containing 21,488+ canonical entity records with names, types, and occurrence counts
- **Investigator_View**: The existing `investigator.html` SPA containing the Theory Dashboard and Theory Deep Dive rendering logic
- **Theory_Deep_Dive**: The existing overlay panel shown when clicking a Theory_Card, which this feature enhances with the 12-section case file layout
- **ACH_Scorecard**: Section 3 of the case file — a radar chart with numeric scores for the 5 ACH dimensions
- **Evidence_For**: Section 4 — supporting documents with citations and relevance scores
- **Evidence_Against**: Section 5 — contradicting documents with explanations
- **Evidence_Gaps_Section**: Section 6 — missing evidence with suggested search queries
- **Key_Entities**: Section 7 — people, organizations, and locations linked to the theory, resolved from the Entity_Table
- **Competing_Theories**: Section 9 — other theories that explain the same evidence
- **Investigator_Assessment**: Section 10 — verdict with investigator notes
- **Recommended_Actions**: Section 11 — AI-suggested subpoenas, interviews, and searches
- **Confidence_Level**: Section 12 — Overall_Score with justification narrative

## Requirements

### Requirement 1: Case File Generation on First View

**User Story:** As an investigator, I want a professional 12-section case file generated automatically when I first view a theory in detail, so that I get structured analysis instead of raw OCR fragments.

#### Acceptance Criteria

1. WHEN the investigator opens the Theory_Deep_Dive for a Theory that has no existing Theory_Case_File in Aurora_DB, THE TheoryEngineService SHALL generate a complete 12-section Case_File_Content using Bedrock_LLM.
2. WHEN generating Case_File_Content, THE TheoryEngineService SHALL pass the Theory title, description, theory_type, ACH dimension scores, all classified evidence passages, and the case entity set to Bedrock_LLM in a structured prompt.
3. THE TheoryEngineService SHALL complete case file generation within 15 seconds, including evidence gathering and Bedrock_LLM invocation.
4. WHEN a Theory_Case_File already exists in Aurora_DB for the requested Theory, THE TheoryEngineService SHALL return the persisted content without invoking Bedrock_LLM.
5. IF Bedrock_LLM invocation fails during case file generation, THEN THE TheoryEngineService SHALL return a partial case file containing only the sections derivable from Aurora_DB data (Theory Statement, Classification, ACH Scorecard, Key Entities) and mark the remaining sections as Section_Gaps.

### Requirement 2: Case File 12-Section Structure

**User Story:** As an investigator, I want each case file to follow a consistent 12-section format, so that I can compare theories using a standardized analytical framework.

#### Acceptance Criteria

1. THE Case_File_Content SHALL contain exactly 12 sections in fixed order: Theory Statement, Classification, ACH Scorecard, Evidence For, Evidence Against, Evidence Gaps, Key Entities, Timeline, Competing Theories, Investigator Assessment, Recommended Actions, Confidence Level.
2. THE Theory Statement section SHALL contain the Theory title and full description text.
3. THE Classification section SHALL contain the Theory_Type value and a rationale paragraph explaining why the theory fits that classification.
4. THE ACH Scorecard section SHALL contain the five ACH dimension names with their numeric scores (0-100) and a brief interpretation for each dimension.
5. THE Evidence For section SHALL contain a list of supporting document citations, each with: source filename, relevant text excerpt (up to 300 characters), relevance score (0-100), and entity names mentioned.
6. THE Evidence Against section SHALL contain a list of contradicting document citations, each with: source filename, relevant text excerpt, relevance score, and an explanation of the contradiction.
7. THE Evidence Gaps section SHALL contain a list of identified missing evidence types, each with: a description of what evidence is missing and a suggested search query to find the evidence.
8. THE Key Entities section SHALL contain a list of entity records, each with: canonical entity name, entity type, occurrence count, and a one-sentence role description explaining the entity's relevance to the theory.
9. THE Timeline section SHALL contain a chronologically ordered list of evidence events, each with: date, event description, source document, and classification (supporting or contradicting).
10. THE Competing Theories section SHALL contain a list of other theories for the same case that share overlapping evidence or entities, each with: theory title, overall score, and a brief comparison statement.
11. THE Investigator Assessment section SHALL contain the current verdict value (or "Pending" if no verdict set) and a notes field for investigator commentary.
12. THE Recommended Actions section SHALL contain a list of AI-suggested next steps, each with: action type (subpoena, interview, document_search, field_investigation), target description, and priority (high, medium, low).
13. THE Confidence Level section SHALL contain the Overall_Score value and a justification narrative paragraph explaining the basis for the confidence assessment.

### Requirement 3: Case File Persistence to Aurora

**User Story:** As an investigator, I want generated case files saved to the database, so that they load instantly on subsequent views without regeneration.

#### Acceptance Criteria

1. THE Aurora_DB SHALL contain a `theory_case_files` table with columns: `case_file_content_id` (UUID primary key), `theory_id` (UUID foreign key to theories), `case_file_id` (UUID foreign key to case_files), `content` (JSONB containing the 12-section structure), `generated_at` (TIMESTAMP WITH TIME ZONE), `last_edited_at` (TIMESTAMP WITH TIME ZONE, nullable), `version` (INTEGER default 1).
2. THE `theory_case_files` table SHALL have a UNIQUE constraint on `theory_id` ensuring one case file per theory.
3. WHEN the TheoryEngineService generates a new Case_File_Content, THE TheoryEngineService SHALL insert the content into the `theory_case_files` table with `generated_at` set to the current timestamp.
4. WHEN the investigator requests a Theory detail that has an existing Theory_Case_File, THE TheoryEngineService SHALL query the `theory_case_files` table and return the persisted content in the response.
5. THE `theory_case_files` table SHALL have a foreign key constraint on `theory_id` referencing `theories(theory_id)` with ON DELETE CASCADE.

### Requirement 4: Section Editing by Investigators

**User Story:** As an investigator, I want to add notes and edit sections of the case file over time, so that I can enrich the analysis as more evidence becomes available.

#### Acceptance Criteria

1. WHEN the investigator clicks an "Edit" button on a Section in the Theory_Deep_Dive, THE Investigator_View SHALL display an inline text editor for that Section's content.
2. WHEN the investigator saves an edited Section, THE Investigator_View SHALL call the Theory_API to update only the modified Section within the Case_File_Content JSONB.
3. WHEN a Section is updated, THE TheoryEngineService SHALL update the `last_edited_at` timestamp and increment the `version` field in the `theory_case_files` table.
4. THE TheoryEngineService SHALL preserve all unmodified Sections when updating a single Section.
5. WHEN the investigator edits the Investigator Assessment section, THE Investigator_View SHALL provide a structured form with a verdict selector and a free-text notes field.

### Requirement 5: Section Gap Detection and Research Further

**User Story:** As an investigator, I want sections with insufficient evidence clearly marked as gaps with a button to research further, so that I know exactly where my analysis is incomplete.

#### Acceptance Criteria

1. WHEN generating Case_File_Content, THE TheoryEngineService SHALL evaluate each Section for evidence sufficiency and mark Sections with insufficient evidence as Section_Gaps.
2. THE TheoryEngineService SHALL mark a Section as a Section_Gap when: Evidence For has zero supporting citations, Evidence Against has zero contradicting citations, Timeline has fewer than 2 chronological events, or Key Entities has zero resolved entities from the Entity_Table.
3. WHEN rendering a Section_Gap in the Theory_Deep_Dive, THE Investigator_View SHALL display a muted placeholder message describing what evidence is needed and a Research_Further_Button.
4. WHEN the investigator clicks a Research_Further_Button, THE Investigator_View SHALL generate a targeted search query based on the Section type and Theory description, populate the Intelligence Search input, and trigger a search.
5. WHEN a Section_Gap is later populated through editing or case file regeneration, THE Investigator_View SHALL remove the gap indicator and display the Section content normally.

### Requirement 6: Entity Resolution from Aurora Entity Table

**User Story:** As an investigator, I want entity references in the case file resolved against the real entity database instead of broken regex fragments, so that entity information is accurate and clickable.

#### Acceptance Criteria

1. WHEN generating the Key Entities section, THE TheoryEngineService SHALL query the Entity_Table in Aurora_DB for all entities matching the Theory's supporting_entities list by canonical_name.
2. THE TheoryEngineService SHALL resolve each entity reference to include: canonical_name, entity_type, occurrence_count from the Entity_Table.
3. WHEN an entity name in the Theory description does not match any record in the Entity_Table, THE TheoryEngineService SHALL exclude the unmatched name from the Key Entities section.
4. WHEN rendering entity names in the Key Entities section, THE Investigator_View SHALL display each entity as a clickable badge that opens the existing DrillDown for that entity.
5. THE TheoryEngineService SHALL use case-insensitive matching when resolving entity names against the Entity_Table.

### Requirement 7: Case File API Endpoints

**User Story:** As a frontend client, I want API endpoints to retrieve and update case file content, so that the deep dive panel can load and save case file data.

#### Acceptance Criteria

1. THE Theory_Handler SHALL expose `GET /case-files/{id}/theories/{theory_id}/case-file` that returns the Theory_Case_File content for the specified Theory.
2. WHEN the GET endpoint is called for a Theory with no existing Theory_Case_File, THE TheoryEngineService SHALL generate the case file, persist the content to Aurora_DB, and return the generated content.
3. THE Theory_Handler SHALL expose `PUT /case-files/{id}/theories/{theory_id}/case-file/sections/{section_index}` that updates a single Section within the Case_File_Content.
4. THE section update endpoint SHALL accept a JSON body containing the updated Section content and merge the update into the existing JSONB content.
5. IF the specified theory_id does not exist, THEN THE Theory_Handler SHALL return a 404 response.
6. IF the section_index is outside the range 0-11, THEN THE Theory_Handler SHALL return a 400 response with a validation error message.
7. THE Theory_Handler SHALL expose `POST /case-files/{id}/theories/{theory_id}/case-file/regenerate` that triggers regeneration of the entire case file, replacing the existing content.

### Requirement 8: Case File Regeneration

**User Story:** As an investigator, I want to regenerate a case file when significant new evidence has been added, so that the analysis reflects the latest case data.

#### Acceptance Criteria

1. WHEN the investigator clicks a "Regenerate Case File" button in the Theory_Deep_Dive, THE Investigator_View SHALL call `POST /case-files/{id}/theories/{theory_id}/case-file/regenerate`.
2. WHEN the regenerate endpoint is called, THE TheoryEngineService SHALL generate a new Case_File_Content using current case evidence and Bedrock_LLM.
3. WHEN regenerating, THE TheoryEngineService SHALL preserve any investigator-edited content in the Investigator Assessment section (Section 10) and merge the edited notes into the new content.
4. WHEN regeneration completes, THE TheoryEngineService SHALL update the existing `theory_case_files` record with the new content, update `generated_at`, and increment `version`.
5. THE Investigator_View SHALL display a confirmation dialog before regeneration warning: "This will regenerate all AI-generated sections. Your notes in Investigator Assessment will be preserved. Continue?"

### Requirement 9: Theory Deep Dive UI — 12-Section Layout

**User Story:** As an investigator, I want the theory deep dive to render all 12 sections in a clean, professional layout, so that I can review the complete case file in one view.

#### Acceptance Criteria

1. WHEN the Theory_Deep_Dive opens, THE Investigator_View SHALL render all 12 sections in a vertical scrollable layout with section headers and dividers.
2. THE Investigator_View SHALL render the ACH Scorecard section (Section 3) with the existing Radar_Chart SVG and numeric score labels for each dimension.
3. THE Investigator_View SHALL render the Evidence For section (Section 4) with expandable citation cards showing source filename, excerpt text, relevance score bar, and entity badges.
4. THE Investigator_View SHALL render the Evidence Against section (Section 5) with a red-tinted left border (#fc8181) and contradiction explanation text.
5. THE Investigator_View SHALL render the Key Entities section (Section 7) with clickable entity badges that open the DrillDown, displaying entity type and occurrence count.
6. THE Investigator_View SHALL render the Timeline section (Section 8) as a horizontal SVG timeline with color-coded markers (green for supporting, red for contradicting evidence).
7. THE Investigator_View SHALL render the Recommended Actions section (Section 11) with action cards showing action type icon, target description, and priority badge.
8. WHEN the Theory_Deep_Dive loads, THE Investigator_View SHALL display a loading skeleton animation while the case file content is being fetched or generated.

### Requirement 10: Case File Content in Theory Detail API Response

**User Story:** As a frontend client, I want the existing theory detail endpoint to include case file content when available, so that the deep dive can render the full case file without a separate API call.

#### Acceptance Criteria

1. WHEN the `GET /case-files/{id}/theories/{theory_id}` endpoint is called, THE Theory_Handler SHALL include the Theory_Case_File content in the response if a persisted case file exists.
2. WHEN no Theory_Case_File exists for the requested Theory, THE Theory_Handler SHALL return the theory detail without case file content and include a `case_file_status` field set to `"not_generated"`.
3. WHEN a Theory_Case_File exists, THE Theory_Handler SHALL include a `case_file_status` field set to `"available"` and a `case_file` object containing the 12-section content, `generated_at`, `last_edited_at`, and `version`.


### Requirement 11: Promote Confirmed Theory to Sub-Case

**User Story:** As an investigator, I want to promote a confirmed theory to its own sub-case, so that I can spin off a focused investigation with its own document collection and entity graph when a theory warrants deeper independent analysis.

#### Acceptance Criteria

1. WHEN a Theory has a verdict of "confirmed", THE Investigator_View SHALL display a "Promote to Sub-Case" button in the Theory_Deep_Dive panel.
2. WHEN the investigator clicks "Promote to Sub-Case", THE Investigator_View SHALL display a confirmation dialog showing the theory title, supporting entities count, and a warning: "This will create a new sub-case under the current case, seeded with the theory's key entities. You can then ingest new documents specific to this investigation."
3. WHEN the investigator confirms promotion, THE Theory_Handler SHALL call the existing `create_sub_case_file` method on CaseFileService with the parent case ID, the theory title as topic_name, the theory description as description, and the theory's supporting_entities as the entity seed list.
4. WHEN the sub-case is created, THE TheoryEngineService SHALL store the sub-case ID on the theory record by updating a `promoted_sub_case_id` field (nullable UUID) in the theories table.
5. WHEN a Theory has already been promoted (promoted_sub_case_id is not null), THE Investigator_View SHALL replace the "Promote to Sub-Case" button with a "View Sub-Case" link that navigates to the sub-case.
6. THE "Promote to Sub-Case" button SHALL only be visible when the Theory verdict is "confirmed" — it SHALL NOT appear for theories with verdict "refuted", "inconclusive", or no verdict.
7. THE Theory_Handler SHALL expose `POST /case-files/{id}/theories/{theory_id}/promote` that creates the sub-case and returns the new sub-case ID.
