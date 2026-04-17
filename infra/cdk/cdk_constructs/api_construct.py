"""API construct — API Gateway REST API with Lambda proxy integration.

Requirements: 9.1
"""

from typing import Optional

from aws_cdk import (
    aws_apigateway as apigw,
    aws_lambda as _lambda,
    aws_logs as logs,
)
from constructs import Construct


class ApiConstruct(Construct):
    """Conditional API Gateway LambdaRestApi. Skipped when pipeline_only=true."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        config: dict,
        api_lambdas: dict[str, _lambda.Function],
    ) -> None:
        super().__init__(scope, id)

        features_cfg = config.get("features", {})
        pipeline_only = features_cfg.get("pipeline_only", False)
        self._api: Optional[apigw.RestApi] = None

        if pipeline_only or not api_lambdas:
            return

        cf_lambda = api_lambdas.get("case_files")
        if not cf_lambda:
            return

        # --- Config-driven API settings (Tasks 1.1, 1.2, 1.3) ---
        api_cfg = config.get("api", {})

        # Task 1.1: Stage-level throttling
        burst = api_cfg.get("throttle_burst_limit", 100)
        rate = api_cfg.get("throttle_rate_limit", 50)

        # Task 1.2: Config-driven CORS origins
        cors_origins = api_cfg.get("cors_allow_origins", None)
        allow_origins = cors_origins if cors_origins else apigw.Cors.ALL_ORIGINS

        # Task 1.3: Conditional access logging
        stage_opts: dict = {
            "stage_name": "v1",
            "throttling_burst_limit": burst,
            "throttling_rate_limit": rate,
        }
        if api_cfg.get("access_logging", False):
            access_log_group = logs.LogGroup(
                self, "ApiAccessLogs",
                retention=logs.RetentionDays.THREE_MONTHS,
            )
            stage_opts["access_log_destination"] = apigw.LogGroupLogDestination(access_log_group)
            stage_opts["access_log_format"] = apigw.AccessLogFormat.clf()

        self._api = apigw.LambdaRestApi(
            self, "ResearchAnalystApi",
            handler=cf_lambda,
            rest_api_name="Research Analyst API",
            description="REST API for the Research Analyst Platform",
            deploy_options=apigw.StageOptions(**stage_opts),
            proxy=True,
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=allow_origins,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                ],
            ),
        )

    @property
    def api(self) -> Optional[apigw.RestApi]:
        return self._api
