# Implementation Plan: Smart Image Triage & Face Pipeline

## Overview

Implement a four-stage batch pipeline (classify → detect faces → crop → match) that transforms the Evidence Library from 15,291 undifferentiated images into a focused, face-linked investigative tool. The pipeline scripts produce S3 artifacts consumed by an enhanced backend handler and a new frontend classification toggle UI with entity badges.

## Tasks

- [x] 1. Create the image classification script
  - [x] 1.1 Implement `scripts/classify_images.py` with CLI arguments and classification logic
    - Create `scripts/classify_images.py` with argparse for `--case-id`, `--target-case`, `--limit`, `--dry-run`
    - Implement `classify_image_metrics(entropy, color_variance, edge_density)` as a pure function applying priority rules: blank (entropy < 2.0), redacted_text (entropy < 4.0 AND color_variance < 20), document_page (color_variance < 30 AND edge_density > 0.3), photograph (default)
    - Implement metric computation: grayscale entropy via `Image.convert('L').entropy()`, color_variance via `np.std(np.array(Image.convert('L')))`, edge_density via `ImageFilter.FIND_EDGES` pixel ratio
    - Implement S3 listing of `cases/{case_id}/extracted-images/`, download each image, compute metrics, classify, and build the classification artifact JSON
    - Implement summary counts (total, photograph, document_page, redacted_text, blank, errors)
    - Implement resume support via local progress file `scripts/classify_images_progress.json`
    - Implement `--target-case` copy of artifact to combined case
    - Handle errors: log warning on download/analysis failure, increment error counter, continue
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 1.12, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [ ]* 1.2 Write property test for classification priority rules
    - **Property 1: Classification function assigns correct category by priority rules**
    - Use Hypothesis to generate random `(entropy, color_variance, edge_density)` tuples with `entropy ∈ [0, 10]`, `color_variance ∈ [0, 100]`, `edge_density ∈ [0, 1]`
    - Verify output matches expected priority: blank → redacted_text → document_page → photograph
    - **Validates: Requirements 1.3, 1.4, 1.5, 1.6, 1.7, 8.1, 8.2, 8.3, 8.4**

  - [ ]* 1.3 Write property test for classification summary consistency
    - **Property 3: Classification artifact summary counts are consistent**
    - Use Hypothesis to generate random lists of `(s3_key, classification)` pairs
    - Verify `sum(counts.values()) == len(classifications)` and each count matches actual frequency
    - **Validates: Requirements 1.8, 1.9**

- [x] 2. Create the face detection script
  - [x] 2.1 Implement `scripts/detect_faces.py` with classification-filtered face detection
    - Create `scripts/detect_faces.py` with argparse for `--case-id`, `--threshold`, `--limit`, `--dry-run`
    - Load `image_classification.json` from S3 and filter to `classification == "photograph"` entries only
    - For each photograph, call `rekognition.detect_faces(Attributes=['ALL'])` with 100ms rate limiting
    - Build `face_detection_results.json` with bounding boxes, confidence, gender, age_range per image
    - Build `face_crop_metadata.json` in the format consumed by existing `crop_faces.py` (source_s3_key, crop_s3_key, bounding_box, confidence, gender, age_range, source_document_id)
    - Upload both artifacts to `cases/{case_id}/rekognition-artifacts/`
    - Handle errors: log on Rekognition failure, increment error counter, continue; retry with backoff on throttle
    - Log summary: photographs processed, total faces detected, images skipped
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 9.2_

  - [ ]* 2.2 Write property test for photograph-only selection
    - **Property 6: Face detection selects only photograph-classified images**
    - Use Hypothesis to generate random classification artifacts with mixed categories
    - Verify selection function returns only entries where `classification == "photograph"`
    - **Validates: Requirements 4.1**

  - [ ]* 2.3 Write property test for face crop metadata format compatibility
    - **Property 7: Face crop metadata format is compatible with crop_faces.py**
    - Use Hypothesis to generate random face detection results
    - Verify each metadata entry contains all required fields with correct types and value ranges
    - **Validates: Requirements 4.3, 4.4**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Enhance the backend image_evidence_handler with classification filtering
  - [x] 4.1 Add classification loading and filtering to `image_evidence_handler` in `src/lambdas/api/case_files.py`
    - Load `image_classification.json` from S3 at `cases/{case_id}/rekognition-artifacts/image_classification.json`
    - Parse new `classification` query parameter (default: `photograph`; valid: `photograph`, `document_page`, `redacted_text`, `blank`, `all`)
    - Build a lookup dict from classification artifact: `s3_key → classification`
    - Add `classification` field to each image record
    - Filter images by classification (skip filter when `all`)
    - Add `classification_counts` to response summary: `{"photograph": N, "document_page": N, "redacted_text": N, "blank": N}`
    - When classification artifact is missing, return all images unfiltered (backward compatibility)
    - When invalid classification value is provided, default to `photograph`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 4.2 Add entity name merging from face_match_results.json into image records
    - Load `face_match_results.json` and build crop-to-entity+similarity lookup
    - For each image record with face data, resolve entity names and similarity scores into `matched_entities` list
    - Images with no matched faces get empty `matched_entities` list
    - _Requirements: 7.1_

  - [ ]* 4.3 Write property test for backend classification filtering
    - **Property 4: Backend classification filtering returns only matching images**
    - Use Hypothesis to generate random lists of classified image dicts and a random filter value
    - Apply filtering logic and verify all returned images match the filter (or all returned for "all")
    - Verify response summary contains correct `classification_counts`
    - **Validates: Requirements 2.1, 2.3, 2.4, 2.5, 2.6**

  - [ ]* 4.4 Write property test for entity name merging
    - **Property 11: Entity names are correctly merged into image records**
    - Use Hypothesis to generate random image records with face data and random match results
    - Apply merge logic and verify each image's `matched_entities` list is correct
    - **Validates: Requirements 7.1**

