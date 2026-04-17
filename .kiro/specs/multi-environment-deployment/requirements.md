# Requirements Document

## Introduction

The Investigative Intelligence Platform is currently deployed as a monolithic CDK stack with hardcoded values (account ID, region, VPC lookup, public subnets) targeting a single AWS dev account. This feature introduces a config-driven deployment system that parameterizes the entire infrastructure, enabling deployment to any AWS account — including Isengard demo accounts, GovCloud Isengard accounts for FedRAMP testing, and customer production accounts (e.g., DOJ) with strict security policies. The system must support graceful degradation when AWS services are unavailable in certain partitions, partition-aware IAM ARNs, conditional resource creation, and standalone CloudFormation template output for non-technical deployment.

## Glossary

- **Deployment_Config**: A JSON file in `infra/cdk/deployment-configs/` that parameterizes all infrastructure settings for a target environment (account, region, partition, service toggles, capacity, encryption, tags)
- **CDK_Stack**: The Python-based aws-cdk-lib stack (`ResearchAnalystStack`) that synthesizes into a CloudFormation template
- **Config_Loader**: A Python module that reads and validates a Deployment_Config JSON file at CDK synth time
- **Partition**: The AWS partition identifier — `aws` for commercial regions, `aws-us-gov` for GovCloud regions
- **Deploy_CLI**: The deployment script (`infra/cdk/deploy.py`) that orchestrates synth, asset publishing, and CloudFormation deployment
- **Modular_Construct**: A CDK Construct class encapsulating a logical group of related AWS resources (e.g., VPC, Aurora, Neptune) with conditional creation based on Deployment_Config
- **Graceful_Degradation**: The ability of the CDK_Stack to skip unavailable services (Neptune, OpenSearch Serverless) without breaking the remaining infrastructure or Lambda runtime behavior
- **FedRAMP_Model_Registry**: The `config/bedrock_models.json` file that maps AWS regions to FedRAMP compliance levels and lists approved Bedrock model IDs per level
- **CloudFormation_Template**: The synthesized JSON template output from `cdk synth` that can be deployed standalone via the AWS CloudFormation console without the CDK CLI
- **Deployment_Runbook**: The documentation at `docs/deployment-guide.md` with step-by-step instructions for each deployment tier

## Requirements

### Requirement 1: Deployment Configuration Schema

**User Story:** As a platform operator, I want a JSON configuration file that parameterizes all infrastructure settings, so that I can deploy the platform to different AWS accounts by changing a single file.

#### Acceptance Criteria

1. THE Config_Loader SHALL read a Deployment_Config JSON file from `infra/cdk/deployment-configs/` containing the fields: `environment_name`, `account`, `region`, `partition`, `vpc`, `aurora`, `neptune`, `opensearch`, `encryption`, `bedrock`, `features`, `tags`, and `logging`
2. WHEN the `account` field is set to `"CDK_DEFAULT_ACCOUNT"`, THE Config_Loader SHALL resolve the value from the `CDK_DEFAULT_ACCOUNT` environment variable
3. WHEN the `region` field is set to `"CDK_DEFAULT_REGION"`, THE Config_Loader SHALL resolve the value from the `CDK_DEFAULT_REGION` environment variable
4. THE Config_Loader SHALL validate that all required fields are present and have correct types before CDK synthesis begins
5. IF a required field is missing or has an invalid type, THEN THE Config_Loader SHALL raise a descriptive error identifying the field name and expected type
6. THE Config_Loader SHALL provide a `default.json` configuration that reproduces the current dev environment (account `974220725866`, region `us-east-1`, partition `aws`, public subnets, no KMS, Neptune enabled, OpenSearch Serverless enabled)

### Requirement 2: VPC Configuration

**User Story:** As a platform operator, I want to choose between creating a new VPC or importing an existing one, so that I can deploy into accounts with pre-provisioned networking.

#### Acceptance Criteria

1. WHEN `vpc.create_new` is `true`, THE CDK_Stack SHALL create a new VPC with the CIDR block specified in `vpc.cidr`, two availability zones, one NAT gateway, and public, private, and isolated subnet tiers
2. WHEN `vpc.create_new` is `false`, THE CDK_Stack SHALL import the existing VPC identified by `vpc.existing_vpc_id`
3. THE CDK_Stack SHALL use the VPC CIDR block for all security group ingress rules instead of hardcoded CIDR values
4. WHEN `logging.vpc_flow_logs` is `true`, THE CDK_Stack SHALL enable VPC flow logs to CloudWatch Logs on the VPC

### Requirement 3: Aurora Serverless v2 Configuration

**User Story:** As a platform operator, I want to configure Aurora capacity, subnet placement, and encryption per environment, so that dev environments use minimal resources while production environments use private subnets with KMS encryption.

#### Acceptance Criteria

