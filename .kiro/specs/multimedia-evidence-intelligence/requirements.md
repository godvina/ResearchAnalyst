# Requirements Document

## Introduction

The Multimedia Evidence Intelligence feature adds visual, video, and audio analysis capabilities to the investigative platform. It extends the existing Rekognition handler to crop and store face thumbnails, introduces a tiered video intelligence pipeline, integrates Amazon Transcribe for audio/speech analysis, and provides a unified media-type routing system in the ingestion pipeline. A demo-ready face photo system provides immediate value for the Epstein case investigation wall while the full automated pipeline is built out.

## Glossary

- **Ingestion_Pipeline**: The Step Functions orchestration that processes uploaded evidence files through parsing, extraction, embedding, Rekognition, and graph loading stages
- **Rekognition_Handler**: The Lambda function (`rekognition_handler.py`) that runs Amazon Rekognition APIs on image and video files to detect faces, labels, text, and watchlist matches
- **Face_Crop_Service**: The component responsible for extracting face bounding box regions from source images, resizing to thumbnails, and storing in S3
- **Entity_Photo_API**: The API endpoint that returns a mapping of entity names to presigned S3 URLs for face thumbnail images
- **Video_Analyzer**: The component that orchestrates tiered Rekognition video analysis (label detection, face detection, celebrity recognition, content moderation, key frame extraction)
- **Audio_Transcriber**: The component that integrates Amazon Transcribe for speech-to-text conversion with speaker diarization on audio and video files
- **Media_Router**: The ingestion pipeline component that classifies incoming files by media type (image, video, audio, document) and routes them to the appropriate processing handler
- **Knowledge_Graph**: The vis-network graph visualization in `investigator.html` that displays entity nodes and relationship edges
- **Neptune_Graph**: The Amazon Neptune graph database storing entity vertices and relationship edges
- **OpenSearch_Index**: The OpenSearch Serverless collection used for semantic search across document text and transcripts
- **Presigned_URL**: A time-limited S3 URL generated server-side that grants temporary read access to a private S3 object
- **Face_Thumbnail**: A 100x100px JPEG image cropped from a source evidence image at a detected face bounding box location
- **Investigative_Label**: A Rekognition-detected object category relevant to investigations (weapons, vehicles, currency, drugs, documents, electronics)
- **Speaker_Diarization**: The process of partitioning an audio stream into segments labeled by speaker identity (Speaker 0, Speaker 1, etc.)
- **Key_Frame**: A still image extracted from a video at a specific timestamp flagged as investigatively relevant
- **Demo_Photo_Set**: A curated collection of public domain or Creative Commons licensed photographs of known persons, stored in S3 for immediate demo use

## Requirements

### Requirement 1: Face Crop Pipeline During Rekognition Processing

**User Story:** As an investigator, I want the system to automatically crop and store face thumbnails when processing evidence images, so that identified persons can be displayed with their actual face on the investigation knowledge graph.

#### Acceptance Criteria

1. WHEN the Rekognition_Handler detects a face with confidence >= 90% in a source image, THE Face_Crop_Service SHALL crop the bounding box region from the source image and save a 100x100px JPEG thumbnail
2. THE Face_Crop_Service SHALL store each Face_Thumbnail at the S3 path `cases/{case_id}/face-crops/{entity_name}/{hash}.jpg` where `{hash}` is derived from the source image key and bounding box coordinates
3. WHEN multiple faces are detected in a single source image, THE Face_Crop_Service SHALL produce one Face_Thumbnail per detected face
4. WHEN multiple Face_Thumbnails exist for the same entity, THE Face_Crop_Service SHALL select the highest-confidence crop as the primary thumbnail and store a `primary_thumbnail.jpg` copy
5. THE Face_Crop_Service SHALL store the S3 key of the primary Face_Thumbnail as a `face_thumbnail_s3_key` vertex property on the corresponding person entity node in the Neptune_Graph
6. IF the source image cannot be read or the crop region is invalid, THEN THE Face_Crop_Service SHALL log a warning and continue processing remaining faces without failing the pipeline step

### Requirement 2: Entity Photo API

**User Story:** As a frontend developer, I want an API endpoint that returns entity-to-photo URL mappings, so that the knowledge graph can display real face photos on person nodes.

#### Acceptance Criteria

1. THE Entity_Photo_API SHALL expose a `GET /case-files/{case_id}/entity-photos` endpoint that returns a JSON mapping of entity names to Presigned_URLs for their primary Face_Thumbnails
2. THE Entity_Photo_API SHALL generate Presigned_URLs with a 1-hour expiration time
3. WHEN no Face_Thumbnail exists for a given entity, THE Entity_Photo_API SHALL omit that entity from the response (not return a null or empty URL)
4. THE Entity_Photo_API SHALL also check for demo photos in the `face-crops/demo/` S3 prefix and include them in the response when no pipeline-generated crop exists for that entity
5. THE Entity_Photo_API SHALL return the response within 2 seconds for cases with up to 100 entity photos
6. THE Knowledge_Graph SHALL call the Entity_Photo_API on graph load and use returned Presigned_URLs for `circularImage` node rendering when the photo display mode is active

