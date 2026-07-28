"""ComputeStack — ECR repos, ECS Fargate cluster, ALB, task definitions, IAM roles.

Three services:
  - ingestion   (public, port 8000) — receives events, writes to Kinesis
  - consumer    (private, no port)  — reads Kinesis, writes to S3
  - analytics-api (public, port 8001) — serves metrics from Redshift/Athena/DynamoDB

IAM follows least privilege — each task role grants only what that service needs.
Images are pulled from ECR; the GitHub Actions pipeline pushes on every main commit.
"""
import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_elasticloadbalancingv2 as elbv2
import aws_cdk.aws_iam as iam
import aws_cdk.aws_logs as logs
from constructs import Construct

from stacks.lake import LakeStack
from stacks.network import NetworkStack
from stacks.stream import StreamStack

# Log retention — keep 2 weeks, low cost
LOG_RETENTION = logs.RetentionDays.TWO_WEEKS


class ComputeStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        network: NetworkStack,
        lake: LakeStack,
        stream: StreamStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- ECR repositories -----------------------------------------------
        self.ecr_ingestion = ecr.Repository(
            self, "EcrIngestion",
            repository_name="analytics/ingestion",
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=5)],
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        self.ecr_consumer = ecr.Repository(
            self, "EcrConsumer",
            repository_name="analytics/consumer",
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=5)],
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        self.ecr_analytics_api = ecr.Repository(
            self, "EcrAnalyticsApi",
            repository_name="analytics/analytics-api",
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=5)],
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # --- ECS cluster ----------------------------------------------------
        self.cluster = ecs.Cluster(
            self, "Cluster",
            vpc=network.vpc,
            container_insights=True,
        )

        # --- Security groups ------------------------------------------------
        # Defined here (not NetworkStack) to avoid cross-stack cyclic references
        # with the ALB security group that CDK auto-creates.

        # ALB: accepts HTTP from anywhere
        alb_sg = ec2.SecurityGroup(
            self, "AlbSg",
            vpc=network.vpc,
            description="ALB - inbound HTTP from internet",
            allow_all_outbound=True,
        )
        alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")

        # Fargate tasks: accept only from ALB; egress via NAT to AWS APIs
        self.tasks_sg = ec2.SecurityGroup(
            self, "TasksSg",
            vpc=network.vpc,
            description="Fargate tasks - inbound from ALB only",
            allow_all_outbound=True,
        )
        self.tasks_sg.add_ingress_rule(alb_sg, ec2.Port.tcp(8000), "ALB → ingestion")
        self.tasks_sg.add_ingress_rule(alb_sg, ec2.Port.tcp(8001), "ALB → analytics-api")

        # --- Task IAM roles -------------------------------------------------

        # ingestion: kinesis:PutRecord on the events stream only
        ingestion_role = iam.Role(
            self, "IngestionTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="ingestion service - PutRecord on events stream",
        )
        ingestion_role.add_to_policy(iam.PolicyStatement(
            sid="KinesisWrite",
            actions=["kinesis:PutRecord", "kinesis:PutRecords"],
            resources=[lake.stream.stream_arn],
        ))

        # consumer: Kinesis read + S3 write to bronze/ and silver/ prefixes
        consumer_role = iam.Role(
            self, "ConsumerTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="consumer service - read Kinesis, write S3 bronze/silver",
        )
        consumer_role.add_to_policy(iam.PolicyStatement(
            sid="KinesisRead",
            actions=[
                "kinesis:GetRecords",
                "kinesis:GetShardIterator",
                "kinesis:DescribeStream",
                "kinesis:DescribeStreamSummary",
                "kinesis:ListShards",
                "kinesis:ListStreams",
            ],
            resources=[lake.stream.stream_arn],
        ))
        consumer_role.add_to_policy(iam.PolicyStatement(
            sid="S3WriteLake",
            actions=["s3:PutObject", "s3:DeleteObject"],
            resources=[
                lake.bucket.arn_for_objects("bronze/*"),
                lake.bucket.arn_for_objects("silver/*"),
            ],
        ))
        consumer_role.add_to_policy(iam.PolicyStatement(
            sid="S3ListBucket",
            actions=["s3:ListBucket", "s3:GetBucketLocation"],
            resources=[lake.bucket.bucket_arn],
        ))

        # analytics-api: Athena ad-hoc + S3 gold read + DynamoDB cache + Redshift Data API
        analytics_api_role = iam.Role(
            self, "AnalyticsApiTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="analytics-api - Athena, S3 gold, DynamoDB cache, Redshift Data API",
        )
        analytics_api_role.add_to_policy(iam.PolicyStatement(
            sid="AthenaQuery",
            actions=[
                "athena:StartQueryExecution",
                "athena:GetQueryExecution",
                "athena:GetQueryResults",
                "athena:StopQueryExecution",
            ],
            resources=[
                f"arn:aws:athena:{self.region}:{self.account}:workgroup/analytics",
            ],
        ))
        analytics_api_role.add_to_policy(iam.PolicyStatement(
            sid="GlueCatalogRead",
            actions=[
                "glue:GetDatabase",
                "glue:GetTable",
                "glue:GetPartitions",
            ],
            resources=[
                f"arn:aws:glue:{self.region}:{self.account}:catalog",
                f"arn:aws:glue:{self.region}:{self.account}:database/analytics",
                f"arn:aws:glue:{self.region}:{self.account}:table/analytics/*",
            ],
        ))
        analytics_api_role.add_to_policy(iam.PolicyStatement(
            sid="S3ReadLake",
            actions=["s3:GetObject"],
            resources=[
                lake.bucket.arn_for_objects("gold/*"),
                lake.bucket.arn_for_objects("silver/*"),
                lake.bucket.arn_for_objects("athena-results/*"),
            ],
        ))
        analytics_api_role.add_to_policy(iam.PolicyStatement(
            sid="S3AthenaResults",
            actions=["s3:PutObject"],
            resources=[lake.bucket.arn_for_objects("athena-results/*")],
        ))
        analytics_api_role.add_to_policy(iam.PolicyStatement(
            sid="S3ListBucket",
            actions=["s3:ListBucket", "s3:GetBucketLocation"],
            resources=[lake.bucket.bucket_arn],
        ))
        analytics_api_role.add_to_policy(iam.PolicyStatement(
            sid="DynamoDBCache",
            actions=["dynamodb:GetItem", "dynamodb:PutItem"],
            resources=[stream.cache_table.table_arn],
        ))
        analytics_api_role.add_to_policy(iam.PolicyStatement(
            sid="RedshiftDataApi",
            actions=[
                "redshift-data:ExecuteStatement",
                "redshift-data:DescribeStatement",
                "redshift-data:GetStatementResult",
            ],
            resources=[
                f"arn:aws:redshift-serverless:{self.region}:{self.account}:workgroup/*",
            ],
        ))

        # Expose roles so SchedulerStack can reference for jobs
        self.ingestion_task_role    = ingestion_role
        self.consumer_task_role     = consumer_role
        self.analytics_api_task_role = analytics_api_role

        # --- Common env vars ------------------------------------------------
        bucket_name = lake.bucket.bucket_name
        common_env = {
            "ENV":                "production",
            "AWS_REGION":         self.region,
            "S3_BUCKET":          bucket_name,
            "ATHENA_DATABASE":    "analytics",
        }

        # --- ingestion task definition + ALB service ------------------------
        ingestion_td = ecs.FargateTaskDefinition(
            self, "IngestionTd",
            cpu=256, memory_limit_mib=512,
            task_role=ingestion_role,
        )
        ingestion_td.add_container(
            "ingestion",
            image=ecs.ContainerImage.from_ecr_repository(self.ecr_ingestion, tag="latest"),
            environment={
                **common_env,
                "KINESIS_STREAM_NAME": lake.stream.stream_name,
            },
            port_mappings=[ecs.PortMapping(container_port=8000)],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ingestion",
                log_retention=LOG_RETENTION,
            ),
        )

        # --- ingestion ALB + service ----------------------------------------
        ingestion_alb = elbv2.ApplicationLoadBalancer(
            self, "IngestionAlb",
            vpc=network.vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=alb_sg,
        )
        ingestion_listener = ingestion_alb.add_listener(
            "IngestionListener", port=80, open=False,
        )

        self.ingestion_service = ecs.FargateService(
            self, "IngestionService",
            cluster=self.cluster,
            task_definition=ingestion_td,
            desired_count=1,
            security_groups=[self.tasks_sg],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            min_healthy_percent=100,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )
        ingestion_listener.add_targets(
            "IngestionTargets",
            port=8000,
            targets=[self.ingestion_service],
            health_check=elbv2.HealthCheck(path="/health", healthy_http_codes="200"),
        )

        # --- consumer task definition + standalone service ------------------
        consumer_td = ecs.FargateTaskDefinition(
            self, "ConsumerTd",
            cpu=256, memory_limit_mib=512,
            task_role=consumer_role,
        )
        consumer_td.add_container(
            "consumer",
            image=ecs.ContainerImage.from_ecr_repository(self.ecr_consumer, tag="latest"),
            environment={
                **common_env,
                "KINESIS_STREAM_NAME": lake.stream.stream_name,
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="consumer",
                log_retention=LOG_RETENTION,
            ),
        )

        # Consumer runs in private subnets — no ALB, no public IP
        self.consumer_service = ecs.FargateService(
            self, "ConsumerService",
            cluster=self.cluster,
            task_definition=consumer_td,
            desired_count=1,
            security_groups=[self.tasks_sg],
            vpc_subnets=cdk.aws_ec2.SubnetSelection(
                subnet_type=cdk.aws_ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            min_healthy_percent=100,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )

        # --- analytics-api task definition + ALB service --------------------
        analytics_api_td = ecs.FargateTaskDefinition(
            self, "AnalyticsApiTd",
            cpu=256, memory_limit_mib=512,
            task_role=analytics_api_role,
        )
        analytics_api_td.add_container(
            "analytics-api",
            image=ecs.ContainerImage.from_ecr_repository(self.ecr_analytics_api, tag="latest"),
            environment={
                **common_env,
                "REDSHIFT_WORKGROUP":     "analytics",
                "REDSHIFT_DATABASE":      "analytics",
                "DYNAMODB_CACHE_TABLE":   "metrics-cache",
                "DASHBOARD_DIR":          "/app/dashboard",
            },
            port_mappings=[ecs.PortMapping(container_port=8001)],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="analytics-api",
                log_retention=LOG_RETENTION,
            ),
        )

        # --- analytics-api ALB + service ------------------------------------
        analytics_alb = elbv2.ApplicationLoadBalancer(
            self, "AnalyticsApiAlb",
            vpc=network.vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=alb_sg,
        )
        analytics_listener = analytics_alb.add_listener(
            "AnalyticsApiListener", port=80, open=False,
        )

        self.analytics_api_service = ecs.FargateService(
            self, "AnalyticsApiService",
            cluster=self.cluster,
            task_definition=analytics_api_td,
            desired_count=1,
            security_groups=[self.tasks_sg],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            min_healthy_percent=100,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )
        analytics_listener.add_targets(
            "AnalyticsApiTargets",
            port=8001,
            targets=[self.analytics_api_service],
            health_check=elbv2.HealthCheck(path="/health", healthy_http_codes="200"),
        )

        # --- Outputs --------------------------------------------------------
        cdk.CfnOutput(self, "IngestionUrl",
            value=ingestion_alb.load_balancer_dns_name,
            description="Ingestion API endpoint",
        )
        cdk.CfnOutput(self, "AnalyticsApiUrl",
            value=analytics_alb.load_balancer_dns_name,
            description="Analytics API / dashboard endpoint",
        )
        cdk.CfnOutput(self, "EcrIngestionUri",
            value=self.ecr_ingestion.repository_uri,
            description="ECR URI for ingestion (used by CI)",
        )
        cdk.CfnOutput(self, "EcrConsumerUri",
            value=self.ecr_consumer.repository_uri,
            description="ECR URI for consumer (used by CI)",
        )
        cdk.CfnOutput(self, "EcrAnalyticsApiUri",
            value=self.ecr_analytics_api.repository_uri,
            description="ECR URI for analytics-api (used by CI)",
        )
