# Implementation Plan: AI Image Description

## Overview

Incrementally build the Bedrock Claude vision image description pipeline step. Start with the pure service functions and config validation, then the Lambda handler, then wire into Step Functions and the graph loader, then extend the API and frontend. Each task builds on the previous, ending with full integration.

## Tasks

- [x] 1. Create image description service with pure functions
  - [x] 1.1 Create `src/services/image_description_service.py` with `apply_trigger_filter(image_rek_map, config)` function
    - Accepts a dict mapping image S3 keys to `{face_count, labels_with_confidence}` and an `image_description` config dict
    - When `describe_all_images` is false: select images where `face_count >= 1` OR any label confidence >= `min_rekognition_confidence`
    - When `describe_all_images` is true: select all images
    - Sort selected by face_count desc, then investigative label count desc
    - Truncate to `max_images_per_run`
    - Return list of `{s3_key, face_count, labels, reason}` dicts
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 1.2 Add `build_investigative_prompt(rek_context, custom_prompt)` to the service
    - When `custom_prompt` is not None, return the custom prompt with Rekognition context appended
    - When `custom_prompt` is None, build the default investigative prompt with sections: (a) people, (b) setting, (c) objects of interest, (d) activities, (e) investigative observations
    - Include instruction to report only observable facts, note apparent minors, and avoid speculative conclusions
    - Embed the Rekognition face count and label list into the prompt text
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 1.3 Add `extract_mentioned_entities(description, entity_names)` to the service
    - Case-insensitive substring match: for each entity name in `entity_names`, check if it appears as a substring in the description (case-insensitive)
    - Return the list of matched entity names (original casing from `entity_names`)
    - _Requirements: 6.3_

  - [x] 1.4 Add `build_description_artifact(case_id, run_id, model_id, descriptions, images_evaluated, images_skipped)` to the service
    - Build the artifact dict with `descriptions` array and `summary` section
    - Summary: `images_evaluated`, `images_described` (len of descriptions), `images_skipped`, `total_input_tokens`, `total_output_tokens`, `estimated_cost_usd`, `total_duration_ms`
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 1.5 Add `parse_bedrock_response(response_body)` to the service
    - Extract description text from Claude's response JSON format (`content[0].text`)
    - Return empty string if content block is missing
    - _Requirements: 1.3_

  - [ ]* 1.6 Write property tests for image description service (`tests/unit/test_image_description_properties.py`)
    - **Property 1: Trigger filter selects images with faces or investigative labels**
    - **Validates: Requirements 2.1, 2.2**
    - **Property 2: Trigger filter describe_all override selects all images**
    - **Validates: Requirements 2.3**
    - **Property 3: Trigger filter respects max_images_per_run with priority ordering**
    - **Validates: Requirements 2.4**
    - **Property 9: Investigative prompt contains all required sections and context**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.5**
    - **Property 10: Custom prompt overrides default prompt**
    - **Validates: Requirements 10.4**
    - **Property 11: Entity mention extraction is case-insensitive substring match**
    - **Validates: Requirements 6.3**
    - **Property 13: Artifact summary totals are consistent with descriptions array**
    - **Validates: Requirements 8.3**
    - **Property 14: Artifact S3 key follows the required path pattern**
    - **Validates: Requirements 8.1**

  - [ ]* 1.7 Write unit tests for image description service (`tests/unit/test_image_description_service.py`)
    - Test empty image list → empty selection
    - Test single image with no faces and no labels → skipped (unless describe_all)
    - Test image with 5 faces and 3 labels → selected, correct priority score
    - Test Bedrock response parsing: valid response → extracted text; empty content → empty string
    - Test entity extraction: "John Doe" matches "john doe was seen"; "John" does NOT match entity "John Doe"
    - _Requirements: 1.3, 2.1, 2.2, 2.3, 6.3_

- [x] 2. Extend config validation for image_description section
  - [x] 2.1 Add `image_description` to `_VALID_SECTIONS` and add `_validate_image_description()` in `src/services/config_validation_service.py`
    - Add `"image_description"` to `_VALID_SECTIONS` set
    - Add `_IMAGE_DESCRIPTION_KEYS` set: `{"enabled", "model_id", "describe_all_images", "max_images_per_run", "max_tokens_per_image", "min_rekognition_confidence", "custom_prompt", "use_batch_inference"}`
    - Add to `_SECTION_KEYS` mapping
    - Validate: `model_id` must match `anthropic.claude-3-*` pattern, `max_images_per_run` must be int 1–500, `max_tokens_per_image` must be int 256–4096, `min_rekognition_confidence` must be float 0.0–1.0
    - Call `_validate_image_description()` from `validate()` method
    - _Requirements: 3.4_

  - [ ]* 2.2 Write property test for config validation
    - **Property 7: Config validation catches invalid image_description parameters**
    - **Validates: Requirements 3.4**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Create image description Lambda handler
  - [x] 4.1 Create `src/lambdas/ingestion/image_description_handler.py` with `handler(event, context)`
    - Read `effective_config.image_description` from event; if not enabled, return `{"status": "skipped"}`
    - Load Rekognition artifact from S3 using `rekognition_result.artifact_key`
    - Build image-to-Rekognition map from artifact results
    - Call `apply_trigger_filter()` to select images
    - Log trigger filter results: total available, selected, skipped, reasons
    - For each selected image: download from S3, base64 encode, call Bedrock `invoke_model` with investigative prompt
    - On per-image Bedrock failure (timeout, throttle, content filter): log error, skip image, continue
    - Extract entity mentions by loading case entities from extraction artifacts
    - Generate embedding for each description using configured embed model
    - Index each description in search backend with fields: `case_file_id`, `document_id`, `image_s3_key`, `text`, `source_type="image_description"`, `rekognition_labels`, `embedding`
    - Store description artifact JSON to `cases/{case_id}/image-description-artifacts/{run_id}_descriptions.json`
    - Return output with `case_id`, `status`, `descriptions`, `images_evaluated`, `images_described`, `images_skipped`, `artifact_key`
    - Use model_id from config, defaulting to `anthropic.claude-3-haiku-20240307-v1:0`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.5, 5.1, 5.2, 5.4, 8.1, 8.2, 8.3, 8.4_

  - [x] 4.2 Add batch inference support to the handler
    - When `use_batch_inference` is true: prepare JSONL batch input file, upload to S3 at `cases/{case_id}/image-description-artifacts/{run_id}_batch_input.jsonl`, submit to Bedrock Batch Inference API
    - Return `batch_job_id` and `status: "batch_submitted"`
    - On batch submission failure: fall back to real-time invocation for up to `max_images_per_run` images, log warning
    - When `use_batch_inference` is false or absent: use real-time `invoke_model` (default)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 4.3 Write property tests for handler behavior
    - **Property 4: Description output contains all required fields**
    - **Validates: Requirements 1.4, 5.2, 8.2**
    - **Property 5: Individual image failures do not fail the handler**
    - **Validates: Requirements 1.5**
    - **Property 6: Model ID defaults correctly from config**
    - **Validates: Requirements 1.6**
    - **Property 8: Disabled or absent config means step is skipped**
    - **Validates: Requirements 3.2, 3.3**
    - **Property 15: Each description is indexed with embedding in search backend**
    - **Validates: Requirements 5.1, 5.4**

