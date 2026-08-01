# Requirements Document

## Introduction

The Typology Subgraph Pipeline replaces real-time Neptune graph traversal with a pre-computed, asynchronous pipeline architecture. For large cases (100K+ entities), real-time Neptune queries exceed the API Gateway 29-second timeout, causing "Failed to fetch" errors in the investigator UI. This feature introduces a background Step Function pipeline that extracts typology-specific subgraphs offline, scores them against prosecution patterns, stores results in Aurora, and serves pre-computed data at page-load time with sub-second latency.

## Glossary

- **Pipeline**: The AWS Step Functions state machine that orchestrates background typology extraction, scoring, and storage after document ingestion completes
- **Typology_Module**: One of the 11 crime typology pattern recognition engines (sex_trafficking, fraud_waste_abuse, drug_trafficking, money_laundering, cybercrime, terrorism_financing, public_corruption, organized_crime, child_exploitation, sanctions_evasion, environmental_crime)
- **Subgraph**: A subset of the Neptune graph containing only the entities and relationships relevant to a specific crime typology
- **Summary_Graph**: A condensed graph of 30-50 hub nodes representing entities that appear across multiple typologies, used for cross-typology visualization
- **Hub_Node**: An entity that appears in two or more typology subgraphs, indicating multi-crime involvement
- **Typology_Score**: A composite score (0.0-1.0) representing the strength of a typology match for a given case, derived from k-NN vector similarity and pattern matching
- **Match_Strength**: A classification of typology score into Strong (cosine similarity ≥ 0.80), Moderate (0.60-0.79), or Weak (< 0.60) categories
- **Staleness_Flag**: A boolean marker on a stored typology result indicating that new documents have been ingested since the last pipeline computation
- **Ingestion_Pipeline**: The existing Step Functions workflow that processes uploaded documents into Neptune entities and OpenSearch embeddings
- **Aurora_Cache**: The Aurora PostgreSQL tables storing pre-computed typology scores, subgraph summaries, and summary graph data
- **Investigator_UI**: The investigator.html frontend with Command Center, Top 5 Patterns, and Crime Typology panels
- **Case_Entity_Threshold**: The configurable entity count (default: 100,000) above which a case is classified as large and requires pipeline pre-computation

## Requirements

### Requirement 1: Pipeline Trigger After Ingestion

**User Story:** As a system administrator, I want the typology pipeline to run automatically after document ingestion completes, so that pre-computed results are available before investigators access the case.

#### Acceptance Criteria

1. WHEN the Ingestion_Pipeline completes successfully for a case, THE Pipeline SHALL initiate typology subgraph extraction for that case within 60 seconds
2. WHEN the Pipeline is triggered, THE Pipeline SHALL execute independently of the Investigator_UI with no dependency on API Gateway
3. IF the Pipeline fails to start after ingestion completion, THEN THE Pipeline SHALL record the failure in Aurora with a timestamp, case identifier, and error description
4. THE Pipeline SHALL support manual triggering by a system administrator via an API endpoint or Step Functions console

### Requirement 2: Typology Subgraph Extraction

**User Story:** As a federal investigative analyst, I want the system to extract crime-specific subgraphs from the full Neptune graph, so that I see only the relationships relevant to each typology.

#### Acceptance Criteria

1. WHEN the Pipeline processes a case, THE Pipeline SHALL execute targeted Neptune queries for each of the 11 Typology_Modules
2. WHEN extracting a subgraph for a Typology_Module, THE Pipeline SHALL retrieve only the entity types and relationship patterns defined by that module (e.g., person→financial_entity edges for Financial Control, person→location edges with temporal clustering for Transportation)
3. THE Pipeline SHALL complete subgraph extraction for a single typology within 300 seconds, utilizing the full Lambda timeout without API Gateway constraints
4. IF a Neptune query exceeds 300 seconds for a single typology, THEN THE Pipeline SHALL terminate that query, log the timeout, and proceed to the next typology
5. THE Pipeline SHALL process all 11 typologies for a case with 348K entities within 60 minutes total execution time

### Requirement 3: Typology Scoring Against Prosecution Patterns

**User Story:** As a federal investigative analyst, I want each typology subgraph scored against known prosecution patterns, so that I can prioritize the strongest leads.

#### Acceptance Criteria

1. WHEN a typology subgraph is extracted, THE Pipeline SHALL compute a Typology_Score by performing k-NN vector similarity search against prosecution pattern embeddings in OpenSearch
2. THE Pipeline SHALL classify each Typology_Score into a Match_Strength category: Strong (cosine similarity ≥ 0.80), Moderate (0.60-0.79), or Weak (< 0.60)
3. WHEN a typology subgraph scores Strong or Moderate, THE Pipeline SHALL invoke Bedrock Claude Haiku to generate a structured narrative summary of the evidence patterns
4. THE Pipeline SHALL generate a Bedrock synthesis for each scored typology within 30 seconds per invocation
5. IF Bedrock invocation fails or times out, THEN THE Pipeline SHALL store the Typology_Score and Match_Strength without the narrative summary and mark the result as synthesis_pending

### Requirement 4: Pre-Computed Results Storage in Aurora

