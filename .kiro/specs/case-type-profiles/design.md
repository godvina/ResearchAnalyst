# Design Document: Case Type Profiles

## Overview

This feature adds two capabilities to the Research Analyst platform:

1. **Case Type Profile Registry** — A Python dictionary of curated Rekognition label sets, entity extraction focus areas, and AI analysis tuning per investigation category (antitrust, financial fraud, drug trafficking, etc.). Profiles are stored in `config_validation_service.py` alongside `CONFIG_TEMPLATES` and applied to cases via `pipeline_config_service.py`, which merges profile data into the case's pipeline config. The `rekognition_handler.py` is extended to check `effective_config.rekognition.investigative_labels` before falling back to the hardcoded `INVESTIGATIVE_LABELS` set.

2. **Frontend Data Loader** — A fresh `data-loader.html` page (NOT modifications to batch-loader.html) that provides a thin UI for: (a) selecting a case type profile, (b) uploading files via the existing ingest API, (c) triggering the existing Step Functions pipeline for S3 prefix-based bulk loads (same pattern as `fast_load.py`), and (d) polling pipeline execution status.

### Design Decisions & Rationale

- **Fresh data-loader.html**: The batch-loader.html attempted to build its own extraction system and failed. The new page is a thin UI that calls existing working APIs only.
- **No CDK changes**: All changes are code-level — new API routes in the existing case_files.py dispatcher, service extensions, and a new frontend page.
- **EXTEND, don't rewrite**: Per lessons-learned.md, we never rewrite working modules. We add new methods to existing services and new routes to the existing dispatcher.
- **CASE_TYPE_PROFILES dict in config_validation_service.py**: Colocated with CONFIG_TEMPLATES for consistency. Profiles are separate from templates — profiles define what to detect, templates define how to process.
- **SFN trigger via boto3**: The data-loader.html triggers Step Functions the same way fast_load.py does — `sfn.start_execution()` with case_id and document_ids. The API handler in case_files.py wraps this call.

## Architecture

```mermaid
graph TD
    subgraph Frontend
        DL[data-loader.html]
    end

    subgraph API Layer
        CF[case_files.py dispatcher]
    end

    subgraph Services
        CVS[config_validation_service.py<br/>CASE_TYPE_PROFILES dict]
        PCS[pipeline_config_service.py<br/>apply_case_type_profile]
        CRS[config_resolution_service.py<br/>resolve_effective_config]
    end

    subgraph Pipeline
        SFN[Step Functions<br/>Ingestion Pipeline]
        RH[rekognition_handler.py<br/>configurable labels]
    end

    DL -->|GET /case-type-profiles| CF
    DL -->|POST /case-files/{id}/apply-case-type| CF
    DL -->|POST /case-files/{id}/ingest| CF
    DL -->|POST /case-files/{id}/trigger-pipeline| CF
    DL -->|GET /case-files/{id}/pipeline-execution/{arn}| CF

    CF --> CVS
    CF --> PCS
    CF --> SFN

    PCS --> CVS
    PCS --> CRS

    SFN --> RH
    RH -->|reads| CRS
```

## Components and Interfaces

### 1. CASE_TYPE_PROFILES Registry (config_validation_service.py)

**Location**: `src/services/config_validation_service.py` — new `CASE_TYPE_PROFILES` dict alongside existing `CONFIG_TEMPLATES`.

**Interface**:
```python
CASE_TYPE_PROFILES: dict[str, dict] = {
    "case_type_name": {
        "display_name": "Human Readable Name",
        "investigative_labels": ["label1", "label2", ...],
        "entity_focus": ["person", "organization", ...],
        "analysis_focus": ["focus_area_1", "focus_area_2", ...],
    },
    ...
}
```

**Profiles defined** (10 case types):
- `child_sex_trafficking` — current INVESTIGATIVE_LABELS set (default/legacy)
- `antitrust` — document, spreadsheet, chart, graph, meeting, conference room, whiteboard, presentation, phone, computer, email, contract, invoice, receipt, ledger, calendar, memo, fax, signature, stamp, seal, corporate logo, office, boardroom
- `financial_fraud` — currency, money, cash, check, receipt, ledger, invoice, contract, computer, laptop, phone, document, spreadsheet, safe, briefcase, bank, office
- `drug_trafficking` — drug, pill, syringe, weapon, gun, car, boat, airplane, phone, cash, money, suitcase, bag, package, scale, tunnel, border
- `public_corruption` — document, contract, money, cash, check, phone, computer, office, boardroom, meeting, badge, government building, flag, briefcase, envelope
- `organized_crime` — weapon, gun, knife, car, boat, phone, cash, money, jewelry, watch, safe, suitcase, tattoo, nightclub, restaurant, warehouse
- `cybercrime` — computer, laptop, phone, tablet, monitor, server, cable, usb, hard drive, keyboard, screen, code, terminal, router
- `environmental_crime` — factory, smokestack, pipe, barrel, drum, chemical, water, river, soil, truck, warehouse, document, map, satellite
- `tax_evasion` — document, spreadsheet, ledger, invoice, receipt, check, cash, money, computer, phone, safe, briefcase, office, filing cabinet, bank
- `money_laundering` — currency, money, cash, check, bank, safe, briefcase, jewelry, watch, car, boat, real estate, restaurant, casino, phone, computer, document

