#!/usr/bin/env python3
"""
CDK App for QueenAI Agentic Chat Pipeline Infrastructure
"""

import os
from aws_cdk import App, Environment
from bedrock_agent_stack import BedrockAgentStack

app = App()

# Get environment from context or use defaults
env = Environment(
    account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
    region=os.environ.get('CDK_DEFAULT_REGION', 'us-west-2')
)

# Create Bedrock Agent Stack
BedrockAgentStack(
    app,
    "QueenAI-BedrockAgent-Stack",
    env=env,
    description="Bedrock Coordinator Agent for QueenAI agentic chat pipeline"
)

app.synth()
