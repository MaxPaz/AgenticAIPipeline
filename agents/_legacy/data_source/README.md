# Data Source Agent

## Overview

The Data Source Agent is a Bedrock sub-agent that analyzes user questions and determines what data sources are available to answer them. It acts as a **strategic planner** that recommends data sources without executing queries.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Coordinator Agent (Supervisor)                  │
│                                                              │
│  1. Receives user question                                  │
│  2. Invokes Data Source Agent                               │
│  3. Gets DataSourceDecision recommendation                  │
│  4. Invokes Smart Retrieval Agent with decision             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│           Data Source Agent (Sub-agent)                      │
│                                                              │
│  - Analyzes question against KPI metadata                   │
│  - Identifies available KPIs                                │
│  - Determines if transactional data might be needed         │
│  - Selects date range and frequency                         │
│  - Requests clarification when needed                       │
│                                                              │
│  Returns: DataSourceDecision (JSON)                         │
└─────────────────────────────────────────────────────────────┘
```

## Key Responsibilities

1. **Analyze Questions**: Understand what the user is asking for
2. **Match KPIs**: Identify which pre-calculated KPIs could answer the question
3. **Assess Transactional Need**: Determine if granular data is required
4. **Select Date Range**: Extract or infer appropriate date ranges
5. **Request Clarification**: Identify ambiguous questions

## Important: Strategic Planner, Not Executor

The Data Source Agent:
- ✅ Analyzes and recommends data sources
- ✅ Returns structured decisions
- ❌ Does NOT retrieve data
- ❌ Does NOT execute queries
- ❌ Does NOT have action groups/tools

The Smart Retrieval Agent handles actual data retrieval.

## Data Structures

### DataSourceDecision

```python
@dataclass
class DataSourceDecision:
    kpi_ids: List[int]                    # Empty if no KPIs available
    date_range: str                       # e.g., "2024-01 to 2024-12"
    frequency: str                        # "monthly", "weekly", "daily"
    transactional_might_be_needed: bool   # Hint for Smart Retrieval Agent
    needs_clarification: bool             # True if question is ambiguous
    clarification_question: Optional[str] # Question to ask user
    reasoning: str                        # Explanation of decision
    confidence: float                     # 0.0 to 1.0
```

## Decision Criteria

### When KPIs Are Available
- Question asks for metrics matching KPI definitions
- Aggregated data is sufficient
- Examples: "total sales", "average revenue", "customer count"

### When Transactional Data Might Be Needed
- Question requires store-level or product-level detail
- Specific filters needed (e.g., "stores in California")
- Custom calculations not in KPIs
- Granular data requested (e.g., "list of transactions")

### When Clarification Is Needed
- Date range is ambiguous ("recently", "last period")
- Customer/chain name is unclear
- Multiple interpretations possible
- Frequency not specified

## Examples

### Example 1: Simple KPI Question

**Input:**
```json
{
  "question": "What were our total sales last month?",
  "kpi_metadata": [
    {"kpi_id": 1, "kpi_name": "Net Sales", "definition": "Total sales revenue"}
  ]
}
```

**Output:**
```json
{
  "kpi_ids": [1],
  "date_range": "2024-12 to 2024-12",
  "frequency": "monthly",
  "transactional_might_be_needed": false,
  "needs_clarification": false,
  "clarification_question": null,
  "reasoning": "Question asks for total sales which is available as a KPI. Date range is clear.",
  "confidence": 0.95
}
```

### Example 2: Transactional Detail Needed

**Input:**
```json
{
  "question": "Show me sales by store in California for December 2024"
}
```

**Output:**
```json
{
  "kpi_ids": [],
  "date_range": "2024-12 to 2024-12",
  "frequency": "monthly",
  "transactional_might_be_needed": true,
  "needs_clarification": false,
  "clarification_question": null,
  "reasoning": "Question requires store-level detail with geographic filter. This needs transactional data.",
  "confidence": 0.90
}
```

### Example 3: Ambiguous Date

**Input:**
```json
{
  "question": "What were sales recently?"
}
```

**Output:**
```json
{
  "kpi_ids": [1],
  "date_range": "",
  "frequency": "monthly",
  "transactional_might_be_needed": false,
  "needs_clarification": true,
  "clarification_question": "What time period would you like to see? For example: last month, last quarter, or last year?",
  "reasoning": "The term 'recently' is ambiguous. Need to clarify the specific date range.",
  "confidence": 0.70
}
```

## Deployment

The Data Source Agent is deployed via CDK as part of the Bedrock Agent Stack.

### CDK Deployment

```bash
cd infrastructure/cdk
cdk deploy
```

This creates:
- Data Source Agent (Bedrock sub-agent)
- IAM role with model invocation permissions
- Agent alias (prod)
- Permissions for Coordinator to invoke this agent

### Outputs

After deployment, you'll get:
- `DataSourceAgentId`: Agent ID for invocation
- `DataSourceAgentAliasId`: Alias ID for stable endpoint
- `DataSourceAgentArn`: Full ARN

## Testing

### Run All Tests

```bash
python agents/data_source/test_data_source_agent.py
```

### Interactive Testing

```bash
python agents/data_source/test_data_source_agent.py --interactive
```

### Test Specific Question

```bash
python agents/data_source/test_data_source_agent.py --question "What were sales last month?"
```

## Usage

### From Coordinator Agent

The Coordinator Agent invokes this sub-agent:

```python
# Coordinator Agent invokes Data Source Agent
response = bedrock_agent_runtime.invoke_agent(
    agentId=data_source_agent_id,
    agentAliasId=data_source_agent_alias_id,
    sessionId=session_id,
    inputText=json.dumps({
        "question": user_question,
        "context": conversation_context,
        "kpi_metadata": kpi_list,
        "transactional_schema": schema_list
    })
)

