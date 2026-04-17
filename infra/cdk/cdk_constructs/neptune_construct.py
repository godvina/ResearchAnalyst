"""Neptune construct — conditional Neptune Serverless cluster.

Requirements: 4.1, 4.2, 17.1, 17.2
"""

from typing import Optional

import aws_cdk as cdk
from aws_cdk import (
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_neptune_alpha as neptune,
)
from constructs import Construct


_SUBNET_TYPE_MAP = {
    "PUBLIC": ec2.SubnetType.PUBLIC,
    "PRIVATE_WITH_EGRESS": ec2.SubnetType.PRIVATE_WITH_EGRESS,
}


class NeptuneConstruct(Construct):
    """Conditional Neptune Serverless cluster. Skips creation when disabled."""

    def __init__(
        self, scope: Construct, id: str, *, config: dict, vpc: ec2.IVpc,
    ) -> None:
        super().__init__(scope, id)

        neptune_cfg = config.get("neptune", {})
        self._enabled = neptune_cfg.get("enabled", False)
        self._cluster: Optional[neptune.DatabaseCluster] = None

        if not self._enabled:
            return

        subnet_type = _SUBNET_TYPE_MAP.get(
            neptune_cfg.get("subnet_type", "PUBLIC"), ec2.SubnetType.PUBLIC,
        )

        # Security group
        neptune_sg = ec2.SecurityGroup(
            self, "NeptuneSG",
            vpc=vpc,
            description="Neptune Serverless security group",
            allow_all_outbound=False,
        )
        neptune_sg.add_ingress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(8182),
            "Allow Neptune from VPC",
        )

        self._cluster = neptune.DatabaseCluster(
            self, "NeptuneCluster",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=subnet_type),
            security_groups=[neptune_sg],
            instance_type=neptune.InstanceType.SERVERLESS,
            serverless_scaling_configuration=neptune.ServerlessScalingConfiguration(
                min_capacity=neptune_cfg.get("min_capacity", 1),
                max_capacity=neptune_cfg.get("max_capacity", 8),
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

    @property
    def cluster(self) -> Optional[neptune.DatabaseCluster]:
        return self._cluster

    @property
    def enabled(self) -> bool:
        return self._enabled
