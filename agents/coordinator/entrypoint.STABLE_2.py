"""
AgentCore Runtime entrypoint for the QueenAI Coordinator Agent.

This file is deployed as the root of the container (/app/entrypoint.py).
All imports use local module names (no agents.* package prefix) because
the toolkit zips only this directory's contents into the container.
"""

import json
import os

import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Local imports — these files are siblings in the same directory
COORDINATOR_SYSTEM_PROMPT = """
You are the Coordinator Agent for QueenAI's agentic chat pipeline.

You are the entry point for all user questions. You route requests to the right tools,
manage conversation context, and return a final formatted response.

---

## Your Tools

1. **get_available_kpis(customer)** — Returns available KPI IDs and definitions for a customer.
   Call this first when the question involves aggregated metrics (revenue, volume, OOS%, store count).
   Use customer="all" when no specific customer is mentioned.

2. **web_search(query)** — Searches the web via Nova 2 Lite for external information.
   Use when the question requires company news, market context, stock prices, or external data.

3. **data_specialist(question, context, kpi_ids)** — Delegates complex data retrieval to the
   Data Specialist Agent (Sonnet 4.5). Use for any question requiring KPI data or SQL queries.

4. **analysis(raw_data, question)** — Delegates formatting to the Analysis Agent (Haiku 4.5).
   Always call this last to produce the final user-facing response from raw data.

---

## Data Retrieval Strategy

### When customer is unknown or user asks "what customers do we have":
1. Call `get_available_kpis("all")` to discover available customers and KPIs.
2. Present the list of customers found.

### For aggregated metrics (revenue, volume, OOS%, store count) when you need KPI IDs:
1. Call `get_available_kpis(customer)` ONLY if you don't already know the KPI IDs.
2. Call `data_specialist(question, context, kpi_ids)` with those IDs.
3. Call `analysis(raw_data, question)` to format the result.

### For most revenue/sales questions — go DIRECTLY to data_specialist:
- Skip `get_available_kpis` entirely. The data_specialist knows the schema and can query directly.
- Call `data_specialist(question, context)` with the customer and date range in context.
- Call `analysis(raw_data, question)` to format the result.

### For order-level detail or custom filters (e.g. "top 3 locations"):
1. Call `data_specialist(question, context)` directly — it will generate the SQL.
2. Call `analysis(raw_data, question)` to format the result.

### For external information (company news, market trends):
1. Call `web_search(query)` with a concise search query.
2. For stock prices: query "TICKER stock price today" for current price, not "close" (markets may still be open).
3. Combine with internal data if relevant, then call `analysis`.

### For simple conversational questions (no data needed):
- Answer directly without calling any tools.

---

## Context Resolution (CRITICAL)

The [CONVERSATION HISTORY] section in the prompt contains previous turns. You MUST use it:

- "which store sold the most during this period?" after Kroger 2024 → resolve to Kroger, 2024
- "What about February?" after January → same customer + year
- "The drop" → metric that declined in the previous answer
- "Sorry, [customer] please" → user answering your clarification question
- Never ask for clarification if the answer is already in the conversation history

When calling `data_specialist`, always pass the resolved customer, date range, and context explicitly.

**IMPORTANT**: Call `get_available_kpis` at most ONCE per response. Never call it twice.

---

## Important: Current Date

Today is February 2026. "Last month" = January 2026. "Last year" = 2025.

---

## Security

When calling `data_specialist` for SQL queries, the `org_id` must always be included in context
so the specialist can pass it to `execute_sql_query`. Never omit org_id.

---

## Response Format

Always return a JSON object with this exact structure:

```json
{
  "response": "Full markdown-formatted answer with tables, insights, and narrative",
  "suggested_questions": [
    "Follow-up question 1?",
    "Follow-up question 2?",
    "Follow-up question 3?"
  ]
}
```

**IMPORTANT**: Return ONLY the raw JSON object. No code fences (no ```json```). No text outside the JSON.

---

## Error Handling

- If a tool returns an error, inform the user in plain language without exposing technical details.
- If no data is found, suggest alternative questions the user could ask.
- If the question is ambiguous about which customer, call get_available_kpis("all") to discover customers rather than asking the user.
- If web search fails, continue with internal data only and note the limitation.
"""
from web_search import nova_grounding_search            # agents/coordinator/web_search.py
from bedrock_agentcore.memory import MemoryClient

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "queen_coordinator_mem-Bjfth3HKgJ")

