# Requirements Document

## Introduction

The ISV Data Bridge is an API-first integration module that connects the Investigative Intelligence Platform to third-party legal and investigative software — eDiscovery tools (Relativity, Nuix), case management systems, and other ISV platforms — via their REST APIs. Rather than embedding ISV UIs via iframes, the Data Bridge pulls case metadata, document lists, and search results from ISV APIs and feeds them into the existing intelligence graph (Neptune) and document store (Aurora). Investigators see a unified view where ISV-sourced documents and entities appear alongside natively ingested evidence, with deep-links back to the originating tool for full document review. A setup wizard in the Admin tab allows users to configure ISV connections by providing API endpoints and credentials. Background sync keeps ISV data current. Each ISV gets a connector class implementing a common interface, with Phase 1 supporting Relativity (REST API v1), Nuix (REST API), and a generic REST connector for other tools.

## Glossary

- **Data_Bridge**: The backend Python module that orchestrates ISV API connections, data pulls, and ingestion into the platform's Neptune graph and Aurora document store.
- **ISV_Connector**: A Python class implementing the common connector interface (`list_cases`, `list_documents`, `search`, `get_document`) for a specific ISV product. Each supported ISV has its own connector class.
- **Connector_Interface**: The abstract base class defining the four standard methods all ISV_Connectors must implement: `list_cases()`, `list_documents(case_id)`, `search(query)`, and `get_document(document_id)`.
- **Connector_Registry**: The in-memory registry that maps ISV type identifiers (e.g., "relativity", "nuix", "generic_rest") to their corresponding ISV_Connector class.
- **ISV_Connection**: A configured instance of an ISV_Connector, consisting of an ISV type, API endpoint URL, encrypted credentials, and sync configuration, persisted in Aurora.
- **Connection_Store**: The Aurora database table that persists ISV_Connection records including encrypted credentials, sync status, and last sync timestamp.
- **Credential_Vault**: The encryption layer that encrypts ISV API credentials (API keys, OAuth tokens) using AWS KMS before storing them in the Connection_Store and decrypts them at runtime for API calls.
- **Setup_Wizard**: The multi-step UI in the Admin tab that guides users through selecting an ISV tool, providing API endpoint and credentials, testing the connection, and enabling sync.
- **Sync_Engine**: The background process (triggered via EventBridge scheduled rules) that periodically pulls updated data from each active ISV_Connection and feeds it into the ingestion pipeline.
- **Sync_Job**: A single execution of the Sync_Engine for one ISV_Connection, tracked with a job ID, status, and item counts.
- **Connected_Tools_Panel**: The sidebar UI panel showing all configured ISV_Connections with their sync status, last sync time, and item counts.
- **Deep_Link_Generator**: The utility that constructs URLs to open a specific document or case in the ISV's native web UI.
- **ISV_Document**: A document record pulled from an ISV API, containing ISV-native metadata (control number, custodian, date ranges) mapped to the platform's document model.
- **ISV_Entity**: An entity (person, organization, date, location) extracted from ISV_Document metadata and mapped into the Neptune graph.
- **Admin_UI**: The Admin tab in the frontend application at `src/frontend/admin.html`.
- **Investigator_UI**: The investigator frontend at `src/frontend/investigator.html`.
- **Bridge_API**: The set of REST API endpoints under `/v1/integrations/` that manage ISV_Connections and trigger sync operations.


## Requirements

### Requirement 1: Connector Interface and Registry

**User Story:** As a platform developer, I want a common interface for all ISV connectors, so that adding support for a new ISV tool requires only implementing a single class without modifying the core Data Bridge logic.

#### Acceptance Criteria

