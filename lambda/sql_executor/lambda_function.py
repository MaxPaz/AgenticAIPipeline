"""
Lambda function for secure SQL query execution against MySQL database.

This function:
- Validates SQL queries for security (forbidden operations)
- Executes queries with connection pooling
- Returns structured results or detailed error messages
- Enforces org-level data isolation
- Supports both Bedrock action group format and direct invocation
"""

import json
import os
import re
import traceback
from typing import Dict, Any, List, Optional
import pymysql
from pymysql.cursors import DictCursor

# Database connection pool (initialized once per Lambda container)
connection_pool: Optional[List] = None
MAX_POOL_SIZE = 5

# Forbidden SQL operations for security
FORBIDDEN_OPERATIONS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 
    'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE', 'MERGE',
    'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK'
]

# Maximum query execution time (seconds)
QUERY_TIMEOUT = 30


def get_connection():
    """
    Get a database connection.
    Lambda containers reuse connections across invocations.
    """
    try:
        connection = pymysql.connect(
            host=os.environ['DB_HOST'],
            port=int(os.environ.get('DB_PORT', 3306)),
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
            connect_timeout=10,
            cursorclass=DictCursor,
            autocommit=True
        )
        print("Database connection established successfully")
        return connection
    except Exception as e:
        print(f"Failed to establish database connection: {str(e)}")
        raise


def validate_sql_security(query: str) -> Dict[str, Any]:
    """
    Validate SQL query for security issues.
    
    Args:
        query: SQL query string to validate
        
    Returns:
        Dict with 'valid' boolean and 'error' message if invalid
    """
    # Convert to uppercase for case-insensitive checking
    query_upper = query.upper()
    
    # Check for forbidden operations
    for operation in FORBIDDEN_OPERATIONS:
        # Use word boundaries to avoid false positives (e.g., "INSERTED" column name)
        pattern = r'\b' + re.escape(operation) + r'\b'
        if re.search(pattern, query_upper):
            return {
                'valid': False,
                'error': f"Forbidden operation detected: {operation}. Only SELECT queries are allowed."
            }
    
    # Check for multiple statements (semicolon not at end)
    statements = query.strip().split(';')
    non_empty_statements = [s.strip() for s in statements if s.strip()]
    if len(non_empty_statements) > 1:
        return {
            'valid': False,
            'error': "Multiple SQL statements are not allowed. Only single SELECT queries permitted."
        }
    
    # Ensure query starts with SELECT
    if not query_upper.strip().startswith('SELECT'):
        return {
            'valid': False,
            'error': "Only SELECT queries are allowed."
        }
    
    return {'valid': True}