1. THE CDK_Stack SHALL create the Aurora Serverless v2 cluster with `serverless_v2_min_capacity` and `serverless_v2_max_capacity` set to the values from `aurora.min_capacity` and `aurora.max_capacity` in the Deployment_Config
2. WHEN `aurora.subnet_type` is `"PRIVATE_WITH_EGRESS"`, THE CDK_Stack SHALL place the Aurora cluster in private subnets with NAT gateway egress
3. WHEN `aurora.subnet_type` is `"PUBLIC"`, THE CDK_Stack SHALL place the Aurora cluster in public subnets
4. WHEN `encryption.kms_key_arn` is a non-null string, THE CDK_Stack SHALL encrypt the Aurora cluster using the specified KMS customer-managed key
5. WHEN `encryption.kms_key_arn` is `null`, THE CDK_Stack SHALL use the default AWS-managed encryption for the Aurora cluster

### Requirement 4: Conditional Neptune Creation

**User Story:** As a platform operator, I want to disable Neptune in environments where it is unavailable (e.g., GovCloud), so that the platform deploys without graph database features when necessary.

#### Acceptance Criteria

1. WHEN `neptune.enabled` is `true`, THE CDK_Stack SHALL create the Neptune Serverless cluster with capacity from `neptune.min_capacity` and `neptune.max_capacity`, and subnet placement from `neptune.subnet_type`
2. WHEN `neptune.enabled` is `false`, THE CDK_Stack SHALL skip Neptune cluster creation entirely
3. WHEN `neptune.enabled` is `false`, THE CDK_Stack SHALL set the Lambda environment variable `NEPTUNE_ENDPOINT` to an empty string
4. WHEN `neptune.enabled` is `false`, THE CDK_Stack SHALL omit Neptune IAM policy statements from all Lambda execution roles

### Requirement 5: Conditional OpenSearch Configuration

**User Story:** As a platform operator, I want to select between OpenSearch Serverless, provisioned OpenSearch, or disabled OpenSearch, so that I can adapt to service availability in different AWS partitions.

#### Acceptance Criteria

1. WHEN `opensearch.mode` is `"serverless"`, THE CDK_Stack SHALL create an OpenSearch Serverless VECTORSEARCH collection with encryption, network, and data access policies
2. WHEN `opensearch.mode` is `"disabled"`, THE CDK_Stack SHALL skip all OpenSearch resource creation
3. WHEN `opensearch.mode` is `"disabled"`, THE CDK_Stack SHALL set the Lambda environment variables `OPENSEARCH_ENDPOINT` and `OPENSEARCH_COLLECTION_ID` to empty strings
4. WHEN `opensearch.enabled` is `false`, THE CDK_Stack SHALL omit OpenSearch IAM policy statements from all Lambda execution roles

### Requirement 6: Partition-Aware IAM Policies

**User Story:** As a platform operator, I want all IAM policy ARNs to use the correct AWS partition, so that the stack deploys in both commercial (`aws`) and GovCloud (`aws-us-gov`) partitions.

#### Acceptance Criteria

1. THE CDK_Stack SHALL construct all IAM policy resource ARNs using `arn:${partition}:` where `partition` is read from the Deployment_Config
2. THE CDK_Stack SHALL use `cdk.Aws.PARTITION` or the Deployment_Config `partition` value for Bedrock, Neptune, RDS, S3, Secrets Manager, Step Functions, Rekognition, Textract, and Lambda ARN construction
3. THE CDK_Stack SHALL replace all existing hardcoded `arn:aws:` strings with partition-parameterized ARN construction

### Requirement 7: Encryption and TLS Configuration

**User Story:** As a platform operator, I want to enforce KMS encryption and TLS for production environments, so that the platform meets FedRAMP and DOJ security requirements.

#### Acceptance Criteria

1. WHEN `encryption.kms_key_arn` is a non-null string, THE CDK_Stack SHALL encrypt the S3 data lake bucket using the specified KMS customer-managed key
2. WHEN `encryption.enforce_tls` is `true`, THE CDK_Stack SHALL configure the S3 bucket policy to deny requests that do not use TLS
3. WHEN `encryption.kms_key_arn` is a non-null string and `opensearch.mode` is `"serverless"`, THE CDK_Stack SHALL configure the OpenSearch Serverless encryption policy to use the specified KMS key instead of the AWS-owned key
4. THE CDK_Stack SHALL maintain `require_tls=True` on the RDS Proxy for all environments

### Requirement 8: Bedrock Model Configuration

**User Story:** As a platform operator, I want to specify which Bedrock models to use per environment, so that GovCloud deployments use only FedRAMP-approved models.

#### Acceptance Criteria

