# Requirements Document

## Introduction

The Smart Image Triage and Face Pipeline addresses a critical usability problem: the Evidence Library currently displays all 15,291 extracted images for the Epstein case with no filtering. The vast majority of these images are PDF page extractions — redacted court documents, legal filings, and text-heavy pages — not actual photographs. This feature adds a batch image classification pipeline that uses Pillow-based heuristics (entropy, color variance, edge density) to classify each extracted image as "photograph", "document_page", "redacted_text", or "blank". The Evidence Library then defaults to showing only photographs, reducing the visible set from ~15,000 to a few hundred actionable images. On top of this filtered set, the feature runs Rekognition face detection only on photographs (saving API costs), crops detected faces, and matches them against known entity demo photos to link identified persons to evidence images.

## Glossary

- **Image_Classifier**: The batch script that downloads extracted images from S3, analyzes visual properties using Pillow, and assigns each image a classification category.
- **Classification_Category**: One of four labels assigned to each extracted image: "photograph" (real photo with people, scenes, objects), "document_page" (text-heavy page with structured layout), "redacted_text" (heavily redacted page with black bars), or "blank" (mostly white/empty page).
- **Image_Entropy**: A measure of information density in an image computed from the histogram of pixel values. Low entropy indicates uniform content (blank or redacted); high entropy indicates varied visual content.
- **Color_Variance**: The standard deviation of pixel values across color channels, measuring how colorful or monotone an image is. Document pages and redacted text have low color variance; photographs have high color variance.
- **Edge_Density**: The ratio of edge pixels to total pixels detected via a Sobel or similar edge filter, measuring structural layout density. Document pages with text lines have high edge density relative to their low color variance.
- **Classification_Artifact**: The JSON file stored in S3 at `cases/{case_id}/rekognition-artifacts/image_classification.json` containing the classification result for every extracted image.
- **Image_Evidence_Handler**: The existing `GET /case-files/{id}/image-evidence` endpoint in `case_files.py` that returns paginated image records for the Evidence Library.
- **Face_Detection_Pipeline**: The batch process that runs Rekognition `detect_faces` on photograph-classified images only, producing face bounding box metadata.
- **Face_Cropper**: The batch process that crops detected face regions from source photographs, resizes to 200x200 JPEG thumbnails, and uploads to S3.
- **Face_Matcher**: The batch process that compares cropped face thumbnails against known entity demo photos using Rekognition `compare_faces` and records match results.
- **Known_Entity_Photos**: Demo photographs stored at `cases/{case_id}/face-crops/demo/{entity_name}.jpg` used as reference images for face matching.
- **S3_Bucket**: research-analyst-data-lake-974220725866, the data lake bucket storing all case artifacts.
- **Main_Case**: Case 7f05e8d5-4492-4f19-8894-25367606db96 containing 15,291 extracted images.
- **Combined_Case**: Case ed0b6c27-3b6b-4255-b9d0-efe8f4383a99, the UI-facing case that aggregates results.
- **Evidence_Library**: The frontend Evidence tab in investigator.html that displays a browsable grid of evidence images.
- **Graph_Connection_Panel**: The section within the Evidence Detail Modal that shows entity connections for an evidence item.

## Requirements

### Requirement 1: Batch Image Classification Script

**User Story:** As an investigator, I want extracted images automatically classified by visual content type, so that I can focus on actual photographs instead of scrolling through thousands of document page extractions.

#### Acceptance Criteria

1. WHEN the Image_Classifier script is run for a case, THE Image_Classifier SHALL list all extracted images under `cases/{case_id}/extracted-images/` in S3_Bucket and download each image for analysis.
2. THE Image_Classifier SHALL compute Image_Entropy, Color_Variance, and Edge_Density for each downloaded image using Pillow image analysis functions.
3. WHEN Image_Entropy is below 2.0, THE Image_Classifier SHALL assign the Classification_Category "blank" to that image.
4. WHEN Image_Entropy is below 4.0 AND Color_Variance is below 20, THE Image_Classifier SHALL assign the Classification_Category "redacted_text" to that image.
5. WHEN Color_Variance is below 30 AND Edge_Density is above 0.3, THE Image_Classifier SHALL assign the Classification_Category "document_page" to that image.
6. WHEN an image does not match any of the above threshold conditions, THE Image_Classifier SHALL assign the Classification_Category "photograph" to that image.
7. THE Image_Classifier SHALL evaluate classification rules in priority order: blank first, then redacted_text, then document_page, then photograph as the default.
8. WHEN classification completes, THE Image_Classifier SHALL save the Classification_Artifact to `cases/{case_id}/rekognition-artifacts/image_classification.json` containing each image S3 key, its Classification_Category, and the computed metrics (entropy, color_variance, edge_density).
9. THE Image_Classifier SHALL include a summary section in the Classification_Artifact with counts per Classification_Category and total images processed.
10. THE Image_Classifier SHALL accept `--case-id`, `--limit`, and `--dry-run` CLI arguments, and support resume from a local progress file so that interrupted runs continue from the last processed image index.
11. IF an image cannot be downloaded or analyzed, THEN THE Image_Classifier SHALL log a warning, increment an error counter, and continue processing remaining images.
12. THE Image_Classifier SHALL also copy the Classification_Artifact to the Combined_Case path in S3_Bucket when a `--target-case` argument is provided.