- [x] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Wire into Step Functions pipeline and CDK stack
  - [x] 6.1 Add `CheckImageDescriptionEnabled` and `ImageDescriptionStep` states to `infra/step_functions/ingestion_pipeline.json`
    - Insert `CheckImageDescriptionEnabled` Choice state: change `FaceCropStep.Next` from `ChooseGraphLoadStrategy` to `CheckImageDescriptionEnabled`, and change `CheckFaceCropEnabled.Default` from `ChooseGraphLoadStrategy` to `CheckImageDescriptionEnabled`
    - Use `IsPresent` guard before `BooleanEquals` on `$.effective_config.image_description.enabled` (per Lesson Learned #24)
    - Default route → `ChooseGraphLoadStrategy`
    - Add `ImageDescriptionStep` Task state invoking `${ImageDescriptionLambdaArn}` with parameters: `case_id`, `rekognition_result`, `effective_config`
    - Set `TimeoutSeconds: 900`, retry up to 2 times on transient failures with exponential backoff
    - Catch all errors → store in `$.image_description_error`, continue to `ChooseGraphLoadStrategy`
    - `ImageDescriptionStep.Next` → `ChooseGraphLoadStrategy`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 6.2 Add `image_description` Lambda to CDK stack in `infra/cdk/stacks/research_analyst_stack.py`
    - Add `"image_description"` entry to `_create_ingestion_lambdas()` dict using `self._make_lambda("IngestionImageDescriptionLambda", "lambdas.ingestion.image_description_handler.handler", vpc, env, timeout_seconds=900, memory_mb=1024)`
    - Add `"ImageDescriptionLambdaArn": ingestion_lambdas["image_description"].function_arn` to `definition_substitutions` in `_create_state_machine()`
    - _Requirements: 4.1, 4.3_

- [x] 7. Extend graph loader to handle image descriptions
  - [x] 7.1 Modify `src/lambdas/ingestion/graph_load_handler.py` to process `image_description_result`
    - Read `image_description_result` from event (passed by Step Functions)
    - For each description, group by `source_document_id`
    - For documents with multiple descriptions, concatenate with `\n\n` separator
    - Set `image_descriptions` property on document nodes in Neptune (via Gremlin or bulk CSV)
    - Create `DESCRIBED_IN_IMAGE` edges from matched entity nodes to document nodes, with `image_s3_key` as edge property
    - Skip gracefully if `image_description_result` is absent or empty
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 7.2 Write property test for description concatenation
    - **Property 12: Multiple descriptions per document are concatenated**
    - **Validates: Requirements 6.4**

- [x] 8. Extend API to return image descriptions
  - [x] 8.1 Modify `document_images_handler` in `src/lambdas/api/case_files.py` to include `description` field
    - After building the images list, load the image description artifact from S3 (`cases/{case_id}/image-description-artifacts/`)
    - For each image in the response, look up its description from the artifact by matching `image_s3_key`
    - Add `description` field to each image dict (null if no description exists)
    - Add `rekognition_labels` field from the description artifact's `rekognition_context`
    - _Requirements: 7.4_

- [x] 9. Extend investigator drill-down panel for AI Scene Description
  - [x] 9.1 Modify `src/frontend/investigator.html` to display AI Scene Description in drill-down panel
    - In the document images rendering section, after each image thumbnail, check if `description` field is present
    - When present: render a collapsible block labeled "AI Scene Description" with the description text, and show Rekognition labels as tags above it
    - When absent: show only Rekognition labels without an empty placeholder
    - Use existing collapsible UI patterns from the drill-down panel
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The design uses Python throughout — all implementation tasks use Python
- DO NOT rewrite existing working code — EXTEND only (per lessons-learned.md)
- Lambda timeout should be 900s for VPC Lambdas
- Use `IsPresent` guard before `BooleanEquals` in SFN Choice states (Lesson Learned #24)
- Bedrock model default: `anthropic.claude-3-haiku-20240307-v1:0`
