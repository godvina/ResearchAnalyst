# Requirements Document

## Introduction

Visual Evidence Intelligence provides the complete visual analysis pipeline for investigative case analysis. The system processes extracted images from case documents through AWS Rekognition for label detection and face analysis, crops and matches detected faces against known entity photos, loads visual entity data into the Neptune knowledge graph, and serves the results through a paginated API and frontend gallery. This spec formalizes the already-implemented components and defines the remaining work: Neptune graph loading of Rekognition label data, full-scale image processing, and scalable face matching.

## Glossary

- **Rekognition_Pipeline**: The set of scripts and services that call AWS Rekognition APIs (detect_labels, compare_faces) on extracted case images and store results as JSON artifacts in S3.
- **Face_Cropper**: The script (scripts/crop_faces.py) that reads face bounding box metadata from S3, downloads source images, crops face regions with padding, resizes to 200x200 thumbnails, and uploads to S3.
- **Face_Matcher**: The script (scripts/match_faces.py) that uses Rekognition CompareFaces to compare unidentified face crops against known entity photos and copies matched crops to named entity folders in S3.
- **Label_Detector**: The script (scripts/batch_rekognition_labels.py) that runs Rekognition detect_labels on extracted images, filters for investigative labels above a confidence threshold, and saves per-image results and a consolidated summary to S3.
- **Graph_Loader**: The script (scripts/load_rekognition_to_graph.py) that reads Rekognition label artifacts from S3, creates visual_entity nodes and co-occurrence edges, generates Neptune bulk-load CSV files, and triggers the Neptune bulk loader.
- **Image_Evidence_API**: The GET /case-files/{id}/image-evidence endpoint in case_files.py that returns paginated image records with labels, face data, presigned URLs, and summary statistics.
- **Image_Evidence_Gallery**: The frontend section in investigator.html that displays matched face images for entities and other detected faces with presigned URL thumbnails.
- **Entity_Photo_Service**: The service (src/services/entity_photo_service.py) that resolves entity photos from pipeline face-crops and demo photos with priority ordering (pipeline > demo).
- **Visual_Entity**: A Neptune graph node representing a person, object, or artifact detected by Rekognition in a case image (e.g., Person, Document, Boat, Weapon).
- **DETECTED_IN_Edge**: A Neptune graph edge linking a Visual_Entity node to the source document node where the entity was visually detected.
- **Investigative_Labels**: The curated set of Rekognition label categories relevant to investigations (persons, documents, vehicles, weapons, drugs, jewelry, locations, etc.) defined in batch_rekognition_labels.py.
- **S3_Bucket**: research-analyst-data-lake-974220725866, the data lake bucket storing all case artifacts.
- **Main_Case**: Case 7f05e8d5-4492-4f19-8894-25367606db96 containing 15,791 extracted images.
- **Combined_Case**: Case ed0b6c27-3b6b-4255-b9d0-efe8f4383a99, the UI-facing case that aggregates results.

## Requirements

### Requirement 1: Batch Rekognition Label Detection [IMPLEMENTED]

**User Story:** As an investigator, I want all extracted images from a case to be analyzed by Rekognition for object and scene labels, so that I can discover visual evidence patterns across thousands of documents.

#### Acceptance Criteria

1. WHEN a batch label detection run is initiated for a case, THE Label_Detector SHALL list all extracted images under `cases/{case_id}/extracted-images/` in S3_Bucket and process each image through Rekognition detect_labels.
2. THE Label_Detector SHALL filter detected labels against the Investigative_Labels set and retain only labels with confidence at or above 70%.
3. WHEN processing completes, THE Label_Detector SHALL save a consolidated summary (image count, unique labels, label frequency counts, error count) to `cases/{case_id}/rekognition-artifacts/batch_labels_summary.json` in S3_Bucket.
4. WHEN processing completes, THE Label_Detector SHALL save per-image label details (only images with at least one matching label) to `cases/{case_id}/rekognition-artifacts/batch_labels_details.json` in S3_Bucket.
5. THE Label_Detector SHALL support resume from a local progress file so that interrupted runs continue from the last processed image index.
6. THE Label_Detector SHALL support configurable parallelism (default 3 threads) and rate-limit Rekognition calls with a 50ms delay between batches to avoid throttling.
7. IF a Rekognition API call fails for a single image, THEN THE Label_Detector SHALL log the error, increment the error counter, and continue processing remaining images.

