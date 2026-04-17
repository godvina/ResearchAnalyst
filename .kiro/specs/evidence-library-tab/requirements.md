# Requirements Document

## Introduction

The Evidence Library Tab adds a dedicated "Evidence" tab to the investigator UI (investigator.html) that serves as a centralized browsable evidence library for a selected case. Currently, images only appear in the entity drill-down panel when clicking a person entity. The Evidence Library provides a "war room wall" experience where investigators can browse all physical evidence (images, videos, documents) in a visual grid/gallery, filter by media type and Rekognition labels, view full-size images with label overlays and face bounding boxes, play videos with basic controls, request AI-powered analysis of individual evidence items via Bedrock, and explore graph connections between evidence and entities. The tab consumes the existing `GET /case-files/{id}/image-evidence` API and `GET /case-files/{id}/entity-photos` API, and extends the pattern to video evidence served via presigned S3 URLs.

## Glossary

- **Evidence_Library_Tab**: The new "Evidence" tab in investigator.html that displays a browsable grid/gallery of all evidence items for the selected case.
- **Evidence_Item**: A single piece of evidence displayed in the library — an image, video, or document — with associated metadata (labels, faces, entity connections).
- **Evidence_Grid**: The responsive grid/gallery layout within the Evidence_Library_Tab that displays Evidence_Item thumbnails in a card-based arrangement.
- **Image_Evidence_API**: The existing `GET /case-files/{id}/image-evidence` endpoint that returns paginated image records with Rekognition labels, face data, presigned URLs, and summary statistics.
- **Entity_Photo_API**: The existing `GET /case-files/{id}/entity-photos` endpoint that returns entity-name-to-presigned-URL mappings for face thumbnails.
- **Evidence_Detail_Modal**: The overlay/modal that appears when an investigator clicks an Evidence_Item, showing full-size content with metadata, labels, face data, and entity connections.
- **Label_Filter**: A UI control that allows filtering Evidence_Items by Rekognition-detected Investigative_Labels (weapons, vehicles, persons, documents, currency, electronics).
- **Media_Type_Filter**: A UI control that allows filtering Evidence_Items by media type (images, videos, documents).
- **Summary_Statistics_Bar**: The statistics bar at the top of the Evidence_Library_Tab showing aggregate counts (total images, total videos, total documents, images with faces, images with investigative labels).
- **AI_Insights_Panel**: A panel within the Evidence_Detail_Modal that displays Bedrock-generated analysis of what an evidence item shows and how it connects to the case.
- **Graph_Connection_View**: A section within the Evidence_Detail_Modal that shows which entities in the Neptune knowledge graph an evidence item connects to (persons appearing, documents referencing it).
- **Video_Player**: An HTML5 video element with basic playback controls (play, pause, seek, volume) that plays video evidence via presigned S3 URLs.
- **Presigned_URL**: A time-limited S3 URL (1-hour expiration) generated server-side that grants temporary read access to a private S3 object.
- **Investigative_Label**: A Rekognition-detected object category relevant to investigations (weapons, vehicles, currency, drugs, documents, electronics, persons).
- **Face_Bounding_Box**: A rectangular overlay drawn on an image indicating where Rekognition detected a face, with the matched entity name displayed.
- **Bedrock_Analysis_API**: The API endpoint that accepts an evidence item reference and returns AI-generated analysis text from Amazon Bedrock describing the evidence content and case connections.

## Requirements

### Requirement 1: Evidence Library Tab Registration

**User Story:** As an investigator, I want an "Evidence" tab in the investigator UI tab bar, so that I can navigate to the evidence library alongside the existing case analysis tabs.

#### Acceptance Criteria

1. THE Evidence_Library_Tab SHALL appear in the investigator.html tab bar with the label "🔍 Evidence" and invoke `switchTab('evidence')` when clicked.
2. WHEN the investigator clicks the Evidence_Library_Tab, THE investigator UI SHALL display the `tab-evidence` content panel and hide all other tab content panels.
3. THE `switchTab` function SHALL include 'evidence' in the allTabs array and handle loading evidence data when the evidence tab is activated.
4. THE Evidence_Library_Tab SHALL use the dark theme styling consistent with all other tabs in the investigator UI (dark background, light text, accent colors matching the existing palette).

### Requirement 2: Summary Statistics Bar

**User Story:** As an investigator, I want to see aggregate evidence counts at the top of the evidence library, so that I can quickly understand the scope and composition of evidence in the case.

#### Acceptance Criteria

