# Requirements Document

## Introduction

The Research Analyst Platform is a reusable, serverless research engine that enables users to create unlimited "case files" to research any topic. The platform follows investigative journalism principles — structured data collection, entity extraction, pattern discovery, and cross-referencing — to help users "find the needle in the haystack when they don't know the needle." AI discovers hidden patterns and connections; a human analyst reviews and directs the investigation.

The architecture is built on Aurora Serverless v2 (pgvector), Neptune Serverless, Bedrock Knowledge Bases + Agents, S3, Lambda, Step Functions, and a Streamlit frontend (with a future option to port to Next.js for a polished customer-facing demo). All case files share the same infrastructure with logical separation, and the system scales to near-zero when idle.

The first use case is Ancient Aliens public transcripts as a demonstration of the platform's capabilities.

## Glossary

- **Platform**: The Research Analyst Platform — the complete serverless system including all backend services, AI components, and frontend interface
- **Case_File**: A logical research container representing a single research topic. Stored as a metadata record containing case ID, topic name, description, search parameters, S3 prefixes, Aurora filters, Neptune subgraph labels, research status, findings, and pattern reports
- **Sub_Case_File**: A Case_File created by drilling down into a specific pattern or entity discovered within a parent Case_File, inheriting context from the parent
- **Ingestion_Pipeline**: The Step Functions orchestration that processes raw data through extraction, vectorization, and graph population stages
- **Entity**: A discrete concept extracted from source data — such as a person, location, date, artifact, civilization, or theme — represented as a node in Neptune
- **Pattern**: An unexpected or statistically notable connection between Entities discovered through graph traversal or vector similarity queries
- **Research_Interface**: The Streamlit-based frontend for interacting with case files — a structured investigation tool with parameterized queries, data visualizations, and graph exploration. Designed for rapid iteration on analysis logic, with a future path to a Next.js frontend for polished customer demos
- **Knowledge_Base**: A Bedrock Knowledge Base configured with Aurora pgvector as its vector store, used for semantic search across case file documents
- **Graph**: The Neptune Serverless graph database storing Entities as nodes and their relationships (co-occurrences, causal links, thematic connections) as edges
- **Vector_Store**: Aurora Serverless v2 with pgvector extension, storing document embeddings for semantic similarity search
- **Data_Lake**: S3 storage organized by case ID containing raw transcripts, processed documents, and extraction artifacts
- **Pattern_Report**: A structured summary of discovered Patterns within or across Case_Files, including AI-generated explanations and confidence scores
- **Cross_Case_Graph**: A dedicated Neptune subgraph that links Entities from multiple Case_Files via cross-case edges, persisted as a named investigative workspace without modifying the original Case_File subgraphs

## Requirements

### Requirement 1: Case File Creation

**User Story:** As a research analyst, I want to create a new case file for any research topic, so that I can begin a structured investigation without requiring new infrastructure.

#### Acceptance Criteria

1. WHEN a user submits a new case file request with a topic name and description, THE Platform SHALL create a Case_File metadata record in Aurora containing a unique case ID, topic name, description, creation timestamp, research status set to "created", and empty findings
2. WHEN a Case_File is created, THE Platform SHALL provision logical separation in the Data_Lake by creating an S3 prefix structure under the case ID for raw data, processed documents, and extraction artifacts
3. WHEN a Case_File is created, THE Platform SHALL assign Neptune subgraph labels scoped to the case ID so that Entities and relationships are logically isolated per case
4. THE Platform SHALL allow creation of unlimited Case_Files without requiring infrastructure provisioning beyond the initial shared deployment
5. IF a Case_File creation request is missing required fields (topic name or description), THEN THE Platform SHALL return a validation error specifying the missing fields

### Requirement 2: Data Ingestion Pipeline

**User Story:** As a research analyst, I want to ingest raw source data into a case file, so that the platform can process and index the data for investigation.

#### Acceptance Criteria

1. WHEN raw data files are uploaded to a Case_File, THE Ingestion_Pipeline SHALL store the original files in the Data_Lake under the case-specific S3 prefix
2. WHEN the Ingestion_Pipeline processes a document, THE Platform SHALL use Bedrock to extract Entities (people, locations, dates, artifacts, civilizations, themes) and relationships from the document text
3. WHEN Entities are extracted, THE Ingestion_Pipeline SHALL create corresponding nodes in the Graph with the Case_File subgraph label and properties including entity type, name, source document reference, and extraction confidence score
4. WHEN relationships between Entities are extracted, THE Ingestion_Pipeline SHALL create edges in the Graph with relationship type, source document reference, and confidence score
5. WHEN a document is processed, THE Ingestion_Pipeline SHALL generate vector embeddings via Bedrock and store them in the Vector_Store with metadata linking back to the Case_File and source document
6. WHEN the Ingestion_Pipeline processes a document, THE Platform SHALL index the document into the Knowledge_Base for semantic retrieval
7. WHEN all documents in a batch are processed, THE Ingestion_Pipeline SHALL update the Case_File status to "indexed" and record processing statistics (document count, entity count, relationship count)
8. IF a document fails processing, THEN THE Ingestion_Pipeline SHALL log the failure with the document identifier and error details, skip the failed document, and continue processing remaining documents
9. IF the Ingestion_Pipeline encounters an unrecoverable error, THEN THE Platform SHALL set the Case_File status to "error" and record the error details in the Case_File metadata