**User Story:** As a federal investigative analyst, I want typology results stored in Aurora, so that page loads are fast regardless of case size.

#### Acceptance Criteria

1. WHEN the Pipeline completes scoring for a typology, THE Pipeline SHALL persist the Typology_Score, Match_Strength, subgraph summary, key entities, and Bedrock narrative to Aurora_Cache
2. THE Pipeline SHALL store results in a schema that supports retrieval of all typology scores for a case in a single query
3. THE Pipeline SHALL record a computation timestamp with each stored result to enable staleness detection
4. IF a result already exists for the same case and typology, THEN THE Pipeline SHALL overwrite the previous result with the new computation

### Requirement 5: Aurora-First Serving at Page Load

**User Story:** As a federal investigative analyst, I want to see typology results immediately when I open a case, so that I do not wait for graph queries to complete.

#### Acceptance Criteria

1. WHEN an investigator requests typology data for a case with pre-computed results, THE Investigator_UI SHALL load all typology scores, subgraph summaries, and key entities from Aurora_Cache
2. THE Investigator_UI SHALL return pre-computed typology data to the frontend within 500 milliseconds
3. WHILE pre-computed results exist for a case, THE Investigator_UI SHALL serve those results without invoking Neptune or Bedrock at page-load time
4. WHEN pre-computed results carry a Staleness_Flag, THE Investigator_UI SHALL display the results with a visible indicator that updated analysis is pending

### Requirement 6: Cross-Typology Summary Graph

**User Story:** As a federal investigative analyst, I want a focused summary graph showing entities involved in multiple crime typologies, so that I can identify key subjects without navigating an unreadable 348K-entity graph.

#### Acceptance Criteria

1. WHEN the Pipeline completes scoring for all typologies of a case, THE Pipeline SHALL build a Summary_Graph containing 30-50 Hub_Nodes
2. THE Pipeline SHALL select Hub_Nodes as entities that appear in two or more typology subgraphs
3. THE Pipeline SHALL include edges between Hub_Nodes that represent their relationships from the Neptune graph
4. THE Pipeline SHALL annotate each Hub_Node with the list of typologies in which the entity participates and the corresponding Match_Strength values
5. THE Pipeline SHALL store the Summary_Graph in Aurora_Cache in a format suitable for frontend graph visualization rendering

### Requirement 7: Incremental Update on New Document Ingestion

**User Story:** As a system administrator, I want the pipeline to re-process only affected typologies when new documents arrive, so that pipeline execution time scales with the size of the update rather than the full case.

#### Acceptance Criteria

1. WHEN new documents are ingested for a case with existing pre-computed results, THE Pipeline SHALL set the Staleness_Flag on all typology results affected by the new entities
2. WHEN the Pipeline executes for a case with stale results, THE Pipeline SHALL re-process only the typologies whose Staleness_Flag is set
3. THE Pipeline SHALL determine affected typologies by mapping new entity types to Typology_Module entity type definitions
4. IF all typologies are affected by a new ingestion, THEN THE Pipeline SHALL execute a full re-computation rather than incremental updates

### Requirement 8: Backward Compatibility for Small Cases

**User Story:** As a federal investigative analyst working small cases, I want existing real-time typology functionality to continue working without change, so that the pipeline does not degrade my workflow.

#### Acceptance Criteria

1. WHILE a case has fewer entities than the Case_Entity_Threshold, THE Investigator_UI SHALL continue using real-time Neptune queries for typology analysis
2. WHEN a case exceeds the Case_Entity_Threshold, THE Investigator_UI SHALL serve typology data exclusively from Aurora_Cache
3. THE Pipeline SHALL execute for cases above the Case_Entity_Threshold without altering the query paths used for cases below it
4. IF a case crosses the Case_Entity_Threshold due to new ingestion, THEN THE Pipeline SHALL trigger a full pipeline computation for that case

### Requirement 9: Pipeline Health Monitoring

**User Story:** As a system administrator, I want visibility into pipeline execution status and failures, so that I can diagnose issues and ensure results are current.

#### Acceptance Criteria

1. THE Pipeline SHALL record execution start time, end time, status (succeeded, failed, partial), and per-typology timing in Aurora
2. WHEN a Pipeline execution fails, THE Pipeline SHALL emit a CloudWatch alarm with the case identifier, failed step, and error message
3. THE Pipeline SHALL expose a health status API endpoint that returns the last execution time and status for a given case
4. WHILE the Pipeline is executing for a case, THE health status API SHALL report the execution as in_progress with the current step identifier

### Requirement 10: Concurrent Pipeline Execution Safety

**User Story:** As a system administrator, I want to ensure that multiple pipeline executions for the same case do not corrupt stored results, so that data integrity is maintained.

#### Acceptance Criteria

1. IF a Pipeline execution is already in progress for a case, THEN THE Pipeline SHALL reject or queue a duplicate trigger for the same case
2. THE Pipeline SHALL use database-level locking or conditional writes when persisting results to Aurora_Cache to prevent partial overwrites
3. WHEN a queued execution begins after a prior execution completes, THE Pipeline SHALL use the latest graph state rather than a stale snapshot

