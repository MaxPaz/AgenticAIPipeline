# Smart Retrieval Agent Instructions

This file contains the system instructions for the Smart Retrieval Agent in AWS Bedrock.

## Purpose

The Smart Retrieval Agent autonomously retrieves data from available sources (KPIs and/or transactional database). It has 2 Lambda function tools and decides which to use based on the data source decision.

## How to Use

When creating or updating the Smart Retrieval Agent in AWS Bedrock Console:

1. Go to AWS Bedrock Console → Agents
2. Select the Smart Retrieval Agent
3. In the "Instructions" section, copy the content from `instructions.txt`
4. Configure Action Groups (see below)
5. Save and create a new version

## Instructions File

The canonical instructions are in: `instructions.txt`

## Action Groups

This agent requires 2 action groups with Lambda functions:

### 1. GetKpiDataActionGroup
- **Lambda Function**: `get_kpi_data`
- **API Path**: `/get_kpi_data`
- **Method**: POST
- **Parameters**:
  - `kpi_ids` (string, required): Comma-separated KPI IDs
  - `date_range` (string, required): "YYYY-MM to YYYY-MM"
  - `frequency` (string, optional): "monthly", "weekly", or "daily"
  - `org_id` (string, optional): Organization ID

### 2. ExecuteSqlQueryActionGroup
- **Lambda Function**: `execute_sql_query`
- **API Path**: `/execute_sql_query`
- **Method**: POST
- **Parameters**:
  - `sql_query` (string, required): SQL SELECT query
  - `org_id` (string, optional): Organization ID
  - `timeout` (integer, optional): Query timeout in seconds

## Key Capabilities

- Retrieves KPI data using `get_kpi_data` tool
- Executes SQL queries using `execute_sql_query` tool
- Autonomously decides which tool(s) to use
- Handles retries on failures (max 3 attempts)
- Validates data sufficiency
- Combines data from multiple sources when needed

## Output Format

Returns JSON with:
- `kpi_data`: Array of KPI results or null
- `transactional_data`: Array of query results or null
- `data_sources_used`: Array of strings ("KPI", "Transactional", or both)
- `notes`: Explanation of what was retrieved
- `sql_query`: SQL query executed (if any)
- `success`: Boolean
- `error_message`: String or null

## Deployment

See `deploy.sh` for automated deployment script.

## Testing

To test the agent independently:
```bash
python -c "from agents.smart_retrieval.smart_retrieval_agent import SmartRetrievalAgent; agent = SmartRetrievalAgent(); print(agent.retrieve_data({'kpi_ids': [17870], 'date_range': '2024-01 to 2024-12'}, 'What were sales?', 'default'))"
```

## Notes

- This agent requires Lambda functions to be deployed first
- Lambda functions must have proper IAM roles for RDS access
- Action groups must be configured in Bedrock Console
