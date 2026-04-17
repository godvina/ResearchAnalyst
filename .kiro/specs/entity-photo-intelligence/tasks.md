# Implementation Plan: Entity Photo Intelligence

## Overview

Extend existing ingestion pipeline and API services to persist face-crop graph edges in Neptune, enrich the entity-photos API with source/count metadata, add a document-images endpoint, and update the investigator drill-down UI to display face crop thumbnails and document image galleries. No new Lambdas or CDK changes — all work extends existing files.

## Tasks

- [x] 1. Extend Rekognition Handler to emit face_crop_metadata
  - [x] 1.1 Add face_crop_metadata construction in `rekognition_handler.py`
    - After `FaceCropService.crop_faces()` returns, build a `face_crop_metadata` list from the crop results
    - Each entry: `crop_s3_key`, `source_s3_key`, `source_document_id` (via `_parse_source_document_id`), `bounding_box`, `confidence`, `entity_name`
    - Include `face_crop_metadata` in the handler return value alongside `entities`
    - _Requirements: 1.2_

  - [ ]* 1.2 Write property test for face_crop_metadata completeness
    - **Property 2: face_crop_metadata output completeness**
    - Generate random Rekognition results with varying numbers of faces and watchlist matches
    - Verify every entry in the output metadata has all required fields
    - **Validates: Requirements 1.2**

- [x] 2. Extend Graph Load Handler for face crop nodes and edges
  - [x] 2.1 Add `_load_face_crop_metadata()` function in `graph_load_handler.py`
    - Read `face_crop_metadata` from the event
    - Generate FaceCrop node CSV rows with label `FaceCrop_{case_id}` and properties: `crop_s3_key`, `source_document_id`, `confidence`, `case_file_id`, `entity_name`
    - Generate `FACE_DETECTED_IN` edge rows from FaceCrop → Document node when `source_document_id != "unknown"`
    - Log warning when `source_document_id == "unknown"` and skip edge creation
    - Wire into `_generate_and_upload_csv()` and Gremlin fallback paths
    - _Requirements: 1.1, 1.3_

  - [x] 2.2 Add HAS_FACE_CANDIDATE and HAS_FACE_MATCH edge generation
    - For each document with face crops, find person entities extracted from that same document
    - Create `HAS_FACE_CANDIDATE` edges (person → FaceCrop) with `association_source: "document_co_occurrence"`
    - Create `HAS_FACE_MATCH` edges from watchlist match data with `association_source: "watchlist_match"` and `similarity` score
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 2.3 Write property test for FACE_DETECTED_IN edge creation
    - **Property 1: FACE_DETECTED_IN edge creation for valid document IDs**
    - Generate random face_crop_metadata lists with mix of valid and "unknown" document IDs
    - Verify edge CSV output contains FACE_DETECTED_IN rows only for valid doc IDs
    - **Validates: Requirements 1.1, 1.3**

  - [ ]* 2.4 Write property test for HAS_FACE_CANDIDATE edges
    - **Property 3: HAS_FACE_CANDIDATE edges from document co-occurrence**
    - Generate random sets of person entities and face crops sharing document IDs
    - Verify HAS_FACE_CANDIDATE edges are created for every (person, face_crop) pair sharing a document
    - **Validates: Requirements 2.1, 2.3**

  - [ ]* 2.5 Write property test for HAS_FACE_MATCH edges
    - **Property 4: HAS_FACE_MATCH edges from watchlist matches**
    - Generate random watchlist match results
    - Verify HAS_FACE_MATCH edges are created with correct similarity scores and association_source
    - **Validates: Requirements 2.2, 2.3**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Extend Entity Photo Service with source and face_crop_count metadata
  - [x] 4.1 Update `get_entity_photos()` in `entity_photo_service.py`
    - Add `entity_metadata` dict to response with `source` ("pipeline" or "demo") and `face_crop_count` per entity
    - Add `_count_entity_crops(case_id, entity_name)` method that lists files under `face-crops/{entity_name}/` excluding `primary_thumbnail.jpg`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 4.2 Write property test for photo source priority
    - **Property 5: Photo source priority**
    - Generate random combinations of pipeline and demo photo S3 listings
    - Verify pipeline always wins when both exist, demo is used as fallback, source field is always correct
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 4.3 Write property test for face crop count accuracy
    - **Property 6: Face crop count accuracy**
    - Generate random S3 listings with varying numbers of crop files per entity
    - Verify face_crop_count matches actual file count excluding primary_thumbnail.jpg
    - **Validates: Requirements 3.4**

