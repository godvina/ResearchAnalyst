"""OpenSearch construct — conditional OpenSearch Serverless collection.

Requirements: 5.1, 5.2, 7.3, 17.1, 17.2
"""

import json
from typing import Optional

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_opensearchserverless as aoss,
)
from constructs import Construct


class OpenSearchConstruct(Construct):
    """Conditional OpenSearch Serverless VECTORSEARCH collection."""

    def __init__(
        self, scope: Construct, id: str, *, config: dict, vpc: ec2.IVpc,
    ) -> None:
        super().__init__(scope, id)

        os_cfg = config.get("opensearch", {})
        mode = os_cfg.get("mode", "disabled")
        self._enabled = mode == "serverless"
        self._collection: Optional[aoss.CfnCollection] = None
        self._endpoint = ""
        self._collection_id = ""

        if not self._enabled:
            return

        encryption_cfg = config.get("encryption", {})
        kms_key_arn = encryption_cfg.get("kms_key_arn")
        collection_name = "research-analyst-search"

        # --- Encryption policy ---
        if kms_key_arn:
            enc_policy_doc = {
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": [f"collection/{collection_name}"],
                    },
                ],
                "AWSOwnedKey": False,
                "KmsARN": kms_key_arn,
            }
        else:
            enc_policy_doc = {
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": [f"collection/{collection_name}"],
                    },
                ],
                "AWSOwnedKey": True,
            }

        encryption_policy = aoss.CfnSecurityPolicy(
            self, "OSSEncryptionPolicy",
            name=f"{collection_name}-enc",
            type="encryption",
            policy=json.dumps(enc_policy_doc),
        )

        # --- VPC endpoint for AOSS ---
        aoss_vpce_sg = ec2.SecurityGroup(
            self, "OSSVpcEndpointSG",
            vpc=vpc,
            description="Security group for OpenSearch Serverless VPC endpoint",
            allow_all_outbound=True,
        )
        aoss_vpce_sg.add_ingress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(443),
            "Allow HTTPS from VPC to AOSS endpoint",
        )
        self._vpce_sg = aoss_vpce_sg

        # Determine subnet type for VPC endpoint — match the config or default PUBLIC
        aurora_subnet = config.get("aurora", {}).get("subnet_type", "PUBLIC")
        if aurora_subnet == "PRIVATE_WITH_EGRESS":
            vpce_subnet_type = ec2.SubnetType.PRIVATE_WITH_EGRESS
        else:
            vpce_subnet_type = ec2.SubnetType.PUBLIC

        aoss_vpce = ec2.InterfaceVpcEndpoint(
            self, "OSSVpcEndpoint",
            vpc=vpc,
            service=ec2.InterfaceVpcEndpointService(
                cdk.Fn.sub("com.amazonaws.${AWS::Region}.aoss"),
                443,
            ),
            subnets=ec2.SubnetSelection(subnet_type=vpce_subnet_type),
            security_groups=[aoss_vpce_sg],
            private_dns_enabled=True,
        )

        # --- Network policy ---
        network_policy = aoss.CfnSecurityPolicy(
            self, "OSSNetworkPolicy",
            name=f"{collection_name}-net",
            type="network",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{collection_name}"],
                        },
                        {
                            "ResourceType": "dashboard",
                            "Resource": [f"collection/{collection_name}"],
                        },
                    ],
                    "AllowFromPublic": False,
                    "SourceVPCEs": [aoss_vpce.vpc_endpoint_id],
                },
            ]),
        )

        # --- Data access policy ---
        data_access_policy = aoss.CfnAccessPolicy(
            self, "OSSDataAccessPolicy",
            name=f"{collection_name}-dap",
            type="data",
            policy=cdk.Fn.sub(
                json.dumps([
                    {
                        "Rules": [
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{collection_name}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                ],
                            },
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                ],
                            },
                        ],
                        "Principal": [
                            "arn:aws:iam::${AWS::AccountId}:root",
                        ],
                        "Description": "Lambda access to OpenSearch Serverless collection",
                    },
                ])
            ),
        )

        # --- Collection ---
        self._collection = aoss.CfnCollection(
            self, "OSSCollection",
            name=collection_name,
            type="VECTORSEARCH",
            description="Enterprise tier vector + full-text search for Research Analyst Platform",
        )
        self._collection.add_dependency(encryption_policy)
        self._collection.add_dependency(network_policy)
        self._collection.add_dependency(data_access_policy)

        # Store for downstream permission grants
        self._collection_name = collection_name

    @property
    def collection(self) -> Optional[aoss.CfnCollection]:
        return self._collection

    @property
    def endpoint(self) -> str:
        if self._collection:
            return self._collection.attr_collection_endpoint
        return ""

    @property
    def collection_id(self) -> str:
        if self._collection:
            return self._collection.attr_id
        return ""

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def vpce_sg(self):
        """VPC endpoint security group — used by LambdaConstruct for ingress rules."""
        return getattr(self, "_vpce_sg", None)

    @property
    def collection_name(self) -> str:
        return getattr(self, "_collection_name", "")
