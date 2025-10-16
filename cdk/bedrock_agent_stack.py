"""
AWS CDK Stack for Bedrock Agents

This stack creates:
- Coordinator Agent (Supervisor) with Claude 3.5 Sonnet
- Data Source Agent (Sub-agent) with Claude 3.5 Haiku
- IAM roles for both agents
- Agent aliases for production
- Agent collaboration configuration
"""

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_bedrock as bedrock,
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    CfnOutput,
    Duration,
    BundlingOptions
)
from constructs import Construct
import json


class BedrockAgentStack(Stack):
    """CDK Stack for Bedrock Coordinator Agent."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Agent configuration
        agent_name = "QueenAI-Coordinator-Agent"
        model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        
        # Create IAM role for Bedrock Agent
        agent_role = iam.Role(
            self, "BedrockAgentRole",
            role_name="QueenAI-Bedrock-Agent-Role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="IAM role for QueenAI Bedrock Coordinator Agent",
            inline_policies={
                "BedrockModelInvocation": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/*"
                            ]
                        )
                    ]
                )
            }
        )

        # Agent instructions
        instructions = self._get_coordinator_instructions()

        # Create Bedrock Agent (will add collaborators after sub-agents are created)
        agent = bedrock.CfnAgent(
            self, "CoordinatorAgent",
            agent_name=agent_name,
            agent_resource_role_arn=agent_role.role_arn,
            foundation_model=model_id,
            instruction=instructions,
            description="Coordinator Agent for QueenAI agentic chat pipeline",
            idle_session_ttl_in_seconds=1800,  # 30 minutes
            # Memory configuration
            memory_configuration=bedrock.CfnAgent.MemoryConfigurationProperty(
                enabled_memory_types=["SESSION_SUMMARY"],
                storage_days=30
            )
        )

        # Agent depends on role
        agent.node.add_dependency(agent_role)

        # Create agent alias
        agent_alias = bedrock.CfnAgentAlias(
            self, "CoordinatorAgentAlias",
            agent_id=agent.attr_agent_id,
            agent_alias_name="prod",
            description="Production alias for Coordinator Agent"
        )

        # ===================================================================
        # Data Source Agent (Sub-agent)
        # ===================================================================
        
        # Create IAM role for Data Source Agent
        data_source_role = iam.Role(
            self, "DataSourceAgentRole",
            role_name="QueenAI-DataSource-Agent-Role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="IAM role for QueenAI Data Source Agent",
            inline_policies={
                "BedrockModelInvocation": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/*"
                            ]
                        )
                    ]
                )
            }
        )

        # Data Source Agent instructions
        data_source_instructions = self._get_data_source_instructions()

        # Create Data Source Agent (using Sonnet 3.7 for better structured output)
        data_source_agent = bedrock.CfnAgent(
            self, "DataSourceAgent",
            agent_name="QueenAI-DataSource-Agent",
            agent_resource_role_arn=data_source_role.role_arn,
            foundation_model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            instruction=data_source_instructions,
            description="Data Source Agent for analyzing questions and determining available data sources",
            idle_session_ttl_in_seconds=1800,
            # No memory needed for this stateless analysis agent
        )

        data_source_agent.node.add_dependency(data_source_role)

        # Create Data Source Agent alias
        data_source_alias = bedrock.CfnAgentAlias(
            self, "DataSourceAgentAlias",
            agent_id=data_source_agent.attr_agent_id,
            agent_alias_name="prod",
            description="Production alias for Data Source Agent"
        )

        # Grant Coordinator Agent permission to invoke Data Source Agent
        agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeAgent"
                ],
                resources=[
                    data_source_agent.attr_agent_arn
                ]
            )
        )

        # ===================================================================
        # Outputs
        # ===================================================================
        
        # Coordinator Agent Outputs
        CfnOutput(
            self, "CoordinatorAgentId",
            value=agent.attr_agent_id,
            description="Coordinator Agent ID",
            export_name="BedrockCoordinatorAgentId"
        )

        CfnOutput(
            self, "CoordinatorAgentAliasId",
            value=agent_alias.attr_agent_alias_id,
            description="Coordinator Agent Alias ID",
            export_name="BedrockCoordinatorAgentAliasId"
        )

        CfnOutput(
            self, "CoordinatorAgentArn",
            value=agent.attr_agent_arn,
            description="Coordinator Agent ARN",
            export_name="BedrockCoordinatorAgentArn"
        )

        # Data Source Agent Outputs
        CfnOutput(
            self, "DataSourceAgentId",
            value=data_source_agent.attr_agent_id,
            description="Data Source Agent ID",
            export_name="BedrockDataSourceAgentId"
        )

        CfnOutput(
            self, "DataSourceAgentAliasId",
            value=data_source_alias.attr_agent_alias_id,
            description="Data Source Agent Alias ID",
            export_name="BedrockDataSourceAgentAliasId"
        )

        CfnOutput(
            self, "DataSourceAgentArn",
            value=data_source_agent.attr_agent_arn,
            description="Data Source Agent ARN",
            export_name="BedrockDataSourceAgentArn"
        )

        # ===================================================================
        # Lambda Functions for Smart Retrieval Agent Action Groups
        # ===================================================================
        
        # Shared Lambda execution role
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            role_name="QueenAI-Lambda-Execution-Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for QueenAI Lambda functions",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole")
            ]
        )

        # Create Lambda Layer for pymysql (shared dependency)
        pymysql_layer = lambda_.LayerVersion(
            self, "PyMySQLLayer",
            code=lambda_.Code.from_asset("../../lambda/layers/pymysql"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="PyMySQL library for database connections"
        )

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
                    ec2.Subnet.from_subnet_id(self, "Subnet2", "subnet-2a64ea01")
                ]
            ),
            security_groups=[
                ec2.SecurityGroup.from_security_group_id(
                    self, "LambdaSecurityGroup",
                    security_group_id="sg-0a6221ae499043e85"
                )
            ],
            allow_public_subnet=True,  # RDS is in public subnet for demo
            environment={
                "DB_HOST": "queen-demo-mysql.c06zxi4g5mx8.us-west-2.rds.amazonaws.com",
                "DB_PORT": "3306",
                "DB_NAME": "queen_demo",
                "DB_USER": "admin",
                "DB_PASSWORD": "QueenDemo2024!"  # TODO: Use Secrets Manager in production
            }
        )

        # Lambda 2: sql_executor (reference existing manually deployed Lambda)
        # Reference existing SQL executor Lambda
        # TODO: Replace with your AWS account ID and Lambda function name
        account_id = self.account  # Uses the account from CDK context
        sql_executor_lambda = lambda_.Function.from_function_arn(
            self, "SqlExecutorLambda",
            function_arn=f"arn:aws:lambda:{self.region}:{account_id}:function:queen-sql-executor-lambda"
        )

        # ===================================================================
        # Smart Retrieval Agent (Sub-agent with 2 Action Groups)
        # ===================================================================
        
        # Create IAM role for Smart Retrieval Agent
        smart_retrieval_role = iam.Role(
            self, "SmartRetrievalAgentRole",
            role_name="QueenAI-SmartRetrieval-Agent-Role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="IAM role for QueenAI Smart Retrieval Agent",
            inline_policies={
                "BedrockModelInvocation": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/*"
                            ]
                        )
                    ]
                ),
                "LambdaInvocation": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["lambda:InvokeFunction"],
                            resources=[
                                get_kpi_data_lambda.function_arn,
                                sql_executor_lambda.function_arn
                            ]
                        )
                    ]
                )
            }
        )

        # Grant Lambda permissions to be invoked by Bedrock
        get_kpi_data_lambda.grant_invoke(iam.ServicePrincipal("bedrock.amazonaws.com"))
        sql_executor_lambda.grant_invoke(iam.ServicePrincipal("bedrock.amazonaws.com"))

        # Smart Retrieval Agent instructions
        smart_retrieval_instructions = self._get_smart_retrieval_instructions()

        # Smart Retrieval Agent instructions
        smart_retrieval_instructions = self._get_smart_retrieval_instructions()

        # Create Smart Retrieval Agent (using Sonnet 3.7 for best SQL generation)
        smart_retrieval_agent = bedrock.CfnAgent(
            self, "SmartRetrievalAgent",
            agent_name="QueenAI-SmartRetrieval-Agent",
            agent_resource_role_arn=smart_retrieval_role.role_arn,
            foundation_model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            instruction=smart_retrieval_instructions,
            description="Smart Retrieval Agent that autonomously retrieves data from KPIs and/or transactional database",
            idle_session_ttl_in_seconds=1800,
            # Action groups will be added after agent creation
        )

        smart_retrieval_agent.node.add_dependency(smart_retrieval_role)
        smart_retrieval_agent.node.add_dependency(get_kpi_data_lambda)
        smart_retrieval_agent.node.add_dependency(sql_executor_lambda)

        # Action Group 1: get_kpi_data
        get_kpi_data_action_group = bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name="GetKpiDataActionGroup",
            description="Retrieves pre-calculated KPI data from sales_metrics table",
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=get_kpi_data_lambda.function_arn
            ),
            api_schema=bedrock.CfnAgent.APISchemaProperty(
                payload=json.dumps(self._get_kpi_data_schema())
            )
        )

        # Action Group 2: execute_sql_query
        execute_sql_action_group = bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name="ExecuteSqlQueryActionGroup",
            description="Executes SQL queries against transactional database",
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=sql_executor_lambda.function_arn
            ),
            api_schema=bedrock.CfnAgent.APISchemaProperty(
                payload=json.dumps(self._get_execute_sql_schema())
            )
        )

        # Note: Action groups need to be added via update after agent creation
        # This is a CDK limitation - we'll document this in deployment steps

        # Create Smart Retrieval Agent alias
        smart_retrieval_alias = bedrock.CfnAgentAlias(
            self, "SmartRetrievalAgentAlias",
            agent_id=smart_retrieval_agent.attr_agent_id,
            agent_alias_name="prod",
            description="Production alias for Smart Retrieval Agent"
        )

        # Grant Coordinator Agent permission to invoke Smart Retrieval Agent
        agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeAgent"],
                resources=[smart_retrieval_agent.attr_agent_arn]
            )
        )

        # ===================================================================
        # Analysis Agent (Sub-agent)
        # ===================================================================
        
        # Create IAM role for Analysis Agent
        analysis_role = iam.Role(
            self, "AnalysisAgentRole",
            role_name="QueenAI-Analysis-Agent-Role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="IAM role for QueenAI Analysis Agent",
            inline_policies={
                "BedrockFullAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["bedrock:*"],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # Analysis Agent instructions
        analysis_instructions = self._get_analysis_instructions()

        # Create Analysis Agent (using Haiku 3.5 for fast, cost-effective insights)
        analysis_agent = bedrock.CfnAgent(
            self, "AnalysisAgent",
            agent_name="QueenAI-Analysis-Agent",
            agent_resource_role_arn=analysis_role.role_arn,
            foundation_model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
            instruction=analysis_instructions,
            description="Analysis Agent for data interpretation and business insights",
            idle_session_ttl_in_seconds=1800,
            # No memory needed for this stateless analysis agent
        )

        analysis_agent.node.add_dependency(analysis_role)

        # Create Analysis Agent alias
        analysis_alias = bedrock.CfnAgentAlias(
            self, "AnalysisAgentAlias",
            agent_id=analysis_agent.attr_agent_id,
            agent_alias_name="prod",
            description="Production alias for Analysis Agent"
        )

        # Grant Coordinator Agent permission to invoke Analysis Agent
        agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeAgent"],
                resources=[analysis_agent.attr_agent_arn]
            )
        )

        # ===================================================================
        # Additional Outputs
        # ===================================================================
        
        # Lambda Outputs
        CfnOutput(
            self, "GetKpiDataLambdaArn",
            value=get_kpi_data_lambda.function_arn,
            description="Get KPI Data Lambda ARN",
            export_name="GetKpiDataLambdaArn"
        )

        CfnOutput(
            self, "SqlExecutorLambdaArn",
            value=sql_executor_lambda.function_arn,
            description="SQL Executor Lambda ARN",
            export_name="SqlExecutorLambdaArn"
        )

        # Smart Retrieval Agent Outputs
        CfnOutput(
            self, "SmartRetrievalAgentId",
            value=smart_retrieval_agent.attr_agent_id,
            description="Smart Retrieval Agent ID",
            export_name="BedrockSmartRetrievalAgentId"
        )

        CfnOutput(
            self, "SmartRetrievalAgentAliasId",
            value=smart_retrieval_alias.attr_agent_alias_id,
            description="Smart Retrieval Agent Alias ID",
            export_name="BedrockSmartRetrievalAgentAliasId"
        )

        CfnOutput(
            self, "SmartRetrievalAgentArn",
            value=smart_retrieval_agent.attr_agent_arn,
            description="Smart Retrieval Agent ARN",
            export_name="BedrockSmartRetrievalAgentArn"
        )

        # Analysis Agent Outputs
        CfnOutput(
            self, "AnalysisAgentId",
            value=analysis_agent.attr_agent_id,
            description="Analysis Agent ID",
            export_name="BedrockAnalysisAgentId"
        )

        CfnOutput(
            self, "AnalysisAgentAliasId",
            value=analysis_alias.attr_agent_alias_id,
            description="Analysis Agent Alias ID",
            export_name="BedrockAnalysisAgentAliasId"
        )

        CfnOutput(
            self, "AnalysisAgentArn",
            value=analysis_agent.attr_agent_arn,
            description="Analysis Agent ARN",
            export_name="BedrockAnalysisAgentArn"
        )

    def _get_coordinator_instructions(self) -> str:
        """Get the coordinator agent instructions."""
        return """You are the Coordinator Agent for QueenAI's agentic chat pipeline.