### Requirement 2: Evidence Library Default Filter by Classification

**User Story:** As an investigator, I want the Evidence Library to show only actual photographs by default, so that I see a manageable set of relevant images instead of all 15,291 extracted pages.

#### Acceptance Criteria

1. WHEN the Classification_Artifact exists for a case, THE Image_Evidence_Handler SHALL load the classification data and use it to filter image records.
2. WHEN no `classification` query parameter is provided, THE Image_Evidence_Handler SHALL default to returning only images classified as "photograph".
3. WHEN a `classification` query parameter is provided with a valid Classification_Category value, THE Image_Evidence_Handler SHALL return only images matching that category.
4. WHEN the `classification` query parameter is set to "all", THE Image_Evidence_Handler SHALL return images of all Classification_Categories without filtering.
5. THE Image_Evidence_Handler SHALL include the Classification_Category in each image record returned to the frontend.
6. THE Image_Evidence_Handler SHALL include classification summary counts (photograph count, document_page count, redacted_text count, blank count) in the response summary statistics.
7. WHEN the Classification_Artifact does not exist for a case, THE Image_Evidence_Handler SHALL return all images without classification filtering, maintaining backward compatibility.

### Requirement 3: Evidence Library Classification Toggle UI

**User Story:** As an investigator, I want a toggle in the Evidence Library to switch between viewing only photographs and viewing all images, so that I can access document pages when needed while defaulting to the useful photo view.

#### Acceptance Criteria

1. THE Evidence_Library SHALL display a classification filter control with options: "Photos Only" (default active), "Documents", "Redacted", "Blank", and "All".
2. WHEN the investigator selects "Photos Only", THE Evidence_Library SHALL request images with `classification=photograph` from the Image_Evidence_Handler.
3. WHEN the investigator selects "All", THE Evidence_Library SHALL request images with `classification=all` from the Image_Evidence_Handler.
4. WHEN the investigator selects "Documents", THE Evidence_Library SHALL request images with `classification=document_page` from the Image_Evidence_Handler.
5. THE classification filter control SHALL display the count of images in each category using data from the response summary classification counts.
6. THE classification filter control SHALL use the same dark theme styling as existing filter controls in the Evidence Library.

### Requirement 4: Face Detection on Photographs Only

**User Story:** As a platform operator, I want face detection to run only on photograph-classified images, so that Rekognition API costs are minimized and false positives from text-heavy document pages are avoided.

#### Acceptance Criteria

1. WHEN the Face_Detection_Pipeline script is run for a case, THE Face_Detection_Pipeline SHALL load the Classification_Artifact and select only images classified as "photograph".
2. FOR EACH photograph-classified image, THE Face_Detection_Pipeline SHALL call Rekognition `detect_faces` with the image S3 key and store the detected face bounding boxes, confidence scores, and facial attributes.
3. WHEN face detection completes, THE Face_Detection_Pipeline SHALL save face detection results to `cases/{case_id}/rekognition-artifacts/face_detection_results.json` containing each image S3 key, detected faces with bounding boxes, confidence scores, gender estimates, and age range estimates.
4. THE Face_Detection_Pipeline SHALL save face crop metadata to `cases/{case_id}/rekognition-artifacts/face_crop_metadata.json` in the same format consumed by the existing Face_Cropper script.
5. THE Face_Detection_Pipeline SHALL accept `--case-id`, `--threshold` (minimum confidence, default 80), `--limit`, and `--dry-run` CLI arguments.
6. THE Face_Detection_Pipeline SHALL rate-limit Rekognition calls with a 100ms delay between API calls to avoid throttling.
7. IF a Rekognition `detect_faces` call fails for a single image, THEN THE Face_Detection_Pipeline SHALL log the error, increment an error counter, and continue processing remaining images.
8. THE Face_Detection_Pipeline SHALL log the number of photographs processed, total faces detected, and images skipped due to non-photograph classification.

### Requirement 5: Face Cropping from Detected Photographs

**User Story:** As an investigator, I want detected faces cropped from photographs as individual thumbnails, so that I can visually identify persons appearing in evidence photos.

#### Acceptance Criteria

1. WHEN face crop metadata exists at `cases/{case_id}/rekognition-artifacts/face_crop_metadata.json`, THE Face_Cropper SHALL download each source photograph, crop the face region using the bounding box coordinates with 30% padding, and resize to a 200x200 JPEG thumbnail.
2. THE Face_Cropper SHALL upload each cropped thumbnail to `cases/{case_id}/face-crops/unidentified/{crop_filename}.jpg` in S3_Bucket.
3. WHEN a `--target-case` argument is provided, THE Face_Cropper SHALL copy each cropped thumbnail to the corresponding path under the target case ID.
4. IF a source image download fails or the cropped region is smaller than 20x20 pixels, THEN THE Face_Cropper SHALL skip that face, log a warning, and continue processing remaining faces.
5. THE Face_Cropper SHALL log the total number of faces cropped, faces skipped, and errors encountered.

