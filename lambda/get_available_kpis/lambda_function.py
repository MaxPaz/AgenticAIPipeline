"""
Get Available KPIs Lambda Function

This Lambda function is an action group for the Data Source Agent.
It returns all available KPIs for a given customer, allowing the agent
to choose the appropriate KPIs based on the user's question.

Action Group: get_available_kpis
Parameters:
- customer: Customer name (e.g., "Customer A", "Customer B") or "all" for all customers

The function:
1. Loads KPI metadata from JSON file
2. Filters by customer (page_name field)
3. Returns compact list with KPI ID, name, and short definition
4. Agent (Claude) selects appropriate KPIs based on user question
"""

import json
import os
from typing import List, Dict, Any, Optional


def load_kpi_metadata() -> List[Dict[str, Any]]:
    """
    Load KPI metadata from JSON file.
    
    Returns:
        List of KPI metadata dictionaries
    """
    # Try multiple paths
    possible_paths = [
        # Lambda path
        os.path.join(os.path.dirname(__file__), 'metadata', 'kpi_meta_data.json'),
        # Local testing from lambda directory
        os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'kpi_meta_data.json'),
        # Absolute path from project root
        'metadata/kpi_meta_data.json'
    ]
    
    for metadata_path in possible_paths:
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    raise FileNotFoundError(f"Could not find kpi_meta_data.json in any of: {possible_paths}")


def extract_customer_from_page_name(page_name: str) -> str:
    """
    Extract customer name from page_name field.
    
    Args:
        page_name: e.g., "Draft Customer A", "Draft Customer B"
        
    Returns:
        Customer name: e.g., "Customer A", "Customer B"
    """
    # Remove "Draft " prefix if present
    if page_name.startswith("Draft "):
        return page_name[6:]
    return page_name


def filter_kpis_by_customer(
    kpis: List[Dict[str, Any]],
    customer: str
) -> List[Dict[str, Any]]:
    """
    Filter KPIs by customer name.
    
    Args:
        kpis: List of all KPIs
        customer: Customer name or "all"
        
    Returns:
        Filtered list of KPIs
    """
    if customer.lower() == "all":
        return kpis
    
    # Case-insensitive matching
    customer_lower = customer.lower()
    
    filtered = []
    for kpi in kpis:
        page_name = kpi.get('page_name', '')
        extracted_customer = extract_customer_from_page_name(page_name)
        
        if customer_lower in extracted_customer.lower():
            filtered.append(kpi)
    
    return filtered


def format_kpis_for_agent(kpis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format KPIs into compact structure for agent consumption.
    
    Args:
        kpis: List of KPI metadata
        
    Returns:
        Compact list with only essential fields
    """
    formatted = []
    
    for kpi in kpis:
        formatted.append({
            'kpi_id': kpi['kpi_id'],
            'kpi_name': kpi['kpi_name'],
            'definition': kpi['short_definition'],
            'unit': kpi['unit'],
            'group': kpi.get('group_name', 'Unknown')
        })
    
    return formatted


def lambda_handler(event, context):
    """
    Lambda handler for get_available_kpis action group.
    
    Args:
        event: Lambda event containing action group parameters
        context: Lambda context
        
    Returns:
        Action group response with available KPIs
    """
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Extract parameters from event
        parameters = {}
        
        if 'requestBody' in event and 'content' in event['requestBody']:
            # New Bedrock format
            content = event['requestBody']['content']
            if 'application/json' in content and 'properties' in content['application/json']:
                parameters = {p['name']: p['value'] for p in content['application/json']['properties']}
        elif 'parameters' in event:
            # Old format
            parameters = {p['name']: p['value'] for p in event['parameters']}
        else:
            # Fallback
            parameters = event
        
        # Get customer parameter
        customer = parameters.get('customer', 'all')
        
        print(f"Parameters: customer={customer}")
        
        # Load all KPIs
        all_kpis = load_kpi_metadata()
        print(f"Loaded {len(all_kpis)} total KPIs")
        
        # Filter by customer
        filtered_kpis = filter_kpis_by_customer(all_kpis, customer)
        print(f"Filtered to {len(filtered_kpis)} KPIs for customer: {customer}")
        
        # Format for agent
        formatted_kpis = format_kpis_for_agent(filtered_kpis)
        
        # Prepare response
        response_body = {
            'customer': customer,
            'kpi_count': len(formatted_kpis),
            'kpis': formatted_kpis
        }
        
        # Return response in Bedrock action group format
        response = {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'GetAvailableKpisActionGroup'),
                'apiPath': event.get('apiPath', '/get_available_kpis'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 200,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(response_body, default=str)
                    }
                }
            }
        }
        
        return response
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'GetAvailableKpisActionGroup'),
                'apiPath': event.get('apiPath', '/get_available_kpis'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({
                            'error': str(e),
                            'kpis': []
                        })
                    }
                }
            }
        }
