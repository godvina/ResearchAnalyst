# Requirements Document

## Introduction

This specification covers six targeted enhancements to the existing Pipeline Monitor Dashboard in the Research Analyst application (`src/frontend/investigator.html`). The dashboard currently renders pipeline step cards with an ops center header, but needs improvements to metrics display, interactivity, data accuracy, AI recommendations, and production planning. The backend pipeline status API (`GET /case-files/{id}/pipeline-status`) and `PipelineStatusService` already exist and return step-level metrics from S3, Aurora, Neptune, and OpenSearch Serverless.

## Glossary

- **Dashboard**: The Pipeline Monitor tab in `investigator.html` that displays pipeline health metrics and step cards
- **Ops_Center_Header**: The top 4-card summary row showing progress ring, throughput, error rate, and AI health
- **Step_Card**: A UI card representing one pipeline step (e.g., S3 Upload, Parsing, Extraction) with icon, metric, progress bar, and status dot
- **Detail_Overlay**: A modal/overlay panel that appears when a Step_Card is clicked, showing step-specific details
- **PipelineStatusService**: The Python backend service (`pipeline_status_service.py`) that aggregates metrics from S3, Aurora, Neptune, and OpenSearch
- **AOSS**: Amazon OpenSearch Serverless — the vector search backend
- **Throughput**: The rate of document processing, measured in documents per hour or documents per minute
- **Workload_Tier**: A classification of case size: Small (<100 docs), Medium (100–10K docs), Large (10K–100K docs), Enterprise (100K+ docs)
- **Production_Target**: A user-specified document count representing the intended production-scale workload
- **S3_Prefix**: The key prefix path in S3 under which case documents are stored (e.g., `cases/{id}/raw/`, `cases/{id}/documents/`, `epstein_files/`)
- **Index_Name**: The OpenSearch Serverless index name used to query vector counts for a case

## Requirements

### Requirement 1: Docs/Minute Metric in Ops Center Header

**User Story:** As an investigator, I want to see throughput in docs/minute alongside docs/hour in the ops center header, so that I can quickly gauge real-time processing speed at a human-readable scale.

#### Acceptance Criteria

1. THE Dashboard SHALL display a docs/minute metric in the Ops_Center_Header throughput card, computed as `throughput_per_hour / 60` rounded to one decimal place
2. THE Dashboard SHALL display both docs/hour and docs/minute values simultaneously in the throughput card
3. WHEN throughput_per_hour is 0, THE Dashboard SHALL display "0" for both docs/hour and docs/minute
4. THE PipelineStatusService SHALL include a `throughput_per_minute` field in the summary response, computed as `throughput_per_hour / 60` rounded to one decimal place

### Requirement 2: Step Card Click Detail Overlay

**User Story:** As an investigator, I want to click on a pipeline step card and see detailed information about that step, so that I can diagnose issues and understand step-specific performance.

#### Acceptance Criteria

1. WHEN a user clicks a Step_Card, THE Dashboard SHALL display a Detail_Overlay containing the step service name, primary metric value, current status, and step detail text
2. THE Detail_Overlay SHALL display an activity log section showing the step status (idle, running, completed, error) and the step percentage complete
3. THE Detail_Overlay SHALL display per-step AI recommendations based on the step status and metric values
4. WHEN a user clicks outside the Detail_Overlay or clicks a close button, THE Dashboard SHALL close the Detail_Overlay
5. THE Detail_Overlay SHALL use the existing `.monitor-overlay` and `.monitor-detail` CSS classes already defined in the stylesheet
6. WHEN the step status is "running", THE Detail_Overlay SHALL display the progress percentage and estimated time remaining for that step
7. WHEN the step status is "error", THE Detail_Overlay SHALL highlight the error state in red and suggest checking CloudWatch logs

### Requirement 3: Fix OpenSearch Vector Count Showing 0

**User Story:** As an investigator, I want the vector count to reflect the actual number of indexed vectors, so that I can trust the dashboard metrics.

#### Acceptance Criteria

