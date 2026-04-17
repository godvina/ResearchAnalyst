# Requirements Document

## Introduction

This feature extends the ingestion pipeline to extract embedded images from PDF documents during the parsing step, feed those images through the existing Rekognition analysis path, and crop detected faces into thumbnails for the investigation wall. Currently, the pipeline only extracts text from PDFs — embedded photographs, scanned pages, and inline images are discarded. By extracting images during the existing `ParseDocument` step, saving them to S3, and wiring them into the Rekognition and face-crop pipeline stages, investigators gain automatic visual intelligence from PDF evidence without any manual image extraction.

## Glossary

- **Document_Parser**: The service (`document_parser.py`) that converts raw uploaded files into structured `ParsedDocument` representations during the `ParseDocument` step of the Ingestion_Pipeline
- **PDF_Image_Extractor**: The component within Document_Parser responsible for detecting and extracting embedded images from PDF files using PyMuPDF (fitz)
- **Ingestion_Pipeline**: The Step Functions orchestration (`ingestion_pipeline.json`) that processes uploaded evidence files through parsing, extraction, embedding, Rekognition, and graph loading stages
- **Rekognition_Handler**: The Lambda function (`rekognition_handler.py`) that runs Amazon Rekognition APIs on image files under a case's S3 prefix to detect faces, labels, text, and watchlist matches
- **Face_Crop_Service**: The service that crops face bounding box regions from source images, resizes to thumbnails, and stores in S3 for the investigation wall (defined in the multimedia-evidence-intelligence spec)
- **FaceCropStep**: The Step Functions state that runs after RekognitionStep to produce face thumbnails from Rekognition detections
- **Extracted_Image**: An image embedded within a PDF file that has been extracted and saved as a standalone file (JPEG or PNG) in S3
- **S3_Data_Lake**: The S3 bucket storing all case evidence, structured as `cases/{case_id}/` with sub-prefixes for raw files, processed output, extractions, and extracted images
- **Investigation_Wall**: The vis-network knowledge graph visualization in `investigator.html` that displays entity nodes with optional face photo rendering
- **Neptune_Graph**: The Amazon Neptune graph database storing entity vertices and relationship edges
- **Parse_Result**: The output of the `ParseDocument` step, containing `raw_text`, `sections`, `source_metadata`, and now `extracted_images` metadata

## Requirements

### Requirement 1: Extract Embedded Images from PDF Files During Parsing

**User Story:** As an investigator, I want embedded images automatically extracted from PDF evidence files during ingestion, so that photographs, scanned pages, and inline graphics within PDFs are available for visual analysis without manual extraction.

#### Acceptance Criteria

1. WHEN the Document_Parser processes a PDF file, THE PDF_Image_Extractor SHALL iterate over each page and extract all embedded images using PyMuPDF (fitz)
2. THE PDF_Image_Extractor SHALL save each Extracted_Image as a standalone file (JPEG for photographic content, PNG for graphics with transparency) to S3 at the path `cases/{case_id}/extracted-images/{document_id}_page{page_num}_img{img_index}.{ext}`
3. THE PDF_Image_Extractor SHALL skip images smaller than 50x50 pixels to filter out decorative elements, icons, and line-art artifacts
4. THE PDF_Image_Extractor SHALL record metadata for each Extracted_Image in the Parse_Result, including the source page number, image dimensions, file size in bytes, and the S3 key where the image was stored
5. WHEN a PDF page contains no extractable images, THE PDF_Image_Extractor SHALL continue to the next page without error
6. IF PyMuPDF fails to open or read a PDF file, THEN THE PDF_Image_Extractor SHALL fall back to text-only extraction using the existing parser logic and log a warning with the document_id and error reason
7. THE PDF_Image_Extractor SHALL process PDF files within the existing ParseDocument Lambda timeout by extracting images concurrently with text extraction in the same page iteration loop

### Requirement 2: Store Extracted Images in S3 with Consistent Layout

**User Story:** As a platform operator, I want extracted PDF images stored in a predictable S3 prefix structure, so that downstream pipeline steps (Rekognition, face cropping) can discover and process them reliably.

#### Acceptance Criteria

1. THE PDF_Image_Extractor SHALL store all Extracted_Images under the S3 prefix `cases/{case_id}/extracted-images/`
2. THE PDF_Image_Extractor SHALL name each Extracted_Image file using the pattern `{document_id}_page{page_num}_img{img_index}.{ext}` where page_num is zero-indexed and img_index is the sequential image number on that page
3. THE PDF_Image_Extractor SHALL set the S3 Content-Type header to `image/jpeg` for JPEG files and `image/png` for PNG files
4. THE Parse_Result SHALL include an `extracted_images` field containing a list of objects, each with keys: `s3_key`, `page_num`, `width`, `height`, `file_size_bytes`, and `source_document_id`
5. WHEN no images are extracted from a PDF, THE Parse_Result SHALL include an empty `extracted_images` list rather than omitting the field

### Requirement 3: Feed Extracted Images into Rekognition Analysis

**User Story:** As an investigator, I want extracted PDF images automatically analyzed by Rekognition for face detection, label detection, and text detection, so that persons and objects in PDF evidence are identified and added to the knowledge graph.

#### Acceptance Criteria

