"""Aurora construct — Serverless v2 PostgreSQL with RDS Proxy.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 7.4, 17.1, 17.2
"""

import aws_cdk as cdk
from aws_cdk import (
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_kms as kms,
    aws_rds as rds,
)
from constructs import Construct


_SUBNET_TYPE_MAP = {
    "PUBLIC": ec2.SubnetType.PUBLIC,
    "PRIVATE_WITH_EGRESS": ec2.SubnetType.PRIVATE_WITH_EGRESS,
}


class AuroraConstruct(Construct):
    """Aurora Serverless v2 cluster with RDS Proxy."""

    def __init__(
        self, scope: Construct, id: str, *, config: dict, vpc: ec2.IVpc,
    ) -> None:
        super().__init__(scope, id)

        aurora_cfg = config.get("aurora", {})
        encryption_cfg = config.get("encryption", {})
        subnet_type = _SUBNET_TYPE_MAP.get(
            aurora_cfg.get("subnet_type", "PUBLIC"), ec2.SubnetType.PUBLIC,
        )

        # Security group
        aurora_sg = ec2.SecurityGroup(
            self, "AuroraSG",
            vpc=vpc,
            description="Aurora Serverless v2 security group",
            allow_all_outbound=False,
        )
        aurora_sg.add_ingress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(5432),
            "Allow PostgreSQL from VPC",
        )

        # KMS encryption
        kms_key_arn = encryption_cfg.get("kms_key_arn")
        storage_encryption_key = (
            kms.Key.from_key_arn(self, "AuroraKmsKey", kms_key_arn)
            if kms_key_arn else None
        )

        self._cluster = rds.DatabaseCluster(
            self, "AuroraCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_4,
            ),
            serverless_v2_min_capacity=aurora_cfg.get("min_capacity", 0.5),
            serverless_v2_max_capacity=aurora_cfg.get("max_capacity", 8),
            writer=rds.ClusterInstance.serverless_v2("Writer"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=subnet_type),
            security_groups=[aurora_sg],
            default_database_name="research_analyst",
            storage_encryption_key=storage_encryption_key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # RDS Proxy
        self._proxy = rds.DatabaseProxy(
            self, "AuroraProxy",
            proxy_target=rds.ProxyTarget.from_cluster(self._cluster),
            secrets=[self._cluster.secret],
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=subnet_type),
            db_proxy_name="research-analyst-proxy",
            require_tls=True,
        )

    @property
    def cluster(self) -> rds.DatabaseCluster:
        return self._cluster

    @property
    def secret(self):
        return self._cluster.secret

    @property
    def proxy(self) -> rds.DatabaseProxy:
        return self._proxy
