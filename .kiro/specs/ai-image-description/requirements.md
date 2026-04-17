# Requirements Document

## Introduction

This feature adds Bedrock Claude vision-based image description as a new pipeline step in the investigative intelligence platform. While Rekognition provides structured detections (faces, labels, text), Claude's vision API generates rich natural language descriptions of image content — describing scenes, relationships between people, contextual observations, and investigatively relevant details that structured detection cannot capture. For example, Claude can describe "Two individuals on a private yacht, one appears to be a minor" whereas Rekognition would only output labels like "Person", "Boat", "Water".

The feature runs as a new Step Functions state after the Rekognition step, reusing the same extracted images list. Descriptions are indexed in OpenSearch for full-text search, stored as properties on document nodes in Neptune, and surfaced in the investigator drill-down panel alongside Rekognition labels. A tiered triggering strategy controls cost by only describing images where Rekognition found investigatively relevant content (faces or investigative labels), with a per-case configuration toggle to override this behavior.

## Glossary

- **Ingestion_Pipeline**: The Step Functions orchestration (`ingestion_pipeline.json`) that processes uploaded evidence files through parsing, extraction, embedding, Rekognition, face cropping, and graph loading stages
- **Image_Description_Handler**: The new Lambda function that sends extracted images to Bedrock Claude's vision API and returns natural language descriptions for each image
- **Bedrock_Vision_API**: The Amazon Bedrock `invoke_model` API called with Claude's multimodal message format, accepting base64-encoded images alongside text prompts
- **Investigative_Prompt**: The system prompt sent to Claude alongside each image, instructing the model to describe people, settings, objects, activities, and investigatively relevant observations
- **Image_Description**: A natural language text string returned by Claude describing the visual content of a single image, typically 100-500 words
- **Rekognition_Result**: The output of the Rekognition_Handler containing faces, labels, text detections, and watchlist matches for all processed images in a case
- **Extracted_Image**: An image extracted from a PDF by PyMuPDF during the Parse step, stored at `cases/{case_id}/extracted-images/` in S3
- **Trigger_Filter**: The logic that determines which images are sent to Claude for description based on Rekognition detections (faces found, investigative labels detected, or explicit override)
- **Neptune_Graph**: The Amazon Neptune graph database storing entity vertices, document nodes, and relationship edges
- **OpenSearch_Index**: The search index (Aurora pgvector for standard tier, OpenSearch Serverless for enterprise) used for semantic and keyword search across document text
- **Drill_Down_Panel**: The right-side panel in `investigator.html` that shows entity details, related documents, images, and AI analysis when a graph node is clicked
- **Effective_Config**: The resolved pipeline configuration for a case, computed by merging the System_Default_Config with case-level overrides
- **Batch_Inference_API**: The Amazon Bedrock Batch Inference API that processes multiple inference requests asynchronously at 50% reduced cost compared to real-time invocation
- **Description_Artifact**: A JSON file stored in S3 containing all image descriptions for a pipeline run, at `cases/{case_id}/image-description-artifacts/`

## Requirements

### Requirement 1: Bedrock Claude Vision Image Description Lambda

**User Story:** As an investigator, I want extracted images automatically described by an AI vision model using investigative-focused prompts, so that I get rich natural language descriptions of visual evidence that go beyond structured label detection.

#### Acceptance Criteria

1. WHEN the Image_Description_Handler receives a list of image S3 keys, THE Image_Description_Handler SHALL download each image from S3, encode it as base64, and send it to the Bedrock_Vision_API using the Claude model specified in the Effective_Config
2. THE Image_Description_Handler SHALL use the Investigative_Prompt that instructs Claude to describe: number of people visible and their apparent age range, gender, and interactions; the setting or location; objects of investigative interest (weapons, drugs, currency, documents, electronics, vehicles, luxury items); activities being performed; and any observations that could be relevant to a criminal or trafficking investigation
3. THE Image_Description_Handler SHALL return an Image_Description of 100-500 words for each processed image, containing structured observations rather than speculative conclusions
4. THE Image_Description_Handler SHALL include the source S3 key, source document ID, and Rekognition context (detected labels and face count) alongside each Image_Description in the output
5. IF the Bedrock_Vision_API call fails for a specific image (timeout, throttling, content filter), THEN THE Image_Description_Handler SHALL log the error with the image S3 key and continue processing remaining images without failing the pipeline step
6. THE Image_Description_Handler SHALL use the Bedrock model ID from `effective_config.image_description.model_id`, defaulting to `anthropic.claude-3-haiku-20240307-v1:0`

### Requirement 2: Tiered Trigger Filter for Cost Control

**User Story:** As a platform operator, I want image descriptions to run only on images where Rekognition found investigatively relevant content by default, so that Claude vision API costs are controlled while still capturing high-value descriptions.

#### Acceptance Criteria