Your role is to orchestrate the conversation flow and manage specialized agents to answer user questions about business data.

## Your Responsibilities:

1. **Understand User Intent**: Analyze the user's question to determine what they're asking for.

2. **Manage Context**: Use conversation history to understand follow-up questions and maintain context across the conversation.

3. **Orchestrate Agents**: You will coordinate with specialized agents:
   - Data Source Agent: Determines what data sources are available (KPIs vs transactional data)
   - Smart Retrieval Agent: Autonomously retrieves data from KPIs and/or transactional database
   - Analysis Agent: Interprets results and generates business insights

4. **Handle Clarifications**: If the question is ambiguous, ask specific clarifying questions with examples or options.

5. **Provide Progress Updates**: Keep users informed about what you're doing (e.g., "Analyzing your question...", "Retrieving data...", "Generating insights...").

6. **Error Handling**: Handle errors gracefully and provide helpful guidance to users.

## Workflow:

1. Receive user question
2. Extract context from conversation history (you have access to session memory automatically)
3. Determine if clarification is needed - if so, ask and wait for response
4. Invoke Data Source Agent to determine what data sources are available
5. Invoke Smart Retrieval Agent to get data (it will autonomously decide whether to use KPIs, SQL, or both)
6. Invoke Analysis Agent to interpret results and generate insights
7. Generate 2-4 relevant follow-up question suggestions
8. Provide the final response with insights and suggestions

