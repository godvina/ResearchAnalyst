# Requirements Document

## Introduction

The Customer Deployment Wizard enables the Research Analyst Platform to be packaged and deployed into a customer's own AWS landing zone via CloudFormation. It consolidates frontend configuration into a shared `config.js`, removes legacy Streamlit dependencies, adds a deployment wizard UI for environment configuration and module selection, generates parameterized CloudFormation templates sized by data volume tier, supports sample test runs to prove the system works before full deployment, and produces a downloadable deployment package (ZIP) containing all artifacts needed for a standalone installation.

## Glossary

- **Deployment_Wizard**: The `deployment-wizard.html` page that guides customers through environment configuration, module selection, data volume sizing, sample test runs, and deployment package generation.
- **Config_JS**: A shared JavaScript configuration file (`config.js`) imported by all HTML frontend pages, replacing per-file hardcoded API_URL constants.
- **Template_Generator**: The enhanced `deployment_generator.py` service that produces parameterized CloudFormation YAML templates from wizard inputs.
- **Deployment_Package**: A downloadable ZIP archive containing the CloudFormation template, frontend files with config.js, helper scripts, deployment guide, and cost estimate.
- **Sample_Test_Runner**: The component that accepts 1-5 uploaded sample documents, runs them through the ingestion pipeline, and displays extraction results.
- **Cost_Calculator**: The component that computes monthly and annual cost breakdowns by AWS service based on data volume tier and module selection, using pricing data from `config/aws_pricing.json`.
- **Data_Volume_Tier**: One of four infrastructure sizing categories (Small, Medium, Large, Enterprise) that determines Neptune instance size, Aurora capacity, and OpenSearch OCU count.
- **Module**: A deployable functional unit of the platform — one of Investigator, Prosecutor, Network Discovery, or Document Assembly.
- **Frontend_Pages**: The set of 9 static HTML files (investigator.html, prosecutor.html, network_discovery.html, document_assembly.html, chatbot.html, pipeline-config.html, wizard.html, portfolio.html, workbench.html) served from S3/CloudFront.
- **Streamlit_Remnants**: Legacy Streamlit files (app.py, case_dashboard.py, validation.py, __init__.py comment, .streamlit/ directory) that are no longer used since the frontend migrated to static HTML.

## Requirements

### Requirement 1: Shared Frontend Configuration File

**User Story:** As a platform deployer, I want all frontend pages to read configuration from a single shared file, so that I can change the API endpoint and tenant settings in one place instead of editing 9 HTML files.

#### Acceptance Criteria

1. THE Config_JS SHALL export the following properties: API_URL (string, API Gateway endpoint), TENANT_NAME (string, customer name for branding), MODULES_ENABLED (array of strings, active module identifiers), and REGION (string, AWS region).
2. WHEN a Frontend_Page loads, THE Frontend_Page SHALL import Config_JS and use the API_URL property for all API requests instead of a hardcoded constant.
3. THE Config_JS SHALL provide a default API_URL value of `'__API_URL__'` as a placeholder that deployment tooling replaces during package generation.
4. WHEN Config_JS defines MODULES_ENABLED, THE Frontend_Pages SHALL show navigation links only for enabled Modules.
5. WHEN Config_JS defines TENANT_NAME, THE Frontend_Pages SHALL display the tenant name in the page header area.

### Requirement 2: Remove Streamlit Dependency

**User Story:** As a platform deployer, I want all Streamlit code and configuration removed, so that the frontend is purely static HTML/JS with no Python server dependency.

#### Acceptance Criteria

1. THE Platform SHALL contain zero Python files that import the `streamlit` library under `src/frontend/`.
2. THE Platform SHALL not include a `.streamlit/` configuration directory.
3. THE `src/frontend/__init__.py` SHALL not reference Streamlit in comments or code.
4. WHEN the deployment package is generated, THE Deployment_Package SHALL not include any Streamlit-related files.

### Requirement 3: Deployment Wizard UI — Environment Configuration

**User Story:** As a customer deployer, I want to specify my AWS environment details in a guided wizard, so that the deployment is configured for my specific AWS landing zone.

#### Acceptance Criteria

1. THE Deployment_Wizard SHALL present input fields for: AWS region (dropdown), AWS account ID (text, 12-digit), VPC CIDR (text, CIDR notation), KMS key ARN (text, ARN format), and S3 bucket name for the data lake (text).
2. WHEN the deployer selects an AWS region, THE Deployment_Wizard SHALL include us-east-1, us-west-2, us-gov-west-1, and us-gov-east-1 as options.
3. IF the deployer enters an AWS account ID that is not exactly 12 digits, THEN THE Deployment_Wizard SHALL display a validation error and prevent progression to the next step.
4. IF the deployer enters a VPC CIDR that does not match CIDR notation (e.g., `10.0.0.0/16`), THEN THE Deployment_Wizard SHALL display a validation error.
5. IF the deployer enters a KMS key ARN that does not start with `arn:aws:kms:` or `arn:aws-us-gov:kms:`, THEN THE Deployment_Wizard SHALL display a validation error.