1. WHEN the Trigger_Filter evaluates an image for description, THE Trigger_Filter SHALL select the image if Rekognition detected one or more faces in that image
2. WHEN the Trigger_Filter evaluates an image for description, THE Trigger_Filter SHALL select the image if Rekognition detected one or more Investigative_Labels (from the existing 120+ label set in `rekognition_handler.py`) with confidence above the configured threshold
3. WHEN `effective_config.image_description.describe_all_images` is set to true, THE Trigger_Filter SHALL select all extracted images regardless of Rekognition detections
4. WHEN `effective_config.image_description.max_images_per_run` is set, THE Trigger_Filter SHALL limit the number of images sent to Claude to that maximum, prioritizing images with the most Rekognition detections (faces first, then investigative label count)
5. THE Image_Description_Handler SHALL log the trigger filter results: total images available, images selected for description, images skipped, and the selection reason for each selected image

### Requirement 3: Pipeline Configuration for Image Description

**User Story:** As a platform operator, I want image description behavior configurable per case through the existing pipeline configuration system, so that I can enable, disable, or tune the feature based on case needs and budget.

#### Acceptance Criteria

1. THE Effective_Config SHALL support an `image_description` section with parameters: `enabled` (boolean, default false), `model_id` (string, default `anthropic.claude-3-haiku-20240307-v1:0`), `describe_all_images` (boolean, default false), `max_images_per_run` (integer, default 50), `max_tokens_per_image` (integer, default 1024), and `min_rekognition_confidence` (float, default 0.7)
2. WHEN `effective_config.image_description.enabled` is false or absent, THE Ingestion_Pipeline SHALL skip the Image Description step entirely
3. WHEN the `image_description` section is not present in the Effective_Config, THE Ingestion_Pipeline SHALL treat image description as disabled and skip the step
4. THE Config_Validation_Service SHALL validate that `model_id` references a valid Bedrock Claude model identifier, `max_images_per_run` is a positive integer, `max_tokens_per_image` is between 256 and 4096, and `min_rekognition_confidence` is between 0.0 and 1.0

### Requirement 4: Step Functions Pipeline Integration

**User Story:** As a platform developer, I want the image description step wired into the Step Functions pipeline after Rekognition and face cropping, so that it runs automatically as part of every ingestion where it is enabled.

#### Acceptance Criteria