- [x] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement frontend classification toggle UI and entity badges
  - [x] 6.1 Add classification filter bar to Evidence Library in `src/frontend/investigator.html`
    - Insert a classification filter control above the existing label filter in the Evidence Library tab
    - Add buttons: "📷 Photos Only" (default active), "📄 Documents", "🔒 Redacted", "⬜ Blank", "All"
    - Each button displays the count from `summary.classification_counts`
    - Clicking a button sets `evidenceClassificationFilter` variable and re-fetches with `?classification=<value>`
    - Style with existing dark theme `.ev-filter-btn` pattern
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 6.2 Add entity name badges on image cards and detail modal
    - When `matched_entities` is non-empty on an image record, render entity name badges below label badges on the image card
    - Badge style: green background matching `.tag-person` pattern
    - In the Evidence Detail Modal's Graph Connection Panel, list each matched entity with crop thumbnail and similarity score
    - Display matched entities sorted by confidence descending
    - Display unidentified faces with "Unidentified" label and crop thumbnail
    - _Requirements: 7.2, 7.3, 7.4, 7.5_

  - [ ]* 6.3 Write property test for frontend classification filter URL construction
    - **Property 5: Frontend classification filter constructs correct API URL**
    - Use fast-check to generate random classification filter values from the valid set
    - Verify constructed URL contains `classification={value}` as query parameter
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.5**

  - [ ]* 6.4 Write property test for detail modal entity display ordering
    - **Property 12: Detail modal displays entities sorted by confidence with unidentified faces**
    - Use fast-check to generate random lists of matched and unmatched faces
    - Verify output is sorted by confidence descending with unidentified faces labeled correctly
    - **Validates: Requirements 7.2, 7.3, 7.4, 7.5**

- [x] 7. Wire pipeline artifacts end-to-end and add remaining property tests
  - [x] 7.1 Verify pipeline artifact dependency chain
    - Confirm `classify_images.py` output is consumed by `detect_faces.py`
    - Confirm `detect_faces.py` output (`face_crop_metadata.json`) is consumed by existing `crop_faces.py`
    - Confirm `crop_faces.py` output is consumed by existing `match_faces.py`
    - Confirm `match_faces.py` output (`face_match_results.json`) is consumed by enhanced `image_evidence_handler`
    - Ensure all scripts accept `--case-id` and default to main case
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 7.2 Write property test for face crop output dimensions
    - **Property 8: Face crop output is 200×200 JPEG with correct padding**
    - Use Hypothesis to generate random Pillow images (≥ 20×20) and random valid bounding boxes
    - Call `crop_face` and verify output is 200×200 JPEG bytes
    - **Validates: Requirements 5.1**

  - [ ]* 7.3 Write property test for face matcher highest-similarity selection
    - **Property 9: Face matcher selects highest similarity match above threshold**
    - Use Hypothesis to generate random lists of `(entity_name, similarity_score)` pairs and a random threshold
    - Verify selected match is the highest-scoring entity ≥ threshold (or None)
    - **Validates: Requirements 6.2**

  - [ ]* 7.4 Write property test for incremental matching skip logic
    - **Property 10: Incremental matching skips completed comparisons**
    - Use Hypothesis to generate random sets of completed `(crop, entity)` pairs and new pairs
    - Verify pairs to process equals `new_pairs - completed_pairs`
    - **Validates: Requirements 6.5**

  - [ ]* 7.5 Write property test for metric computation bounds
    - **Property 2: Metric computation produces correct values**
    - Use Hypothesis to generate random Pillow images
    - Verify entropy matches `Image.convert('L').entropy()`, color_variance matches `np.std(...)`, edge_density is in [0.0, 1.0]
    - **Validates: Requirements 1.2, 8.5, 8.6, 8.7**

- [x] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis (Python) and fast-check (JavaScript)
- Unit tests validate specific examples and edge cases
- Existing scripts (`crop_faces.py`, `match_faces.py`) require no changes — they already consume the artifact formats produced by the new scripts
- The `face_crop_service.py` service is separate from the batch scripts and is not modified