1. WHEN the Evidence_Library_Tab loads for a selected case, THE Summary_Statistics_Bar SHALL display the following counts: total images, total videos, total documents, images with detected faces, and images with Investigative_Labels.
2. THE Summary_Statistics_Bar SHALL retrieve image statistics from the Image_Evidence_API summary response fields (total, total_faces, matched_faces, images_with_labels, label_counts).
3. THE Summary_Statistics_Bar SHALL retrieve video counts by listing video files associated with the case from S3 (files with .mp4 or .mov extensions).
4. THE Summary_Statistics_Bar SHALL retrieve document counts from the existing case file list API response.
5. WHEN the Image_Evidence_API returns no data for the selected case, THE Summary_Statistics_Bar SHALL display zero for all image-related counts.

### Requirement 3: Evidence Grid Gallery View

**User Story:** As an investigator, I want to browse all evidence items in a visual grid layout, so that I can scan through photos, videos, and documents like a physical evidence wall.

#### Acceptance Criteria

1. THE Evidence_Grid SHALL display Evidence_Items as thumbnail cards in a responsive grid layout that adapts to the browser viewport width.
2. WHEN displaying image Evidence_Items, THE Evidence_Grid SHALL show a thumbnail loaded via the presigned URL from the Image_Evidence_API, the filename, the number of detected faces, and up to three Investigative_Label badges.
3. WHEN displaying video Evidence_Items, THE Evidence_Grid SHALL show a video icon placeholder thumbnail, the filename, the file format (.mp4 or .mov), and a play icon overlay.
4. WHEN displaying document Evidence_Items, THE Evidence_Grid SHALL show a document icon placeholder thumbnail, the filename, and the document type.
5. THE Evidence_Grid SHALL support pagination controls (previous page, next page, page number display) using the Image_Evidence_API pagination parameters (page, page_size).
6. THE Evidence_Grid SHALL load the first page of evidence automatically when the Evidence_Library_Tab is activated and a case is selected.
7. WHEN no evidence items exist for the selected case, THE Evidence_Grid SHALL display an empty state message indicating no evidence has been processed for the case.

### Requirement 4: Media Type Filtering

**User Story:** As an investigator, I want to filter the evidence grid by media type, so that I can focus on just photos, just videos, or just documents.

#### Acceptance Criteria

1. THE Media_Type_Filter SHALL provide toggle buttons for three categories: Images, Videos, and Documents.
2. WHEN the investigator selects the Images filter, THE Evidence_Grid SHALL display only image Evidence_Items retrieved from the Image_Evidence_API.
3. WHEN the investigator selects the Videos filter, THE Evidence_Grid SHALL display only video Evidence_Items (.mp4 and .mov files).
4. WHEN the investigator selects the Documents filter, THE Evidence_Grid SHALL display only document Evidence_Items.
5. WHEN the investigator selects "All" or no specific filter, THE Evidence_Grid SHALL display all media types combined.
6. THE Media_Type_Filter SHALL visually indicate the currently active filter selection.

### Requirement 5: Rekognition Label Filtering

**User Story:** As an investigator, I want to filter evidence by Rekognition-detected labels, so that I can quickly find images containing weapons, vehicles, persons, or other investigatively relevant objects.

#### Acceptance Criteria

1. THE Label_Filter SHALL display a dropdown or tag selector populated with the unique Investigative_Labels returned in the Image_Evidence_API summary label_counts field.
2. WHEN the investigator selects a label from the Label_Filter, THE Evidence_Grid SHALL re-fetch images from the Image_Evidence_API with the `label_filter` query parameter set to the selected label.
3. WHEN the investigator selects the "Has Faces" filter option, THE Evidence_Grid SHALL re-fetch images from the Image_Evidence_API with the `has_faces=true` query parameter.
4. THE Label_Filter SHALL display the count of images matching each label next to the label name, using data from the summary label_counts.
5. WHEN the investigator clears the Label_Filter, THE Evidence_Grid SHALL re-fetch the unfiltered image list from the Image_Evidence_API.

### Requirement 6: Image Evidence Detail Modal

**User Story:** As an investigator, I want to click an image and see it full-size with Rekognition labels overlaid and face bounding boxes drawn, so that I can examine visual evidence in detail and understand what AI detected.

#### Acceptance Criteria

