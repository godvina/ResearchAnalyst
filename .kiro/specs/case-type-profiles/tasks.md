# Implementation Plan: Case Type Profiles

## Overview

Extend the Research Analyst platform with a case type profile registry and a frontend data loader page. All changes extend existing modules — no rewrites. The implementation adds the CASE_TYPE_PROFILES dict to config_validation_service.py, a new apply_case_type_profile method to pipeline_config_service.py, configurable label resolution in rekognition_handler.py, new API routes in case_files.py, and a fresh data-loader.html frontend page.

## Tasks

- [ ] 1. Add CASE_TYPE_PROFILES registry and validation extensions to config_validation_service.py
  - [ ] 1.1 Add CASE_TYPE_PROFILES dictionary with all 10 case type profiles
    - Add the `CASE_TYPE_PROFILES` dict alongside `CONFIG_TEMPLATES` in `src/services/config_validation_service.py`
    - Define profiles for: child_sex_trafficking, antitrust, financial_fraud, drug_trafficking, public_corruption, organized_crime, cybercrime, environmental_crime, tax_evasion, money_laundering
    - Each profile has: display_name (str), investigative_labels (list[str]), entity_focus (list[str]), analysis_focus (list[str])
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ] 1.2 Add "investigative_labels" to _REKOGNITION_KEYS and add "metadata" to _VALID_SECTIONS
    - Add `"investigative_labels"` to the `_REKOGNITION_KEYS` set
    - Add `"metadata"` to the `_VALID_SECTIONS` set
    - In `_validate_rekognition`, add validation that `investigative_labels` must be a list of strings when present
    - _Requirements: 2.4, 2.5, 3.3_

  - [ ]* 1.3 Write property test: Profile structural invariant (Property 1)
    - **Property 1: Profile structural invariant**
    - For every profile in CASE_TYPE_PROFILES, verify it has exactly display_name (str), investigative_labels (non-empty list[str]), entity_focus (non-empty list[str]), analysis_focus (non-empty list[str])
    - **Validates: Requirements 1.2**

  - [ ]* 1.4 Write property test: Investigative labels validation (Property 4)
    - **Property 4: Investigative labels validation**
    - Generate random values (lists, ints, dicts, nested lists with non-strings). Verify ConfigValidationService.validate accepts only list[str] for rekognition.investigative_labels
    - **Validates: Requirements 2.5**

  - [ ]* 1.5 Write unit tests for config_validation_service extensions
    - Test all 10 case types exist in CASE_TYPE_PROFILES
    - Test antitrust profile contains expected labels (document, spreadsheet, chart, etc.)
    - Test `{"rekognition": {"investigative_labels": ["doc"]}}` passes validation
    - Test `{"rekognition": {"investigative_labels": 123}}` fails validation
    - Test `{"metadata": {"case_type": "antitrust"}}` passes validation (metadata section accepted)
    - Add tests to `tests/unit/test_config_validation_service.py`
    - _Requirements: 1.1, 1.2, 2.4, 2.5_

