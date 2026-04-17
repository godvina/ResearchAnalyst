# Implementation Plan: Multi-Environment Deployment

## Overview

Refactor the monolithic `ResearchAnalystStack` into a config-driven, modular CDK stack. Work proceeds foundation-first: ConfigLoader and config files, then modular constructs one at a time, then stack refactoring, CLI enhancement, Lambda runtime degradation, and validation.

## Tasks

- [x] 1. Create ConfigLoader module and deployment config files
  - [x] 1.1 Create `infra/cdk/config_loader.py` with `ConfigLoader` class and `ConfigValidationError` exception
    - Implement `load()`, `_resolve_env_vars()`, `_validate()`, and `_validate_bedrock_models()` methods
    - Validate all required fields, types, conditional fields (e.g., `vpc.cidr` when `create_new=true`, `neptune.min_capacity` when `enabled=true`)
    - Resolve `CDK_DEFAULT_ACCOUNT` and `CDK_DEFAULT_REGION` placeholders from environment variables
    - Validate excluded Bedrock providers against configured model IDs
    - Cross-reference GovCloud configs against `config/bedrock_models.json` FedRAMP registry
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 8.3, 8.4, 14.3_

  - [ ]* 1.2 Write property tests for ConfigLoader (Properties 1–3, 6, 8)
    - **Property 1: Config load round-trip** — serialize valid config to JSON, load via ConfigLoader, verify all fields preserved
    - **Validates: Requirement 1.1**
    - **Property 2: Environment variable placeholder resolution** — set env vars, verify CDK_DEFAULT_ACCOUNT/REGION resolved
    - **Validates: Requirements 1.2, 1.3**
    - **Property 3: Validation rejects missing required fields** — remove any required field, verify ConfigValidationError names the field
    - **Validates: Requirements 1.4, 1.5**
    - **Property 6: Excluded provider model validation** — configure excluded provider matching model prefix, verify error raised
    - **Validates: Requirements 8.3, 8.4**
    - **Property 8: GovCloud FedRAMP-high model validation** — aws-us-gov configs must only use fedramp_high models
    - **Validates: Requirement 14.3**
    - Create Hypothesis strategies: `valid_config()`, `valid_model_id()`, `valid_account_id()`, `valid_region()`
    - Place tests in `tests/infra/test_config_loader.py`

  - [x] 1.3 Create deployment config JSON files in `infra/cdk/deployment-configs/`
    - Create `default.json` reproducing current dev environment (account `974220725866`, region `us-east-1`, public subnets, no KMS, all services enabled)
    - Create `isengard-demo.json` with `CDK_DEFAULT_ACCOUNT`/`CDK_DEFAULT_REGION`, `vpc.create_new=true`, all services enabled
    - Create `govcloud-isengard.json` with partition `aws-us-gov`, region `us-gov-west-1`, private subnets, KMS, Neptune disabled, OpenSearch disabled, VPC flow logs
    - Create `govcloud-production.json` with same security controls as govcloud-isengard plus production capacity and CUI tag
    - _Requirements: 1.6, 14.1, 14.2, 14.3, 14.4, 15.1, 15.2_

  - [ ]* 1.4 Write unit tests for ConfigLoader
    - Test loading each config file and verifying key field values
    - Test env var resolution with mocked environment variables
    - Test each validation error case (missing field, wrong type, conditional field missing, excluded provider)
    - Place tests in `tests/infra/test_config_loader.py`

- [x] 2. Checkpoint — Ensure ConfigLoader tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Create SecurityConstruct and VpcConstruct
  - [x] 3.1 Create `infra/cdk/constructs/security_construct.py`
    - Implement `SecurityConstruct` with `data_bucket` property
    - S3 bucket with versioning, block public access, lifecycle rules
    - KMS encryption when `encryption.kms_key_arn` is non-null, else S3-managed
    - TLS enforcement bucket policy when `encryption.enforce_tls` is `true`
    - Use `override_logical_id()` to preserve existing logical IDs from current stack
    - _Requirements: 7.1, 7.2_

  - [x] 3.2 Create `infra/cdk/constructs/vpc_construct.py`
    - Implement `VpcConstruct` with `vpc` property
    - `create_new=true` → new VPC with config CIDR, 2 AZs, 1 NAT GW, public/private/isolated subnets
    - `create_new=false` → `Vpc.from_lookup(existing_vpc_id)`
    - VPC flow logs to CloudWatch when `logging.vpc_flow_logs=true`
    - Use `override_logical_id()` to preserve existing logical IDs
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 4. Create AuroraConstruct
  - [x] 4.1 Create `infra/cdk/constructs/aurora_construct.py`
    - Implement `AuroraConstruct` with `cluster`, `secret`, `proxy` properties
    - Aurora Serverless v2 with capacity from config `aurora.min_capacity`/`aurora.max_capacity`
    - Subnet placement from `aurora.subnet_type` (PUBLIC or PRIVATE_WITH_EGRESS)
    - KMS encryption when `encryption.kms_key_arn` is non-null
    - RDS Proxy with `require_tls=True`
    - Security group ingress from VPC CIDR on port 5432
    - Use `override_logical_id()` to preserve existing logical IDs
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 7.4, 17.1, 17.2_

