"""
Get KPI Data Lambda Function

This Lambda function is an action group for the Smart Retrieval Agent.
It retrieves pre-calculated KPI data from the reddyice_s3_commercial_money table.

Action Group: get_kpi_data
Parameters:
- kpi_ids: List of KPI IDs to retrieve (comma-separated string or list)
- date_range: Date range in format "YYYY-MM to YYYY-MM"
- frequency: "monthly", "weekly", or "daily"
- org_id: Organization ID (default: "default")

The function:
1. Builds XBR-style SQL queries based on KPI IDs
2. Substitutes date range and frequency parameters
3. Executes queries via database connection
4. Parses and formats results
5. Validates data quality
6. Returns structured KPI data

Note: Uses the same MySQL RDS database as sql_executor, queries
the reddyice_s3_commercial_money table which contains pre-calculated KPI data.
"""

import json
import os
import sys
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import calendar
import pymysql
from pymysql.cursors import DictCursor

# Database connection parameters (same as sql_executor)
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')


def get_db_connection():
    """Create database connection to MySQL RDS."""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursorclass=DictCursor,
        autocommit=True
    )


def parse_date_range(date_range: str) -> tuple:
    """
    Parse date range string.
    
    Args:
        date_range: "YYYY-MM to YYYY-MM"
        
    Returns:
        (start_date, end_date) tuple
    """
    parts = date_range.split(' to ')
    if len(parts) != 2:
        raise ValueError(f"Invalid date range format: {date_range}")
    
    start_date = parts[0].strip()
    end_date = parts[1].strip()
    
    return start_date, end_date


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


def map_kpi_name_to_column(kpi_name: str) -> Optional[str]:
    """
    Map KPI name to database column.
    
    This function maps KPI names from metadata to actual database columns
    in the reddyice_s3_commercial_money table.
    
    Args:
        kpi_name: Name of the KPI (e.g., "Total Revenue", "Average OOS%")
        
    Returns:
        Database column name or None if KPI is not in the database
        
    Examples:
        "Total Revenue" → "cy_revenue"
        "Total Volume" → "cy_volume"
        "Total SSS Revenue" → "cy_sss_revenue"
        "Total Store Count" → "store_count"
        "Average OOS%" → "cy_oos_percent"
    """
    kpi_lower = kpi_name.lower()
    
    # Revenue mappings
    if "sss revenue" in kpi_lower:
        return "cy_sss_revenue"
    elif "revenue" in kpi_lower:
        return "cy_revenue"
    
    # Volume mappings (exclude 7lb equivalent)
    elif "sss volume" in kpi_lower:
        return "cy_sss_volume"
    elif "volume" in kpi_lower and "7lb" not in kpi_lower:
        return "cy_volume"
    
    # Store count
    elif "store count" in kpi_lower:
        return "store_count"
    
    # OOS percentage
    elif "oos" in kpi_lower or "out-of-stock" in kpi_lower or "out of stock" in kpi_lower:
        return "cy_oos_percent"
    
    # If no match, return None (KPI not in our database)
    # These might be order-related KPIs that need transactional data
    return None


def get_kpi_mapping() -> Dict[int, Dict[str, Any]]:
    """
    Load KPI mapping dynamically from metadata file.
    Maps all 897 KPI IDs to their corresponding database columns.
    
    Returns:
        Dictionary mapping KPI ID to column info
    """
    # Load metadata
    try:
        metadata = load_kpi_metadata()
    except Exception as e:
        print(f"Warning: Could not load KPI metadata: {e}")
        print("Falling back to empty mapping")
        return {}
    
    # Build mapping
    mapping = {}
    unmapped_count = 0
    
    for kpi in metadata:
        kpi_id = kpi['kpi_id']
        kpi_name = kpi['kpi_name']
        customer = extract_customer_from_page_name(kpi.get('page_name', ''))
        
        # Map KPI name to database column
        column = map_kpi_name_to_column(kpi_name)
        
        if column:
            # This KPI maps to a database column
            mapping[kpi_id] = {
                "column": column,
                "name": kpi_name,
                "unit": kpi.get('unit', 'unknown'),
                "chain": customer
            }
        else:
            # This KPI doesn't map to our database (e.g., order-related KPIs)
            unmapped_count += 1
    
    print(f"Loaded {len(mapping)} KPI mappings from metadata")
    print(f"Skipped {unmapped_count} KPIs that don't map to database columns")
    
    return mapping