1. THE Connector_Interface SHALL define four abstract methods: `list_cases()` returning a list of case metadata objects, `list_documents(case_id: str)` returning a list of ISV_Document objects, `search(query: str, case_id: Optional[str])` returning a list of ISV_Document objects matching the query, and `get_document(document_id: str)` returning a single ISV_Document with full metadata.
2. THE Connector_Interface SHALL define a `test_connection()` method that validates the API endpoint is reachable and the provided credentials are accepted, returning a boolean success status and a descriptive message.
3. THE Connector_Registry SHALL map string ISV type identifiers to their ISV_Connector classes, supporting at minimum: "relativity", "nuix", and "generic_rest".
4. WHEN an ISV_Connector is instantiated, THE Data_Bridge SHALL pass the decrypted API endpoint URL and credentials from the Credential_Vault to the connector constructor.
5. IF an ISV API call fails with a retryable error (HTTP 429, 500, 502, 503), THEN THE ISV_Connector SHALL retry the call up to 3 times with exponential backoff starting at 2 seconds.
6. IF an ISV API call fails with a non-retryable error (HTTP 401, 403, 404), THEN THE ISV_Connector SHALL raise a typed exception containing the HTTP status code and ISV error message without retrying.
7. THE Connector_Interface SHALL define a `get_deep_link(document_id: str)` method that returns a URL string for opening the specified document in the ISV's native web UI.

### Requirement 2: Relativity Connector (Phase 1)

**User Story:** As an investigator using Relativity for eDiscovery, I want the platform to pull case metadata and document lists from my Relativity instance, so that I can see Relativity documents alongside other evidence in the intelligence graph.

#### Acceptance Criteria

1. THE Relativity ISV_Connector SHALL authenticate with the Relativity REST API v1 using either API key (X-CSRF header + username/password) or OAuth2 client credentials, as configured in the ISV_Connection.
2. WHEN `list_cases()` is called, THE Relativity ISV_Connector SHALL call the Relativity Workspace API (`/Relativity.REST/api/Relativity.Workspaces/`) and return workspace metadata mapped to case objects with fields: isv_case_id, case_name, created_date, and document_count.
3. WHEN `list_documents(case_id)` is called, THE Relativity ISV_Connector SHALL call the Relativity Document Query API for the specified workspace and return documents with fields: isv_document_id (control number), title, custodian, date_created, file_type, file_size_bytes, and extracted_text_preview (first 500 characters).
4. WHEN `search(query, case_id)` is called, THE Relativity ISV_Connector SHALL execute a dtSearch or keyword search against the specified workspace and return matching documents with hit highlights.
5. WHEN `get_deep_link(document_id)` is called, THE Relativity ISV_Connector SHALL return a URL in the format `https://{endpoint}/Relativity/Review.aspx?AppID={workspace_id}&ArtifactID={artifact_id}` that opens the document in the Relativity review interface.
6. THE Relativity ISV_Connector SHALL paginate API responses using Relativity's `start` and `length` parameters, fetching up to 1000 documents per page.
7. IF the Relativity API returns a 401 Unauthorized response, THEN THE Relativity ISV_Connector SHALL raise a credential error and update the ISV_Connection status to "auth_failed" in the Connection_Store.

### Requirement 3: Nuix Connector (Phase 1)

**User Story:** As an investigator using Nuix for eDiscovery processing, I want the platform to pull case and document data from my Nuix REST API, so that Nuix-processed evidence appears in my unified intelligence view.

#### Acceptance Criteria

1. THE Nuix ISV_Connector SHALL authenticate with the Nuix REST API using API key authentication via the `Authorization: Bearer {api_key}` header.
2. WHEN `list_cases()` is called, THE Nuix ISV_Connector SHALL call the Nuix Cases API and return case metadata mapped to case objects with fields: isv_case_id, case_name, created_date, and document_count.
3. WHEN `list_documents(case_id)` is called, THE Nuix ISV_Connector SHALL call the Nuix Items API for the specified case and return documents with fields: isv_document_id (GUID), title (item name), custodian, date_created, file_type (MIME type), file_size_bytes, and extracted_text_preview.
4. WHEN `search(query, case_id)` is called, THE Nuix ISV_Connector SHALL execute a Nuix query using the Nuix search syntax against the specified case and return matching items.
5. WHEN `get_deep_link(document_id)` is called, THE Nuix ISV_Connector SHALL return a URL that opens the item in the Nuix web review interface.
6. THE Nuix ISV_Connector SHALL handle Nuix API pagination using offset and limit parameters, fetching up to 500 items per page.

### Requirement 4: Generic REST Connector (Phase 1)

