# Implementation Plan: Well-Architected Alignment

## Overview

Harden the existing CDK infrastructure to align with the AWS Well-Architected Framework. All changes extend existing constructs and are config-driven — demo configs stay permissive, production configs get hardened. Ordered for minimal risk: low-touch existing file changes first, new construct second, stack wiring third, configs and docs last.

## Tasks

- [x] 1. Extend ApiConstruct with throttling, CORS, and access logging
  - [x] 1.1 Add stage-level throttling to API Gateway
    - Read `config["api"]["throttle_burst_limit"]` and `config["api"]["throttle_rate_limit"]` from deployment config
    - Default to burst=100, rate=50 when keys are absent
    - Add `throttling_burst_limit` and `throttling_rate_limit` to the existing `deploy_options=apigw.StageOptions(...)` block
    - Add `from aws_cdk import aws_logs as logs` import for later use
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 1.2 Make CORS origins config-driven
    - Read `config["api"]["cors_allow_origins"]` — if present (list of strings), use it as `allow_origins`
    - Default to `Cors.ALL_ORIGINS` when key is absent to preserve backward compatibility
    - Do not modify existing `allow_methods` or `allow_headers` settings
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 1.3 Add conditional access logging
    - When `config["api"]["access_logging"]` is `true`, create a `logs.LogGroup` with `retention=RetentionDays.THREE_MONTHS`
    - Wire it into `deploy_options` as `access_log_destination=apigw.LogGroupLogDestination(log_group)` with `access_log_format=apigw.AccessLogFormat.clf()`
    - When key is absent or `false`, do not create the log group or configure access logging
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 1.4 Write CDK assertion tests for ApiConstruct extensions
    - Test custom throttle values are applied to StageDescription
    - Test default throttle values (100/50) when config keys absent
    - Test custom CORS origins appear in AllowOrigins
    - Test default CORS is `["*"]` when config key absent
    - Test access log group created with 90-day retention when enabled
    - Test no AccessLogSetting when access_logging is absent/false
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 8.1, 8.4_

- [x] 2. Extend LambdaConstruct with DLQ, X-Ray, and scoped Bedrock IAM
  - [x] 2.1 Add shared SQS Dead Letter Queue
    - Create `sqs.Queue` named `research-analyst-dlq` with 14-day `retention_period`
    - When `config["encryption"]["kms_key_arn"]` is set, encrypt with KMS; otherwise use SQS-managed encryption
    - Add `dead_letter_queue` optional parameter to `_make_lambda` method
    - Pass the DLQ to `case_files` and all ingestion Lambda functions
    - Add required imports: `aws_sqs as sqs`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 2.2 Enable X-Ray active tracing on all Lambdas
    - Add `tracing=_lambda.Tracing.ACTIVE` to every `_lambda.Function` created by `_make_lambda`
    - This is unconditional — all environments get tracing
    - _Requirements: 4.1, 4.2_

  - [x] 2.3 Scope Bedrock IAM permissions to specific model ARNs
    - Read `bedrock.llm_model_id` and `bedrock.embedding_model_id` from config
    - When both are present, construct model-specific ARNs using `cdk.Fn.sub("arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/<model_id>")`
    - Grant `bedrock:InvokeModel` on LLM ARN to `extract` and `case_files`
    - Grant `bedrock:InvokeModel` on embedding ARN to `embed` and `case_files`
    - Grant `bedrock:InvokeModelWithResponseStream` on LLM ARN to `case_files`
    - Fall back to existing wildcard policy when model IDs are absent
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 2.4 Write CDK assertion tests for LambdaConstruct extensions
    - Test DLQ created with 14-day retention (MessageRetentionPeriod=1209600)
    - Test all Lambda functions have DeadLetterConfig
    - Test DLQ KMS encryption when `encryption.kms_key_arn` is set
    - Test all Lambda resources have `TracingConfig.Mode="Active"`
    - Test scoped IAM policies use specific model ARNs, not wildcard
    - Test InvokeModel granted to extract, embed, case_files; InvokeModelWithResponseStream to case_files only
    - _Requirements: 3.1, 3.2, 3.5, 4.1, 7.1, 7.2, 7.3, 7.4_

- [x] 3. Extend SecurityConstruct with config-driven S3 removal policy
  - [x] 3.1 Add config-driven removal policy to S3 bucket
    - Read `config["s3"]["removal_policy"]` — when `"RETAIN"`, set `removal_policy=RemovalPolicy.RETAIN` and `auto_delete_objects=False`
    - When absent or `"DESTROY"`, keep existing behavior (`RemovalPolicy.DESTROY` with `auto_delete_objects=True`)
    - _Requirements: 6.1, 6.2_

  - [ ]* 3.2 Write CDK assertion tests for SecurityConstruct extensions
    - Test `DeletionPolicy=Retain` and no auto-delete custom resource when `s3.removal_policy="RETAIN"`
    - Test `DeletionPolicy=Delete` when config key absent (default behavior)
    - _Requirements: 6.1, 6.2_