### Requirement 3: Demo Face Photo Setup

**User Story:** As a demo presenter, I want pre-loaded face photos of key Epstein case persons available immediately, so that the investigation wall displays real photos without waiting for the full automated pipeline.

#### Acceptance Criteria

1. THE Demo_Photo_Set SHALL include public domain or Creative Commons licensed photographs for the following persons: Jeffrey Epstein, Ghislaine Maxwell, Prince Andrew, Bill Clinton, Donald Trump, Alan Dershowitz, Les Wexner, Jean-Luc Brunel
2. THE Demo_Photo_Set photographs SHALL be downloaded from the URLs specified in `data/entity_photos.json`, resized to 200x200px JPEG, and uploaded to S3 at `cases/{case_id}/face-crops/demo/{entity_name}.jpg`
3. A setup script SHALL automate the download, resize, and S3 upload process for the Demo_Photo_Set, accepting a case_id parameter
4. THE Entity_Photo_API SHALL serve Demo_Photo_Set images via Presigned_URLs identically to pipeline-generated Face_Thumbnails
5. WHEN both a Demo_Photo_Set image and a pipeline-generated Face_Thumbnail exist for the same entity, THE Entity_Photo_API SHALL prefer the pipeline-generated Face_Thumbnail

### Requirement 4: Video Intelligence — Tier 1 Automated Triage

**User Story:** As an investigator, I want video evidence to be automatically scanned for investigatively relevant content, so that I can quickly identify which videos deserve deeper analysis without watching every file manually.

#### Acceptance Criteria

1. WHEN a video file (.mp4, .mov) enters the Ingestion_Pipeline, THE Video_Analyzer SHALL run Rekognition `StartLabelDetection` and `StartFaceDetection` on the video
2. THE Video_Analyzer SHALL filter detected labels to Investigative_Labels (persons, weapons, vehicles, documents, currency, electronics) and record their timestamps with confidence scores
3. THE Video_Analyzer SHALL store Tier 1 results as structured JSON at `cases/{case_id}/video-analysis/{filename}_tier1.json` containing timestamp ranges, detected labels, face count per segment, and confidence scores
4. THE Video_Analyzer SHALL create a summary record in the Neptune_Graph linking the video document entity to detected Investigative_Labels with timestamp metadata on the edges
5. IF Rekognition `StartLabelDetection` or `StartFaceDetection` fails for a video, THEN THE Video_Analyzer SHALL log the error, mark the video as `triage_failed` in the analysis metadata, and continue processing other videos

### Requirement 5: Video Intelligence — Tier 2 On-Demand Deep Dive

**User Story:** As an investigator, I want to trigger deeper analysis on specific flagged videos, so that I can get celebrity recognition, content moderation flags, and key frame extractions for videos that appear relevant.

#### Acceptance Criteria

1. WHEN an investigator clicks "Analyze Deeper" on a Tier 1 flagged video, THE Video_Analyzer SHALL run Rekognition `StartCelebrityRecognition` and `StartContentModeration` on that video
2. THE Video_Analyzer SHALL extract Key_Frames at each timestamp flagged during Tier 1 analysis and store them as JPEG images in S3 at `cases/{case_id}/video-keyframes/{filename}/{timestamp_ms}.jpg`
3. THE Video_Analyzer SHALL store Tier 2 results at `cases/{case_id}/video-analysis/{filename}_tier2.json` containing celebrity matches, moderation labels, and key frame S3 keys with timestamps
4. THE Video_Analyzer SHALL link Key_Frame images to the video entity in the Neptune_Graph with timestamp metadata on the edges
5. WHEN a celebrity is recognized in the video, THE Video_Analyzer SHALL create or update the corresponding person entity in the Neptune_Graph and add an edge to the video document entity with the timestamp range

### Requirement 6: Video Intelligence — Tier 3 Human Review Interface

**User Story:** As an investigator, I want to review flagged video segments with AI annotations and playback controls, so that I can efficiently verify AI findings and make investigative decisions.

#### Acceptance Criteria

1. THE Knowledge_Graph frontend SHALL present flagged video segments with start and end timestamps, detected labels, and confidence scores in a review panel
2. THE review panel SHALL provide video playback controls that allow the investigator to play just the flagged segment (start timestamp to end timestamp) rather than the entire video
3. THE review panel SHALL overlay AI-generated annotations (detected labels, celebrity names, moderation flags) synchronized with the video playback position
4. WHEN an investigator marks a video segment as "confirmed relevant", THE system SHALL update the Neptune_Graph edge metadata to include the investigator confirmation and timestamp
5. THE review panel SHALL support keyboard navigation: spacebar for play/pause, left/right arrows for 5-second skip, and number keys 1-9 to jump to flagged segments