### Requirement 2: Face Cropping from Detected Bounding Boxes [IMPLEMENTED]

**User Story:** As an investigator, I want detected faces to be cropped from source images as individual thumbnails, so that I can visually identify persons of interest across documents.

#### Acceptance Criteria

1. WHEN face crop metadata exists at `cases/{case_id}/rekognition-artifacts/face_crop_metadata.json`, THE Face_Cropper SHALL download each source image, crop the face region using the Rekognition bounding box coordinates with 30% padding, and resize to a 200x200 JPEG thumbnail.
2. THE Face_Cropper SHALL upload each cropped thumbnail to the S3 path specified in the face_crop_metadata crop_s3_key field.
3. WHEN a target-case argument is provided, THE Face_Cropper SHALL copy each cropped thumbnail to the corresponding path under the target case ID.
4. IF a source image download fails or the cropped region is smaller than 20x20 pixels, THEN THE Face_Cropper SHALL skip that face and log a warning.

### Requirement 3: Face Matching Against Known Entities [IMPLEMENTED]

**User Story:** As an investigator, I want unidentified face crops to be compared against known entity photos, so that I can automatically identify persons of interest appearing in case documents.

#### Acceptance Criteria

1. WHEN face matching is initiated, THE Face_Matcher SHALL list all known entity demo photos under `cases/{case_id}/face-crops/demo/` and all unidentified face crops under `cases/{case_id}/face-crops/unidentified/` in S3_Bucket.
2. FOR EACH unidentified crop, THE Face_Matcher SHALL call Rekognition CompareFaces against every known entity photo and select the entity with the highest similarity score at or above the threshold (default 80%).
3. WHEN a match is found, THE Face_Matcher SHALL copy the crop to `cases/{case_id}/face-crops/{entity_name}/{crop_filename}` in S3_Bucket and to the corresponding path under the Combined_Case.
4. WHEN all crops are processed, THE Face_Matcher SHALL save match results (matched crops with entity names and similarity scores, unmatched crop list, threshold used) to `cases/{case_id}/rekognition-artifacts/face_match_results.json`.
5. IF Rekognition CompareFaces returns an InvalidParameterException (no face detected in an image), THEN THE Face_Matcher SHALL skip that comparison and continue.
6. THE Face_Matcher SHALL rate-limit CompareFaces calls with a 100ms delay between comparisons.

### Requirement 4: Image Evidence Gallery API [IMPLEMENTED]

**User Story:** As an investigator, I want a paginated API endpoint that returns images with their Rekognition labels, face data, and viewable URLs, so that the frontend can display a visual evidence gallery.

#### Acceptance Criteria

1. WHEN a GET request is made to `/case-files/{id}/image-evidence`, THE Image_Evidence_API SHALL return a paginated list of image records, each containing s3_key, filename, source_document_id, labels array, faces array, and face_count.
2. THE Image_Evidence_API SHALL support query parameters: page (default 1), page_size (default 50, max 200), label_filter (filter images containing a specific label), and has_faces (filter to images with detected faces).
3. THE Image_Evidence_API SHALL generate presigned S3 URLs (1-hour expiration) for each image in the current page.
4. THE Image_Evidence_API SHALL return summary statistics including label frequency counts, unique label count, total faces detected, and matched face count.
5. WHEN batch_labels_details.json exists for the case, THE Image_Evidence_API SHALL use label data as the base for image records; WHEN label data does not exist, THE Image_Evidence_API SHALL fall back to listing extracted images from S3 (capped at 5000).
6. THE Image_Evidence_API SHALL merge face crop metadata and face match results into each image record, resolving matched entity names from face_match_results.json.

### Requirement 5: Image Evidence Gallery Frontend [IMPLEMENTED]

**User Story:** As an investigator, I want to see matched face images and other detected faces in the entity drill-down panel, so that I can visually confirm entity appearances across case documents.

#### Acceptance Criteria

