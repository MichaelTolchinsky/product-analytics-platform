#!/usr/bin/env python3
"""CDK app entry point.

Account and region come from the environment — never hardcoded:
  export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  export CDK_DEFAULT_REGION=eu-north-1

GitHub repository is the only app-specific value here. No account IDs,
usernames, or secrets appear in this file.

Deploy order:
  NetworkStack → LakeStack → StreamStack → ComputeStack → SchedulerStack → PipelineStack
"""
import os

import aws_cdk as cdk

from stacks.compute import ComputeStack
from stacks.lake import LakeStack
from stacks.network import NetworkStack
from stacks.pipeline import PipelineStack
from stacks.scheduler import SchedulerStack
from stacks.stream import StreamStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ.get("CDK_DEFAULT_REGION", "eu-north-1"),
)

network   = NetworkStack(app, "NetworkStack", env=env)
lake      = LakeStack(app, "LakeStack", env=env)
stream    = StreamStack(app, "StreamStack", lake=lake, env=env)
compute   = ComputeStack(app, "ComputeStack", network=network, lake=lake, stream=stream, env=env)
scheduler = SchedulerStack(app, "SchedulerStack", compute=compute, lake=lake, env=env)

PipelineStack(
    app, "PipelineStack",
    github_repository="MichaelTolchinsky/product-analytics-platform",
    ecr_ingestion=compute.ecr_ingestion,
    ecr_consumer=compute.ecr_consumer,
    ecr_analytics_api=compute.ecr_analytics_api,
    ingestion_service=compute.ingestion_service,
    consumer_service=compute.consumer_service,
    analytics_api_service=compute.analytics_api_service,
    env=env,
)

cdk.Tags.of(app).add("project", "product-analytics-platform")
cdk.Tags.of(app).add("managed-by", "cdk")

app.synth()
