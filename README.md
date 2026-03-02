# QueenAI Agentic Chat Pipeline

A conversational AI system for natural language querying of business KPI and transactional data, built on **AWS Bedrock AgentCore** with the **Strands Agents SDK**.

## Architecture

One AgentCore runtime hosts three Strands agents running in-process using the **Graph multi-agent pattern**:

![Architecture Diagram](agentcore_architecture_diagram.png)

```
User → Streamlit UI
  → invoke_agent_runtime → AgentCore Runtime (queen_coordinator)
      Router Agent (Haiku 4.5) — classifies intent in 1 LLM turn
        ↓ DATA_QUERY          ↓ WEB_QUERY         ↓ CONVERSATIONAL
      [Strands Graph]        [Strands Graph]      direct response
      data_specialist         web_search
           ↓                      ↓
        analysis              analysis
           ↓                      ↓
      JSON response ←────────────┘
  ← { response, suggested_questions }
```

All three agents run in the same container — no network hops between them. This replaces the old 4-agent Bedrock Agents setup that took 40–60 seconds per query. Current latency: **12–20 seconds** depending on query complexity.

### Why Graph?

The previous V1 architecture used the **agent-as-tool** pattern: the coordinator LLM decided which tools to call across 2–3 turns (~7s each = 14–21s overhead). V2 uses **Strands GraphBuilder** to wire the pipeline deterministically:

- **Router** classifies intent in a single LLM turn (~1.5s)
- **Graph** routes to the right nodes without further LLM decisions
- Each node (data_specialist, analysis) runs once, in order

Strands also supports **Swarm** (self-organizing agents that hand off to each other) and **A2A** (Agent-to-Agent protocol for cross-service agent calls). Graph was chosen here because the pipeline is deterministic — the path is always the same regardless of the question.

## Project Structure

```
.
├── agents/
│   └── coordinator/            # All agents inline in one container
│       ├── entrypoint.py       # AgentCore app — deployed to AWS (V2 Graph)
│       ├── entrypoint.STABLE.py    # Original stable backup
│       ├── entrypoint.STABLE_2.py  # V1 agent-as-tool backup
│       ├── entrypoint.V2.py    # Current V2 (same as entrypoint.py)
│       └── web_search.py       # Nova 2 Lite web search helper
├── lambda/
│   ├── get_available_kpis/     # Returns KPI metadata for a customer
│   ├── get_kpi_data/           # Retrieves aggregated KPI data from MySQL
│   └── sql_executor/           # Executes SELECT queries against MySQL
├── infrastructure/
│   └── cdk/
│       └── bedrock_agent_stack.py  # CDK stack (Lambda + AgentCore IAM)
├── ui/
│   └── app.py                  # Streamlit chat interface
├── .bedrock_agentcore.yaml     # AgentCore CLI config (includes memory config)
└── .env.example                # Environment variable template
```

## Quick Start

### Prerequisites

- Python 3.10+
- AWS account with Bedrock access (us-west-2)
- AWS CLI configured (`aws configure`)
- Virtual environment: `source venv/bin/activate`

### Run the UI

```bash
source venv/bin/activate
python3 -m streamlit run ui/app.py
```

Open `http://localhost:8501/?user=yourname` — the `?user=` param sets your identity for memory persistence. Add `?chat=1` (or 2, 3) to switch between isolated conversation sessions for the same user.

Requires `.env` with:
```
AGENTCORE_AGENT_ID=queen_coordinator-agAC6uDNBA
AWS_REGION=us-west-2
AWS_ACCOUNT_ID=<your-account-id>   # optional, avoids STS call on startup
```

### Redeploy the Agent

```bash
source venv/bin/activate
agentcore launch --auto-update-on-conflict
```

To roll back to the previous stable version:
```bash
cp agents/coordinator/entrypoint.STABLE_2.py agents/coordinator/entrypoint.py
agentcore launch --auto-update-on-conflict
```

## Environment Variables

```bash
# Required — AgentCore
AGENTCORE_AGENT_ID=queen_coordinator-agAC6uDNBA
AWS_REGION=us-west-2
AWS_ACCOUNT_ID=<your-account-id>   # optional

# Required — Database (consumed by Lambda functions)
# The Lambda functions connect to a MySQL database to retrieve KPI and
# transactional data. Set these in the Lambda environment variables or
# via AWS Secrets Manager.
DB_HOST=<rds-endpoint>
DB_PORT=3306
DB_NAME=<database-name>
DB_USER=<username>
DB_PASSWORD=<password>

# Optional — AgentCore Memory
AGENTCORE_MEMORY_ID=queen_coordinator_mem-Bjfth3HKgJ
```

## Database

The three Lambda functions (`get_available_kpis`, `get_kpi_data`, `sql_executor`) connect to a MySQL database to retrieve business data. You need to provision a MySQL-compatible database (e.g. Amazon RDS) and configure the connection details in the Lambda environment variables listed above.

The Lambdas require network access to the database. If the database is in a VPC, configure the Lambda VPC settings accordingly.

## AgentCore Memory

The pipeline uses **AgentCore Memory (STM_ONLY)** to persist conversation history across page refreshes and sessions. Memory is scoped per user (`actor_id`) and per conversation (`session_id`).

### How it works

- `?user=yourname` in the URL → `actor_id = "yourname"`
- `?chat=1` (or 2, 3) → `session_id = "yourname_chat_1_<hash>"`
- Each conversation slot has isolated memory
- Page refresh restores the same session (stable session ID)
- "New Conversation" cycles to the next slot (1→2→3→1)

### Provisioning memory

Memory is provisioned via the AgentCore CLI and stored in `.bedrock_agentcore.yaml`:

```bash
agentcore configure   # follow prompts to enable STM memory
agentcore launch      # deploys agent with memory attached
```

The memory resource (`queen_coordinator_mem-Bjfth3HKgJ`) is created once and reused across deployments. To provision in a new account, run `agentcore configure` and select STM_ONLY mode.

Alternatively, create the memory resource via AWS CLI:
```bash
aws bedrock-agentcore create-memory \
  --name queen_coordinator_mem \
  --memory-configuration '{"sessionSummaryConfiguration": {"maxTokens": 1024}}' \
  --region us-west-2
```

Then add the memory ID to `.bedrock_agentcore.yaml` under `memory.memory_id`.

## Deployed Resources

| Resource | ID / Name |
|---|---|
| AgentCore Runtime | `queen_coordinator-agAC6uDNBA` |
| AgentCore Memory | `queen_coordinator_mem-Bjfth3HKgJ` |
| Lambda: get_available_kpis | `get_available_kpis` |
| Lambda: get_kpi_data | `queen-get-kpi-data-lambda` |
| Lambda: sql_executor | `queen-sql-executor-lambda` |
| CloudWatch Logs | `/aws/bedrock-agentcore/runtimes/queen_coordinator-agAC6uDNBA-DEFAULT` |

## Example Queries

- "What were total sales for Q2 2024?"
- "Show me out-of-stock rates for all customers this month"
- "Compare January 2025 revenue to January 2024"
- "What's the latest news about [company]?" (requires Web Search toggle ON)

## Legacy

The original 4-agent Bedrock Agents implementation (40–60s latency) is preserved in `agents/_legacy/` for reference. The V1 agent-as-tool entrypoint is preserved as `entrypoint.STABLE_2.py`.
