# Requirements Document

## Introduction

The Investigative Intelligence Platform is a serverless AI-powered investigative analysis system deployed on AWS. A code review against the AWS Well-Architected Framework has identified gaps across the Reliability, Security, Operational Excellence, and Performance Efficiency pillars. This spec hardens the existing CDK infrastructure to close those gaps before customer-facing demos and GovCloud pilot deployments. All changes extend existing constructs and are config-driven — demo configs remain permissive while production configs get hardened.

## Glossary

- **Platform**: The Investigative Intelligence Platform CDK application deployed via `ResearchAnalystStack`.
- **API_Gateway**: The `LambdaRestApi` REST API created by `ApiConstruct` in `infra/cdk/cdk_constructs/api_construct.py`.
- **Lambda_Construct**: The construct in `infra/cdk/cdk_constructs/lambda_construct.py` that creates all Lambda functions and IAM policies.
- **Security_Construct**: The construct in `infra/cdk/cdk_constructs/security_construct.py` that creates the S3 data lake bucket.
- **Pipeline_Construct**: The construct in `infra/cdk/cdk_constructs/pipeline_construct.py` that creates the Step Functions state machine.
- **Deployment_Config**: A JSON file in `infra/cdk/deployment-configs/` that controls environment-specific resource settings.
- **DLQ**: Dead Letter Queue — an SQS queue that captures failed asynchronous Lambda invocations.
- **Observability_Construct**: A new CDK construct to be created at `infra/cdk/cdk_constructs/observability_construct.py` for CloudWatch alarms.
- **WAF_Pillar**: One of the six pillars of the AWS Well-Architected Framework (Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, Sustainability).

## Requirements

### Requirement 1: API Gateway Throttling

**User Story:** As a platform operator, I want API Gateway to enforce rate limits, so that a runaway frontend loop or unexpected traffic spike cannot exhaust Lambda concurrency and degrade the platform for all users.

#### Acceptance Criteria

1. WHEN the Platform is deployed with a Deployment_Config that includes `api.throttle_burst_limit` and `api.throttle_rate_limit`, THE API_Gateway SHALL apply those values as the stage-level throttle settings in `deploy_options`.
2. WHEN the Deployment_Config does not include `api.throttle_burst_limit` or `api.throttle_rate_limit`, THE API_Gateway SHALL apply default throttle settings of 100 requests per second burst limit and 50 requests per second steady-state rate limit.
3. THE API_Gateway SHALL apply throttle settings via `apigw.StageOptions` `throttling_burst_limit` and `throttling_rate_limit` parameters within the existing `deploy_options` block.

### Requirement 2: Config-Driven CORS Origins

**User Story:** As a security engineer, I want CORS origins on the API Gateway to be restricted in production, so that only authorized frontend domains can make cross-origin requests.

#### Acceptance Criteria

1. WHEN the Deployment_Config includes `api.cors_allow_origins` as a list of origin strings, THE API_Gateway SHALL use those origins in the `allow_origins` parameter of `default_cors_preflight_options`.
2. WHEN the Deployment_Config does not include `api.cors_allow_origins`, THE API_Gateway SHALL default to `Cors.ALL_ORIGINS` to preserve backward compatibility with demo deployments.
3. THE API_Gateway SHALL read CORS configuration from `config.get("api", {})` without modifying any other existing CORS settings (allow_methods, allow_headers).

### Requirement 3: Lambda Dead Letter Queues

**User Story:** As a platform operator, I want failed asynchronous Lambda invocations to be captured in a Dead Letter Queue, so that silent failures are visible and can be investigated.

#### Acceptance Criteria

1. THE Lambda_Construct SHALL create one SQS queue named `research-analyst-dlq` to serve as the shared Dead Letter Queue for Lambda functions.
2. THE Lambda_Construct SHALL configure the `dead_letter_queue` property on the `case_files` Lambda function to point to the shared DLQ.
3. THE Lambda_Construct SHALL configure the `dead_letter_queue` property on each ingestion Lambda function to point to the shared DLQ.
4. THE Lambda_Construct SHALL set the DLQ message retention period to 14 days.
5. WHEN the Deployment_Config includes `encryption.kms_key_arn`, THE Lambda_Construct SHALL encrypt the DLQ using that KMS key.

### Requirement 4: Lambda X-Ray Tracing

**User Story:** As a platform operator, I want distributed tracing enabled on all Lambda functions, so that timeout issues, cold starts, and downstream service latency can be diagnosed.

#### Acceptance Criteria

1. THE Lambda_Construct SHALL set `tracing=Tracing.ACTIVE` on every Lambda function created by the `_make_lambda` method.
2. THE Lambda_Construct SHALL use `aws_cdk.aws_lambda.Tracing.ACTIVE` to enable AWS X-Ray active tracing.

### Requirement 5: CloudWatch Alarms

**User Story:** As a platform operator, I want CloudWatch alarms on critical failure metrics, so that Lambda errors, duration spikes, and Step Functions failures trigger alerts without manual log monitoring.

#### Acceptance Criteria

