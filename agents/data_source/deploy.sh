#!/bin/bash
# Deploy script for Data Source Agent

set -e

echo "=========================================="
echo "Data Source Agent Deployment"
echo "=========================================="

# Configuration
AGENT_NAME="QueenAI-DataSource-Agent"
REGION="${AWS_REGION:-us-west-2}"
MODEL_ID="us.anthropic.claude-3-7-sonnet-20250219-v1:0"

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

# Check if agent exists
echo "Checking if agent exists..."
AGENT_ID=$(aws bedrock-agent list-agents \
    --region $REGION \
    --query "agentSummaries[?agentName=='$AGENT_NAME'].agentId" \
    --output text 2>/dev/null || echo "")

if [ -z "$AGENT_ID" ]; then
    echo "Agent does not exist. Creating new agent..."
    
    # Read instructions
    INSTRUCTIONS=$(cat current_instructions.txt)
    
    # Create agent
    AGENT_ID=$(aws bedrock-agent create-agent \
        --region $REGION \
        --agent-name "$AGENT_NAME" \
        --foundation-model "$MODEL_ID" \
        --instruction "$INSTRUCTIONS" \
        --description "Analyzes user questions and determines available data sources" \
        --query 'agent.agentId' \
        --output text)
    
    echo "Created agent with ID: $AGENT_ID"
else
    echo "Agent exists with ID: $AGENT_ID"
    echo "Updating agent..."
    
    # Read instructions
    INSTRUCTIONS=$(cat current_instructions.txt)
    
    # Update agent
    aws bedrock-agent update-agent \
        --region $REGION \
        --agent-id "$AGENT_ID" \
        --agent-name "$AGENT_NAME" \
        --foundation-model "$MODEL_ID" \
        --instruction "$INSTRUCTIONS" \
        --description "Analyzes user questions and determines available data sources"
    
    echo "Updated agent"
fi

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
echo "1. Create an agent alias in AWS Console"
echo "2. Test the agent"
echo "3. Add this agent as a collaborator to the Coordinator Agent"
echo ""
