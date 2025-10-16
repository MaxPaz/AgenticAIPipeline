# Browser Agent - AgentCore Runtime Deployment Guide

This guide explains how to deploy the Browser Agent to AWS Bedrock AgentCore Runtime so it can be called by other Bedrock Agents.

## Overview

The Browser Agent is deployed as a containerized service in AgentCore Runtime, which allows it to be invoked by the Coordinator Agent or other Bedrock Agents for external web search and information extraction.

### Architecture

```
Bedrock Coordinator Agent
    ↓
AgentCore Runtime (Browser Agent Container)
    ↓
Bedrock AgentCore Browser Service (Managed Chrome)
    ↓
Nova Act (Intelligent Automation)
    ↓
Web Pages
```

## Prerequisites

### 1. Install AgentCore Starter Toolkit

```bash
pip install "bedrock-agentcore-starter-toolkit>=0.1.21"
```

### 2. AWS Configuration

Ensure AWS credentials are configured:
```bash
aws configure
# Or verify existing configuration:
aws sts get-caller-identity
```

### 3. Required Permissions

Your IAM user/role needs:
- `bedrock-agentcore:*` - For AgentCore Runtime operations
- `ecr:*` - For pushing Docker images
- `iam:CreateRole`, `iam:AttachRolePolicy` - For creating execution role
- `logs:*` - For CloudWatch logging
- `bedrock:InvokeModel` - For Nova Act

### 4. Environment Variables

Create or update `.env` file:
```bash
AWS_REGION=us-west-2
NOVA_ACT_API_KEY=your_nova_act_api_key_here
```

## Deployment Steps

### Option 1: Automated Deployment (Recommended)

Run the deployment script:

```bash
cd "Browser Agent"
./deploy.sh
```

The script will:
1. Check prerequisites
2. Configure the agent
3. Build and push Docker container
4. Deploy to AgentCore Runtime
5. Test the deployment

### Option 2: Manual Deployment

#### Step 1: Configure the Agent

```bash
cd "Browser Agent"
agentcore configure -e browser_agent.py
```

