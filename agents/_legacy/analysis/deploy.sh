#!/bin/bash
# Deploy script for Analysis Agent

set -e

echo "=========================================="
echo "Analysis Agent Deployment"
echo "=========================================="

# Configuration
AGENT_NAME="QueenAI-Analysis-Agent"
REGION="${AWS_REGION:-us-west-2}"

# Model selection (set USE_HAIKU=true for performance optimization)
USE_HAIKU="${USE_HAIKU:-false}"

if [ "$USE_HAIKU" = "true" ]; then
    MODEL_ID="us.anthropic.claude-3-5-haiku-20241022-v1:0"
    echo "Using Claude 3.5 Haiku (optimized for performance)"
else
    MODEL_ID="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    echo "Using Claude 3.7 Sonnet (more capable but slower)"
fi

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
    INSTRUCTIONS=$(cat instructions.txt)
    
    # Create agent
    AGENT_ID=$(aws bedrock-agent create-agent \
        --region $REGION \
        --agent-name "$AGENT_NAME" \
        --foundation-model "$MODEL_ID" \
        --instruction "$INSTRUCTIONS" \
        --description "Interprets query results and generates business insights" \
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
        --description "Interprets query results and generates business insights"
    
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
echo "Model: $MODEL_ID"
echo ""
echo "IMPORTANT - Performance Optimization:"
echo "1. In AWS Bedrock Console, enable 'Return to User' option"
echo "   This allows direct response to user (saves 15-17 seconds)"
echo ""
echo "2. Consider using Haiku model for 3-5x performance improvement:"
echo "   export USE_HAIKU=true && ./deploy.sh"
echo ""
echo "Next steps:"
echo "1. Enable 'Return to User' in AWS Console"
echo "2. Create an agent alias"
echo "3. Test the agent"
echo "4. Add this agent as a collaborator to the Coordinator Agent"
echo ""