## Guidelines:

- Be conversational, helpful, and professional
- Provide progress updates for operations that take time
- Always validate that the answer actually addresses the user's question
- If data is insufficient, explain what's missing and suggest alternatives
- Cite data sources in your responses (e.g., "Based on KPI data..." or "From transactional records...")
- Format numbers appropriately:
  - Currency: $1,234.56
  - Percentages: 45.2%
  - Large numbers: 1,234,567
  - Dates: Convert "2025-M1" to "January 2025"
- If you encounter errors, explain them in user-friendly terms without technical jargon
- When suggesting follow-up questions, make them specific and actionable

## Context Awareness:

You have access to conversation history through session memory. Use this to:
- Understand references to previous questions (e.g., "What about last month?" refers to a date range mentioned earlier)
- Remember customer names, KPIs, and filters from earlier in the conversation
- Provide continuity across multiple turns

## Example Interactions:

User: "What were our sales last month?"
You: "Let me retrieve the sales data for last month. [invoke agents] Based on our KPI data, total sales for December 2024 were $2.5M, up 12% from November. Would you like to see this broken down by region or product category?"

User: "Show me by region"
You: [remembers context about sales and December 2024] "Here's the regional breakdown for December 2024 sales: [data]. The West region led with $1.2M. Would you like to drill down into specific stores or see trends over time?"
"""

    def _get_data_source_instructions(self) -> str:
        """Get the data source agent instructions."""
        return """You are the Data Source Agent for QueenAI's agentic chat pipeline.

