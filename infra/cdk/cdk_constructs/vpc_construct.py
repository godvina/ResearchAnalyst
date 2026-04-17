"""VPC construct — create new or import existing VPC with optional flow logs.

Requirements: 2.1, 2.2, 2.3, 2.4
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_logs as logs,
)
from constructs import Construct


class VpcConstruct(Construct):
    """VPC — create new with config CIDR or import existing by ID."""

    def __init__(self, scope: Construct, id: str, *, config: dict) -> None:
        super().__init__(scope, id)

        vpc_cfg = config.get("vpc", {})
        create_new = vpc_cfg.get("create_new", False)

        if create_new:
            self._vpc = ec2.Vpc(
                self, "ResearchVpc",
                ip_addresses=ec2.IpAddresses.cidr(vpc_cfg["cidr"]),
                max_azs=2,
                nat_gateways=1,
                subnet_configuration=[
                    ec2.SubnetConfiguration(
                        name="Public",
                        subnet_type=ec2.SubnetType.PUBLIC,
                        cidr_mask=24,
                    ),
                    ec2.SubnetConfiguration(
                        name="Private",
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                        cidr_mask=24,
                    ),
                    ec2.SubnetConfiguration(
                        name="Isolated",
                        subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                        cidr_mask=24,
                    ),
                ],
            )
        else:
            existing_vpc_id = vpc_cfg.get("existing_vpc_id", "")
            if existing_vpc_id == "default":
                self._vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)
            else:
                self._vpc = ec2.Vpc.from_lookup(
                    self, "ImportedVpc", vpc_id=existing_vpc_id,
                )

        # VPC flow logs
        if config.get("logging", {}).get("vpc_flow_logs", False):
            log_group = logs.LogGroup(
                self, "VpcFlowLogGroup",
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            )
            ec2.FlowLog(
                self, "VpcFlowLog",
                resource_type=ec2.FlowLogResourceType.from_vpc(self._vpc),
                destination=ec2.FlowLogDestination.to_cloud_watch_logs(log_group),
            )

    @property
    def vpc(self) -> ec2.IVpc:
        """The VPC (created or imported)."""
        return self._vpc
