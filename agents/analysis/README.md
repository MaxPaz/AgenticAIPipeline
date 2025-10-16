# Analysis Agent

The Analysis Agent interprets query results and generates business-aware insights for QueenAI's agentic chat pipeline.

## Overview

The Analysis Agent is a Bedrock sub-agent that:
- Analyzes KPI and transactional data
- Formats data with proper currency, percentages, and dates
- Generates natural language insights
- Creates markdown tables for data visualization
- Suggests relevant follow-up questions
- Identifies data quality issues

## Architecture

The Analysis Agent can operate in two modes:

1. **Bedrock Agent Mode**: Uses AWS Bedrock Agent for analysis (when agent_id is configured)
2. **Direct Claude Mode**: Uses direct Claude API invocation (fallback mode)

## Features

### Data Formatting

- **Currency**: $1,234.56 with comma separators
- **Percentages**: 45.2% with one decimal place
- **Large Numbers**: 1,234,567 with comma separators
- **Dates**: Converts "2025-M1" to "January 2025"

### Insight Generation

Generates 3-5 key insights that:
- Highlight important trends
- Compare values (e.g., "up 12% from last month")
- Identify outliers or anomalies
- Provide business context
- Are specific and actionable

### Markdown Tables

Creates properly formatted tables:
```markdown
| Metric | Value | Change |
|--------|------:|-------:|
| Revenue | $1.2M | +12% |
| Orders | 5,432 | +8% |
```

### Follow-up Questions

Suggests 2-4 relevant questions that:
- Explore different dimensions (time, geography, product)
- Drill down into details
- Compare segments
- Investigate trends

## Usage

### Basic Usage

```python
from agents.analysis import AnalysisAgent, analyze_data

# Initialize agent
agent = AnalysisAgent(metadata_dir="./metadata")

# Analyze KPI data
retrieval_result = {
    "kpi_data": [
        {"metric_date": "2024-12", "revenue": 2500000, "orders_count": 5432}
    ],
    "data_sources_used": ["KPI"]
}

result = agent.analyze_data(
    question="What were our sales last month?",
    retrieval_result=retrieval_result
)

print(result.narrative)
print(result.formatted_data)
print(result.key_insights)
print(result.suggested_questions)
```

### With Bedrock Agent

```python
# Configure agent IDs
agent = AnalysisAgent(
    agent_id="YOUR_AGENT_ID",
    agent_alias_id="YOUR_ALIAS_ID",
    metadata_dir="./metadata"
)

# Analysis will use Bedrock Agent
result = agent.analyze_data(question, retrieval_result, context)
```

### Convenience Function

```python
from agents.analysis import analyze_data

result = analyze_data(
    question="What were our sales last month?",
    retrieval_result=retrieval_result,
    context={"date_ranges": ["2024-12"]}
)
```

## Data Structures

### AnalysisResult

```python
@dataclass
class AnalysisResult:
    narrative: str  # Natural language explanation
    formatted_data: str  # Markdown tables
    key_insights: List[str]  # Bullet points
    data_quality_notes: List[str]  # Quality issues
    suggested_questions: List[str]  # Follow-ups
    success: bool  # Success flag
    error_message: Optional[str]  # Error if failed
```

## Configuration

### Environment Variables

```bash
# Optional: Use Bedrock Agent
export ANALYSIS_AGENT_ID="your-agent-id"
export ANALYSIS_AGENT_ALIAS_ID="your-alias-id"

# AWS Configuration
export AWS_REGION="us-west-2"
export AWS_PROFILE="your-profile"
```

### Metadata Directory

The agent requires metadata files:
- `metadata/kpi_meta_data.json` - KPI definitions
- `metadata/unique_kpis.json` - Root KPI templates
- `metadata/transactional_meta_data.json` - Schema info

## CDK Deployment

The Analysis Agent can be deployed using AWS CDK:

```python
# In bedrock_agent_stack.py
analysis_agent = bedrock.CfnAgent(
    self, "AnalysisAgent",
    agent_name="QueenAI-Analysis-Agent",
    agent_resource_role_arn=analysis_role.role_arn,
    foundation_model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    instruction=self._get_analysis_instructions(),
    description="Analysis Agent for data interpretation and insights"
)
```

## Testing

```bash
# Run tests
python -m pytest agents/analysis/test_analysis_agent.py -v

# Test with sample data
python agents/analysis/test_analysis_agent.py
```

## Example Output

### Input
```json
{
  "question": "What were our sales last month?",
  "retrieval_result": {
    "kpi_data": [
      {"metric_date": "2024-12", "revenue": 2500000, "orders_count": 5432}
    ]
  }
}
```

### Output
```json
{
  "narrative": "In December 2024, total revenue was $2.5M from 5,432 orders.",
  "formatted_data": "| Metric | Value |\n|--------|------:|\n| Revenue | $2,500,000 |\n| Orders | 5,432 |",
  "key_insights": [
    "Revenue reached $2.5M in December 2024",
    "Order volume was strong at 5,432 transactions"
  ],
  "suggested_questions": [
    "How does this compare to November 2024?",
    "What's the revenue breakdown by region?"
  ],
  "success": true
}
```

## Requirements

See `requirements.txt` in the project root:
- boto3 >= 1.28.0
- python-dotenv >= 1.0.0

## Integration

The Analysis Agent integrates with:
- **Coordinator Agent**: Receives analysis requests
- **Smart Retrieval Agent**: Receives data to analyze
- **Streamlit UI**: Displays formatted results

## Best Practices

1. **Always format numbers**: Use proper currency, percentage, and number formatting
2. **Generate specific insights**: Avoid generic statements
3. **Create clean tables**: Use proper markdown formatting
4. **Suggest relevant questions**: Base suggestions on the data and context
5. **Note quality issues**: Always report data quality problems
6. **Be concise**: Keep narratives focused and actionable

## Troubleshooting

### JSON Parsing Errors

If the agent returns invalid JSON:
- Check the model temperature (should be low for structured output)
- Verify the instructions are clear about JSON-only output
- Use the fallback parsing logic

### Missing Insights

If insights are generic:
- Provide more context in the input
- Include KPI metadata for better interpretation
- Use Claude 3.5 Sonnet for higher quality analysis

### Formatting Issues

If data formatting is incorrect:
- Verify the formatting rules in instructions
- Check that the model has access to the data
- Test with simpler data first

## Future Enhancements

- Chart generation (matplotlib, plotly)
- Anomaly detection
- Trend analysis
- Comparative analysis across periods
- Export to PDF/Excel
