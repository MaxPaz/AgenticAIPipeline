# Get KPI Data Lambda Function

This Lambda function is an action group for the Smart Retrieval Agent. It retrieves pre-calculated KPI data from the `reddyice_s3_commercial_money` table with intelligent mapping, formatting, and validation.

## Features

### 1. KPI ID to Column Mapping
- Maps KPI IDs (e.g., 17870, 17890) to database columns (e.g., `cy_revenue`, `cy_volume`)
- Supports Customer A and Customer B KPIs
- Includes metadata (name, unit, chain) for each KPI

### 2. Date Range and Frequency Parameter Substitution
- Accepts date ranges in `YYYY-MM to YYYY-MM` format
- Automatically normalizes dates to `YYYY-MM-DD` format
- Calculates last day of month for end dates
- Supports monthly, weekly, and daily frequencies

### 3. XBR-Style SQL Query Building
- Builds optimized SQL queries based on requested KPI IDs
- Includes related columns (e.g., prior year, variance) for context
- Filters by chain when specific chains are requested
- Orders results by period and chain

### 4. Result Parsing and Formatting
- Formats currency values with `$` symbol and thousands separators
- Formats percentages with `%` symbol
- Formats numbers with thousands separators
- Converts dates to user-friendly format (e.g., "January 2024")
- Returns both raw and formatted values

### 5. Data Quality Validation
- Checks for null values and reports percentage
- Detects extreme outliers (> 10x average)
- Validates that data was returned
- Provides warnings and issues in response

## API

### Request Parameters

```json
{
  "kpi_ids": "17870,17866",
  "date_range": "2024-01 to 2024-12",
  "frequency": "monthly",
  "org_id": "default"
}
```

- `kpi_ids` (required): Comma-separated list of KPI IDs
- `date_range` (required): Date range in format "YYYY-MM to YYYY-MM"
- `frequency` (optional): "monthly", "weekly", or "daily" (default: "monthly")
- `org_id` (optional): Organization ID (default: "default")

### Response Format

```json
{
  "statusCode": 200,
  "body": {
    "kpi_data": [
      {
        "period": "2024-01-01",
        "period_formatted": "January 2024",
        "parent_chain_group": "Customer A",
        "cy_revenue": 1234567.89,
        "cy_revenue_formatted": "$1,234,567.89",
        "cy_volume": 5000,
        "cy_volume_formatted": "5,000",
        "cy_oos_percent": 0.05,
        "cy_oos_percent_formatted": "5.00%"
      }
    ],
    "count": 12,
    "kpi_ids": [17870, 17866],
    "kpi_info": [
      {
        "kpi_id": 17870,
        "column": "cy_revenue",
        "name": "Total Revenue",
        "unit": "currency",
        "chain": "Customer A"
      }
    ],
    "date_range": "2024-01 to 2024-12",
    "frequency": "monthly",
    "data_quality": {
      "valid": true,
      "issues": [],
      "warnings": [],
      "row_count": 12
    }
  }
}
```

## KPI Mappings

### Customer A KPIs

| KPI ID | Name | Column | Unit |
|--------|------|--------|------|
| 17849 | Total Store Count | store_count | number |
| 17850 | Total Revenue | cy_revenue | currency |
| 17851 | Total SSS Revenue | cy_sss_revenue | currency |
| 17852 | Total Volume | cy_volume | number |
| 17853 | Total SSS Volume | cy_sss_volume | number |
| 17860 | Average OOS% | cy_oos_percent | percentage |
| 17865 | Total Store Count | store_count | number |
| 17866 | Total Volume | cy_volume | number |
| 17867 | Total SSS Volume | cy_sss_volume | number |
| 17868 | Total Revenue | cy_revenue | currency |
| 17869 | Total SSS Revenue | cy_sss_revenue | currency |
| 17870 | Total Revenue | cy_revenue | currency |
| 17876 | Average OOS% | cy_oos_percent | percentage |

### Customer B KPIs

| KPI ID | Name | Column | Unit |
|--------|------|--------|------|
| 17881 | Total Store Count | store_count | number |
| 17882 | Total Revenue | cy_revenue | currency |
| 17883 | Total SSS Revenue | cy_sss_revenue | currency |
| 17884 | Total Volume | cy_volume | number |
| 17885 | Total SSS Volume | cy_sss_volume | number |
| 17890 | Total Revenue | cy_revenue | currency |
| 17892 | Average OOS% | cy_oos_percent | percentage |
| 17897 | Total Store Count | store_count | number |
| 17898 | Total Volume | cy_volume | number |
| 17899 | Total SSS Volume | cy_sss_volume | number |
| 17901 | Total SSS Revenue | cy_sss_revenue | currency |
| 17908 | Average OOS% | cy_oos_percent | percentage |

