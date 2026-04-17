# Design Document: Visual Evidence Intelligence

## Overview

Visual Evidence Intelligence provides the complete visual analysis pipeline for investigative case analysis. The system processes extracted images through AWS Rekognition for label detection and face analysis, crops and matches detected faces against known entity photos, loads visual entity data into the Neptune knowledge graph, and serves results through a paginated API and frontend gallery.

Requirements 1–6 are already implemented and working in production. This design documents the existing architecture and defines the new work for Requirements 7–9: Neptune graph loading of Rekognition label data, full-scale image processing across 15,791 images, and scalable face matching with incremental comparison tracking.

Per `docs/lessons-learned.md`: all new work EXTENDS existing scripts and services. No rewrites.

## Architecture

The visual evidence pipeline operates as a set of offline scripts and online services connected through S3 artifacts:

```mermaid
graph TD
    subgraph "Offline Scripts (Already Implemented)"
        A[batch_rekognition_labels.py] -->|writes| S1[batch_labels_summary.json]
        A -->|writes| S2[batch_labels_details.json]
        B[crop_faces.py] -->|reads| S3[face_crop_metadata.json]
        B -->|writes| S4[face-crops/unidentified/*.jpg]
        C[match_faces.py] -->|reads| S4
        C -->|reads| S5[face-crops/demo/*.jpg]
        C -->|writes| S6[face-crops/{entity}/*.jpg]
        C -->|writes| S7[face_match_results.json]
    end

    subgraph "New Work (Requirements 7-9)"
        D[load_rekognition_to_graph.py<br/>EXTEND for label data] -->|reads| S2
        D -->|writes| S8[neptune-bulk-load CSVs]
        D -->|triggers| N[Neptune Bulk Loader]
        E[Full-scale processing<br/>run existing scripts on all 15,791 images]
        F[match_faces.py<br/>EXTEND with comparison tracking]
    end

    subgraph "Online Services (Already Implemented)"
        G[case_files.py<br/>image_evidence_handler] -->|reads| S1
        G -->|reads| S2
        G -->|reads| S3
        G -->|reads| S7
        H[entity_photo_service.py] -->|reads| S6
        H -->|reads| S5
        I[investigator.html<br/>Image Evidence Gallery]
    end

    G -->|presigned URLs| I
    H -->|base64 data URIs| I
```

### S3 Artifact Layout

All artifacts live under `s3://research-analyst-data-lake-974220725866/cases/{case_id}/`:

```
cases/{case_id}/
├── extracted-images/              # Source images from PDF extraction
│   └── {doc_id}_page{N}_img{M}.jpg
├── rekognition-artifacts/
│   ├── batch_labels_summary.json  # Aggregate label stats
│   ├── batch_labels_details.json  # Per-image label results
│   ├── face_crop_metadata.json    # Bounding box metadata
│   └── face_match_results.json    # Match results with entity names
├── face-crops/
│   ├── demo/                      # Known entity reference photos
│   │   └── {entity_name}.jpg
│   ├── unidentified/              # Unmatched face crops
│   │   └── {hash}.jpg
│   └── {entity_name}/             # Matched face crops per entity
│       ├── {hash}.jpg
│       └── primary_thumbnail.jpg
neptune-bulk-load/{case_id}/
├── rek_{batch_id}_nodes.csv       # Visual entity nodes
└── rek_{batch_id}_edges.csv       # Co-occurrence edges
```

## Components and Interfaces

### Existing Components (Requirements 1–6)

#### 1. Label Detector — `scripts/batch_rekognition_labels.py`

Batch script that calls Rekognition `detect_labels` on all extracted images. Filters against the `INVESTIGATIVE_LABELS` set (persons, documents, vehicles, weapons, drugs, jewelry, locations, etc.) with a 70% confidence threshold. Supports resume via local progress file and configurable parallelism (default 3 threads, 50ms delay between batches).

**Interface**: CLI with `--case-id`, `--limit`, `--parallel` args.
**Output**: `batch_labels_summary.json` and `batch_labels_details.json` to S3.

#### 2. Face Cropper — `scripts/crop_faces.py`

Reads `face_crop_metadata.json`, downloads source images, crops face regions using Rekognition bounding box coordinates with 30% padding, resizes to 200×200 JPEG thumbnails, uploads to S3. Supports `--target-case` for cross-case copying.

