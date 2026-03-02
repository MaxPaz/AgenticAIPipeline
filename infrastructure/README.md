# Infrastructure

The CDK stack in `cdk/bedrock_agent_stack.py` provisions the Lambda functions and IAM role for the AgentCore agent.

> **Note**: The AgentCore runtime itself is deployed via the `agentcore` CLI, not CDK. See the root README for deployment instructions.

## What the CDK stack deploys

- `queen-get-kpi-data-lambda` — KPI data retrieval (with VPC config)
- `queen-sql-executor-lambda` — SQL query execution (referenced by ARN)
- `queen-get-available-kpis-lambda` — KPI metadata lookup
- `QueenAI-AgentCore-Role` — IAM role for the AgentCore runtime (Lambda invoke + Bedrock model permissions)

## Deploy

```bash
cd infrastructure/cdk
pip install -r requirements.txt
cdk bootstrap  # first time only
cdk deploy
```

Outputs: `AgentCoreAgentId`, `AgentCoreEndpoint`, Lambda ARNs.

## Legacy

The original CDK stack deployed 4 Bedrock Agents. That code is removed; `deploy_agent_collaboration.py` is preserved in `infrastructure/_legacy/` for reference.
