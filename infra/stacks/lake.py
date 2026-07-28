"""LakeStack — S3 data lake, Kinesis stream, Glue catalog, Athena workgroup.

Bucket name: product-analytics-lake-{account_id}  (globally unique, deterministic).
"""

import aws_cdk as cdk
import aws_cdk.aws_athena as athena
import aws_cdk.aws_glue as glue
import aws_cdk.aws_kinesis as kinesis
import aws_cdk.aws_s3 as s3
from constructs import Construct


class LakeStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- S3 data lake ---------------------------------------------------
        # Name embeds account ID → globally unique, no collision risk
        self.bucket = s3.Bucket(
            self,
            "LakeBucket",
            bucket_name=f"product-analytics-lake-{self.account}",
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            # Keep lake data; only purge temp Athena results
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="expire-athena-results",
                    prefix="athena-results/",
                    expiration=cdk.Duration.days(7),
                ),
            ],
            removal_policy=cdk.RemovalPolicy.RETAIN,  # never auto-delete lake data
        )

        # --- Kinesis event stream -------------------------------------------
        # 1 shard = 1 MB/s ingest, 2 MB/s read
        self.stream = kinesis.Stream(
            self,
            "EventStream",
            stream_name="events",
            shard_count=1,
            retention_period=cdk.Duration.hours(24),
            encryption=kinesis.StreamEncryption.KMS,  # AWS-managed KMS key
        )

        # --- Glue Data Catalog ----------------------------------------------
        self.glue_database = glue.CfnDatabase(
            self,
            "GlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="analytics",
                description="Product analytics data lake (bronze / silver / gold)",
            ),
        )

        # --- Athena workgroup -----------------------------------------------
        # Enforce per-query cost control (100 MB limit suitable for gold scans)
        self.athena_workgroup = athena.CfnWorkGroup(
            self,
            "AthenaWorkgroup",
            name="analytics",
            description="Analytics queries over the data lake",
            recursive_delete_option=True,
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{self.bucket.bucket_name}/athena-results/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3",
                    ),
                ),
                bytes_scanned_cutoff_per_query=100 * 1024 * 1024,  # 100 MB — cost guard
                enforce_work_group_configuration=True,
                publish_cloud_watch_metrics_enabled=True,
            ),
        )
        self.athena_workgroup.add_dependency(self.glue_database)
