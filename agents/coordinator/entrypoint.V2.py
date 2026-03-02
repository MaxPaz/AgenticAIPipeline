"""
AgentCore Runtime entrypoint V2 — Strands GraphBuilder multi-agent pattern.

Architecture change from V1 (agent-as-tool) to Graph:

V1 flow (current):
  Coordinator LLM → decides to call data_specialist tool → decides to call analysis tool
  Problem: 2-3 LLM turns just for routing (~7s each = 14-21s coordinator overhead)

V2 flow (Graph):
  Router LLM (1 turn) → classifies intent → Graph routes deterministically:
    - data query:    router → data_specialist_node → analysis_node
    - web query:     router → web_search_node → analysis_node
    - conversational: router → direct_response_node
  Benefit: Router only needs 1 LLM turn (~2-3s), then Graph handles the rest without LLM routing.

Rollback: cp entrypoint.py entrypoint.py.bak && cp entrypoint.V2.py entrypoint.py && deploy
"""

import json
import os
import re as _re
import threading
import time as _time

import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient

from web_search import nova_grounding_search

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "queen_coordinator_mem-Bjfth3HKgJ")

_memory_client = MemoryClient(region_name=AWS_REGION)

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

_timing_lock = threading.Lock()
_timing_events: list = []
_result_store: dict = {"result": None}


def _timing_reset():
    global _timing_events
    with _timing_lock:
        _timing_events = []
        _result_store["result"] = None


def _timing_record(label: str, ms: int, agent: str = "coordinator"):
    with _timing_lock:
        _timing_events.append({"label": label, "ms": ms, "agent": agent})


def _timing_log() -> list:
    return _timing_events


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
# System prompts
# ---------------------------------------------------------------------------

ROUTER_SYSTEM_PROMPT = """
You are the Router Agent for QueenAI's agentic chat pipeline.
Your ONLY job is to classify the user's intent and output a routing decision.

## Intent Categories

1. DATA_QUERY — question requires internal database data (revenue, sales, KPIs, OOS%, store counts, orders, fulfillment)
2. WEB_QUERY — question requires external information (stock prices, company news, market trends)
3. CONVERSATIONAL — greeting, clarification, or question answerable without data

## Context Resolution
The [CONVERSATION HISTORY] section contains previous turns. Use it to resolve implicit references:
- "what about February?" after a Kroger question → DATA_QUERY about Kroger February
- "how does that compare?" → DATA_QUERY using the same customer/period from history

## Current Date
Today is February 2026. "Last month" = January 2026. "Last year" = 2025.
Data only exists from 2024 onwards.

## Output Format
Output ONLY a raw JSON object:
{
  "intent": "DATA_QUERY" | "WEB_QUERY" | "CONVERSATIONAL",
  "resolved_question": "The fully resolved question with customer, date range, and metric explicit",
  "context": "customer=X, date=Y, org_id=Z, metric=W",
  "direct_response": "Only set this for CONVERSATIONAL — the actual answer to return"
}

No code fences. No explanation. Just the JSON.
"""

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

### reddyice_s3_order_details (individual orders, NO revenue)
Columns: sugar_order_number, order_created_date, customer_no, customer_name,
order_status, order_category, order_type, last_service_date, age_in_days,
last_updated, reason_of_call, parent_chain_group, region, market, bu,
total_orders, fulfillment_days

NO revenue columns. Use for order counts and fulfillment metrics only.

## CRITICAL Data Model Rules
- Revenue/Sales → reddyice_s3_commercial_money ONLY
- Orders/Fulfillment → reddyice_s3_order_details ONLY
- Make ONE decision, execute ONCE — no exploratory queries

## CRITICAL: Current Date
Today is February 2026. "Last month" = January 2026. "Last year" = 2025.
Data only exists from 2024 onwards.
- "last month" → mon_year >= '2026-01-01' AND mon_year < '2026-02-01'
- "last year" → YEAR(mon_year) = 2025
- "last quarter" → Q4 2025 → October–December 2025

## SQL Rules
- SELECT only. No INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE.
- Always include parent_chain_group filter when a specific customer is mentioned.
- Always pass org_id to execute_sql_query.
- Use LIMIT 100.
- mon_year is TIMESTAMP. Use YEAR(mon_year) = 2024 or date range comparisons. NEVER BETWEEN '2024-01' AND '2024-12'.

## Output Format
Return JSON: {"kpi_data": [...], "transactional_data": [...], "data_sources_used": [...],
"notes": "...", "sql_query": "...", "success": true, "error_message": null}
"""

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
- Do NOT include a "Suggested Follow-up Questions" section inside the response field.
- The response field must be a plain markdown string, never a JSON object or JSON string.
"""

