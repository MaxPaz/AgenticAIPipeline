# Analysis Agent Instructions

This file contains the system instructions for the Analysis Agent in AWS Bedrock.

## Purpose

The Analysis Agent interprets query results and generates business-aware insights. It formats data, creates visualizations, and suggests follow-up questions.

## How to Use

When creating or updating the Analysis Agent in AWS Bedrock Console:

1. Go to AWS Bedrock Console → Agents
2. Select the Analysis Agent
3. In the "Instructions" section, copy the content from `instructions.txt`
4. **IMPORTANT**: Enable "Return to User" option for direct response (performance optimization)
5. Save and create a new version

## Instructions File

The canonical instructions are in: `instructions.txt`

## Recommended Model

**For Performance**: Use Claude 3.5 Haiku
- Model ID: `us.anthropic.claude-3-5-haiku-20241022-v1:0`
- 3-5x faster than Sonnet
- Sufficient for structured analysis tasks
- Lower cost

**Current**: Claude 3.7 Sonnet (slower but more capable)

## Key Capabilities

- Analyzes KPI and transactional data
- Formats data (currency, percentages, dates)
- Generates markdown tables
- Provides business insights
- Suggests follow-up questions
- Validates data quality

## Output Format

Returns JSON with:
- `narrative`: Natural language explanation
- `formatted_data`: Markdown tables
- `key_insights`: Array of 3-5 bullet points
- `data_quality_notes`: Array of data quality issues
- `suggested_questions`: Array of 2-4 follow-up questions
- `success`: Boolean
- `error_message`: String or null

## Performance Optimization

**Enable Direct Response:**
- In Bedrock Console, enable "Return to User" option
- This allows the Analysis Agent to respond directly to the user
- Saves 15-17 seconds by eliminating Coordinator round-trip

## Deployment

See `deploy.sh` for automated deployment script.

## Testing

To test the agent independently:
```bash
python -c "from agents.analysis.analysis_agent import AnalysisAgent; agent = AnalysisAgent(); print(agent.analyze_data('What were sales?', {'kpi_data': [...]}, {}, 'default'))"
```

## Notes

- This agent does NOT have action groups or Lambda functions
- It only analyzes and formats data
- Consider using Haiku model for 3-5x performance improvement
- Enable "Return to User" for direct response optimization