### Requirement 3: Pattern Discovery

**User Story:** As a research analyst, I want the platform to discover hidden patterns and unexpected connections in my case file data, so that I can identify leads worth investigating further.

#### Acceptance Criteria

1. WHEN a user initiates pattern discovery on a Case_File, THE Platform SHALL query the Graph for unexpected Entity connections within the Case_File subgraph using graph traversal algorithms (shortest path, community detection, centrality analysis)
2. WHEN the Platform identifies a candidate Pattern, THE Platform SHALL use Bedrock to generate a natural-language explanation of the Pattern including the Entities involved, the nature of the connection, and a confidence score
3. WHEN pattern discovery completes, THE Platform SHALL produce a Pattern_Report containing all discovered Patterns ranked by confidence score and novelty
4. WHEN a user requests semantic pattern discovery, THE Platform SHALL query the Vector_Store for clusters of semantically similar content across documents within the Case_File
5. THE Platform SHALL combine graph-based and vector-based pattern results into a unified Pattern_Report, deduplicating overlapping discoveries

### Requirement 4: Drill-Down Investigation

**User Story:** As a research analyst, I want to drill down into a discovered pattern or entity to create a focused sub-investigation, so that I can research specific leads in depth.

#### Acceptance Criteria

1. WHEN a user selects a Pattern or Entity for drill-down, THE Platform SHALL create a Sub_Case_File linked to the parent Case_File with the selected Pattern or Entity as the research focus
2. WHEN a Sub_Case_File is created, THE Platform SHALL copy relevant Entity nodes and relationships from the parent Case_File subgraph into the Sub_Case_File subgraph as seed data
3. WHEN a Sub_Case_File exists, THE Platform SHALL allow the user to ingest additional external data specific to the drill-down topic through the standard Ingestion_Pipeline
4. THE Platform SHALL maintain a navigable parent-child hierarchy between Case_Files and their Sub_Case_Files

### Requirement 5: Cross-Case Analysis and Dynamic Knowledge Graph

**User Story:** As a research analyst, I want to dynamically create cross-case knowledge graphs that connect related cases, so that I can discover and persist patterns across disparate research topics while keeping individual cases logically separated by default.

#### Acceptance Criteria

1. THE Platform SHALL keep all Case_File data logically separated by default — no cross-case graph edges or shared subgraphs SHALL exist unless explicitly created by the analyst
2. WHEN a user selects two or more Case_Files for cross-reference, THE Platform SHALL query the Graph for shared or similar Entities across the selected Case_File subgraphs
3. WHEN cross-case Entities are identified, THE Platform SHALL use Bedrock to analyze and explain the significance of cross-case connections
4. WHEN cross-case pattern comparison completes, THE Platform SHALL produce a cross-reference Pattern_Report listing shared Entities, parallel patterns, and AI-generated analysis of potential connections
5. WHEN a user initiates a cross-case investigation, THE Platform SHALL create a dedicated Cross_Case_Graph — a new Neptune subgraph that links Entities from the selected Case_Files via cross-case edges without modifying the original Case_File subgraphs
6. THE Platform SHALL persist each Cross_Case_Graph as a named, reusable investigative workspace with its own metadata record (linked case IDs, creation date, analyst notes, status)
7. WHEN a new Case_File is ingested, THE Platform SHALL automatically scan for potential Entity overlaps with existing Case_Files and notify the analyst of candidate cross-case connections without creating links
8. WHEN the analyst confirms a candidate cross-case connection, THE Platform SHALL add the connection to an existing or new Cross_Case_Graph
9. THE Platform SHALL allow the analyst to add or remove Case_Files from an existing Cross_Case_Graph at any time, dynamically updating the cross-case edges
10. THE Platform SHALL render Cross_Case_Graphs in the Research_Interface with visual distinction between within-case edges and cross-case edges
11. THE Platform SHALL allow cross-referencing between any combination of Case_Files and Sub_Case_Files

### Requirement 6: Structured Research Interface

**User Story:** As a research analyst, I want a structured investigation interface with guided prompts, so that I can collect and analyze data consistently without relying on freeform chat.

#### Acceptance Criteria

1. THE Research_Interface SHALL be built with Streamlit and present case file data through a structured dashboard showing case metadata, ingestion status, entity counts, relationship counts, and pattern discovery results
2. THE Research_Interface SHALL provide parameterized query templates via Streamlit sidebar controls and form inputs for common investigative actions (entity search, relationship exploration, timeline analysis, geographic clustering)
3. WHEN a user executes a structured query, THE Research_Interface SHALL display results in a consistent, tabular or visual format appropriate to the query type using Streamlit's native data display and charting components
4. THE Research_Interface SHALL render an interactive network graph visualization of the Neptune Graph data for the selected Case_File using a Streamlit-compatible graph library (e.g., streamlit-agraph or pyvis), with Entities as nodes and relationships as edges
5. WHEN a user interacts with the graph visualization, THE Research_Interface SHALL allow filtering by entity type, relationship type, confidence score, and source document via Streamlit sidebar controls
6. THE Research_Interface SHALL provide a findings log where the analyst can record observations, tag Entities, and annotate Patterns within a Case_File
7. THE Research_Interface SHALL enforce structured data collection by providing predefined input formats and validation for analyst notes and research parameters

