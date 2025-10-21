# QueenAI Agentic Chat Pipeline - Bedrock Agent Architecture

## Overview

This project implements a **4-agent architecture** using **AWS Bedrock Agents** for autonomous data retrieval and analysis. The agents are configured and orchestrated entirely within AWS Bedrock - **no Python orchestration code is used**.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Streamlit UI                              │
│                     (ui/app.py)                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ bedrock_client.invoke_agent()
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Bedrock Coordinator Agent                      │
│                  (Configured in Bedrock Console)                 │
│                                                                   │
│  - Orchestrates workflow                                         │
│  - Manages conversation context                                  │
│  - Routes to specialized agents                                  │
└──────┬──────────────────┬──────────────────┬────────────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Data Source │  │ Smart Retrieval  │  │ Analysis Agent   │
│   Agent     │  │     Agent        │  │                  │
│             │  │                  │  │                  │
│ Determines  │  │ Retrieves data   │  │ Generates        │
│ available   │  │ autonomously     │  │ insights         │
│ data sources│  │                  │  │                  │
└─────────────┘  └────────┬─────────┘  └──────────────────┘
                          │
                          │ Calls Lambda Functions
                          ▼
                 ┌─────────────────────┐
                 │  Lambda Functions   │
                 │                     │
                 │  - get_kpi_data     │
                 │  - execute_sql_query│
                 └──────────┬──────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  MySQL RDS      │
                   │  Database       │
                   └─────────────────┘
```

## Key Components

### 1. Streamlit UI (`ui/app.py`)
- **Purpose**: User interface for chat interactions
- **Key Function**: Calls `bedrock_client.invoke_agent()` directly
- **No Python Orchestration**: All agent coordination happens in Bedrock

### 2. Bedrock Coordinator Agent
- **Configured In**: AWS Bedrock Console
- **Model**: Claude 3.7 Sonnet
- **Responsibilities**:
  - Receives user questions
  - Manages conversation context
  - Routes to specialized agents via Agent Collaboration
  - Returns final response to user

### 3. Bedrock Data Source Agent
- **Configured In**: AWS Bedrock Console
- **Model**: Claude 3.7 Sonnet
- **Responsibilities**:
  - Analyzes user questions
  - Determines available data sources (KPIs vs transactional)
  - Returns data source recommendations

### 4. Bedrock Smart Retrieval Agent
- **Configured In**: AWS Bedrock Console
- **Model**: Claude 3.7 Sonnet
- **Action Groups**:
  - `get_kpi_data` → Lambda function
  - `execute_sql_query` → Lambda function
- **Responsibilities**:
  - Autonomously retrieves data
  - Decides whether to use KPIs, SQL, or both
  - Handles retries and error recovery

### 5. Bedrock Analysis Agent
- **Configured In**: AWS Bedrock Console
- **Model**: Claude 3.7 Sonnet (recommend switching to Haiku)
- **Responsibilities**:
  - Interprets query results
  - Generates business insights
  - Formats data (currency, percentages, dates)
  - Creates markdown tables
  - Suggests follow-up questions

### 6. Lambda Functions
- **get_kpi_data**: Retrieves pre-calculated KPI data from MySQL
- **execute_sql_query**: Executes SQL queries against MySQL with security validation

### 7. MySQL RDS Database
- **Tables**:
  - `reddyice_s3_commercial_money`: Pre-calculated KPI data
  - `reddyice_s3_order_details`: Transactional order data

## Important Notes

### ⚠️ No Python Orchestration
- The Python files in `agents/` directory (e.g., `data_source_agent.py`, `analysis_agent.py`) are **NOT used** in the actual execution
- They exist only as **reference implementations** and **documentation**
- **All orchestration happens in Bedrock Console** via Agent Collaboration

## How to Implement This in Your AWS Account

### Step 1: Create Lambda Functions
1. Deploy `lambda/get_kpi_data/` to AWS Lambda
2. Deploy `lambda/sql_executor/` to AWS Lambda
3. Configure environment variables (DB_HOST, DB_USER, etc.)
4. Attach IAM roles with RDS access

### Step 2: Create Bedrock Agents

#### Coordinator Agent:
```
Name: QueenAI-Coordinator-Agent
Model: Claude 3.7 Sonnet
Instructions: [Copy from agents/coordinator_agent.py docstring]
Agent Collaboration: Enable
  - DataSourceAgent
  - SmartRetrievalAgent
  - AnalysisAgent