# Parse response
decision = json.loads(response['completion'])
```

### From Python Code (Direct)

```python
from agents.data_source.data_source_agent import DataSourceAgent

agent = DataSourceAgent()
decision = agent.determine_data_source(
    question="What were our sales last month?",
    context={"date_ranges": [], "customers": []},
    org_id="default"
)

print(f"KPI IDs: {decision.kpi_ids}")
print(f"Needs clarification: {decision.needs_clarification}")
```

## Model Configuration

- **Model**: Claude 3.7 Sonnet
- **Reason**: Better structured output (returns clean JSON without extra text)
- **Cost**: ~$3 per 1M input tokens, $15 per 1M output tokens
- **Why not Haiku**: Haiku often adds text before JSON, Sonnet 3.7 follows instructions better

## Files

```
agents/data_source/
├── __init__.py                    # Package initialization
├── data_source_agent.py           # Main agent implementation
├── test_data_source_agent.py      # Test suite
└── README.md                      # This file
```

## Integration with Other Agents

### Workflow

1. **Coordinator Agent** receives user question
2. **Coordinator** invokes **Data Source Agent** with:
   - User question
   - Conversation context
   - KPI metadata
   - Transactional schema
3. **Data Source Agent** analyzes and returns `DataSourceDecision`
4. **Coordinator** checks if clarification is needed:
   - If yes: Ask user and wait for response
   - If no: Proceed to Smart Retrieval Agent
5. **Coordinator** invokes **Smart Retrieval Agent** with decision
6. **Smart Retrieval Agent** uses the decision to retrieve data

## Next Steps

After implementing the Data Source Agent:

1. ✅ Deploy via CDK
2. ✅ Test with various question types
3. ⏭️ Implement Smart Retrieval Agent (Task 7)
4. ⏭️ Configure agent collaboration in Coordinator
5. ⏭️ Test end-to-end workflow

## Troubleshooting

### Agent returns unclear decisions

- Check KPI metadata quality
- Ensure transactional schema is complete
- Review agent instructions in CDK stack

### Low confidence scores

- Question may be genuinely ambiguous
- Consider asking for clarification
- Check if metadata covers the question domain

### Wrong KPI IDs selected

- Review KPI definitions in metadata
- Update agent instructions with better examples
- Consider fine-tuning prompt

## Cost Optimization

- Uses Haiku model for cost efficiency
- Stateless (no memory overhead)
- Fast response times (~1-2 seconds)
- Typical cost: $0.001 - $0.005 per invocation

## Monitoring

Monitor via CloudWatch:
- Invocation count
- Latency
- Error rates
- Clarification request frequency

```bash
aws logs tail /aws/bedrock/agent/DataSourceAgent --follow
```
