#!/bin/bash

# Deploy get_kpi_data Lambda function
# This Lambda retrieves pre-calculated KPI data from the sales_metrics table

set -e

FUNCTION_NAME="queen-get-kpi-data-lambda"
REGION="us-west-2"
RUNTIME="python3.11"
HANDLER="lambda_function.lambda_handler"
ROLE_NAME="QueenAI-Lambda-Execution-Role"

echo "=========================================="
echo "Deploying get_kpi_data Lambda Function"
echo "=========================================="

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: $ACCOUNT_ID"

# Check if IAM role exists (should be created by sql_executor)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
if aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
    echo "✓ Using existing IAM role: $ROLE_NAME"
else
    echo "Error: IAM role $ROLE_NAME not found"
    echo "Please deploy sql_executor Lambda first to create the shared IAM role"
    exit 1
fi

# Create deployment package
echo ""
echo "Creating deployment package..."
rm -rf package
mkdir -p package

# Install dependencies
pip install -r requirements.txt -t package/ --quiet

# Copy Lambda function
cp lambda_function.py package/

# Create ZIP file
cd package
zip -r ../lambda_deployment.zip . > /dev/null
cd ..

echo "✓ Deployment package created: lambda_deployment.zip"

# Check if Lambda function exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
    echo ""
    echo "Updating existing Lambda function..."
    
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://lambda_deployment.zip \
        --region $REGION \
        --output json > /dev/null
    
    echo "✓ Lambda function updated: $FUNCTION_NAME"
else
    echo ""
    echo "Creating new Lambda function..."
    
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role $ROLE_ARN \
        --handler $HANDLER \
        --zip-file fileb://lambda_deployment.zip \
        --timeout 60 \
        --memory-size 512 \
        --region $REGION \
        --description "Retrieves pre-calculated KPI data from sales_metrics table" \
        --output json > /dev/null
    
    echo "✓ Lambda function created: $FUNCTION_NAME"
fi

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query 'Configuration.FunctionArn' --output text)

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo "Function Name: $FUNCTION_NAME"
echo "Function ARN: $LAMBDA_ARN"
echo "Region: $REGION"
echo ""
echo "Next Steps:"
echo "1. Configure environment variables (same as sql_executor):"
echo "   aws lambda update-function-configuration \\"
echo "     --function-name $FUNCTION_NAME \\"
echo "     --environment Variables='{DB_HOST=<endpoint>,DB_PORT=3306,DB_NAME=queen_demo,DB_USER=admin,DB_PASSWORD=<password>}' \\"
echo "     --region $REGION"
echo ""
echo "2. If using VPC, configure VPC settings (same as sql_executor):"
echo "   aws lambda update-function-configuration \\"
echo "     --function-name $FUNCTION_NAME \\"
echo "     --vpc-config SubnetIds=<subnet-ids>,SecurityGroupIds=<sg-ids> \\"
echo "     --region $REGION"
echo ""
echo "3. Add to .env file:"
echo "   GET_KPI_DATA_LAMBDA_ARN=$LAMBDA_ARN"
echo ""

# Cleanup
rm -rf package lambda_deployment.zip

echo "✓ Cleanup complete"