### Requirement 4: Deployment Wizard UI — Module Selection

**User Story:** As a customer deployer, I want to choose which platform modules to deploy, so that I only pay for and install the capabilities my team needs.

#### Acceptance Criteria

1. THE Deployment_Wizard SHALL present checkboxes for four Modules: Investigator, Prosecutor, Network Discovery, and Document Assembly.
2. THE Deployment_Wizard SHALL require at least one Module to be selected before allowing progression to the next step.
3. WHEN the deployer selects a set of Modules, THE Template_Generator SHALL include only the Lambda functions, API routes, and frontend pages for the selected Modules in the generated CloudFormation template.
4. THE Deployment_Wizard SHALL pre-select the Investigator Module by default because it is the core module.

### Requirement 5: Deployment Wizard UI — Data Volume Sizing

**User Story:** As a customer deployer, I want to specify my expected data volume, so that the infrastructure is sized appropriately and I get an accurate cost estimate.

#### Acceptance Criteria

1. THE Deployment_Wizard SHALL present input fields for: expected document count (number), average document size in MB (number), and estimated entity count (number).
2. WHEN the deployer enters document count and average size, THE Deployment_Wizard SHALL compute and display the estimated total data volume.
3. WHEN the deployer enters data volume inputs, THE Deployment_Wizard SHALL automatically determine the Data_Volume_Tier (Small, Medium, Large, or Enterprise) and display the selected tier.
4. THE Deployment_Wizard SHALL display the infrastructure sizing for the selected Data_Volume_Tier: Neptune instance type, Aurora ACU range, and OpenSearch OCU count.

### Requirement 6: Data Volume Tier Definitions

**User Story:** As a platform architect, I want data volume tiers to map to specific infrastructure sizes, so that the platform performs well at each scale.

#### Acceptance Criteria

1. WHEN the document count is less than 100,000, THE Template_Generator SHALL select the Small tier with Neptune Serverless (1-4 NCU), Aurora Serverless v2 (0.5-4 ACU), and 2 OpenSearch OCUs.
2. WHEN the document count is between 100,000 and 1,000,000, THE Template_Generator SHALL select the Medium tier with Neptune r6g.xlarge, Aurora Serverless v2 (1-8 ACU), and 4 OpenSearch OCUs.
3. WHEN the document count is between 1,000,000 and 10,000,000, THE Template_Generator SHALL select the Large tier with Neptune r6g.2xlarge, Aurora Serverless v2 (2-16 ACU), 8 OpenSearch OCUs, and parallel Step Functions orchestration.
4. WHEN the document count is 10,000,000 or more, THE Template_Generator SHALL select the Enterprise tier with Neptune r6g.4xlarge, Aurora Serverless v2 (4-32 ACU), 16 or more OpenSearch OCUs, S3 batch operations, and parallel ingestion via SQS plus Lambda fleet.

### Requirement 7: Cost Estimation

**User Story:** As a customer deployer, I want to see a detailed cost breakdown before committing to deployment, so that I can budget appropriately and get approval.

#### Acceptance Criteria

1. WHEN the deployer completes data volume sizing, THE Cost_Calculator SHALL compute and display a monthly cost breakdown by AWS service (Aurora, Neptune, OpenSearch, S3, Lambda, API Gateway, Bedrock, CloudFront).
2. THE Cost_Calculator SHALL compute and display an annual cost estimate equal to the monthly cost multiplied by 12.
3. THE Cost_Calculator SHALL use pricing data from `config/aws_pricing.json` for all calculations.
4. WHEN the deployer changes the Data_Volume_Tier or Module selection, THE Cost_Calculator SHALL recalculate the cost estimate within 1 second.
5. THE Cost_Calculator SHALL display one-time ingestion processing costs separately from recurring monthly infrastructure costs.

### Requirement 8: Sample Test Run

**User Story:** As a customer deployer, I want to upload a few sample documents and see them processed through the pipeline, so that I can verify the system works before committing to a full deployment.

#### Acceptance Criteria