# Memory client — module-level singleton
_memory_client = MemoryClient(region_name=AWS_REGION)

# ---------------------------------------------------------------------------
# Specialist system prompt (inline — specialist/ is not in this zip)
# ---------------------------------------------------------------------------

SPECIALIST_SYSTEM_PROMPT = """
You are the Data Specialist Agent for QueenAI's agentic chat pipeline.

## Your Responsibilities
1. Analyze the question and decide whether to use KPI data, SQL queries, or both.
2. Call get_kpi_data when KPI IDs are provided or the question asks for aggregated metrics.
3. Call execute_sql_query when order-level detail or custom filters are needed.
4. Retry failed SQL queries up to 3 attempts total.
5. Return all collected data in structured JSON.

## Database Schema

### reddyice_s3_commercial_money (chain-level KPI aggregates)
Columns: mon_year, parent_chain_group, company_chain, channel_group, channel,
cy_revenue, py_revenue, revenue_variance, revenue_variance_percent,
cy_volume, py_volume, volume_variance, percent_volume_change,
cy_sss_revenue, py_sss_revenue, sss_revenue_variance,
cy_sss_volume, py_sss_volume, sss_volume_variance,
store_count, cy_oos_percent, py_oos_percent, quarter

NO customer_name column. NO individual store revenue. Use parent_chain_group for customer.
Known customers in this table: use SELECT DISTINCT parent_chain_group to discover them.

### reddyice_s3_order_details (individual orders, NO revenue)
Columns: sugar_order_number, order_created_date, customer_no, customer_name,
order_status, order_category, order_type, last_service_date, age_in_days,
last_updated, reason_of_call, parent_chain_group, region, market, bu,
total_orders, fulfillment_days

NO revenue columns. Use for order counts and fulfillment metrics only.
Has customer_name for individual store locations.

## CRITICAL Data Model Rules — Apply Before Every Query

**Revenue/Sales questions → use `reddyice_s3_commercial_money` ONLY:**
- Revenue data ONLY exists at CHAIN level (parent_chain_group). No individual store revenue.
- When asked "sales by location" → explain the limitation, then provide chain-level monthly data from `reddyice_s3_commercial_money`
- NEVER query `reddyice_s3_order_details` for revenue or sales amounts

**Order/Fulfillment questions → use `reddyice_s3_order_details` ONLY:**
- Individual store names (customer_name) only exist here
- No revenue in this table — only order counts, fulfillment days, order status

**Decision rule — make ONE decision, execute ONCE:**
- Revenue/sales → `reddyice_s3_commercial_money` directly, no exploration
- Orders/fulfillment → `reddyice_s3_order_details` directly, no exploration
- Do NOT run exploratory queries to check what data exists — trust the schema above

## CRITICAL: Current Date

Today is February 2026. "Last month" = January 2026. "Last year" = 2025.
Data only exists from 2024 onwards. If asked about 2023 or earlier, say so immediately without querying.

When the coordinator passes a question with "last month", "this year", etc., resolve it:
- "last month" → January 2026 → use mon_year >= '2026-01-01' AND mon_year < '2026-02-01'
- "this year" → 2026 → use YEAR(mon_year) = 2026
- "last year" → 2025 → use YEAR(mon_year) = 2025
- "last quarter" → Q4 2025 → October–December 2025

## SQL Rules
- SELECT only. No INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE.
- No multiple statements.
- Always include parent_chain_group filter when a specific customer is mentioned.
- Always pass org_id to execute_sql_query.
- Use LIMIT 100 to prevent large result sets.
- mon_year is a TIMESTAMP column. Use YEAR(mon_year) = 2024 or mon_year >= '2024-01-01' AND mon_year < '2025-01-01'. NEVER use BETWEEN '2024-01' AND '2024-12'.
- Data only exists from 2024 onwards. If asked about 2023 or earlier, say so immediately without querying.
- Known customers: Kroger, Circle K (and others). Do not query to discover customers — use what's provided.

## Output Format
Return JSON: {"kpi_data": [...], "transactional_data": [...], "data_sources_used": [...],
"notes": "...", "sql_query": "...", "success": true, "error_message": null}
"""