- [ ] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Add apply_case_type_profile method to pipeline_config_service.py
  - [ ] 3.1 Implement apply_case_type_profile method
    - Add `from services.config_validation_service import CASE_TYPE_PROFILES` import to `src/services/pipeline_config_service.py`
    - Add `apply_case_type_profile(self, case_id: str, case_type: str, created_by: str) -> ConfigVersion` method
    - Look up case_type in CASE_TYPE_PROFILES; raise ValueError with available types if not found
    - Build config overlay: `{"rekognition": {"investigative_labels": profile["investigative_labels"]}, "extract": {"entity_types": profile["entity_focus"]}, "metadata": {"case_type": case_type}}`
    - Get existing active config (if any) and deep-merge the overlay
    - Call self.create_or_update_config() with merged config
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 3.2 Write property test: Profile application completeness (Property 5)
    - **Property 5: Profile application completeness**
    - For each valid case type in CASE_TYPE_PROFILES, mock DB calls and verify apply_case_type_profile produces config where rekognition.investigative_labels matches profile, extract.entity_types matches entity_focus, metadata.case_type matches the case type string
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 3.3 Write property test: Unknown case type raises ValueError (Property 6)
    - **Property 6: Unknown case type raises ValueError**
    - Generate random strings not in CASE_TYPE_PROFILES keys. Verify apply_case_type_profile raises ValueError whose message contains available case type names
    - **Validates: Requirements 3.5, 4.3**

  - [ ]* 3.4 Write unit tests for apply_case_type_profile
    - Test applying "antitrust" produces correct config overlay
    - Test applying unknown type raises ValueError with available types list
    - Test that existing active config is deep-merged (not replaced)
    - Add tests to `tests/unit/test_pipeline_config_service.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 4. Extend rekognition_handler.py to use configurable investigative labels
  - [ ] 4.1 Modify _results_to_entities to accept and use a custom label set
    - In `src/lambdas/ingestion/rekognition_handler.py`, modify `_results_to_entities` to accept an `active_labels` parameter (set of lowercase strings)
    - Replace the hardcoded `INVESTIGATIVE_LABELS` reference in the label filtering logic with `active_labels`
    - In `handler()`, resolve active_labels: check `config.get("investigative_labels")` from the rekognition effective_config; if present and non-empty, use `set(l.lower() for l in custom_labels)`, otherwise fall back to `INVESTIGATIVE_LABELS`
    - Pass `active_labels` to `_results_to_entities`
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 4.2 Write property test: Label resolution uses config when present (Property 3)
    - **Property 3: Label resolution uses config when present**
    - Generate random non-empty lists of label strings. Verify that when passed as investigative_labels in config, _results_to_entities uses exactly those labels (lowercased). When absent/empty, verify INVESTIGATIVE_LABELS is used
    - **Validates: Requirements 2.2, 2.3**

  - [ ]* 4.3 Write unit tests for configurable label resolution
    - Test that custom labels from effective_config are used for filtering
    - Test that empty/absent investigative_labels falls back to INVESTIGATIVE_LABELS
    - Add tests to `tests/unit/test_handler_effective_config.py`
    - _Requirements: 2.1, 2.2, 2.3_

- [ ] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Add API routes to case_files.py dispatcher
  - [ ] 6.1 Add case type profile API handlers and route wiring
    - In `src/lambdas/api/case_files.py`, add route matching for:
      - `GET /case-type-profiles` → `list_case_type_profiles` handler
      - `POST /case-files/{id}/apply-case-type` → `apply_case_type_handler`
      - `GET /case-files/{id}/case-type` → `get_case_type_handler`
      - `POST /case-files/{id}/trigger-pipeline` → `trigger_pipeline_handler`
      - `GET /pipeline-execution-status` → `pipeline_execution_status_handler`
    - Add route matching in `dispatch_handler` BEFORE the catch-all case-file CRUD routes
    - `list_case_type_profiles`: import CASE_TYPE_PROFILES, return array of {name, display_name} objects
    - `apply_case_type_handler`: parse body for case_type, call PipelineConfigService.apply_case_type_profile, return effective config; 400 on ValueError
    - `get_case_type_handler`: get active config, return metadata.case_type or null
    - `trigger_pipeline_handler`: parse body for s3_prefix, validate non-empty, call boto3 sfn.start_execution (same pattern as fast_load.py), return execution_arn; 400 on empty prefix
    - `pipeline_execution_status_handler`: parse query param arn, call sfn.describe_execution, return status; 404 on invalid ARN
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.2, 6.3, 6.4, 6.5, 7.4, 7.5_

  - [ ]* 6.2 Write property test: Unknown case type yields empty profile (Property 2)
    - **Property 2: Unknown case type yields empty profile**
    - Generate random strings not in CASE_TYPE_PROFILES. Verify the lookup returns an empty profile (empty lists for all three fields)
    - **Validates: Requirements 1.4**

  - [ ]* 6.3 Write unit tests for API route handlers
    - Test GET /case-type-profiles returns all 10 profiles with display names
    - Test POST apply-case-type with valid type returns success
    - Test POST apply-case-type with unknown type returns 400 with available types
    - Test POST trigger-pipeline with empty s3_prefix returns 400
    - Test GET pipeline-execution-status with invalid ARN returns 404
    - Add tests to `tests/unit/test_api_handlers.py`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.3, 6.4, 7.4, 7.5_

- [ ] 7. Create data-loader.html frontend page
  - [ ] 7.1 Create src/frontend/data-loader.html with all sections
    - Create a fresh `src/frontend/data-loader.html` page (DO NOT modify batch-loader.html)
    - Use same dark theme + green accent styling as investigator.html
    - Implement 5 sections:
      1. Case Selector — dropdown populated from GET /case-files
      2. Case Type Profile — dropdown from GET /case-type-profiles, POST to apply on selection
      3. File Upload — drag-and-drop zone + file picker, sends base64 POST to /case-files/{id}/ingest
      4. S3 Prefix Trigger — text input + button, POST to /case-files/{id}/trigger-pipeline
      5. Pipeline Status — polls GET /pipeline-execution-status?arn={arn}, shows status with visual indicator
    - File upload shows progress (N of M), handles per-file errors, shows summary
    - Pipeline status polls every 5 seconds, stops on SUCCEEDED/FAILED
    - Standalone page, no modifications to existing pages
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.5, 7.1, 7.2, 7.3, 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- DO NOT modify batch-loader.html — data-loader.html is a fresh page
- All API routes go through case_files.py mega-dispatcher with {proxy+}
- SFN trigger follows the same boto3 sfn.start_execution pattern as fast_load.py
- No CDK changes needed — all changes are code-level extensions
- Property tests use `hypothesis` with `@given` decorators and `@settings(max_examples=100)`
