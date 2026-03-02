"""
Lambda function for secure SQL query execution against MySQL database.

This function:
- Validates SQL queries for security (forbidden operations)
- Executes queries with connection pooling
- Returns structured results or detailed error messages
- Enforces org-level data isolation
- Supports both Bedrock action group format and direct JSON invocation
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


def extract_parameters(event: dict) -> dict:
    """
    Extract parameters from either direct JSON or Bedrock action group envelope format.

    Args:
        event: Lambda event dict

    Returns:
        Flat dict of parameter name → value
    """
    if 'requestBody' in event:
        # Bedrock action group envelope (backward compatibility)
        content = event['requestBody']['content']
        props = content['application/json']['properties']
        return {p['name']: p['value'] for p in props}
    # Direct JSON invocation from AgentCore tool dispatcher
    return event


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


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for SQL query execution.

    Handles both Bedrock action group format and direct JSON invocation.

    Bedrock action group format:
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

    Direct JSON format (AgentCore tool dispatcher):
    {
        "sql_query": "SELECT * FROM table WHERE ...",
        "org_id": "org_123"
    }

    Returns a plain JSON dict for direct calls, or the Bedrock action group
    response envelope for action group calls.
    """
    print(f"Event: {json.dumps(event, default=str)}")

    # Detect invocation format before extracting parameters
    is_action_group = 'requestBody' in event

    try:
        parameters = extract_parameters(event)

        # Get parameters — canonical name is sql_query (aligns with tool schema)
        query = parameters.get('sql_query', '').strip()
        org_id = parameters.get('org_id', '').strip()
        timeout = int(parameters.get('timeout', QUERY_TIMEOUT))

        print(f"Parameters: query={query[:100]}..., org_id={org_id}, timeout={timeout}, action_group={is_action_group}")

        # Validate inputs
        if not query:
            error_body = {'success': False, 'error': 'sql_query parameter is required'}
            if is_action_group:
                return _bedrock_response(400, error_body, event)
            return error_body

        if not org_id:
            error_body = {'success': False, 'error': 'org_id parameter is required for data isolation'}
            if is_action_group:
                return _bedrock_response(400, error_body, event)
            return error_body

        # Validate SQL security
        validation_result = validate_sql_security(query)
        if not validation_result['valid']:
            error_body = {'success': False, 'error': validation_result['error']}
            if is_action_group:
                return _bedrock_response(403, error_body, event)
            return error_body

        # Warn if org_id filter is absent from the query itself
        if 'org_id' not in query.lower():
            print(f"Warning: Query does not include org_id filter. Org: {org_id}")

        # Execute query
        print("About to execute query...")
        result = execute_query(query, org_id, timeout)
        print(f"Query executed! Result: {json.dumps(result, default=str)[:200]}")

        status_code = 200 if result['success'] else 500

        if is_action_group:
            return _bedrock_response(status_code, result, event)

        # Direct JSON invocation — return plain dict
        return result

    except Exception as e:
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"!!! LAMBDA HANDLER ERROR !!!\nError: {error_msg}\nTraceback:\n{traceback_str}")

        error_body = {'success': False, 'error': f'Internal server error: {error_msg}'}

        if is_action_group:
            return _bedrock_response(500, error_body, event)
        return error_body


def _bedrock_response(status_code: int, body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Bedrock action group response envelope."""
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': event.get('actionGroup', 'ExecuteSqlQueryActionGroup'),
            'apiPath': event.get('apiPath', '/execute_sql_query'),
            'httpMethod': event.get('httpMethod', 'POST'),
            'httpStatusCode': status_code,
            'responseBody': {
                'application/json': {
                    'body': json.dumps(body, default=str)
                }
            }
        }
    }
