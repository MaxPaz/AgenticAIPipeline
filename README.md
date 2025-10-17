# Infrastructure Deployment - Bedrock Coordinator Agent

## Overview

This directory contains AWS CDK infrastructure code to deploy the Bedrock Coordinator Agent.
Due to current CDK limitations, the infrastructre needs manual support to be created.

This project was built with Kiro --> https://kiro.dev/

## Prerequisites

1. **AWS CLI configured** with credentials
2. **Node.js** installed (for CDK CLI)
3. **Python 3.9+** installed
4. **AWS CDK CLI** installed

## Quick Start

```bash
# 1. Install CDK CLI (if not already installed)
npm install -g aws-cdk

# 2. Install Python dependencies
cd infrastructure/cdk
pip install -r requirements.txt

# 3. Bootstrap CDK (first time only)
cdk bootstrap

# 4. Deploy the stack
cdk deploy

# 5. Copy outputs to .env file
# The deployment will output BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID
```

## Detailed Steps

### Step 1: Install CDK CLI

```bash
npm install -g aws-cdk

# Verify installation
cdk --version
```

### Step 2: Install Python Dependencies

```bash
cd infrastructure/cdk
pip install -r requirements.txt
```

### Step 3: Bootstrap CDK (First Time Only)

This creates the necessary S3 bucket and IAM roles for CDK deployments:

```bash
cdk bootstrap aws://ACCOUNT-ID/us-west-2
```

Or let CDK auto-detect your account:

```bash
cdk bootstrap
```

### Step 4: Preview Changes (Optional)

See what will be created:

```bash
cdk diff
```

### Step 5: Deploy

```bash
cdk deploy
```

You'll see output like:

```
✅  QueenAI-BedrockAgent-Stack

Outputs:
QueenAI-BedrockAgent-Stack.AgentId = XXXXXXXXXX
QueenAI-BedrockAgent-Stack.AgentAliasId = XXXXXXXXXX
QueenAI-BedrockAgent-Stack.AgentArn = arn:aws:bedrock:us-west-2:123456789012:agent/XXXXXXXXXX
QueenAI-BedrockAgent-Stack.AgentRoleArn = arn:aws:iam::123456789012:role/QueenAI-Bedrock-Agent-Role
```

### Step 6: Update .env File

Copy the outputs to your `.env` file in the project root:

```bash
# Add these to .env
BEDROCK_AGENT_ID=XXXXXXXXXX
BEDROCK_AGENT_ALIAS_ID=XXXXXXXXXX
AWS_REGION=us-west-2
```

## What Gets Deployed

The CDK stack creates:

1. **IAM Role** (`QueenAI-Bedrock-Agent-Role`)
   - Trust policy for Bedrock service
   - Permissions to invoke foundation models

2. **Bedrock Agent** (`QueenAI-Coordinator-Agent`)
   - Claude 3.5 Sonnet model
   - Session memory enabled (30 days)
   - Orchestration instructions configured

3. **Agent Alias** (`prod`)
   - Production alias for stable endpoint

## CDK Commands

```bash
# List all stacks
cdk list

# Show differences
cdk diff

# Deploy stack
cdk deploy

# Destroy stack (cleanup)
cdk destroy

# Synthesize CloudFormation template
cdk synth
```

## Updating the Agent

To update agent configuration:

1. Edit `infrastructure/cdk/bedrock_agent_stack.py`
2. Run `cdk diff` to preview changes
3. Run `cdk deploy` to apply changes

## Cleanup

To remove all resources:

```bash
cdk destroy
```

This will delete:
- Bedrock Agent
- Agent Alias
- IAM Role

## Troubleshooting

### "CDK not found"

Install CDK CLI:
```bash
npm install -g aws-cdk
```

### "Bootstrap required"

Run bootstrap:
```bash
cdk bootstrap
```

### "Access Denied"

Ensure your AWS credentials have permissions for:
- IAM (create roles)
- Bedrock (create agents)
- CloudFormation (create stacks)

### "Model not available"

Check available models in your region:
```bash
aws bedrock list-foundation-models --region us-west-2
```

## Cost Estimate

- **IAM Role**: Free
- **Bedrock Agent**: Free (no charge for agent itself)
- **Model Usage**: Pay per token
  - Claude 3.5 Sonnet: ~$3 input / $15 output per 1M tokens
  - Typical conversation: $0.01 - $0.05

## Next Steps

After deployment:

1. Test the agent:
   ```bash
   python agents/test_coordinator_agent.py
   ```

2. Run examples:
   ```bash
   python agents/example_usage.py
   ```

3. Integrate with Streamlit UI (Task 12)

## Architecture

```
CDK Stack
├── IAM Role
│   └── Bedrock model invocation permissions
├── Bedrock Agent
│   ├── Foundation Model: Claude 3.5 Sonnet
│   ├── Memory: SESSION_SUMMARY (30 days)
│   └── Instructions: Orchestration logic
└── Agent Alias (prod)
    └── Stable endpoint for production
```

## Files

- `app.py` - CDK app entry point
- `bedrock_agent_stack.py` - Stack definition
- `requirements.txt` - Python dependencies
- `cdk.json` - CDK configuration
- `README.md` - This file