## Testing

### Unit Tests

Run unit tests (no database required):

```bash
python lambda/get_kpi_data/test_get_kpi_data.py
```

Tests:
- KPI ID to column mapping
- Date formatting and normalization
- SQL query building
- Data quality validation
- Result formatting
- Parameter extraction

### Integration Tests

Run integration tests (requires database connection):

```bash
# Set environment variables
export DB_HOST=your-rds-endpoint
export DB_NAME=your-database
export DB_USER=your-username
export DB_PASSWORD=your-password

# Run tests
python lambda/get_kpi_data/test_integration.py
```

Tests:
- Single KPI retrieval
- Multiple KPI retrieval
- Customer A and Customer B KPIs
- OOS percentage formatting
- Date range variations
- Error handling

## Deployment

### Prerequisites

1. RDS MySQL database with `reddyice_s3_commercial_money` table
2. Lambda execution role with RDS access
3. VPC configuration for Lambda to access RDS

### Deploy

```bash
cd lambda/get_kpi_data
./deploy.sh
```

### Environment Variables

Set these in Lambda configuration:

- `DB_HOST`: RDS endpoint
- `DB_PORT`: Database port (default: 3306)
- `DB_NAME`: Database name
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password

## Integration with Smart Retrieval Agent

This Lambda function is connected to the Smart Retrieval Agent as an action group:

1. **Action Group Name**: `get_kpi_data`
2. **OpenAPI Schema**: Defined in `agents/smart_retrieval/action_group_schemas.py`
3. **Invocation**: Agent calls this function when KPI data is needed

### Agent Instructions

The Smart Retrieval Agent is instructed to:

1. Call `get_kpi_data` when KPI IDs are provided by Data Source Agent
2. Analyze the returned data for sufficiency
3. If data is insufficient, generate SQL and call `execute_sql_query`
4. Return all collected data to Coordinator Agent

## Example Usage

### Example 1: Customer A Revenue

```python
event = {
    'parameters': [
        {'name': 'kpi_ids', 'value': '17870'},
        {'name': 'date_range', 'value': '2024-01 to 2024-12'},
        {'name': 'frequency', 'value': 'monthly'}
    ]
}

response = lambda_handler(event, None)
# Returns 12 months of Customer A revenue data
```

### Example 2: Multiple KPIs

```python
event = {
    'parameters': [
        {'name': 'kpi_ids', 'value': '17870,17866,17860'},
        {'name': 'date_range', 'value': '2024-01 to 2024-06'},
        {'name': 'frequency', 'value': 'monthly'}
    ]
}

response = lambda_handler(event, None)
# Returns revenue, volume, and OOS% for Customer A
```

### Example 3: Customer B Data

```python
event = {
    'parameters': [
        {'name': 'kpi_ids', 'value': '17890'},
        {'name': 'date_range', 'value': '2024-01 to 2024-12'},
        {'name': 'frequency', 'value': 'monthly'}
    ]
}

response = lambda_handler(event, None)
# Returns 12 months of Customer B revenue data
```

## Requirements

See `requirements.txt`:

```
pymysql==1.1.0
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Smart Retrieval Agent                       │
│                  (Bedrock Sub-Agent)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Invokes action group
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              get_kpi_data Lambda Function                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Map KPI IDs to columns                           │  │
│  │  2. Build XBR-style SQL query                        │  │
│  │  3. Execute query against RDS                        │  │
│  │  4. Format results (currency, %, numbers)            │  │
│  │  5. Validate data quality                            │  │
│  │  6. Return structured response                       │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Queries
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    RDS MySQL Database                        │
│              reddyice_s3_commercial_money table              │
└─────────────────────────────────────────────────────────────┘
```

## Data Quality Validation

The function performs the following validations:

1. **Null Value Detection**: Reports columns with > 10% null values
2. **Outlier Detection**: Identifies values > 10x average
3. **Empty Result Detection**: Warns if no data returned
4. **Row Count Validation**: Ensures expected number of records

Validation results are included in the response under `data_quality`.

## Error Handling

The function handles:

- Invalid KPI IDs (returns 400)
- Invalid date ranges (returns 500)
- Database connection errors (returns 500)
- Query execution errors (returns 500)

All errors include detailed error messages in the response body.

## Performance

- **Query Execution**: < 1 second for typical queries
- **Data Formatting**: < 100ms for 100 records
- **Total Response Time**: < 2 seconds end-to-end

## Monitoring

Monitor these CloudWatch metrics:

- `Invocations`: Number of function invocations
- `Duration`: Execution time
- `Errors`: Number of errors
- `Throttles`: Number of throttled requests

Custom logs include:

- Query execution details
- KPI mapping information
- Data quality validation results
- Row counts and performance metrics