Your role is to analyze user questions and determine what data sources are AVAILABLE to answer them.

## Your Responsibilities:

1. **Analyze the Question**: Understand what the user is asking for.

2. **Match Against KPI Metadata**: Determine if pre-calculated KPIs exist that could answer this question.

3. **Assess Transactional Need**: Determine if transactional data might be needed for more detailed analysis.

4. **Select Date Range and Frequency**: Based on the question, determine appropriate date range and frequency.

5. **Request Clarification**: If the question is ambiguous, identify what needs clarification.

## Important: You are a Strategic Planner, NOT an Executor

- You DO NOT retrieve data
- You DO NOT execute queries
- You ONLY analyze and recommend what data sources are available
- The Smart Retrieval Agent will handle actual data retrieval

## Decision Criteria:

### When KPIs Are Available:
- The question asks for metrics that match KPI definitions
- The question can be answered with aggregated data
- Examples: "total sales", "average revenue", "customer count"

### When Transactional Data Might Be Needed:
- The question requires store-level or product-level detail
- The question needs specific filters (e.g., "stores in California")
- The question requires custom calculations not in KPIs
- The question asks for granular data (e.g., "list of transactions")

### When Clarification Is Needed:
- Date range is ambiguous (e.g., "recently", "last period")
- Customer/chain name is unclear
- Multiple interpretations are possible
- Frequency is not specified (monthly vs weekly vs daily)

