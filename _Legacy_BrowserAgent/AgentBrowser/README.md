# External Search Agent

A Bedrock Agent that provides external web search capabilities using the Browser Agent (AgentCore Runtime).

## Architecture

```
User Question
     ↓
External Search Agent (Bedrock Agent)
     ↓
Action Group (Lambda)
     ↓
Browser Agent (AgentCore Runtime)
     ↓
Nova Act + Bedrock Browser
     ↓
Web Search Results
```

## Components

### 1. External Search Agent (Bedrock Agent)
- **Model**: Claude 3.5 Sonnet
- **Purpose**: Determines when to use external search and orchestrates web browsing
- **Instructions**: `external_search_instructions.txt`

### 2. Action Group (Lambda Function)
- **Function**: `external_search_lambda.py`
- **Purpose**: Bridges Bedrock Agent and Browser Agent
- **Actions**:
  - `search_company_info`: Search for company information
  - `extract_web_data`: Extract data from specific URLs
  - `custom_browse`: Execute custom browsing with natural language

### 3. Browser Agent (AgentCore Runtime)
- **Location**: `../browser_agent.py`
- **Purpose**: Executes actual web browsing using Nova Act
- **ARN**: `arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:runtime/browser_agent-ID`

## Deployment

### Prerequisites
- Browser Agent must be deployed (see `../README.md`)
- AWS credentials configured
- Python 3.11+
- boto3 installed

### Deploy the Agent

```bash
python deploy_external_search_agent.py
```

This will:
1. Create Lambda execution role
2. Deploy Lambda function
3. Create Bedrock Agent role
4. Create/update External Search Agent
5. Create action group
6. Prepare agent and create alias

### Deployment Output

```
Agent ID: XXXXXXXXXX
Agent Alias ID: XXXXXXXXXX
Lambda Function: arn:aws:lambda:us-west-2:ACCOUNT:function:external-search-lambda
```

Save these IDs for testing!

## Testing

### Run Test Scenarios

```bash
python test_external_search_agent.py
```

Select option 1 to run predefined test scenarios:
- Company news search
- Stock price queries
- Company information
- Custom web browsing
- URL data extraction

### Interactive Mode

```bash
python test_external_search_agent.py
```

Select option 2 for interactive testing.

### Example Queries

**Company News:**
```
What's the latest news about Tesla?
```

**Stock Price:**
```
What's Amazon's current stock price?
```

**Company Information:**
```
Tell me about Microsoft's recent acquisitions
```

**Custom Browse:**
```
Go to Google and search for 'Apple earnings Q4 2024'
```

**URL Extraction:**
```
Extract the main headline from https://www.infobae.com
```

## API Reference

### search_company_info

Search for company information on the web.

**Parameters:**
- `company_name` (required): Name of the company
- `search_type` (optional): Type of search
  - `news`: Recent news articles
  - `general`: Company overview
  - `financial`: Financial metrics

**Example:**
```json
{
  "company_name": "Tesla",
  "search_type": "news"
}
```

### extract_web_data

Extract specific data from a URL.

**Parameters:**
- `url` (required): URL to navigate to
- `extraction_instructions` (required): What to extract

**Example:**
```json
{
  "url": "https://finance.yahoo.com/quote/TSLA",
  "extraction_instructions": "Extract the current stock price"
}
```

### custom_browse

Execute custom browsing action with natural language.

**Parameters:**
- `prompt` (required): Natural language instruction

**Example:**
```json
{
  "prompt": "Go to Google, search for 'Amazon Q4 earnings', and summarize the top result"
}
```

## Integration with Coordinator Agent

To integrate with your existing Coordinator Agent:

1. **Add as Sub-Agent** (if using agent collaboration):
   ```python
   # In Coordinator Agent instructions
   "When user asks for external/recent information, invoke ExternalSearchAgent"
   ```

2. **Add as Action Group** (alternative approach):
   - Export the OpenAPI schema
   - Add as action group to Coordinator Agent
   - Lambda will handle routing to Browser Agent

3. **Manual Invocation** (from Streamlit):
   ```python
   # Invoke External Search Agent directly
   response = bedrock_agent_runtime.invoke_agent(
       agentId="EXTERNAL_SEARCH_AGENT_ID",
       agentAliasId="ALIAS_ID",
       sessionId=session_id,
       inputText=user_question
   )
   ```

## Troubleshooting

### Lambda Timeout
- Increase Lambda timeout (currently 300s)
- Browser operations can take 30-60 seconds

### Permission Errors
- Verify Lambda has permission to invoke Browser Agent
- Check IAM roles have correct policies

### Browser Agent Not Responding
- Verify Browser Agent is deployed and running
- Check Browser Agent ARN in Lambda environment variables
- Test Browser Agent directly: `agentcore invoke '{"action": "custom", "prompt": "test"}'`

### No Results Returned
- Check CloudWatch logs for Lambda function
- Verify OpenAPI schema matches Lambda handler
- Test Lambda function directly in AWS Console

## Monitoring

### CloudWatch Logs

**Lambda Logs:**
```bash
aws logs tail /aws/lambda/external-search-lambda --follow
```

**Browser Agent Logs:**
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/browser_agent-C0OfY22wUw-DEFAULT --follow
```

### Metrics to Monitor
- Lambda invocation count
- Lambda duration
- Lambda errors
- Browser Agent invocation count
- Browser Agent response times

## Cost Considerations

- **Lambda**: ~$0.20 per 1M requests + compute time
- **Bedrock Agent**: ~$0.002 per 1K input tokens, ~$0.008 per 1K output tokens
- **Browser Agent (AgentCore)**: Charged per session/minute
- **Nova Act**: API usage charges

Estimated cost per query: $0.05 - $0.15 depending on complexity

## Limitations

- Browser operations can be slow (30-60 seconds)
- Some websites may block automated browsing
- Rate limiting may apply for frequent searches
- Nova Act API key required (set in Browser Agent)

## Future Enhancements

- [ ] Add caching for frequently searched companies
- [ ] Implement parallel searches for multiple companies
- [ ] Add support for more search engines
- [ ] Implement result ranking and relevance scoring
- [ ] Add support for image extraction
- [ ] Implement PDF document extraction

## Support

For issues or questions:
1. Check CloudWatch logs
2. Test Browser Agent independently
3. Verify all IAM permissions
4. Review OpenAPI schema and Lambda handler alignment
