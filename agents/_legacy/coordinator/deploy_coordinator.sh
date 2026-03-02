#!/bin/bash
# Deploy script for Coordinator Agent with Agent Collaboration

set -e

echo "=========================================="
echo "Coordinator Agent Deployment"
echo "=========================================="

# Configuration
AGENT_NAME="QueenAI-Coordinator-Agent"
REGION="${AWS_REGION:-us-west-2}"
MODEL_ID="us.anthropic.claude-3-7-sonnet-20250219-v1:0"

# Collaborator Agent IDs (must be set as environment variables or updated here)
DATA_SOURCE_AGENT_ID="${DATA_SOURCE_AGENT_ID:-}"
SMART_RETRIEVAL_AGENT_ID="${SMART_RETRIEVAL_AGENT_ID:-}"
ANALYSIS_AGENT_ID="${ANALYSIS_AGENT_ID:-}"

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

# Check collaborator agent IDs
if [ -z "$DATA_SOURCE_AGENT_ID" ] || [ -z "$SMART_RETRIEVAL_AGENT_ID" ] || [ -z "$ANALYSIS_AGENT_ID" ]; then
    echo "WARNING: Collaborator agent IDs not set"
    echo "Agent collaboration must be configured manually in AWS Console"
    echo ""
    echo "Required environment variables:"
    echo "  export DATA_SOURCE_AGENT_ID=<agent-id>"
    echo "  export SMART_RETRIEVAL_AGENT_ID=<agent-id>"
    echo "  export ANALYSIS_AGENT_ID=<agent-id>"
    echo ""
    SKIP_COLLABORATION=true
else
    SKIP_COLLABORATION=false
    echo "Collaborator Agents:"
    echo "  Data Source Agent: $DATA_SOURCE_AGENT_ID"
    echo "  Smart Retrieval Agent: $SMART_RETRIEVAL_AGENT_ID"
    echo "  Analysis Agent: $ANALYSIS_AGENT_ID"
    echo ""
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
    INSTRUCTIONS=$(cat coordinator_instructions.txt)
    
    # Create agent
    AGENT_ID=$(aws bedrock-agent create-agent \
        --region $REGION \
        --agent-name "$AGENT_NAME" \
        --foundation-model "$MODEL_ID" \
        --instruction "$INSTRUCTIONS" \
        --description "Orchestrates the agentic chat pipeline and manages specialized agents" \
        --query 'agent.agentId' \
        --output text)
    
    echo "Created agent with ID: $AGENT_ID"
else
    echo "Agent exists with ID: $AGENT_ID"
    echo "Updating agent..."
    
    # Read instructions
    INSTRUCTIONS=$(cat coordinator_instructions.txt)
    
    # Update agent
    aws bedrock-agent update-agent \
        --region $REGION \
        --agent-id "$AGENT_ID" \
        --agent-name "$AGENT_NAME" \
        --foundation-model "$MODEL_ID" \
        --instruction "$INSTRUCTIONS" \
        --description "Orchestrates the agentic chat pipeline and manages specialized agents"
    
    echo "Updated agent"
fi

echo ""
echo "=========================================="
echo "Configuring Agent Collaboration"
echo "=========================================="

if [ "$SKIP_COLLABORATION" = "true" ]; then
    echo "Skipping agent collaboration configuration (agent IDs not provided)"
    echo ""
    echo "To configure agent collaboration:"
    echo "1. Go to AWS Bedrock Console → Agents"
    echo "2. Select the Coordinator Agent"
    echo "3. Go to 'Agent Collaboration' section"
    echo "4. Add the following collaborators:"
    echo "   - DataSourceAgent"
    echo "   - SmartRetrievalAgent"
    echo "   - AnalysisAgent (enable 'Return to User')"
    echo ""
else
    echo "Configuring agent collaboration..."
    echo ""
    echo "Note: Agent collaboration must be configured via AWS Console"
    echo "The AWS CLI does not fully support agent collaboration configuration yet"
    echo ""
    echo "Manual steps required:"
    echo "1. Go to AWS Bedrock Console → Agents → $AGENT_NAME"
    echo "2. Click 'Agent Collaboration'"
    echo "3. Add collaborator: DataSourceAgent"
    echo "   - Agent ID: $DATA_SOURCE_AGENT_ID"
    echo "   - Alias: DRAFT or specific alias"
    echo ""
    echo "4. Add collaborator: SmartRetrievalAgent"
    echo "   - Agent ID: $SMART_RETRIEVAL_AGENT_ID"
    echo "   - Alias: DRAFT or specific alias"
    echo ""
    echo "5. Add collaborator: AnalysisAgent"
    echo "   - Agent ID: $ANALYSIS_AGENT_ID"
    echo "   - Alias: DRAFT or specific alias"
    echo "   - ⚠️ IMPORTANT: Enable 'Return to User' option"
    echo ""
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
echo "1. Configure agent collaboration in AWS Console (see above)"
echo "2. Create an agent alias"
echo "3. Update Streamlit UI with agent ID and alias ID"
echo "4. Test end-to-end workflow"
echo ""
echo "Streamlit configuration:"
echo "  export BEDROCK_AGENT_ID=$AGENT_ID"
echo "  export BEDROCK_AGENT_ALIAS_ID=<your-alias-id>"
echo "  export AWS_REGION=$REGION"
echo ""