## Input Format:

You will receive a JSON object with:
{
  "question": "user's question",
  "context": {
    "date_ranges": ["previously mentioned dates"],
    "customers": ["previously mentioned customers"],
    "kpis_mentioned": [previously mentioned KPI IDs],
    "filters": {}
  },
  "kpi_metadata": [list of available KPIs with definitions],
  "transactional_schema": [list of available tables and columns]
}

## Output Format:

You must return ONLY a valid JSON object. Do not include any text before or after the JSON.

Return this structure:
{
  "kpi_ids": [list of KPI IDs that match, or empty list],
  "date_range": "YYYY-MM to YYYY-MM",
  "frequency": "monthly|weekly|daily",
  "transactional_might_be_needed": true|false,
  "needs_clarification": true|false,
  "clarification_question": "specific question to ask user, or null",
  "reasoning": "explanation of your decision",
  "confidence": 0.0 to 1.0
}

## Examples:

### Example 1: Simple KPI Question
Input: {"question": "What were our total sales last month?"}
Output:
{
  "kpi_ids": [1, 2],
  "date_range": "2024-12 to 2024-12",
  "frequency": "monthly",
  "transactional_might_be_needed": false,
  "needs_clarification": false,
  "clarification_question": null,
  "reasoning": "Question asks for total sales which is available as KPIs. Date range is clear (last month).",
  "confidence": 0.95
}

### Example 2: Transactional Detail Needed
Input: {"question": "Show me sales by store in California"}
Output:
{
  "kpi_ids": [],
  "date_range": "2024-12 to 2024-12",
  "frequency": "monthly",
  "transactional_might_be_needed": true,
  "needs_clarification": false,
  "clarification_question": null,
  "reasoning": "Question requires store-level detail with geographic filter. This needs transactional data.",
  "confidence": 0.90
}

### Example 3: Ambiguous Date
Input: {"question": "What were sales recently?"}
Output:
{
  "kpi_ids": [1],
  "date_range": "",
  "frequency": "monthly",
  "transactional_might_be_needed": false,
  "needs_clarification": true,
  "clarification_question": "What time period would you like to see? For example: last month, last quarter, or last year?",
  "reasoning": "The term 'recently' is ambiguous. Need to clarify the specific date range.",
  "confidence": 0.70
}

## Guidelines:

- CRITICAL: Return ONLY the JSON object, no other text
- Always return valid JSON
- Be specific in your reasoning
- When in doubt, ask for clarification
- Consider conversation context when interpreting questions
- Match KPI names and definitions carefully

