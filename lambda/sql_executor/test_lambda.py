"""
Test script for SQL Executor Lambda function.
Tests both local execution and deployed Lambda invocation.
"""

import json
import os
import sys

# Try to import boto3 for deployed testing
try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    print("Warning: boto3 not installed. Deployed Lambda testing will be skipped.")

# Try to import lambda function (may fail if psycopg2 not installed locally)
try:
    from lambda_function import lambda_handler, validate_sql_security
    LAMBDA_AVAILABLE = True
except ImportError as e:
    LAMBDA_AVAILABLE = False
    print(f"Warning: Cannot import lambda_function ({e}). Local testing will be limited.")

def test_security_validation():
    """Test SQL security validation logic."""
    if not LAMBDA_AVAILABLE:
        print("\n=== Skipping SQL Security Validation (lambda_function not available) ===\n")
        return True
    
    print("\n=== Testing SQL Security Validation ===\n")
    
    test_cases = [
        {
            "query": "SELECT * FROM users WHERE org_id = 'org_123'",
            "should_pass": True,
            "description": "Valid SELECT query"
        },
        {
            "query": "SELECT name, email FROM users WHERE created_at > '2024-01-01'",
            "should_pass": True,
            "description": "Valid SELECT with date filter"
        },
        {
            "query": "INSERT INTO users (name) VALUES ('test')",
            "should_pass": False,
            "description": "INSERT operation (forbidden)"
        },
        {
            "query": "UPDATE users SET name = 'test' WHERE id = 1",
            "should_pass": False,
            "description": "UPDATE operation (forbidden)"
        },
        {
            "query": "DELETE FROM users WHERE id = 1",
            "should_pass": False,
            "description": "DELETE operation (forbidden)"
        },
        {
            "query": "DROP TABLE users",
            "should_pass": False,
            "description": "DROP operation (forbidden)"
        },
        {
            "query": "SELECT * FROM users; DROP TABLE users;",
            "should_pass": False,
            "description": "Multiple statements (SQL injection attempt)"
        },
        {
            "query": "EXEC sp_executesql N'SELECT * FROM users'",
            "should_pass": False,
            "description": "EXEC operation (forbidden)"
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        result = validate_sql_security(test["query"])
        expected = test["should_pass"]
        actual = result["valid"]
        
        status = "✓ PASS" if actual == expected else "✗ FAIL"
        
        print(f"{status}: {test['description']}")
        print(f"  Query: {test['query'][:60]}...")
        
        if actual != expected:
            print(f"  Expected: {expected}, Got: {actual}")
            if not result["valid"]:
                print(f"  Error: {result['error']}")
            failed += 1
        else:
            passed += 1
        
        print()
    
    print(f"Results: {passed} passed, {failed} failed\n")
    return failed == 0


def test_lambda_local():
    """Test Lambda function locally (without database connection)."""
    if not LAMBDA_AVAILABLE:
        print("\n=== Skipping Local Lambda Handler Tests (lambda_function not available) ===\n")
        return
    
    print("\n=== Testing Lambda Handler Locally ===\n")
    
    # Test 1: Missing query parameter
    print("Test 1: Missing query parameter")
    event = {"body": json.dumps({"org_id": "org_123"})}
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response: {response['body']}\n")
    
    # Test 2: Missing org_id parameter
    print("Test 2: Missing org_id parameter")
    event = {"body": json.dumps({"query": "SELECT * FROM users"})}
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response: {response['body']}\n")
    
    # Test 3: Forbidden operation
    print("Test 3: Forbidden operation (DELETE)")
    event = {
        "body": json.dumps({
            "query": "DELETE FROM users WHERE id = 1",
            "org_id": "org_123"
        })
    }
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response: {response['body']}\n")
    
    # Test 4: Valid query structure (will fail without DB connection)
    print("Test 4: Valid query structure (will fail without DB)")
    event = {
        "body": json.dumps({
            "query": "SELECT * FROM users WHERE org_id = 'org_123' LIMIT 10",
            "org_id": "org_123"
        })
    }
    response = lambda_handler(event, None)
    print(f"Status Code: {response['statusCode']}")
    print(f"Response: {response['body']}\n")


def test_lambda_deployed(function_name="queen-sql-executor-lambda", region="us-west-2"):
    """Test deployed Lambda function via AWS API."""
    if not BOTO3_AVAILABLE:
        print("\n=== Cannot test deployed Lambda (boto3 not installed) ===\n")
        print("Install boto3: pip install boto3")
        return
    
    print(f"\n=== Testing Deployed Lambda Function ===\n")
    print(f"Function: {function_name}")
    print(f"Region: {region}\n")
    
    try:
        lambda_client = boto3.client('lambda', region_name=region)
        
        # Test with a simple valid query
        test_payload = {
            "query": "SELECT 1 as test_column",
            "org_id": "org_test_123"
        }
        
        print(f"Invoking Lambda with payload:")
        print(json.dumps(test_payload, indent=2))
        print()
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(test_payload)
        )
        
        # Parse response
        response_payload = json.loads(response['Payload'].read())
        
        print(f"Lambda Response:")
        print(f"Status Code: {response['StatusCode']}")
        print(f"Response Payload:")
        print(json.dumps(response_payload, indent=2))
        
        # Check if execution was successful
        if response['StatusCode'] == 200:
            body = json.loads(response_payload.get('body', '{}'))
            if body.get('success'):
                print("\n✓ Lambda execution successful!")
                print(f"Rows returned: {body.get('row_count', 0)}")
                print(f"Execution time: {body.get('execution_time_ms', 0)}ms")
            else:
                print(f"\n✗ Lambda execution failed: {body.get('error')}")
        else:
            print(f"\n✗ Lambda invocation failed with status {response['StatusCode']}")
        
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"✗ Lambda function '{function_name}' not found in region '{region}'")
        print("Make sure the function is deployed first using deploy.sh")
    except Exception as e:
        print(f"✗ Error testing deployed Lambda: {str(e)}")


if __name__ == "__main__":
    print("=" * 60)
    print("SQL Executor Lambda - Test Suite")
    print("=" * 60)
    
    # Run security validation tests
    security_passed = test_security_validation()
    
    # Run local Lambda handler tests
    test_lambda_local()
    
    # Ask user if they want to test deployed Lambda
    if LAMBDA_AVAILABLE:
        print("\nTo test the deployed Lambda function, run:")
        print("  python test_lambda.py --deployed")
        print("\nOr test with custom function name and region:")
        print("  python test_lambda.py --deployed --function-name your-function --region us-east-1")
    else:
        print("\nNote: Local testing skipped due to missing dependencies.")
        print("This is normal - the Lambda will have all dependencies when deployed.")
    
    if "--deployed" in sys.argv:
        function_name = "queen-sql-executor-lambda"
        region = "us-west-2"
        
        # Parse custom function name and region
        if "--function-name" in sys.argv:
            idx = sys.argv.index("--function-name")
            if idx + 1 < len(sys.argv):
                function_name = sys.argv[idx + 1]
        
        if "--region" in sys.argv:
            idx = sys.argv.index("--region")
            if idx + 1 < len(sys.argv):
                region = sys.argv[idx + 1]
        
        test_lambda_deployed(function_name, region)
    
    print("\n" + "=" * 60)
    print("Test suite complete!")
    print("=" * 60)