- [x] 5. Create NeptuneConstruct
  - [x] 5.1 Create `infra/cdk/constructs/neptune_construct.py`
    - Implement `NeptuneConstruct` with `cluster`, `enabled` properties
    - `neptune.enabled=true` → create Neptune Serverless with configured capacity and subnet type
    - `neptune.enabled=false` → no resources created, `cluster` returns `None`
    - Security group ingress from VPC CIDR on port 8182
    - Use `override_logical_id()` to preserve existing logical IDs
    - _Requirements: 4.1, 4.2, 17.1, 17.2_

- [x] 6. Create OpenSearchConstruct
  - [x] 6.1 Create `infra/cdk/constructs/opensearch_construct.py`
    - Implement `OpenSearchConstruct` with `collection`, `endpoint`, `collection_id`, `enabled` properties
    - `mode="serverless"` → AOSS collection with encryption, network, data access policies and VPC endpoint
    - `mode="disabled"` → no resources, endpoint/collection_id return empty strings
    - KMS encryption on AOSS when `encryption.kms_key_arn` is set
    - Use `override_logical_id()` to preserve existing logical IDs
    - _Requirements: 5.1, 5.2, 7.3, 17.1, 17.2_

- [x] 7. Create LambdaConstruct
  - [x] 7.1 Create `infra/cdk/constructs/lambda_construct.py`
    - Implement `LambdaConstruct` with `api_lambdas`, `ingestion_lambdas` properties
    - Build Lambda env vars from construct outputs including feature flags (`NEPTUNE_ENABLED`, `OPENSEARCH_ENABLED`, `REKOGNITION_ENABLED`)
    - Set `NEPTUNE_ENDPOINT` to empty string when Neptune disabled
    - Set `OPENSEARCH_ENDPOINT`/`OPENSEARCH_COLLECTION_ID` to empty strings when OpenSearch disabled
    - Set `BEDROCK_LLM_MODEL_ID` and `BEDROCK_EMBEDDING_MODEL_ID` from config
    - `features.pipeline_only=true` → skip API Lambda creation
    - `features.rekognition=false` → skip rekognition Lambda and IAM permissions
    - All IAM ARNs use `cdk.Aws.PARTITION` instead of hardcoded `aws`
    - Use `override_logical_id()` to preserve existing logical IDs
    - _Requirements: 4.3, 4.4, 5.3, 5.4, 6.1, 6.2, 6.3, 8.1, 8.2, 9.1, 9.2, 9.3, 9.4, 16.1_

  - [ ]* 7.2 Write property tests for Lambda env var building (Properties 4, 5, 7)
    - **Property 4: Disabled services produce empty endpoint env vars** — Neptune disabled → NEPTUNE_ENDPOINT="", OpenSearch disabled → OPENSEARCH_ENDPOINT=""
    - **Validates: Requirements 4.3, 5.3**
    - **Property 5: Bedrock model IDs flow from config to Lambda env vars** — arbitrary model IDs appear in env var dict
    - **Validates: Requirements 8.1, 8.2**
    - **Property 7: Feature toggles flow to Lambda env vars** — boolean toggles map to "true"/"false" strings
    - **Validates: Requirements 9.4, 16.1**
    - Place tests in `tests/infra/test_env_var_builder.py`

- [x] 8. Create PipelineConstruct and ApiConstruct
  - [x] 8.1 Create `infra/cdk/constructs/pipeline_construct.py`
    - Implement `PipelineConstruct` with `state_machine` property
    - Create Step Functions state machine from ASL definition
    - Substitute Lambda ARNs into ASL template
    - Grant invoke permissions
    - Use `override_logical_id()` to preserve existing logical IDs
    - _Requirements: 9.3_

  - [x] 8.2 Create `infra/cdk/constructs/api_construct.py`
    - Implement `ApiConstruct` with `api` property
    - `features.pipeline_only=true` → no API Gateway created
    - Otherwise create LambdaRestApi with CORS and proxy integration
    - Use `override_logical_id()` to preserve existing logical IDs
    - _Requirements: 9.1_

- [x] 9. Checkpoint — Ensure all constructs compile cleanly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Refactor ResearchAnalystStack to use modular constructs
  - [x] 10.1 Update `infra/cdk/stacks/research_analyst_stack.py` to accept `config` parameter and instantiate constructs
    - Accept `config: dict` in constructor
    - Apply tags from `config["tags"]` and `Environment` tag from `config["environment_name"]`
    - Instantiate constructs in order: VPC → Security → Aurora → Neptune → OpenSearch → Lambda → Pipeline → Api
    - Add CloudFormation Parameters (`EnvironmentName`, `AWSAccountId`, `AWSRegion`, `KMSKeyArn`)
    - Add CloudFormation Conditions for Neptune, OpenSearch, Rekognition
    - Add CloudFormation Outputs for API Gateway URL, S3 bucket, Aurora endpoint, Neptune endpoint
    - Remove all existing inline resource creation methods (replaced by constructs)
    - _Requirements: 10.1, 10.2, 10.3, 11.1, 11.2, 11.3, 11.4, 12.1, 12.2, 12.3, 12.4, 19.1, 19.3_

  - [x] 10.2 Update `infra/cdk/app.py` to use ConfigLoader
    - Read config path from CDK context (`-c config=...`)
    - Load and validate config via `ConfigLoader`
    - Pass config to `ResearchAnalystStack` constructor
    - Set `env` from config `account`/`region`
    - _Requirements: 1.1, 11.2_

