"""
QueenAI Agentic Chat Pipeline - Streamlit UI

This Streamlit application provides an interactive chat interface for the agentic chat pipeline.
It integrates with the Bedrock Coordinator Agent to provide:
- Real-time streaming responses
- Progress updates showing agent workflow stages
- Session management for conversation continuity
- Latency tracking between agent calls
- Error handling with user-friendly messages
"""

import streamlit as st
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import boto3
from botocore.config import Config
import json
import os
import logging
from dotenv import load_dotenv
import threading

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


def fetch_token_usage_from_cloudwatch(session_id: str, start_time: float, end_time: float) -> Dict[str, int]:
    """
    Fetch token usage from CloudWatch Logs for a specific query.
    
    Args:
        session_id: Bedrock session ID
        start_time: Query start time (unix timestamp)
        end_time: Query end time (unix timestamp)
        
    Returns:
        Dictionary with total_input_tokens and total_output_tokens
    """
    try:
        logs_client = boto3.client('logs', region_name=os.getenv('AWS_REGION', 'us-west-2'))
        log_group = 'BedrockLogging'  # Correct log group name without leading slash
        
        # Convert to milliseconds with tight time window
        # Use a narrow window to capture only this specific query
        start_ms = int(start_time * 1000)  # Exact start time
        end_ms = int((end_time + 3) * 1000)  # 3 second buffer after for log delays
        
        # Query for model invocation logs with usage data
        # The actual structure is: output.outputBodyJson.usage.inputTokens
        query = '''
        fields @timestamp, output.outputBodyJson.usage.inputTokens as inputTokens, output.outputBodyJson.usage.outputTokens as outputTokens
        | filter ispresent(inputTokens)
        | stats sum(inputTokens) as total_input, sum(outputTokens) as total_output
        '''
        
        logger.info(f"CloudWatch query time window: {start_time} to {end_time} ({end_time - start_time:.1f}s duration)")
        
        query_response = logs_client.start_query(
            logGroupName=log_group,
            startTime=start_ms,
            endTime=end_ms,
            queryString=query,
            limit=1000
        )
        
        query_id = query_response['queryId']
        
        # Wait for query to complete (max 3 seconds)
        for _ in range(6):
            time.sleep(0.5)
            result = logs_client.get_query_results(queryId=query_id)
            
            if result['status'] == 'Complete':
                if result['results'] and len(result['results']) > 0:
                    # Parse results
                    result_fields = {item['field']: item['value'] for item in result['results'][0]}
                    total_input = int(float(result_fields.get('total_input', 0)))
                    total_output = int(float(result_fields.get('total_output', 0)))
                    
                    logger.info(f"Fetched token usage: {total_input} input, {total_output} output")
                    return {
                        'total_input_tokens': total_input,
                        'total_output_tokens': total_output,
                        'total_tokens': total_input + total_output
                    }
                break
            elif result['status'] == 'Failed':
                logger.warning(f"CloudWatch query failed: {result.get('statistics', {})}")
                break
        
        logger.warning("CloudWatch query timed out or returned no results")
        return {'total_input_tokens': 0, 'total_output_tokens': 0, 'total_tokens': 0}
        
    except Exception as e:
        logger.error(f"Error fetching token usage from CloudWatch: {e}")
        return {'total_input_tokens': 0, 'total_output_tokens': 0, 'total_tokens': 0}