1. THE Rekognition_Handler SHALL scan the `cases/{case_id}/extracted-images/` S3 prefix in addition to the existing media file prefixes when listing files for analysis
2. WHEN the Rekognition_Handler discovers Extracted_Images in the `extracted-images/` prefix, THE Rekognition_Handler SHALL process each image using the same `detect_faces`, `detect_labels`, and `detect_text` APIs used for directly uploaded images
3. THE Rekognition_Handler SHALL include Extracted_Images in the results artifact JSON alongside results from directly uploaded media files
4. THE Rekognition_Handler SHALL tag each result from an Extracted_Image with the `source_document_id` parsed from the filename, enabling traceability back to the originating PDF
5. IF an Extracted_Image is corrupt or unreadable by Rekognition, THEN THE Rekognition_Handler SHALL log a warning and continue processing remaining images

### Requirement 4: Crop Faces from PDF-Extracted Images for the Investigation Wall

**User Story:** As an investigator, I want faces detected in PDF-extracted images automatically cropped and available on the investigation wall, so that persons appearing in PDF evidence (court filings, reports, scanned photos) are visually represented in the knowledge graph.

#### Acceptance Criteria

1. THE Face_Crop_Service SHALL process face detections from Extracted_Images identically to face detections from directly uploaded images, producing 100x100px JPEG thumbnails
2. THE Face_Crop_Service SHALL store face crops from Extracted_Images at the same S3 path pattern `cases/{case_id}/face-crops/{entity_name}/{hash}.jpg` used for all other face crops
3. WHEN a face detected in an Extracted_Image matches a watchlist entity, THE Face_Crop_Service SHALL associate the crop with that entity and update the `face_thumbnail_s3_key` property on the corresponding Neptune_Graph vertex
4. THE FaceCropStep in the Ingestion_Pipeline SHALL receive Extracted_Image face detections as part of the standard Rekognition result payload without requiring separate invocation

### Requirement 5: Build FaceCropService for Bounding Box Cropping

**User Story:** As a platform developer, I want a reusable FaceCropService that crops face regions from any source image using Rekognition bounding box coordinates, so that face thumbnails are generated consistently across all image sources (uploaded photos, PDF extractions, video key frames).

#### Acceptance Criteria

1. THE Face_Crop_Service SHALL accept a source image (as S3 key or raw bytes) and a Rekognition bounding box dict (with normalized Width, Height, Left, Top values between 0.0 and 1.0) and return cropped JPEG bytes resized to 100x100 pixels
2. THE Face_Crop_Service SHALL clamp bounding box coordinates that exceed image boundaries (Left+Width > 1.0 or Top+Height > 1.0) to the image edge rather than raising an error
3. THE Face_Crop_Service SHALL compute a deterministic hash from the source S3 key and bounding box coordinates to generate the output filename, ensuring the same face detection always produces the same crop path
4. WHEN multiple crops exist for the same entity, THE Face_Crop_Service SHALL select the crop with the highest Rekognition confidence as the primary thumbnail and copy it to `primary_thumbnail.jpg`
5. THE Face_Crop_Service SHALL use Pillow (PIL) for image manipulation, accepting JPEG, PNG, and TIFF input formats
6. IF the source image cannot be downloaded from S3 or is corrupt, THEN THE Face_Crop_Service SHALL log a warning with the S3 key and skip that crop without failing the batch

### Requirement 6: Wire FaceCropStep into Step Functions After Rekognition

**User Story:** As a platform developer, I want the FaceCropStep added to the Step Functions pipeline after the RekognitionStep, so that face cropping runs automatically as part of every ingestion that includes Rekognition analysis.

#### Acceptance Criteria

1. THE Ingestion_Pipeline SHALL include a `FaceCropStep` state that executes after `RekognitionStep` and before `ChooseGraphLoadStrategy`
2. THE FaceCropStep SHALL receive the `case_id`, `rekognition_result`, and `effective_config` from the pipeline state and pass them to the Face_Crop_Service Lambda handler
3. IF the FaceCropStep fails for any reason, THEN THE Ingestion_Pipeline SHALL catch the error, store it in `$.face_crop_error`, and continue to `ChooseGraphLoadStrategy` without failing the pipeline
4. WHEN Rekognition is disabled in the effective config, THE Ingestion_Pipeline SHALL skip both the RekognitionStep and the FaceCropStep
5. THE FaceCropStep SHALL have a timeout of 300 seconds and retry up to 2 times on transient Lambda failures with exponential backoff

### Requirement 7: Pipeline Observability for Image Extraction

**User Story:** As a platform operator, I want visibility into how many images were extracted from PDFs and how they flowed through Rekognition and face cropping, so that I can monitor pipeline health and debug extraction issues.

#### Acceptance Criteria

1. THE Parse_Result SHALL include an `image_extraction_summary` object containing: `total_pages_scanned`, `total_images_found`, `images_saved`, `images_skipped_too_small`, and `extraction_errors`
2. THE Rekognition_Handler return payload SHALL include an `extracted_image_count` field indicating how many Extracted_Images from the `extracted-images/` prefix were processed
3. THE FaceCropStep return payload SHALL include `crops_from_extracted_images` count alongside the existing `crops_created` count
4. IF image extraction encounters errors on specific pages, THEN THE PDF_Image_Extractor SHALL log each error with the document_id, page number, and error message, and include the count in `extraction_errors`