# ---------------------------------------------------------------------------
# Tools for specialist agent
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

    Args:
        sql_query: A SELECT SQL query using only allowed tables and columns
        org_id: Organization ID for tenant isolation (required)
    """
    return _invoke_lambda("queen-sql-executor-lambda", {
        "sql_query": sql_query, "org_id": org_id,
    }, agent="data_specialist")


# ---------------------------------------------------------------------------
# Agent instances (created fresh per request to avoid context bleed)
# ---------------------------------------------------------------------------

def _make_router_agent() -> Agent:
    return Agent(
        model=BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0", region_name=AWS_REGION),
        system_prompt=ROUTER_SYSTEM_PROMPT,
        tools=[],
        callback_handler=None,
    )


def _make_specialist_agent() -> Agent:
    return Agent(
        model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0", region_name=AWS_REGION),
        system_prompt=SPECIALIST_SYSTEM_PROMPT,
        tools=[get_kpi_data, execute_sql_query],
        callback_handler=None,
    )


def _make_analysis_agent() -> Agent:
    return Agent(
        model=BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0", region_name=AWS_REGION),
        system_prompt=ANALYSIS_SYSTEM_PROMPT,
        tools=[],
        callback_handler=None,
    )


# ---------------------------------------------------------------------------
# Graph execution — replaces the coordinator LLM routing loop
# ---------------------------------------------------------------------------

def _run_graph_pipeline(full_prompt: str, web_search_enabled: bool, org_id: str) -> str:
    """
    Execute the pipeline using Strands Graph:
    1. Router classifies intent (1 LLM turn, ~2-3s)
    2. Graph routes deterministically based on intent:
       - DATA_QUERY:     specialist → analysis
       - WEB_QUERY:      web_search → analysis
       - CONVERSATIONAL: direct response (no further LLM calls)
    """
    # Step 1: Router classifies intent
    t_router = _time.time()
    router = _make_router_agent()
    router_result = str(router(full_prompt))
    _timing_record("agent:router", int((_time.time() - t_router) * 1000), agent="coordinator")

    # Parse router decision
    routing = _parse_json(router_result)
    if not routing:
        # Router failed — fall back to treating as data query
        routing = {"intent": "DATA_QUERY", "resolved_question": full_prompt, "context": f"org_id={org_id}"}

    intent = routing.get("intent", "DATA_QUERY")
    resolved_question = routing.get("resolved_question", full_prompt)
    context = routing.get("context", f"org_id={org_id}")

    # Step 2: Handle CONVERSATIONAL directly (no more LLM calls needed)
    if intent == "CONVERSATIONAL":
        direct = routing.get("direct_response", "")
        if direct:
            return json.dumps({
                "response": direct,
                "suggested_questions": [
                    "What were total sales for Q2 2024?",
                    "Show me Kroger revenue by month in 2024",
                    "What were Circle K sales in January 2025?",
                ]
            })

    # Step 3: Build Graph for DATA_QUERY or WEB_QUERY
    specialist = _make_specialist_agent()
    analysis = _make_analysis_agent()

    builder = GraphBuilder()

    if intent == "WEB_QUERY" and web_search_enabled:
        # web_search → analysis
        # We use a thin wrapper agent for web search since Graph needs Agent nodes
        WEB_AGENT_PROMPT = f"""You are a web search agent. Search for: {resolved_question}