1. THE PipelineStatusService SHALL query OpenSearch Serverless using multiple Index_Name formats when the primary format returns 0 or errors: `case_{id_with_underscores}`, `case-{id}`, and `{id}`
2. WHEN the primary Index_Name query fails or returns 0, THE PipelineStatusService SHALL attempt a `GET /_cat/indices` request to discover the actual index name containing the case identifier
3. THE PipelineStatusService SHALL return the vector count from the first Index_Name format that returns a non-zero count
4. IF all Index_Name formats fail, THEN THE PipelineStatusService SHALL return 0 for the vector count and include the attempted index names in the error details

### Requirement 4: Fix S3 Document Count Showing 0

**User Story:** As an investigator, I want the S3 document count to accurately reflect all uploaded files regardless of which prefix they are stored under, so that the progress percentage is correct.

#### Acceptance Criteria

1. THE PipelineStatusService SHALL check multiple S3_Prefix paths for case documents: `cases/{id}/raw/`, `cases/{id}/documents/`, and `epstein_files/`
2. THE PipelineStatusService SHALL aggregate object counts across all matching S3_Prefix paths to produce the total_objects count
3. WHEN the `cases/{id}/raw/` prefix returns 0 objects, THE PipelineStatusService SHALL check the alternative prefixes before reporting 0
4. THE PipelineStatusService SHALL return the list of prefixes that contained objects in the S3 stats response
5. WHEN counting objects under `epstein_files/`, THE PipelineStatusService SHALL use pagination with a reasonable page size to avoid API Gateway timeout (29 seconds)

### Requirement 5: Workload-Tier-Specific AI Recommendations

**User Story:** As an investigator, I want AI recommendations that are specific to my case's document volume, so that I receive actionable advice appropriate to my workload scale.

#### Acceptance Criteria

1. THE PipelineStatusService SHALL classify each case into a Workload_Tier based on total_source_files: Small (<100), Medium (100–10,000), Large (10,000–100,000), Enterprise (100,000+)
2. WHEN the Workload_Tier is Small, THE PipelineStatusService SHALL include a recommendation: "This is a test run. At production scale ({total_source_files} docs), serial processing is fine. Consider batch mode for larger datasets."
3. WHEN the Workload_Tier is Medium, THE PipelineStatusService SHALL include a recommendation: "Current serial processing is adequate. For faster results, enable Step Functions Map state with concurrency 5–10."
4. WHEN the Workload_Tier is Large, THE PipelineStatusService SHALL include a recommendation: "Enable Step Functions Map state with concurrency 10–50 for optimal throughput at this scale."
5. WHEN the Workload_Tier is Enterprise, THE PipelineStatusService SHALL include a recommendation: "Use SQS fan-out with 100+ concurrent Lambda workers. Consider EMR Spark for batch processing at this volume."
6. THE PipelineStatusService SHALL include the Workload_Tier label and document count range in the health assessment response
7. THE Dashboard SHALL display the Workload_Tier label in the AI Health card of the Ops_Center_Header

### Requirement 6: Production Target Projection

**User Story:** As an investigator, I want to specify a production target document count and see projected processing time, so that I can plan capacity and decide whether to enable parallel processing.

#### Acceptance Criteria

1. THE Dashboard SHALL display a "Production Target" input field in the Ops_Center_Header or below the step cards where the user can enter a target document count
2. WHEN the user enters a Production_Target and current throughput is greater than 0, THE Dashboard SHALL compute and display the projected processing time as: `Production_Target / throughput_per_hour` formatted in hours or days
3. THE Dashboard SHALL display a parallel-mode projection alongside the serial projection, using an estimated parallel throughput of `throughput_per_hour * 50` (representing 50x concurrency)
4. THE Dashboard SHALL format the projection as: "At current throughput, processing {target} docs would take {X} days. With parallel mode (50x): {Y} hours."
5. WHEN throughput_per_hour is 0, THE Dashboard SHALL display "No throughput data available — start processing to see projections" instead of a numeric projection
6. THE Dashboard SHALL update the projection in real-time as the user types in the Production_Target input field
