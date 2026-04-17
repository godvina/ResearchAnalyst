"""Lambda construct — all API and ingestion Lambda functions with IAM.

Requirements: 4.3, 4.4, 5.3, 5.4, 6.1, 6.2, 6.3, 8.1, 8.2, 9.1, 9.2, 9.3, 9.4, 16.1
"""

import os

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_kms as kms,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_sqs as sqs,
)
from constructs import Construct

from .aurora_construct import AuroraConstruct
from .neptune_construct import NeptuneConstruct
from .opensearch_construct import OpenSearchConstruct

# Path to project root (infra/cdk/cdk_constructs -> infra/cdk -> infra -> project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_SUBNET_TYPE_MAP = {
    "PUBLIC": ec2.SubnetType.PUBLIC,
    "PRIVATE_WITH_EGRESS": ec2.SubnetType.PRIVATE_WITH_EGRESS,
}


def build_lambda_env(
    config: dict,
    aurora: AuroraConstruct,
    neptune: NeptuneConstruct,
    opensearch: OpenSearchConstruct,
    data_bucket: s3.Bucket,
) -> dict:
    """Build the shared Lambda environment variable dict from config and construct outputs."""
    bedrock_cfg = config.get("bedrock", {})
    neptune_cfg = config.get("neptune", {})
    os_cfg = config.get("opensearch", {})
    features_cfg = config.get("features", {})

    env = {
        "AURORA_PROXY_ENDPOINT": aurora.proxy.endpoint,
        "AURORA_SECRET_ARN": aurora.secret.secret_arn,
        "AURORA_DB_NAME": "research_analyst",
        "S3_DATA_BUCKET": data_bucket.bucket_name,
        "S3_BUCKET_NAME": data_bucket.bucket_name,
        "NEPTUNE_PORT": "8182",
        "BULK_LOAD_THRESHOLD": "20",
        "ACCESS_CONTROL_ENABLED": "false",
        # Bedrock model IDs from config
        "BEDROCK_LLM_MODEL_ID": bedrock_cfg.get("llm_model_id", ""),
        "BEDROCK_EMBEDDING_MODEL_ID": bedrock_cfg.get("embedding_model_id", ""),
        # Feature flags
        "NEPTUNE_ENABLED": "true" if neptune_cfg.get("enabled", False) else "false",
        "OPENSEARCH_ENABLED": "true" if os_cfg.get("mode", "disabled") == "serverless" else "false",
        "REKOGNITION_ENABLED": "true" if features_cfg.get("rekognition", True) else "false",
    }

    # Neptune endpoint — empty when disabled
    if neptune.enabled and neptune.cluster:
        env["NEPTUNE_ENDPOINT"] = neptune.cluster.cluster_endpoint.hostname
    else:
        env["NEPTUNE_ENDPOINT"] = ""

    # OpenSearch endpoint — empty when disabled
    if opensearch.enabled and opensearch.collection:
        env["OPENSEARCH_ENDPOINT"] = opensearch.endpoint
        env["OPENSEARCH_COLLECTION_ID"] = opensearch.collection_id
    else:
        env["OPENSEARCH_ENDPOINT"] = ""
        env["OPENSEARCH_COLLECTION_ID"] = ""

    return env