1. THE CDK_Stack SHALL set the Lambda environment variable `BEDROCK_LLM_MODEL_ID` to the value from `bedrock.llm_model_id` in the Deployment_Config
2. THE CDK_Stack SHALL set the Lambda environment variable `BEDROCK_EMBEDDING_MODEL_ID` to the value from `bedrock.embedding_model_id` in the Deployment_Config
3. WHEN `bedrock.excluded_providers` contains one or more provider names, THE Config_Loader SHALL validate that the configured `llm_model_id` and `embedding_model_id` do not belong to an excluded provider
4. IF a configured Bedrock model ID belongs to an excluded provider, THEN THE Config_Loader SHALL raise an error identifying the model and the excluded provider

### Requirement 9: Feature Toggle System

**User Story:** As a platform operator, I want to selectively deploy subsets of the platform (pipeline only, investigative UI, discovery engine, image analysis), so that initial deployments can start with core ingestion and add features incrementally.

#### Acceptance Criteria

1. WHEN `features.pipeline_only` is `true`, THE CDK_Stack SHALL create only the ingestion pipeline resources (S3, Aurora, Lambda ingestion functions, Step Functions state machine) and skip API Gateway, API Lambda functions, and frontend-related resources
2. WHEN `features.rekognition` is `false`, THE CDK_Stack SHALL skip creation of the Rekognition-related Lambda functions and omit Rekognition IAM permissions
3. THE CDK_Stack SHALL always create the core resources (VPC, S3, Aurora, ingestion Lambdas, Step Functions) regardless of feature toggle settings
4. THE CDK_Stack SHALL pass feature toggle values as Lambda environment variables so that runtime code can check which features are available

### Requirement 10: Mandatory Resource Tagging

**User Story:** As a platform operator, I want all AWS resources to be tagged with environment-specific metadata, so that cost allocation and compliance auditing work across all deployment tiers.

#### Acceptance Criteria

1. THE CDK_Stack SHALL apply all key-value pairs from the `tags` object in the Deployment_Config as CloudFormation stack-level tags
2. THE CDK_Stack SHALL add an `Environment` tag with the value of `environment_name` from the Deployment_Config to all resources
3. WHEN the `tags` object is empty or missing, THE CDK_Stack SHALL apply only the `Environment` tag

### Requirement 11: CDK Stack Modular Refactoring

**User Story:** As a developer, I want the monolithic CDK stack refactored into modular constructs, so that each infrastructure concern is isolated and conditionally created based on the Deployment_Config.

#### Acceptance Criteria

1. THE CDK_Stack SHALL organize resources into separate Construct classes for VPC, Aurora, Neptune, OpenSearch, Lambda, Step Functions, API Gateway, and Security
2. EACH Modular_Construct SHALL accept the Deployment_Config as a constructor parameter and create resources conditionally based on the configuration
3. THE CDK_Stack SHALL maintain all resources within a single CloudFormation stack (not cross-stack references)
4. THE CDK_Stack SHALL produce identical CloudFormation output when using the `default.json` Deployment_Config compared to the current hardcoded stack

### Requirement 12: CloudFormation Standalone Template Output

**User Story:** As a non-technical user, I want to deploy the platform via the CloudFormation console without installing the CDK CLI, so that I can stand up the platform using only a web browser.

#### Acceptance Criteria

1. WHEN `cdk synth` completes, THE CDK_Stack SHALL produce a CloudFormation template that is deployable via the AWS CloudFormation console without the CDK CLI
2. THE CloudFormation_Template SHALL include CloudFormation Parameters for `EnvironmentName`, `AWSAccountId`, `AWSRegion`, and `KMSKeyArn` so that operators can override values at deploy time
3. THE CloudFormation_Template SHALL include CloudFormation Conditions for optional resources (Neptune, OpenSearch, Rekognition) that evaluate based on the Parameters
4. THE CloudFormation_Template SHALL include CloudFormation Outputs for the API Gateway URL, S3 bucket name, Aurora cluster endpoint, and Neptune cluster endpoint (when created)

### Requirement 13: Deployment CLI Enhancement

**User Story:** As a platform operator, I want the deployment script to accept a config file, validate it, and orchestrate the full deployment lifecycle, so that I can deploy to any environment with a single command.

#### Acceptance Criteria

1. THE Deploy_CLI SHALL accept a `--config` command-line flag specifying the path to a Deployment_Config JSON file
2. WHEN `--config` is not provided, THE Deploy_CLI SHALL default to `infra/cdk/deployment-configs/default.json`
3. THE Deploy_CLI SHALL validate the Deployment_Config before running `cdk synth`
4. IF config validation fails, THEN THE Deploy_CLI SHALL print the validation errors and exit with a non-zero exit code without running synth
5. THE Deploy_CLI SHALL run post-deployment steps including Aurora database migrations and frontend S3 upload
6. WHEN deployment completes, THE Deploy_CLI SHALL print a summary containing the API Gateway URL, frontend URL, and next steps