**Interface**: CLI with `--case-id`, `--target-case`, `--dry-run` args.
**Output**: JPEG thumbnails to `face-crops/unidentified/` in S3.

#### 3. Face Matcher — `scripts/match_faces.py`

Compares unidentified face crops against known entity demo photos using Rekognition `CompareFaces`. Selects the entity with the highest similarity score ≥ 80% threshold. Copies matched crops to named entity folders in both main and combined case paths. Rate-limits at 100ms between comparisons.

**Interface**: CLI with `--case-id`, `--threshold`, `--dry-run` args.
**Output**: Copies to `face-crops/{entity_name}/` and `face_match_results.json` to S3.

#### 4. Image Evidence API — `src/lambdas/api/case_files.py::image_evidence_handler`

GET `/case-files/{id}/image-evidence` endpoint. Returns paginated image records with labels, face data, presigned URLs (1-hour expiry), and summary statistics. Supports `page`, `page_size`, `label_filter`, `has_faces` query params. Falls back to S3 listing (capped at 5000) when label data doesn't exist.

**Interface**: HTTP GET with query parameters.
**Output**: JSON with `images[]`, `total`, `page`, `summary`.

#### 5. Image Evidence Gallery — `src/frontend/investigator.html`

Displays matched face crop thumbnails for person entities in the drill-down panel. Shows entity name labels and similarity confidence scores. Loads via `_loadImageEvidence()` function.

#### 6. Entity Photo Service — `src/services/entity_photo_service.py`

Resolves entity photos with priority: pipeline `primary_thumbnail.jpg` > demo photos. Downloads from S3 and returns base64 data URIs for vis.js graph node embedding. Returns `entity_metadata` with source and `face_crop_count`.

### New Components (Requirements 7–9)

#### 7. Graph Loader Extension — `scripts/load_rekognition_to_graph.py` (EXTEND)

The existing script reads from `doj-cases-974220725866-us-east-1` (photo-metadata and rekognition-output). The extension adds a new function to read `batch_labels_details.json` from the data lake bucket and create Visual_Entity nodes + DETECTED_IN edges + co-occurrence edges.

**New function**: `collect_label_entities(case_id)` — reads `batch_labels_details.json`, creates Visual_Entity nodes per unique label, maps labels to entity types (person/vehicle/document/weapon/artifact), creates DETECTED_IN edges to source documents, creates co-occurrence edges between labels in the same source document.

**Extension approach**:
- Add `collect_label_entities()` alongside existing `collect_visual_entities()`
- Add `--mode` CLI arg: `rekognition` (existing), `labels` (new), `all` (both)
- Reuse existing `generate_csv_and_load()` for CSV generation and Neptune bulk load trigger
- Node ID format: `{case_id}_visual_{label_name}` to avoid collision with existing entity nodes
- Edge label: `DETECTED_IN` for entity→document, `CO_OCCURS_WITH` for entity↔entity

**Entity type mapping**:
```python
LABEL_TYPE_MAP = {
    "person": {"person", "people", "human", "face", "man", "woman", "boy", "girl", "child", "adult"},
    "vehicle": {"car", "vehicle", "automobile", "truck", "van", "bus", "motorcycle", "boat", "yacht", "ship", "airplane", "aircraft", "helicopter", "jet"},
    "document": {"document", "text", "paper", "letter", "page", "book", "newspaper", "receipt", "check", "passport", "id card", "license", "certificate", "contract"},
    "weapon": {"weapon", "gun", "pistol", "rifle", "knife", "sword"},
    "artifact": ...  # everything else in INVESTIGATIVE_LABELS
}
```

#### 8. Full-Scale Processing — Operational (no new code)

Run existing scripts sequentially on the full 15,791 image corpus:
1. `batch_rekognition_labels.py --case-id {MAIN_CASE}` (resume-capable)
2. `crop_faces.py --case-id {MAIN_CASE} --target-case {COMBINED_CASE}`
3. Sync artifacts: copy `batch_labels_summary.json` and `batch_labels_details.json` from main case to combined case path
4. `load_rekognition_to_graph.py --mode labels --case-id {MAIN_CASE}`

No new code needed — just running existing scripts to completion and syncing artifacts.

#### 9. Scalable Face Matcher Extension — `scripts/match_faces.py` (EXTEND)