- [x] 5. Add document images endpoint
  - [x] 5.1 Add `document_images_handler()` in `case_files.py`
    - Parse `doc_id` from path parameters
    - List S3 objects under `cases/{case_id}/extracted-images/` matching `{doc_id}_page*`
    - Generate presigned URLs with 3600s expiration
    - Return empty list with 200 if no images found; return 400 for missing doc_id
    - _Requirements: 4.1, 4.3, 4.4_

  - [x] 5.2 Add Neptune face crop lookup to document images handler
    - Query Neptune for `FACE_DETECTED_IN` edges pointing to the document to find linked face crops
    - Fall back to S3 filename convention matching if Neptune query fails
    - Include face crop presigned URLs in response with `type: "face_crop"`
    - _Requirements: 4.2_

  - [x] 5.3 Add route in `case_files.py` dispatcher
    - Add route match for `/case-files/{id}/documents/{doc_id}/images` before existing `/documents/` catch-all
    - _Requirements: 4.1_

  - [ ]* 5.4 Write property test for document image filtering
    - **Property 7: Document image filtering by document ID prefix**
    - Generate random sets of extracted image filenames and random document IDs
    - Verify filtering returns exactly the files whose names start with the document ID
    - **Validates: Requirements 4.1**

  - [ ]* 5.5 Write property test for document face crops from graph
    - **Property 8: Document face crops from graph linkage**
    - Generate random sets of FACE_DETECTED_IN edge results
    - Verify all linked face crops appear in the document images response
    - **Validates: Requirements 4.2**

- [x] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Frontend: face crop thumbnails in drill-down panel
  - [x] 7.1 Add face crop thumbnail strip to entity drill-down in `investigator.html`
    - Add a "📸 FACE CROPS" section after the entity profile header for person entities
    - Fetch face crops from entity-photos API metadata (`face_crop_count`)
    - Display as a scrollable horizontal thumbnail strip (max 120px height)
    - Click on a thumbnail opens the full-size source image
    - _Requirements: 5.1, 5.3, 5.4_

  - [x] 7.2 Add document image gallery to document expansion in `investigator.html`
    - When a document card is expanded in the drill-down, fetch `GET /case-files/{id}/documents/{doc_id}/images`
    - Display extracted image thumbnails in a grid below the document excerpt
    - Lazy-load images using presigned URLs
    - _Requirements: 5.2_

- [x] 8. Frontend: pipeline photos on graph person nodes
  - [x] 8.1 Update graph rendering to use pipeline photos with visual indicator
    - Use `source` field from entity-photos API to add a visual indicator (green border for pipeline, orange for demo)
    - Ensure `fetchEntityPhotos()` is called on case load and graph re-render
    - Fall back to default person icon when no pipeline or demo photo exists
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 10. (Optional) Aurora face_crops table for fast querying
  - [ ]* 10.1 Create Aurora migration for `face_crops` table
    - Create migration SQL with columns: `id`, `crop_s3_key`, `source_s3_key`, `source_document_id`, `entity_name`, `bounding_box`, `confidence`, `case_file_id`, `created_at`
    - _Requirements: 7.1_

  - [ ]* 10.2 Update FaceCropService to insert records into Aurora
    - After uploading each crop to S3, insert a record into the `face_crops` table
    - _Requirements: 7.1_

  - [ ]* 10.3 Update EntityPhotoService and document images handler to query Aurora
    - Replace S3 listing with Aurora queries by entity name and case ID
    - Replace S3 listing with Aurora queries by source_document_id and case ID
    - _Requirements: 7.2, 7.3_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Aurora face_crops table (task 10) is deferred — S3 listing + Neptune queries are sufficient for MVP
- No CDK changes needed — all work extends existing Lambda handlers and services
- Each task references specific requirements for traceability
- Property tests use `hypothesis` with `@settings(max_examples=100)`