### Requirement 14: GovCloud Deployment Profile

**User Story:** As a platform operator deploying to GovCloud, I want a pre-built configuration that enforces FedRAMP security controls, so that the platform meets compliance requirements without manual configuration.

#### Acceptance Criteria

1. THE Config_Loader SHALL provide a `govcloud-isengard.json` Deployment_Config with partition `aws-us-gov`, region `us-gov-west-1`, private subnets for all databases, KMS encryption enabled, VPC flow logs enabled, Neptune disabled, and OpenSearch mode `disabled`
2. THE Config_Loader SHALL provide a `govcloud-production.json` Deployment_Config with the same security controls as `govcloud-isengard.json` plus CloudTrail logging enabled
3. THE `govcloud-isengard.json` and `govcloud-production.json` configurations SHALL specify Bedrock model IDs that appear in the `fedramp_high` list of the FedRAMP_Model_Registry
4. THE `govcloud-isengard.json` and `govcloud-production.json` configurations SHALL set `encryption.enforce_tls` to `true`

### Requirement 15: Isengard Demo Deployment Profile

**User Story:** As a platform operator, I want a pre-built configuration for clean Isengard demo accounts, so that I can quickly stand up the full platform for colleague demonstrations.

#### Acceptance Criteria

1. THE Config_Loader SHALL provide an `isengard-demo.json` Deployment_Config with partition `aws`, `vpc.create_new` set to `true`, all services enabled (Neptune, OpenSearch Serverless, Rekognition), public subnets for databases, and no KMS encryption
2. THE `isengard-demo.json` configuration SHALL set `account` to `"CDK_DEFAULT_ACCOUNT"` and `region` to `"CDK_DEFAULT_REGION"` so that the values are resolved from environment variables at synth time

### Requirement 16: Lambda Runtime Graceful Degradation

**User Story:** As a developer, I want Lambda functions to detect which services are available at runtime, so that API responses degrade gracefully when Neptune or OpenSearch are not deployed.

#### Acceptance Criteria

1. THE CDK_Stack SHALL set Lambda environment variables `NEPTUNE_ENABLED`, `OPENSEARCH_ENABLED`, and `REKOGNITION_ENABLED` to `"true"` or `"false"` based on the Deployment_Config
2. WHEN `NEPTUNE_ENABLED` is `"false"`, THE Lambda functions SHALL skip all Neptune queries and return empty results for graph-dependent features without raising errors
3. WHEN `OPENSEARCH_ENABLED` is `"false"`, THE Lambda functions SHALL fall back to Aurora pgvector for all vector search operations

### Requirement 17: Security Group Dynamic Configuration

**User Story:** As a platform operator, I want security groups to be created dynamically based on the VPC CIDR, so that the stack works with any VPC configuration without hardcoded IP ranges.

#### Acceptance Criteria

1. THE CDK_Stack SHALL derive all security group ingress CIDR rules from the VPC CIDR block at synth time
2. THE CDK_Stack SHALL create security groups for Aurora, Neptune (when enabled), OpenSearch VPC endpoint (when enabled), and Lambda functions using the VPC CIDR block
3. WHEN `vpc.create_new` is `false`, THE CDK_Stack SHALL read the CIDR block from the imported VPC

### Requirement 18: Deployment Runbook

**User Story:** As a platform operator, I want comprehensive deployment documentation for each tier, so that I can follow step-by-step instructions to deploy the platform in any target environment.

#### Acceptance Criteria

1. THE Deployment_Runbook SHALL include prerequisites (AWS CLI version, CDK version, Python version, account access requirements) for all deployment tiers
2. THE Deployment_Runbook SHALL include step-by-step deployment instructions for Demo (Isengard), GovCloud Test (GovCloud Isengard), and Production (customer account) tiers
3. THE Deployment_Runbook SHALL include example Deployment_Config files for each tier with inline comments explaining each field
4. THE Deployment_Runbook SHALL include a troubleshooting section covering common deployment failures and their resolutions
5. THE Deployment_Runbook SHALL include a post-deployment verification checklist (API health check, Aurora connectivity, Neptune connectivity when enabled, S3 access, Step Functions execution test)

### Requirement 19: Backward Compatibility

**User Story:** As a developer, I want the current dev environment to continue working without changes, so that the multi-environment feature does not break existing workflows.

#### Acceptance Criteria

1. WHEN the `default.json` Deployment_Config is used, THE CDK_Stack SHALL produce a CloudFormation template functionally equivalent to the current hardcoded stack
2. THE Deploy_CLI SHALL maintain backward compatibility with the existing deployment workflow when no `--config` flag is provided
3. THE CDK_Stack SHALL preserve all existing CloudFormation logical IDs for resources in the default configuration to avoid unnecessary resource replacement during stack updates
