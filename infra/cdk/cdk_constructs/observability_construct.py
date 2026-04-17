"""Observability construct — CloudWatch alarms for Lambda and Step Functions.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""

from aws_cdk import (
    Duration,
    aws_cloudwatch as cloudwatch,
    aws_lambda as _lambda,
    aws_sns as sns,
    aws_stepfunctions as sfn,
)
from aws_cdk.aws_cloudwatch_actions import SnsAction
from constructs import Construct


class ObservabilityConstruct(Construct):
    """CloudWatch alarms for Lambda errors/duration and Step Functions failures."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        config: dict,
        lambda_functions: dict[str, _lambda.IFunction],
        state_machine: sfn.IStateMachine,
    ) -> None:
        super().__init__(scope, id)

        monitoring_cfg = config.get("monitoring", {})
        sns_topic_arn = monitoring_cfg.get("alarm_sns_topic_arn")

        # Resolve optional SNS topic for alarm actions
        sns_topic = None
        if sns_topic_arn:
            sns_topic = sns.Topic.from_topic_arn(self, "AlarmTopic", sns_topic_arn)

        alarms: list[cloudwatch.Alarm] = []

        # --- Lambda error alarms (Errors sum > 5 in 5 min) for every function ---
        for fn_name, fn in lambda_functions.items():
            error_alarm = cloudwatch.Alarm(
                self, f"{fn_name}-errors",
                metric=fn.metric_errors(
                    statistic="Sum",
                    period=Duration.minutes(5),
                ),
                threshold=5,
                evaluation_periods=1,
                alarm_description=f"Lambda {fn_name} error rate exceeded threshold",
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            )
            alarms.append(error_alarm)

        # --- case_files duration p95 alarm (> 60000ms in 5 min) ---
        if "case_files" in lambda_functions:
            duration_alarm = cloudwatch.Alarm(
                self, "case-files-duration-p95",
                metric=lambda_functions["case_files"].metric_duration(
                    statistic="p95",
                    period=Duration.minutes(5),
                ),
                threshold=60000,
                evaluation_periods=1,
                alarm_description="case_files Lambda p95 duration exceeded 60s",
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            )
            alarms.append(duration_alarm)

        # --- Step Functions failure alarm (ExecutionsFailed sum > 1 in 5 min) ---
        sfn_alarm = cloudwatch.Alarm(
            self, "sfn-failures",
            metric=state_machine.metric_failed(
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Step Functions execution failures exceeded threshold",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )
        alarms.append(sfn_alarm)

        # --- Add SNS alarm action to every alarm when configured ---
        if sns_topic:
            for alarm in alarms:
                alarm.add_alarm_action(SnsAction(sns_topic))