**User Story:** As an investigator using a tool not yet natively supported, I want to configure a generic REST connector with custom endpoint mappings, so that I can pull data from any ISV with a REST API.

#### Acceptance Criteria

1. THE Generic REST ISV_Connector SHALL accept a configuration object specifying: base URL, authentication type (api_key_header, bearer_token, basic_auth, or oauth2_client_credentials), and endpoint path templates for list_cases, list_documents, search, and get_document.
2. THE Generic REST ISV_Connector SHALL accept a field mapping configuration that maps ISV-specific JSON response fields to the standard ISV_Document fields (isv_document_id, title, custodian, date_created, file_type, file_size_bytes, extracted_text_preview).
3. WHEN any Connector_Interface method is called, THE Generic REST ISV_Connector SHALL substitute path parameters (e.g., `{case_id}`, `{document_id}`) into the configured endpoint templates and execute the HTTP request.
4. THE Generic REST ISV_Connector SHALL accept a deep_link_template string (e.g., `https://{base_url}/view/{document_id}`) and use it to generate deep links by substituting the document ID.
5. IF the ISV API response structure does not match the configured field mappings, THEN THE Generic REST ISV_Connector SHALL log a warning with the unexpected response structure and return a partial ISV_Document with available fields populated and missing fields set to null.


### Requirement 5: Credential Storage and Encryption

**User Story:** As a platform administrator, I want ISV API credentials stored encrypted at rest using KMS, so that sensitive authentication tokens are protected even if the database is compromised.

#### Acceptance Criteria

1. WHEN an ISV_Connection is created or updated with new credentials, THE Credential_Vault SHALL encrypt the credentials using AWS KMS with a dedicated CMK before writing them to the Connection_Store in Aurora.
2. WHEN an ISV_Connector needs credentials for an API call, THE Credential_Vault SHALL decrypt the credentials from the Connection_Store using the KMS CMK and pass them to the connector.
3. THE Connection_Store SHALL store credentials in a `credentials_encrypted` BYTEA column, with the KMS key ARN stored in a separate `kms_key_arn` VARCHAR column.
4. THE Credential_Vault SHALL cache decrypted credentials in memory for the duration of a single Lambda invocation to avoid repeated KMS decrypt calls within the same request.
5. IF a KMS decrypt call fails, THEN THE Credential_Vault SHALL raise a credential error, log the KMS error code, and update the ISV_Connection status to "credential_error" in the Connection_Store.
6. THE Connection_Store SHALL store the credential type (api_key, oauth2_client_credentials, basic_auth, bearer_token) in a `credential_type` VARCHAR column so the Credential_Vault knows the expected credential structure after decryption.

### Requirement 6: Setup Wizard

**User Story:** As a platform administrator, I want a step-by-step wizard to configure ISV connections, so that I can set up integrations without editing configuration files or running scripts.

#### Acceptance Criteria

1. WHEN the administrator opens the Integrations section of the Admin_UI, THE Setup_Wizard SHALL display a list of supported ISV tools (Relativity, Nuix, Generic REST) with icons and descriptions.
2. WHEN the administrator selects an ISV tool, THE Setup_Wizard SHALL display a form requesting: a display name for the connection, the API endpoint URL, and credential fields appropriate to the ISV (API key fields for Relativity, bearer token for Nuix, configurable auth type for Generic REST).
3. WHEN the administrator clicks "Test Connection", THE Setup_Wizard SHALL call the Bridge_API test endpoint which invokes the ISV_Connector's `test_connection()` method and display the result (success with ISV version info, or failure with error details).
4. WHEN the connection test succeeds and the administrator clicks "Save & Enable", THE Setup_Wizard SHALL create the ISV_Connection via the Bridge_API, encrypt and store credentials, and trigger an initial sync.
5. IF the connection test fails, THEN THE Setup_Wizard SHALL display the error message from the ISV_Connector and keep the form editable for correction without clearing previously entered fields.
6. THE Setup_Wizard SHALL validate the API endpoint URL format (must be a valid HTTPS URL) before allowing the test connection step.
7. WHEN the administrator configures a Generic REST connector, THE Setup_Wizard SHALL display additional fields for endpoint path templates and field mappings with example placeholders.

