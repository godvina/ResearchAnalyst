"""Security construct — S3 data lake bucket with conditional encryption and TLS.

Requirements: 7.1, 7.2
"""

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    aws_iam as iam,
    aws_kms as kms,
    aws_s3 as s3,
)
from constructs import Construct


class SecurityConstruct(Construct):
    """S3 data lake bucket with versioning, lifecycle, optional KMS and TLS enforcement."""

    def __init__(self, scope: Construct, id: str, *, config: dict) -> None:
        super().__init__(scope, id)

        encryption_cfg = config.get("encryption", {})
        kms_key_arn = encryption_cfg.get("kms_key_arn")
        enforce_tls = encryption_cfg.get("enforce_tls", False)

        # Config-driven S3 removal policy (Req 6)
        s3_cfg = config.get("s3", {})
        removal = s3_cfg.get("removal_policy", "DESTROY")
        if removal == "RETAIN":
            bucket_removal_policy = RemovalPolicy.RETAIN
            auto_delete = False
        else:
            bucket_removal_policy = RemovalPolicy.DESTROY
            auto_delete = True

        # Determine encryption settings
        if kms_key_arn:
            encryption_key = kms.Key.from_key_arn(self, "ImportedKey", kms_key_arn)
            encryption = s3.BucketEncryption.KMS
        else:
            encryption_key = None
            encryption = s3.BucketEncryption.S3_MANAGED

        self._data_bucket = s3.Bucket(
            self, "DataLakeBucket",
            bucket_name=cdk.Fn.sub("research-analyst-data-lake-${AWS::AccountId}"),
            versioned=True,
            encryption=encryption,
            encryption_key=encryption_key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=bucket_removal_policy,
            auto_delete_objects=auto_delete,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90),
                        ),
                    ],
                ),
            ],
        )

        # TLS enforcement bucket policy
        if enforce_tls:
            self._data_bucket.add_to_resource_policy(
                iam.PolicyStatement(
                    sid="DenyNonTLSRequests",
                    effect=iam.Effect.DENY,
                    principals=[iam.AnyPrincipal()],
                    actions=["s3:*"],
                    resources=[
                        self._data_bucket.bucket_arn,
                        f"{self._data_bucket.bucket_arn}/*",
                    ],
                    conditions={
                        "Bool": {"aws:SecureTransport": "false"},
                    },
                )
            )

    @property
    def data_bucket(self) -> s3.Bucket:
        """The S3 data lake bucket."""
        return self._data_bucket