# Cache the mapping at module level to avoid reloading on every invocation
_KPI_MAPPING_CACHE = None


def get_cached_kpi_mapping() -> Dict[int, Dict[str, Any]]:
    """
    Get KPI mapping with caching for Lambda performance.
    
    Returns:
        Cached KPI mapping dictionary
    """
    global _KPI_MAPPING_CACHE
    
    if _KPI_MAPPING_CACHE is None:
        _KPI_MAPPING_CACHE = get_kpi_mapping()
    
    return _KPI_MAPPING_CACHE





def normalize_date_format(date_str: str) -> str:
    """
    Normalize date string to YYYY-MM-DD format.
    
    Args:
        date_str: Date in YYYY-MM or YYYY-MM-DD format
        
    Returns:
        Date in YYYY-MM-DD format
    """
    if len(date_str) == 7:  # YYYY-MM format
        return f"{date_str}-01"
    return date_str


def get_last_day_of_month(date_str: str) -> str:
    """
    Get the last day of the month for a given date.
    
    Args:
        date_str: Date in YYYY-MM or YYYY-MM-DD format
        
    Returns:
        Date string with last day of month (YYYY-MM-DD)
    """
    if len(date_str) == 7:  # YYYY-MM format
        year, month = map(int, date_str.split('-'))
        last_day = calendar.monthrange(year, month)[1]
        return f"{date_str}-{last_day:02d}"
    return date_str


def build_kpi_query(
    kpi_ids: List[int],
    start_date: str,
    end_date: str,
    frequency: str,
    org_id: str
) -> Tuple[str, List[str]]:
    """
    Build SQL query to retrieve KPI data from reddyice_s3_commercial_money table.
    
    This function builds XBR-style queries that:
    1. Map KPI IDs to specific columns
    2. Filter by date range
    3. Aggregate by frequency (monthly/quarterly)
    4. Filter by chain (Customer A, Customer B, etc.)
    
    Args:
        kpi_ids: List of KPI IDs to retrieve
        start_date: Start date (YYYY-MM or YYYY-MM-DD format)
        end_date: End date (YYYY-MM or YYYY-MM-DD format)
        frequency: "monthly", "weekly", or "daily"
        org_id: Organization ID (maps to parent_chain_group)
        
    Returns:
        Tuple of (SQL query string, list of column names)
    """
    # Normalize dates
    start_date = normalize_date_format(start_date)
    end_date = get_last_day_of_month(end_date)
    
    # Get KPI mappings (cached for performance)
    kpi_mapping = get_cached_kpi_mapping()
    
    # Determine which columns to select based on KPI IDs
    columns_to_select = set()
    chains_to_filter = set()
    kpi_info = []
    
    for kpi_id in kpi_ids:
        if kpi_id in kpi_mapping:
            info = kpi_mapping[kpi_id]
            columns_to_select.add(info['column'])
            chains_to_filter.add(info['chain'])
            kpi_info.append({
                'kpi_id': kpi_id,
                'column': info['column'],
                'name': info['name'],
                'unit': info['unit'],
                'chain': info['chain']
            })
    
    # Build SELECT clause
    select_columns = [
        "mon_year as period",
        "parent_chain_group",
        "company_chain",
        "channel_group",
        "channel"
    ]
    
    # Add requested KPI columns
    for col in sorted(columns_to_select):
        select_columns.append(col)
    
    # Add related columns for context
    if 'cy_revenue' in columns_to_select or 'cy_sss_revenue' in columns_to_select:
        select_columns.extend(['py_revenue', 'revenue_variance', 'revenue_variance_percent'])
    if 'cy_volume' in columns_to_select or 'cy_sss_volume' in columns_to_select:
        select_columns.extend(['py_volume', 'volume_variance', 'percent_volume_change'])
    if 'cy_oos_percent' in columns_to_select:
        select_columns.append('py_oos_percent')
    
    # Remove duplicates while preserving order
    seen = set()
    select_columns = [x for x in select_columns if not (x in seen or seen.add(x))]
    
    # Build WHERE clause
    where_clauses = [
        f"mon_year >= '{start_date}'",
        f"mon_year <= '{end_date}'"
    ]
    
    # Filter by chain if specific chains requested
    if chains_to_filter and len(chains_to_filter) < 2:
        chain_filter = "', '".join(chains_to_filter)
        where_clauses.append(f"parent_chain_group IN ('{chain_filter}')")
    
    # Build query
    query = f"""
        SELECT 
            {', '.join(select_columns)}
        FROM reddyice_s3_commercial_money
        WHERE {' AND '.join(where_clauses)}
        ORDER BY mon_year, parent_chain_group
    """
    
    return query, kpi_info


