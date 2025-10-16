# Coordinator Agent Instructions

This file contains the system instructions for the Coordinator Agent in AWS Bedrock.

## Purpose

The Coordinator Agent orchestrates the entire agentic chat pipeline. It manages conversation context, routes to specialized agents, and returns the final response to the user.

## How to Use

When creating or updating the Coordinator Agent in AWS Bedrock Console:

1. Go to AWS Bedrock Console → Agents
2. Select the Coordinator Agent (or create new)
3. In the "Instructions" section, copy the content from `coordinator_instructions.txt`
4. Configure Agent Collaboration (see below)
5. Save and create a new version

## Instructions File

The canonical instructions are in: `coordinator_instructions.txt`

## Agent Collaboration

The Coordinator Agent must be configured to collaborate with 3 specialized agents:

### Required Collaborators:

1. **DataSourceAgent**
   - Agent ID: (from Data Source Agent deployment)
   - Purpose: Determines available data sources

2. **SmartRetrievalAgent**
   - Agent ID: (from Smart Retrieval Agent deployment)
   - Purpose: Retrieves data autonomously

3. **AnalysisAgent**
   - Agent ID: (from Analysis Agent deployment)
   - Purpose: Generates insights and formats data
   - **IMPORTANT**: Enable "Return to User" for this agent (performance optimization)

## Recommended Model

**Model**: Claude 3.7 Sonnet
- Model ID: `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
- Needed for complex orchestration and context management

## Key Capabilities

- Orchestrates 4-agent workflow
- Manages conversation context
- Routes to specialized agents
- Handles clarifications
- Provides progress updates
- Error handling

## Deployment

See `deploy_coordinator.sh` for automated deployment script.

## Testing

To test the coordinator agent:
```bash
# Via Streamlit UI
streamlit run ui/app.py

# Or via AWS CLI
aws bedrock-agent-runtime invoke-agent \
    --agent-id <coordinator-agent-id> \
    --agent-alias-id <alias-id> \
    --session-id test-session \
    --input-text "What were Customer A sales in 2023?"
```

## Notes

- This agent requires all 3 specialized agents to be deployed first
- Agent collaboration must be configured in Bedrock Console
- Session management is handled automatically by Bedrock
