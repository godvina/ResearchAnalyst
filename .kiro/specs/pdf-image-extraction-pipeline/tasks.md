# Implementation Plan: PDF Image Extraction Pipeline

## Overview

Extend the ingestion pipeline to extract embedded images from PDF documents during parsing, route them through Rekognition, and crop detected faces into thumbnails. All changes are additive — existing modules are extended, never replaced. Implementation language is Python throughout, matching the existing codebase.

## Tasks

- [x] 1. Extend S3 helper and document model for extracted images
  - [x] 1.1 Add `EXTRACTED_IMAGES` prefix type to `src/storage/s3_helper.py`
    - Add `EXTRACTED_IMAGES = "extracted-images"` to the `PrefixType` enum
    - All existing `build_key()`, `prefix_path()`, `upload_file()`, `download_file()`, `list_files()` functions work with the new prefix type without modification
    - _Requirements: 2.1, 2.2_

  - [x] 1.2 Add `extracted_images` field to `ParsedDocument` in `src/models/document.py`
    - Add `extracted_images: list[dict] = Field(default_factory=list)` to `ParsedDocument`
    - Add `image_extraction_summary: dict = Field(default_factory=dict)` to `ParsedDocument`
    - These are additive fields with defaults — existing code is unaffected
    - _Requirements: 2.4, 2.5, 7.1_

  - [ ]* 1.3 Write unit tests for new S3 prefix type in `tests/unit/test_s3_helper.py`
    - Test `PrefixType.EXTRACTED_IMAGES` works with `build_key()` and `prefix_path()`
    - Verify `build_key("case-1", "extracted-images", "doc_page0_img0.jpg")` produces `cases/case-1/extracted-images/doc_page0_img0.jpg`
    - _Requirements: 2.1, 2.2_

- [x] 2. Implement PdfImageExtractor service
  - [x] 2.1 Create `src/services/pdf_image_extractor.py`
    - Implement `PdfImageExtractor.__init__(self, s3_bucket: str)`
    - Implement `extract_images(self, pdf_bytes: bytes, case_id: str, document_id: str) -> dict` that iterates pages via PyMuPDF (fitz), extracts embedded images, skips images < 50x50, saves to S3 at `cases/{case_id}/extracted-images/{document_id}_page{page_num}_img{img_index}.{ext}`
    - Implement `_extract_page_images(self, doc, page_num, case_id, document_id)` for per-page extraction
    - Implement `_save_image_to_s3(self, image_bytes, s3_key, content_type)` with correct Content-Type headers (`image/jpeg` or `image/png`)
    - Save as JPEG for photographic content, PNG for images with alpha/transparency
    - Handle SMASK compositing onto white background before saving
    - Return `extracted_images` list and `image_extraction_summary` dict with counts: `total_pages_scanned`, `total_images_found`, `images_saved`, `images_skipped_too_small`, `extraction_errors`
    - On PyMuPDF failure: catch exception, log warning with document_id and error, return empty `extracted_images` list
    - On per-page failure: log error with document_id and page_num, increment `extraction_errors`, continue to next page
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 7.1, 7.4_

  - [ ]* 2.2 Write property test for extraction summary count invariants
    - **Property 1: PDF image extraction produces complete metadata with consistent summary counts**
    - Generate random lists of image metadata (varying dimensions, page numbers); verify `images_saved + images_skipped_too_small + extraction_errors == total_images_found`, each item in `extracted_images` has all required keys, and `extracted_images` is always a list
    - **Validates: Requirements 1.1, 1.4, 2.4, 2.5, 7.1**

  - [ ]* 2.3 Write property test for S3 key format and content type
    - **Property 2: Extracted image S3 key format and content type correctness**
    - Generate random case_ids, document_ids, page_nums, img_indexes, and formats; verify S3 key matches `cases/{case_id}/extracted-images/{document_id}_page{page_num}_img{img_index}.{ext}` and content type is correct
    - **Validates: Requirements 1.2, 2.1, 2.2, 2.3**

  - [ ]* 2.4 Write property test for small image filtering
    - **Property 3: Small image filtering by minimum dimension**
    - Generate random image dimensions (0–5000); verify images < 50x50 are excluded and >= 50x50 are included
    - **Validates: Requirements 1.3**

  - [ ]* 2.5 Write property test for document ID round-trip from filename
    - **Property 4: Source document ID round-trip from extracted image filename**
    - Generate random document_id strings (excluding `_page` substring); verify `parse_document_id(generate_filename(doc_id, page, idx, ext)) == doc_id`
    - **Validates: Requirements 3.4**

