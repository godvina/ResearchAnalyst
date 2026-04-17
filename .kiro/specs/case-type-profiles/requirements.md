# Requirements Document

## Introduction

This feature adds case type pipeline profiles and a frontend ingestion trigger to the Research Analyst platform. Case type profiles provide curated Rekognition label sets, entity extraction focus areas, and AI analysis tuning per case type (e.g., Antitrust, Financial Fraud, Drug Trafficking). The frontend ingestion trigger adds a "Load Data" section to investigator.html for uploading files and triggering the existing Step Functions pipeline from the browser. Both capabilities extend existing systems without rewriting working code.

## Glossary

- **Case_Type_Profile**: A JSON configuration object that defines the Rekognition investigative labels, entity extraction focus areas, and AI analysis focus for a specific category of investigation (e.g., "antitrust", "financial_fraud", "drug_trafficking").
- **Investigative_Labels**: A set of Rekognition label strings used to filter which detected objects are promoted to graph entities during image/video analysis.
- **Effective_Config**: The merged pipeline configuration for a case, computed by deep-merging system defaults with case-level overrides via ConfigResolutionService.
- **Rekognition_Handler**: The Lambda function (rekognition_handler.py) that processes images and videos using Amazon Rekognition and converts detections to entities.
- **Entity_Extraction_Service**: The service (entity_extraction_service.py) that uses Bedrock LLM to extract entities and relationships from document text.
- **Config_Validation_Service**: The service (config_validation_service.py) that validates pipeline configuration JSON and holds CONFIG_TEMPLATES.
- **Pipeline_Config_Service**: The service (pipeline_config_service.py) that manages CRUD operations on per-case pipeline configs with versioning.
- **Case_Files_Dispatcher**: The Lambda mega-dispatcher (case_files.py) that routes all API requests under the case-files path.
- **Ingestion_Pipeline**: The existing Step Functions state machine that orchestrates document ingestion (config resolution, upload, parse, extract, embed, graph load).
- **Investigator_Frontend**: The main frontend HTML page (investigator.html) used by investigators to view and analyze cases.
- **S3_Prefix_Trigger**: A mechanism to start the Ingestion_Pipeline by pointing to an S3 prefix containing files already uploaded to the data lake bucket.

## Requirements

### Requirement 1: Case Type Profile Registry

**User Story:** As an investigator, I want to select a case type when configuring a case, so that the pipeline automatically uses labels, entity types, and analysis focus areas relevant to my investigation category.

#### Acceptance Criteria

1. THE Case_Type_Profile registry SHALL define profiles for at least the following case types: "child_sex_trafficking", "antitrust", "financial_fraud", "drug_trafficking", "public_corruption", "organized_crime", "cybercrime", "environmental_crime", "tax_evasion", "money_laundering".
2. WHEN a Case_Type_Profile is retrieved, THE registry SHALL return a JSON object containing three sections: "investigative_labels" (list of strings), "entity_focus" (list of entity type strings), and "analysis_focus" (list of focus area strings).
3. THE Case_Type_Profile registry SHALL be defined as a Python dictionary in the Config_Validation_Service module alongside the existing CONFIG_TEMPLATES dictionary.
4. WHEN a profile for an unknown case type is requested, THE registry SHALL return an empty profile with no investigative labels, entity focus, or analysis focus overrides.

### Requirement 2: Configurable Investigative Labels via Effective Config

**User Story:** As a platform operator, I want Rekognition label filtering to use case-type-specific labels from the effective config, so that each case type detects the objects most relevant to its investigation category.

#### Acceptance Criteria

1. WHEN the Rekognition_Handler processes images for a case, THE Rekognition_Handler SHALL check effective_config.rekognition.investigative_labels for a case-type-specific label set.
2. WHILE effective_config.rekognition.investigative_labels contains a non-empty list, THE Rekognition_Handler SHALL use that list as the label filter instead of the hardcoded INVESTIGATIVE_LABELS set.
3. WHILE effective_config.rekognition.investigative_labels is absent or empty, THE Rekognition_Handler SHALL fall back to the existing hardcoded INVESTIGATIVE_LABELS set.
4. THE Config_Validation_Service SHALL accept "investigative_labels" as a valid key within the "rekognition" config section.
5. WHEN "investigative_labels" is present in the rekognition config section, THE Config_Validation_Service SHALL validate that the value is a list of strings.

### Requirement 3: Case Type Application via Pipeline Config

**User Story:** As an investigator, I want to apply a case type profile to my case, so that the pipeline config is automatically populated with the correct labels, entity focus, and analysis settings.

#### Acceptance Criteria

