"""PipelineStack — GitHub Actions OIDC provider + deploy role.

No AWS account IDs, usernames, or secrets appear anywhere in this file.
Account/region come from CDK_DEFAULT_ACCOUNT / CDK_DEFAULT_REGION at synth
time. The GitHub repo name is passed as a plain parameter from app.py.

The deploy role grants the minimum permissions needed for the CI pipeline:
  - ECR: push images to the three analytics repos
  - ECS: force-new-deployment + wait stable on the three services
"""
import aws_cdk as cdk
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_iam as iam
from constructs import Construct

_GITHUB_OIDC_ISSUER_HOST = "token.actions.githubusercontent.com"
_GITHUB_OIDC_ISSUER_URL = f"https://{_GITHUB_OIDC_ISSUER_HOST}"


class PipelineStack(cdk.Stack):
    """IAM identity GitHub Actions assumes to build, push, and deploy.

    No AWS access keys are stored in GitHub: the workflow exchanges a
    short-lived OIDC token (scoped to this exact repo + branch) for
    temporary credentials via sts:AssumeRoleWithWebIdentity.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        github_repository: str,
        ecr_ingestion: ecr.IRepository,
        ecr_consumer: ecr.IRepository,
        ecr_analytics_api: ecr.IRepository,
        ingestion_service: ecs.FargateService,
        consumer_service: ecs.FargateService,
        analytics_api_service: ecs.FargateService,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create (or import if already exists) the GitHub OIDC provider.
        # CDK handles the "already exists" case gracefully — it looks up the
        # existing provider by URL rather than trying to create a duplicate.
        github_oidc_provider = iam.OpenIdConnectProvider(
            self,
            "GitHubOidcProvider",
            url=_GITHUB_OIDC_ISSUER_URL,
            client_ids=["sts.amazonaws.com"],
        )

        # StringLike on "sub" restricts this role to workflows running on
        # main in this exact repo — a fork or PR branch can't assume it.
        self.deploy_role = iam.Role(
            self,
            "GitHubActionsDeployRole",
            role_name="analytics-platform-github-actions-deploy",
            max_session_duration=cdk.Duration.hours(1),
            assumed_by=iam.FederatedPrincipal(
                github_oidc_provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        f"{_GITHUB_OIDC_ISSUER_HOST}:aud": "sts.amazonaws.com",
                    },
                    "StringLike": {
                        f"{_GITHUB_OIDC_ISSUER_HOST}:sub": [
                            f"repo:{github_repository}:ref:refs/heads/main",
                        ],
                    },
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
        )

        # ECR auth token — account-level, no resource scope available
        self.deploy_role.add_to_principal_policy(iam.PolicyStatement(
            sid="EcrAuth",
            actions=["ecr:GetAuthorizationToken"],
            resources=["*"],
        ))

        # ECR push — scoped to the three analytics repos only
        self.deploy_role.add_to_principal_policy(iam.PolicyStatement(
            sid="EcrPush",
            actions=[
                "ecr:BatchCheckLayerAvailability",
                "ecr:CompleteLayerUpload",
                "ecr:InitiateLayerUpload",
                "ecr:PutImage",
                "ecr:UploadLayerPart",
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer",
            ],
            resources=[
                ecr_ingestion.repository_arn,
                ecr_consumer.repository_arn,
                ecr_analytics_api.repository_arn,
            ],
        ))

        # ECS deploy — scoped to the three service ARNs
        self.deploy_role.add_to_principal_policy(iam.PolicyStatement(
            sid="EcsDeploy",
            actions=["ecs:UpdateService", "ecs:DescribeServices"],
            resources=[
                ingestion_service.service_arn,
                consumer_service.service_arn,
                analytics_api_service.service_arn,
            ],
        ))

        cdk.CfnOutput(
            self, "DeployRoleArn",
            value=self.deploy_role.role_arn,
            description="ARN for GithubActionsDeployRole — set as AWS_ROLE_ARN in GitHub Actions",
        )
