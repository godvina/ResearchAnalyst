# Bugfix Requirements Document

## Introduction

Multiple services and API endpoints perform unbounded SQL queries (no LIMIT clause) on the `documents` and `entities` tables. At the current scale of 8,974 documents (Epstein Combined), these queries complete within the 29-second API Gateway timeout. When Epstein Main reaches 350,000 documents after ingestion, these unbounded queries will timeout the API Gateway, crash the Lambda, or freeze the browser by sending 100K+ nodes to vis-network for rendering. Additionally, the `discover_vector_patterns` method performs an O(n²) self-join on the documents table which will be catastrophic at 350K rows. This must be fixed before the 90K overnight batch ingestion run.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a case has 350K+ documents THEN `theory_engine_service._extract_entities()` loads ALL entity canonical_names into memory (77K+ rows) without any LIMIT, causing Lambda memory pressure and potential timeout

1.2 WHEN a case has 77K+ entities THEN `anomaly_detection_service._detect_frequency_anomalies()` fetches ALL entities with occurrence_count (no LIMIT), transferring 77K+ rows over the wire and computing z-scores on the full set, risking API Gateway 29s timeout

1.3 WHEN a case has 350K+ documents THEN `pattern_discovery_service.discover_vector_patterns()` performs an O(n²) self-join on the documents table (`FROM documents a JOIN documents b`) without any row LIMIT, causing Aurora query timeout or Lambda crash

1.4 WHEN a case has 350K+ documents THEN `access_control_service._get_all_document_ids()` loads ALL document_ids into a Python set (350K+ UUIDs), consuming excessive memory and risking timeout

1.5 WHEN the frontend knowledge graph loads for a case with 77K+ entities THEN `loadGraph()` in `investigator.html` attempts to render all returned nodes via vis-network, freezing the browser tab

1.6 WHEN a case has 77K+ entities THEN `theory_engine_service._extract_entities()` iterates over ALL entity names doing substring matching against text (`name.lower() in text_lower`), which is O(n*m) and will be extremely slow at scale

1.7 WHEN the anomaly detection `_detect_frequency_anomalies` returns, it embeds ALL 77K+ occurrence counts in the `data_points` field of each Anomaly object, creating massive JSON payloads sent to the frontend

### Expected Behavior (Correct)

2.1 WHEN a case has 350K+ documents THEN `theory_engine_service._extract_entities()` SHALL query entities with a LIMIT (e.g., top 5000 by occurrence_count) to bound memory usage and query time

2.2 WHEN a case has 77K+ entities THEN `anomaly_detection_service._detect_frequency_anomalies()` SHALL add a LIMIT clause (e.g., top 1000 entities by occurrence_count DESC) to bound the query, and compute z-scores on the bounded sample

2.3 WHEN a case has 350K+ documents THEN `pattern_discovery_service.discover_vector_patterns()` SHALL add a LIMIT to the self-join query (e.g., LIMIT 500 result pairs) or use a subquery to restrict input rows, preventing O(n²) explosion

2.4 WHEN a case has 350K+ documents THEN `access_control_service._get_all_document_ids()` SHALL add a LIMIT or use a paginated/streaming approach, or the callers SHALL be refactored to avoid loading all IDs at once

2.5 WHEN the frontend knowledge graph loads for a large case THEN `loadGraph()` SHALL display only the top N entities (e.g., top 100 by degree centrality) with a "Load More" or filtering mechanism, preventing browser freeze

2.6 WHEN `theory_engine_service._extract_entities()` matches entities against text THEN it SHALL use a bounded entity set (top N by occurrence_count) and the matching SHALL complete within a reasonable time budget

2.7 WHEN `_detect_frequency_anomalies` returns anomalies THEN the `data_points` field SHALL contain only a bounded sample (e.g., top 200 counts) rather than all 77K+ values, keeping JSON payloads manageable

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a case has fewer than 10,000 documents (e.g., Epstein Combined with 8,974) THEN the system SHALL CONTINUE TO return the same results as before for all affected endpoints, with no visible change in behavior or data quality

3.2 WHEN `SELECT COUNT(*)` queries are used on documents or entities tables THEN the system SHALL CONTINUE TO return accurate counts without any LIMIT (COUNT queries are already bounded and efficient with an index)

3.3 WHEN the knowledge graph is loaded for a small case (< 200 entities) THEN the system SHALL CONTINUE TO display all entities as it does today, with no pagination or truncation applied

3.4 WHEN the timeline service queries date/event entities THEN the system SHALL CONTINUE TO use its existing LIMIT 500/2000 clauses unchanged (these are already bounded)

3.5 WHEN the discovery engine service queries entities and documents THEN the system SHALL CONTINUE TO use its existing LIMIT 50/20 clauses unchanged (these are already bounded)

3.6 WHEN pattern discovery queries Neptune via Gremlin THEN the system SHALL CONTINUE TO use its existing `.limit(100)`/`.limit(200)` clauses unchanged (these are already bounded)

3.7 WHEN `_gather_case_context` in theory_engine_service queries entities THEN the system SHALL CONTINUE TO use its existing LIMIT 500 clause unchanged (this is already bounded)