1. WHEN a case type profile is applied to a case, THE Pipeline_Config_Service SHALL merge the profile's investigative_labels into the rekognition config section of the case's pipeline config.
2. WHEN a case type profile is applied to a case, THE Pipeline_Config_Service SHALL merge the profile's entity_focus into the extract config section as entity_types.
3. WHEN a case type profile is applied to a case, THE Pipeline_Config_Service SHALL store the applied case_type name in the case's pipeline config metadata.
4. THE Pipeline_Config_Service SHALL expose an apply_case_type_profile method that accepts a case_id and case_type string.
5. WHEN an unknown case_type is provided to apply_case_type_profile, THE Pipeline_Config_Service SHALL raise a ValueError with the list of available case types.

### Requirement 4: Case Type Profile API Endpoint

**User Story:** As a frontend developer, I want API endpoints to list available case types and apply a case type to a case, so that the investigator UI can present case type selection.

#### Acceptance Criteria

1. WHEN a GET request is made to the case type profiles list endpoint, THE Case_Files_Dispatcher SHALL return a JSON array of available case type names with their display labels.
2. WHEN a POST request is made to apply a case type profile to a case, THE Case_Files_Dispatcher SHALL invoke Pipeline_Config_Service.apply_case_type_profile and return the resulting effective config.
3. IF the POST request specifies an unknown case type, THEN THE Case_Files_Dispatcher SHALL return HTTP 400 with an error message listing available case types.
4. WHEN a GET request is made for a specific case's applied case type, THE Case_Files_Dispatcher SHALL return the currently applied case type name or null if none is applied.

### Requirement 5: Frontend File Upload via Existing Ingest API

**User Story:** As an investigator, I want to upload files from my browser into a case, so that I can add evidence without using command-line tools.

#### Acceptance Criteria

1. THE Investigator_Frontend SHALL display a "Load Data" section within the case detail view.
2. WHEN files are dropped onto the upload zone or selected via file picker, THE Investigator_Frontend SHALL send each file to the existing ingest API endpoint as a base64-encoded POST request.
3. WHILE files are uploading, THE Investigator_Frontend SHALL display a progress indicator showing the number of files uploaded out of the total.
4. IF a file upload fails, THEN THE Investigator_Frontend SHALL display the error message for that file and continue uploading remaining files.
5. WHEN all files in a batch have been uploaded, THE Investigator_Frontend SHALL display a summary showing successful and failed upload counts.

### Requirement 6: Frontend S3 Prefix Pipeline Trigger

**User Story:** As an investigator, I want to trigger the ingestion pipeline for files already in S3, so that I can process bulk data that was uploaded directly to the data lake bucket.

#### Acceptance Criteria

1. THE Investigator_Frontend SHALL display an S3 prefix input field within the "Load Data" section.
2. WHEN the user submits an S3 prefix, THE Investigator_Frontend SHALL send a POST request to a pipeline trigger API endpoint with the case_id and s3_prefix.
3. WHEN the pipeline trigger API receives a valid request, THE Case_Files_Dispatcher SHALL start a new Step Functions execution for the specified case and S3 prefix.
4. IF the S3 prefix is empty or missing, THEN THE Case_Files_Dispatcher SHALL return HTTP 400 with a descriptive error message.
5. WHEN a pipeline execution is started, THE Case_Files_Dispatcher SHALL return the Step Functions execution ARN to the frontend.

### Requirement 7: Frontend Ingestion Progress Display

**User Story:** As an investigator, I want to see the status of my pipeline executions, so that I know when ingestion is complete and whether it succeeded.

#### Acceptance Criteria

1. WHEN a pipeline execution has been triggered, THE Investigator_Frontend SHALL poll the pipeline status API endpoint at a regular interval.
2. THE Investigator_Frontend SHALL display the current execution status (RUNNING, SUCCEEDED, FAILED, TIMED_OUT, ABORTED) with a visual indicator.
3. WHEN the execution status changes to SUCCEEDED or FAILED, THE Investigator_Frontend SHALL stop polling and display the final status.
4. THE pipeline status API endpoint SHALL accept an execution ARN and return the current status by querying Step Functions describe_execution.
5. IF the execution ARN is invalid or the execution is not found, THEN THE pipeline status API endpoint SHALL return HTTP 404 with a descriptive error message.

### Requirement 8: Case Type Selection in Frontend

**User Story:** As an investigator, I want to select a case type from a dropdown when viewing a case, so that the pipeline is configured with the right detection profile before I load data.

#### Acceptance Criteria

1. THE Investigator_Frontend SHALL display a case type dropdown selector within the case detail view.
2. WHEN the page loads for a case, THE Investigator_Frontend SHALL fetch the list of available case types from the API and populate the dropdown.
3. WHEN the page loads for a case, THE Investigator_Frontend SHALL fetch the currently applied case type for the case and pre-select it in the dropdown.
4. WHEN the user selects a case type from the dropdown, THE Investigator_Frontend SHALL send a POST request to apply the selected case type profile to the case.
5. WHEN the case type is applied, THE Investigator_Frontend SHALL display a confirmation message showing the applied case type name.