```

#### Data Source Agent:
```
Name: QueenAI-DataSource-Agent
Model: Claude 3.7 Sonnet
Instructions: [Copy from agents/data_source/data_source_agent.py docstring]
```

#### Smart Retrieval Agent:
```
Name: QueenAI-SmartRetrieval-Agent
Model: Claude 3.7 Sonnet
Instructions: [Copy from agents/smart_retrieval/smart_retrieval_agent.py docstring]
Action Groups:
  - GetKpiDataActionGroup → Lambda: get_kpi_data
  - ExecuteSqlQueryActionGroup → Lambda: execute_sql_query
```

#### Analysis Agent:
```
Name: QueenAI-Analysis-Agent
Model: Claude 3.5 Haiku (recommended for performance)
Instructions: [Copy from agents/analysis/analysis_agent.py docstring]
Return to User: Yes (for direct response optimization)
```

### Step 3: Configure Agent Collaboration

In Coordinator Agent:
1. Add "Agent Collaboration" associations
2. Link to DataSourceAgent, SmartRetrievalAgent, AnalysisAgent
3. Configure collaboration prompts

### Step 4: Deploy Streamlit UI
1. Update `ui/app.py` with your Bedrock Agent IDs
2. Set environment variables:
   ```
   BEDROCK_AGENT_ID=<your-coordinator-agent-id>
   BEDROCK_AGENT_ALIAS_ID=<your-agent-alias-id>
   AWS_REGION=us-west-2
   ```
3. Deploy to your hosting platform

### Step 5: Test End-to-End
1. Open Streamlit UI
2. Ask: "What were Customer A sales in 2023?"
3. Verify agents are invoked in correct order
4. Check CloudWatch logs for latency metrics

## Performance Optimization

See `OPTIMIZATION_RECOMMENDATIONS.md` for detailed performance tuning guidance.

**Key Optimizations:**
1. Switch Analysis Agent to Claude 3.5 Haiku (3-5x faster)
2. Enable direct response from Analysis Agent (saves 15-17s)
3. Enable prompt caching (saves 2-3s per invocation)

**Expected Results:**
- Before: 40-60 seconds per complex query
- After: 15-20 seconds per complex query

## Monitoring

### CloudWatch Logs
- Log Group: `BedrockLogging`
- Metrics to track:
  - `latencyMs` per agent
  - `inputTokens` and `outputTokens`
  - Error rates

### Example Log Query:
```bash
aws logs tail BedrockLogging --since 20m --region us-west-2 --format short | grep "latencyMs"
```

## Cost Estimation

**Per Query (Current - All Sonnet):**
- Input: ~14K tokens × $0.003/1K = $0.042
- Output: ~1.5K tokens × $0.015/1K = $0.023
- **Total**: ~$0.065 per query

**Per Query (Optimized - Haiku for Analysis):**
- **Total**: ~$0.045 per query
- **Savings**: 30% cost reduction

## Troubleshooting

### Issue: Agents not collaborating
- **Solution**: Check Agent Collaboration configuration in Bedrock Console
- Verify agent aliases are correct
- Check IAM permissions for agent-to-agent communication

### Issue: Lambda timeouts
- **Solution**: Increase Lambda timeout to 60 seconds
- Optimize SQL queries
- Add database connection pooling

### Issue: High latency
- **Solution**: See `OPTIMIZATION_RECOMMENDATIONS.md`
- Switch to Haiku for Analysis Agent
- Enable prompt caching
- Enable direct response from Analysis Agent

## Support

For questions or issues:
1. Check CloudWatch logs: `BedrockLogging`
2. Review agent configurations in Bedrock Console
3. Test Lambda functions independently
4. Verify database connectivity