class LambdaConstruct(Construct):
    """All Lambda functions with configurable env vars, feature flags, and partition-aware IAM."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        config: dict,
        vpc: ec2.IVpc,
        aurora: AuroraConstruct,
        neptune: NeptuneConstruct,
        opensearch: OpenSearchConstruct,
        data_bucket: s3.Bucket,
    ) -> None:
        super().__init__(scope, id)

        self._config = config
        self._vpc = vpc
        self._aurora = aurora
        self._neptune = neptune
        self._opensearch = opensearch
        self._data_bucket = data_bucket

        features_cfg = config.get("features", {})
        pipeline_only = features_cfg.get("pipeline_only", False)
        rekognition_enabled = features_cfg.get("rekognition", True)

        # Determine subnet type for Lambda placement
        aurora_subnet = config.get("aurora", {}).get("subnet_type", "PUBLIC")
        self._subnet_type = _SUBNET_TYPE_MAP.get(aurora_subnet, ec2.SubnetType.PUBLIC)
        self._allow_public = self._subnet_type == ec2.SubnetType.PUBLIC

        # Build shared env vars
        lambda_env = build_lambda_env(config, aurora, neptune, opensearch, data_bucket)

        # --- Shared Dead Letter Queue (Req 3) ---
        encryption_cfg = config.get("encryption", {})
        kms_key_arn = encryption_cfg.get("kms_key_arn")
        if kms_key_arn:
            imported_key = kms.Key.from_key_arn(self, "DLQKmsKey", kms_key_arn)
            dlq = sqs.Queue(self, "LambdaDLQ",
                queue_name="research-analyst-dlq",
                retention_period=Duration.days(14),
                encryption=sqs.QueueEncryption.KMS,
                encryption_master_key=imported_key,
            )
        else:
            dlq = sqs.Queue(self, "LambdaDLQ",
                queue_name="research-analyst-dlq",
                retention_period=Duration.days(14),
                encryption=sqs.QueueEncryption.SQS_MANAGED,
            )

        # --- Ingestion Lambdas (always created) ---
        self._ingestion_lambdas = self._create_ingestion_lambdas(
            lambda_env, rekognition_enabled, dead_letter_queue=dlq,
        )

        # --- API Lambdas (skipped when pipeline_only) ---
        if pipeline_only:
            self._api_lambdas: dict[str, _lambda.Function] = {}
        else:
            self._api_lambdas = self._create_api_lambdas(lambda_env, dead_letter_queue=dlq)

        # --- Grant permissions ---
        all_lambdas = {**self._api_lambdas, **self._ingestion_lambdas}
        self._grant_permissions(all_lambdas, rekognition_enabled)

    # ------------------------------------------------------------------
    # Helper: create a Lambda function
    # ------------------------------------------------------------------
    def _make_lambda(
        self, fn_id: str, handler: str, env: dict,
        timeout_seconds: int = 60, memory_mb: int = 256,
        dead_letter_queue: sqs.IQueue | None = None,
    ) -> _lambda.Function:
        return _lambda.Function(
            self, fn_id,
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler=handler,
            code=_lambda.Code.from_asset(os.path.join(_PROJECT_ROOT, "src")),
            vpc=self._vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=self._subnet_type),
            allow_public_subnet=self._allow_public,
            environment=env,
            timeout=Duration.seconds(timeout_seconds),
            memory_size=memory_mb,
            tracing=_lambda.Tracing.ACTIVE,
            dead_letter_queue=dead_letter_queue,
        )

    # ------------------------------------------------------------------
    # API Lambdas
    # ------------------------------------------------------------------
    def _create_api_lambdas(
        self, env: dict, dead_letter_queue: sqs.IQueue | None = None,
    ) -> dict[str, _lambda.Function]:
        return {
            "case_files": self._make_lambda(
                "CaseFilesLambda",
                "lambdas.api.case_files.dispatch_handler",
                env, timeout_seconds=900, memory_mb=512,
                dead_letter_queue=dead_letter_queue,
            ),
        }

    # ------------------------------------------------------------------
    # Ingestion Lambdas
    # ------------------------------------------------------------------
    def _create_ingestion_lambdas(
        self, env: dict, rekognition_enabled: bool,
        dead_letter_queue: sqs.IQueue | None = None,
    ) -> dict[str, _lambda.Function]:
        fns: dict[str, _lambda.Function] = {
            "upload": self._make_lambda(
                "IngestionUploadLambda",
                "lambdas.ingestion.upload_handler.handler",
                env, timeout_seconds=300, memory_mb=512,
                dead_letter_queue=dead_letter_queue,
            ),
            "parse": self._make_lambda(
                "IngestionParseLambda",
                "lambdas.ingestion.parse_handler.handler",
                env, timeout_seconds=300, memory_mb=512,
                dead_letter_queue=dead_letter_queue,
            ),
            "extract": self._make_lambda(
                "IngestionExtractLambda",
                "lambdas.ingestion.extract_handler.handler",
                env, timeout_seconds=300, memory_mb=512,
                dead_letter_queue=dead_letter_queue,
            ),
            "embed": self._make_lambda(
                "IngestionEmbedLambda",
                "lambdas.ingestion.embed_handler.handler",
                env, timeout_seconds=300, memory_mb=512,
                dead_letter_queue=dead_letter_queue,
            ),
            "store_artifact": self._make_lambda(
                "IngestionStoreArtifactLambda",
                "lambdas.ingestion.store_artifact_handler.handler",
                env, timeout_seconds=300, memory_mb=512,
                dead_letter_queue=dead_letter_queue,
            ),
            "graph_load": self._make_lambda(
                "IngestionGraphLoadLambda",
                "lambdas.ingestion.graph_load_handler.handler",
                env, timeout_seconds=900, memory_mb=1024,
                dead_letter_queue=dead_letter_queue,
            ),
            "update_status": self._make_lambda(
                "IngestionUpdateStatusLambda",
                "lambdas.ingestion.update_status_handler.handler",
                env, timeout_seconds=300, memory_mb=512,
                dead_letter_queue=dead_letter_queue,
            ),
            "resolve_config": self._make_lambda(
                "IngestionResolveConfigLambda",
                "lambdas.ingestion.resolve_config_handler.handler",
                env, timeout_seconds=300, memory_mb=512,
                dead_letter_queue=dead_letter_queue,
            ),
            "entity_resolution": self._make_lambda(
                "EntityResolutionLambda",
                "lambdas.ingestion.entity_resolution_handler.handler",
                env, timeout_seconds=900, memory_mb=1024,
                dead_letter_queue=dead_letter_queue,
            ),
            "image_description": self._make_lambda(
                "IngestionImageDescriptionLambda",
                "lambdas.ingestion.image_description_handler.handler",
                env, timeout_seconds=900, memory_mb=1024,
                dead_letter_queue=dead_letter_queue,
            ),
        }

        # Rekognition-related lambdas — only when enabled
        if rekognition_enabled:
            fns["rekognition"] = self._make_lambda(
                "IngestionRekognitionLambda",
                "lambdas.ingestion.rekognition_handler.handler",
                env, timeout_seconds=900, memory_mb=1024,
                dead_letter_queue=dead_letter_queue,
            )
            fns["face_crop"] = self._make_lambda(
                "IngestionFaceCropLambda",
                "lambdas.ingestion.face_crop_handler.handler",
                env, timeout_seconds=300, memory_mb=512,
                dead_letter_queue=dead_letter_queue,
            )

        return fns

    # ------------------------------------------------------------------
    # IAM permissions — partition-aware
    # ------------------------------------------------------------------
    def _grant_permissions(
        self, all_lambdas: dict[str, _lambda.Function], rekognition_enabled: bool,
    ) -> None:
        aurora_secret = self._aurora.secret
        data_bucket = self._data_bucket

        for name, fn in all_lambdas.items():
            # All Lambdas can read the Aurora secret
            aurora_secret.grant_read(fn)

            # RDS Proxy connect (IAM auth) — partition-aware
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=["rds-db:connect"],
                resources=[
                    cdk.Fn.sub(
                        "arn:${AWS::Partition}:rds-db:${AWS::Region}:${AWS::AccountId}:dbuser:*/*"
                    ),
                ],
            ))

        # S3 permissions — scoped by function role
        for name in ("upload", "store_artifact", "graph_load"):
            if name in all_lambdas:
                data_bucket.grant_read_write(all_lambdas[name])
        for name in ("parse", "extract", "embed"):
            if name in all_lambdas:
                data_bucket.grant_read(all_lambdas[name])
        if "parse" in all_lambdas:
            data_bucket.grant_write(all_lambdas["parse"], "cases/*/extracted-images/*")
        if "case_files" in all_lambdas:
            data_bucket.grant_read_write(all_lambdas["case_files"])
        if "rekognition" in all_lambdas:
            data_bucket.grant_read_write(all_lambdas["rekognition"])

        # Neptune permissions — only when enabled
        if self._neptune.enabled:
            neptune_policy = iam.PolicyStatement(
                actions=[
                    "neptune-db:ReadDataViaQuery",
                    "neptune-db:WriteDataViaQuery",
                    "neptune-db:GetQueryStatus",
                    "neptune-db:CancelQuery",
                ],
                resources=[
                    cdk.Fn.sub(
                        "arn:${AWS::Partition}:neptune-db:${AWS::Region}:${AWS::AccountId}:*/*"
                    ),
                ],
            )
            for fn in all_lambdas.values():
                fn.add_to_role_policy(neptune_policy)

            if "graph_load" in all_lambdas:
                all_lambdas["graph_load"].add_to_role_policy(iam.PolicyStatement(
                    actions=["neptune-db:StartLoaderJob", "neptune-db:GetLoaderJobStatus"],
                    resources=["*"],
                ))

        # Bedrock — entity extraction + embeddings (partition-aware, scoped when model IDs present)
        bedrock_cfg = self._config.get("bedrock", {})
        llm_model_id = bedrock_cfg.get("llm_model_id")
        embed_model_id = bedrock_cfg.get("embedding_model_id")

        if llm_model_id and embed_model_id:
            # Scoped Bedrock IAM — least-privilege per function (Req 7)
            llm_arn = cdk.Fn.sub(
                f"arn:${{AWS::Partition}}:bedrock:${{AWS::Region}}::foundation-model/{llm_model_id}"
            )
            embed_arn = cdk.Fn.sub(
                f"arn:${{AWS::Partition}}:bedrock:${{AWS::Region}}::foundation-model/{embed_model_id}"
            )

            # InvokeModel on LLM ARN → extract, case_files
            llm_invoke_policy = iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[llm_arn],
            )
            for name in ("extract", "case_files"):
                if name in all_lambdas:
                    all_lambdas[name].add_to_role_policy(llm_invoke_policy)

            # InvokeModel on embedding ARN → embed, case_files
            embed_invoke_policy = iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[embed_arn],
            )
            for name in ("embed", "case_files"):
                if name in all_lambdas:
                    all_lambdas[name].add_to_role_policy(embed_invoke_policy)

            # InvokeModelWithResponseStream on LLM ARN → case_files
            if "case_files" in all_lambdas:
                all_lambdas["case_files"].add_to_role_policy(iam.PolicyStatement(
                    actions=["bedrock:InvokeModelWithResponseStream"],
                    resources=[llm_arn],
                ))
        else:
            # Fallback to existing wildcard policy when model IDs absent
            bedrock_policy = iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    cdk.Fn.sub(
                        "arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/*"
                    ),
                ],
            )
            for name in ("extract", "embed", "case_files"):
                if name in all_lambdas:
                    all_lambdas[name].add_to_role_policy(bedrock_policy)

        # Bedrock Knowledge Base
        bedrock_kb_policy = iam.PolicyStatement(
            actions=["bedrock:Retrieve", "bedrock:RetrieveAndGenerate"],
            resources=[
                cdk.Fn.sub(
                    "arn:${AWS::Partition}:bedrock:${AWS::Region}:${AWS::AccountId}:knowledge-base/*"
                ),
            ],
        )
        if "case_files" in all_lambdas:
            all_lambdas["case_files"].add_to_role_policy(bedrock_kb_policy)

        # Bedrock Agent
        bedrock_agent_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeAgent"],
            resources=[
                cdk.Fn.sub(
                    "arn:${AWS::Partition}:bedrock:${AWS::Region}:${AWS::AccountId}:agent/*"
                ),
            ],
        )
        if "case_files" in all_lambdas:
            all_lambdas["case_files"].add_to_role_policy(bedrock_agent_policy)

        # Rekognition permissions — only when enabled
        if rekognition_enabled and "rekognition" in all_lambdas:
            all_lambdas["rekognition"].add_to_role_policy(iam.PolicyStatement(
                actions=[
                    "rekognition:DetectFaces",
                    "rekognition:DetectLabels",
                    "rekognition:DetectText",
                    "rekognition:SearchFacesByImage",
                    "rekognition:StartLabelDetection",
                    "rekognition:StartFaceDetection",
                    "rekognition:GetLabelDetection",
                    "rekognition:GetFaceDetection",
                ],
                resources=["*"],
            ))

        # Textract + Step Functions + self-invoke for case_files
        if "case_files" in all_lambdas:
            cf_fn = all_lambdas["case_files"]
            cf_fn.add_to_role_policy(iam.PolicyStatement(
                actions=[
                    "textract:DetectDocumentText",
                    "textract:StartDocumentTextDetection",
                    "textract:GetDocumentTextDetection",
                ],
                resources=["*"],
            ))
            cf_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["states:DescribeExecution", "states:ListExecutions"],
                resources=["*"],
            ))
            cf_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[cf_fn.function_arn],
            ))
            cf_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket", "s3:HeadObject"],
                resources=[
                    cdk.Fn.sub("arn:${AWS::Partition}:s3:::doj-cases-*"),
                    cdk.Fn.sub("arn:${AWS::Partition}:s3:::doj-cases-*/*"),
                ],
            ))

        # OpenSearch Serverless permissions — only when enabled
        if self._opensearch.enabled and self._opensearch.collection:
            for fn in all_lambdas.values():
                fn.add_to_role_policy(iam.PolicyStatement(
                    actions=["aoss:APIAccessAll"],
                    resources=[
                        cdk.Fn.join("", [
                            "arn:", cdk.Aws.PARTITION, ":aoss:",
                            cdk.Aws.REGION, ":", cdk.Aws.ACCOUNT_ID,
                            ":collection/", self._opensearch.collection_id,
                        ]),
                    ],
                ))
                # Add Lambda SG to AOSS VPC endpoint SG inbound
                if self._opensearch.vpce_sg:
                    self._opensearch.vpce_sg.add_ingress_rule(
                        fn.connections.security_groups[0],
                        ec2.Port.tcp(443),
                        f"Allow HTTPS from {fn.node.id} to AOSS VPC endpoint",
                    )

    @property
    def api_lambdas(self) -> dict[str, _lambda.Function]:
        return self._api_lambdas

    @property
    def ingestion_lambdas(self) -> dict[str, _lambda.Function]:
        return self._ingestion_lambdas
