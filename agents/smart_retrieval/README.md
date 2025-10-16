# Smart Retrieval Agent

## Overview

The Smart Retrieval Agent is a Bedrock sub-agent that autonomously retrieves data from KPIs and/or transactional databases. It's the core execution agent that makes intelligent decisions about which data sources to use.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Coordinator Agent (Supervisor)                  │
│                                                              │
│  1. Receives DataSourceDecision from Data Source Agent      │
│  2. Invokes Smart Retrieval Agent                           │
│  3. Gets RetrievalResult with all data                      │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│           Smart Retrieval Agent (Sub-agent)                  │
│                                                              │
│  Autonomous Decision Making:                                │
│  - If KPI IDs provided → call get_kpi_data                  │
│  - Evaluate data sufficiency                                │
│  - If insufficient → generate SQL → call execute_sql_query  │
│  - Retry with refined query if needed (max 3 attempts)      │
│  - Return all collected data                                │
│                                                              │
│  Tools (Action Groups):                                     │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ get_kpi_data     │  │ execute_sql_query│               │
│  │ (Lambda)         │  │ (Lambda)         │               │
│  └──────────────────┘  └──────────────────┘               │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │   XBR Database   │  │ Transactional DB │               │
│  │   (KPI Data)     │  │  (Raw Data)      │               │
│  └──────────────────┘  └──────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Autonomous Tool Selection
The agent decides which tools to call based on:
- DataSourceDecision from Data Source Agent
- Data quality assessment
- Question requirements

### 2. Data Validation
After retrieving KPI data, the agent evaluates:
- Does it fully answer the question?
- Is granular detail needed?
- Are specific filters required?

### 3. Adaptive Retrieval
If data is insufficient:
- Generates SQL query
- Executes against transactional DB
- Retries with refined query if needed (max 3 attempts)

### 4. SQL Generation
The agent has SQL generation logic in its instructions:
- PostgreSQL syntax rules
- Root KPI SQL templates as examples
- Security validation rules
- Best practices for query optimization

## Action Groups (Tools)

### Tool 1: get_kpi_data

**Purpose**: Retrieve pre-calculated KPI data from XBR database

**Parameters**:
- `kpi_ids` (string): Comma-separated KPI IDs (e.g., "17870,17868")
- `date_range` (string): Date range "YYYY-MM to YYYY-MM"
- `frequency` (string): "monthly", "weekly", or "daily"
- `org_id` (string): Organization ID (default: "default")

**Returns**:
```json
{
  "kpi_data": [...],
  "count": 10,
  "kpi_ids": [17870, 17868],
  "date_range": "2024-01 to 2024-12",
  "frequency": "monthly"
}
```

**Lambda**: `lambda/get_kpi_data/lambda_function.py`

### Tool 2: execute_sql_query

**Purpose**: Execute SQL queries against transactional database

**Parameters**:
- `sql_query` (string): SQL SELECT query
- `org_id` (string): Organization ID
- `timeout` (integer): Query timeout in seconds (default: 30)

**Returns**:
```json
{
  "success": true,
  "data": [...],
  "row_count": 25,
  "execution_time_ms": 150,
  "error": null
}
```

**Lambda**: `lambda/sql_executor/lambda_function.py` (already exists)

**Security**:
- Only SELECT queries allowed
- No DDL/DML operations
- Query timeout enforcement
- Org-level data isolation

## Agent Instructions

The Smart Retrieval Agent has comprehensive instructions that include:

1. **Tool Usage Guidelines**
   - When to use get_kpi_data
   - When to use execute_sql_query
   - How to combine both tools

2. **SQL Generation Logic**
   - PostgreSQL syntax rules
   - Root KPI SQL templates
   - JOIN patterns
   - WHERE clause construction
   - Date filtering

3. **Data Validation**
   - Sufficiency checks
   - Quality assessment
   - Completeness verification

4. **Error Handling**
   - Retry logic (max 3 attempts)
   - Query refinement strategies
   - Fallback approaches

5. **Security Rules**
   - Only SELECT queries
   - No dangerous operations
   - Org-level isolation

## Data Structures

### Input: DataSourceDecision
```python
{
  "kpi_ids": [17870, 17868],
  "date_range": "2024-01 to 2024-12",
  "frequency": "monthly",
  "transactional_might_be_needed": false,
  "needs_clarification": false,
  "clarification_question": null,
  "reasoning": "...",
  "confidence": 0.95
}
```

### Output: RetrievalResult
```python
{
  "kpi_data": [...],  # KPI data if retrieved
  "transactional_data": [...],  # Transactional data if retrieved
  "data_sources_used": ["KPI", "Transactional", "Both"],
  "notes": "Explanation of what was retrieved and why",
  "sql_query": "SELECT ...",  # SQL query if used
  "success": true,
  "error_message": null
}
```

## Deployment

### Prerequisites
1. XBR database configured (for KPI data)
2. Transactional database configured
3. SQL Executor Lambda deployed (Task 3)
4. Database credentials in environment variables

