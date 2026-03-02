# Data Source Agent Instructions

This file contains the system instructions for the Data Source Agent in AWS Bedrock.

## Purpose

The Data Source Agent analyzes user questions and determines what data sources are available to answer them. It does NOT retrieve data - it only recommends data sources.

## How to Use

When creating or updating the Data Source Agent in AWS Bedrock Console:

1. Go to AWS Bedrock Console → Agents
2. Select the Data Source Agent
3. In the "Instructions" section, copy the content from `current_instructions.txt`
4. Save and create a new version

## Instructions File

The canonical instructions are in: `current_instructions.txt`

## Key Capabilities

- Analyzes user questions
- Matches questions against KPI metadata
- Determines if transactional data is needed
- Selects appropriate date ranges and frequency
- Requests clarification when needed

## Output Format

Returns JSON with:
- `kpi_ids`: List of matching KPI IDs
- `date_range`: Date range in "YYYY-MM to YYYY-MM" format
- `frequency`: "monthly", "weekly", or "daily"
- `transactional_might_be_needed`: Boolean
- `needs_clarification`: Boolean
- `clarification_question`: String or null
- `reasoning`: Explanation
- `confidence`: 0.0 to 1.0

## Testing

To test the agent independently:
```bash
python -c "from agents.data_source.data_source_agent import DataSourceAgent; agent = DataSourceAgent(); print(agent.determine_data_source('What were sales last month?', {}, 'default'))"
```

## Notes

- This agent does NOT have action groups or Lambda functions
- It only analyzes and recommends
- The Smart Retrieval Agent handles actual data retrieval
