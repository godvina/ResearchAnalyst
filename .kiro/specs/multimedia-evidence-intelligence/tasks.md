# Implementation Plan: Multimedia Evidence Intelligence

## Overview

Implement multimedia evidence capabilities in priority order: demo photos for immediate investigation wall value, Entity Photo API, frontend photo mode integration, automated FaceCropService, and pipeline integration. Video, audio, and media router tasks are deferred as optional future work for when multimedia datasets arrive. All code is Python (backend) and HTML/JS (frontend).

## Tasks

- [x] 1. Demo Face Photo Setup
  - [x] 1.1 Create `scripts/setup_demo_photos.py` setup script
    - Read `data/entity_photos.json` to get person names and Wikimedia URLs
    - Download each image (skip entries with empty URLs), resize to 200x200 JPEG using Pillow
    - Upload to S3 at `cases/{case_id}/face-crops/demo/{entity_name}.jpg`
    - Accept `--case-id` and `--bucket` CLI arguments, support `--dry-run` flag
    - Log upload count, skip count, and any download errors
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 1.2 Write property test for demo photo resize
    - **Property 13: Demo photo resize produces correct dimensions**
    - Generate random image dimensions; verify output is always exactly 200x200 JPEG
    - **Validates: Requirements 3.2**

- [x] 2. Entity Photo API
  - [x] 2.1 Create `src/services/entity_photo_service.py`
    - Implement `EntityPhotoService.__init__(self, s3_bucket: str)`
    - Implement `get_entity_photos(self, case_id: str, expiration: int = 3600) -> dict`
    - List pipeline-generated thumbnails at `cases/{case_id}/face-crops/{entity_name}/primary_thumbnail.jpg`
    - List demo photos at `cases/{case_id}/face-crops/demo/` prefix
    - Apply priority: pipeline crop > demo photo > omit
    - Generate presigned URLs with SigV4 signing, scoped to exact S3 key, configurable expiration (default 3600s)
    - Log each presigned URL generation with requesting user identity, entity name, and S3 key for audit
    - Return `{"entity_photos": {name: url}, "photo_count": int, "source_breakdown": {"pipeline": int, "demo": int}}`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.4, 3.5, 10.1, 10.2, 10.4_

  - [ ]* 2.2 Write property test for entity photo priority logic
    - **Property 4: Entity photo priority — pipeline over demo over omit**
    - Generate random combinations of pipeline/demo/no photos per entity; verify priority and no null URLs
    - **Validates: Requirements 2.3, 2.4, 3.4, 3.5**

  - [ ]* 2.3 Write property test for presigned URL scoping
    - **Property 11: Presigned URL scoped to exact S3 key**
    - Verify URL references exactly one S3 object key, no wildcards or prefix-level access
    - **Validates: Requirements 10.2**

  - [ ]* 2.4 Write property test for audit log completeness
    - **Property 12: Audit log completeness for presigned URL generation**
    - Verify every presigned URL generation produces a corresponding audit log entry with user identity, entity name, S3 key
    - **Validates: Requirements 10.4**

  - [x] 2.5 Add entity-photos route to `src/lambdas/api/case_files.py` dispatcher
    - Add route match for `GET /case-files/{id}/entity-photos` in `dispatch_handler`
    - Implement `entity_photos_handler(event, context)` that extracts case_id, instantiates EntityPhotoService, and returns the result
    - _Requirements: 2.1, 2.5_

  - [x] 2.6 Add API Gateway route definition to `infra/api_gateway/api_definition.yaml`
    - Add `GET /case-files/{id}/entity-photos` resource path with CORS options
    - Follow existing YAML structure and naming conventions
    - _Requirements: 2.1_

- [ ] 3. Checkpoint — Ensure demo photos and Entity Photo API work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Frontend Photo Mode Integration
  - [x] 4.1 Add photo display mode to `src/frontend/investigator.html`
    - Call `GET /case-files/{case_id}/entity-photos` on graph load
    - Add a "Photo Mode" toggle button to the graph controls
    - When active, render person nodes with `circularImage` shape using presigned URLs from the API
    - When inactive, render person nodes with existing SVG avatar icons
    - When a presigned URL returns 403 (expired), re-fetch entity photos from the API to get fresh URLs
    - _Requirements: 2.6, 10.3_