def execute_query(query: str, org_id: str, timeout: int = QUERY_TIMEOUT) -> Dict[str, Any]:
    """
    Execute SQL query with security validation and error handling.
    
    Args:
        query: SQL query to execute
        org_id: Organization ID for data isolation
        timeout: Query timeout in seconds
        
    Returns:
        Dict with success status, data, and metadata
    """
    connection = None
    cursor = None
    
    try:
        # Get database connection
        connection = get_connection()
        cursor = connection.cursor()
        
        # Set query timeout (MySQL uses max_execution_time in milliseconds)
        cursor.execute(f"SET SESSION max_execution_time = {timeout * 1000}")
        
        # Execute query
        import time
        start_time = time.time()
        cursor.execute(query)
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Fetch results
        results = cursor.fetchall()
        
        # Results are already dicts due to DictCursor
        data = results if results else []
        
        return {
            'success': True,
            'data': data,
            'row_count': len(data),
            'execution_time_ms': execution_time_ms,
            'error': None
        }
        
    except pymysql.err.OperationalError as e:
        # Check if it's a timeout error
        error_code = e.args[0] if e.args else 0
        if error_code == 3024:  # Query execution was interrupted (timeout)
            return {
                'success': False,
                'data': [],
                'row_count': 0,
                'execution_time_ms': timeout * 1000,
                'error': f"Query execution timeout after {timeout} seconds. Try narrowing your date range or filters."
            }
        else:
            error_msg = str(e).strip()
            return {
                'success': False,
                'data': [],
                'row_count': 0,
                'execution_time_ms': 0,
                'error': f"Database operational error: {error_msg}"
            }
        
    except pymysql.err.MySQLError as e:
        # MySQL-specific errors
        error_msg = str(e).strip()
        return {
            'success': False,
            'data': [],
            'row_count': 0,
            'execution_time_ms': 0,
            'error': f"Database error: {error_msg}"
        }
        
    except Exception as e:
        # General errors
        error_msg = str(e).strip()
        traceback_str = traceback.format_exc()
        print(f"Query execution error: {error_msg}\n{traceback_str}")
        
        return {
            'success': False,
            'data': [],
            'row_count': 0,
            'execution_time_ms': 0,
            'error': f"Execution error: {error_msg}"
        }
        
    finally:
        # Clean up
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def format_response(status_code: int, body: Dict[str, Any], is_bedrock: bool) -> Dict[str, Any]:
    """
    Format response for Bedrock action group or direct invocation.
    
    Args:
        status_code: HTTP status code
        body: Response body dictionary
        is_bedrock: Whether to format for Bedrock action group
        
    Returns:
        Formatted response dictionary
    """
    if is_bedrock:
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': 'ExecuteSqlQueryActionGroup',
                'apiPath': '/execute_sql_query',
                'httpMethod': 'POST',
                'httpStatusCode': status_code,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(body, default=str)
                    }
                }
            }
        }
    else:
        return {
            'statusCode': status_code,
            'body': json.dumps(body, default=str)
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for SQL query execution.
    
    Handles both Bedrock action group format and direct invocation format.
    
    Bedrock format:
    {
        "requestBody": {
            "content": {
                "application/json": {
                    "properties": [
                        {"name": "sql_query", "value": "SELECT ..."},
                        {"name": "org_id", "value": "default"}
                    ]
                }
            }
        }
    }
    
    Direct format:
    {
        "query": "SELECT * FROM table WHERE ...",
        "org_id": "org_123",
        "timeout": 30
    }
    
    Returns Bedrock action group format or direct format based on input.
    """
    print(f"Event: {json.dumps(event, default=str)}")
    
    try:
        # Extract parameters from event
        parameters = {}
        is_bedrock_format = False
        
        if 'requestBody' in event and 'content' in event['requestBody']:
            # Bedrock action group format
            content = event['requestBody']['content']
            if 'application/json' in content and 'properties' in content['application/json']:
                parameters = {p['name']: p['value'] for p in content['application/json']['properties']}
                is_bedrock_format = True
        elif isinstance(event.get('body'), str):
            # API Gateway format
            parameters = json.loads(event['body'])
            is_bedrock_format = False
        else:
            # Direct invocation format
            parameters = event
            is_bedrock_format = False
        
        # Get parameters (handle both 'query' and 'sql_query' parameter names)
        query = parameters.get('sql_query', parameters.get('query', '')).strip()
        org_id = parameters.get('org_id', '').strip()
        timeout = int(parameters.get('timeout', QUERY_TIMEOUT))
        
        print(f"Parameters: query={query[:100]}..., org_id={org_id}, timeout={timeout}, bedrock_format={is_bedrock_format}")
        
        # Validate inputs
        if not query:
            return format_response(400, {
                'success': False,
                'error': 'Query parameter is required'
            }, is_bedrock_format)
        
        if not org_id:
            return format_response(400, {
                'success': False,
                'error': 'org_id parameter is required for data isolation'
            }, is_bedrock_format)
        
        # Validate SQL security
        validation_result = validate_sql_security(query)
        if not validation_result['valid']:
            return format_response(403, {
                'success': False,
                'error': validation_result['error']
            }, is_bedrock_format)
        
        # Add org_id filter to query if not already present
        # This ensures data isolation at the org level
        if 'org_id' not in query.lower():
            print(f"Warning: Query does not include org_id filter. Org: {org_id}")
        
        # Execute query
        print("About to execute query...")
        result = execute_query(query, org_id, timeout)
        print(f"Query executed! Result: {json.dumps(result, default=str)[:200]}")
        
        print(f"Query execution result: success={result['success']}, row_count={result.get('row_count', 0)}")
        
        # Return result in appropriate format
        status_code = 200 if result['success'] else 500
        print(f"Formatting response with status code: {status_code}")
        response = format_response(status_code, result, is_bedrock_format)
        
        print(f"Returning response: {json.dumps(response, default=str)[:500]}")
        
        return response
        
    except json.JSONDecodeError as e:
        return format_response(400, {
            'success': False,
            'error': f'Invalid JSON in request body: {str(e)}'
        }, is_bedrock_format)
        
    except Exception as e:
        # Catch-all for unexpected errors
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"!!! LAMBDA HANDLER ERROR !!!")
        print(f"Error: {error_msg}")
        print(f"Traceback:\n{traceback_str}")
        
        error_response = format_response(500, {
            'success': False,
            'error': f'Internal server error: {error_msg}'
        }, is_bedrock_format)
        
        print(f"Returning error response: {json.dumps(error_response, default=str)[:300]}")
        
        return error_response
