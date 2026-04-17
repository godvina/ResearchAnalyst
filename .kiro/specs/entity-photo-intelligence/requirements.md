# Requirements Document

## Introduction

Entity Photo Intelligence links pipeline-extracted face crops from PDF image extraction to graph entities and surfaces them in the investigator drill-down UI. Currently, entity photos come from a static JSON mapping (`data/entity_photos.json`) populated by `setup_demo_photos.py`. The PDF image extraction pipeline already extracts images from PDFs via PyMuPDF, detects faces via Rekognition, and saves face crops to S3. This feature closes the loop by: (1) persisting face-crop-to-document and face-crop-to-entity associations in the graph during ingestion, (2) serving pipeline-extracted photos through the existing entity-photos API, and (3) displaying document-level images and pipeline face crops in the investigator drill-down panel.

## Glossary

- **Ingestion_Pipeline**: The Step Functions pipeline that processes uploaded documents through parsing, entity extraction, Rekognition analysis, and graph loading.
- **Rekognition_Handler**: The Lambda function (`rekognition_handler.py`) that runs Amazon Rekognition face detection, label detection, and text detection on images and videos for a case.
- **Face_Crop_Service**: The service (`face_crop_service.py`) that crops face bounding box regions from source images, resizes them to 100×100 JPEG thumbnails, and uploads them to S3 under `cases/{case_id}/face-crops/{entity_name}/`.
- **Entity_Photo_Service**: The service (`entity_photo_service.py`) that generates entity-name-to-base64-data-URI mappings by listing pipeline and demo face crops from S3.
- **Entity_Photos_API**: The API endpoint `GET /case-files/{id}/entity-photos` that returns entity photo mappings for the graph visualization.
- **Graph_Loader**: The Lambda function (`graph_load_handler.py`) that loads entities and relationships into the Neptune graph database.
- **Neptune_Graph**: The Amazon Neptune graph database storing entities, documents, and their relationships.
- **Drill_Down_Panel**: The right-side panel in the investigator UI (`investigator.html`) that shows entity details, ego graph, AI analysis, and related documents when a graph node is clicked.
- **Face_Crop**: A 100×100 JPEG thumbnail of a detected face, stored at `cases/{case_id}/face-crops/{entity_name}/{hash}.jpg` in S3.
- **Extracted_Image**: A full image extracted from a PDF by PyMuPDF, stored at `cases/{case_id}/extracted-images/` in S3.
- **Source_Document_ID**: The document identifier parsed from an extracted image filename using the pattern `{document_id}_page{N}_img{M}.{ext}`.
- **Primary_Thumbnail**: The highest-confidence face crop for an entity, copied to `cases/{case_id}/face-crops/{entity_name}/primary_thumbnail.jpg`.

## Requirements

### Requirement 1: Persist Face-Crop-to-Document Edges in the Graph

**User Story:** As an investigator, I want face crops linked to their source documents in the graph, so that I can trace a face back to the PDF it was extracted from.

#### Acceptance Criteria

1. WHEN the Rekognition_Handler processes an extracted image with a parseable Source_Document_ID, THE Graph_Loader SHALL create a `FACE_DETECTED_IN` edge from the Face_Crop node to the source document node in the Neptune_Graph.
2. WHEN the Rekognition_Handler produces face detection results, THE Ingestion_Pipeline SHALL include `face_crop_metadata` in the output passed to the Graph_Loader, containing the S3 key of each Face_Crop, the source S3 key, the Source_Document_ID, the bounding box coordinates, and the detection confidence.
3. IF the Source_Document_ID parsed from an extracted image filename equals "unknown", THEN THE Graph_Loader SHALL still create the Face_Crop node but omit the `FACE_DETECTED_IN` edge and log a warning.

### Requirement 2: Associate Face Crops with Person Entities

**User Story:** As an investigator, I want face crops automatically associated with person entities mentioned in the same source document, so that I can see faces relevant to each person of interest.

#### Acceptance Criteria

1. WHEN a person entity is extracted from a document that also has Face_Crop detections, THE Graph_Loader SHALL create a `HAS_FACE_CANDIDATE` edge from the person entity node to each Face_Crop node linked to that document.
2. WHEN a Rekognition watchlist match identifies a face as a named person, THE Face_Crop_Service SHALL associate that Face_Crop directly with the matched person entity using a `HAS_FACE_MATCH` edge with the watchlist similarity score as an edge property.
3. THE Graph_Loader SHALL store the association source as an edge property with value `"document_co_occurrence"` for document-based associations and `"watchlist_match"` for Rekognition watchlist matches.