- [x] 3. Extend parse_handler for PDF image extraction
  - [x] 3.1 Add PDF image extraction code path to `src/lambdas/ingestion/parse_handler.py`
    - Add `_try_extract_pdf_images(raw_bytes, case_id, document_id, effective_config)` function
    - Check `effective_config.parse.extract_images` (default `true`) before extracting
    - When filename ends with `.pdf`, call `PdfImageExtractor.extract_images()` with the raw bytes
    - On any error in image extraction: log warning, fall back to text-only extraction
    - Add `extracted_images` (list) and `image_extraction_summary` (dict) to the handler return payload
    - For non-PDF files, return `extracted_images: []` and `image_extraction_summary: {}`
    - Preserve all existing text extraction logic untouched — the PDF image extraction runs as a separate step
    - Handle the case where the raw file is a PDF: attempt UTF-8 decode for text, and separately pass raw bytes to PdfImageExtractor
    - _Requirements: 1.1, 1.6, 1.7, 2.4, 2.5, 7.1_

  - [ ]* 3.2 Write unit tests for parse_handler PDF path
    - Test with a `.txt` file: verify `extracted_images` is `[]` and `image_extraction_summary` is `{}`
    - Test with a `.pdf` file: verify both text and images are extracted
    - Test with corrupt PDF: verify graceful fallback to text-only with empty `extracted_images`
    - Test with `extract_images: false` in config: verify image extraction is skipped
    - _Requirements: 1.6, 2.5_

- [x] 4. Checkpoint — Ensure PDF image extraction works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Extend Rekognition handler for extracted images
  - [x] 5.1 Add `_list_extracted_images()` to `src/lambdas/ingestion/rekognition_handler.py`
    - Implement `_list_extracted_images(s3_client, s3_bucket, case_id)` that lists files under `cases/{case_id}/extracted-images/` prefix
    - In `handler()`, call `_list_extracted_images()` and merge results with existing `_list_media_files()` output
    - Tag each result from an extracted image with `source_document_id` parsed from the filename (split on `_page`)
    - Add `extracted_image_count` field to the handler return payload
    - If an extracted image filename doesn't match the expected pattern, set `source_document_id` to `"unknown"` and log warning
    - If an extracted image is corrupt/unreadable by Rekognition, log warning and continue (existing per-image error handling)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 7.2_

  - [ ]* 5.2 Write property test for Rekognition extracted image discovery
    - **Property 5: Rekognition handler discovers all extracted images alongside uploaded media**
    - Generate random counts of uploaded media and extracted images; verify total processed equals sum and `extracted_image_count` is correct
    - **Validates: Requirements 3.1, 3.3, 7.2**

  - [ ]* 5.3 Write unit tests for source_document_id parsing
    - Test parsing `doc-123_page0_img0.jpg` → `source_document_id: "doc-123"`
    - Test parsing `doc_with_underscores_page2_img1.png` → `source_document_id: "doc_with_underscores"`
    - Test parsing malformed filename → `source_document_id: "unknown"`
    - _Requirements: 3.4_

- [x] 6. Implement FaceCropService
  - [x] 6.1 Create `src/services/face_crop_service.py`
    - Implement `FaceCropService.__init__(self, s3_bucket: str)`
    - Implement `crop_faces(self, case_id: str, rekognition_results: list[dict]) -> dict` that processes all face detections with confidence >= 0.90
    - Implement `_crop_single_face(self, image_bytes: bytes, bounding_box: dict, target_size=(100,100)) -> bytes` using Pillow — clamp bounding box coordinates that exceed image boundaries to the edge
    - Implement `_compute_crop_hash(self, s3_key: str, bounding_box: dict) -> str` using SHA-256 of `"{s3_key}:{Left}:{Top}:{Width}:{Height}"`, return first 12 hex chars
    - Store crops at `cases/{case_id}/face-crops/{entity_name}/{hash}.jpg`
    - Select highest-confidence crop per entity as `primary_thumbnail.jpg`
    - Accept JPEG, PNG, and TIFF input formats via Pillow
    - On source image download failure or corrupt image: log warning with S3 key, skip that crop, continue processing
    - Return `{"crops_created": int, "crops_from_extracted_images": int, "entities_with_thumbnails": list, "primary_thumbnails": dict, "errors": list}`
    - _Requirements: 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 6.2 Write property test for face crop output dimensions
    - **Property 6: Face crop output is valid 100x100 JPEG**
    - Generate random valid images (various sizes/formats) and random bounding boxes with values in [0,1]; verify output is valid 100x100 JPEG
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 6.3 Write property test for crop hash determinism
    - **Property 7: Face crop hash determinism and S3 path format**
    - Generate random S3 keys and bounding box dicts; verify same inputs → same 12-char hex hash, different inputs → different hashes
    - **Validates: Requirements 4.2, 5.3**

  - [ ]* 6.4 Write property test for primary thumbnail selection
    - **Property 8: Primary thumbnail is highest confidence crop**
    - Generate random lists of crops per entity with varying confidences; verify primary = max confidence
    - **Validates: Requirements 5.4**

