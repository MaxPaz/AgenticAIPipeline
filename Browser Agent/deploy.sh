#!/bin/bash

# Deploy Browser Agent to Bedrock AgentCore Runtime
# This script uses the agentcore starter toolkit to deploy the browser agent

set -e

echo "=========================================="
echo "Browser Agent - AgentCore Runtime Deployment"
echo "=========================================="

# Check if agentcore toolkit is installed
if ! command -v agentcore &> /dev/null; then
    echo "❌ agentcore toolkit not found"
    echo "Installing bedrock-agentcore-starter-toolkit..."
    pip install "bedrock-agentcore-starter-toolkit>=0.1.21"
fi

# Check AWS credentials
echo ""
echo "📋 Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured"
    echo "Please run: aws configure"
    exit 1
fi

echo "✅ AWS credentials configured"

# Check region
AWS_REGION=$(aws configure get region)
echo "📍 AWS Region: ${AWS_REGION:-us-west-2}"

# Check if NOVA_ACT_API_KEY is set
if [ -z "$NOVA_ACT_API_KEY" ]; then
    echo ""
    echo "⚠️  NOVA_ACT_API_KEY not set in environment"
    echo "Reading from .env file..."
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    fi
    
    if [ -z "$NOVA_ACT_API_KEY" ]; then
        echo "❌ NOVA_ACT_API_KEY not found"
        echo "Please set it in .env file or environment"
        exit 1
    fi
fi

echo "✅ NOVA_ACT_API_KEY configured"

# Configure the agent
echo ""
echo "=========================================="
echo "Step 1: Configure Browser Agent"
echo "=========================================="

# Check if already configured
if [ -f .bedrock_agentcore.yaml ]; then
    echo "⚠️  Existing configuration found"
    read -p "Do you want to reconfigure? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Reconfiguring..."
        agentcore configure -e browser_agent.py
    else
        echo "Using existing configuration"
    fi
else
    echo "Configuring Browser Agent..."
    echo ""
    echo "When prompted:"
    echo "  1. Execution Role: Press Enter to auto-create"
    echo "  2. ECR Repository: Press Enter to auto-create"
    echo "  3. Requirements File: Confirm requirements.txt"
    echo "  4. OAuth Configuration: Type 'no'"
    echo "  5. Request Header Allowlist: Type 'no'"
    echo "  6. Memory Configuration: Type 'no' (browser agent doesn't need memory)"
    echo ""
    
    agentcore configure -e browser_agent.py
fi

# Deploy to AgentCore Runtime
echo ""
echo "=========================================="
echo "Step 2: Deploy to AgentCore Runtime"
echo "=========================================="

echo "Launching Browser Agent to AgentCore Runtime..."
echo "This will:"
echo "  1. Build Docker container with dependencies"
echo "  2. Push to ECR repository"
echo "  3. Deploy to AgentCore Runtime"
echo "  4. Configure CloudWatch logging"
echo "  5. Activate endpoint"
echo ""

agentcore launch

# Check deployment status
echo ""
echo "=========================================="
echo "Step 3: Verify Deployment"
echo "=========================================="

echo "Checking deployment status..."
agentcore status

# Test the deployment
echo ""
echo "=========================================="
echo "Step 4: Test Browser Agent"
echo "=========================================="

echo "Testing with a simple query..."
agentcore invoke '{"action": "custom", "prompt": "Go to https://aws.amazon.com and tell me the main heading"}'

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Your Browser Agent is now deployed to AgentCore Runtime"
echo ""
echo "To invoke the agent:"
echo "  agentcore invoke '{\"action\": \"search_company\", \"company_name\": \"Amazon\", \"search_type\": \"news\"}'"
echo ""
echo "To check status:"
echo "  agentcore status"
echo ""
echo "To view logs:"
echo "  agentcore status  # Get log command from output"
echo ""
echo "To destroy resources:"
echo "  agentcore destroy"
echo ""