- [x] 11. Enhance Deploy CLI
  - [x] 11.1 Update `infra/cdk/deploy.py` with `--config` flag
    - Add `argparse` with `--config` defaulting to `infra/cdk/deployment-configs/default.json`
    - Load and validate config before synth; print errors and exit on failure
    - Pass config path to CDK synth via context flag
    - Update `publish_assets()` and `deploy()` to use config account/region
    - Print post-deployment summary with API Gateway URL, bucket name, next steps
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 19.2_

- [x] 12. Checkpoint — Ensure stack synth works with default.json
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Add Lambda runtime graceful degradation
  - [x] 13.1 Add feature flag checks to Neptune-dependent Lambda code
    - Add `NEPTUNE_ENABLED` env var check to `src/services/neptune_graph_loader.py` and `src/db/neptune.py`
    - When `NEPTUNE_ENABLED != "true"`, return empty results `{"entities": [], "relationships": [], "source": "disabled"}` without raising errors
    - Default missing env var to `"false"` (conservative)
    - _Requirements: 16.1, 16.2_

  - [x] 13.2 Add feature flag checks to OpenSearch-dependent Lambda code
    - Add `OPENSEARCH_ENABLED` env var check to `src/services/opensearch_serverless_backend.py` and `src/services/semantic_search_service.py`
    - When `OPENSEARCH_ENABLED != "true"`, fall back to Aurora pgvector search via `src/services/aurora_pgvector_backend.py`
    - _Requirements: 16.1, 16.3_

  - [x] 13.3 Add feature flag checks to Rekognition-dependent Lambda code
    - Add `REKOGNITION_ENABLED` env var check to `src/lambdas/ingestion/rekognition_handler.py` and `src/services/face_crop_service.py`
    - When `REKOGNITION_ENABLED != "true"`, return `{"labels": [], "faces": [], "source": "disabled"}` without raising errors
    - _Requirements: 9.2, 16.1_

  - [ ]* 13.4 Write property tests for Lambda graceful degradation (Properties 9, 10)
    - **Property 9: Neptune graceful degradation returns empty results** — when NEPTUNE_ENABLED="false", graph queries return empty result set without exceptions
    - **Validates: Requirement 16.2**
    - **Property 10: OpenSearch fallback to pgvector** — when OPENSEARCH_ENABLED="false", search delegates to Aurora pgvector path
    - **Validates: Requirement 16.3**
    - Place tests in `tests/infra/test_lambda_degradation.py`

  - [ ]* 13.5 Write unit tests for graceful degradation
    - Test Neptune disabled returns empty results
    - Test OpenSearch disabled falls back to pgvector
    - Test Rekognition disabled returns empty results
    - Test missing env var defaults to "false"
    - Place tests in `tests/infra/test_lambda_degradation.py`

- [x] 14. Checkpoint — Ensure graceful degradation tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. CDK assertion tests and backward compatibility validation
  - [ ]* 15.1 Write CDK assertion tests
    - `tests/infra/test_stack_default.py`: Synth with `default.json`, verify logical IDs match current template
    - `tests/infra/test_stack_govcloud.py`: Synth with GovCloud config, verify no Neptune/OpenSearch resources, verify partition in ARNs
    - `tests/infra/test_stack_conditional.py`: Synth with `pipeline_only=true`, verify no API Gateway; toggle services and verify
    - `tests/infra/test_stack_encryption.py`: Synth with KMS key, verify S3/Aurora/OpenSearch encryption config
    - `tests/infra/test_stack_template.py`: Verify CloudFormation Parameters, Conditions, and Outputs exist
    - _Requirements: 11.4, 12.1, 12.2, 12.3, 12.4, 19.1, 19.3_

  - [x] 15.2 Validate backward compatibility
    - Run `cdk synth` with `default.json` and compare CloudFormation logical IDs against current synthesized template
    - Verify no hardcoded `arn:aws:` strings remain in GovCloud template output
    - Verify all 4 config profiles synth without errors
    - _Requirements: 6.1, 6.2, 6.3, 19.1, 19.3_

- [x] 16. Update deployment documentation
  - [x] 16.1 Update `docs/deployment-guide.md` with multi-environment instructions
    - Add prerequisites section (AWS CLI, CDK, Python versions, account access)
    - Add step-by-step instructions for Demo, GovCloud Test, and Production tiers
    - Add example config files with inline comments
    - Add troubleshooting section for common deployment failures
    - Add post-deployment verification checklist
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

- [x] 17. Final checkpoint — Full validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The `default.json` backward compatibility validation (task 15.2) is the critical acceptance gate
