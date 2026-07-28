"""SchedulerStack — EventBridge rules that trigger jobs on a schedule.

Two rules:
  1. silver-gold-job  — runs runner.py (silver refine → gold aggregate) every hour
  2. redshift-load    — runs redshift/load.py after gold completes (15 min offset)

Both run as ECS Fargate tasks using the same container images as the services
but with a one-shot CMD override. Separate task roles with minimal permissions.
"""
import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as targets
import aws_cdk.aws_iam as iam
import aws_cdk.aws_logs as logs
from constructs import Construct

from stacks.compute import ComputeStack
from stacks.lake import LakeStack


class SchedulerStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        compute: ComputeStack,
        lake: LakeStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # IAM role that EventBridge uses to launch ECS tasks
        scheduler_role = iam.Role(
            self, "SchedulerRole",
            assumed_by=iam.ServicePrincipal("events.amazonaws.com"),
            description="EventBridge - launch ECS Fargate job tasks",
        )
        scheduler_role.add_to_policy(iam.PolicyStatement(
            sid="RunTask",
            actions=["ecs:RunTask"],
            resources=["*"],
            conditions={
                "ArnLike": {
                    "ecs:cluster": compute.cluster.cluster_arn,
                },
            },
        ))
        scheduler_role.add_to_policy(iam.PolicyStatement(
            sid="PassTaskRoles",
            actions=["iam:PassRole"],
            resources=[
                compute.consumer_task_role.role_arn,
                compute.analytics_api_task_role.role_arn,
            ],
        ))

        # Common env for job tasks (same as services)
        job_env = {
            "ENV":             "production",
            "AWS_REGION":      self.region,
            "S3_BUCKET":       lake.bucket.bucket_name,
            "ATHENA_DATABASE": "analytics",
        }

        # --- silver + gold job (runner.py) ----------------------------------
        # consumer image already has runner.py; override CMD
        runner_td = ecs.FargateTaskDefinition(
            self, "RunnerTd",
            cpu=256, memory_limit_mib=512,
            task_role=compute.consumer_task_role,
        )
        runner_td.add_container(
            "runner",
            image=ecs.ContainerImage.from_ecr_repository(compute.ecr_consumer, tag="latest"),
            command=["python", "jobs/runner.py"],
            environment=job_env,
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="runner",
                log_retention=logs.RetentionDays.TWO_WEEKS,
            ),
        )

        events.Rule(
            self, "SilverGoldSchedule",
            description="Run silver→gold jobs every hour",
            schedule=events.Schedule.cron(minute="0"),   # top of every hour
            targets=[
                targets.EcsTask(
                    cluster=compute.cluster,
                    task_definition=runner_td,
                    launch_type=ecs.LaunchType.FARGATE,
                    task_count=1,
                    subnet_selection=ec2.SubnetSelection(
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                    ),
                    role=scheduler_role,
                )
            ],
        )

        # --- Redshift load job (redshift/load.py) ---------------------------
        # analytics-api image has the load script; override CMD
        load_td = ecs.FargateTaskDefinition(
            self, "RedshiftLoadTd",
            cpu=256, memory_limit_mib=512,
            task_role=compute.analytics_api_task_role,
        )
        load_td.add_container(
            "redshift-load",
            image=ecs.ContainerImage.from_ecr_repository(compute.ecr_analytics_api, tag="latest"),
            command=["python", "jobs/redshift/load.py"],
            environment={
                **job_env,
                "REDSHIFT_WORKGROUP": "analytics",
                "REDSHIFT_DATABASE":  "analytics",
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="redshift-load",
                log_retention=logs.RetentionDays.TWO_WEEKS,
            ),
        )

        events.Rule(
            self, "RedshiftLoadSchedule",
            description="Load gold → Redshift marts 15 min after gold jobs",
            schedule=events.Schedule.cron(minute="15"),  # :15 past every hour
            targets=[
                targets.EcsTask(
                    cluster=compute.cluster,
                    task_definition=load_td,
                    launch_type=ecs.LaunchType.FARGATE,
                    task_count=1,
                    subnet_selection=ec2.SubnetSelection(
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                    ),
                    role=scheduler_role,
                )
            ],
        )