### Requirement 6: Face Matching Against Known Entities

**User Story:** As an investigator, I want cropped faces automatically compared against known entity photos, so that persons of interest appearing in evidence photographs are identified and linked.

#### Acceptance Criteria

1. WHEN face matching is initiated, THE Face_Matcher SHALL list all Known_Entity_Photos under `cases/{case_id}/face-crops/demo/` and all unidentified face crops under `cases/{case_id}/face-crops/unidentified/` in S3_Bucket.
2. FOR EACH unidentified crop, THE Face_Matcher SHALL call Rekognition `compare_faces` against every Known_Entity_Photo and select the entity with the highest similarity score at or above the threshold (default 80%).
3. WHEN a match is found, THE Face_Matcher SHALL copy the crop to `cases/{case_id}/face-crops/{entity_name}/{crop_filename}` in S3_Bucket and to the corresponding path under the Combined_Case.
4. WHEN all crops are processed, THE Face_Matcher SHALL save cumulative match results to `cases/{case_id}/rekognition-artifacts/face_match_results.json` containing matched crops with entity names and similarity scores, unmatched crop list, and threshold used.
5. THE Face_Matcher SHALL track completed comparisons in a local log file and skip already-completed comparisons on re-runs to support incremental matching.
6. IF Rekognition `compare_faces` returns an InvalidParameterException for an image, THEN THE Face_Matcher SHALL skip that comparison and continue processing.
7. THE Face_Matcher SHALL rate-limit `compare_faces` calls with a 100ms delay between comparisons to avoid throttling.

### Requirement 7: Entity Linking in Evidence Library

**User Story:** As an investigator, I want matched entity names displayed on image cards and in the detail modal, so that I can see which known persons appear in each evidence photograph.

#### Acceptance Criteria

1. WHEN face match results exist for a case, THE Image_Evidence_Handler SHALL merge matched entity names into each image record, resolving entity names from `face_match_results.json`.
2. THE Evidence_Library image cards SHALL display matched entity name badges on images where faces have been identified.
3. WHEN an investigator opens the Evidence Detail Modal for an image with matched faces, THE Graph_Connection_Panel SHALL list each matched entity with their face crop thumbnail and similarity confidence score.
4. WHEN an image has multiple matched entities, THE Graph_Connection_Panel SHALL list all matched entities sorted by confidence score descending.
5. WHEN an image has unidentified faces (no match above threshold), THE Graph_Connection_Panel SHALL display those faces with the label "Unidentified" and their face crop thumbnail.

### Requirement 8: Classification Heuristic Accuracy

**User Story:** As a platform operator, I want the image classification heuristics to correctly separate photographs from document pages with reasonable accuracy, so that investigators see relevant photos and do not miss important evidence.

#### Acceptance Criteria

1. THE Image_Classifier SHALL classify images with high color variance (above 30) and moderate-to-high entropy (above 4.0) as "photograph" to capture real photos with people, scenes, and objects.
2. THE Image_Classifier SHALL classify images with low color variance (below 30) and high edge density (above 0.3) as "document_page" to capture text-heavy pages with structured line layouts.
3. THE Image_Classifier SHALL classify images with very low entropy (below 2.0) as "blank" regardless of other metrics, to capture mostly white or empty pages.
4. THE Image_Classifier SHALL classify images with low entropy (below 4.0) and very low color variance (below 20) as "redacted_text" to capture heavily redacted pages with black bars.
5. THE Image_Classifier SHALL compute Color_Variance as the standard deviation of pixel values across the grayscale-converted image.
6. THE Image_Classifier SHALL compute Edge_Density as the ratio of edge pixels (detected via a Sobel-like filter or Pillow edge filter) to total pixels.
7. THE Image_Classifier SHALL compute Image_Entropy using the Pillow Image.entropy() method on the grayscale-converted image.

### Requirement 9: Pipeline Orchestration and Artifact Dependencies

**User Story:** As a platform operator, I want the classification, face detection, face cropping, and face matching scripts to run in a clear sequential order with artifact dependencies, so that each step consumes the output of the previous step.

#### Acceptance Criteria

1. THE Image_Classifier SHALL run first and produce the Classification_Artifact as its output.
2. THE Face_Detection_Pipeline SHALL depend on the Classification_Artifact and run second, producing face_detection_results.json and face_crop_metadata.json.
3. THE Face_Cropper SHALL depend on face_crop_metadata.json and run third, producing cropped face thumbnails in S3.
4. THE Face_Matcher SHALL depend on cropped face thumbnails and Known_Entity_Photos and run fourth, producing face_match_results.json.
5. WHEN any pipeline step fails, THE subsequent steps SHALL still be runnable independently using previously generated artifacts from S3.
6. THE pipeline scripts SHALL all accept a `--case-id` argument to target a specific case and default to Main_Case.