1. WHEN the investigator clicks an image Evidence_Item in the Evidence_Grid, THE Evidence_Detail_Modal SHALL open and display the full-size image loaded via the presigned URL.
2. THE Evidence_Detail_Modal SHALL overlay Face_Bounding_Boxes on the image for each detected face, with the matched entity name (or "Unidentified") displayed adjacent to each bounding box.
3. THE Evidence_Detail_Modal SHALL display a list of all Rekognition-detected labels for the image with their confidence scores.
4. THE Evidence_Detail_Modal SHALL display the source document ID and filename for the image.
5. WHEN the image has an AI description from the weapon_ai_descriptions data, THE Evidence_Detail_Modal SHALL display the AI description text and the false-positive assessment.
6. THE Evidence_Detail_Modal SHALL provide a close button and support closing via the Escape key.

### Requirement 7: Video Playback

**User Story:** As an investigator, I want to click a video evidence item and play it with basic controls, so that I can review video evidence directly within the evidence library.

#### Acceptance Criteria

1. WHEN the investigator clicks a video Evidence_Item in the Evidence_Grid, THE Evidence_Detail_Modal SHALL open and display the Video_Player loaded with the video presigned S3 URL.
2. THE Video_Player SHALL provide standard HTML5 video controls: play, pause, seek bar, volume control, and fullscreen toggle.
3. THE Video_Player SHALL support .mp4 and .mov video formats.
4. IF the video presigned URL fails to load or the video format is unsupported by the browser, THEN THE Video_Player SHALL display an error message with the filename and a suggestion to download the file.
5. THE Evidence_Detail_Modal SHALL display the video filename and any associated metadata (file size, format) alongside the Video_Player.

### Requirement 8: AI Insights Panel

**User Story:** As an investigator, I want to click "Analyze" on any evidence item and get an AI-generated analysis of what the evidence shows and how it connects to the case, so that I can get rapid investigative insights without manual review.

#### Acceptance Criteria

1. THE Evidence_Detail_Modal SHALL include an "Analyze" button that triggers a Bedrock AI analysis request for the currently displayed evidence item.
2. WHEN the investigator clicks "Analyze" on an image, THE AI_Insights_Panel SHALL send the image metadata (labels, faces, entity connections, source document) to the Bedrock_Analysis_API and display the returned analysis text.
3. WHEN the investigator clicks "Analyze" on a video, THE AI_Insights_Panel SHALL send the video metadata (filename, associated entities, associated documents) to the Bedrock_Analysis_API and display the returned analysis text.
4. WHILE the Bedrock_Analysis_API request is in progress, THE AI_Insights_Panel SHALL display a loading indicator with the text "Analyzing evidence...".
5. IF the Bedrock_Analysis_API request fails, THEN THE AI_Insights_Panel SHALL display an error message indicating the analysis could not be completed.
6. THE AI_Insights_Panel SHALL display the analysis text in a scrollable panel within the Evidence_Detail_Modal.

### Requirement 9: Graph Connection View

**User Story:** As an investigator, I want to see which entities in the knowledge graph an evidence item connects to, so that I can understand which persons appear in a photo and which documents reference it.

#### Acceptance Criteria

1. THE Evidence_Detail_Modal SHALL include a Graph_Connection_View section that lists all entities connected to the displayed evidence item.
2. WHEN displaying an image with matched faces, THE Graph_Connection_View SHALL list each matched entity name with their face thumbnail (from the Entity_Photo_API) and the match confidence score.
3. WHEN displaying an image with a source_document_id, THE Graph_Connection_View SHALL display the source document name as a clickable link that navigates to that document in the cases tab.
4. THE Graph_Connection_View SHALL display entity connections grouped by type: Persons, Documents, and Locations.
5. WHEN no entity connections exist for an evidence item, THE Graph_Connection_View SHALL display a message indicating no graph connections have been identified.

### Requirement 10: Dark Theme Consistency

**User Story:** As an investigator, I want the evidence library to match the dark theme of the rest of the investigator UI, so that the visual experience is cohesive and comfortable for extended use.

#### Acceptance Criteria

1. THE Evidence_Library_Tab SHALL use the same dark background color (#0d1117), text color (#e6edf3), and accent colors (#4a9eff, #238636) as the existing investigator.html tabs.
2. THE Evidence_Grid thumbnail cards SHALL use the same card styling (background #161b22, border #30363d, border-radius, hover effects) as cards in other investigator tabs.
3. THE Evidence_Detail_Modal SHALL use a dark overlay background with a dark-themed modal panel consistent with existing modal/overlay patterns in the investigator UI.
4. THE Summary_Statistics_Bar SHALL use the same stat-card styling as statistics displays in other investigator tabs.
5. THE Label_Filter and Media_Type_Filter controls SHALL use the same button and dropdown styling as filter controls in other investigator tabs.