IMPORTANT: Your entire response must be a single valid JSON object. Do not add explanations, greetings, or any other text outside the JSON.
"""

    def _get_smart_retrieval_instructions(self) -> str:
        """Get the smart retrieval agent instructions."""
        return """You are the Smart Retrieval Agent for QueenAI's agentic chat pipeline.

Your role is to autonomously retrieve data from available sources and validate sufficiency.

## Your Responsibilities:

1. **Retrieve KPI Data**: If KPI IDs are provided, call get_kpi_data to retrieve pre-calculated metrics
2. **Evaluate Sufficiency**: Analyze if the retrieved data fully answers the user's question
3. **Generate SQL if Needed**: If data is insufficient, generate SQL queries for transactional data
4. **Execute SQL**: Call execute_sql_query to get detailed data
5. **Retry on Failure**: If SQL fails, analyze error and retry with refined query (max 3 attempts)
6. **Return All Data**: Return all collected data (KPI and/or transactional)

## Available Tools:

### Tool 1: get_kpi_data
Retrieves pre-calculated KPI data from sales_metrics table.

Parameters:
- kpi_ids: Comma-separated KPI IDs (e.g., "17870,17868")
- date_range: Date range "YYYY-MM to YYYY-MM"
- frequency: "monthly", "weekly", or "daily"
- org_id: Organization ID

Returns: KPI data with revenue, orders_count, avg_order_value, new_customers

### Tool 2: execute_sql_query
Executes SQL queries against transactional database.

Parameters:
- sql_query: SQL SELECT query
- org_id: Organization ID
- timeout: Query timeout in seconds (default: 30)

Returns: Query results as array of objects

## Decision Logic:

### When to use get_kpi_data:
- KPI IDs are provided in the input
- Question asks for aggregated metrics (revenue, orders, averages)
- Pre-calculated data is sufficient

### When to use execute_sql_query:
- Need store-level or product-level detail
- Need specific filters (e.g., "stores in California")
- Need custom calculations not in KPIs
- KPI data is insufficient

### When to use BOTH:
- Start with KPIs for overview
- Then get transactional data for details
- Combine both for comprehensive answer

## SQL Generation Rules (PostgreSQL/MySQL):

### Available Tables:
- organizations (org_id, org_name, industry)
- users (user_id, org_id, email, full_name, role)
- products (product_id, org_id, product_name, category, price)
- orders (order_id, org_id, user_id, product_id, quantity, total_amount, order_date, status)
- sales_metrics (metric_id, org_id, metric_date, revenue, orders_count, avg_order_value, new_customers)

### SQL Best Practices:
1. Always include org_id filter for data isolation
2. Use proper JOINs (INNER JOIN, LEFT JOIN)
3. Use WHERE clauses for filtering
4. Use GROUP BY for aggregations
5. Use ORDER BY for sorting
6. Use LIMIT to prevent large result sets
7. Format dates as 'YYYY-MM-DD'

### Example SQL Queries:

**Sales by product:**
```sql
SELECT p.product_name, SUM(o.total_amount) as total_revenue, COUNT(*) as order_count
FROM orders o
JOIN products p ON o.product_id = p.product_id
WHERE o.org_id = 'org_001' AND o.order_date >= '2024-01-01'
GROUP BY p.product_id, p.product_name
ORDER BY total_revenue DESC
LIMIT 10
```

**Recent orders:**
```sql
SELECT o.order_id, u.full_name, p.product_name, o.total_amount, o.order_date
FROM orders o
JOIN users u ON o.user_id = u.user_id
JOIN products p ON o.product_id = p.product_id
WHERE o.org_id = 'org_001'
ORDER BY o.order_date DESC
LIMIT 20
```

## Security Rules:

- ONLY SELECT queries allowed
- NO INSERT, UPDATE, DELETE, DROP, ALTER, CREATE
- NO multiple statements (no semicolons except at end)
- Always include org_id filter
- Use parameterized values (no SQL injection)

## Error Handling:

If SQL execution fails:
1. Analyze the error message
2. Identify the issue (syntax, missing table, invalid column, etc.)
3. Generate a refined query
4. Retry (max 3 attempts)
5. If all attempts fail, return error with explanation

## Output Format:

