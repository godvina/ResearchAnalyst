"""Pipeline construct — Step Functions ingestion state machine.

Requirements: 9.3
"""

import os

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
)
from constructs import Construct

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class PipelineConstruct(Construct):
    """Step Functions state machine from ASL definition with Lambda ARN substitutions."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        config: dict,
        ingestion_lambdas: dict[str, _lambda.Function],
    ) -> None:
        super().__init__(scope, id)

        asl_path = os.path.join(
            _PROJECT_ROOT, "infra", "step_functions", "ingestion_pipeline.json",
        )
        with open(asl_path) as f:
            asl_body = f.read()

        # Build substitution map — only include lambdas that exist
        substitutions: dict[str, str] = {}
        lambda_map = {
            "upload": "IngestionUploadLambdaArn",
            "parse": "IngestionParseLambdaArn",
            "extract": "IngestionExtractLambdaArn",
            "embed": "IngestionEmbedLambdaArn",
            "store_artifact": "IngestionStoreArtifactLambdaArn",
            "graph_load": "IngestionGraphLoadLambdaArn",
            "update_status": "IngestionUpdateStatusLambdaArn",
            "resolve_config": "IngestionResolveConfigLambdaArn",
            "rekognition": "IngestionRekognitionLambdaArn",
        }
        # Additional ASL placeholder aliases
        alias_map = {
            "resolve_config": "ResolveConfigLambdaArn",
            "extract": "ClassificationLambdaArn",
            "rekognition": "RekognitionLambdaArn",
            "face_crop": "FaceCropLambdaArn",
            "image_description": "ImageDescriptionLambdaArn",
        }

        for key, placeholder in lambda_map.items():
            if key in ingestion_lambdas:
                substitutions[placeholder] = ingestion_lambdas[key].function_arn

        for key, placeholder in alias_map.items():
            if key in ingestion_lambdas:
                substitutions[placeholder] = ingestion_lambdas[key].function_arn

        self._state_machine = sfn.StateMachine(
            self, "IngestionPipeline",
            state_machine_name="research-analyst-ingestion",
            definition_body=sfn.DefinitionBody.from_string(asl_body),
            definition_substitutions=substitutions,
            timeout=Duration.hours(24),
        )

        # Grant state machine permission to start nested executions
        self._state_machine.add_to_role_policy(iam.PolicyStatement(
            actions=["states:StartExecution"],
            resources=["*"],
        ))

        # Grant invoke on all ingestion lambdas
        for fn in ingestion_lambdas.values():
            fn.grant_invoke(self._state_machine.role)

    @property
    def state_machine(self) -> sfn.StateMachine:
        return self._state_machine
