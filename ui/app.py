"""
QueenAI Agentic Chat Pipeline - Streamlit UI

This Streamlit application provides an interactive chat interface for the agentic chat pipeline.
It integrates with the AgentCore Runtime to provide:
- Real-time streaming responses
- Progress updates showing agent workflow stages
- Session management for conversation continuity
- Latency tracking between agent calls
- Error handling with user-friendly messages
"""

import streamlit as st
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List
import boto3
from botocore.config import Config
import json
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('streamlit_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task 7.3 — Validate required environment variables at startup
# ---------------------------------------------------------------------------
_AGENTCORE_AGENT_ID = os.getenv('AGENTCORE_AGENT_ID', '')
_AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
_AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID', '')  # optional — avoids STS call if set


# Page configuration (must come before any other st calls)
st.set_page_config(
    page_title="QueenAI Chat",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Check required env vars before rendering anything else
_missing_vars = []
if not _AGENTCORE_AGENT_ID:
    _missing_vars.append('AGENTCORE_AGENT_ID')

if _missing_vars:
    st.error(
        f"Missing required environment variable(s): {', '.join(_missing_vars)}. "
        "Please set them in your .env file or environment and restart the app."
    )
    st.stop()

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #1f77b4;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left: 4px solid #4caf50;
    }
    .progress-update {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 0.3rem;
        font-size: 0.9rem;
    }
    .error-message {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .latency-info {
        font-size: 0.8rem;
        color: #888;
        margin-top: 0.5rem;
    }
    .stage-badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-size: 0.8rem;
        font-weight: bold;
        margin-right: 0.5rem;
    }
    .stage-data-source {
        background-color: #e3f2fd;
        color: #1976d2;
    }
    .stage-retrieval {
        background-color: #f3e5f5;
        color: #7b1fa2;
    }
    .stage-analysis {
        background-color: #e8f5e9;
        color: #388e3c;
    }
    .stage-response {
        background-color: #fff3e0;
        color: #f57c00;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    # Task 7.4 — Session ID via uuid4
    if 'session_id' not in st.session_state:
        user_id = st.query_params.get("user", "demo_user")
        chat_slot = st.query_params.get("chat", "1")
        # runtimeSessionId requires min 33 chars — pad with a stable hash
        import hashlib
        base = f"{user_id}_chat_{chat_slot}"
        suffix = hashlib.md5(base.encode()).hexdigest()
        st.session_state.session_id = f"{base}_{suffix}"
        logger.info(f"Session ID set: {st.session_state.session_id}")

    if 'messages' not in st.session_state:
        st.session_state.messages = []
        logger.info("Initialized empty message history")

    # Task 7.1 — AgentCore Runtime client (bedrock-agentcore)
    if 'agentcore_client' not in st.session_state:
        config = Config(
            read_timeout=180,
            connect_timeout=10,
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )
        st.session_state.agentcore_client = boto3.client(
            'bedrock-agentcore',
            region_name=_AWS_REGION,
            config=config
        )

    # Task 7.1 — AgentCore agent ID from env var
    if 'agentcore_agent_id' not in st.session_state:
        st.session_state.agentcore_agent_id = _AGENTCORE_AGENT_ID

    # Build and cache the full ARN (avoids STS call on every message)
    if 'agentcore_agent_arn' not in st.session_state:
        if _AWS_ACCOUNT_ID:
            # Fast path — no STS call needed
            account_id = _AWS_ACCOUNT_ID
        else:
            t_sts = time.time()
            account_id = boto3.client('sts', region_name=_AWS_REGION).get_caller_identity()['Account']
            logger.info(f"[TIMING] STS get_caller_identity: {time.time() - t_sts:.3f}s")
        st.session_state.agentcore_agent_arn = (
            f"arn:aws:bedrock-agentcore:{_AWS_REGION}:{account_id}:runtime/{_AGENTCORE_AGENT_ID}"
        )
        logger.info(f"[TIMING] Agent ARN cached: {st.session_state.agentcore_agent_arn}")

    if 'org_id' not in st.session_state:
        st.session_state.org_id = "default"

    if 'user_id' not in st.session_state:
        # Use ?user= URL param for stable identity across page refreshes
        # e.g. http://localhost:8501/?user=maxpaz
        st.session_state.user_id = st.query_params.get("user", "demo_user")

    if 'total_latency' not in st.session_state:
        st.session_state.total_latency = 0

    if 'message_count' not in st.session_state:
        st.session_state.message_count = 0

    if 'stage_latencies' not in st.session_state:
        st.session_state.stage_latencies = {}

    if 'suggested_questions' not in st.session_state:
        st.session_state.suggested_questions = []


def get_stage_badge(stage: str) -> str:
    """Get HTML badge for workflow stage."""
    stage_classes = {
        'data_source': 'stage-data-source',
        'retrieval': 'stage-retrieval',
        'analysis': 'stage-analysis',
        'response': 'stage-response'
    }

    stage_names = {
        'data_source': '📊 Data Source',
        'retrieval': '🔍 Retrieval',
        'analysis': '📈 Analysis',
        'response': '💬 Response'
    }

    css_class = stage_classes.get(stage, 'stage-badge')
    name = stage_names.get(stage, stage.title())

    return f'<span class="stage-badge {css_class}">{name}</span>'


def display_timeline(events: List[Dict[str, Any]], start_time: float, completed: bool = False):
    """Display agent execution timeline with timing."""
    if not events:
        return

    timeline_html = '<div style="background: #f8f9fa; padding: 1rem; border-radius: 0.5rem; margin: 1rem 0;">'
    timeline_html += '<div style="font-weight: bold; margin-bottom: 0.5rem;">🔄 Agent Execution Timeline</div>'

    tool_colors = {
        'get_kpi_data': '#2196F3',
        'execute_sql_query': '#9C27B0',
        'web_search': '#4CAF50',
        'get_available_kpis': '#FF9800',
        'data_specialist': '#F44336',
        'analysis': '#00BCD4',
    }

    for event in events:
        if event['type'] == 'tool_use':
            tool_name = event.get('name', 'unknown')
            elapsed = event.get('time', 0)
            color = tool_colors.get(tool_name, '#757575')

            timeline_html += f'''
            <div style="margin: 0.5rem 0; padding: 0.5rem; background: white; border-left: 4px solid {color}; border-radius: 0.3rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 500;">🔧 {tool_name}</span>
                    <span style="color: #666; font-size: 0.85rem;">{elapsed:.2f}s</span>
                </div>
            </div>
            '''

        elif event['type'] == 'lambda':
            action = event.get('name', 'unknown')
            elapsed = event.get('time', 0)

            timeline_html += f'''
            <div style="margin: 0.5rem 0 0.5rem 2rem; padding: 0.4rem; background: #FFF3E0; border-left: 3px solid #FF9800; border-radius: 0.3rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.9rem;">📊 {action}</span>
                    <span style="color: #666; font-size: 0.85rem;">{elapsed:.2f}s</span>
                </div>
            </div>
            '''

    if completed:
        timeline_html += '<div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #ddd; color: #4CAF50; font-weight: 500;">✓ Workflow Complete</div>'

    timeline_html += '</div>'
    st.markdown(timeline_html, unsafe_allow_html=True)


def display_message(message: Dict[str, Any]):
    """Display a chat message using st.chat_message for proper markdown rendering."""
    role = message.get('role', 'user')
    content = message.get('content', '')
    timestamp = message.get('timestamp', '')
    metadata = message.get('metadata', {})

    if role == 'user':
        with st.chat_message("user"):
            st.markdown(content)
            st.caption(timestamp)

    elif role == 'assistant':
        with st.chat_message("assistant"):
            # Escape $ signs to prevent Streamlit treating them as LaTeX math delimiters
            safe_content = content.replace("$", r"\$")
            st.markdown(safe_content)

            latency = metadata.get('latency', 0)
            timing_ui = metadata.get('timing', {})
            agent_timing = metadata.get('agent_timing', {})
            invoke_ms = timing_ui.get('invoke_ms', 0)
            read_ms = timing_ui.get('read_ms', 0)
            agent_total_ms = agent_timing.get('total_ms', 0)
            coordinator_ms = agent_timing.get('coordinator_ms', 0)
            ui_overhead_ms = max(0, int(latency * 1000) - invoke_ms - read_ms)
            network_ms = max(0, invoke_ms - agent_total_ms) if agent_total_ms else invoke_ms
            events = agent_timing.get('events', [])

            st.caption(f"⏱️ {latency:.2f}s  ·  {timestamp}")

            # Suggested questions as clickable buttons
            suggested = metadata.get('suggested_questions', [])
            if suggested:
                st.markdown("**Suggested follow-up questions:**")
                cols = st.columns(min(len(suggested), 2))
                for i, q in enumerate(suggested):
                    with cols[i % 2]:
                        if st.button(q, key=f"sq_{hash(q)}_{timestamp}", use_container_width=True):
                            st.session_state.user_input = q
                            st.rerun()

            # Timing breakdown
            with st.expander("🔍 Full Timing Breakdown", expanded=False):
                rows = [
                    f"| 🖥️ UI overhead | {ui_overhead_ms} ms |",
                    f"| 🌐 Network to AgentCore | {network_ms} ms |",
                ]
                if coordinator_ms:
                    tool_total = sum(e['ms'] for e in events)
                    coord_model_ms = max(0, coordinator_ms - tool_total)
                    rows.append(f"| 🎯 Coordinator | {coord_model_ms} ms |")
                for e in events:
                    label, ms = e['label'], e['ms']
                    agent = e.get('agent', 'coordinator')
                    prefix = "🎯 [coordinator]" if agent == "coordinator" else "🔬 [data_specialist]"
                    if label == 'lambda:get_available_kpis':
                        rows.append(f"| {prefix} Lambda: get_available_kpis | {ms} ms |")
                    elif label == 'nova:nova_grounding_search':
                        rows.append(f"| 🌐 Web Search | {ms} ms |")
                    elif label == 'agent:data_specialist':
                        rows.append(f"| 🔬 Data Specialist | {ms} ms |")
                    elif label == 'agent:analysis':
                        rows.append(f"| 📊 Analysis Agent | {ms} ms |")
                    elif label == 'agent:router':
                        rows.append(f"| 🎯 Router | {ms} ms |")
                    elif label.startswith('lambda:'):
                        rows.append(f"| {prefix} Lambda: {label[7:]} | {ms} ms |")
                    else:
                        rows.append(f"| {prefix} {label} | {ms} ms |")
                rows.append(f"| 📥 Response read | {read_ms} ms |")
                rows.append(f"| **Total** | **{int(latency * 1000)} ms** |")
                st.markdown("| Stage | Time |\n|---|---|\n" + "\n".join(rows))

    elif role == 'error':
        with st.chat_message("assistant"):
            st.error(content)


def process_user_message(user_input: str):
    """Process user message and get response from AgentCore Runtime agent."""
    t0 = time.time()
    logger.info(f"[TIMING] process_user_message start")

    # Add user message to chat
    user_message = {
        'role': 'user',
        'content': user_input,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'metadata': {}
    }
    st.session_state.messages.append(user_message)

    # Create placeholders
    response_placeholder = st.empty()
    progress_placeholder = st.empty()

    start_time = time.time()
    timeline_events = []
    response_content = ""

    try:
        with progress_placeholder:
            st.info("Processing your request...")

        t_before_invoke = time.time()
        logger.info(f"[TIMING] UI setup done: {t_before_invoke - t0:.3f}s — invoking AgentCore now")

        # Invoke AgentCore Runtime
        response = st.session_state.agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=st.session_state.agentcore_agent_arn,
            runtimeSessionId=st.session_state.session_id,
            contentType="application/json",
            accept="application/json",
            payload=json.dumps({
                "prompt": user_input,
                "org_id": st.session_state.org_id,
                "actor_id": st.session_state.user_id,
                "session_id": st.session_state.session_id,
                "web_search_enabled": st.session_state.get('web_search_enabled', False),
                "history": [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[-6:]
                    if m["role"] in ("user", "assistant") and isinstance(m.get("content"), str)
                ],
            }).encode("utf-8"),
        )

        t_after_invoke = time.time()
        logger.info(f"[TIMING] invoke_agent_runtime returned: {t_after_invoke - t_before_invoke:.3f}s")

        # Read response body — update progress with elapsed time while waiting
        with progress_placeholder:
            st.info(f"⏳ Agent thinking... ({t_after_invoke - t_before_invoke:.1f}s to connect, reading response...)")

        stream = response.get("response")
        if stream is not None:
            raw = stream.read()
            response_content = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        else:
            response_content = ""

        t_after_read = time.time()
        logger.info(f"[TIMING] stream.read() done: {t_after_read - t_after_invoke:.3f}s — {len(response_content)} chars")

        # Clear progress
        progress_placeholder.empty()

        total_latency = t_after_read - t0
        logger.info(f"[TIMING] Total end-to-end: {total_latency:.3f}s (UI setup: {t_before_invoke - t0:.3f}s, invoke: {t_after_invoke - t_before_invoke:.3f}s, read: {t_after_read - t_after_invoke:.3f}s)")

        # Update session metrics
        st.session_state.total_latency += total_latency
        st.session_state.message_count += 1

        # Parse JSON response from coordinator
        suggested_questions = []
        display_content = response_content

        try:
            stripped = response_content.strip()
            logger.info(f"[PARSE] Raw response preview: {stripped[:200]}")

            response_data = None

            # Try bare JSON first (most common — agent returns plain JSON)
            try:
                response_data = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                pass

            # Fallback: extract from ```json ... ``` code fence
            if response_data is None:
                import re
                json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', stripped)
                if json_match:
                    try:
                        response_data = json.loads(json_match.group(1))
                    except (json.JSONDecodeError, ValueError):
                        pass

            # Fallback: find first { ... } block
            if response_data is None:
                import re
                json_match = re.search(r'\{[\s\S]*\}', stripped)
                if json_match:
                    try:
                        response_data = json.loads(json_match.group(0))
                    except (json.JSONDecodeError, ValueError):
                        pass

            if response_data and isinstance(response_data, dict):
                if 'response' in response_data:
                    inner = response_data['response']
                    # Handle double-wrapped: response field contains another ```json...``` or JSON
                    if isinstance(inner, str):
                        inner_stripped = inner.strip()
                        # Try to unwrap nested code fence
                        import re
                        fence_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', inner_stripped)
                        if fence_match:
                            try:
                                inner_data = json.loads(fence_match.group(1))
                                if 'response' in inner_data:
                                    inner = inner_data['response']
                                    if 'suggested_questions' in inner_data:
                                        suggested_questions = inner_data['suggested_questions']
                            except (json.JSONDecodeError, ValueError):
                                pass
                        display_content = inner
                    logger.info("[PARSE] Extracted response field from JSON")
                if 'suggested_questions' in response_data and not suggested_questions:
                    sq = response_data['suggested_questions']
                    if isinstance(sq, list):
                        suggested_questions = sq
                # Extract agent-side timing if present
                agent_timing_raw = response_data.get('_timing', {})
            else:
                logger.info("[PARSE] No JSON structure found — using raw response")
                agent_timing_raw = {}

            if suggested_questions:
                st.session_state.suggested_questions = suggested_questions

        except Exception as e:
            logger.warning(f"[PARSE] Failed to parse response: {e}")
            agent_timing_raw = {}

        response_content = display_content

        # Add assistant message to chat
        assistant_message = {
            'role': 'assistant',
            'content': response_content,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'metadata': {
                'latency': total_latency,
                'timing': {
                    'invoke_ms': int((t_after_invoke - t_before_invoke) * 1000),
                    'read_ms': int((t_after_read - t_after_invoke) * 1000),
                },
                'agent_timing': agent_timing_raw,
                'timeline': timeline_events,
                'suggested_questions': suggested_questions,
            }
        }
        st.session_state.messages.append(assistant_message)
        logger.info(f"Added assistant message to history. Total messages: {len(st.session_state.messages)}")

        # Invalidate memory cache so sidebar refreshes on next render
        st.session_state.pop("memory_turns", None)

        with response_placeholder:
            display_message(assistant_message)

        logger.info("Successfully displayed final message")

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_str = str(e)

        logger.error(f"Error processing message: {error_str}")
        logger.error(f"Error details: {error_details}")

        progress_placeholder.empty()

        if 'Read timed out' in error_str or 'timeout' in error_str.lower():
            friendly_message = """
**Request Timed Out**

The request took too long to complete. This can happen with complex queries.

**What you can do:**
- Try again — it often works on retry
- Try a simpler or more specific question
- Check if the AgentCore endpoint is reachable
"""
        elif 'service unavailable' in error_str.lower():
            friendly_message = """
**Service Temporarily Unavailable**

The AgentCore runtime is experiencing high load. This is typically temporary.

**What you can do:**
- Wait 30 seconds and try again
- Try a simpler question first
- Check the sidebar for connection status
"""
        elif 'AccessDenied' in error_str or 'accessDeniedException' in error_str:
            friendly_message = """
**Permission Error**

The client doesn't have permission to invoke the AgentCore agent.

**What you can do:**
- Contact your administrator
- Check IAM role permissions for bedrock-agentcore-runtime
"""
        elif 'ThrottlingException' in error_str or 'TooManyRequests' in error_str:
            friendly_message = """
**Rate Limit Exceeded**

Too many requests in a short time.

**What you can do:**
- Wait a few seconds and try again
"""
        else:
            friendly_message = f"""
**An Error Occurred**

{error_str}

**What you can do:**
- Try rephrasing your question
- Check the connection status in the sidebar
- Start a new conversation
"""

        error_message = {
            'role': 'error',
            'content': friendly_message,
            'metadata': {
                'error_details': error_details,
                'error_type': type(e).__name__
            }
        }

        with response_placeholder:
            display_message(error_message)

            if any(x in error_str.lower() for x in ['timeout', 'service unavailable', 'throttling']):
                if st.button("🔄 Retry Request", key=f"retry_{time.time()}"):
                    st.rerun()

        st.session_state.messages.append(error_message)
        logger.info(f"Added error message to history. Error type: {type(e).__name__}")


def main():
    """Main Streamlit application."""
    logger.info("Starting Streamlit application")

    # Initialize session state
    initialize_session_state()

    # Header
    st.markdown('<div class="main-header">👑 QueenAI Chat</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Intelligent Business Data Assistant</div>', unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # Web search toggle
        web_search_enabled = st.toggle(
            "🌐 Web Search",
            value=st.session_state.get('web_search_enabled', False),
            help="When ON, the agent can search the web for external information (news, stock prices, market data). When OFF, only internal database tools are used."
        )
        st.session_state.web_search_enabled = web_search_enabled
        if web_search_enabled:
            st.caption("Web search active — agent may query external sources.")
        else:
            st.caption("Internal data only — faster, no external queries.")

        st.divider()

        # Task 7.4 — Session info (no agent_id / agent_alias_id)
        st.subheader("Session Information")
        st.text(f"Session ID: {st.session_state.session_id[:8]}...")
        st.text(f"User: {st.session_state.user_id}")
        st.text(f"Chat: #{st.query_params.get('chat', '1')}")
        st.text(f"Org ID: {st.session_state.org_id}")

        # Metrics
        st.subheader("📊 Metrics")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Messages", st.session_state.message_count)
        with col2:
            avg_latency = (
                st.session_state.total_latency / st.session_state.message_count
                if st.session_state.message_count > 0 else 0
            )
            st.metric("Avg Latency", f"{avg_latency:.2f}s")

        if st.session_state.stage_latencies:
            st.subheader("⏱️ Last Query Breakdown")
            for stage, latency in st.session_state.stage_latencies.items():
                st.text(f"{stage.replace('_', ' ').title()}: {latency:.2f}s")

        st.divider()

        # Suggested / example questions
        if st.session_state.suggested_questions:
            st.subheader("💡 Suggested Follow-up Questions")
            st.caption(f"✨ {len(st.session_state.suggested_questions)} AI-suggested questions based on your conversation")
            questions_to_show = st.session_state.suggested_questions
        else:
            st.subheader("💡 Example Questions")
            questions_to_show = [
                "What were total sales for Q2 2024?",
                "Show me Kroger revenue by month in 2024",
                "Compare Q1 vs Q2 2025 sales",
                "What were Circle K sales in January 2025?",
                "Which customers had the highest revenue in 2024?"
            ]

        for question in questions_to_show:
            if st.button(question, key=f"question_{hash(question)}", use_container_width=True):
                st.session_state.user_input = question
                st.rerun()

        st.divider()

        # Task 7.4 — "New Conversation" button (renamed from "Clear Chat")
        if st.button("🗑️ New Conversation", use_container_width=True):
            old_session_id = st.session_state.session_id
            st.session_state.messages = []
            # Increment chat slot in URL — keeps user identity, starts fresh memory
            current_slot = int(st.query_params.get("chat", "1"))
            new_slot = (current_slot % 3) + 1  # cycles 1→2→3→1
            st.query_params["chat"] = str(new_slot)
            # session_id will be re-derived on next render from the new URL param
            del st.session_state["session_id"]
            st.session_state.total_latency = 0
            st.session_state.message_count = 0
            st.session_state.stage_latencies = {}
            st.session_state.suggested_questions = []
            st.session_state.pop("memory_turns", None)
            logger.info(f"New conversation. Old: {old_session_id}, slot: {new_slot}")
            st.rerun()

        if st.button("🔌 Test Connection", use_container_width=True):
            with st.spinner("Testing AgentCore connection..."):
                try:
                    test_client = boto3.client(
                        'bedrock-agentcore-control',
                        region_name=_AWS_REGION,
                    )
                    test_client.get_agent_runtime(
                        agentRuntimeId=st.session_state.agentcore_agent_id
                    )
                    st.success(f"✅ Connected to AgentCore\nAgent ID: {st.session_state.agentcore_agent_id}")
                except Exception as e:
                    err = str(e)
                    if any(x in err for x in ['ResourceNotFoundException', 'AccessDenied']):
                        st.warning(f"⚠️ Endpoint reachable but agent not found\nAgent ID: {st.session_state.agentcore_agent_id}\n{err}")
                    else:
                        st.error(f"❌ Connection failed: {err}")

        st.divider()

        # Memory viewer
        with st.expander("🧠 AgentCore Memory", expanded=False):
            st.caption(f"User: {st.session_state.user_id} · Session: {st.session_state.session_id[:8]}...")
            if st.button("🔄 Refresh Memory", use_container_width=True, key="refresh_memory"):
                st.session_state.pop("memory_turns", None)

            if "memory_turns" not in st.session_state or st.session_state.get("memory_refresh_session") != st.session_state.session_id:
                try:
                    from bedrock_agentcore.memory import MemoryClient as _MemClient
                    _mc = _MemClient(region_name=_AWS_REGION)
                    turns = _mc.get_last_k_turns(
                        memory_id=os.getenv("AGENTCORE_MEMORY_ID", "queen_coordinator_mem-Bjfth3HKgJ"),
                        actor_id=st.session_state.user_id,
                        session_id=st.session_state.session_id,
                        k=10,
                    )
                    st.session_state.memory_turns = turns
                    st.session_state.memory_refresh_session = st.session_state.session_id
                except Exception as e:
                    st.session_state.memory_turns = []
                    st.caption(f"⚠️ {e}")

            turns = st.session_state.get("memory_turns", [])
            if not turns:
                st.caption("No memory stored yet for this session.")
            else:
                st.caption(f"✅ {len(turns)} turn(s) stored in AgentCore Memory")
                for i, turn in enumerate(turns):
                    for msg in turn:
                        role = msg.get("role", "")
                        content = msg.get("content", {})
                        text = content.get("text", "") if isinstance(content, dict) else str(content)
                        icon = "👤" if role == "USER" else "🤖"
                        st.markdown(f"**{icon} {role}** _{text[:120]}{'...' if len(text) > 120 else ''}_")

    # Main chat area
    chat_container = st.container()

    with chat_container:
        if not st.session_state.messages:
            st.info(
                "📊 **QueenAI Data Assistant**\n\n"
                "I can help you analyze your business data, KPIs, and transactions. "
                "Ask me about sales, revenue, stores, or any business metrics!"
            )
        else:
            for message in st.session_state.messages:
                display_message(message)

    # Chat input
    st.divider()

    default_input = st.session_state.get('user_input', '')
    if default_input:
        del st.session_state.user_input

    user_input = st.chat_input("Ask a question about your business data...", key="chat_input")

    input_to_process = user_input or default_input

    if input_to_process:
        logger.info(f"Processing input: {input_to_process[:50]}...")
        with chat_container:
            process_user_message(input_to_process)
        logger.info("Rerunning Streamlit app to display new message")
        st.rerun()


if __name__ == "__main__":
    main()
