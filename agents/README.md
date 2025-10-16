# Agents

This directory contains the agent configurations and deployment scripts for the QueenAI agentic chat pipeline.

## ⚠️ Important: Bedrock Agents, Not Python

**The agents are configured and run in AWS Bedrock Console, NOT as Python code.**

- The Python files (`.py`) are **reference implementations only**
- Actual execution happens in AWS Bedrock via Agent Collaboration
- Streamlit UI calls Bedrock directly using `bedrock_client.invoke_agent()`

## Agent Structure

### Coordinator Agent (this folder)
- **Purpose**: Orchestrates the entire workflow
- **Files**:
  - `coordinator_instructions.txt` - System instructions for Bedrock
  - `deploy_coordinator.sh` - Deployment script
  - `requirements.txt` - Python dependencies (reference only)
  - `INSTRUCTIONS.md` - Documentation

### Specialized Agents (subfolders)

Each agent folder contains:
- `instructions.txt` - System instructions for Bedrock
- `deploy.sh` - Deployment script
- `requirements.txt` - Python dependencies (reference only)
- `INSTRUCTIONS.md` - Documentation
- `*.py` - Reference implementation (NOT used in production)

## Deployment Order

Deploy agents in this order:

1. **Data Source Agent** (no dependencies)
   ```bash
   cd data_source
   ./deploy.sh
   ```

2. **Smart Retrieval Agent** (requires Lambda functions)
   ```bash
   cd smart_retrieval
   export GET_KPI_DATA_LAMBDA_ARN=arn:aws:lambda:...
   export EXECUTE_SQL_LAMBDA_ARN=arn:aws:lambda:...
   ./deploy.sh
   ```

3. **Analysis Agent** (no dependencies)
   ```bash
   cd analysis
   # For performance: export USE_HAIKU=true
   ./deploy.sh
   ```

4. **Coordinator Agent** (requires all 3 agents above)
   ```bash
   cd ..  # back to agents folder
   export DATA_SOURCE_AGENT_ID=<agent-id>
   export SMART_RETRIEVAL_AGENT_ID=<agent-id>
   export ANALYSIS_AGENT_ID=<agent-id>
   ./deploy_coordinator.sh
   ```

## Agent Collaboration

After deploying all agents, configure Agent Collaboration in AWS Bedrock Console:

1. Go to Coordinator Agent → Agent Collaboration
2. Add collaborators:
   - DataSourceAgent
   - SmartRetrievalAgent
   - AnalysisAgent (enable "Return to User" for performance)

## Testing

Test the complete workflow:
```bash
# Update environment variables
export BEDROCK_AGENT_ID=<coordinator-agent-id>
export BEDROCK_AGENT_ALIAS_ID=<alias-id>
export AWS_REGION=us-west-2

# Run Streamlit UI
cd ../ui
streamlit run app.py
```

## Performance Optimization

See `../OPTIMIZATION_RECOMMENDATIONS.md` for detailed performance tuning.

**Key optimizations:**
- Switch Analysis Agent to Haiku (3-5x faster)
- Enable direct response from Analysis Agent
- Enable prompt caching

## Documentation

- `INSTRUCTIONS.md` - Coordinator Agent documentation
- `data_source/INSTRUCTIONS.md` - Data Source Agent documentation
- `smart_retrieval/INSTRUCTIONS.md` - Smart Retrieval Agent documentation
- `analysis/INSTRUCTIONS.md` - Analysis Agent documentation
- `../BEDROCK_AGENT_ARCHITECTURE.md` - Complete architecture guide