# ---------------------------------------------------------------------------
# Analysis system prompt (inline)
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """
You are the Analysis Agent for QueenAI's agentic chat pipeline.
You receive raw data and produce the final user-facing response.
You have NO tools — pure text-in, text-out formatting.

## Formatting Rules
- Currency: $1,234.56
- Percentages: 45.2%
- Large integers: 1,234,567
- Dates: "January 2025" (not 2025-01)
- Tables: always use proper markdown pipe syntax with header separator row (|---|---|)

## Data Context
- Available data covers 2024 and 2025 only. Never suggest questions about 2023 or earlier, or 2026 onwards.
- When suggesting follow-up questions, use specific months/quarters within 2024-2025.
- Use ALL fields present in the raw data — never silently drop columns
- If prior year fields (py_*) are present, always include them alongside current year (cy_*) for comparison
- If variance fields are present, include them in the table or narrative
- Highlight notable trends, outliers, or patterns visible in the data
- Calculate derived metrics (totals, averages, % differences) when the data supports it

## Output Format
Return a raw JSON object (NO code fences, NO markdown wrapping):
{"response": "full markdown answer with tables and insights",
"suggested_questions": ["question 1?", "question 2?"]}

CRITICAL:
- Output ONLY the raw JSON object. No ```json``` fences. No text before or after. Just the JSON.
- Do NOT include a "Suggested Follow-up Questions" section inside the response field — put them only in suggested_questions.
- The response field must be a plain markdown string, never a JSON object or JSON string.
"""

# ---------------------------------------------------------------------------
# Timing collector — module-level list with lock (works across async threads)
# ---------------------------------------------------------------------------

import threading
import time as _time

_timing_lock = threading.Lock()
_timing_events: list = []
_analysis_result_store: dict = {"result": None}  # shared across threads, protected by _timing_lock

def _timing_log() -> list:
    return _timing_events

def _timing_reset():
    global _timing_events
    with _timing_lock:
        _timing_events = []

def _timing_record(label: str, ms: int, agent: str = "coordinator"):
    with _timing_lock:
        _timing_events.append({"label": label, "ms": ms, "agent": agent})

# ---------------------------------------------------------------------------
# Lambda helper
# ---------------------------------------------------------------------------

def _invoke_lambda(function_name: str, payload: dict, agent: str = "coordinator") -> dict:
    t0 = _time.time()
    client = boto3.client("lambda", region_name=AWS_REGION)
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(payload).encode(),
    )
    result = json.loads(response["Payload"].read())
    _timing_record(f"lambda:{function_name}", int((_time.time() - t0) * 1000), agent=agent)
    if response.get("FunctionError") or (isinstance(result, dict) and result.get("error")):
        return result if isinstance(result, dict) else {"error": str(result)}
    return result

# ---------------------------------------------------------------------------
# Analysis Agent
# ---------------------------------------------------------------------------

analysis_agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0", region_name=AWS_REGION),
    system_prompt=ANALYSIS_SYSTEM_PROMPT,
    tools=[],
)

# ---------------------------------------------------------------------------
# Data Specialist Agent
# ---------------------------------------------------------------------------

@tool
def get_kpi_data(kpi_ids: str, date_range: str, frequency: str, org_id: str = "default") -> dict:
    """Retrieves pre-calculated KPI data from the reddyice_s3_commercial_money table.

    Args:
        kpi_ids: Comma-separated KPI IDs (e.g. '17870,17868')
        date_range: Date range in format 'YYYY-MM to YYYY-MM'
        frequency: One of 'monthly', 'weekly', 'daily'
        org_id: Organization ID for tenant isolation
    """
    return _invoke_lambda("queen-get-kpi-data-lambda", {
        "kpi_ids": kpi_ids, "date_range": date_range,
        "frequency": frequency, "org_id": org_id,
    }, agent="data_specialist")