**New features**:
- `--comparison-log` flag: path to a JSON file tracking completed comparisons
- On each run, load the comparison log, skip already-completed `(crop_key, entity_key)` pairs
- After each match run, append new comparisons to the log
- Cumulative results: load existing `face_match_results.json`, merge new matches, write back
- New entity photos are automatically picked up by listing `face-crops/demo/`

**Comparison log format**:
```json
{
    "completed_comparisons": [
        {"crop": "abc123.jpg", "entity": "John_Doe", "timestamp": "2025-01-01T00:00:00Z"}
    ],
    "last_run": "2025-01-01T00:00:00Z"
}
```

## Data Models

### Neptune Visual_Entity Node (CSV format)

| Column | Type | Description |
|--------|------|-------------|
| ~id | String | `{case_id}_visual_{label_name}` |
| ~label | String | `VisualEntity_{case_id}` |
| entity_type | String | person, vehicle, document, weapon, artifact |
| canonical_name | String | Rekognition label name |
| confidence | Double | Average confidence across detections |
| occurrence_count | Int | Number of images containing this label |
| case_file_id | String | Case ID |
| source | String | `rekognition_label` |

### Neptune DETECTED_IN Edge (CSV format)

| Column | Type | Description |
|--------|------|-------------|
| ~id | String | `{case_id}_detected_{label}_{doc_id}` |
| ~from | String | Visual_Entity node ID |
| ~to | String | Document node ID (from source_document_id) |
| ~label | String | `DETECTED_IN` |
| confidence | Double | Max confidence for this label in this document |
| case_file_id | String | Case ID |

### Neptune Co-occurrence Edge (CSV format)

| Column | Type | Description |
|--------|------|-------------|
| ~id | String | `{case_id}_cooccur_{label1}_{label2}` |
| ~from | String | Visual_Entity node ID for label1 |
| ~to | String | Visual_Entity node ID for label2 |
| ~label | String | `CO_OCCURS_WITH` |
| co_occurrence_count | Int | Number of documents where both labels appear |
| case_file_id | String | Case ID |

### S3 Artifacts

**batch_labels_details.json** (per-image label results):
```json
[
    {
        "s3_key": "cases/{case_id}/extracted-images/{filename}.jpg",
        "labels": [
            {"name": "Person", "confidence": 98.5, "parents": ["Human"]},
            {"name": "Document", "confidence": 87.2, "parents": ["Text"]}
        ],
        "all_label_count": 15,
        "error": null
    }
]
```

**face_match_results.json** (cumulative, extended for Req 9):
```json
{
    "matches": [
        {"crop": "abc123.jpg", "entity": "John_Doe", "similarity": 92.3, "source_key": "...", "new_key": "...", "run_timestamp": "2025-01-01T00:00:00Z"}
    ],
    "no_match": ["def456.jpg"],
    "threshold": 80.0,
    "runs": [
        {"timestamp": "2025-01-01T00:00:00Z", "new_matches": 5, "new_crops": 20, "new_entities": 0}
    ]
}
```