1. THE Platform SHALL include a new Observability_Construct at `infra/cdk/cdk_constructs/observability_construct.py`.
2. THE Observability_Construct SHALL create a CloudWatch alarm for the `case_files` Lambda function that triggers when the `Errors` metric sum exceeds 5 in a 5-minute evaluation period.
3. THE Observability_Construct SHALL create a CloudWatch alarm for the `case_files` Lambda function that triggers when the `Duration` p95 metric exceeds 60000 milliseconds in a 5-minute evaluation period.
4. THE Observability_Construct SHALL create a CloudWatch alarm for each ingestion Lambda function that triggers when the `Errors` metric sum exceeds 5 in a 5-minute evaluation period.
5. THE Observability_Construct SHALL create a CloudWatch alarm for the Step Functions state machine that triggers when the `ExecutionsFailed` metric sum exceeds 1 in a 5-minute evaluation period.
6. THE Observability_Construct SHALL be instantiated in `ResearchAnalystStack` and receive references to the Lambda functions and the Step Functions state machine.
7. WHEN the Deployment_Config includes `monitoring.alarm_sns_topic_arn`, THE Observability_Construct SHALL add that SNS topic as an alarm action on every alarm.

### Requirement 6: Config-Driven S3 Removal Policy

**User Story:** As a platform operator, I want the S3 data lake bucket to retain data in production environments, so that `cdk destroy` cannot accidentally wipe investigation evidence.

#### Acceptance Criteria

1. WHEN the Deployment_Config includes `s3.removal_policy` set to `"RETAIN"`, THE Security_Construct SHALL set the S3 bucket `removal_policy` to `RemovalPolicy.RETAIN` and `auto_delete_objects` to `False`.
2. WHEN the Deployment_Config does not include `s3.removal_policy` or sets it to `"DESTROY"`, THE Security_Construct SHALL keep the existing behavior of `RemovalPolicy.DESTROY` with `auto_delete_objects=True`.

### Requirement 7: Scoped Bedrock IAM Permissions

**User Story:** As a security engineer, I want Bedrock IAM permissions scoped to specific model ARNs from the deployment config, so that Lambda functions follow least-privilege and cannot invoke unauthorized models.

#### Acceptance Criteria

1. WHEN the Deployment_Config includes `bedrock.llm_model_id` and `bedrock.embedding_model_id`, THE Lambda_Construct SHALL construct Bedrock `InvokeModel` IAM policy resources using those specific model IDs instead of the wildcard `foundation-model/*` pattern.
2. THE Lambda_Construct SHALL grant `bedrock:InvokeModel` on the LLM model ARN to the `extract` and `case_files` Lambda functions.
3. THE Lambda_Construct SHALL grant `bedrock:InvokeModel` on the embedding model ARN to the `embed` and `case_files` Lambda functions.
4. THE Lambda_Construct SHALL grant `bedrock:InvokeModelWithResponseStream` on the LLM model ARN to the `case_files` Lambda function.
5. THE Lambda_Construct SHALL use `Fn.sub("arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/<model_id>")` to construct partition-aware model ARNs.

### Requirement 8: API Gateway Access Logging

**User Story:** As a security engineer, I want API Gateway access logs written to CloudWatch Logs, so that all API requests are auditable for compliance and incident investigation.

#### Acceptance Criteria

1. WHEN the Deployment_Config includes `api.access_logging` set to `true`, THE API_Gateway SHALL create a CloudWatch Logs log group for access logs.
2. WHEN `api.access_logging` is enabled, THE API_Gateway SHALL configure `deploy_options` with `access_log_destination` pointing to the created log group.
3. WHEN `api.access_logging` is enabled, THE API_Gateway SHALL use the `AccessLogFormat.clf()` combined log format for access log entries.
4. WHEN the Deployment_Config does not include `api.access_logging` or sets it to `false`, THE API_Gateway SHALL not configure access logging to preserve backward compatibility.
5. THE API_Gateway SHALL set the access log group retention to 90 days.

### Requirement 9: Conditional CloudTrail

**User Story:** As a compliance officer, I want CloudTrail deployed as part of the CDK stack when configured, so that all AWS API calls are logged for audit without manual post-deployment setup.

#### Acceptance Criteria

1. WHEN the Deployment_Config includes `logging.cloudtrail` set to `true`, THE Platform SHALL create a CloudTrail trail within the `ResearchAnalystStack`.
2. THE CloudTrail trail SHALL log management events for all AWS API calls in the account.
3. THE CloudTrail trail SHALL store logs in the existing S3 data lake bucket under the `cloudtrail/` prefix.
4. WHEN the Deployment_Config does not include `logging.cloudtrail` or sets it to `false`, THE Platform SHALL not create a CloudTrail trail.
5. WHEN the Deployment_Config includes `encryption.kms_key_arn`, THE CloudTrail trail SHALL encrypt logs using that KMS key.

### Requirement 10: Well-Architected Documentation

**User Story:** As a solutions architect preparing for customer demos and GovCloud pilots, I want the deployment architecture document to include a Well-Architected alignment section, so that reviewers can see how each pillar is addressed.

#### Acceptance Criteria

1. THE Platform documentation at `docs/Investigative-Intelligence-Deployment-Architecture.md` SHALL include a new section titled "Well-Architected Framework Alignment".
2. THE Well-Architected section SHALL contain a subsection for each of the six WAF pillars: Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, and Sustainability.
3. Each pillar subsection SHALL list the specific controls implemented by this spec (throttling, DLQ, X-Ray, alarms, scoped IAM, access logging, CloudTrail, config-driven removal policy).
4. THE Well-Architected section SHALL reference the config keys that enable each control (e.g., `api.throttle_burst_limit`, `logging.cloudtrail`, `s3.removal_policy`).