- [ ] 4. Checkpoint — Verify existing construct extensions
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Create ObservabilityConstruct and wire into stack
  - [x] 5.1 Create `infra/cdk/cdk_constructs/observability_construct.py`
    - Create CloudWatch error alarm (Errors sum > 5 in 5 min) for `case_files` Lambda
    - Create CloudWatch duration alarm (Duration p95 > 60000ms in 5 min) for `case_files` Lambda
    - Create CloudWatch error alarm (Errors sum > 5 in 5 min) for each ingestion Lambda
    - Create CloudWatch alarm for Step Functions (ExecutionsFailed sum > 1 in 5 min)
    - When `config["monitoring"]["alarm_sns_topic_arn"]` is set, add SNS topic as alarm action on every alarm
    - Accept `config`, `lambda_functions` dict, and `state_machine` as constructor parameters
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 5.2 Export ObservabilityConstruct from `infra/cdk/cdk_constructs/__init__.py`
    - Add `from .observability_construct import ObservabilityConstruct` import
    - Add `"ObservabilityConstruct"` to `__all__` list
    - _Requirements: 5.1_

  - [x] 5.3 Wire ObservabilityConstruct into ResearchAnalystStack
    - Import `ObservabilityConstruct` in `research_analyst_stack.py`
    - Instantiate after Lambda and Pipeline constructs
    - Pass `config`, Lambda function references (`{**lambdas.api_lambdas, **lambdas.ingestion_lambdas}`), and `pipeline.state_machine`
    - _Requirements: 5.6_

  - [ ]* 5.4 Write CDK assertion tests for ObservabilityConstruct
    - Test Lambda error alarms created for each function
    - Test case_files duration p95 alarm with 60000ms threshold
    - Test Step Functions failure alarm with threshold 1
    - Test SNS alarm actions added when `monitoring.alarm_sns_topic_arn` is configured
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.7_

- [x] 6. Add conditional CloudTrail to ResearchAnalystStack
  - [x] 6.1 Implement conditional CloudTrail trail
    - When `config["logging"]["cloudtrail"]` is `true`, create a `cloudtrail.Trail` in `ResearchAnalystStack`
    - Log management events, store logs in existing S3 data lake bucket under `cloudtrail/` prefix
    - When `config["encryption"]["kms_key_arn"]` is set, encrypt trail logs with that KMS key
    - When `logging.cloudtrail` is absent or `false`, do not create a trail
    - Add required imports: `aws_cloudtrail as cloudtrail`, `aws_kms as kms`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 6.2 Write CDK assertion tests for conditional CloudTrail
    - Test Trail resource created with `S3KeyPrefix="cloudtrail"` when enabled
    - Test no Trail resource when `logging.cloudtrail` is absent/false
    - Test KMSKeyId on Trail when `encryption.kms_key_arn` is set
    - _Requirements: 9.1, 9.4, 9.5_

- [ ] 7. Checkpoint — Verify new construct and stack wiring
  - Ensure all tests pass, ask the user if questions arise.

- [-] 8. Update deployment configs with hardened production values
  - [x] 8.1 Add Well-Architected keys to `govcloud-production.json`
    - Add `api.throttle_burst_limit`, `api.throttle_rate_limit`, `api.cors_allow_origins`, `api.access_logging: true`
    - Add `s3.removal_policy: "RETAIN"`
    - Add `monitoring.alarm_sns_topic_arn` (placeholder ARN)
    - Add `logging.cloudtrail: true`
    - Do not modify any existing keys
    - _Requirements: 1.1, 2.1, 6.1, 8.1, 9.1_

  - [x] 8.2 Add Well-Architected keys to `govcloud-isengard.json`
    - Add same hardened keys as production config (staging mirrors production)
    - Do not modify any existing keys
    - _Requirements: 1.1, 2.1, 6.1, 8.1, 9.1_

  - [x] 8.3 Verify demo configs remain unchanged
    - Confirm `default.json`, `isengard-demo.json`, and `pipeline-only.json` have no new keys added
    - All defaults (permissive throttle, ALL_ORIGINS CORS, DESTROY removal, no CloudTrail) apply automatically
    - _Requirements: 1.2, 2.2, 6.2, 8.4, 9.4_

- [x] 9. Add Well-Architected documentation section
  - [x] 9.1 Add "Well-Architected Framework Alignment" section to `docs/Investigative-Intelligence-Deployment-Architecture.md`
    - Add subsections for all six WAF pillars: Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, Sustainability
    - List specific controls per pillar (throttling, DLQ, X-Ray, alarms, scoped IAM, access logging, CloudTrail, config-driven removal policy)
    - Reference the config keys that enable each control
    - Append to end of document — do not modify existing content
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] 10. Final checkpoint — CDK synth verification
  - Run `cdk synth --no-staging` against default config to verify all constructs compile
  - Run `cdk synth --no-staging -c config=govcloud-production` to verify production config
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All changes extend existing code — no existing construct logic is replaced
- Demo configs stay permissive (no new keys); production configs get hardened values
- This is IaC work — CDK assertion tests are the correct testing approach (no property-based tests)
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after logical groupings
