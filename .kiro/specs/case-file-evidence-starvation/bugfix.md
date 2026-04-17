# Bugfix Requirements Document

## Introduction

The theory case file generator in `generate_case_file()` produces sparse, low-quality content and a completely empty legal analysis section (section 12) despite the Epstein Main case containing 345,898 documents and 77,900 entities. The root cause is twofold: (1) evidence starvation — the system fetches only 15 documents via a blind `ORDER BY indexed_at DESC LIMIT 15` query with no relevance filtering, passing only 10 at 150 chars each to Bedrock; and (2) token pressure — a single Bedrock call with `max_tokens=4096` must generate all 13 complex sections, causing the legal analysis section to be truncated or empty.

The fix replaces the blind evidence query with a pgvector KNN semantic search that retrieves the 30 most relevant documents to the theory, uses a two-pass Bedrock generation strategy (sections 1–11 in Pass 1, legal analysis in Pass 2 with a legal-focused KNN query), and adds a confidence penalty for detected section gaps. The existing `AuroraPgvectorBackend` and `SemanticSearchService` infrastructure (Titan Embed + pgvector cosine similarity) is already deployed and will be reused.

## Bug Analysis

### Current Behavior (Defect)

**A. Stale Case Statistics (Post-Sync Display)**

1.1 WHEN Neptune-to-Aurora entity sync completes for a case THEN the `case_files.document_count`, `entity_count`, and `relationship_count` columns are NOT updated, causing the sidebar and case header to display stale counts (e.g., "50 docs · 0 entities · 0 rels" instead of "345,898 docs · 77,900 entities")

1.2 WHEN `_get_case_stats()` reads from `case_files` table and gets `document_count=50` THEN it does a corrective `COUNT(*)` only when count < 100, but the corrected value is not persisted back to `case_files`, so the sidebar remains stale on every page load

**B. Stuck AI Intelligence Briefing**

1.3 WHEN `analyze_case()` detects `doc_count > ASYNC_THRESHOLD` (from corrected stats) THEN it writes `status="processing"` to `investigator_analysis_cache` and fires an async Lambda, but if the async Lambda times out or errors during pattern discovery / hypothesis generation / lead generation on 345K docs, the cache remains stuck at `status="processing"` indefinitely

1.4 WHEN the frontend polls `get_analysis_status()` and the cache shows `status="processing"` THEN the UI displays "Analysis in progress..." with no way to recover or retry, because there is no timeout/expiry on the processing status

**C. Evidence Starvation in Case File Generation**

1.5 WHEN a case file is generated for a case with 345,898 documents THEN the system fetches only 15 documents via `ORDER BY indexed_at DESC LIMIT 15` with `LEFT(raw_text, 150)`, passing only 10 to the Bedrock prompt — these are the 15 most recently indexed documents regardless of relevance to the theory

1.6 WHEN a case file is generated for a case with 77,900 entities THEN the system passes only 20 entities to the Bedrock prompt via `entities[:20]`, limited to the theory's `supporting_entities` list which may be sparse or empty

1.7 WHEN a single Bedrock call with `max_tokens=4096` must generate all 13 sections THEN the legal analysis section (section 12) is returned empty or severely truncated because it is the most complex section and token budget is exhausted by earlier sections

1.8 WHEN `_detect_section_gaps()` identifies empty or sparse sections THEN the confidence score in the returned case file is unaffected because `confidence_level.overall_score` is taken directly from `theory.overall_score` with no penalty applied

1.9 WHEN the legal analysis section is empty THEN the frontend `renderCFLegalAnalysis()` renders a blank section with no statutes, no element readiness, and no sentencing advisory

### Expected Behavior (Correct)

**A. Case Statistics Auto-Refresh**

2.1 WHEN Neptune-to-Aurora entity sync completes, OR when any bulk ingestion/sync operation finishes THEN the system SHALL update `case_files.document_count`, `entity_count`, and `relationship_count` by running `COUNT(*)` queries against the `documents` and `entities` tables and persisting the results

2.2 THE system SHALL expose a `refresh_case_stats` API action that recalculates and persists document/entity/relationship counts for a given case_id, callable from scripts and the frontend

**B. Briefing Recovery**

2.3 WHEN `get_analysis_status()` finds a cached row with `status="processing"` that is older than 15 minutes THEN the system SHALL treat it as expired, delete the stale cache row, and allow a fresh analysis to be triggered

2.4 WHEN the async Lambda analysis fails or times out THEN the system SHALL write `status="error"` with an error message to the cache (this already exists in `run_async_analysis` but may not fire if the Lambda itself times out before reaching the error handler)

**C. KNN Evidence Retrieval and Two-Pass Generation**

2.5 WHEN a case file is generated THEN the system SHALL embed the theory title + description using Bedrock Titan Embed (`amazon.titan-embed-text-v1`) and use the resulting vector to perform a pgvector KNN cosine similarity search (`ORDER BY embedding <=> theory_vector LIMIT 30`) against the case's documents, retrieving the 30 most semantically relevant documents with `LEFT(raw_text, 300)`

2.6 WHEN a case file is generated THEN the system SHALL extract entities that co-occur in the KNN-retrieved documents (up to 40 entities) to provide theory-relevant entity context, supplementing the theory's `supporting_entities` list

2.7 WHEN generating the case file THEN the system SHALL use a two-pass Bedrock generation strategy: Pass 1 generates sections 1–11 using the KNN-retrieved evidence with `max_tokens=6144`, and Pass 2 generates section 12 (legal analysis) in a dedicated Bedrock call using a legal-focused KNN query (theory text + "legal implications statutes criminal charges") with `max_tokens=4096`

2.8 WHEN `_detect_section_gaps()` finds empty or sparse sections THEN the system SHALL reduce the `confidence_level.overall_score` by a penalty of 5 points per gap detected, so the confidence score reflects actual content quality

2.9 WHEN the two-pass generation completes THEN the legal analysis section SHALL contain populated `primary_statute`, `element_readiness`, and `sentencing_advisory` sub-sections (for legal/civil theory types)

2.10 WHEN a case has fewer than 30 documents or documents lack embeddings THEN the system SHALL fall back to the current `ORDER BY indexed_at DESC LIMIT 30` query with `LEFT(raw_text, 300)` so that small cases and un-embedded documents still generate case files

### Unchanged Behavior (Regression Prevention)

3.1 WHEN Bedrock fails during case file generation THEN the system SHALL CONTINUE TO return a fallback case file via `_build_fallback_case_file()`

3.2 WHEN a case file has already been generated and persisted to the `theory_case_files` table THEN the system SHALL CONTINUE TO load the persisted version instantly without re-generation

3.3 WHEN the case has a small number of documents (e.g., fewer than 30) THEN the system SHALL CONTINUE TO generate a case file using all available documents without error

3.4 WHEN competing theories exist for the same case THEN the system SHALL CONTINUE TO fetch and include up to 5 competing theories in the case file prompt

3.5 WHEN entity enrichment is performed after Bedrock response parsing THEN the system SHALL CONTINUE TO merge Aurora entity data into the key_entities section

3.6 WHEN the case file is generated asynchronously via Lambda THEN both Bedrock passes plus the two Titan Embed calls SHALL complete within the Lambda 900-second timeout

3.7 WHEN section editing or regeneration is triggered from the frontend THEN the system SHALL CONTINUE TO support inline section editing and the Regenerate Case File button

3.8 WHEN the existing `AuroraPgvectorBackend` or `SemanticSearchService` is used by other features (document search, pattern discovery, Q&A) THEN those features SHALL CONTINUE TO function without modification