### Requirement 3: Serve Pipeline Face Crops via the Entity Photos API

**User Story:** As a frontend developer, I want the entity-photos API to return pipeline-extracted face crops alongside demo photos, so that the graph visualization uses real extracted faces when available.

#### Acceptance Criteria

1. THE Entity_Photos_API SHALL return pipeline-extracted Primary_Thumbnail photos with higher priority than demo photos when both exist for the same entity name.
2. WHEN no pipeline Primary_Thumbnail exists for an entity, THE Entity_Photos_API SHALL fall back to the demo photo from the `face-crops/demo/` S3 prefix.
3. THE Entity_Photos_API SHALL include a `source` field for each entity photo indicating whether the photo originated from `"pipeline"` or `"demo"`.
4. WHEN the Entity_Photos_API returns photos, THE Entity_Photos_API SHALL include a `face_crop_count` field per entity indicating the total number of Face_Crop files available for that entity (not just the primary thumbnail).

### Requirement 4: Serve Document-Level Extracted Images via a New API Endpoint

**User Story:** As an investigator, I want to see all images extracted from a document in the drill-down panel, so that I can review visual evidence alongside text analysis.

#### Acceptance Criteria

1. WHEN a GET request is made to `/case-files/{id}/documents/{doc_id}/images`, THE Entity_Photos_API SHALL return a list of presigned S3 URLs for all Extracted_Image files whose filenames begin with the specified document ID.
2. WHEN a GET request is made to `/case-files/{id}/documents/{doc_id}/images`, THE Entity_Photos_API SHALL also return presigned S3 URLs for all Face_Crop files linked to that document via `FACE_DETECTED_IN` edges in the Neptune_Graph.
3. IF no extracted images or face crops exist for the specified document, THEN THE Entity_Photos_API SHALL return an empty list with a 200 status code.
4. THE Entity_Photos_API SHALL generate presigned URLs with a default expiration of 3600 seconds.

### Requirement 5: Display Document Images in the Drill-Down Panel

**User Story:** As an investigator, I want to see extracted images and face crops in the drill-down panel when I click on an entity, so that I can visually assess evidence related to a person of interest.

#### Acceptance Criteria

1. WHEN an investigator clicks a person node in the graph, THE Drill_Down_Panel SHALL fetch and display all Face_Crop images associated with that entity via the Entity_Photos_API.
2. WHEN an investigator expands a related document in the Drill_Down_Panel, THE Drill_Down_Panel SHALL fetch and display Extracted_Image thumbnails from that document using the document images endpoint.
3. THE Drill_Down_Panel SHALL display Face_Crop images as a scrollable thumbnail strip with a maximum height of 120 pixels per thumbnail.
4. WHEN an investigator clicks a Face_Crop thumbnail in the Drill_Down_Panel, THE Drill_Down_Panel SHALL display the full-size Extracted_Image from which the face was cropped.

### Requirement 6: Use Pipeline Face Photos on Graph Person Nodes

**User Story:** As an investigator, I want the knowledge graph to show real extracted face photos on person nodes when available, so that I can visually identify persons of interest at a glance.

#### Acceptance Criteria

1. WHEN the graph visualization renders a person node that has a pipeline Primary_Thumbnail, THE graph visualization SHALL use the pipeline photo as the `circularImage` for that node instead of the demo photo.
2. WHEN a person node has no pipeline Primary_Thumbnail and no demo photo, THE graph visualization SHALL render the node with the default person icon.
3. THE graph visualization SHALL refresh entity photos from the Entity_Photos_API each time a case is loaded or the graph is re-rendered.

### Requirement 7: Face Crop Metadata Persistence in Aurora

**User Story:** As a system operator, I want face crop metadata stored in Aurora for fast querying, so that the API can efficiently look up face crops by document or entity without scanning S3.

#### Acceptance Criteria

1. WHEN the Face_Crop_Service creates a new Face_Crop, THE Face_Crop_Service SHALL insert a record into an Aurora `face_crops` table containing the crop S3 key, source image S3 key, Source_Document_ID, entity name, bounding box coordinates, detection confidence, and creation timestamp.
2. WHEN the Entity_Photos_API queries face crops for an entity, THE Entity_Photos_API SHALL query the Aurora `face_crops` table by entity name and case ID instead of listing S3 objects.
3. WHEN the Entity_Photos_API queries face crops for a document, THE Entity_Photos_API SHALL query the Aurora `face_crops` table by Source_Document_ID and case ID.
