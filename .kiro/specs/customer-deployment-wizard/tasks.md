# Implementation Plan: Customer Deployment Wizard

## Overview

Incremental implementation of the Customer Deployment Wizard — shared config.js, Streamlit removal, deployment-wizard.html (6-step wizard), enhanced DeploymentGenerator with tier-aware CloudFormation, CostCalculator service, deployment_handler.py Lambda, ZIP package generation, and sample test run integration. Python backend with Hypothesis property tests, JavaScript/HTML frontend.

## Tasks

- [x] 1. Create shared config.js and migrate all frontend pages
  - [x] 1.1 Create `src/frontend/config.js` with `window.APP_CONFIG` pattern
    - Export API_URL (`'__API_URL__'` placeholder), TENANT_NAME, MODULES_ENABLED, REGION
    - _Requirements: 1.1, 1.3_

  - [x] 1.2 Migrate all 9 HTML pages to import config.js
    - Replace hardcoded `const API_URL = '...'` in each page with `<script src="config.js"></script>` and `const API_URL = window.APP_CONFIG.API_URL`
    - Pages: investigator.html, prosecutor.html, network_discovery.html, document_assembly.html, chatbot.html, pipeline-config.html, wizard.html, portfolio.html, workbench.html
    - Add conditional navigation link rendering based on `MODULES_ENABLED`
    - Display `TENANT_NAME` in page header areas
    - _Requirements: 1.2, 1.4, 1.5_

- [x] 2. Remove Streamlit dependency
  - [x] 2.1 Delete Streamlit files and configuration
    - Delete `src/frontend/app.py`, `src/frontend/pages/case_dashboard.py`, `src/frontend/pages/graph_explorer.py`, `src/frontend/validation.py`
    - Delete `.streamlit/` directory
    - Remove any Streamlit references from `src/frontend/__init__.py`
    - _Requirements: 2.1, 2.2, 2.3_

- [x] 3. Checkpoint — Verify config.js migration and Streamlit removal
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement CostCalculator service
  - [x] 4.1 Create `src/services/cost_calculator.py`
    - Implement `CostCalculator.__init__` loading pricing data from `config/aws_pricing.json`
    - Implement `calculate(tier, modules, document_count, avg_doc_size_mb, entity_count)` returning monthly dict (8 services + total), annual, and one_time dict
    - Implement `_compute_service_cost(service, tier, params)` for per-service calculation
    - All cost values must be non-negative; annual = monthly total × 12
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

  - [ ]* 4.2 Write property test: Cost estimate structural invariants
    - **Property 6: Cost estimate structural invariants**
    - **Validates: Requirements 7.1, 7.2, 7.5**

  - [ ]* 4.3 Write property test: Cost estimate scales with tier
    - **Property 7: Cost estimate scales with tier**
    - **Validates: Requirements 7.1**

  - [ ]* 4.4 Write property test: Data volume computation
    - **Property 5: Data volume computation is correct**
    - **Validates: Requirements 5.2**

  - [ ]* 4.5 Write unit tests for CostCalculator
    - Create `tests/unit/test_cost_calculator.py`
    - Test zero documents, boundary tier values, single module vs all modules
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [x] 5. Enhance DeploymentGenerator with tier-aware template generation
  - [x] 5.1 Add `determine_tier` and `get_tier_sizing` methods
    - Implement tier mapping: Small (<100K), Medium (100K-1M), Large (1M-10M), Enterprise (10M+)
    - Return correct Neptune type, Aurora ACU range, OpenSearch OCU for each tier
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 5.2 Write property test: Tier determination consistency
    - **Property 1: Tier determination is consistent with document count thresholds**
    - **Validates: Requirements 5.3, 6.1, 6.2, 6.3, 6.4**

  - [x] 5.3 Implement `_render_cfn_for_tier` with module-aware resource generation
    - Render CloudFormation template with tier-specific sizing from `get_tier_sizing`
    - Include Lambda functions, API routes, and frontend pages only for selected modules
    - Include Parameters: EnvironmentName, AdminEmail, VpcCidr, DeploymentBucketName, LambdaCodeKey, KmsKeyArn, DataVolumeTier
    - Include Outputs: FrontendURL, ApiGatewayURL, S3DataBucket, AuroraEndpoint, NeptuneEndpoint
    - Handle GovCloud partition (`aws-us-gov`) for us-gov-* regions
    - Propagate KMS key ARN to Aurora, Neptune, S3, OpenSearch resources
    - _Requirements: 4.3, 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 5.4 Write property test: Template includes only selected module resources
    - **Property 4: Template includes only selected module resources**
    - **Validates: Requirements 4.3**

  - [ ]* 5.5 Write property test: CloudFormation template structure invariants
    - **Property 10: CloudFormation template structure invariants**
    - **Validates: Requirements 9.1, 9.2, 9.5**

  - [ ]* 5.6 Write property test: GovCloud partition correctness
    - **Property 11: GovCloud partition correctness**
    - **Validates: Requirements 9.4**

  - [ ]* 5.7 Write property test: KMS encryption propagation
    - **Property 12: KMS encryption propagation**
    - **Validates: Requirements 9.3**

