# Implementation Plan: Evidence Library Tab

## Overview

Add a dedicated "🔍 Evidence" tab to `investigator.html` with a browsable evidence grid/gallery, filtering, detail modal with face bounding boxes, video playback, AI analysis via Bedrock, and graph connections. Two small backend handlers are added to `case_files.py` for evidence analysis and video presigned URLs.

## Tasks

- [x] 1. Register the Evidence tab and create the tab content panel
  - [x] 1.1 Add the Evidence tab button to the `.tabs` bar in `investigator.html`
    - Add `<div class="tab" onclick="switchTab('evidence')">🔍 Evidence</div>` after the Map tab
    - _Requirements: 1.1_
  - [x] 1.2 Add 'evidence' to the `allTabs` array in `switchTab()` and add the evidence load trigger
    - Append `'evidence'` to the allTabs array
    - Add `if (tab === 'evidence' && selectedCaseId) loadEvidence();` alongside the other tab triggers
    - _Requirements: 1.2, 1.3_
  - [x] 1.3 Create the `#tab-evidence` content panel HTML structure
    - Add `<div id="tab-evidence" class="tab-content">` after the Map tab content section
    - Include the section-card container with header row, `#evidenceStats` summary bar, `#evidenceFilters` controls, `#evidenceGrid` container, and `#evidencePagination` controls
    - Include the `#evidenceDetailOverlay` modal structure with close button, content area, metadata panel, graph connections section, and AI insights panel
    - Use dark theme styling consistent with existing tabs (background #0d1117, text #e6edf3, cards #161b22, borders #30363d)
    - _Requirements: 1.4, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 2. Implement summary statistics bar and data loading
  - [x] 2.1 Implement `loadEvidence()` function
    - Guard on `selectedCaseId`, show toast if no case selected
    - Fetch `GET /case-files/{selectedCaseId}/image-evidence?page=1&page_size=50`
    - Fetch `GET /case-files/{selectedCaseId}/entity-photos`
    - Fetch `GET /case-files/{selectedCaseId}/video-evidence`
    - Store results in module-level variables: `evidenceImages`, `evidenceVideos`, `evidenceEntityPhotos`, `evidenceSummary`
    - Call `renderEvidenceStats()` and `renderEvidenceGrid()`
    - _Requirements: 2.1, 2.2, 2.3, 3.6_
  - [x] 2.2 Implement `renderEvidenceStats(summary)` function
    - Render stat cards for: total images, total videos, total documents, images with faces, images with investigative labels
    - Read counts from the image-evidence API summary fields and video-evidence response total
    - Display zero for all counts when API returns no data
    - _Requirements: 2.1, 2.2, 2.5_

- [x] 3. Implement the evidence grid gallery view
  - [x] 3.1 Implement `renderEvidenceGrid()` function
    - Render image cards with thumbnail via presigned URL, filename, face count badge, up to 3 label badges
    - Render video cards with video icon placeholder, filename, format badge (.mp4/.mov), play overlay
    - Render document cards with document icon, filename, document type badge
    - Use responsive CSS grid: `grid-template-columns: repeat(auto-fill, minmax(200px, 1fr))`
    - Show empty state message when no evidence items exist
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7_
  - [x] 3.2 Implement `loadEvidencePage(page)` pagination function
    - Fetch the specified page from Image_Evidence_API with current page_size
    - Re-render grid with new page data
    - Render pagination controls: previous, page X of Y, next
    - _Requirements: 3.5_
  - [ ]* 3.3 Write property test for pagination boundary computation
    - **Property 4: Pagination computes correct page boundaries**
    - **Validates: Requirements 3.5**

- [x] 4. Implement media type and label filtering
  - [x] 4.1 Implement `filterEvidenceByType(mediaType)` function
    - Add toggle buttons for All, Images, Videos, Documents in the filter controls area
    - Set `evidenceMediaFilter` state and re-render grid showing only matching items
    - Visually indicate the active filter selection
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_
  - [x] 4.2 Implement `filterEvidenceByLabel(label)` function
    - Populate label dropdown from the Image_Evidence_API summary `label_counts` field
    - Display count next to each label name
    - Re-fetch images with `label_filter` query parameter when a label is selected
    - Re-fetch with `has_faces=true` when "Has Faces" option is selected
    - Clear filter re-fetches unfiltered list
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  - [ ]* 4.3 Write property test for media type filter correctness
    - **Property 5: Media type filter returns only matching items**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**
  - [ ]* 4.4 Write property test for filter query parameter construction
    - **Property 7: Filter selection constructs correct API query parameters**
    - **Validates: Requirements 5.2, 5.3, 5.5**

- [ ] 5. Checkpoint - Ensure tab, grid, stats, and filters work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement the evidence detail modal for images
  - [x] 6.1 Implement `openEvidenceDetail(type, index)` for images
    - Display full-size image via presigned URL in the modal
    - Draw face bounding boxes on a canvas overlay for each detected face, showing entity name or "Unidentified"
    - List all Rekognition labels with confidence scores
    - Display source document ID and filename
    - Show AI description and false-positive assessment from `weapon_ai_descriptions` when available
    - Add close button and Escape key handler
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 7. Implement video playback in the detail modal
  - [x] 7.1 Implement `openEvidenceDetail(type, index)` for videos
    - Create HTML5 `<video>` element with presigned S3 URL and `controls` attribute
    - Support .mp4 and .mov formats
    - Display video filename and metadata (format) alongside the player
    - Show error message with filename and download suggestion if video fails to load
    - Clean up video playback when modal is closed
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 8. Implement graph connection view in the detail modal
  - [x] 8.1 Implement `renderGraphConnections(item)` function
    - List matched entities with face thumbnails from Entity_Photo_API and confidence scores
    - Display source document name as a clickable link to the cases tab
    - Group connections by type: Persons, Documents, Locations
    - Show "No graph connections identified" when no connections exist
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 9. Add backend evidence-analyze handler
  - [x] 9.1 Add `evidence_analyze_handler` to `src/lambdas/api/case_files.py`
    - Add route matching for `POST /case-files/{id}/evidence-analyze`
    - Parse request body: evidence_type, filename, s3_key, labels, faces, source_document_id, case_context
    - Construct investigative analysis prompt from evidence metadata
    - Call Bedrock `invoke_model` with Claude 3 Haiku
    - Return `{ analysis, evidence_type, model_id }`
    - Return 400 for missing required fields, 500 for Bedrock errors
    - _Requirements: 8.1, 8.2, 8.3_
  - [ ]* 9.2 Write unit test for `evidence_analyze_handler`
    - Test valid request returns analysis text
    - Test missing required fields returns 400
    - _Requirements: 8.1_

- [x] 10. Add backend video-evidence handler
  - [x] 10.1 Add `video_evidence_handler` to `src/lambdas/api/case_files.py`
    - Add route matching for `GET /case-files/{id}/video-evidence`
    - List `.mp4` and `.mov` files under `cases/{case_id}/videos/` in S3
    - Also check `epstein_downloads/videos/` prefix for the Epstein case
    - Generate presigned URLs (1-hour expiration) for each video
    - Return `{ videos: [{ s3_key, filename, format, presigned_url, size_bytes }], total }`
    - _Requirements: 2.3, 7.1_
  - [ ]* 10.2 Write unit test for `video_evidence_handler`
    - Test with no videos returns empty list
    - Test with videos returns correct presigned URLs and metadata
    - _Requirements: 2.3_

- [x] 11. Implement AI insights panel in the frontend
  - [x] 11.1 Implement `analyzeEvidence(type, itemData)` function
    - Add "Analyze" button in the Evidence_Detail_Modal
    - POST to `/case-files/{selectedCaseId}/evidence-analyze` with evidence metadata (type, filename, s3_key, labels, faces, source_document_id, case_context)
    - Show loading indicator "Analyzing evidence..." while request is in progress
    - Display analysis text in a scrollable AI Insights Panel on success
    - Show error message "Analysis could not be completed" on failure
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The frontend code (HTML, CSS, JavaScript) goes in `src/frontend/investigator.html` after the Map tab section
- The backend handlers go in `src/lambdas/api/case_files.py` following the existing `image_evidence_handler` pattern
- No new service files or CDK changes are needed
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