Return a JSON object with:
```json
{
  "kpi_data": [...],  // KPI data if retrieved
  "transactional_data": [...],  // Transactional data if retrieved
  "data_sources_used": ["KPI", "Transactional", "Both"],
  "notes": "Explanation of what was retrieved and why",
  "sql_query": "SELECT ...",  // SQL query if used
  "success": true,
  "error_message": null
}
```

## Example Workflow:

**Input:**
```json
{
  "question": "What were sales last month?",
  "data_source_decision": {
    "kpi_ids": [17870],
    "date_range": "2024-12 to 2024-12",
    "frequency": "monthly",
    "transactional_might_be_needed": false
  },
  "org_id": "org_001"
}
```

**Actions:**
1. Call get_kpi_data with kpi_ids=[17870], date_range="2024-12 to 2024-12"
2. Receive KPI data with revenue metrics
3. Evaluate: Data is sufficient (has revenue for December)
4. Return result with KPI data

**Output:**
```json
{
  "kpi_data": [{...}],
  "transactional_data": null,
  "data_sources_used": ["KPI"],
  "notes": "Retrieved revenue data from KPIs for December 2024",
  "sql_query": null,
  "success": true,
  "error_message": null
}
```

## Guidelines:

- Always try KPIs first if KPI IDs provided
- Evaluate data quality before deciding to query transactional DB
- Generate efficient SQL queries
- Handle errors gracefully with retries
- Provide clear explanations in notes
- Return all collected data
"""

    def _get_analysis_instructions(self) -> str:
        """Get the analysis agent instructions."""
        return """You are the Analysis Agent for QueenAI's agentic chat pipeline.

Your role is to interpret query results and generate business-aware insights.

## Your Responsibilities:

1. **Analyze Data**: Interpret KPI and/or transactional data to answer the user's question
2. **Format Data**: Apply proper formatting for currency, percentages, dates, and numbers
3. **Generate Insights**: Provide business-aware insights and key findings
4. **Create Visualizations**: Generate markdown tables for data presentation
5. **Suggest Questions**: Recommend 2-4 relevant follow-up questions
6. **Quality Checks**: Identify and note any data quality issues

## Data Formatting Rules:

### Currency:
- Format: $1,234.56
- Always include $ symbol
- Use comma separators for thousands
- Show 2 decimal places

### Percentages:
- Format: 45.2%
- Show 1 decimal place
- Include % symbol

### Large Numbers:
- Format: 1,234,567
- Use comma separators for thousands

### Dates:
- Convert "2025-M1" to "January 2025"
- Convert "2025-01" to "January 2025"
- Use full month names

## Markdown Table Generation:

Create tables with proper alignment:
```markdown
| Metric | Value | Change |
|--------|------:|-------:|
| Revenue | $1.2M | +12% |
| Orders | 5,432 | +8% |
```

## Insight Generation:

Generate 3-5 key insights that:
- Highlight important trends
- Compare values (e.g., "up 12% from last month")
- Identify outliers or anomalies
- Provide business context
- Are specific and actionable

## Follow-up Question Suggestions:

Generate 2-4 questions that:
- Explore different dimensions (time, geography, product, customer)
- Drill down into details
- Compare segments
- Investigate trends
- Are specific and actionable

## Output Format:

Return a JSON object:
```json
{
  "narrative": "Natural language explanation of the results",
  "formatted_data": "Markdown tables and formatted data",
  "key_insights": [
    "Insight 1",
    "Insight 2",
    "Insight 3"
  ],
  "data_quality_notes": [
    "Note about data quality if any"
  ],
  "suggested_questions": [
    "Follow-up question 1",
    "Follow-up question 2",
    "Follow-up question 3"
  ],
  "success": true,
  "error_message": null
}
```

## Guidelines:

- Always format numbers according to the rules above
- Generate specific, actionable insights
- Create clean, readable markdown tables
- Suggest relevant follow-up questions
- Note any data quality issues
- Be concise but informative
- Use business-friendly language
- Avoid technical jargon

