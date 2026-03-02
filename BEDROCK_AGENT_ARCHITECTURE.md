# QueenAI — AgentCore Architecture

## Overview

The system uses **AWS Bedrock AgentCore** with the **Strands Agents SDK** to host three in-process agents as a single managed runtime. This replaced the original 4-agent Bedrock Agents setup which had 40–60 second response times due to inter-agent network overhead.

## Architecture

![AgentCore Architecture](agentcore_architecture_diagram.png)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit UI (ui/app.py)                      │
│  boto3 bedrock-agentcore client → invoke_agent_runtime()         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         AgentCore Runtime: queen_coordinator-agAC6uDNBA          │
│         Region: us-west-2  |  ARM64 container via CodeBuild      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Coordinator Agent  (Haiku 4.5)                          │   │
│  │  agents/coordinator/entrypoint.py                        │   │
│  │                                                          │   │
│  │  Tools:                                                  │   │
│  │  • get_available_kpis → Lambda                           │   │
│  │  • web_search → Nova 2 Lite (nova_grounding)             │   │
│  │  • data_specialist → Data Specialist Agent (in-process)  │   │
│  │  • analysis → Analysis Agent (in-process)                │   │
│  └──────────────┬───────────────────────┬───────────────────┘   │
│                 │                       │                         │
│                 ▼                       ▼                         │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │  Data Specialist     │  │  Analysis Agent (Haiku 4.5)      │ │
│  │  Agent (Sonnet 4.5)  │  │  Pure formatting — no tools      │ │
│  │                      │  │  Returns JSON:                   │ │
│  │  Tools:              │  │  { response, suggested_questions }│ │
│  │  • get_kpi_data      │  └──────────────────────────────────┘ │
│  │  • execute_sql_query │                                        │
│  └──────────┬───────────┘                                        │
└─────────────┼──────────────────────────────────────────────────-─┘
              │ boto3 lambda.invoke (direct JSON payload)
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Lambda Functions                          │
│  queen-get-available-kpis-lambda                                 │
│  queen-get-kpi-data-lambda                                       │
│  queen-sql-executor-lambda                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MySQL RDS Database                            │
│  reddyice_s3_commercial_money  — chain-level KPI aggregates      │
│  reddyice_s3_order_details     — individual order records        │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### AgentCore Runtime
- **Deployed via**: `agentcore launch` (Strands starter toolkit)
- **Container**: ARM64, built by CodeBuild, stored in ECR
- **Entry point**: `agents/coordinator/entrypoint.py`
- **Agent ID**: `queen_coordinator-agAC6uDNBA`
- **Logs**: `/aws/bedrock-agentcore/runtimes/queen_coordinator-agAC6uDNBA-DEFAULT`

### Coordinator Agent
- **Model**: `us.anthropic.claude-haiku-4-5-20251001-v1:0` (cross-region inference profile)
- **Role**: Routes questions, resolves conversation context, calls tools
- **File**: `agents/coordinator/agent.py` + `agents/coordinator/prompts.py`

### Data Specialist Agent
- **Model**: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
- **Role**: KPI planning, SQL generation, data retrieval, retry logic (max 3 attempts)
- **File**: `agents/specialist/agent.py` + `agents/specialist/prompts.py`
- **Invoked as**: a tool by the Coordinator (in-process, no network hop)

### Analysis Agent
- **Model**: `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- **Role**: Formats raw data into markdown response with insights and follow-up questions
- **File**: `agents/analysis/agent.py` + `agents/analysis/prompts.py`
- **No tools** — pure text-in, text-out

### Web Search
- **Implementation**: `agents/coordinator/web_search.py`
- **Model**: `us.amazon.nova-2-lite-v1:0` with `nova_grounding` system tool
- **Replaces**: Old Nova Act browser automation (was 60s, now 1–2s)

### Lambda Functions
All three accept both direct JSON payloads (AgentCore) and legacy Bedrock action group envelope format (backward compatible).

| Function | Purpose |
|---|---|
| `queen-get-available-kpis-lambda` | Returns KPI IDs and definitions for a customer |
| `queen-get-kpi-data-lambda` | Retrieves pre-calculated KPI data from MySQL |
| `queen-sql-executor-lambda` | Executes SELECT queries with security validation |

### Security
- SQL validation: SELECT-only, no forbidden ops, no multi-statement, org_id required
- AgentCore IAM role: `lambda:InvokeFunction` scoped to the three Lambda ARNs only
- Tenant isolation: `org_id` passed through all data queries

## Performance

| Metric | Old (Bedrock Agents) | New (AgentCore) |
|---|---|---|
| Simple KPI query | 40–60s | ~3–5s |
| SQL query | 40–60s | ~5–8s |
| Web search | 60s (Nova Act) | 1–2s (Nova Lite) |
| Agent hops | 4 (network) | 3 (in-process) |
| Model | Sonnet 3.7 only | Haiku 4.5 + Sonnet 4.5 |

## Deployment

```bash
# Deploy / update the agent
source venv/bin/activate
agentcore launch --auto-update-on-conflict

# Invoke directly (CLI smoke test)
agentcore invoke '{"prompt": "Hello"}'

# Tail logs
aws logs tail /aws/bedrock-agentcore/runtimes/queen_coordinator-agAC6uDNBA-DEFAULT \
  --region us-west-2 --since 10m
```

## Legacy Architecture

The original implementation used 4 separate Bedrock Agents with native Agent Collaboration. Each agent invocation added 10–20 seconds of overhead. That code is preserved in `agents/_legacy/` for reference.

```
Old: UI → Bedrock Coordinator → Data Source Agent → Smart Retrieval Agent → Analysis Agent
          (10-20s each hop)      (10-20s)             (10-20s)               (10-20s)
          Total: 40-60s

New: UI → AgentCore Runtime → [Coordinator → Specialist → Analysis] (all in-process)
          Total: 3-8s
```
