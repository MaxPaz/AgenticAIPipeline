"""
AWS CDK Stack for Bedrock AgentCore

This stack creates:
- AgentCore runtime agent (replaces four-agent Bedrock Agents pipeline)
- IAM role for AgentCore with Lambda invoke and Bedrock model permissions
- Lambda functions: get_kpi_data, sql_executor (reference), get_available_kpis
- CloudFormation outputs for AgentCore agent ID and endpoint
"""

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    CfnOutput,
    CfnResource,
    Duration,
)
from constructs import Construct


class BedrockAgentStack(Stack):
    """CDK Stack for AgentCore Coordinator Agent."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ===================================================================
        # Shared Lambda execution role
        # ===================================================================

        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            role_name="QueenAI-Lambda-Execution-Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for QueenAI Lambda functions",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
            ],
        )

        # ===================================================================
        # Lambda Layer
        # ===================================================================

        pymysql_layer = lambda_.LayerVersion(
            self, "PyMySQLLayer",
            code=lambda_.Code.from_asset("../../lambda/layers/pymysql"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="PyMySQL library for database connections",
        )

        # ===================================================================
        # Lambda Functions
        # ===================================================================

        # Lambda 1: get_kpi_data
        get_kpi_data_lambda = lambda_.Function(
            self, "GetKpiDataLambda",
            function_name="queen-get-kpi-data-lambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("../../lambda/get_kpi_data"),
            layers=[pymysql_layer],
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            description="Retrieves pre-calculated KPI data from sales_metrics table",
            vpc=ec2.Vpc.from_lookup(self, "ExistingVpc", vpc_id="vpc-22c16b5a"),
            vpc_subnets=ec2.SubnetSelection(
                subnets=[
                    ec2.Subnet.from_subnet_id(self, "Subnet1", "subnet-e11b0dbb"),
                    ec2.Subnet.from_subnet_id(self, "Subnet2", "subnet-2a64ea01"),
                ]
            ),
            security_groups=[
                ec2.SecurityGroup.from_security_group_id(
                    self, "LambdaSecurityGroup",
                    security_group_id="sg-0a6221ae499043e85",
                )
            ],
            allow_public_subnet=True,
            environment={
                "DB_HOST": "queen-demo-mysql.c06zxi4g5mx8.us-west-2.rds.amazonaws.com",
                "DB_PORT": "3306",
                "DB_NAME": "queen_demo",
                "DB_USER": "admin",
                "DB_PASSWORD": "QueenDemo2024!",  # TODO: Use Secrets Manager in production
            },
        )

        # Lambda 2: sql_executor (reference existing Lambda)
        account_id = self.account
        sql_executor_lambda = lambda_.Function.from_function_arn(
            self, "SqlExecutorLambda",
            function_arn=f"arn:aws:lambda:{self.region}:{account_id}:function:queen-sql-executor-lambda",
        )

        # Lambda 3: get_available_kpis (existing function — different naming convention)
        get_available_kpis_lambda = lambda_.Function.from_function_arn(
            self, "GetAvailableKpisLambda",
            function_arn=f"arn:aws:lambda:{self.region}:{account_id}:function:get_available_kpis",
        )

        # ===================================================================
        # AgentCore IAM Role
        # ===================================================================

        agentcore_role = iam.Role(
            self, "AgentCoreRole",
            role_name="QueenAI-AgentCore-Role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="IAM role for QueenAI AgentCore Coordinator Agent",
            inline_policies={
                "LambdaInvoke": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["lambda:InvokeFunction"],
                            resources=[
                                get_kpi_data_lambda.function_arn,
                                sql_executor_lambda.function_arn,
                                get_available_kpis_lambda.function_arn,
                            ],
                        )
                    ]
                ),
                "BedrockModelInvoke": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/*"
                            ],
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["bedrock:Converse"],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/us.amazon.nova-2-lite-v1:0"
                            ],
                        ),
                    ]
                ),
            },
        )

        # Grant Lambda invoke permissions to AgentCore role
        get_kpi_data_lambda.grant_invoke(agentcore_role)
        sql_executor_lambda.grant_invoke(agentcore_role)
        get_available_kpis_lambda.grant_invoke(agentcore_role)

        # ===================================================================
        # AgentCore Agent (L1 CfnResource — L2 not yet available)
        # ===================================================================

        agentcore_agent = CfnResource(
            self, "AgentCoreCoordinator",
            type="AWS::BedrockAgentCore::Agent",
            properties={
                "AgentName": "QueenAI-AgentCore-Coordinator",
                "ModelId": self.node.try_get_context("coordinator_model_id") or "us.anthropic.claude-haiku-4-5",
                "ExecutionRoleArn": agentcore_role.role_arn,
                "Description": "QueenAI coordinator agent — replaces four-agent Bedrock Agents pipeline",
            },
        )

        # ===================================================================
        # CloudFormation Outputs
        # ===================================================================

        CfnOutput(
            self, "AgentCoreAgentId",
            value=agentcore_agent.get_att("AgentId").to_string(),
            description="AgentCore Coordinator Agent ID",
            export_name="AgentCoreAgentId",
        )

        CfnOutput(
            self, "AgentCoreEndpoint",
            value=f"https://bedrock-agentcore.{self.region}.amazonaws.com",
            description="AgentCore runtime endpoint URL",
            export_name="AgentCoreEndpoint",
        )

        CfnOutput(
            self, "GetKpiDataLambdaArn",
            value=get_kpi_data_lambda.function_arn,
            description="Get KPI Data Lambda ARN",
            export_name="GetKpiDataLambdaArn",
        )

        CfnOutput(
            self, "SqlExecutorLambdaArn",
            value=sql_executor_lambda.function_arn,
            description="SQL Executor Lambda ARN",
            export_name="SqlExecutorLambdaArn",
        )

        CfnOutput(
            self, "GetAvailableKpisLambdaArn",
            value=get_available_kpis_lambda.function_arn,
            description="Get Available KPIs Lambda ARN",
            export_name="GetAvailableKpisLambdaArn",
        )
