"""Config-driven Research Analyst Platform stack using modular constructs.

Requirements: 10.1, 10.2, 10.3, 11.1, 11.2, 11.3, 11.4, 12.1, 12.2, 12.3, 12.4, 19.1, 19.3
"""

import aws_cdk as cdk
from aws_cdk import aws_cloudtrail as cloudtrail, aws_iam as iam, aws_kms as kms
from constructs import Construct

from cdk_constructs import (
    SecurityConstruct,
    VpcConstruct,
    AuroraConstruct,
    NeptuneConstruct,
    OpenSearchConstruct,
    LambdaConstruct,
    PipelineConstruct,
    ApiConstruct,
    ObservabilityConstruct,
)


class ResearchAnalystStack(cdk.Stack):
    """Config-driven Research Analyst Platform stack."""

    def __init__(self, scope: Construct, construct_id: str, *, config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Tags ---
        for key, value in config.get("tags", {}).items():
            cdk.Tags.of(self).add(key, value)
        cdk.Tags.of(self).add("Environment", config["environment_name"])

        # --- CloudFormation Parameters ---
        cdk.CfnParameter(self, "EnvironmentName", default=config["environment_name"],
                          description="Deployment environment name")
        cdk.CfnParameter(self, "AWSRegion", default=config["region"],
                          description="AWS region for deployment")

        # --- 1. VPC ---
        vpc_construct = VpcConstruct(self, "Vpc", config=config)
        vpc = vpc_construct.vpc

        # --- 2. Security (S3 bucket) ---
        security = SecurityConstruct(self, "Security", config=config)

        # --- 3. Aurora ---
        aurora = AuroraConstruct(self, "Aurora", config=config, vpc=vpc)

        # --- 4. Neptune (conditional) ---
        neptune = NeptuneConstruct(self, "Neptune", config=config, vpc=vpc)

        # --- 5. OpenSearch (conditional) ---
        opensearch = OpenSearchConstruct(self, "OpenSearch", config=config, vpc=vpc)

        # --- 6. Lambda functions ---
        lambdas = LambdaConstruct(
            self, "Lambda",
            config=config,
            vpc=vpc,
            aurora=aurora,
            neptune=neptune,
            opensearch=opensearch,
            data_bucket=security.data_bucket,
        )

        # --- 7. Step Functions pipeline ---
        pipeline = PipelineConstruct(
            self, "Pipeline",
            config=config,
            ingestion_lambdas=lambdas.ingestion_lambdas,
        )

        # Wire: API Lambda needs State Machine ARN
        if "case_files" in lambdas.api_lambdas:
            lambdas.api_lambdas["case_files"].add_environment(
                "STATE_MACHINE_ARN", pipeline.state_machine.state_machine_arn,
            )
            pipeline.state_machine.grant_start_execution(lambdas.api_lambdas["case_files"])

        # --- 7b. Observability (CloudWatch alarms) ---
        ObservabilityConstruct(
            self, "Observability",
            config=config,
            lambda_functions={**lambdas.api_lambdas, **lambdas.ingestion_lambdas},
            state_machine=pipeline.state_machine,
        )

        # --- 8. API Gateway (conditional) ---
        api = ApiConstruct(
            self, "Api",
            config=config,
            api_lambdas=lambdas.api_lambdas,
        )

        # --- Bedrock KB Role ---
        self._create_bedrock_kb_role(security.data_bucket, aurora.cluster, config)

        # --- Conditional CloudTrail (Req 9) ---
        logging_cfg = config.get("logging", {})
        if logging_cfg.get("cloudtrail", False):
            encryption_cfg = config.get("encryption", {})
            trail_kms_key_arn = encryption_cfg.get("kms_key_arn")
            trail_encryption_key = (
                kms.Key.from_key_arn(self, "TrailKmsKey", trail_kms_key_arn)
                if trail_kms_key_arn
                else None
            )
            cloudtrail.Trail(
                self, "AuditTrail",
                bucket=security.data_bucket,
                s3_key_prefix="cloudtrail",
                is_multi_region_trail=False,
                encryption_key=trail_encryption_key,
            )

        # --- CloudFormation Outputs ---
        cdk.CfnOutput(self, "AuroraClusterEndpoint",
                       value=aurora.cluster.cluster_endpoint.hostname)
        cdk.CfnOutput(self, "RdsProxyEndpoint",
                       value=aurora.proxy.endpoint)
        cdk.CfnOutput(self, "DataBucketName",
                       value=security.data_bucket.bucket_name)

        if neptune.enabled and neptune.cluster:
            cdk.CfnOutput(self, "NeptuneClusterEndpoint",
                           value=neptune.cluster.cluster_endpoint.hostname)

        if opensearch.enabled and opensearch.collection:
            cdk.CfnOutput(self, "OpenSearchEndpoint",
                           value=opensearch.endpoint)
            cdk.CfnOutput(self, "OpenSearchCollectionId",
                           value=opensearch.collection_id)

        if api.api:
            cdk.CfnOutput(self, "ApiGatewayUrl",
                           value=api.api.url)

    def _create_bedrock_kb_role(self, data_bucket, aurora_cluster, config):
        """Create Bedrock Knowledge Base IAM role."""
        role = iam.Role(
            self, "BedrockKBRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Bedrock Knowledge Base to access Aurora pgvector and S3",
        )
        data_bucket.grant_read(role)
        role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                cdk.Fn.sub(
                    "arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/"
                    + config.get("bedrock", {}).get("embedding_model_id", "amazon.titan-embed-text-v2:0")
                ),
            ],
        ))
        role.add_to_policy(iam.PolicyStatement(
            actions=["rds-data:ExecuteStatement", "rds-data:BatchExecuteStatement"],
            resources=[aurora_cluster.cluster_arn],
        ))
        return role