- [ ] 5. FaceCropService — Automated Pipeline Component
  - [ ] 5.1 Create `src/services/face_crop_service.py`
    - Implement `FaceCropService.__init__(self, s3_bucket: str)`
    - Implement `crop_faces(self, case_id: str, rekognition_results: list[dict]) -> dict`
    - For each face with confidence >= 0.90: download source image from S3, crop bounding box region, resize to 100x100 JPEG, upload to `cases/{case_id}/face-crops/{entity_name}/{hash}.jpg`
    - Implement `_crop_single_face(self, image_bytes, bounding_box, target_size=(100,100)) -> bytes` using Pillow
    - Implement `_compute_crop_hash(self, s3_key, bounding_box) -> str` for deterministic dedup
    - Select highest-confidence crop per entity as `primary_thumbnail.jpg`
    - Store `face_thumbnail_s3_key` vertex property on person entity in Neptune graph
    - On invalid image or crop failure: log warning, skip that face, continue processing remaining faces
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 5.2 Write property test for face crop confidence filter
    - **Property 1: Face crop confidence filter and count invariant**
    - Generate random lists of face detections with confidences 0.0–1.0; verify crop count = faces with confidence >= 0.90 and each crop is 100x100 JPEG
    - **Validates: Requirements 1.1, 1.3**

  - [ ]* 5.3 Write property test for deterministic S3 path generation
    - **Property 2: Deterministic S3 path generation**
    - Generate random case_ids, entity names, S3 keys, bounding boxes; verify path format and same inputs → same path, different inputs → different paths
    - **Validates: Requirements 1.2**

  - [ ]* 5.4 Write property test for primary thumbnail selection
    - **Property 3: Primary thumbnail is highest confidence**
    - Generate random lists of crops per entity with varying confidences; verify primary = max confidence
    - **Validates: Requirements 1.4**

  - [ ]* 5.5 Write property test for error resilience
    - **Property 5: Error resilience — invalid inputs don't crash processing**
    - Generate batches with random invalid inputs mixed in; verify processing continues and success + error counts = total
    - **Validates: Requirements 1.6**

- [ ] 6. FaceCropStep — Pipeline Integration
  - [ ] 6.1 Create `src/lambdas/ingestion/face_crop_handler.py`
    - Implement `handler(event, context)` that extracts case_id and rekognition_result from Step Functions event
    - Instantiate FaceCropService and call `crop_faces`
    - Return `{"case_id": ..., "status": "completed"|"skipped", "crops_created": int, "primary_thumbnails": {...}}`
    - If no face detections in input, return `status: "skipped"`
    - _Requirements: 1.1, 1.6_

  - [ ] 6.2 Add FaceCropStep state to `infra/step_functions/ingestion_pipeline.json`
    - Insert `FaceCropStep` Task state between `RekognitionStep` and `ChooseGraphLoadStrategy`
    - Change `RekognitionStep.Next` from `"ChooseGraphLoadStrategy"` to `"FaceCropStep"`
    - Set `FaceCropStep.Next` to `"ChooseGraphLoadStrategy"`
    - Add Catch block: on any error, capture to `$.face_crop_error` and continue to `ChooseGraphLoadStrategy` (non-blocking)
    - Add Retry with 2 max attempts, 3s interval, 2.0 backoff for TaskFailed/Lambda.ServiceException
    - Set TimeoutSeconds: 300
    - Pass `case_id`, `rekognition_result`, and `effective_config` via Parameters
    - _Requirements: 1.1, 1.6_

- [ ] 7. Checkpoint — Ensure FaceCropService and pipeline integration work
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 8. Video Intelligence — Tier 1 Automated Triage (Future)
  - [ ]* 8.1 Create `src/services/video_analyzer_service.py` with Tier 1 analysis
    - Implement `VideoAnalyzerService.__init__(self, s3_bucket: str)`
    - Implement `analyze_tier1(self, case_id: str, s3_key: str, config: dict) -> dict`
    - Run Rekognition `StartLabelDetection` and `StartFaceDetection` on video
    - Filter labels to INVESTIGATIVE_LABELS set (weapons, vehicles, currency, drugs, documents, electronics)
    - Store results at `cases/{case_id}/video-analysis/{filename}_tier1.json`
    - Create Neptune graph edges linking video entity to detected investigative labels with timestamp metadata
    - On failure: log error, mark video as `triage_failed`, continue
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 8.2 Write property test for investigative label filtering
    - **Property 6: Investigative label filtering**
    - Generate random label sets; verify only INVESTIGATIVE_LABELS pass through
    - **Validates: Requirements 4.2**

  - [ ]* 8.3 Write property test for video analysis output path format
    - **Property 15: Video analysis output path format**
    - Verify Tier 1 results stored at `cases/{case_id}/video-analysis/{filename}_tier1.json`
    - **Validates: Requirements 4.3**