@tool
def execute_sql_query(sql_query: str, org_id: str) -> dict:
    """Executes a SELECT SQL query against the MySQL database.
    Only SELECT queries are permitted. Always include org_id.

    Args:
        sql_query: A SELECT SQL query using only allowed tables and columns
        org_id: Organization ID for tenant isolation (required)
    """
    return _invoke_lambda("queen-sql-executor-lambda", {
        "sql_query": sql_query, "org_id": org_id,
    }, agent="data_specialist")


data_specialist_agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0", region_name=AWS_REGION),
    system_prompt=SPECIALIST_SYSTEM_PROMPT,
    tools=[get_kpi_data, execute_sql_query],
)

# ---------------------------------------------------------------------------
# Coordinator Agent
# ---------------------------------------------------------------------------

@tool
def get_available_kpis(customer: str) -> dict:
    """Returns available KPI IDs and definitions for a given customer.
    Call this first to identify which KPI IDs to pass to the data_specialist.

    Args:
        customer: Customer/chain name (e.g. 'Customer A') or 'all' for all customers
    """
    return _invoke_lambda("get_available_kpis", {"customer": customer}, agent="coordinator")


@tool
def web_search(query: str) -> dict:
    """Searches the web for external information about companies, market trends, or news.

    Args:
        query: A concise search query
    """
    t0 = _time.time()
    result = nova_grounding_search(query)
    _timing_record("nova:nova_grounding_search", int((_time.time() - t0) * 1000), agent="coordinator")
    return result


@tool
def data_specialist(question: str, context: str, kpi_ids: str = "") -> str:
    """Delegates complex data retrieval to the Data Specialist Agent.
    Returns raw structured data for the coordinator to pass to analysis.

    Args:
        question: The user's data question (include customer, date range, metric)
        context: Relevant conversation context (customer name, date range, org_id)
        kpi_ids: Optional comma-separated KPI IDs from get_available_kpis
    """
    t0 = _time.time()
    prompt = f"Context: {context}\n\nQuestion: {question}"
    if kpi_ids:
        prompt += f"\n\nAvailable KPI IDs: {kpi_ids}"
    result = str(data_specialist_agent(prompt))
    _timing_record("agent:data_specialist", int((_time.time() - t0) * 1000))
    return result



@tool
def analysis(raw_data: str, question: str) -> str:
    """Formats raw data into a user-facing response with markdown tables and insights.
    This is the FINAL step — the result is returned directly to the user.

    Args:
        raw_data: JSON string or text of retrieved KPI or SQL data
        question: The original user question for context
    """
    t0 = _time.time()
    prompt = f"Question: {question}\n\nRaw data:\n{raw_data}\n\nFormat this into a response."
    result = str(analysis_agent(prompt))
    _timing_record("agent:analysis", int((_time.time() - t0) * 1000))
    with _timing_lock:
        _analysis_result_store["result"] = result
    return result


coordinator_agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0", region_name=AWS_REGION),
    system_prompt=COORDINATOR_SYSTEM_PROMPT,
    tools=[get_available_kpis, web_search, data_specialist, analysis],
)

# Pre-built variant without web_search (avoids per-request Agent() construction)
coordinator_agent_no_web = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0", region_name=AWS_REGION),
    system_prompt=COORDINATOR_SYSTEM_PROMPT,
    tools=[get_available_kpis, data_specialist, analysis],
)

