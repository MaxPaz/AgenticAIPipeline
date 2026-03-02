"""
Browser Agent for Bedrock AgentCore Runtime

This agent provides external web search and information extraction capabilities
using Bedrock AgentCore Browser with Nova Act.
"""

import os
import logging
import threading
import sys
from typing import Dict, Any
from bedrock_agentcore import BedrockAgentCoreApp, PingStatus
from browser_session_manager import BrowserSessionManager, ExternalSearchTool

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Log module initialization
logger.info("="*80)
logger.info("BROWSER AGENT MODULE INITIALIZING")
logger.info(f"Python version: {sys.version}")
logger.info(f"__name__ = {__name__}")
logger.info(f"__file__ = {__file__}")
logger.info("="*80)

# Initialize Bedrock AgentCore App
logger.info("Initializing BedrockAgentCoreApp...")
app = BedrockAgentCoreApp()
logger.info("BedrockAgentCoreApp initialized successfully")

# Global variables for concurrency control
_agent_busy = False
_active_requests = 0
_request_lock = threading.Lock()
_max_concurrent_requests = 1  # Only allow 1 concurrent request

logger.info("Setting up ping handler...")
@app.ping
def health_check():
    """Custom ping handler to report agent health status"""
    status = PingStatus.HEALTHY_BUSY if _agent_busy else PingStatus.HEALTHY
    logger.debug(f"Ping handler called - returning {status} (busy={_agent_busy}, active={_active_requests})")
    return status

logger.info("Ping handler registered")


