"""NetworkStack — VPC and subnets only.

Security groups live in ComputeStack alongside the resources that use them,
avoiding cross-stack cyclic references with the ALB SG.

Single NAT gateway (cost: ~$32/mo) — acceptable for a portfolio project.
Production-grade: increase to one per AZ for HA.
"""
import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
from constructs import Construct


class NetworkStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Two AZs, one NAT GW — low cost, sufficient for portfolio
        self.vpc = ec2.Vpc(
            self, "Vpc",
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
            ],
        )