1. WHEN a person entity is selected in the drill-down panel, THE Image_Evidence_Gallery SHALL display matched face crop thumbnails for that entity using presigned S3 URLs.
2. THE Image_Evidence_Gallery SHALL display face crop thumbnails with entity name labels and similarity confidence scores.
3. THE Image_Evidence_Gallery SHALL appear within the investigator.html drill-down panel as a dedicated section for person-type entities.

### Requirement 6: Entity Photo Resolution with Priority [IMPLEMENTED]

**User Story:** As an investigator, I want entity photos on the knowledge graph to use pipeline-generated face crops when available and fall back to demo photos, so that the graph always shows the most accurate visual representation.

#### Acceptance Criteria

1. THE Entity_Photo_Service SHALL resolve entity photos with priority: pipeline-generated primary_thumbnail.jpg takes precedence over demo photos.
2. THE Entity_Photo_Service SHALL download resolved photos from S3 and return base64 data URIs for direct embedding in vis.js graph nodes.
3. THE Entity_Photo_Service SHALL return entity_metadata for each entity including the photo source (pipeline or demo) and face_crop_count.

### Requirement 7: Neptune Graph Loading of Rekognition Label Data [NOT YET IMPLEMENTED]

**User Story:** As an investigator, I want Rekognition-detected visual entities (persons, objects, artifacts) loaded into the Neptune knowledge graph, so that visual evidence is connected to the document network and discoverable through graph traversal.

#### Acceptance Criteria

1. WHEN batch label results exist at `cases/{case_id}/rekognition-artifacts/batch_labels_details.json`, THE Graph_Loader SHALL read the label data and create Visual_Entity nodes for each unique investigative label detected across all images.
2. THE Graph_Loader SHALL create DETECTED_IN_Edge edges linking each Visual_Entity node to the source document node where the label was detected, using the source_document_id extracted from the image filename.
3. THE Graph_Loader SHALL create co-occurrence edges between Visual_Entity nodes that appear in images from the same source document.
4. THE Graph_Loader SHALL generate Neptune bulk-load CSV files (nodes CSV and edges CSV) and upload them to `neptune-bulk-load/{case_id}/` in S3_Bucket.
5. WHEN a Neptune endpoint and IAM role are configured, THE Graph_Loader SHALL trigger the Neptune bulk loader API and poll for completion status.
6. THE Graph_Loader SHALL assign entity types based on label categories: person labels map to type "person", vehicle labels map to type "vehicle", document labels map to type "document", weapon labels map to type "weapon", and other investigative labels map to type "artifact".
7. IF the Neptune bulk load fails, THEN THE Graph_Loader SHALL log the failure status and the load ID for debugging.

### Requirement 8: Full-Scale Image Processing Pipeline [NOT YET IMPLEMENTED]

**User Story:** As an investigator, I want all 15,791 extracted images in the main case to be fully processed through Rekognition and the results synced to the combined case, so that the complete visual evidence corpus is available for analysis.

#### Acceptance Criteria

1. WHEN the full-scale processing run completes for Main_Case, THE Rekognition_Pipeline SHALL have processed all 15,791 extracted images through detect_labels and saved complete results to S3.
2. WHEN full-scale results are available for Main_Case, THE Rekognition_Pipeline SHALL sync the batch_labels_summary.json and batch_labels_details.json artifacts to the Combined_Case path in S3_Bucket.
3. WHEN full-scale face detection results are available, THE Face_Cropper SHALL crop all newly detected faces and upload thumbnails to both Main_Case and Combined_Case paths.
4. THE Rekognition_Pipeline SHALL use the Label_Detector resume capability to continue from the last processed image if a previous run was interrupted.

### Requirement 9: Scalable Face Matching [NOT YET IMPLEMENTED]

**User Story:** As an investigator, I want face matching to scale as new entities are identified, so that newly discovered persons of interest are automatically matched against the full corpus of face crops.

#### Acceptance Criteria

1. WHEN new entity photos are added to the known entities folder, THE Face_Matcher SHALL support re-running against all unidentified crops plus any crops not yet compared against the new entities.
2. THE Face_Matcher SHALL track which entity-crop comparisons have already been performed and skip duplicate comparisons on re-runs.
3. WHEN new face crops are generated from full-scale processing, THE Face_Matcher SHALL include the new crops in the next matching run.
4. THE Face_Matcher SHALL update face_match_results.json with cumulative results across multiple matching runs, preserving previous match data.
