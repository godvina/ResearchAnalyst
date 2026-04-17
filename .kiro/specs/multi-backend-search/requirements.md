# Requirements Document

## Introduction

The Multi-Backend Search feature extends the Research Analyst Platform to support two search/vector backend tiers selectable per case file. The Standard Tier uses the existing Aurora Serverless v2 with pgvector — cost-effective, scales to zero, suitable for demos and datasets under ~500K documents. The Enterprise Tier adds OpenSearch Serverless — designed for large-scale enterprise use cases (millions of documents) with full-text search, hybrid search, faceted filtering, and sub-second response times.

This feature introduces a SearchBackend abstraction layer (Python Protocol) that both backends implement, ensuring the rest of the codebase is backend-agnostic. The tier is selected at case file creation time and determines how ingestion, indexing, and search operations are routed. Existing Standard tier cases continue to work exactly as before — this is purely additive.

## Glossary

- **Platform**: The Research Analyst Platform — the complete serverless system including all backend services, AI components, and frontend interface
- **Case_File**: A logical research container representing a single research topic, now including a search_tier attribute that determines which backend handles its search and indexing operations
- **Search_Tier**: An enumeration with two values — "standard" and "enterprise" — assigned at Case_File creation time and immutable thereafter
- **SearchBackend**: A Python Protocol (interface) defining the contract for search and indexing operations. Both the Aurora_Backend and OpenSearch_Backend implement this protocol
- **Aurora_Backend**: The SearchBackend implementation using Aurora Serverless v2 with pgvector for vector similarity search. This is the existing implementation, now wrapped behind the SearchBackend protocol
- **OpenSearch_Backend**: The SearchBackend implementation using OpenSearch Serverless for full-text search, vector search, hybrid search, and faceted filtering
- **Hybrid_Search**: A search mode available only on Enterprise tier that combines keyword-based full-text search with semantic vector similarity search, merging and re-ranking results from both approaches
- **Faceted_Filter**: A structured filter available only on Enterprise tier that narrows search results by metadata dimensions such as date range, person name, document type, or entity type
- **Ingestion_Pipeline**: The Step Functions orchestration that processes raw data through extraction, vectorization, and graph population stages, now routing indexing operations to the correct backend based on the Case_File's Search_Tier
- **Knowledge_Base**: A Bedrock Knowledge Base configured with either Aurora pgvector (Standard tier, native integration) or OpenSearch Serverless (Enterprise tier, via Bedrock's OpenSearch connector) as its vector store
- **Backend_Factory**: A factory component that returns the correct SearchBackend implementation based on a Case_File's Search_Tier
- **Research_Interface**: The Streamlit-based frontend, which adapts its search UI to show additional capabilities (faceted filters, hybrid search toggle) when viewing an Enterprise tier Case_File

## Requirements

### Requirement 1: SearchBackend Abstraction Layer

**User Story:** As a platform developer, I want a unified search interface that abstracts over multiple backend implementations, so that the rest of the codebase does not need to know which backend a case file uses.

#### Acceptance Criteria

1. THE Platform SHALL define a SearchBackend Python Protocol specifying methods for indexing documents, searching by vector similarity, and deleting indexed documents for a Case_File
2. THE Aurora_Backend SHALL implement the SearchBackend Protocol by delegating to the existing Aurora pgvector vector search logic
3. THE OpenSearch_Backend SHALL implement the SearchBackend Protocol by delegating to OpenSearch Serverless APIs for indexing and search operations
4. THE Platform SHALL provide a Backend_Factory that accepts a Search_Tier value and returns the corresponding SearchBackend implementation
5. WHEN any service in the Platform performs a search or indexing operation, THE Platform SHALL obtain the SearchBackend from the Backend_Factory using the Case_File's Search_Tier and invoke operations through the SearchBackend Protocol only

### Requirement 2: Tier Selection at Case File Creation

**User Story:** As a research analyst, I want to choose a search tier (Standard or Enterprise) when creating a case file, so that I can match the backend capabilities to the scale and complexity of my investigation.

#### Acceptance Criteria

1. WHEN a user creates a new Case_File, THE Research_Interface SHALL present a Search_Tier selector with two options: "Standard" (Aurora pgvector) and "Enterprise" (OpenSearch Serverless), defaulting to "Standard"
2. WHEN a Case_File creation request includes a Search_Tier value, THE Platform SHALL store the Search_Tier as an immutable attribute on the Case_File metadata record in Aurora
3. IF a Case_File creation request specifies an invalid Search_Tier value, THEN THE Platform SHALL return a validation error specifying the allowed values ("standard", "enterprise")
4. WHEN a Case_File has been created, THE Platform SHALL reject any request to change the Case_File's Search_Tier and return an error indicating the tier is immutable
5. THE Platform SHALL display the Search_Tier on the case file detail view and case file listing in the Research_Interface

### Requirement 3: Ingestion Pipeline Routing

**User Story:** As a research analyst, I want the ingestion pipeline to automatically route document indexing to the correct backend based on my case file's tier, so that I do not need to manage backend details during data ingestion.

#### Acceptance Criteria

1. WHEN the Ingestion_Pipeline processes documents for a Case_File, THE Ingestion_Pipeline SHALL resolve the SearchBackend via the Backend_Factory using the Case_File's Search_Tier
2. WHEN the Ingestion_Pipeline generates embeddings for a Standard tier Case_File, THE Ingestion_Pipeline SHALL store the embeddings in Aurora pgvector via the Aurora_Backend
3. WHEN the Ingestion_Pipeline generates embeddings for an Enterprise tier Case_File, THE Ingestion_Pipeline SHALL index the document text and embeddings into OpenSearch Serverless via the OpenSearch_Backend
4. WHEN the Ingestion_Pipeline indexes documents for an Enterprise tier Case_File, THE OpenSearch_Backend SHALL index both the full document text (for keyword search) and the vector embedding (for semantic search) in a single OpenSearch index scoped to the Case_File
5. IF the SearchBackend raises an indexing error during ingestion, THEN THE Ingestion_Pipeline SHALL log the error with the document identifier and backend type, and continue processing remaining documents

### Requirement 4: Enterprise Tier Search Capabilities

**User Story:** As a research analyst working on a large-scale enterprise case, I want access to full-text keyword search, hybrid search, and faceted filtering, so that I can efficiently find relevant information across millions of documents.

#### Acceptance Criteria

1. WHEN a user performs a search on an Enterprise tier Case_File, THE OpenSearch_Backend SHALL support full-text keyword search across all indexed document text with relevance ranking
2. WHEN a user performs a search on an Enterprise tier Case_File, THE OpenSearch_Backend SHALL support vector similarity search using the same SearchBackend interface as the Standard tier
3. WHEN a user enables hybrid search on an Enterprise tier Case_File, THE OpenSearch_Backend SHALL execute both keyword search and vector similarity search, merge the result sets, and return a unified ranked result list
4. WHEN a user applies Faceted_Filters on an Enterprise tier Case_File, THE OpenSearch_Backend SHALL narrow search results by the specified filter dimensions: date range, person name, document type, and entity type
5. WHEN a search is performed on an Enterprise tier Case_File, THE OpenSearch_Backend SHALL return results within 1 second for indexes containing up to 4 million documents
6. WHEN a user performs a search on a Standard tier Case_File, THE Aurora_Backend SHALL perform vector similarity search only, consistent with the existing behavior

### Requirement 5: OpenSearch Serverless Infrastructure

**User Story:** As a platform operator, I want OpenSearch Serverless to be provisioned by the CDK stack but only activated when needed, so that Enterprise tier capabilities are available without incurring costs for Standard-only deployments.

#### Acceptance Criteria

1. THE Platform CDK stack SHALL provision an OpenSearch Serverless collection configured for vector search with the necessary encryption, network, and data access policies
2. THE Platform CDK stack SHALL create IAM roles granting Lambda functions permission to index and search against the OpenSearch Serverless collection
3. WHEN no Enterprise tier Case_Files exist, THE OpenSearch Serverless collection SHALL incur minimal cost by having no active indexing compute units
4. WHEN an Enterprise tier Case_File is created and documents are ingested, THE OpenSearch Serverless collection SHALL automatically scale indexing and search compute to handle the workload
5. THE Platform CDK stack SHALL pass the OpenSearch Serverless collection endpoint and collection ID to Lambda functions via environment variables

### Requirement 6: Bedrock Knowledge Base Dual-Backend Integration

**User Story:** As a research analyst, I want Bedrock Knowledge Base semantic search to work regardless of which tier my case file uses, so that AI-assisted analysis is available for all investigations.

#### Acceptance Criteria

1. WHEN a Standard tier Case_File is used for semantic search, THE Platform SHALL route Bedrock Knowledge Base queries through the existing Aurora pgvector native integration
2. WHEN an Enterprise tier Case_File is used for semantic search, THE Platform SHALL route Bedrock Knowledge Base queries through Bedrock's OpenSearch Serverless connector
3. THE Platform SHALL configure separate Bedrock Knowledge Base data sources for each backend type so that retrieval operations are scoped to the correct vector store
4. WHEN a user performs AI-assisted analysis (entity analysis or pattern analysis) on any Case_File, THE Platform SHALL use the appropriate Bedrock Knowledge Base data source based on the Case_File's Search_Tier

### Requirement 7: Frontend Adaptive Search Interface

**User Story:** As a research analyst, I want the search interface to show me the capabilities available for my case file's tier, so that I can take advantage of Enterprise features when available without being confused by options that do not apply.

#### Acceptance Criteria

1. WHEN a user views the search page for a Standard tier Case_File, THE Research_Interface SHALL display the existing semantic search interface with no additional controls
2. WHEN a user views the search page for an Enterprise tier Case_File, THE Research_Interface SHALL display additional controls: a keyword search input, a hybrid search toggle, and faceted filter panels for date range, person, document type, and entity type
3. WHEN a user toggles hybrid search on an Enterprise tier Case_File, THE Research_Interface SHALL send both the semantic query and keyword query to the search API and display the merged results
4. WHEN a user applies faceted filters on an Enterprise tier Case_File, THE Research_Interface SHALL include the filter parameters in the search API request and update results accordingly
5. THE Research_Interface SHALL clearly indicate the active Search_Tier for the current Case_File so the analyst understands which capabilities are available

### Requirement 8: Backward Compatibility

**User Story:** As a research analyst with existing Standard tier case files, I want all my current investigations to continue working exactly as before, so that the multi-backend feature does not disrupt ongoing work.

#### Acceptance Criteria

1. THE Platform SHALL treat all existing Case_Files created before the multi-backend feature as Standard tier by defaulting the Search_Tier to "standard" when the attribute is absent
2. WHEN the Platform processes search or indexing operations for a Case_File with no explicit Search_Tier, THE Platform SHALL route all operations through the Aurora_Backend
3. THE Platform SHALL not require any data migration for existing Case_Files — all existing Aurora pgvector embeddings, documents, and metadata SHALL remain accessible without modification
4. WHEN the Aurora database schema is updated to include the search_tier column, THE Platform SHALL apply a default value of "standard" to all existing rows

### Requirement 9: Search API Extension

**User Story:** As a platform developer, I want the search API to support the new search modes and filter parameters, so that the frontend can access Enterprise tier capabilities through a consistent API.

#### Acceptance Criteria

1. THE Platform search API endpoint SHALL accept an optional "search_mode" parameter with values "semantic" (default), "keyword", or "hybrid"
2. THE Platform search API endpoint SHALL accept an optional "filters" parameter containing faceted filter criteria (date_from, date_to, person, document_type, entity_type)
3. WHEN the search API receives a "keyword" or "hybrid" search_mode for a Standard tier Case_File, THE Platform SHALL return an error indicating that the requested search mode is not available for the Standard tier
4. WHEN the search API receives a "filters" parameter for a Standard tier Case_File, THE Platform SHALL return an error indicating that faceted filtering is not available for the Standard tier
5. THE Platform search API response SHALL include a "search_tier" field and an "available_modes" field so the client can determine which capabilities are supported for the Case_File