### CDK Deployment

The Smart Retrieval Agent is deployed via CDK with:
- Bedrock Agent configuration
- 2 Lambda functions (action groups)
- IAM roles with proper permissions
- OpenAPI schemas for action groups

```bash
cd infrastructure/cdk
cdk deploy
```

### Environment Variables

Add to `.env`:
```
SMART_RETRIEVAL_AGENT_ID=<agent-id>
SMART_RETRIEVAL_AGENT_ALIAS_ID=<alias-id>

# For get_kpi_data Lambda
XBR_DB_HOST=<xbr-host>
XBR_DB_PORT=5432
XBR_DB_NAME=<xbr-db>
XBR_DB_USER=<user>
XBR_DB_PASSWORD=<password>

# For execute_sql_query Lambda (already configured)
DB_HOST=<transactional-host>
DB_PORT=3306
DB_NAME=<transactional-db>
DB_USER=<user>
DB_PASSWORD=<password>
```

## Testing

### Test Autonomous Tool Selection

```python
from agents.smart_retrieval import SmartRetrievalAgent

agent = SmartRetrievalAgent()

# Test 1: KPI-only retrieval
decision = {
    "kpi_ids": [17870],
    "date_range": "2024-01 to 2024-12",
    "frequency": "monthly",
    "transactional_might_be_needed": false
}

result = agent.retrieve_data(decision, "What were sales last year?")
print(f"Data sources used: {result.data_sources_used}")
print(f"KPI data: {len(result.kpi_data)} records")

# Test 2: Transactional retrieval
decision = {
    "kpi_ids": [],
    "date_range": "2024-12 to 2024-12",
    "frequency": "monthly",
    "transactional_might_be_needed": true
}

result = agent.retrieve_data(decision, "Show sales by store in California")
print(f"SQL used: {result.sql_query}")
print(f"Transactional data: {len(result.transactional_data)} records")
```

### Test Data Validation

The agent should:
- ✅ Retrieve KPI data when KPI IDs provided
- ✅ Evaluate if KPI data is sufficient
- ✅ Generate SQL if more detail needed
- ✅ Execute SQL and return results
- ✅ Retry with refined query on failure
- ✅ Return all collected data

## Model Configuration

- **Model**: Claude 3.7 Sonnet
- **Reason**: 
  - Best at following complex instructions
  - Excellent SQL generation capabilities
  - Strong reasoning for autonomous decisions
  - Reliable structured output
- **Cost**: ~$3 input / $15 output per 1M tokens

## Integration with Other Agents

### Workflow

1. **Data Source Agent** analyzes question → Returns DataSourceDecision
2. **Coordinator** invokes **Smart Retrieval Agent** with decision
3. **Smart Retrieval Agent**:
   - Calls get_kpi_data if KPI IDs provided
   - Evaluates data sufficiency
   - Calls execute_sql_query if needed
   - Returns RetrievalResult
4. **Coordinator** invokes **Analysis Agent** with all data
5. **Analysis Agent** generates insights

## Files

```
agents/smart_retrieval/
├── __init__.py                      # Package initialization
├── smart_retrieval_agent.py         # Main agent implementation
├── action_group_schemas.py          # OpenAPI schemas for action groups
├── README.md                        # This file
└── test_smart_retrieval_agent.py    # Test suite (to be created)

lambda/get_kpi_data/
├── lambda_function.py               # get_kpi_data action group
└── requirements.txt                 # Dependencies

lambda/sql_executor/
├── lambda_function.py               # execute_sql_query action group (exists)
└── requirements.txt                 # Dependencies (exists)
```

## Next Steps

1. ✅ Create Smart Retrieval Agent structure
2. ⏭️ Deploy get_kpi_data Lambda function
3. ⏭️ Add Smart Retrieval Agent to CDK stack
4. ⏭️ Configure action groups in CDK
5. ⏭️ Deploy and test
6. ⏭️ Verify autonomous tool selection
7. ⏭️ Test end-to-end workflow

## Troubleshooting

### Agent doesn't call tools
- Check action group configuration in CDK
- Verify Lambda permissions
- Review agent instructions

### SQL generation fails
- Check root KPI templates in instructions
- Verify transactional schema is provided
- Review PostgreSQL syntax rules

### get_kpi_data returns no data
- Verify XBR database connection
- Check KPI IDs are valid
- Verify date range format

### execute_sql_query fails
- Check SQL security validation
- Verify query syntax
- Check database permissions
- Review timeout settings

## Cost Optimization

- Uses Sonnet 3.7 for best quality
- Typical cost per retrieval: $0.02-0.05
- 1,000 retrievals/day: ~$600/month
- Can optimize by caching common queries

## Monitoring

Monitor via CloudWatch:
- Tool invocation frequency (KPI vs SQL)
- SQL query success rate
- Retry attempts
- Data sufficiency rate
- Average retrieval time

```bash
aws logs tail /aws/bedrock/agent/SmartRetrievalAgent --follow
```
