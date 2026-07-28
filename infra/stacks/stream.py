"""StreamStack — Redshift Serverless namespace/workgroup + DynamoDB cache table.

Redshift Serverless:
  - base_capacity=8 RPU (minimum) — auto-pauses after 30 min idle (no charges while paused)
  - Costs ~$0.36/RPU-hour only when active — suitable for portfolio

DynamoDB:
  - PAY_PER_REQUEST (on-demand) — zero cost when idle
  - TTL enabled on 'ttl' attribute
"""
import aws_cdk as cdk
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_iam as iam
import aws_cdk.aws_redshiftserverless as redshift
from constructs import Construct

from stacks.lake import LakeStack


class StreamStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        lake: LakeStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- IAM role for Redshift Serverless → S3 COPY ---------------------
        # Redshift needs to read gold Parquet from S3 during COPY commands
        self.redshift_s3_role = iam.Role(
            self, "RedshiftS3Role",
            assumed_by=iam.ServicePrincipal("redshift.amazonaws.com"),
            description="Allows Redshift Serverless to COPY Parquet from the lake bucket",
        )
        lake.bucket.grant_read(self.redshift_s3_role, "gold/*")

        # --- Redshift Serverless --------------------------------------------
        self.rs_namespace = redshift.CfnNamespace(
            self, "RsNamespace",
            namespace_name="analytics",
            db_name="analytics",
            iam_roles=[self.redshift_s3_role.role_arn],
            # Admin credentials managed via Secrets Manager (CDK default)
        )

        self.rs_workgroup = redshift.CfnWorkgroup(
            self, "RsWorkgroup",
            workgroup_name="analytics",
            namespace_name="analytics",
            base_capacity=8,           # minimum RPU — auto-pauses when idle
            publicly_accessible=False,  # accessed only via Data API, never direct TCP
        )
        self.rs_workgroup.add_dependency(self.rs_namespace)

        # --- DynamoDB metrics cache -----------------------------------------
        self.cache_table = dynamodb.Table(
            self, "MetricsCache",
            table_name="metrics-cache",
            partition_key=dynamodb.Attribute(
                name="cache_key",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=cdk.RemovalPolicy.DESTROY,  # cache is ephemeral
        )