Use the web_search tool and return the raw results as JSON."""

        @tool
        def web_search_tool(query: str) -> dict:
            """Search the web for current information.
            Args:
                query: Search query string
            """
            t0 = _time.time()
            result = nova_grounding_search(query)
            _timing_record("nova:nova_grounding_search", int((_time.time() - t0) * 1000), agent="coordinator")
            return result

        web_agent = Agent(
            model=BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0", region_name=AWS_REGION),
            system_prompt=WEB_AGENT_PROMPT,
            tools=[web_search_tool],
            callback_handler=None,
        )
        web_node = builder.add_node(web_agent, node_id="web_search")
        analysis_node = builder.add_node(analysis, node_id="analysis")
        builder.add_edge("web_search", "analysis")
        builder.set_entry_point("web_search")
        task = f"Search for: {resolved_question}"

    else:
        # DATA_QUERY: specialist → analysis
        specialist_node = builder.add_node(specialist, node_id="data_specialist")
        analysis_node = builder.add_node(analysis, node_id="analysis")
        builder.add_edge("data_specialist", "analysis")
        builder.set_entry_point("data_specialist")
        task = f"Context: {context}\n\nQuestion: {resolved_question}"

    graph = builder.build()

    # Wrap graph execution with per-node timing via hooks
    _node_timings: dict = {}
    _node_timings_lock = threading.Lock()

    def _on_node_start(event) -> None:
        with _node_timings_lock:
            _node_timings[event.node_id] = _time.time()

    def _on_node_stop(event) -> None:
        with _node_timings_lock:
            t0 = _node_timings.pop(event.node_id, None)
        if t0 is None:
            return
        ms = int((_time.time() - t0) * 1000)
        if event.node_id == "data_specialist":
            _timing_record("agent:data_specialist", ms, agent="data_specialist")
        elif event.node_id == "analysis":
            _timing_record("agent:analysis", ms, agent="analysis")
        elif event.node_id == "web_search":
            _timing_record("nova:nova_grounding_search", ms, agent="coordinator")

    from strands.hooks.events import BeforeNodeCallEvent, AfterNodeCallEvent
    graph.hooks.add_callback(BeforeNodeCallEvent, _on_node_start)
    graph.hooks.add_callback(AfterNodeCallEvent, _on_node_stop)

    t_graph = _time.time()
    graph_result = graph(task)
    graph_ms = int((_time.time() - t_graph) * 1000)

    # If hooks didn't fire (fallback), estimate from graph total
    recorded_labels = {e["label"] for e in _timing_log()}
    if "agent:data_specialist" not in recorded_labels and intent == "DATA_QUERY":
        _timing_record("agent:data_specialist", int(graph_ms * 0.6), agent="data_specialist")
        _timing_record("agent:analysis", int(graph_ms * 0.4), agent="analysis")

    # Extract final result from graph — last node (analysis) output
    analysis_node_result = graph_result.results.get("analysis")
    if analysis_node_result:
        agent_results = analysis_node_result.get_agent_results()
        if agent_results:
            final_text = str(agent_results[-1])
            with _timing_lock:
                _result_store["result"] = final_text
            return final_text

    # Fallback: return whatever the graph produced
    return str(graph_result)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> dict | None:
    t = text.strip()
    m = _re.search(r'```json\s*(\{[\s\S]*?\})\s*```', t)
    if m:
        t = m.group(1)
    try:
        return json.loads(t)
    except (json.JSONDecodeError, ValueError):
        return None


def _resolve_wrapped(parsed: dict) -> dict:
    """Recursively unwrap double-wrapped response fields."""
    if 'response' not in parsed:
        return parsed
    inner_val = parsed['response']
    if isinstance(inner_val, dict) and 'response' in inner_val:
        parsed['response'] = inner_val['response']
        if 'suggested_questions' in inner_val and not parsed.get('suggested_questions'):
            parsed['suggested_questions'] = inner_val['suggested_questions']
        return _resolve_wrapped(parsed)
    if isinstance(inner_val, str):
        inner = _parse_json(inner_val)
        if inner and isinstance(inner, dict) and 'response' in inner:
            parsed['response'] = inner['response']
            if 'suggested_questions' in inner and not parsed.get('suggested_questions'):
                parsed['suggested_questions'] = inner['suggested_questions']
            return _resolve_wrapped(parsed)
    return parsed


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
    actor_id = payload.get("actor_id", "demo_user")
    session_id = payload.get("session_id", "default_session")

    # Read memory
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
    except Exception:
        history = payload.get("history", [])[-6:]

    # Build full prompt with history
    if history:
        context_lines = []
        for turn in history:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if role == "user":
                context_lines.append(f"User: {content}")
            elif role == "assistant":
                context_lines.append(f"Assistant: {content[:300]}..." if len(content) > 300 else f"Assistant: {content}")
        full_prompt = f"[CONVERSATION HISTORY]\n{chr(10).join(context_lines)}\n\n[CURRENT QUESTION]\n{prompt}"
    else:
        full_prompt = prompt

    if not web_search_enabled:
        full_prompt = f"[INTERNAL DATA ONLY]\n\n{full_prompt}"

    # Run graph pipeline
    response_text = _run_graph_pipeline(full_prompt, web_search_enabled, org_id)

    total_ms = int((_time.time() - t_start) * 1000)
    coordinator_ms = total_ms  # entire pipeline time

    timing = {
        "total_ms": total_ms,
        "coordinator_ms": coordinator_ms,
        "events": _timing_log(),
    }

    # Parse and unwrap response
    parsed = _parse_json(response_text)
    if parsed and isinstance(parsed, dict):
        parsed = _resolve_wrapped(parsed)
        parsed["_timing"] = timing
        final_response = parsed.get("response", response_text)
    else:
        parsed = {"response": response_text, "suggested_questions": [], "_timing": timing}
        final_response = response_text

    # Save to memory
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
    except Exception as _mem_err:
        print(f"[MEMORY ERROR] create_event failed: {_mem_err}")

    return parsed


if __name__ == "__main__":
    app.run()