# ---------------------------------------------------------------------------
# AgentCore App
# ---------------------------------------------------------------------------

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload, context):
    _timing_reset()
    t_start = _time.time()

    prompt = payload.get("prompt", "")
    if not prompt:
        return {"error": "Missing 'prompt' in payload"}

    org_id = payload.get("org_id", os.environ.get("ORG_ID", "default"))
    os.environ["ORG_ID"] = org_id

    web_search_enabled = payload.get("web_search_enabled", False)

    # User identity for memory namespacing
    actor_id = payload.get("actor_id", "demo_user")
    session_id = payload.get("session_id", "default_session")

    # ---------------------------------------------------------------------------
    # Read conversation history from AgentCore Memory (STM)
    # Falls back to payload history if memory read fails
    # ---------------------------------------------------------------------------
    history = []
    try:
        turns = _memory_client.get_last_k_turns(
            memory_id=MEMORY_ID,
            actor_id=actor_id,
            session_id=session_id,
            k=6,
        )
        for turn in turns:
            for msg in turn:
                role = msg.get("role", "").upper()
                content = msg.get("content", {})
                text = content.get("text", "") if isinstance(content, dict) else str(content)
                if role == "USER":
                    history.append({"role": "user", "content": text})
                elif role == "ASSISTANT":
                    history.append({"role": "assistant", "content": text})
    except Exception as _mem_err:
        # Fall back to payload history if memory unavailable
        history = payload.get("history", [])
        history = history[-6:] if len(history) > 6 else history

    # Build the full prompt including conversation context
    if history:
        context_lines = []
        for turn in history:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if role == "user":
                context_lines.append(f"User: {content}")
            elif role == "assistant":
                context_lines.append(f"Assistant: {content[:300]}..." if len(content) > 300 else f"Assistant: {content}")
        context_str = "\n".join(context_lines)
        full_prompt = f"[CONVERSATION HISTORY]\n{context_str}\n\n[CURRENT QUESTION]\n{prompt}"
    else:
        full_prompt = prompt

    if not web_search_enabled:
        full_prompt = f"[INTERNAL DATA ONLY — do not use web_search tool]\n\n{full_prompt}"

    # Use pre-built agent (no per-request construction overhead)
    agent = coordinator_agent if web_search_enabled else coordinator_agent_no_web

    # Reset analysis result cache before running
    with _timing_lock:
        _analysis_result_store["result"] = None

    t_coordinator_start = _time.time()
    result = agent(full_prompt)
    coordinator_ms = int((_time.time() - t_coordinator_start) * 1000)

    # If analysis tool ran, use its result directly — skip coordinator re-processing
    with _timing_lock:
        analysis_result = _analysis_result_store["result"]
    response_text = analysis_result if analysis_result else str(result)
    total_ms = int((_time.time() - t_start) * 1000)

    timing = {
        "total_ms": total_ms,
        "coordinator_ms": coordinator_ms,
        "events": _timing_log(),
    }

    import re as _re

    def _unwrap(text: str) -> dict | None:
        t = text.strip()
        m = _re.search(r'```json\s*(\{[\s\S]*?\})\s*```', t)
        if m:
            t = m.group(1)
        try:
            return json.loads(t)
        except (json.JSONDecodeError, ValueError):
            return None

    def _resolve(parsed: dict) -> dict:
        if 'response' not in parsed:
            return parsed
        inner_val = parsed['response']
        if isinstance(inner_val, dict) and 'response' in inner_val:
            parsed['response'] = inner_val['response']
            if 'suggested_questions' in inner_val and not parsed.get('suggested_questions'):
                parsed['suggested_questions'] = inner_val['suggested_questions']
            return _resolve(parsed)
        if isinstance(inner_val, str):
            inner = _unwrap(inner_val)
            if inner and isinstance(inner, dict) and 'response' in inner:
                parsed['response'] = inner['response']
                if 'suggested_questions' in inner and not parsed.get('suggested_questions'):
                    parsed['suggested_questions'] = inner['suggested_questions']
                return _resolve(parsed)
        return parsed

    parsed = _unwrap(response_text)
    if parsed and isinstance(parsed, dict):
        parsed = _resolve(parsed)
        parsed["_timing"] = timing
        final_response = parsed.get("response", response_text)
    else:
        parsed = {"response": response_text, "suggested_questions": [], "_timing": timing}
        final_response = response_text

    # ---------------------------------------------------------------------------
    # Save this turn to AgentCore Memory (STM) — fire and forget, don't block
    # ---------------------------------------------------------------------------
    try:
        _memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=actor_id,
            session_id=session_id,
            messages=[
                (prompt, "USER"),
                (final_response[:2000], "ASSISTANT"),
            ],
        )
    except Exception as _mem_save_err:
        import logging as _logging
        _logging.getLogger(__name__).warning(f"[MEMORY] create_event failed: {_mem_save_err}")
        print(f"[MEMORY ERROR] create_event failed: {_mem_save_err}")

    return parsed


if __name__ == "__main__":
    app.run()