- [ ]* 9. Video Intelligence — Tier 2 On-Demand Deep Dive (Future)
  - [ ]* 9.1 Add Tier 2 analysis to `src/services/video_analyzer_service.py`
    - Implement `analyze_tier2(self, case_id: str, s3_key: str, tier1_result: dict) -> dict`
    - Run Rekognition `StartCelebrityRecognition` and `StartContentModeration`
    - Extract key frames at each Tier 1 flagged timestamp, store as JPEG at `cases/{case_id}/video-keyframes/{filename}/{timestamp_ms}.jpg`
    - Store Tier 2 results at `cases/{case_id}/video-analysis/{filename}_tier2.json`
    - Link key frames and celebrity matches to Neptune graph with timestamp metadata
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 9.2 Write property test for key frame extraction
    - **Property 7: Key frame extraction matches flagged timestamps**
    - Verify N flagged timestamps produce exactly N JPEG key frames at correct S3 paths
    - **Validates: Requirements 5.2**

- [ ]* 10. Video Intelligence — Tier 3 Human Review Interface (Future)
  - [ ]* 10.1 Add video review panel to `src/frontend/investigator.html`
    - Display flagged video segments with timestamps, labels, and confidence scores
    - Provide segment playback controls (start to end timestamp)
    - Overlay AI annotations synchronized with playback position
    - Support "confirmed relevant" marking that updates Neptune edge metadata
    - Add keyboard navigation: spacebar play/pause, arrows 5s skip, 1-9 jump to flagged segments
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ]* 11. Audio Intelligence — Transcription and Search (Future)
  - [ ]* 11.1 Create `src/services/audio_transcriber_service.py`
    - Implement `AudioTranscriberService.__init__(self, s3_bucket: str)`
    - Implement `transcribe(self, case_id: str, s3_key: str, config: dict) -> dict`
    - Submit to Amazon Transcribe with speaker diarization (max 10 speakers)
    - Store raw output at `cases/{case_id}/transcripts/{filename}_transcript.json`
    - Parse into structured transcript at `cases/{case_id}/transcripts/{filename}_structured.json`
    - On failure: log error, mark as `transcription_failed`, continue
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 11.2 Write property test for transcript parsing
    - **Property 8: Transcribe output parsing preserves all segments**
    - Generate mock Transcribe output; verify structured parsing preserves all segments with speaker, timestamps, text
    - **Validates: Requirements 7.4**

  - [ ]* 11.3 Implement entity mention detection and graph integration
    - Implement `detect_entity_mentions(self, case_id, transcript, known_entities) -> list[dict]`
    - Create Neptune edges linking audio/video entity to mentioned entities with speaker label and timestamp range
    - Flag co-occurrence segments (2+ entities within same speaker turn or 30-second window)
    - Store flags at `cases/{case_id}/transcripts/{filename}_flags.json`
    - Index transcript segments in OpenSearch for semantic search
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 11.4 Write property test for entity co-occurrence flagging
    - **Property 9: Entity co-occurrence flagging within 30-second window**
    - Generate transcripts with random entity mentions; verify flagging logic for 2+ entities within window
    - **Validates: Requirements 8.3**

  - [ ]* 11.5 Write property test for graph edge creation from entity mentions
    - **Property 14: Entity mention detection in transcripts creates graph edges**
    - Verify each known entity mention creates a Neptune edge with speaker label and timestamp range
    - **Validates: Requirements 8.2**

  - [ ]* 11.6 Add transcript viewer to `src/frontend/investigator.html`
    - Display speaker labels, timestamps, and clickable segments
    - Click segment to jump to corresponding audio/video playback position
    - _Requirements: 8.5_

- [ ]* 12. Media Type Router (Future)
  - [ ]* 12.1 Add media type classification to config resolution
    - Extend `src/services/config_resolution_service.py` with `MEDIA_TYPE_MAP` classification
    - Classify by extension: image (.jpg, .jpeg, .png, .tiff, .tif), video (.mp4, .mov), audio (.mp3, .wav, .m4a), document (all others)
    - Case-insensitive extension matching
    - Record `media_type` on document metadata during upload
    - Log warning for unrecognized extensions, default to "document"
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [ ]* 12.2 Write property test for media type classification
    - **Property 10: Media type classification correctness**
    - Generate random filenames with various extensions; verify correct classification and case-insensitivity
    - **Validates: Requirements 9.1, 9.6, 9.7**

  - [ ]* 12.3 Add VideoTier1Branch and AudioTranscribeBranch to Step Functions
    - Add parallel branches after ProcessDocuments in `infra/step_functions/ingestion_pipeline.json`
    - Route video files to VideoAnalyzerService, audio files to AudioTranscriberService
    - Both branches non-blocking with Catch fallthrough
    - _Requirements: 9.2, 9.3, 9.4_

- [ ] 13. Final checkpoint — Ensure all implemented tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Tasks 1–7 are the core build-now scope: demo photos, Entity Photo API, frontend photo mode, FaceCropService, and pipeline integration
- Tasks 8–12 are future work for when video, audio, and multimedia datasets arrive
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The design uses Python throughout — no language selection needed