1. THE Sample_Test_Runner SHALL accept between 1 and 5 document uploads (PDF, DOCX, TXT formats).
2. WHEN the deployer uploads sample documents, THE Sample_Test_Runner SHALL process each document through the ingestion pipeline stages: parse, extract entities, generate embeddings, and load to graph.
3. WHEN processing completes, THE Sample_Test_Runner SHALL display for each document: entities found (with types and confidence scores), relationships discovered, and document classification.
4. IF a sample document fails to process, THEN THE Sample_Test_Runner SHALL display the failure reason and the pipeline stage where the failure occurred.
5. THE Sample_Test_Runner SHALL display a summary showing total entities extracted, total relationships found, and entity type distribution across all sample documents.

### Requirement 9: CloudFormation Template Generation

**User Story:** As a customer deployer, I want a parameterized CloudFormation template generated from my wizard inputs, so that I can deploy the full platform stack into my AWS account with a single stack creation.

#### Acceptance Criteria

1. WHEN the deployer clicks "Generate Deployment Package", THE Template_Generator SHALL produce a CloudFormation YAML template that includes resources for: Aurora PostgreSQL Serverless v2, Neptune (sized by Data_Volume_Tier), OpenSearch Serverless (OCUs based on Data_Volume_Tier), S3 data lake bucket, Lambda functions for all selected Module handlers, API Gateway REST API, Step Functions ingestion pipeline, CloudFront distribution with S3 origin for frontend hosting, IAM roles and policies, and VPC configuration.
2. THE Template_Generator SHALL parameterize the CloudFormation template with input parameters for: EnvironmentName, AdminEmail, VpcCidr, DeploymentBucketName, LambdaCodeKey, KmsKeyArn, and DataVolumeTier (Small/Medium/Large/Enterprise).
3. WHEN the deployer specifies a KMS key ARN, THE Template_Generator SHALL configure Aurora, Neptune, S3, and OpenSearch resources to use that KMS key for encryption at rest.
4. WHEN the deployer selects a GovCloud region (us-gov-west-1 or us-gov-east-1), THE Template_Generator SHALL use the `aws-us-gov` partition in all ARN references.
5. THE Template_Generator SHALL include CloudFormation Outputs for: frontend URL, API Gateway URL, S3 data bucket name, Aurora endpoint, and Neptune endpoint.

### Requirement 10: Deployment Package Generation

**User Story:** As a customer deployer, I want to download a complete deployment package as a ZIP file, so that I have everything needed to deploy the platform into my AWS account.

#### Acceptance Criteria

1. WHEN the deployer clicks "Download Deployment Package", THE Deployment_Wizard SHALL generate a ZIP file containing: `deploy.yaml` (parameterized CloudFormation template), `frontend/` directory (all selected Module HTML files plus config.js with API_URL placeholder), `scripts/` directory (deployment helper scripts for DB migration, statute seeding, and Lambda deployment), `DEPLOYMENT_GUIDE.md` (auto-generated step-by-step instructions specific to the deployer's configuration), and `COST_ESTIMATE.md` (detailed cost breakdown).
2. THE `DEPLOYMENT_GUIDE.md` SHALL include the deployer's selected AWS region, Data_Volume_Tier, selected Modules, and specific CLI commands with the deployer's S3 bucket name and stack name pre-filled.
3. THE `config.js` in the deployment package SHALL contain `API_URL: '__API_URL__'` as a placeholder, with the DEPLOYMENT_GUIDE.md instructing the deployer to replace it with the API Gateway URL from CloudFormation stack outputs.
4. THE `frontend/` directory in the Deployment_Package SHALL include only the HTML files for the selected Modules plus shared pages (chatbot.html, pipeline-config.html, portfolio.html, workbench.html).
5. THE `scripts/` directory SHALL include: `migrate_db.sh` (runs Aurora schema migrations), `seed_statutes.sh` (seeds the statute reference data), and `deploy_lambdas.sh` (packages and uploads Lambda code to S3).

### Requirement 11: Deployment Wizard Navigation and Validation

**User Story:** As a customer deployer, I want the wizard to guide me through each step with clear validation, so that I produce a correct deployment package without errors.

#### Acceptance Criteria

1. THE Deployment_Wizard SHALL present steps in this order: Environment Configuration, Module Selection, Data Volume Sizing, Cost Estimate Review, Sample Test Run (optional), and Generate Deployment Package.
2. THE Deployment_Wizard SHALL display a progress indicator showing the current step and total steps.
3. WHEN the deployer clicks "Next" on a step, THE Deployment_Wizard SHALL validate all required fields on the current step before advancing.
4. THE Deployment_Wizard SHALL allow the deployer to navigate back to previous steps and modify inputs without losing data entered in subsequent steps.
5. THE Deployment_Wizard SHALL allow the deployer to skip the Sample Test Run step and proceed directly to deployment package generation.