### Requirement 7: Case File Management

**User Story:** As a research analyst, I want to manage the lifecycle of my case files, so that I can organize, archive, and track the status of my investigations.

#### Acceptance Criteria

1. THE Platform SHALL support Case_File statuses: "created", "ingesting", "indexed", "investigating", "archived", and "error"
2. WHEN a user requests to archive a Case_File, THE Platform SHALL set the Case_File status to "archived" and retain all associated data in the Data_Lake, Vector_Store, and Graph
3. THE Platform SHALL provide a case file listing view showing all Case_Files with their status, creation date, topic, document count, entity count, and last activity timestamp
4. WHEN a user searches for Case_Files, THE Platform SHALL support filtering by status, topic keyword, creation date range, and entity count range
5. IF a user requests deletion of a Case_File, THEN THE Platform SHALL remove the Case_File metadata, associated S3 data, Vector_Store embeddings, and Graph subgraph data, and confirm deletion to the user

### Requirement 8: Cost-Optimized Serverless Scaling

**User Story:** As a platform operator, I want the system to scale to near-zero when idle, so that costs remain minimal when no active research is being conducted.

#### Acceptance Criteria

1. THE Platform SHALL use Aurora Serverless v2 configured to scale down to 0.5 ACU during idle periods
2. THE Platform SHALL use Neptune Serverless configured to scale to the minimum capacity (1 NCU) during idle periods
3. THE Platform SHALL use Lambda functions for all compute operations so that processing costs are pay-per-invocation only
4. THE Platform SHALL use Step Functions for pipeline orchestration so that orchestration costs are pay-per-state-transition only
5. THE Platform SHALL use Bedrock on-demand pricing so that AI processing costs are pay-per-invocation only
6. THE Platform SHALL store all raw and processed data in S3 with lifecycle policies to transition infrequently accessed data to S3 Infrequent Access after 90 days

### Requirement 9: Entity Extraction and Graph Population

**User Story:** As a research analyst, I want the platform to automatically extract entities and relationships from ingested documents, so that I can explore connections without manual data entry.

#### Acceptance Criteria

1. WHEN processing a document, THE Platform SHALL extract the following Entity types at minimum: Person, Location, Date, Artifact, Civilization, Theme, and Event
2. WHEN an Entity is extracted, THE Platform SHALL assign an entity type, a canonical name, source document references, occurrence count, and an extraction confidence score
3. WHEN the same Entity appears across multiple documents within a Case_File, THE Platform SHALL merge duplicate Entities into a single Graph node and aggregate occurrence counts and source references
4. WHEN a relationship between two Entities is extracted, THE Platform SHALL classify the relationship type (co-occurrence, causal, temporal, geographic, thematic) and store it as a Graph edge
5. WHEN entity extraction completes for a document, THE Platform SHALL store the extraction results as a structured JSON artifact in the Data_Lake alongside the source document

### Requirement 10: Bedrock Knowledge Base Integration

**User Story:** As a research analyst, I want to perform semantic searches across my case file documents, so that I can find relevant information using natural language queries.

#### Acceptance Criteria

1. THE Platform SHALL configure a Bedrock Knowledge_Base with Aurora pgvector as the vector store for each Case_File's document corpus
2. WHEN a user submits a semantic query against a Case_File, THE Platform SHALL retrieve relevant document passages from the Knowledge_Base ranked by semantic similarity
3. WHEN semantic search results are returned, THE Platform SHALL include source document references, relevance scores, and surrounding context for each result
4. WHEN a user requests an AI-assisted analysis of a Pattern or Entity, THE Platform SHALL use a Bedrock Agent with access to the Knowledge_Base to generate a structured analytical summary
5. THE Platform SHALL use Bedrock embedding models to generate vector representations of all ingested documents during the Ingestion_Pipeline

### Requirement 11: Data Parsing and Structured Output

**User Story:** As a research analyst, I want ingested documents to be parsed into a consistent internal format, so that downstream processing (entity extraction, vectorization, graph population) operates on clean, structured data.

#### Acceptance Criteria

1. WHEN a raw document is ingested, THE Ingestion_Pipeline SHALL parse the document into a structured internal representation containing document ID, case file ID, source metadata, raw text content, and extracted sections
2. THE Ingestion_Pipeline SHALL format the structured internal representation back into a human-readable document for review and export
3. FOR ALL valid structured document representations, parsing then formatting then parsing SHALL produce an equivalent structured representation (round-trip property)
4. IF a raw document cannot be parsed due to unsupported format or corruption, THEN THE Ingestion_Pipeline SHALL return a descriptive error including the document identifier and the reason for failure
