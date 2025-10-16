# SQL Executor Lambda Function

Secure Lambda function for executing SQL queries against PostgreSQL database with built-in security validation and connection pooling.

## Features

- **Security Validation**: Blocks INSERT, UPDATE, DELETE, DROP, and other dangerous operations
- **Connection Pooling**: Efficient database connection reuse across Lambda invocations
- **Error Handling**: Detailed error messages for debugging
- **Query Timeout**: Configurable timeout to prevent long-running queries
- **Org-Level Isolation**: Enforces organization-level data access control

## Project Structure

```
lambda/sql_executor/
├── lambda_function.py      # Main Lambda handler
├── requirements.txt        # Python dependencies
├── deploy.sh              # Deployment script
├── test_lambda.py         # Test suite
├── iam_policy.json        # IAM policy for Lambda role
└── README.md              # This file
```

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Python 3.11 or later
3. PostgreSQL database (RDS or self-hosted)
4. VPC configuration if using RDS in VPC

## Deployment

### Step 1: Make deployment script executable

```bash
cd lambda/sql_executor
chmod +x deploy.sh
```

### Step 2: Deploy the Lambda function

```bash
./deploy.sh
```

This script will:
- Create a deployment package with dependencies
- Create IAM role with necessary permissions
- Deploy or update the Lambda function
- Output the Lambda ARN

### Step 3: Configure environment variables

After deployment, configure the database connection:

```bash
aws lambda update-function-configuration \
  --function-name queen-sql-executor-lambda \
  --environment Variables='{
    DB_HOST=your-rds-endpoint.rds.amazonaws.com,
    DB_PORT=5432,
    DB_NAME=your_database,
    DB_USER=your_username,
    DB_PASSWORD=your_password
  }' \
  --region us-west-2
```

### Step 4: Configure VPC (if using RDS in VPC)

```bash
aws lambda update-function-configuration \
  --function-name queen-sql-executor-lambda \
  --vpc-config SubnetIds=subnet-xxx,subnet-yyy,SecurityGroupIds=sg-xxx \
  --region us-west-2
```

**Important**: Ensure the security group allows outbound traffic to your RDS instance on port 5432.

### Step 5: Update .env file

Add the Lambda ARN to your project's `.env` file:

```bash
SQL_EXECUTOR_LAMBDA_ARN=arn:aws:lambda:us-west-2:123456789012:function:queen-sql-executor-lambda
```

## Testing

### Run local tests (no database required)

```bash
python test_lambda.py
```

This tests:
- SQL security validation logic
- Lambda handler input validation
- Error handling

### Test deployed Lambda function

```bash
python test_lambda.py --deployed
```

Or with custom function name and region:

```bash
python test_lambda.py --deployed --function-name my-function --region us-east-1
```

### Manual testing with AWS CLI

```bash
aws lambda invoke \
  --function-name queen-sql-executor-lambda \
  --payload '{"query":"SELECT 1 as test","org_id":"org_123"}' \
  --region us-west-2 \
  response.json

cat response.json
```

## Usage

### Request Format

```json
{
  "query": "SELECT * FROM users WHERE org_id = 'org_123' AND created_at > '2024-01-01'",
  "org_id": "org_123",
  "timeout": 30
}
```

### Response Format (Success)

```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "data": [
      {"id": 1, "name": "John", "email": "john@example.com"},
      {"id": 2, "name": "Jane", "email": "jane@example.com"}
    ],
    "row_count": 2,
    "execution_time_ms": 150,
    "error": null
  }
}
```

### Response Format (Error)

```json
{
  "statusCode": 403,
  "body": {
    "success": false,
    "error": "Forbidden operation detected: DELETE. Only SELECT queries are allowed."
  }
}
```

## Security Features

### Forbidden Operations

The following SQL operations are blocked:
- INSERT, UPDATE, DELETE
- DROP, ALTER, CREATE, TRUNCATE
- EXEC, EXECUTE, MERGE
- GRANT, REVOKE
- COMMIT, ROLLBACK

### Additional Security

- Only single SELECT statements allowed
- Query timeout enforcement (default 30 seconds)
- Org-level data isolation (org_id required)
- Connection pooling prevents connection exhaustion

## IAM Permissions

The Lambda function requires the following permissions:

1. **Basic Lambda Execution** (AWSLambdaBasicExecutionRole)
   - CloudWatch Logs access

2. **VPC Access** (AWSLambdaVPCAccessExecutionRole)
   - Network interface management for VPC connectivity

3. **RDS Access** (custom policy in iam_policy.json)
   - Describe RDS instances and clusters

## Monitoring

### CloudWatch Logs

View Lambda execution logs:

```bash
aws logs tail /aws/lambda/queen-sql-executor-lambda --follow --region us-west-2
```

### CloudWatch Metrics

Monitor Lambda performance:
- Invocations
- Duration
- Errors
- Throttles

## Troubleshooting

### Connection timeout

- Check VPC configuration and security groups
- Verify RDS endpoint is accessible from Lambda subnets
- Ensure security group allows inbound traffic on port 5432

### Query timeout

- Increase timeout parameter in request
- Optimize query with proper indexes
- Add more specific filters to reduce data scanned

### Permission denied

- Verify IAM role has necessary permissions
- Check database user has SELECT permissions
- Ensure RDS security group allows Lambda security group

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DB_HOST | Yes | PostgreSQL host endpoint |
| DB_PORT | No | Database port (default: 5432) |
| DB_NAME | Yes | Database name |
| DB_USER | Yes | Database username |
| DB_PASSWORD | Yes | Database password |

### Lambda Settings

- **Runtime**: Python 3.11
- **Timeout**: 60 seconds
- **Memory**: 512 MB
- **Handler**: lambda_function.lambda_handler

## Development

### Local development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=testdb
export DB_USER=testuser
export DB_PASSWORD=testpass
```

3. Run tests:
```bash
python test_lambda.py
```

### Update deployment

After making changes to `lambda_function.py`:

```bash
./deploy.sh
```

The script will automatically update the existing Lambda function.