### Requirement 7: Background Sync Engine

**User Story:** As an investigator, I want ISV data to stay current without manual intervention, so that newly added documents in Relativity or Nuix automatically appear in my intelligence view.

#### Acceptance Criteria

1. THE Sync_Engine SHALL be triggered by an EventBridge scheduled rule at a configurable interval (default: every 6 hours) for each active ISV_Connection.
2. WHEN a Sync_Job runs, THE Sync_Engine SHALL call `list_documents(case_id)` on the ISV_Connector for each mapped case and compare the returned document list against previously synced documents in Aurora to identify new and updated documents.
3. WHEN new ISV_Documents are identified, THE Sync_Engine SHALL create document records in the Aurora documents table with source_type set to "isv", isv_connection_id referencing the ISV_Connection, and isv_document_id storing the ISV-native identifier.
4. WHEN new ISV_Documents are identified, THE Sync_Engine SHALL extract entities from ISV document metadata (custodian as person entity, date fields as date entities, file type as metadata) and load them into the Neptune graph with an edge linking each entity to the ISV_Document node.
5. WHEN a Sync_Job completes, THE Sync_Engine SHALL update the ISV_Connection record in the Connection_Store with: last_sync_at timestamp, last_sync_status (success, partial, failed), documents_synced count, and documents_new count.
6. IF a Sync_Job encounters more than 50% failures on individual document fetches, THEN THE Sync_Engine SHALL abort the sync, set the ISV_Connection status to "sync_error", and log the failure count and sample error messages.
7. THE Sync_Engine SHALL track sync state using a `last_sync_cursor` field on the ISV_Connection record, storing the ISV-specific pagination token or timestamp to enable incremental syncs.
8. WHEN the investigator triggers a manual sync via the Connected_Tools_Panel, THE Bridge_API SHALL invoke the Sync_Engine for the specified ISV_Connection immediately, bypassing the scheduled interval.

### Requirement 8: ISV Data Ingestion into Graph and Document Store

**User Story:** As an investigator, I want ISV-sourced documents and entities to appear in the same intelligence graph as natively ingested evidence, so that I get a unified view of all case intelligence regardless of source.

#### Acceptance Criteria