1. THE Ingestion_Pipeline SHALL include a `CheckImageDescriptionEnabled` Choice state after the `CheckFaceCropEnabled`/`FaceCropStep` path and before `ChooseGraphLoadStrategy`
2. THE `CheckImageDescriptionEnabled` state SHALL use an `IsPresent` guard followed by a `BooleanEquals` check on `$.effective_config.image_description.enabled`, consistent with the pattern used for `CheckRekognitionEnabled` and `CheckFaceCropEnabled` (per Lesson Learned #24)
3. WHEN image description is enabled, THE Ingestion_Pipeline SHALL execute an `ImageDescriptionStep` Task state that invokes the Image_Description_Handler Lambda with `case_id`, `rekognition_result`, and `effective_config`
4. IF the ImageDescriptionStep fails for any reason, THEN THE Ingestion_Pipeline SHALL catch the error, store it in `$.image_description_error`, and continue to `ChooseGraphLoadStrategy` without failing the pipeline
5. THE ImageDescriptionStep SHALL have a timeout of 900 seconds and retry up to 2 times on transient Lambda failures with exponential backoff

### Requirement 5: Store Descriptions in OpenSearch for Full-Text Search

**User Story:** As an investigator, I want AI image descriptions searchable alongside document text, so that I can find visual evidence by searching for scene descriptions like "yacht" or "minor" or "cash on table".

#### Acceptance Criteria

1. WHEN the Image_Description_Handler produces descriptions, THE Image_Description_Handler SHALL index each Image_Description as a searchable text document in the OpenSearch_Index, associated with the source case ID and source document ID
2. THE indexed Image_Description document SHALL include fields: `case_file_id`, `document_id`, `image_s3_key`, `description_text`, `source_type` (set to `"image_description"`), and `rekognition_labels` (the labels that triggered the description)
3. WHEN an investigator performs a semantic search, THE search results SHALL include matching Image_Descriptions alongside document text results, with the result indicating the source is an image description
4. THE Image_Description_Handler SHALL generate a vector embedding for each description text using the same embedding model configured for the case, enabling semantic similarity search across image descriptions

### Requirement 6: Link Descriptions to Neptune Graph

**User Story:** As an investigator, I want image descriptions linked to document nodes in the knowledge graph and entities mentioned in descriptions connected via edges, so that visual evidence is integrated into the investigation's entity network.

#### Acceptance Criteria

1. WHEN the Image_Description_Handler produces a description for an image, THE Graph_Loader SHALL store the Image_Description as a property (`image_description`) on the source document node in the Neptune_Graph
2. WHEN an Image_Description mentions entity names that match existing entities in the Neptune_Graph for that case, THE Graph_Loader SHALL create `DESCRIBED_IN_IMAGE` edges from those entity nodes to the source document node with the image S3 key as an edge property
3. THE Image_Description_Handler SHALL extract mentioned entity names from each description by comparing against the list of entities already extracted for the case (from the entity extraction step), using case-insensitive substring matching
4. WHEN multiple images from the same source document have descriptions, THE Graph_Loader SHALL concatenate the descriptions (separated by newlines) into a single `image_descriptions` property on the document node

### Requirement 7: Surface Descriptions in the Investigator Drill-Down Panel

**User Story:** As an investigator, I want to see AI image descriptions alongside Rekognition labels when viewing a document's images in the drill-down panel, so that I get both structured detections and narrative context for visual evidence.

#### Acceptance Criteria

1. WHEN an investigator views a document's images in the Drill_Down_Panel, THE Drill_Down_Panel SHALL display the Image_Description text below each image thumbnail alongside the Rekognition labels
2. WHEN an Image_Description is available for an image, THE Drill_Down_Panel SHALL display it in a collapsible text block labeled "AI Scene Description" with the Rekognition labels shown as tags above it
3. WHEN no Image_Description exists for an image (skipped by Trigger_Filter or feature disabled), THE Drill_Down_Panel SHALL display only the Rekognition labels without an empty description placeholder
4. THE Drill_Down_Panel SHALL fetch image descriptions from the document images API endpoint, which SHALL include the `description` field alongside the existing presigned URL and Rekognition label data

### Requirement 8: Description Artifact Storage

**User Story:** As a platform operator, I want all image descriptions stored as a JSON artifact in S3 for audit, debugging, and reprocessing, so that description results are preserved independently of the graph and search index.

#### Acceptance Criteria

1. THE Image_Description_Handler SHALL store all descriptions from a pipeline run as a single JSON artifact at `cases/{case_id}/image-description-artifacts/{run_id}_descriptions.json`
2. THE Description_Artifact SHALL contain for each described image: the image S3 key, source document ID, the full Image_Description text, the Rekognition context that triggered the description, the Claude model ID used, input token count, output token count, and processing duration in milliseconds
3. THE Description_Artifact SHALL include a summary section with: total images evaluated, images described, images skipped, total Bedrock API cost estimate (based on token counts and model pricing), and total processing duration
4. THE Image_Description_Handler SHALL return the artifact S3 key in its output so the pipeline state can reference it

### Requirement 9: Batch Inference Support for Bulk Processing

**User Story:** As a platform operator processing large cases with hundreds of images, I want the option to use Bedrock Batch Inference for image descriptions at 50% reduced cost, so that bulk processing is economically viable.

#### Acceptance Criteria

1. WHEN `effective_config.image_description.use_batch_inference` is set to true, THE Image_Description_Handler SHALL prepare a JSONL batch input file with all selected images and submit it to the Bedrock Batch_Inference_API instead of making individual real-time API calls
2. THE Image_Description_Handler SHALL store the batch input JSONL file at `cases/{case_id}/image-description-artifacts/{run_id}_batch_input.jsonl` in S3
3. WHEN using batch inference, THE Image_Description_Handler SHALL return a `batch_job_id` and status `"batch_submitted"` in its output, and a separate polling mechanism or callback SHALL collect results when the batch job completes
4. WHEN `effective_config.image_description.use_batch_inference` is false or absent, THE Image_Description_Handler SHALL use real-time `invoke_model` calls for each image (the default behavior)
5. IF the Batch_Inference_API submission fails, THEN THE Image_Description_Handler SHALL fall back to real-time invocation for the first `max_images_per_run` images and log a warning about the batch fallback

### Requirement 10: Investigative Prompt Design

**User Story:** As an investigator, I want the AI vision prompt specifically tuned for investigative analysis, so that descriptions focus on details relevant to criminal investigations rather than generic image captioning.

#### Acceptance Criteria

1. THE Investigative_Prompt SHALL instruct Claude to describe the following categories in order: (a) people — count, apparent age ranges, gender, physical descriptions, interactions between individuals, (b) setting — indoor/outdoor, type of location, identifiable landmarks or signage, (c) objects of interest — weapons, drugs, currency, documents, electronics, vehicles, luxury items, (d) activities — what people are doing, body language, (e) investigative observations — anything unusual, potentially illegal, or relevant to trafficking, financial crime, or organized crime investigations
2. THE Investigative_Prompt SHALL instruct Claude to report only observable facts and avoid speculative conclusions or legal judgments
3. THE Investigative_Prompt SHALL instruct Claude to note when individuals appear to be minors based on physical appearance
4. THE Investigative_Prompt SHALL be configurable via `effective_config.image_description.custom_prompt` to allow case-specific prompt overrides while providing the default Investigative_Prompt when no override is set
5. THE Investigative_Prompt SHALL include Rekognition context (detected labels and face count) as additional input to Claude, so the vision model can confirm or refine structured detections