def validate_data_quality(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate data quality and identify issues.
    
    Args:
        results: Query results
        
    Returns:
        Dictionary with validation results
    """
    issues = []
    warnings = []
    
    if not results:
        issues.append("No data returned for the specified date range and KPI IDs")
        return {
            'valid': False,
            'issues': issues,
            'warnings': warnings,
            'row_count': 0
        }
    
    # Check for null values in key columns
    null_counts = {}
    for row in results:
        for key, value in row.items():
            if value is None:
                null_counts[key] = null_counts.get(key, 0) + 1
    
    if null_counts:
        for col, count in null_counts.items():
            pct = (count / len(results)) * 100
            if pct > 50:
                issues.append(f"Column '{col}' has {pct:.1f}% null values")
            elif pct > 10:
                warnings.append(f"Column '{col}' has {pct:.1f}% null values")
    
    # Check for outliers in numeric columns
    numeric_columns = ['cy_revenue', 'cy_volume', 'cy_oos_percent', 'store_count']
    for col in numeric_columns:
        values = [row.get(col) for row in results if row.get(col) is not None]
        if values:
            avg = sum(values) / len(values)
            if avg == 0:
                continue
            
            # Check for extreme outliers (> 10x average)
            outliers = [v for v in values if v > avg * 10]
            if outliers:
                warnings.append(f"Column '{col}' has {len(outliers)} extreme outliers")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'row_count': len(results)
    }


def format_kpi_results(
    results: List[Dict[str, Any]],
    kpi_info: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Format KPI results with proper units and formatting.
    
    Args:
        results: Raw query results
        kpi_info: KPI metadata
        
    Returns:
        Formatted results
    """
    formatted_results = []
    
    for row in results:
        formatted_row = {}
        
        for key, value in row.items():
            if value is None:
                formatted_row[key] = None
                continue
            
            # Format based on column type
            if 'revenue' in key.lower():
                # Currency formatting
                formatted_row[key] = value
                formatted_row[f"{key}_formatted"] = f"${value:,.2f}"
            elif 'percent' in key.lower() or 'oos' in key.lower():
                # Percentage formatting
                formatted_row[key] = value
                if value < 1:  # If stored as decimal
                    formatted_row[f"{key}_formatted"] = f"{value * 100:.2f}%"
                else:  # If stored as percentage
                    formatted_row[f"{key}_formatted"] = f"{value:.2f}%"
            elif 'volume' in key.lower() or 'count' in key.lower():
                # Number formatting with thousands separator
                formatted_row[key] = value
                formatted_row[f"{key}_formatted"] = f"{value:,.0f}"
            elif key == 'period' or 'date' in key.lower():
                # Date formatting
                if isinstance(value, datetime):
                    formatted_row[key] = value.strftime('%Y-%m-%d')
                    formatted_row[f"{key}_formatted"] = value.strftime('%B %Y')
                else:
                    formatted_row[key] = str(value)
                    formatted_row[f"{key}_formatted"] = str(value)
            else:
                formatted_row[key] = value
        
        formatted_results.append(formatted_row)
    
    return formatted_results


def lambda_handler(event, context):
    """
    Lambda handler for get_kpi_data action group.
    
    Args:
        event: Lambda event containing action group parameters
        context: Lambda context
        
    Returns:
        Action group response
    """
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Extract parameters from event
        # Bedrock action groups pass parameters in different formats
        parameters = {}
        
        if 'requestBody' in event and 'content' in event['requestBody']:
            # New Bedrock format: requestBody.content.application/json.properties
            content = event['requestBody']['content']
            if 'application/json' in content and 'properties' in content['application/json']:
                parameters = {p['name']: p['value'] for p in content['application/json']['properties']}
        elif 'parameters' in event:
            # Old format: parameters array
            parameters = {p['name']: p['value'] for p in event['parameters']}
        elif 'actionGroup' in event and 'parameters' in event['actionGroup']:
            # Alternative format: actionGroup.parameters
            parameters = {p['name']: p['value'] for p in event['actionGroup']['parameters']}
        else:
            # Fallback: treat event as parameters dict
            parameters = event
        
        # Get parameters
        kpi_ids_str = parameters.get('kpi_ids', '')
        date_range = parameters.get('date_range', '')
        frequency = parameters.get('frequency', 'monthly')
        org_id = parameters.get('org_id', 'default')
        
        print(f"Parameters: kpi_ids={kpi_ids_str}, date_range={date_range}, frequency={frequency}")
        
        # Parse KPI IDs
        if isinstance(kpi_ids_str, str):
            kpi_ids = [int(x.strip()) for x in kpi_ids_str.split(',') if x.strip()]
        elif isinstance(kpi_ids_str, list):
            kpi_ids = [int(x) for x in kpi_ids_str]
        else:
            kpi_ids = [int(kpi_ids_str)]
        
        if not kpi_ids:
            return {
                'messageVersion': '1.0',
                'response': {
                    'actionGroup': event.get('actionGroup', 'GetKpiDataActionGroup'),
                    'apiPath': event.get('apiPath', '/get_kpi_data'),
                    'httpMethod': event.get('httpMethod', 'POST'),
                    'httpStatusCode': 400,
                    'responseBody': {
                        'application/json': {
                            'body': json.dumps({
                                'error': 'No KPI IDs provided',
                                'kpi_data': []
                            })
                        }
                    }
                }
            }
        
        # Parse date range
        start_date, end_date = parse_date_range(date_range)
        
        # Build query with KPI mapping
        query, kpi_info = build_kpi_query(kpi_ids, start_date, end_date, frequency, org_id)
        print(f"Executing query: {query}")
        print(f"KPI Info: {json.dumps(kpi_info, indent=2)}")
        
        # Execute query
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Convert results to list of dicts
        raw_data = [dict(row) for row in results]
        
        print(f"Retrieved {len(raw_data)} rows")
        
        # Validate data quality
        validation = validate_data_quality(raw_data)
        print(f"Data validation: {json.dumps(validation, indent=2)}")
        
        # Format results
        formatted_data = format_kpi_results(raw_data, kpi_info)
        
        # Prepare response
        response_body = {
            'kpi_data': formatted_data,
            'count': len(formatted_data),
            'kpi_ids': kpi_ids,
            'kpi_info': kpi_info,
            'date_range': date_range,
            'frequency': frequency,
            'data_quality': validation
        }
        
        # Return response in Bedrock action group format
        response = {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'GetKpiDataActionGroup'),
                'apiPath': event.get('apiPath', '/get_kpi_data'),
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
                'actionGroup': event.get('actionGroup', 'GetKpiDataActionGroup'),
                'apiPath': event.get('apiPath', '/get_kpi_data'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({
                            'error': str(e),
                            'kpi_data': []
                        })
                    }
                }
            }
        }