IMPORTANT: Return ONLY a valid JSON object. Do not include explanations outside the JSON.
"""

    def _get_kpi_data_schema(self) -> dict:
        """Get OpenAPI schema for get_kpi_data action group."""
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "Get KPI Data API",
                "version": "1.0.0",
                "description": "Retrieves pre-calculated KPI data from XBR database with intelligent mapping, formatting, and validation"
            },
            "paths": {
                "/get_kpi_data": {
                    "post": {
                        "summary": "Get KPI Data",
                        "description": "Retrieves pre-calculated KPI data for specified KPI IDs, date range, and frequency. Maps KPI IDs to database columns, formats results with proper units (currency, percentages, numbers), and validates data quality.",
                        "operationId": "getKpiData",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "kpi_ids": {
                                                "type": "string",
                                                "description": "Comma-separated list of KPI IDs to retrieve. Examples: '17870' (Customer A Revenue), '17890' (Customer B Revenue), '17866' (Customer A Volume), '17860' (Customer A OOS%)"
                                            },
                                            "date_range": {
                                                "type": "string",
                                                "description": "Date range in format 'YYYY-MM to YYYY-MM' (e.g., '2024-01 to 2024-12'). Supports partial dates."
                                            },
                                            "frequency": {
                                                "type": "string",
                                                "enum": ["monthly", "weekly", "daily"],
                                                "description": "Data frequency: monthly, weekly, or daily",
                                                "default": "monthly"
                                            },
                                            "org_id": {
                                                "type": "string",
                                                "description": "Organization ID for data isolation",
                                                "default": "default"
                                            }
                                        },
                                        "required": ["kpi_ids", "date_range"]
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Successfully retrieved KPI data",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "kpi_data": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "description": "KPI data record with raw values and formatted strings (e.g., cy_revenue_formatted: '$1,234.56')"
                                                    },
                                                    "description": "Array of formatted KPI data records with both raw and formatted values"
                                                },
                                                "count": {
                                                    "type": "integer",
                                                    "description": "Number of records returned"
                                                },
                                                "kpi_ids": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "integer"
                                                    },
                                                    "description": "KPI IDs that were queried"
                                                },
                                                "kpi_info": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "kpi_id": {"type": "integer"},
                                                            "column": {"type": "string"},
                                                            "name": {"type": "string"},
                                                            "unit": {"type": "string"},
                                                            "chain": {"type": "string"}
                                                        }
                                                    },
                                                    "description": "Metadata about the KPIs that were retrieved"
                                                },
                                                "date_range": {
                                                    "type": "string",
                                                    "description": "Date range that was queried"
                                                },
                                                "frequency": {
                                                    "type": "string",
                                                    "description": "Frequency that was used"
                                                },
                                                "data_quality": {
                                                    "type": "object",
                                                    "properties": {
                                                        "valid": {"type": "boolean"},
                                                        "issues": {"type": "array", "items": {"type": "string"}},
                                                        "warnings": {"type": "array", "items": {"type": "string"}},
                                                        "row_count": {"type": "integer"}
                                                    },
                                                    "description": "Data quality validation results"
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "Bad request - invalid parameters"
                            },
                            "500": {
                                "description": "Internal server error"
                            }
                        }
                    }
                }
            }
        }

    def _get_execute_sql_schema(self) -> dict:
        """Get OpenAPI schema for execute_sql_query action group."""
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "Execute SQL Query API",
                "version": "1.0.0",
                "description": "Executes SQL queries against transactional database"
            },
            "paths": {
                "/execute_sql_query": {
                    "post": {
                        "summary": "Execute SQL Query",
                        "description": "Executes a SQL query with security validation",
                        "operationId": "executeSqlQuery",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "sql_query": {
                                                "type": "string",
                                                "description": "SQL query to execute (SELECT only)"
                                            },
                                            "org_id": {
                                                "type": "string",
                                                "description": "Organization ID",
                                                "default": "org_001"
                                            },
                                            "timeout": {
                                                "type": "integer",
                                                "description": "Query timeout in seconds",
                                                "default": 30
                                            }
                                        },
                                        "required": ["sql_query"]
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Successfully executed query",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "success": {"type": "boolean"},
                                                "data": {
                                                    "type": "array",
                                                    "items": {"type": "object"}
                                                },
                                                "row_count": {"type": "integer"},
                                                "execution_time_ms": {"type": "number"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
