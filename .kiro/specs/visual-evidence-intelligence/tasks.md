# Implementation Plan: Visual Evidence Intelligence

## Overview

Requirements 1–6 are already implemented and working in production. The remaining work covers three areas: extending `load_rekognition_to_graph.py` with a `collect_label_entities()` function for Neptune graph loading (Req 7), running existing scripts at full scale on 15,791 images with artifact syncing (Req 8), and extending `match_faces.py` with incremental comparison tracking (Req 9). All changes EXTEND existing code per `docs/lessons-learned.md`.

Additional completed work (post-spec):
- Clickable label gallery: label tags in the Visual Evidence Summary are clickable, opening a filtered image gallery overlay (Palantir-style faceted browsing)
- Redaction false-positive detection documented: Rekognition "Weapon/Gun" labels on redacted documents are false positives (Issue 31 in lessons-learned)
- Data Loader page created (`data-loader.html`) and linked from home page, replacing failed batch-loader
- All documentation updated in `docs/lessons-learned.md`

## Tasks

- [x] 1. Batch Rekognition label detection
  - Label_Detector script processes images through detect_labels, filters investigative labels ≥ 70% confidence, saves summary and details JSON to S3
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

- [x] 2. Face cropping from detected bounding boxes
  - Face_Cropper reads face_crop_metadata.json, crops with 30% padding, resizes to 200×200, uploads to S3 with target-case support
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3. Face matching against known entities
  - Face_Matcher compares unidentified crops against demo photos via CompareFaces, copies matches to named entity folders, saves results JSON
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 4. Image evidence gallery API
  - GET /case-files/{id}/image-evidence returns paginated images with labels, faces, presigned URLs, summary stats, label filtering, face data merge
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 5. Image evidence gallery frontend
  - Investigator.html drill-down panel shows matched face thumbnails with entity names and confidence scores
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 6. Entity photo resolution with priority
  - Entity_Photo_Service resolves pipeline primary_thumbnail.jpg > demo photos, returns base64 data URIs with metadata
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 7. Extend graph loader with Rekognition label data
  - [x] 7.1 Add `collect_label_entities()` function to `scripts/load_rekognition_to_graph.py`
    - Read `batch_labels_details.json` from `cases/{case_id}/rekognition-artifacts/` in the data lake bucket
    - Extract source_document_id from each image's s3_key filename pattern `{doc_id}_page{N}_img{M}.jpg`
    - Create Visual_Entity dict per unique label name with entity_type from LABEL_TYPE_MAP, average confidence, and occurrence_count
    - Build (label, source_document_id) pairs for DETECTED_IN edges
    - Build co-occurrence pairs for labels sharing the same source_document_id
    - Node ID format: `{case_id}_visual_{label_name}` to avoid collision with existing entity nodes
    - _Requirements: 7.1, 7.2, 7.3, 7.6_

  - [x] 7.2 Add LABEL_TYPE_MAP constant and `map_label_type()` helper
    - Define mapping dict: person labels → "person", vehicle → "vehicle", document → "document", weapon → "weapon", all others → "artifact"
    - Cover all labels in INVESTIGATIVE_LABELS set from batch_rekognition_labels.py
    - _Requirements: 7.6_

  - [x] 7.3 Extend `generate_csv_and_load()` to support Visual_Entity nodes and DETECTED_IN / CO_OCCURS_WITH edges
    - Nodes CSV header: `~id,~label,entity_type:String,canonical_name:String,confidence:Double,occurrence_count:Int,case_file_id:String,source:String`
    - Node ~label: `VisualEntity_{case_id}`
    - DETECTED_IN edges: `~id,~from,~to,~label,confidence:Double,case_file_id:String`
    - CO_OCCURS_WITH edges: `~id,~from,~to,~label,co_occurrence_count:Int,case_file_id:String`
    - Upload CSVs to `neptune-bulk-load/{case_id}/` and trigger Neptune bulk loader
    - _Requirements: 7.4, 7.5, 7.7_

  - [x] 7.4 Add `--mode` CLI argument to main()
    - `rekognition` (default): existing behavior — collect_visual_entities() + generate_csv_and_load()
    - `labels`: new — collect_label_entities() + generate_csv_and_load() with Visual_Entity format
    - `all`: run both modes sequentially
    - _Requirements: 7.1, 7.4_

  - [ ]* 7.5 Write property test for label-to-entity-type mapping (Property 15)
    - **Property 15: Label-to-entity-type mapping**
    - For all labels in INVESTIGATIVE_LABELS, verify each maps to exactly one type from {person, vehicle, document, weapon, artifact}
    - **Validates: Requirements 7.6**

  - [ ]* 7.6 Write property test for Visual_Entity node creation (Property 11)
    - **Property 11: Visual_Entity node creation from label data**
    - Generate random batch_labels_details entries, verify unique node count equals unique label count
    - **Validates: Requirements 7.1**

  - [ ]* 7.7 Write property test for DETECTED_IN edge creation (Property 12)
    - **Property 12: DETECTED_IN edge creation**
    - Generate random images with labels and source_document_ids, verify one edge per unique (label, doc_id) pair
    - **Validates: Requirements 7.2**

  - [ ]* 7.8 Write property test for co-occurrence edge creation (Property 13)
    - **Property 13: Co-occurrence edge creation**
    - Generate random multi-label documents, verify edge count equals N*(N-1)/2 per document
    - **Validates: Requirements 7.3**

  - [ ]* 7.9 Write property test for Neptune CSV format (Property 14)
    - **Property 14: Neptune CSV generation format**
    - Generate random entities and edges, verify CSV headers, row counts, and referential integrity
    - **Validates: Requirements 7.4**