1. WHEN ISV_Documents are synced, THE Data_Bridge SHALL create document records in the Aurora documents table with the following ISV-specific fields: isv_connection_id (UUID), isv_document_id (VARCHAR), isv_source_type (VARCHAR — "relativity", "nuix", "generic_rest"), and deep_link_url (VARCHAR).
2. WHEN ISV_Documents are synced, THE Data_Bridge SHALL create entity nodes in Neptune with label `Entity_{case_id}` for each entity extracted from ISV metadata, with an additional property `source_type` set to "isv" and `isv_connection_id` set to the connection UUID.
3. WHEN ISV entities match existing entities in the Neptune graph (same canonical_name and entity_type within the same case), THE Data_Bridge SHALL merge the ISV entity with the existing entity by incrementing the occurrence_count and adding ISV document references rather than creating duplicate nodes.
4. THE Data_Bridge SHALL create `SOURCED_FROM` edges in Neptune linking ISV_Document nodes to their originating ISV_Connection node, enabling queries like "show all documents from Relativity".
5. WHEN an ISV_Document includes extracted text (from the ISV's own text extraction), THE Data_Bridge SHALL generate an embedding via Bedrock Titan Embed and store it in the Aurora documents table for semantic search.
6. IF an ISV_Document does not include extracted text, THEN THE Data_Bridge SHALL store the document metadata without an embedding and set the embedding column to null.

### Requirement 9: Unified View with ISV Document Counts

**User Story:** As an investigator, I want to see how many ISV-sourced documents match each entity, so that I understand the full evidence picture across all connected tools.

#### Acceptance Criteria

1. WHEN the Entity Dossier panel displays an entity, THE Investigator_UI SHALL show ISV document counts grouped by source tool (e.g., "12 documents in Relativity", "3 documents in Nuix") alongside the native document count.
2. WHEN the investigator clicks on an ISV document count, THE Investigator_UI SHALL expand a list of ISV_Documents showing: title, custodian, date, file type, and an "Open in [Tool Name]" button.
3. WHEN the investigator clicks "Open in [Tool Name]", THE Investigator_UI SHALL open the Deep_Link_Generator URL in a new browser tab, navigating directly to the document in the ISV's native review interface.
4. WHEN semantic search results include ISV-sourced documents, THE Investigator_UI SHALL display them with an ISV source badge (tool icon and name) and the "Open in [Tool Name]" deep-link button.
5. THE Investigator_UI SHALL display ISV-sourced documents with a distinct visual indicator (colored border or badge) to differentiate them from natively ingested documents.


### Requirement 10: Connected Tools Panel

**User Story:** As an investigator, I want a sidebar panel showing all connected ISV tools with their sync status, so that I can monitor integration health at a glance.

#### Acceptance Criteria

1. THE Connected_Tools_Panel SHALL be displayed in the Investigator_UI sidebar showing each configured ISV_Connection as a card with: tool icon, display name, connection status (connected, syncing, auth_failed, sync_error, disabled), last sync timestamp, and document count.
2. WHEN an ISV_Connection status is "connected" and the last sync completed successfully, THE Connected_Tools_Panel SHALL display a green status indicator.
3. WHEN an ISV_Connection status is "syncing", THE Connected_Tools_Panel SHALL display a spinning indicator and the sync progress (documents processed / total).
4. WHEN an ISV_Connection status is "auth_failed" or "sync_error", THE Connected_Tools_Panel SHALL display a red status indicator with the error summary and a "Reconfigure" button that opens the Setup_Wizard for that connection.
5. WHEN the investigator clicks "Sync Now" on a Connected_Tools_Panel card, THE Investigator_UI SHALL trigger a manual sync via the Bridge_API and update the card status to "syncing".
6. THE Connected_Tools_Panel SHALL refresh connection statuses every 30 seconds while visible.

### Requirement 11: Bridge API Endpoints

**User Story:** As a platform developer, I want a complete REST API for managing ISV connections and triggering syncs, so that the Admin UI and Investigator UI can interact with the Data Bridge without direct database access.

#### Acceptance Criteria

1. WHEN a POST request is sent to `/v1/integrations/connections`, THE Bridge_API SHALL create a new ISV_Connection, encrypt and store credentials via the Credential_Vault, and return the connection ID.
2. WHEN a GET request is sent to `/v1/integrations/connections`, THE Bridge_API SHALL return all ISV_Connections for the current organization with status, last sync time, and document counts (credentials excluded from response).
3. WHEN a GET request is sent to `/v1/integrations/connections/{connection_id}`, THE Bridge_API SHALL return the full ISV_Connection details including sync history (credentials excluded from response).
4. WHEN a PUT request is sent to `/v1/integrations/connections/{connection_id}`, THE Bridge_API SHALL update the ISV_Connection configuration and re-encrypt credentials if changed.
5. WHEN a DELETE request is sent to `/v1/integrations/connections/{connection_id}`, THE Bridge_API SHALL soft-delete the ISV_Connection by setting status to "disabled" and retain synced documents in Aurora and Neptune.
6. WHEN a POST request is sent to `/v1/integrations/connections/{connection_id}/test`, THE Bridge_API SHALL invoke the ISV_Connector's `test_connection()` method and return the result.
7. WHEN a POST request is sent to `/v1/integrations/connections/{connection_id}/sync`, THE Bridge_API SHALL trigger an immediate Sync_Job for the specified connection and return the sync job ID.
8. WHEN a GET request is sent to `/v1/integrations/connections/{connection_id}/sync/history`, THE Bridge_API SHALL return the list of Sync_Jobs for the connection, sorted by start time descending, limited to the most recent 20 jobs.
9. THE Bridge_API SHALL return HTTP 404 with a descriptive error message when a connection_id does not exist.
10. THE Bridge_API SHALL exclude encrypted credentials from all GET responses, returning only the credential_type and a masked indicator (e.g., "api_key: ****last4chars").

### Requirement 12: ISV Connection Database Schema

**User Story:** As a platform developer, I want a well-defined database schema for ISV connections, so that connection state, credentials, and sync history are persisted reliably.

#### Acceptance Criteria

1. THE Connection_Store SHALL define an `isv_connections` table with columns: connection_id (UUID PRIMARY KEY), organization_id (UUID), isv_type (VARCHAR — "relativity", "nuix", "generic_rest"), display_name (VARCHAR), api_endpoint_url (VARCHAR), credential_type (VARCHAR), credentials_encrypted (BYTEA), kms_key_arn (VARCHAR), config_json (JSONB — for generic REST field mappings and endpoint templates), status (VARCHAR — "connected", "syncing", "auth_failed", "sync_error", "disabled"), last_sync_at (TIMESTAMP), last_sync_status (VARCHAR), last_sync_cursor (VARCHAR), documents_synced (INTEGER DEFAULT 0), created_at (TIMESTAMP), updated_at (TIMESTAMP).
2. THE Connection_Store SHALL define an `isv_sync_jobs` table with columns: sync_job_id (UUID PRIMARY KEY), connection_id (UUID REFERENCES isv_connections), started_at (TIMESTAMP), completed_at (TIMESTAMP), status (VARCHAR — "running", "completed", "partial", "failed"), documents_fetched (INTEGER), documents_new (INTEGER), documents_updated (INTEGER), errors (JSONB), error_count (INTEGER DEFAULT 0).
3. THE Aurora documents table SHALL be extended with nullable columns: isv_connection_id (UUID REFERENCES isv_connections), isv_document_id (VARCHAR), isv_source_type (VARCHAR), deep_link_url (VARCHAR).
4. THE Connection_Store SHALL define a unique constraint on (isv_type, api_endpoint_url, organization_id) to prevent duplicate connections to the same ISV instance.

### Requirement 13: Connector Serialization Round-Trip

**User Story:** As a platform developer, I want ISV connector configurations to serialize and deserialize correctly, so that connector state is preserved across Lambda invocations and sync jobs.

#### Acceptance Criteria

1. THE ISV_Connection configuration (isv_type, api_endpoint_url, credential_type, config_json) SHALL serialize to JSON for storage and deserialize back to an equivalent ISV_Connection object.
2. FOR ALL valid ISV_Connection configurations, serializing to JSON then deserializing SHALL produce an ISV_Connection object with identical isv_type, api_endpoint_url, credential_type, and config_json values (round-trip property).
3. THE Generic REST connector's field mapping configuration SHALL serialize to JSON and deserialize back to an equivalent field mapping object that produces identical document transformations when applied to the same ISV API response.
4. IF a serialized ISV_Connection JSON contains an unrecognized isv_type, THEN THE Data_Bridge SHALL raise a descriptive error identifying the unknown type rather than silently creating a misconfigured connector.

### Requirement 14: Error Handling and Connection Health

**User Story:** As a platform administrator, I want clear visibility into ISV connection health and errors, so that I can quickly diagnose and fix integration issues.

#### Acceptance Criteria

1. WHEN an ISV_Connector encounters an authentication failure (HTTP 401 or 403), THE Data_Bridge SHALL update the ISV_Connection status to "auth_failed" and record the error timestamp and message in the Connection_Store.
2. WHEN an ISV_Connector encounters a connectivity failure (DNS resolution failure, TCP timeout, or TLS error), THE Data_Bridge SHALL update the ISV_Connection status to "sync_error" and record the error details.
3. WHEN the Sync_Engine completes a Sync_Job with errors, THE Data_Bridge SHALL store the error details in the isv_sync_jobs.errors JSONB column as an array of objects with fields: document_id, error_type, error_message, and timestamp.
4. WHEN the administrator views an ISV_Connection with status "auth_failed" or "sync_error" in the Admin_UI, THE Setup_Wizard SHALL display the most recent error message and a "Re-test Connection" button.
5. THE Bridge_API SHALL include a `GET /v1/integrations/health` endpoint that returns the status of all ISV_Connections with a summary: total connections, healthy count, error count, and last successful sync timestamp per connection.
