"""
Lambda function to invoke the Browser Agent (AgentCore Runtime)
This Lambda acts as a bridge between Bedrock Agent and the Browser Agent
"""

import json
import boto3
import os
import logging
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Bedrock AgentCore Runtime client
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

# Browser Agent ARN from environment variable
BROWSER_AGENT_ARN = os.environ.get(
    'BROWSER_AGENT_ARN',
    os.environ.get('BROWSER_AGENT_ARN', 'arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:runtime/browser_agent-ID')
)


def invoke_browser_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invoke the Browser Agent via Bedrock AgentCore Runtime
    
    Args:
        payload: Dictionary with action and parameters
        
    Returns:
        Response from Browser Agent
    """
    try:
        logger.info(f"Invoking Browser Agent with payload: {payload}")
        
        # Invoke the Browser Agent
        response = bedrock_agent_runtime.invoke_agent_runtime(
            agentRuntimeArn=BROWSER_AGENT_ARN,
            runtimeSessionId=f"external-search-{os.urandom(8).hex()}",
            inputText=json.dumps(payload)
        )
        
        # Parse the response
        result_text = response.get('completion', '')
        
        # Try to parse as JSON
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            result = {"content": result_text, "success": True}
        
        logger.info(f"Browser Agent response: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error invoking Browser Agent: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to invoke Browser Agent"
        }


def search_company_info(company_name: str, search_type: str = "general") -> Dict[str, Any]:
    """
    Search for company information using the Browser Agent
    
    Args:
        company_name: Name of the company to search for
        search_type: Type of search (news, general, financial)
        
    Returns:
        Search results with company information
    """
    payload = {
        "action": "search_company",
        "company_name": company_name,
        "search_type": search_type
    }
    
    return invoke_browser_agent(payload)


def extract_web_data(url: str, extraction_instructions: str) -> Dict[str, Any]:
    """
    Navigate to a URL and extract specific information
    
    Args:
        url: URL to navigate to
        extraction_instructions: Instructions for what data to extract
        
    Returns:
        Extracted data from the webpage
    """
    payload = {
        "action": "extract_data",
        "url": url,
        "extraction_instructions": extraction_instructions
    }
    
    return invoke_browser_agent(payload)


def custom_browse(prompt: str) -> Dict[str, Any]:
    """
    Execute a custom browsing action with natural language
    
    Args:
        prompt: Natural language instruction for browsing
        
    Returns:
        Result of the browsing action
    """
    payload = {
        "action": "custom",
        "prompt": prompt
    }
    
    return invoke_browser_agent(payload)


def lambda_handler(event, context):
    """
    Lambda handler for Bedrock Agent action group
    
    Expected event structure from Bedrock Agent:
    {
        "actionGroup": "external_search_actions",
        "apiPath": "/search_company_info" or "/extract_web_data" or "/custom_browse",
        "httpMethod": "POST",
        "parameters": [
            {"name": "company_name", "value": "Amazon"},
            {"name": "search_type", "value": "news"}
        ]
    }
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Extract action information
        api_path = event.get('apiPath', '')
        parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
        
        # Route to appropriate function
        if api_path == '/search_company_info':
            company_name = parameters.get('company_name', '')
            search_type = parameters.get('search_type', 'general')
            
            if not company_name:
                result = {
                    "success": False,
                    "error": "Missing required parameter: company_name"
                }
            else:
                result = search_company_info(company_name, search_type)
                
        elif api_path == '/extract_web_data':
            url = parameters.get('url', '')
            extraction_instructions = parameters.get('extraction_instructions', '')
            
            if not url or not extraction_instructions:
                result = {
                    "success": False,
                    "error": "Missing required parameters: url and extraction_instructions"
                }
            else:
                result = extract_web_data(url, extraction_instructions)
                
        elif api_path == '/custom_browse':
            prompt = parameters.get('prompt', '')
            
            if not prompt:
                result = {
                    "success": False,
                    "error": "Missing required parameter: prompt"
                }
            else:
                result = custom_browse(prompt)
                
        else:
            result = {
                "success": False,
                "error": f"Unknown API path: {api_path}"
            }
        
        # Format response for Bedrock Agent
        response = {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', ''),
                'apiPath': api_path,
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 200 if result.get('success') else 400,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(result)
                    }
                }
            }
        }
        
        logger.info(f"Returning response: {json.dumps(response)}")
        return response
        
    except Exception as e:
        logger.error(f"Lambda handler error: {e}", exc_info=True)
        
        # Return error response
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', ''),
                'apiPath': event.get('apiPath', ''),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({
                            'success': False,
                            'error': str(e),
                            'message': 'Internal server error'
                        })
                    }
                }
            }
        }