### 2. Config Validation Extension (config_validation_service.py)

**Change**: Add `"investigative_labels"` to `_REKOGNITION_KEYS` set so the validator accepts it.

**New validation**: When `investigative_labels` is present in the rekognition section, validate it is a `list[str]`.

### 3. Pipeline Config Service Extension (pipeline_config_service.py)

**New method**: `apply_case_type_profile(case_id: str, case_type: str, created_by: str) -> ConfigVersion`

```python
def apply_case_type_profile(self, case_id: str, case_type: str, created_by: str) -> ConfigVersion:
    """Look up CASE_TYPE_PROFILES[case_type], merge into case pipeline config."""
```

**Logic**:
1. Look up `case_type` in `CASE_TYPE_PROFILES`. Raise `ValueError` if not found (with list of available types).
2. Build a config overlay: `{"rekognition": {"investigative_labels": profile["investigative_labels"]}, "extract": {"entity_types": profile["entity_focus"]}, "metadata": {"case_type": case_type}}`
3. Get existing active config for the case (if any) and deep-merge the overlay.
4. Call `self.create_or_update_config()` with the merged config.

**Note**: The `metadata` section needs to be added to `_VALID_SECTIONS` in config_validation_service.py.

### 4. Rekognition Handler Extension (rekognition_handler.py)

**Change**: In the label filtering logic (line ~483), check `config.get("investigative_labels")` first. If present and non-empty, use that set. Otherwise fall back to `INVESTIGATIVE_LABELS`.

```python
# In handler(), after extracting config:
custom_labels = config.get("investigative_labels")
active_labels = set(l.lower() for l in custom_labels) if custom_labels else INVESTIGATIVE_LABELS

# In _convert_to_entities(), pass active_labels and use it instead of INVESTIGATIVE_LABELS
```

### 5. API Routes (case_files.py)