### Requirement 7: Audio Intelligence — Transcription

**User Story:** As an investigator, I want audio and video files to be automatically transcribed with speaker identification, so that I can search spoken content and identify who said what in evidence recordings.

#### Acceptance Criteria

1. WHEN an audio file (.mp3, .wav, .m4a) or video file (.mp4, .mov) enters the Ingestion_Pipeline, THE Audio_Transcriber SHALL submit the file to Amazon Transcribe for speech-to-text conversion
2. THE Audio_Transcriber SHALL enable Speaker_Diarization with a maximum of 10 speakers per file
3. THE Audio_Transcriber SHALL store the raw Transcribe output JSON at `cases/{case_id}/transcripts/{filename}_transcript.json`
4. THE Audio_Transcriber SHALL parse the Transcribe output into a structured transcript with speaker labels, start/end timestamps per segment, and the transcribed text
5. THE Audio_Transcriber SHALL store the structured transcript at `cases/{case_id}/transcripts/{filename}_structured.json`
6. IF Amazon Transcribe fails or returns an error for a file, THEN THE Audio_Transcriber SHALL log the error, mark the file as `transcription_failed` in metadata, and continue processing other files

### Requirement 8: Audio Intelligence — Search and Graph Integration

**User Story:** As an investigator, I want transcribed speech indexed for search and linked to the knowledge graph, so that I can find spoken references to entities and discover connections across audio evidence.

#### Acceptance Criteria

1. THE Audio_Transcriber SHALL index each transcript segment (speaker + text + timestamps) in the OpenSearch_Index alongside document text, enabling semantic search across spoken content
2. WHEN a known entity name is mentioned in a transcript segment, THE Audio_Transcriber SHALL create an edge in the Neptune_Graph linking the audio/video document entity to the mentioned entity with the speaker label and timestamp range as edge properties
3. THE Audio_Transcriber SHALL flag transcript segments where two or more key entities are mentioned within the same speaker turn or within a 30-second window as high-priority investigative leads
4. THE Audio_Transcriber SHALL store flagged co-occurrence segments at `cases/{case_id}/transcripts/{filename}_flags.json` with the entity names, speaker labels, timestamps, and the transcribed text of the segment
5. THE Knowledge_Graph frontend SHALL display a transcript viewer with speaker labels, timestamps, and clickable segments that jump to the corresponding audio/video playback position

### Requirement 9: Media Type Routing in Ingestion Pipeline

**User Story:** As a platform operator, I want the ingestion pipeline to automatically detect file types and route them to the appropriate processing handler, so that images, videos, audio files, and documents each receive specialized analysis.

#### Acceptance Criteria

1. THE Media_Router SHALL classify each incoming file by extension into one of four categories: image (.jpg, .jpeg, .png, .tiff, .tif), video (.mp4, .mov), audio (.mp3, .wav, .m4a), or document (all other extensions)
2. WHEN a file is classified as image, THE Media_Router SHALL route the file to the Rekognition_Handler for face detection, label detection, text detection, and the Face_Crop_Service for thumbnail generation
3. WHEN a file is classified as video, THE Media_Router SHALL route the file to the Video_Analyzer for Tier 1 automated triage and to the Audio_Transcriber for speech-to-text extraction
4. WHEN a file is classified as audio, THE Media_Router SHALL route the file to the Audio_Transcriber for speech-to-text extraction with Speaker_Diarization
5. WHEN a file is classified as document, THE Media_Router SHALL route the file to the existing text extraction pipeline (parse, extract entities, embed)
6. THE Media_Router SHALL record the classified media type as metadata on the document record for downstream processing steps to reference
7. IF a file extension is not recognized, THEN THE Media_Router SHALL default to the document processing path and log a warning with the unrecognized extension

### Requirement 10: Presigned URL Security and Expiration

**User Story:** As a security-conscious platform operator, I want face thumbnails and media assets served through time-limited presigned URLs, so that evidence images are not publicly accessible and access is controlled.

#### Acceptance Criteria

1. THE Entity_Photo_API SHALL generate Presigned_URLs using AWS SigV4 signing with a configurable expiration time (default: 3600 seconds)
2. THE Entity_Photo_API SHALL generate Presigned_URLs scoped to the specific S3 object key, preventing path traversal to other case files
3. WHEN a Presigned_URL expires, THE Knowledge_Graph frontend SHALL detect the 403 response and re-fetch entity photos from the Entity_Photo_API to obtain fresh URLs
4. THE system SHALL log each Presigned_URL generation event with the requesting user identity, entity name, and S3 key for audit purposes