- [x] 8. Checkpoint — Ensure graph loader extension works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Extend face matcher with incremental comparison tracking
  - [x] 9.1 Add comparison log loading/saving to `scripts/match_faces.py`
    - Add `--comparison-log` CLI arg (default: `scripts/face_match_comparison_log.json`)
    - On startup, load existing comparison log; if corrupted/missing, start fresh with empty log and log warning
    - Build a set of completed `(crop_filename, entity_name)` tuples from the log
    - After processing, append new comparisons with timestamps to the log and save
    - _Requirements: 9.1, 9.2_

  - [x] 9.2 Add skip logic for already-completed comparisons
    - Before calling CompareFaces for a (crop, entity) pair, check if it exists in the completed set
    - If already completed, skip the API call entirely
    - Track skipped count and log summary at end
    - _Requirements: 9.2_

  - [x] 9.3 Add cumulative results merging to `scripts/match_faces.py`
    - On startup, load existing `face_match_results.json` from S3; if corrupted/missing, start fresh
    - After matching, merge new matches into existing matches (no duplicate crop+entity entries)
    - Append a run entry to the `runs` array with timestamp, new_matches count, new_crops count, new_entities count
    - Write merged results back to S3
    - _Requirements: 9.4_

  - [ ]* 9.4 Write property test for incremental comparison tracking (Property 16)
    - **Property 16: Incremental comparison tracking**
    - Generate random completed logs and current (crop, entity) pairs, verify new comparisons = set difference
    - **Validates: Requirements 9.1, 9.2**

  - [ ]* 9.5 Write property test for cumulative match results merge (Property 17)
    - **Property 17: Cumulative match results merge**
    - Generate random existing and new match results, verify merge has no duplicates and runs array grows by 1
    - **Validates: Requirements 9.4**

- [x] 10. Full-scale processing pipeline execution
  - [x] 10.1 Add artifact sync helper to `scripts/load_rekognition_to_graph.py`
    - Add `sync_artifacts_to_combined(case_id, combined_case_id)` function
    - Copy `batch_labels_summary.json` and `batch_labels_details.json` from main case path to combined case path in S3
    - _Requirements: 8.2_

  - [x] 10.2 Add `--sync-combined` CLI flag to `scripts/load_rekognition_to_graph.py`
    - When set, call `sync_artifacts_to_combined()` after label collection
    - Use COMBINED_CASE constant already defined in match_faces.py (add to load_rekognition_to_graph.py)
    - _Requirements: 8.2_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Requirements 1–6 (tasks 1–6) are already implemented — marked complete
- All new code EXTENDS existing scripts — no rewrites per docs/lessons-learned.md
- No CDK or infrastructure changes needed
- Full-scale processing (Req 8.1, 8.3, 8.4) is operational — run existing scripts manually, no new code
- Property tests use Python `hypothesis` library with `@settings(max_examples=100)`