**comparison_log.json** (new for Req 9):
```json
{
    "completed_comparisons": [
        {"crop": "abc123.jpg", "entity": "John_Doe", "timestamp": "2025-01-01T00:00:00Z"}
    ],
    "last_run": "2025-01-01T00:00:00Z",
    "total_comparisons": 1500
}
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Investigative label filtering

*For any* list of Rekognition labels with varying names and confidence scores, filtering against the INVESTIGATIVE_LABELS set with a 70% confidence threshold should retain only labels whose lowercased name is in the set AND whose confidence is ≥ 70.0, and reject all others.

**Validates: Requirements 1.2**

### Property 2: Label detection output consistency

*For any* set of per-image label detection results, the summary's `images_processed` count should equal the number of results, `unique_labels` should equal the number of distinct label names across all results, `total_label_instances` should equal the sum of all label counts, and the details list should contain only images with at least one label.

**Validates: Requirements 1.3, 1.4**

### Property 3: Face crop bounding box calculation

*For any* image dimensions (width, height) and Rekognition bounding box (Left, Top, Width, Height as normalized 0.0–1.0 floats), the crop coordinates with 30% padding should be: x1 = max(0, (Left - Width*0.3) * img_width), y1 = max(0, (Top - Height*0.3) * img_height), x2 = min(img_width, (Left + Width + Width*0.3) * img_width), y2 = min(img_height, (Top + Height + Height*0.3) * img_height), and the output should be exactly 200×200 pixels when the crop region is ≥ 20×20.

**Validates: Requirements 2.1**

### Property 4: Case ID path transformation

*For any* S3 key containing a source case ID and a target case ID, replacing the source case ID with the target case ID in the key should produce a valid S3 key under the target case, and the path structure after the case ID should be preserved.

**Validates: Requirements 2.3, 8.2**

### Property 5: Best match selection from similarity scores

*For any* set of (entity_name, similarity_score) pairs from CompareFaces results and a threshold T, the selected match should be the entity with the highest similarity score that is ≥ T. If no score meets the threshold, no match should be selected.

**Validates: Requirements 3.2**

### Property 6: Match destination path construction

*For any* case ID, entity name, and crop filename, the destination path should be `cases/{case_id}/face-crops/{entity_name}/{crop_filename}`, and the combined case path should be the same with the combined case ID substituted.

**Validates: Requirements 3.3**

### Property 7: Image evidence pagination and filtering

*For any* list of image records, page number P, page size S, and optional label filter L: the returned page should contain at most S records starting from index (P-1)*S, and when L is specified, every returned image should contain a label matching L (case-insensitive).

**Validates: Requirements 4.1, 4.2**

### Property 8: Image evidence summary statistics

*For any* batch labels summary and face data, the returned summary should have `total_faces` equal to the length of face_crop_metadata, `matched_faces` equal to the number of entries in face_match_results matches, and `label_counts` matching the summary's label_counts.

**Validates: Requirements 4.4**

### Property 9: Face data merge into image records

*For any* image record with an S3 key that has corresponding entries in face_crop_metadata and face_match_results, the merged record's `faces` array should contain one entry per face crop for that image, and each face entry's `entity_name` should reflect the match result (or "unidentified" if no match).

**Validates: Requirements 4.6**

### Property 10: Entity photo priority resolution

*For any* entity that has both a pipeline `primary_thumbnail.jpg` and a demo photo, the resolved photo should come from the pipeline source. For any entity with only a demo photo, the demo photo should be used. The returned data should be a valid `data:image/jpeg;base64,...` URI, and entity_metadata should include the correct `source` field ("pipeline" or "demo") and a non-negative `face_crop_count`.

**Validates: Requirements 6.1, 6.2, 6.3**

### Property 11: Visual_Entity node creation from label data

*For any* batch_labels_details.json containing images with labels, the number of generated Visual_Entity nodes should equal the number of unique label names across all images, and each node's `canonical_name` should appear in at least one image's label list.

**Validates: Requirements 7.1**

### Property 12: DETECTED_IN edge creation

*For any* image with labels and a parseable source_document_id, there should be exactly one DETECTED_IN edge per unique (label, source_document_id) pair, linking the Visual_Entity node to the document node.

**Validates: Requirements 7.2**

### Property 13: Co-occurrence edge creation

*For any* source document that has N distinct labels detected across its images, the number of co-occurrence edges for that document should be exactly N*(N-1)/2 (one per unique unordered pair), and no duplicate edges should exist.

**Validates: Requirements 7.3**

### Property 14: Neptune CSV generation format

*For any* set of Visual_Entity nodes and edges, the generated nodes CSV should have the header `~id,~label,entity_type:String,canonical_name:String,confidence:Double,occurrence_count:Int,case_file_id:String,source:String` and one data row per node, and the edges CSV should have the correct header and one row per edge, with all `~from` and `~to` values referencing valid node IDs.

**Validates: Requirements 7.4**

### Property 15: Label-to-entity-type mapping

*For any* Rekognition label name in the INVESTIGATIVE_LABELS set, the assigned entity_type should be: "person" for person-related labels, "vehicle" for vehicle labels, "document" for document labels, "weapon" for weapon labels, and "artifact" for all others. The mapping should be exhaustive — every investigative label maps to exactly one type.

**Validates: Requirements 7.6**

### Property 16: Incremental comparison tracking

*For any* comparison log containing previously completed (crop, entity) pairs and a current set of all (crop, entity) pairs to evaluate, the set of new comparisons to perform should be exactly the set difference: all pairs minus completed pairs. No previously completed comparison should be re-executed.

**Validates: Requirements 9.1, 9.2**

### Property 17: Cumulative match results merge

*For any* existing face_match_results.json with previous matches and a new set of match results, the merged output should contain all previous matches plus all new matches with no duplicate (crop, entity) entries, and the `runs` array should have one additional entry recording the new run's statistics.

**Validates: Requirements 9.4**

## Error Handling

### Existing Error Handling (Requirements 1–6)

| Component | Error | Handling |
|-----------|-------|----------|
| Label Detector | Rekognition API failure on single image | Log error, increment counter, continue processing |
| Label Detector | S3 listing failure | Fail fast — cannot proceed without image list |
| Face Cropper | Source image download failure | Skip face, log warning |
| Face Cropper | Crop region < 20×20 pixels | Skip face, return empty bytes |
| Face Matcher | CompareFaces InvalidParameterException | Skip comparison, continue (no face in image) |
| Face Matcher | Other CompareFaces errors | Log warning, skip, continue |
| Image Evidence API | Missing case ID | Return 400 VALIDATION_ERROR |
| Image Evidence API | S3 artifact not found | Graceful fallback (empty labels, empty faces) |
| Image Evidence API | Presigned URL generation failure | Set presigned_url to empty string |
| Entity Photo Service | S3 download failure | Return None, skip entity |

### New Error Handling (Requirements 7–9)

| Component | Error | Handling |
|-----------|-------|----------|
| Graph Loader (labels) | batch_labels_details.json not found | Log error, exit with message |
| Graph Loader (labels) | Unparseable source_document_id from filename | Skip that image's edges, log warning |
| Graph Loader (labels) | Neptune bulk load failure | Log failure status and load ID, do not retry |
| Graph Loader (labels) | CSV upload to S3 failure | Fail fast — cannot proceed without CSVs |
| Face Matcher (incremental) | Comparison log corrupted/unparseable | Start fresh with empty log, log warning |
| Face Matcher (incremental) | face_match_results.json corrupted | Start fresh with empty results, log warning |

## Testing Strategy

### Property-Based Testing

Use `hypothesis` (Python) for property-based testing. Each property test runs a minimum of 100 iterations.

Property tests should cover:
- **Label filtering** (Property 1): Generate random label lists with varying names and confidences, verify filter correctness
- **Output consistency** (Property 2): Generate random detection results, verify summary/details consistency
- **Bounding box math** (Property 3): Generate random image dimensions and bounding boxes, verify crop coordinates
- **Path transformation** (Property 4): Generate random case IDs and S3 keys, verify substitution
- **Best match selection** (Property 5): Generate random similarity score sets, verify selection logic
- **Pagination/filtering** (Property 7): Generate random image lists and query params, verify slicing
- **Node creation** (Property 11): Generate random label data, verify unique node count
- **DETECTED_IN edges** (Property 12): Generate random label-document pairs, verify edge count
- **Co-occurrence edges** (Property 13): Generate random multi-label documents, verify N*(N-1)/2 edges
- **CSV format** (Property 14): Generate random entities/edges, verify CSV structure and referential integrity
- **Type mapping** (Property 15): For all labels in INVESTIGATIVE_LABELS, verify type assignment
- **Comparison tracking** (Property 16): Generate random completed logs and new pairs, verify set difference
- **Cumulative merge** (Property 17): Generate random existing and new results, verify merge correctness

Each test must be tagged: `# Feature: visual-evidence-intelligence, Property {N}: {title}`

### Unit Testing

Unit tests complement property tests for specific examples and edge cases:
- Empty image list → summary has zero counts
- Image with no matching labels → excluded from details
- Bounding box at image edge → coordinates clamped correctly
- Face crop < 20×20 → returns empty bytes
- No CompareFaces matches above threshold → no match selected
- Page beyond total → returns empty page
- label_filter with no matches → returns empty list
- Entity with only demo photo → demo selected
- Entity with only pipeline photo → pipeline selected
- Empty batch_labels_details.json → zero Visual_Entity nodes
- Single-label document → zero co-occurrence edges
- Comparison log with all pairs completed → zero new comparisons
- Merge with no new matches → results unchanged

### Test Configuration

```python
from hypothesis import given, settings, strategies as st

@settings(max_examples=100)
@given(...)
def test_property_N(...):
    # Feature: visual-evidence-intelligence, Property N: {title}
    ...
```