- [x] 7. Implement FaceCropHandler Lambda and wire into Step Functions
  - [x] 7.1 Create `src/lambdas/ingestion/face_crop_handler.py`
    - Implement `handler(event, context)` that extracts `case_id`, `rekognition_result`, and `effective_config` from the Step Functions event
    - Check `effective_config.face_crop.enabled` (default `true`) before processing
    - Instantiate `FaceCropService` and call `crop_faces()`
    - Return `{"case_id": ..., "status": "completed"|"skipped", "crops_created": int, "crops_from_extracted_images": int, "primary_thumbnails": {...}}`
    - If no face detections in input, return `status: "skipped"`
    - _Requirements: 4.4, 6.2, 7.3_

  - [x] 7.2 Add FaceCropStep and CheckFaceCropEnabled states to `infra/step_functions/ingestion_pipeline.json`
    - Change `RekognitionStep.Next` from `"ChooseGraphLoadStrategy"` to `"CheckFaceCropEnabled"`
    - Add `CheckFaceCropEnabled` Choice state with `IsPresent` guard on `$.effective_config.face_crop` before checking `$.effective_config.face_crop.enabled` (per Lesson Learned #24)
    - Default to `ChooseGraphLoadStrategy` when face_crop config is missing
    - Add `FaceCropStep` Task state with `Resource: "${FaceCropLambdaArn}"`, passing `case_id`, `rekognition_result`, and `effective_config`
    - Set `ResultPath: "$.face_crop_result"`, `TimeoutSeconds: 300`
    - Add Retry: `["States.TaskFailed", "Lambda.ServiceException"]`, 2 max attempts, 3s interval, 2.0 backoff
    - Add Catch: `["States.ALL"]` → `ResultPath: "$.face_crop_error"` → `Next: "ChooseGraphLoadStrategy"` (non-blocking)
    - `FaceCropStep.Next` → `"ChooseGraphLoadStrategy"`
    - When Rekognition is disabled, both RekognitionStep and FaceCropStep are skipped (existing `CheckRekognitionEnabled` routes to `ChooseGraphLoadStrategy`)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 8. Checkpoint — Ensure FaceCropService and pipeline integration work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Pipeline observability and config extensions
  - [x] 9.1 Update system default config with new sections
    - Add `parse.extract_images: true` and `parse.min_image_dimension: 50` to the system default config schema
    - Add `face_crop.enabled: true`, `face_crop.min_face_confidence: 0.90`, `face_crop.thumbnail_size: 100`, `face_crop.thumbnail_format: "jpeg"` to the system default config schema
    - These are additive config keys — existing config resolution logic handles them automatically via deep merge
    - _Requirements: 1.3, 1.7, 5.1, 5.4_

  - [ ]* 9.2 Write unit tests for config-driven behavior
    - Test that `extract_images: false` in effective_config skips PDF image extraction
    - Test that `face_crop.enabled: false` skips face cropping
    - Test that `min_image_dimension: 100` changes the filtering threshold
    - _Requirements: 1.3, 1.7_

- [x] 10. Final checkpoint — Ensure all implemented tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All changes are additive — existing modules are extended, never replaced (per lessons-learned.md)
- The design uses Python throughout — no language selection needed
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Step Functions ASL changes use `IsPresent` guard before `BooleanEquals` per Lesson Learned #24
- FaceCropStep uses non-blocking Catch pattern — failures never block graph loading