When prompted:
- **Execution Role**: Press Enter to auto-create
- **ECR Repository**: Press Enter to auto-create
- **Requirements File**: Confirm `requirements.txt`
- **OAuth Configuration**: Type `no`
- **Request Header Allowlist**: Type `no`
- **Memory Configuration**: Type `no` (browser agent doesn't need memory)

#### Step 2: Deploy to AgentCore Runtime

```bash
agentcore launch
```

This will:
- Build Docker container with all dependencies
- Push to Amazon ECR
- Deploy to AgentCore Runtime
- Configure CloudWatch logging
- Activate the endpoint

Expected output:
```
# Container deployed to Bedrock AgentCore
Agent ARN: arn:aws:bedrock-agentcore:us-west-2:123456789:runtime/browser_agent-xyz
```

#### Step 3: Verify Deployment

```bash
agentcore status
```

Expected output:
```
Agent Status: ACTIVE
Endpoint: https://bedrock-agentcore.us-west-2.amazonaws.com/runtime/browser_agent-xyz
```

## Testing the Deployment

### Test 1: Custom Browser Action

```bash
agentcore invoke '{"action": "custom", "prompt": "Go to https://aws.amazon.com and tell me the main heading"}'
```

### Test 2: Company Search

```bash
agentcore invoke '{"action": "search_company", "company_name": "Amazon", "search_type": "news"}'
```

### Test 3: Data Extraction

```bash
agentcore invoke '{"action": "extract_data", "url": "https://aws.amazon.com/bedrock/", "extraction_instructions": "Extract the main features of Amazon Bedrock"}'
```

## Integration with Coordinator Agent

Once deployed, the Browser Agent can be invoked by the Coordinator Agent.

### Method 1: Direct Invocation

The Coordinator Agent can invoke the Browser Agent using the AgentCore Runtime ARN:

```python
import boto3

client = boto3.client('bedrock-agentcore')

response = client.invoke_agent(
    agentId='browser_agent-xyz',
    agentAliasId='TSTALIASID',
    sessionId='unique-session-id',
    inputText=json.dumps({
        "action": "search_company",
        "company_name": "Customer A",
        "search_type": "news"
    })
)
```

### Method 2: As a Sub-Agent

Configure the Coordinator Agent to use the Browser Agent as a sub-agent in the Bedrock console or via CDK.

## Monitoring and Logs

### View Agent Status

```bash
agentcore status
```

### View Logs

```bash
# Get log command from status output
agentcore status

# Then run the command shown, e.g.:
aws logs tail /aws/bedrock-agentcore/runtimes/AGENT_ID-DEFAULT \
  --log-stream-name-prefix "YYYY/MM/DD/[runtime-logs]" \
  --follow
```

### CloudWatch Dashboard

Access the GenAI Observability dashboard:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#gen-ai-observability/agent-core
```

## API Reference

### Invoke Payload Format

The Browser Agent accepts the following payload formats:

#### 1. Company Search

```json
{
  "action": "search_company",
  "company_name": "Amazon",
  "search_type": "news"
}
```

**Parameters:**
- `action`: "search_company"
- `company_name`: Name of the company to search for
- `search_type`: "news", "general", or "financial"

**Response:**
```json
{
  "success": true,
  "company_name": "Amazon",
  "search_type": "news",
  "content": "...",
  "source": "Web search via Nova Act"
}
```

#### 2. Data Extraction

```json
{
  "action": "extract_data",
  "url": "https://example.com",
  "extraction_instructions": "Extract the main heading and first paragraph"
}
```

**Parameters:**
- `action`: "extract_data"
- `url`: URL to navigate to
- `extraction_instructions`: Instructions for what to extract

**Response:**
```json
{
  "success": true,
  "url": "https://example.com",
  "content": "...",
  "source": "Extracted from https://example.com"
}
```

#### 3. Custom Action

```json
{
  "action": "custom",
  "prompt": "Go to AWS website and find information about Bedrock"
}
```

**Parameters:**
- `action`: "custom"
- `prompt`: Natural language instruction for the browser

**Response:**
```json
{
  "success": true,
  "prompt": "...",
  "content": "...",
  "source": "Browser automation via Nova Act"
}
```

## Updating the Agent

### Update Code

1. Modify `browser_agent.py` or `browser_session_manager.py`
2. Redeploy:

```bash
agentcore launch
```

This will create a new version while keeping the old version active.

### Update Dependencies

1. Modify `requirements.txt`
2. Redeploy:

```bash
agentcore launch
```

## Cleanup

To remove all resources:

```bash
agentcore destroy
```

This removes:
- AgentCore Runtime endpoint and agent
- Amazon ECR repository and images
- IAM roles (if auto-created)
- CloudWatch log groups

## Troubleshooting

### Issue: Docker build fails

**Solution**: Ensure Docker is running and you have permissions to build images.

### Issue: ECR push fails

**Solution**: Check IAM permissions for ECR operations:
```bash
aws ecr describe-repositories
```

### Issue: Agent invocation fails with 504 timeout

**Solution**: 
- Check CloudWatch logs for errors
- Verify NOVA_ACT_API_KEY is set correctly
- Increase timeout in agent configuration

### Issue: CAPTCHA challenges

**Solution**: This is expected behavior. Nova Act will not solve CAPTCHAs. Use:
- Direct URLs to specific pages
- Authenticated APIs when possible
- Alternative search methods

### Issue: Memory or resource limits

**Solution**: Adjust container resources in `.bedrock_agentcore.yaml`:
```yaml
resources:
  memory: 2048
  cpu: 1024
```

## Cost Considerations

### AgentCore Runtime Costs
- Container runtime: Per-second billing
- Memory allocation: Based on configured memory
- Network egress: Standard AWS data transfer rates

### Browser Session Costs
- Browser session time: Per-minute billing
- WebSocket connections: Per-connection charges

### Nova Act Costs
- API calls: Per-action billing
- Check Nova Act pricing for current rates

## Best Practices

### 1. Session Management
- Always use context managers to ensure proper cleanup
- Set appropriate timeouts for browser sessions
- Implement retry logic for transient failures

### 2. Error Handling
- Log all errors with sufficient context
- Return structured error responses
- Implement graceful degradation

### 3. Security
- Never log sensitive information
- Validate all input parameters
- Use IAM roles with least privilege
- Rotate API keys regularly

### 4. Performance
- Cache frequently accessed data
- Use specific URLs instead of search when possible
- Implement request throttling
- Monitor CloudWatch metrics

### 5. Monitoring
- Set up CloudWatch alarms for errors
- Monitor invocation latency
- Track browser session duration
- Review logs regularly

## Next Steps

1. ✅ Deploy Browser Agent to AgentCore Runtime
2. ⏭️ Configure Coordinator Agent to use Browser Agent
3. ⏭️ Test end-to-end integration
4. ⏭️ Set up monitoring and alerts
5. ⏭️ Optimize performance based on usage patterns

## Support

For issues or questions:
- Check CloudWatch logs for detailed error messages
- Review the [Bedrock AgentCore Documentation](bedrock-agentcore-dg.pdf)
- Consult the [Nova Act Documentation](https://nova.amazon.com/act)

## Resources

- [AgentCore Starter Toolkit Documentation](https://pypi.org/project/bedrock-agentcore-starter-toolkit/)
- [Bedrock AgentCore Developer Guide](bedrock-agentcore-dg.pdf)
- [Nova Act API Reference](https://nova.amazon.com/act/docs)
- [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
