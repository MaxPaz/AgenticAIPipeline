#!/bin/bash
# Deploy script for Smart Retrieval Agent

set -e

echo "=========================================="
echo "Smart Retrieval Agent Deployment"
echo "=========================================="

# Configuration
AGENT_NAME="QueenAI-SmartRetrieval-Agent"
REGION="${AWS_REGION:-us-west-2}"
MODEL_ID="us.anthropic.claude-3-7-sonnet-20250219-v1:0"

# Lambda ARNs (must be set as environment variables or updated here)
GET_KPI_DATA_LAMBDA_ARN="${GET_KPI_DATA_LAMBDA_ARN:-}"
EXECUTE_SQL_LAMBDA_ARN="${EXECUTE_SQL_LAMBDA_ARN:-}"

echo ""
echo "Configuration:"
echo "  Agent Name: $AGENT_NAME"
echo "  Region: $REGION"
echo "  Model: $MODEL_ID"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI is not installed"
    exit 1
fi

# Check Lambda ARNs
if [ -z "$GET_KPI_DATA_LAMBDA_ARN" ] || [ -z "$EXECUTE_SQL_LAMBDA_ARN" ]; then
    echo "ERROR: Lambda ARNs not set"
    echo "Please set environment variables:"
    echo "  export GET_KPI_DATA_LAMBDA_ARN=arn:aws:lambda:..."
    echo "  export EXECUTE_SQL_LAMBDA_ARN=arn:aws:lambda:..."
    exit 1
fi

# Check if agent exists
echo "Checking if agent exists..."
AGENT_ID=$(aws bedrock-agent list-agents \
    --region $REGION \
    --query "agentSummaries[?agentName=='$AGENT_NAME'].agentId" \
    --output text 2>/dev/null || echo "")

if [ -z "$AGENT_ID" ]; then
    echo "Agent does not exist. Creating new agent..."
    
    # Read instructions
    INSTRUCTIONS=$(cat instructions.txt)
    
    # Create agent
    AGENT_ID=$(aws bedrock-agent create-agent \
        --region $REGION \
        --agent-name "$AGENT_NAME" \
        --foundation-model "$MODEL_ID" \
        --instruction "$INSTRUCTIONS" \
        --description "Autonomously retrieves data from KPIs and/or transactional database" \
        --query 'agent.agentId' \
        --output text)
    
    echo "Created agent with ID: $AGENT_ID"
else
    echo "Agent exists with ID: $AGENT_ID"
    echo "Updating agent..."
    
    # Read instructions
    INSTRUCTIONS=$(cat instructions.txt)
    
    # Update agent
    aws bedrock-agent update-agent \
        --region $REGION \
        --agent-id "$AGENT_ID" \
        --agent-name "$AGENT_NAME" \
        --foundation-model "$MODEL_ID" \
        --instruction "$INSTRUCTIONS" \
        --description "Autonomously retrieves data from KPIs and/or transactional database"
    
    echo "Updated agent"
fi

echo ""
echo "=========================================="
echo "Configuring Action Groups"
echo "=========================================="

# Note: Action groups must be configured manually in AWS Console or via API
# This is because the schema definitions are complex

echo "Action groups must be configured in AWS Bedrock Console:"
echo ""
echo "1. GetKpiDataActionGroup"
echo "   - Lambda: $GET_KPI_DATA_LAMBDA_ARN"
echo "   - API Path: /get_kpi_data"
echo "   - Method: POST"
echo ""
echo "2. ExecuteSqlQueryActionGroup"
echo "   - Lambda: $EXECUTE_SQL_LAMBDA_ARN"
echo "   - API Path: /execute_sql_query"
echo "   - Method: POST"
echo ""

# Prepare agent
echo "Preparing agent..."
aws bedrock-agent prepare-agent \
    --region $REGION \
    --agent-id "$AGENT_ID"

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo "Agent ID: $AGENT_ID"
echo "Agent Name: $AGENT_NAME"
echo ""
echo "Next steps:"
echo "1. Configure action groups in AWS Console (see above)"
echo "2. Create an agent alias"
echo "3. Test the agent with both tools"
echo "4. Add this agent as a collaborator to the Coordinator Agent"
echo ""