- [x] 6. Implement deployment package ZIP generation
  - [x] 6.1 Add `generate_deployment_package_zip`, `_generate_cost_estimate_md`, `_select_frontend_files`, `_generate_helper_scripts`
    - Generate ZIP containing: deploy.yaml, frontend/ (config.js + selected module HTML + shared pages), scripts/ (migrate_db.sh, seed_statutes.sh, deploy_lambdas.sh), DEPLOYMENT_GUIDE.md, COST_ESTIMATE.md
    - Ensure no Streamlit files in package
    - DEPLOYMENT_GUIDE.md must contain deployer's region, tier, modules, S3 bucket in CLI examples
    - config.js in package must have `'__API_URL__'` placeholder
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 2.4_

  - [ ]* 6.2 Write property test: Deployment package structure completeness
    - **Property 13: Deployment package structure completeness**
    - **Validates: Requirements 10.1, 10.3, 10.4, 10.5, 2.4**

  - [ ]* 6.3 Write property test: Deployment guide contains customer-specific values
    - **Property 14: Deployment guide contains customer-specific values**
    - **Validates: Requirements 10.2**

- [x] 7. Checkpoint — Verify backend services
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Create deployment_handler.py Lambda with API routes
  - [x] 8.1 Create `src/lambdas/api/deployment_handler.py`
    - Implement `dispatch_handler(event, context)` routing to 5 endpoints
    - `POST /deployment/validate` — validate wizard inputs (account ID, CIDR, KMS ARN, modules)
    - `POST /deployment/cost-estimate` — compute cost breakdown via CostCalculator
    - `POST /deployment/sample-run` — start sample pipeline run (1-5 docs) via SampleRunService
    - `GET /deployment/sample-run/{id}` — get sample run status/results with summary aggregation
    - `POST /deployment/generate-package` — generate ZIP and return download URL
    - _Requirements: 3.3, 3.4, 3.5, 4.2, 7.1, 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 10.1_

  - [ ]* 8.2 Write property test: Wizard input validation
    - **Property 2: Wizard input validation correctly accepts and rejects inputs**
    - **Validates: Requirements 3.3, 3.4, 3.5**

  - [ ]* 8.3 Write property test: Module selection requires at least one
    - **Property 3: Module selection requires at least one module**
    - **Validates: Requirements 4.2**

  - [ ]* 8.4 Write property test: Sample test runner accepts 1-5 documents only
    - **Property 8: Sample test runner accepts 1-5 documents only**
    - **Validates: Requirements 8.1**

  - [ ]* 8.5 Write property test: Sample run summary aggregation
    - **Property 9: Sample run summary aggregation is correct**
    - **Validates: Requirements 8.5**

  - [ ]* 8.6 Write unit tests for deployment_handler
    - Create `tests/unit/test_deployment_handler.py`
    - Test each endpoint with valid/invalid inputs, error responses
    - _Requirements: 3.3, 3.4, 3.5, 4.2, 8.1_

- [x] 9. Create deployment-wizard.html with 6-step wizard UI
  - [x] 9.1 Create `src/frontend/deployment-wizard.html`
    - Import config.js, follow existing wizard.html styling (progress bar, step sections, nav buttons)
    - Step 1: Environment Configuration — AWS region dropdown (us-east-1, us-west-2, us-gov-west-1, us-gov-east-1), account ID, VPC CIDR, KMS ARN, S3 bucket name with client-side validation
    - Step 2: Module Selection — 4 checkboxes (Investigator pre-selected), require ≥1 selected
    - Step 3: Data Volume Sizing — document count, avg doc size MB, entity count, auto-compute tier + total volume display
    - Step 4: Cost Estimate Review — monthly/annual breakdown by service, one-time vs recurring, calls POST /deployment/cost-estimate
    - Step 5: Sample Test Run (optional, skippable) — upload 1-5 docs, display extraction results per doc + summary
    - Step 6: Generate Deployment Package — summary review, generate + download ZIP via POST /deployment/generate-package
    - Progress indicator showing current step / total steps
    - Back navigation preserving all entered data
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.4, 5.1, 5.2, 5.3, 5.4, 7.1, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5, 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 9.2 Add deployment-wizard.html navigation link to all frontend pages
    - Add nav link to the nav bar in all 9 HTML pages + deployment-wizard.html itself
    - _Requirements: 11.1_

- [x] 10. Wire API Gateway routes for deployment endpoints
  - [x] 10.1 Update `infra/api_gateway/api_definition.yaml` with deployment routes
    - Add POST /deployment/validate, POST /deployment/cost-estimate, POST /deployment/sample-run, GET /deployment/sample-run/{id}, POST /deployment/generate-package
    - Wire to deployment_handler Lambda
    - _Requirements: 8.1, 9.1, 10.1_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (17 properties total)
- Unit tests validate specific examples and edge cases
- Frontend property tests (Properties 15, 16, 17) for navigation links, step validation, and back-nav data preservation are covered by the wizard HTML implementation and can be validated with fast-check if desired