New routes added to the dispatcher:

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/case-type-profiles` | `list_case_type_profiles` | List all available case type names + display labels |
| POST | `/case-files/{id}/apply-case-type` | `apply_case_type_handler` | Apply a case type profile to a case |
| GET | `/case-files/{id}/case-type` | `get_case_type_handler` | Get currently applied case type for a case |
| POST | `/case-files/{id}/trigger-pipeline` | `trigger_pipeline_handler` | Start SFN execution for S3 prefix |
| GET | `/pipeline-execution-status` | `pipeline_execution_status_handler` | Query SFN describe_execution by ARN |

### 6. Frontend: data-loader.html

**Location**: `src/frontend/data-loader.html`

**Sections**:
1. **Case Selector** — Dropdown to pick a case (fetches from GET /case-files)
2. **Case Type Profile** — Dropdown populated from GET /case-type-profiles, with POST to apply
3. **File Upload** — Drag-and-drop zone + file picker, sends files to POST /case-files/{id}/ingest
4. **S3 Prefix Trigger** — Text input for S3 prefix, triggers POST /case-files/{id}/trigger-pipeline
5. **Pipeline Status** — Polls GET /pipeline-execution-status?arn={arn} and displays status

**Pattern**: Same styling as investigator.html (dark theme, green accents). Standalone page, no modifications to existing pages.

## Data Models

### CASE_TYPE_PROFILES Entry Schema

```python
{
    "display_name": str,              # Human-readable name
    "investigative_labels": list[str], # Rekognition labels to track
    "entity_focus": list[str],         # Entity types for extraction
    "analysis_focus": list[str],       # AI analysis focus areas
}
```

### Pipeline Config with Case Type Applied

After applying a case type profile, the pipeline config gains:

```json
{
    "rekognition": {
        "enabled": true,
        "investigative_labels": ["document", "spreadsheet", "chart", ...],
        "min_object_confidence": 0.7
    },
    "extract": {
        "entity_types": ["person", "organization", "financial_amount", ...]
    },
    "metadata": {
        "case_type": "antitrust"
    }
}
```

### Trigger Pipeline Request/Response

**Request** (POST /case-files/{id}/trigger-pipeline):
```json
{
    "s3_prefix": "cases/{case_id}/raw/"
}
```

**Response**:
```json
{
    "execution_arn": "arn:aws:states:us-east-1:...:execution:...",
    "status": "RUNNING",
    "started_at": "2024-01-01T00:00:00Z"
}
```

### Pipeline Execution Status Response

**Response** (GET /pipeline-execution-status?arn={arn}):
```json
{
    "execution_arn": "arn:aws:states:...",
    "status": "RUNNING|SUCCEEDED|FAILED|TIMED_OUT|ABORTED",
    "start_date": "2024-01-01T00:00:00Z",
    "stop_date": "2024-01-01T00:05:00Z"
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Profile structural invariant

*For any* case type profile in CASE_TYPE_PROFILES, the profile must contain exactly three keys — `investigative_labels`, `entity_focus`, and `analysis_focus` — each of which is a non-empty list of strings, plus a `display_name` string.

**Validates: Requirements 1.2**

### Property 2: Unknown case type yields empty profile

*For any* string that is not a key in CASE_TYPE_PROFILES, looking up that string should return an empty profile (empty lists for investigative_labels, entity_focus, and analysis_focus).

**Validates: Requirements 1.4**

### Property 3: Label resolution uses config when present

*For any* non-empty list of label strings provided in `effective_config.rekognition.investigative_labels`, the resolved label set used for filtering should equal exactly that list (lowercased). When the list is absent or empty, the resolved set should equal the hardcoded `INVESTIGATIVE_LABELS`.

**Validates: Requirements 2.2, 2.3**

### Property 4: Investigative labels validation

*For any* value placed in `rekognition.investigative_labels`, the config validation service should accept it if and only if it is a list of strings. Non-list values and lists containing non-strings should produce validation errors.

**Validates: Requirements 2.5**

### Property 5: Profile application completeness

*For any* valid case type string in CASE_TYPE_PROFILES, applying the profile to a case should produce a pipeline config where: (a) `rekognition.investigative_labels` equals the profile's `investigative_labels`, (b) `extract.entity_types` equals the profile's `entity_focus`, and (c) `metadata.case_type` equals the case type string.

**Validates: Requirements 3.1, 3.2, 3.3**

### Property 6: Unknown case type raises ValueError

*For any* string not present in CASE_TYPE_PROFILES, calling `apply_case_type_profile` should raise a `ValueError` whose message contains the list of available case type names.

**Validates: Requirements 3.5, 4.3**

## Error Handling

| Scenario | Layer | Behavior |
|----------|-------|----------|
| Unknown case type in API | case_files.py | Return HTTP 400 with available case types list |
| Unknown case type in service | pipeline_config_service.py | Raise `ValueError` with available types |
| Invalid investigative_labels type | config_validation_service.py | Return `ValidationError` — must be list of strings |
| Empty S3 prefix in trigger | case_files.py | Return HTTP 400 with descriptive message |
| Invalid SFN execution ARN | case_files.py | Return HTTP 404 with descriptive message |
| SFN start_execution fails | case_files.py | Return HTTP 500 with error details |
| File upload fails (single file) | data-loader.html | Show error for that file, continue remaining uploads |
| No active config for case | config_resolution_service.py | Use system defaults (existing behavior, unchanged) |

## Testing Strategy

### Unit Tests

Unit tests verify specific examples and edge cases:

- **Profile registry completeness**: Verify all 10 required case types exist in `CASE_TYPE_PROFILES`
- **Antitrust labels**: Verify the antitrust profile contains the specified labels (document, spreadsheet, chart, etc.)
- **Config validation acceptance**: Verify `{"rekognition": {"investigative_labels": ["doc"]}}` passes validation
- **Config validation rejection**: Verify `{"rekognition": {"investigative_labels": 123}}` fails validation
- **API list endpoint**: Verify GET /case-type-profiles returns all profiles with display names
- **API apply endpoint**: Verify POST apply-case-type with valid type returns effective config
- **API error cases**: Verify 400 for unknown type, 400 for empty S3 prefix, 404 for invalid ARN
- **Trigger pipeline**: Verify the SFN input is correctly constructed with case_id and document_ids

### Property-Based Tests

Property-based tests verify universal properties across generated inputs. Use `hypothesis` library with minimum 100 iterations per test.

Each property test must be tagged with a comment referencing the design property:

- **Feature: case-type-profiles, Property 1: Profile structural invariant** — Generate all profile keys, verify structure
- **Feature: case-type-profiles, Property 2: Unknown case type yields empty profile** — Generate random strings, verify empty profile returned
- **Feature: case-type-profiles, Property 3: Label resolution uses config when present** — Generate random label lists, verify resolution logic
- **Feature: case-type-profiles, Property 4: Investigative labels validation** — Generate random values (lists, ints, dicts, etc.), verify validation accepts only list[str]
- **Feature: case-type-profiles, Property 5: Profile application completeness** — For each valid case type, verify all three sections are correctly merged
- **Feature: case-type-profiles, Property 6: Unknown case type raises ValueError** — Generate random strings not in registry, verify ValueError raised

Each correctness property is implemented by a single property-based test. Property tests use `hypothesis` with `@given` decorators and `@settings(max_examples=100)`.