logger.info("Setting up entrypoint handler...")
@app.entrypoint
def invoke(payload: Dict[str, Any], context=None) -> Dict[str, Any]:
    """
    Main entry point for the Browser Agent when invoked by Bedrock.
    
    This function is called by AgentCore Runtime when the agent is invoked.
    
    Args:
        payload: Dict containing:
            - prompt: str - The user's request
            - action: str - The action to perform ("search_company", "extract_data", "custom")
            - company_name: str - (optional) Company name for search
            - search_type: str - (optional) Type of search ("news", "general", "financial")
            - url: str - (optional) URL for data extraction
            - extraction_instructions: str - (optional) Instructions for extraction
            
    Returns:
        Dict containing the response with success status and content
    """
    global _agent_busy, _active_requests
    
    logger.info("="*80)
    logger.info("ENTRYPOINT INVOKED")
    logger.info(f"Payload received: {payload}")
    logger.info(f"Context: {context}")
    logger.info("="*80)
    
    # Check if we're at max capacity
    with _request_lock:
        logger.debug(f"Checking capacity: active={_active_requests}, max={_max_concurrent_requests}")
        if _active_requests >= _max_concurrent_requests:
            logger.warning(f"Agent at max capacity ({_active_requests} active requests), rejecting new request")
            return {
                "success": False,
                "error": "Agent busy",
                "message": "Agent is currently processing another request. Please try again."
            }
        _active_requests += 1
        _agent_busy = True
        logger.info(f"Request accepted. Active requests now: {_active_requests}")
    
    try:
        
        # Get configuration from environment
        region = os.getenv("AWS_REGION", "us-west-2")
        nova_act_api_key = os.getenv("NOVA_ACT_API_KEY")
        
        logger.info(f"Configuration: region={region}, nova_act_key={'SET' if nova_act_api_key else 'NOT SET'}")
        
        if not nova_act_api_key:
            logger.error("NOVA_ACT_API_KEY not configured")
            return {
                "success": False,
                "error": "NOVA_ACT_API_KEY not configured",
                "message": "Please set NOVA_ACT_API_KEY environment variable"
            }
        
        # Determine action
        action = payload.get("action", "custom")
        prompt = payload.get("prompt", "")
        
        logger.info(f"Action: {action}, Prompt: {prompt}")
        
        # Initialize search tool
        search_tool = ExternalSearchTool(region=region, nova_act_api_key=nova_act_api_key)
        
        if action == "search_company":
            # Company information search
            company_name = payload.get("company_name", "")
            search_type = payload.get("search_type", "general")
            
            if not company_name:
                return {
                    "success": False,
                    "error": "Missing company_name parameter"
                }
            
            logger.info(f"Searching for company: {company_name}, type: {search_type}")
            result = search_tool.search_company_info(company_name, search_type)
            return result
            
        elif action == "extract_data":
            # Web data extraction
            url = payload.get("url", "")
            extraction_instructions = payload.get("extraction_instructions", "")
            
            if not url or not extraction_instructions:
                return {
                    "success": False,
                    "error": "Missing url or extraction_instructions parameter"
                }
            
            logger.info(f"Extracting data from: {url}")
            result = search_tool.extract_web_data(url, extraction_instructions)
            return result
            
        elif action == "custom" or prompt:
            # Custom browser action with natural language prompt
            if not prompt:
                logger.error("Missing prompt parameter for custom action")
                return {
                    "success": False,
                    "error": "Missing prompt parameter for custom action"
                }
            
            logger.info(f"Executing custom action: {prompt}")
            
            # Use browser session manager directly for custom actions
            logger.info("Creating BrowserSessionManager...")
            manager = BrowserSessionManager(region=region, nova_act_api_key=nova_act_api_key)
            
            try:
                logger.info("Creating browser session...")
                with manager.create_browser_session() as nova_act:
                    logger.info("Browser session created, executing Nova Act...")
                    
                    # Enhanced prompt to help Nova Act handle interactive elements and suggest specific strategies
                    enhanced_prompt = f"{prompt}. Try these strategies in order:\n1. Use a search engine like DuckDuckGo (https://duckduckgo.com) which is less likely to show CAPTCHAs\n2. If you encounter cookie consent dialogs, accept them\n3. If you encounter CAPTCHAs or other blocking elements, try searching on Wikipedia or a different news source\n4. If blocked by one site, try another news source\n5. Focus on getting the key information rather than perfect formatting"
                    logger.debug(f"Executing enhanced prompt: {enhanced_prompt}")
                    
                    result = nova_act.act(enhanced_prompt)
                    logger.info(f"Nova Act completed successfully")
                    
                    response = {
                        "success": True,
                        "prompt": prompt,
                        "content": result.response if hasattr(result, 'response') else str(result),
                        "source": "Browser automation via Nova Act"
                    }
                    logger.info(f"Returning response: {response}")
                    return response
            except Exception as e:
                error_str = str(e)
                logger.error(f"Error executing custom action: {error_str}", exc_info=True)
                
                # Check if it's a HumanValidationError
                if "HumanValidationError" in error_str:
                    # Provide more helpful guidance for CAPTCHA issues
                    return {
                        "success": False,
                        "prompt": prompt,
                        "error": "The website requires human verification (CAPTCHA or similar). This content cannot be accessed automatically. Try rephrasing your query to specify a different news source, such as 'What does Wikipedia say about Tesla?' or 'Get Tesla news from Reuters'.",
                        "error_type": "HumanValidationError"
                    }
                
                return {
                    "success": False,
                    "prompt": prompt,
                    "error": error_str
                }
        
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "message": "Supported actions: search_company, extract_data, custom"
            }
            
    except Exception as e:
        logger.error(f"Browser Agent error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": "An error occurred while processing the request"
        }
    finally:
        # Always decrement active requests counter
        with _request_lock:
            _active_requests -= 1
            if _active_requests == 0:
                _agent_busy = False
            logger.info(f"Request completed (active requests: {_active_requests})")
            logger.info("="*80)


logger.info("Entrypoint handler registered")
logger.info("="*80)
logger.info("BROWSER AGENT MODULE INITIALIZATION COMPLETE")
logger.info("="*80)

# For testing locally - DISABLED to prevent automatic execution in container
# Use test_local.py for local testing instead
# if __name__ == "__main__":
#     # Test the agent locally
#     test_payload = {
#         "action": "custom",
#         "prompt": "Go to https://aws.amazon.com and tell me what services are featured on the homepage"
#     }
#     
#     print("Testing Browser Agent locally...")
#     print(f"Payload: {test_payload}")
#     print("\nResponse:")
#     response = invoke(test_payload)
#     print(response)