# Page configuration
st.set_page_config(
    page_title="QueenAI Chat",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
        logger.info(f"New session created: {st.session_state.session_id}")
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        logger.info("Initialized empty message history")
    
    if 'bedrock_client' not in st.session_state:
        # Configure boto3 client with extended timeout for Bedrock service hiccups
        config = Config(
            read_timeout=180,  # Increased from default 60s to handle service delays
            connect_timeout=10,
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )
        st.session_state.bedrock_client = boto3.client(
            'bedrock-agent-runtime',
            region_name=os.getenv('AWS_REGION', 'us-west-2'),
            config=config
        )
    
    if 'agent_id' not in st.session_state:
        st.session_state.agent_id = os.getenv('BEDROCK_AGENT_ID', 'IVOZ9TEFQZ')
    
    if 'agent_alias_id' not in st.session_state:
        st.session_state.agent_alias_id = os.getenv('BEDROCK_AGENT_ALIAS_ID', 'UPB6NZO4RU')
    
    if 'org_id' not in st.session_state:
        st.session_state.org_id = "default"
    
    if 'user_id' not in st.session_state:
        st.session_state.user_id = "demo_user"
    
    if 'total_latency' not in st.session_state:
        st.session_state.total_latency = 0
    
    if 'message_count' not in st.session_state:
        st.session_state.message_count = 0
    
    if 'stage_latencies' not in st.session_state:
        st.session_state.stage_latencies = {}
    
    if 'search_mode' not in st.session_state:
        st.session_state.search_mode = 'internal'  # 'internal' or 'web'
    
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
    
    # Build timeline HTML
    timeline_html = '<div style="background: #f8f9fa; padding: 1rem; border-radius: 0.5rem; margin: 1rem 0;">'
    timeline_html += '<div style="font-weight: bold; margin-bottom: 0.5rem;">🔄 Agent Execution Timeline</div>'
    
    agent_colors = {
        'DataSourceAgent': '#2196F3',
        'SmartRetrievalAgent': '#9C27B0',
        'AnalysisAgent': '#4CAF50',
        'User': '#FF9800'
    }
    
    current_time = 0
    for event in events:
        if event['type'] == 'agent_start':
            agent = event['agent']
            elapsed = event['time']
            color = agent_colors.get(agent, '#757575')
            
            timeline_html += f'''
            <div style="margin: 0.5rem 0; padding: 0.5rem; background: white; border-left: 4px solid {color}; border-radius: 0.3rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 500;">🤖 {agent}</span>
                    <span style="color: #666; font-size: 0.85rem;">{elapsed:.2f}s</span>
                </div>
            </div>
            '''
            current_time = elapsed
        
        elif event['type'] == 'agent_complete':
            agent = event['agent']
            duration = event['duration']
            
            timeline_html += f'''
            <div style="margin-left: 2rem; color: #666; font-size: 0.85rem;">
                ✓ Completed in {duration:.2f}s
            </div>
            '''
        
        elif event['type'] == 'lambda_call':
            action = event['action']
            elapsed = event['time']
            
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
    """Display a chat message with appropriate styling."""
    role = message.get('role', 'user')
    content = message.get('content', '')
    timestamp = message.get('timestamp', '')
    metadata = message.get('metadata', {})
    
    if role == 'user':
        st.markdown(f"""
        <div class="chat-message user-message">
            <div><strong>You</strong> <span style="color: #888; font-size: 0.8rem;">{timestamp}</span></div>
            <div style="margin-top: 0.5rem;">{content}</div>
        </div>
        """, unsafe_allow_html=True)
    
    elif role == 'assistant':
        st.markdown(f"""
        <div class="chat-message assistant-message">
            <div><strong>QueenAI Assistant</strong> <span style="color: #888; font-size: 0.8rem;">{timestamp}</span></div>
            <div style="margin-top: 0.5rem;">{content}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Display latency info if available
        if 'latency' in metadata:
            st.markdown(f"""
            <div class="latency-info">
                ⏱️ Response time: {metadata['latency']:.2f}s
            </div>
            """, unsafe_allow_html=True)
        
        # Display timeline if available
        if 'timeline' in metadata and metadata['timeline']:
            with st.expander("🔍 View Agentic Workflow Execution", expanded=False):
                timeline = metadata['timeline']
                lambda_calls = [e for e in timeline if e['type'] == 'lambda']
                total_time = metadata.get('latency', 0)
                
                # Calculate agent timing estimates
                if lambda_calls:
                    first_lambda = lambda_calls[0]['time']
                    last_lambda = lambda_calls[-1]['time']
                    
                    # Estimate agent times
                    coordinator_time = first_lambda
                    data_source_time = first_lambda
                    retrieval_time = last_lambda - first_lambda
                    analysis_time = total_time - last_lambda
                    
                    st.markdown("### 🤖 Autonomous Agent Workflow\n")
                    
                    # Show workflow with coordinator orchestrating
                    st.markdown(f"**Coordinator Agent** - Orchestrates entire workflow (`{total_time:.1f}s total`)")
                    st.markdown(f"  ↓ *Routes to* **Data Source Agent** `~{data_source_time:.1f}s` - Identified KPIs, determined data sources")
                    st.markdown(f"  ↓ *Routes to* **Smart Retrieval Agent** `~{retrieval_time:.1f}s` - Retrieved data autonomously ({len(lambda_calls)} data calls)")
                    
                    # Show unique data retrieval actions
                    seen_actions = {}
                    for event in lambda_calls:
                        action_name = event['name'].split('/')[-1].replace('_', ' ').title()
                        if action_name not in seen_actions:
                            seen_actions[action_name] = []
                        seen_actions[action_name].append(event['time'])
                    
                    for action_name, times in seen_actions.items():
                        if len(times) == 1:
                            st.markdown(f"      - 📊 {action_name} at {times[0]:.1f}s")
                        else:
                            st.markdown(f"      - 📊 {action_name} ({len(times)}x) at {times[0]:.1f}s, {times[-1]:.1f}s")
                    
                    st.markdown(f"  ↓ *Routes to* **Analysis Agent** `~{analysis_time:.1f}s` - Generated insights and formatted response")
                    st.markdown(f"  ↓ *Returns final answer to user*")
                    
                    # Display token usage if available
                    if 'token_usage' in metadata and metadata['token_usage'].get('total_tokens', 0) > 0:
                        token_info = metadata['token_usage']
                        st.markdown("---")
                        st.markdown("### 🎯 Token Usage")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Input Tokens", f"{token_info['total_input_tokens']:,}")
                        with col2:
                            st.metric("Output Tokens", f"{token_info['total_output_tokens']:,}")
                        with col3:
                            st.metric("Total Tokens", f"{token_info['total_tokens']:,}")

    
    elif role == 'progress':
        stage = metadata.get('stage', '')
        badge = get_stage_badge(stage)
        st.markdown(f"""
        <div class="progress-update">
            {badge} {content}
        </div>
        """, unsafe_allow_html=True)
    
    elif role == 'error':
        st.markdown(f"""
        <div class="error-message">
            <strong>⚠️ Error</strong><br>
            {content}
        </div>
        """, unsafe_allow_html=True)


def invoke_browser_agent(prompt: str) -> Dict[str, Any]:
    """
    Invoke the Browser Agent for web search using agentcore CLI.
    
    Args:
        prompt: Search query or browsing instruction
        
    Returns:
        Response from Browser Agent
    """
    try:
        logger.info(f"Invoking Browser Agent with prompt: {prompt[:100]}...")
        
        # Prepare payload
        payload = {
            "action": "custom",
            "prompt": prompt
        }
        
        # Use subprocess to call agentcore CLI
        import subprocess
        
        # Change to Browser Agent directory and invoke
        browser_agent_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Browser Agent")
        
        cmd = [
            "agentcore", "invoke",
            json.dumps(payload)
        ]
        
        result = subprocess.run(
            cmd,
            cwd=browser_agent_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # Parse the output - agentcore returns formatted output
            output = result.stdout
            
            # Try to extract JSON from the output
            # The response is usually in the "Response:" section
            if "Response:" in output:
                response_part = output.split("Response:")[-1].strip()
                try:
                    response_json = json.loads(response_part)
                    return response_json
                except json.JSONDecodeError:
                    # If not JSON, return as text
                    return {
                        "success": True,
                        "content": response_part,
                        "source": "Browser Agent"
                    }
            else:
                return {
                    "success": True,
                    "content": output,
                    "source": "Browser Agent"
                }
        else:
            error_msg = result.stderr or result.stdout
            logger.error(f"Browser Agent invocation failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "message": "Failed to perform web search"
            }
            
    except subprocess.TimeoutExpired:
        logger.error("Browser Agent invocation timed out")
        return {
            "success": False,
            "error": "Request timed out after 60 seconds",
            "message": "Web search took too long"
        }
    except Exception as e:
        logger.error(f"Error invoking Browser Agent: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to perform web search"
        }


def process_web_search(user_input: str):
    """Process web search request using Browser Agent."""
    logger.info(f"Processing web search: {user_input[:100]}...")
    
    # Add user message to chat
    user_message = {
        'role': 'user',
        'content': user_input,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'metadata': {'search_type': 'web'}
    }
    st.session_state.messages.append(user_message)
    
    # Create placeholders
    response_placeholder = st.empty()
    progress_placeholder = st.empty()
    
    # Track timing
    start_time = time.time()
    
    try:
        # Show progress
        with progress_placeholder:
            st.info("🌐 Searching the web with Browser Agent...")
        
        # Invoke Browser Agent
        result = invoke_browser_agent(user_input)
        
        # Calculate latency
        total_latency = time.time() - start_time
        
        # Clear progress
        progress_placeholder.empty()
        
        # Format response based on success
        if result.get('success'):
            content = result.get('content', 'No content returned')
            source = result.get('source', 'Web search')
            prompt = result.get('prompt', user_input)
            
            # Clean up error messages from content if present
            if 'ActAgentFailed' in content or 'HumanValidationError' in content:
                # Extract useful info before the error
                if '\n\n' in content:
                    content = content.split('\n\n')[0]
            
            response_content = f"""**🌐 Web Search Results**

{content}

---
*🔍 Query: {prompt}*  
*📍 Source: {source}*  
*⏱️ Search time: {total_latency:.2f}s*
"""
        else:
            error = result.get('error', 'Unknown error')
            error_type = result.get('error_type', '')
            
            # Make error messages more user-friendly
            if error_type == 'HumanValidationError' or 'HumanValidationError' in error:
                friendly_error = "🚫 **Website Requires Human Verification**\n\nThe website you're trying to access has CAPTCHA or other human verification that prevents automated access. This is common with news websites that want to prevent automated scraping."
                suggestions = """**What you can do:**
- Try a different news source or website
- Search for the topic on a more accessible site like Wikipedia
- For Tesla news, try: "What's on Tesla's official blog?" or "Search Tesla on Wikipedia"
- Specify a particular website known to be accessible: "Get Tesla news from Reuters" or "Find Tesla information on Wikipedia"
- Try rephrasing to focus on specific aspects: "What are Tesla's recent announcements about electric vehicles?"
"""
            elif 'ActAgentFailed' in error:
                friendly_error = "The browser automation encountered an issue. This can happen with complex websites or when the page structure is unexpected."
                suggestions = """**Suggestions:**
- Try rephrasing your query more specifically
- For URL extraction, specify exactly what information you need
- Some websites may be difficult to access automatically
"""
            elif 'timeout' in error.lower():
                friendly_error = "The search took too long and timed out. Please try a simpler query."
                suggestions = """**Suggestions:**
- Try a more specific query
- Focus on a single piece of information
"""
            else:
                friendly_error = error
                suggestions = """**Suggestions:**
- Try rephrasing your query
- Check if the website is accessible
"""
            
            response_content = f"""**⚠️ Web Search Issue**

{friendly_error}

{suggestions}

*Search time: {total_latency:.2f}s*
"""
        
        # Update session metrics
        st.session_state.total_latency += total_latency
        st.session_state.message_count += 1
        
        # Add assistant message
        assistant_message = {
            'role': 'assistant',
            'content': response_content,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'metadata': {
                'latency': total_latency,
                'search_type': 'web',
                'success': result.get('success', False)
            }
        }
        st.session_state.messages.append(assistant_message)
        
        # Display message
        with response_placeholder:
            display_message(assistant_message)
        
        logger.info(f"Web search completed in {total_latency:.2f}s")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error in web search: {e}")
        logger.error(f"Error details: {error_details}")
        
        progress_placeholder.empty()
        
        error_message = {
            'role': 'error',
            'content': f"**Web Search Error**\n\n{str(e)}\n\nPlease try again or contact support.",
            'metadata': {'error_type': type(e).__name__}
        }
        
        with response_placeholder:
            display_message(error_message)
        
        st.session_state.messages.append(error_message)


def process_user_message(user_input: str):
    """Process user message and get response from Bedrock agent."""
    logger.info(f"Processing user message: {user_input[:100]}...")
    
    # Add user message to chat
    user_message = {
        'role': 'user',
        'content': user_input,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'metadata': {}
    }
    st.session_state.messages.append(user_message)
    logger.info(f"Added user message to history. Total messages: {len(st.session_state.messages)}")
    
    # Create placeholders
    response_placeholder = st.empty()
    progress_placeholder = st.empty()
    
    # Track timing and events
    start_time = time.time()
    timeline_events = []
    agent_times = {}
    last_progress_update = start_time
    current_progress = ""
    current_agent_phase = "coordinator"  # Track which agent is likely working
    
    # Collect response content
    response_content = ""
    
    try:
        # Show initial progress
        current_progress = "🤖 Processing your request..."
        with progress_placeholder:
            st.info(current_progress)
        
        logger.info(f"Invoking Bedrock agent. Session ID: {st.session_state.session_id}, Agent ID: {st.session_state.agent_id}")
        
        # Invoke Bedrock agent with streaming
        response = st.session_state.bedrock_client.invoke_agent(
            agentId=st.session_state.agent_id,
            agentAliasId=st.session_state.agent_alias_id,
            sessionId=st.session_state.session_id,
            inputText=user_input,
            enableTrace=True,
            sessionState={
                'sessionAttributes': {
                    'org_id': st.session_state.org_id,
                    'user_id': st.session_state.user_id
                }
            }
        )
        
        # Process streaming response
        event_stream = response['completion']
        logger.info("Started processing event stream")
        event_count = 0
        
        for event in event_stream:
            event_count += 1
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    chunk_text = chunk['bytes'].decode('utf-8')
                    response_content += chunk_text
                    logger.debug(f"Received chunk: {len(chunk_text)} bytes")
                    
                    # Update response display
                    with response_placeholder.container():
                        st.markdown(f"""
                        <div class="chat-message assistant-message">
                            <div><strong>QueenAI Assistant</strong></div>
                            <div style="margin-top: 0.5rem;">{response_content}</div>
                        </div>
                        """, unsafe_allow_html=True)
            
            elif 'trace' in event:
                trace_data = event['trace']
                if 'trace' in trace_data:
                    trace = trace_data['trace']
                    event_time = time.time() - start_time
                    
                    # Parse orchestration trace
                    if 'orchestrationTrace' in trace:
                        orch_trace = trace['orchestrationTrace']
                        
                        # Check for agent collaboration at multiple levels
                        if 'agentCollaboratorInvocationTrace' in orch_trace:
                            collab_trace = orch_trace['agentCollaboratorInvocationTrace']
                            agent_name = collab_trace.get('agentCollaboratorName', collab_trace.get('agentName'))
                            
                            if agent_name and agent_name not in agent_times:
                                agent_times[agent_name] = {'start': event_time}
                                timeline_events.append({
                                    'type': 'agent',
                                    'name': agent_name,
                                    'time': event_time
                                })
                                
                                # Update agent phase
                                if 'DataSource' in agent_name:
                                    current_agent_phase = 'data_source'
                                elif 'SmartRetrieval' in agent_name or 'Retrieval' in agent_name:
                                    current_agent_phase = 'retrieval'
                                elif 'Analysis' in agent_name:
                                    current_agent_phase = 'analysis'
                                
                                # Update progress
                                with progress_placeholder:
                                    st.info(f"🤖 {agent_name} is working...")
                        
                        # Check model invocation (thinking)
                        if 'modelInvocationInput' in orch_trace:
                            # Infer which agent based on phase
                            agent_name = {
                                'coordinator': 'Coordinator',
                                'data_source': 'Data Source Agent',
                                'retrieval': 'Smart Retrieval Agent',
                                'analysis': 'Analysis Agent'
                            }.get(current_agent_phase, 'Agent')
                            
                            new_progress = f"🧠 {agent_name} is thinking..."
                            # Only update if enough time has passed or it's a different message
                            if new_progress != current_progress and (time.time() - last_progress_update) > 1.0:
                                current_progress = new_progress
                                last_progress_update = time.time()
                                with progress_placeholder:
                                    st.info(current_progress)
                        
                        # Action group invocation (Lambda calls)
                        if 'invocationInput' in orch_trace:
                            inv_input = orch_trace['invocationInput']
                            if 'actionGroupInvocationInput' in inv_input:
                                action_input = inv_input['actionGroupInvocationInput']
                                action_group = action_input.get('actionGroupName', 'Unknown')
                                api_path = action_input.get('apiPath', '')
                                
                                # Update agent phase based on Lambda call
                                if 'GetKpiData' in action_group or 'ExecuteSql' in action_group:
                                    current_agent_phase = 'retrieval'
                                
                                timeline_events.append({
                                    'type': 'lambda',
                                    'name': f"{action_group}{api_path}",
                                    'time': event_time
                                })
                                
                                # Update progress with minimum display time
                                new_progress = f"📊 Smart Retrieval Agent calling {action_group}..."
                                if new_progress != current_progress:
                                    current_progress = new_progress
                                    last_progress_update = time.time()
                                    with progress_placeholder:
                                        st.info(current_progress)
                                
                                # After data retrieval, next thinking is likely analysis
                                if len(timeline_events) > 2:
                                    current_agent_phase = 'analysis'
        
        # Clear progress
        progress_placeholder.empty()
        
        # Calculate total latency
        total_latency = time.time() - start_time
        end_time = time.time()
        
        logger.info(f"Completed processing. Events: {event_count}, Latency: {total_latency:.2f}s, Response length: {len(response_content)} chars")
        
        # Fetch token usage from CloudWatch (this adds ~1-2s)
        with st.spinner("📊 Fetching token usage..."):
            token_usage = fetch_token_usage_from_cloudwatch(
                st.session_state.session_id,
                start_time,
                end_time
            )
        
        # Update session metrics
        st.session_state.total_latency += total_latency
        st.session_state.message_count += 1
        st.session_state.last_token_usage = token_usage
        
        # Parse JSON response from coordinator
        suggested_questions = []
        display_content = response_content  # Default to raw content
        
        try:
            import re
            
            # The Coordinator now returns a JSON response in ```json``` code blocks
            # Format: ```json\n{"response": "...", "suggested_questions": [...]}\n```
            
            json_pattern = r'```json\s*(\{.*?\})\s*```'
            json_match = re.search(json_pattern, response_content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                try:
                    response_data = json.loads(json_str)
                    
                    # Extract the response text
                    if 'response' in response_data:
                        display_content = response_data['response']
                        logger.info("Extracted response from JSON")
                    
                    # Extract suggested questions
                    if 'suggested_questions' in response_data:
                        suggested_questions = response_data['suggested_questions']
                        if isinstance(suggested_questions, list):
                            logger.info(f"Extracted {len(suggested_questions)} questions from JSON")
                        else:
                            logger.warning("suggested_questions is not a list")
                            suggested_questions = []
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON response: {e}")
                    logger.debug(f"JSON string: {json_str[:200]}")
            else:
                logger.debug("No JSON code block found in response, using raw content")
            
            # Update session state with new suggested questions
            if suggested_questions:
                st.session_state.suggested_questions = suggested_questions
            else:
                logger.debug("No suggested questions found in response")
                
        except Exception as e:
            logger.warning(f"Failed to parse response: {e}")
        
        # Use the extracted display content instead of raw response_content
        response_content = display_content
        
        # Add assistant message to chat
        assistant_message = {
            'role': 'assistant',
            'content': response_content,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'metadata': {
                'latency': total_latency,
                'timeline': timeline_events,
                'suggested_questions': suggested_questions,
                'token_usage': token_usage
            }
        }
        st.session_state.messages.append(assistant_message)
        logger.info(f"Added assistant message to history. Total messages: {len(st.session_state.messages)}")
        
        # Display final message with timeline
        with response_placeholder:
            display_message(assistant_message)
        
        logger.info("Successfully displayed final message")
    
    except Exception as e:
        # Handle unexpected errors
        import traceback
        error_details = traceback.format_exc()
        error_str = str(e)
        
        logger.error(f"Error processing message: {error_str}")
        logger.error(f"Error details: {error_details}")
        
        progress_placeholder.empty()
        
        # Provide user-friendly error messages
        if 'Read timed out' in error_str or 'timeout' in error_str.lower():
            friendly_message = """
            **Request Timed Out**
            
            The request took too long to complete. This can happen with complex queries.
            
            **What you can do:**
            - Try again - it often works on retry
            - Try a simpler or more specific question
            - Check if the database is responding slowly
            """
        elif 'dependencyFailedException' in error_str or 'service unavailable' in error_str.lower():
            friendly_message = """
            **Service Temporarily Unavailable**
            
            One of the backend agents is experiencing high load. This is typically temporary.
            
            **What you can do:**
            - Wait 30 seconds and try again
            - Try a simpler question first
            - Check the sidebar for connection status
            """
        elif 'AccessDenied' in error_str or 'accessDeniedException' in error_str:
            friendly_message = """
            **Permission Error**
            
            The agent doesn't have permission to access a required service.
            
            **What you can do:**
            - Contact your administrator
            - Check IAM role permissions
            
            **Technical details:** Agent role needs bedrock:InvokeModel permission.
            """
        elif 'ThrottlingException' in error_str or 'TooManyRequests' in error_str:
            friendly_message = """
            **Rate Limit Exceeded**
            
            Too many requests in a short time.
            
            **What you can do:**
            - Wait a few seconds and try again
            - The system will automatically retry
            """
        else:
            friendly_message = f"""
            **An Error Occurred**
            
            {error_str}
            
            **What you can do:**
            - Try rephrasing your question
            - Check the connection status in the sidebar
            - Clear chat and start a new session
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
            
            # Add retry button for transient errors
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
        
        # Search Mode Selector
        st.subheader("🔍 Search Mode")
        search_mode = st.radio(
            "Choose data source:",
            options=['internal', 'web'],
            format_func=lambda x: "📊 Internal Data (Bedrock Agent)" if x == 'internal' else "🌐 Web Search (Browser Agent)",
            key='search_mode_radio',
            help="Internal: Query your business data\nWeb: Search the internet for external information"
        )
        st.session_state.search_mode = search_mode
        
        if search_mode == 'web':
            st.info("🌐 **Web Search Mode**\n\nUsing Browser Agent with Nova Act to search the web and extract information.")
        else:
            st.info("📊 **Internal Data Mode**\n\nUsing Bedrock Agents to query your business data.")
        
        st.divider()
        
        # Session info
        st.subheader("Session Information")
        st.text(f"Session ID: {st.session_state.session_id[:8]}...")
        st.text(f"Org ID: {st.session_state.org_id}")
        st.text(f"User ID: {st.session_state.user_id}")
        
        # Metrics
        st.subheader("📊 Metrics")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Messages", st.session_state.message_count)
        with col2:
            avg_latency = (st.session_state.total_latency / st.session_state.message_count 
                          if st.session_state.message_count > 0 else 0)
            st.metric("Avg Latency", f"{avg_latency:.2f}s")
        
        # Stage latencies
        if st.session_state.stage_latencies:
            st.subheader("⏱️ Last Query Breakdown")
            for stage, latency in st.session_state.stage_latencies.items():
                st.text(f"{stage.replace('_', ' ').title()}: {latency:.2f}s")
        
        st.divider()
        
        # Dynamic questions: Show follow-ups if available, otherwise show examples
        if st.session_state.suggested_questions and st.session_state.search_mode == 'internal':
            st.subheader("💡 Suggested Follow-up Questions")
            st.caption(f"✨ {len(st.session_state.suggested_questions)} AI-suggested questions based on your conversation")
            questions_to_show = st.session_state.suggested_questions
        else:
            st.subheader("💡 Example Questions")
            if st.session_state.search_mode == 'web':
                questions_to_show = [
                    "What's the latest news about Tesla?",
                    "Get the title from https://www.ctvnews.ca/",
                    "Search for Amazon's current stock price",
                    "Find recent news about Microsoft acquisitions",
                    "What's happening with Apple today?"
                ]
            else:
                questions_to_show = [
                    "What were the total sales last month?",
                    "Show me the top 5 stores by revenue",
                    "What is the average transaction value?",
                    "Compare sales between Q1 and Q2 in 2023",
                    "Which products have the highest margin?"
                ]
        
        for question in questions_to_show:
            if st.button(question, key=f"question_{hash(question)}", use_container_width=True):
                st.session_state.user_input = question
                st.rerun()
        
        st.divider()
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", use_container_width=True):
            old_session_id = st.session_state.session_id
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.total_latency = 0
            st.session_state.message_count = 0
            st.session_state.stage_latencies = {}
            st.session_state.suggested_questions = []  # Clear suggested questions
            logger.info(f"Chat cleared. Old session: {old_session_id}, New session: {st.session_state.session_id}")
            st.rerun()
        
        # Test connection
        if st.button("🔌 Test Connection", use_container_width=True):
            with st.spinner("Testing connection..."):
                try:
                    # Test by listing agents
                    bedrock_agent = boto3.client(
                        'bedrock-agent',
                        region_name=os.getenv('AWS_REGION', 'us-west-2')
                    )
                    bedrock_agent.list_agents(maxResults=1)
                    st.success(f"✅ Connected to Bedrock\nAgent ID: {st.session_state.agent_id}\nAlias ID: {st.session_state.agent_alias_id}")
                except Exception as e:
                    st.error(f"❌ Connection failed: {str(e)}")
    
    # Main chat area
    chat_container = st.container()
    
    # Display chat history
    with chat_container:
        if not st.session_state.messages:
            if st.session_state.search_mode == 'web':
                st.info("🌐 **Web Search Mode Active**\n\nI can search the web, extract information from URLs, and find real-time data using browser automation.\n\nTry asking about company news, stock prices, or paste a URL to extract information!")
            else:
                st.info("📊 **Internal Data Mode Active**\n\nI can help you analyze your business data, KPIs, and transactions.\n\nAsk me about sales, revenue, stores, or any business metrics!")
        else:
            for message in st.session_state.messages:
                display_message(message)
    
    # Chat input
    st.divider()
    
    # Check if there's a pre-filled input from example questions
    default_input = st.session_state.get('user_input', '')
    if default_input:
        del st.session_state.user_input
    
    # Dynamic placeholder based on search mode
    if st.session_state.search_mode == 'web':
        placeholder = "Search the web or enter a URL to extract information..."
    else:
        placeholder = "Ask a question about your business data..."
    
    user_input = st.chat_input(placeholder, key="chat_input")
    
    # Process input from either chat_input or example button
    input_to_process = user_input or default_input
    
    if input_to_process:
        logger.info(f"Processing input in {st.session_state.search_mode} mode: {input_to_process[:50]}...")
        with chat_container:
            # Route to appropriate handler based on search mode
            if st.session_state.search_mode == 'web':
                process_web_search(input_to_process)
            else:
                process_user_message(input_to_process)
        logger.info("Rerunning Streamlit app to display new message")
        st.rerun()


if __name__ == "__main__":
    main()
