"""
Data Source Agent

This module implements the Data Source Agent that analyzes user questions
and determines what data sources are available (KPIs vs transactional data).

The Data Source Agent is a strategic planner that:
- Analyzes questions against available KPI metadata
- Identifies if pre-calculated KPIs exist for the question
- Determines if transactional data might be needed
- Selects appropriate date ranges and frequencies
- Requests clarification when needed
"""

import json
import os
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from config.aws_config import aws_config
from tools.metadata_loader import MetadataLoader, KPIMetadata, TableSchema


@dataclass
class DataSourceDecision:
    """
    Decision about what data sources are available for a question.
    
    This is a strategic recommendation, not an execution result.
    """
    kpi_ids: List[int]  # Empty if no KPIs available
    date_range: str  # e.g., "2024-01" to "2024-12"
    frequency: str  # e.g., "monthly", "weekly", "daily"
    transactional_might_be_needed: bool  # Hint that transactional may be needed
    needs_clarification: bool
    clarification_question: Optional[str]
    reasoning: str  # Explanation of the decision
    confidence: float  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class DataSourceAgent:
    """
    Data Source Agent that determines what data sources are available.
    
    This agent analyzes user questions against KPI metadata and transactional
    schema to determine the best data sources to answer the question.
    
    Key responsibilities:
    - Analyze question against available KPIs
    - Identify if pre-calculated KPIs exist
    - Determine if transactional data might be needed
    - Select appropriate date ranges and frequencies
    - Request clarification when needed
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        agent_alias_id: Optional[str] = None,
        region: Optional[str] = None,
        metadata_dir: str = "./metadata"
    ):
        """
        Initialize the Data Source Agent.
        
        Args:
            agent_id: Bedrock Agent ID (if using separate agent)
            agent_alias_id: Bedrock Agent Alias ID
            region: AWS region
            metadata_dir: Directory containing metadata JSON files
        """
        self.agent_id = agent_id
        self.agent_alias_id = agent_alias_id
        self.region = region or aws_config.region
        
        # Initialize Bedrock clients
        self.bedrock_runtime = aws_config.get_bedrock_runtime_client()
        
        # Initialize metadata loader
        self.metadata_loader = MetadataLoader(metadata_dir)
        
        # Load metadata
        self.kpi_metadata: List[KPIMetadata] = []
        self.transactional_schema: List[TableSchema] = []
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load metadata from JSON files."""
        try:
            self.kpi_metadata = self.metadata_loader.get_kpi_metadata()
            self.transactional_schema = self.metadata_loader.get_transactional_schema()
        except Exception as e:
            print(f"Warning: Failed to load metadata: {e}")

    def _get_agent_instructions(self) -> str:
        """Get the data source agent instructions."""
        return """You are the Data Source Agent for QueenAI's agentic chat pipeline.

Your role is to analyze user questions and determine what data sources are AVAILABLE to answer them.

## Your Responsibilities:

1. **Analyze the Question**: Understand what the user is asking for.

2. **Match Against KPI Metadata**: Determine if pre-calculated KPIs exist that could answer this question.

3. **Assess Transactional Need**: Determine if transactional data might be needed for more detailed analysis.

4. **Select Date Range and Frequency**: Based on the question, determine appropriate date range and frequency.

5. **Request Clarification**: If the question is ambiguous, identify what needs clarification.

## Important: You are a Strategic Planner, NOT an Executor

- You DO NOT retrieve data
- You DO NOT execute queries
- You ONLY analyze and recommend what data sources are available
- The Smart Retrieval Agent will handle actual data retrieval

## Decision Criteria:

### When KPIs Are Available:
- The question asks for metrics that match KPI definitions
- The question can be answered with aggregated data
- Examples: "total sales", "average revenue", "customer count"

### When Transactional Data Might Be Needed:
- The question requires store-level or product-level detail
- The question needs specific filters (e.g., "stores in California")
- The question requires custom calculations not in KPIs
- The question asks for granular data (e.g., "list of transactions")

### When Clarification Is Needed:
- Date range is ambiguous (e.g., "recently", "last period")
- Customer/chain name is unclear
- Multiple interpretations are possible
- Frequency is not specified (monthly vs weekly vs daily)

## Output Format:

You must return a JSON object with this structure:
{
  "kpi_ids": [list of KPI IDs that match, or empty list],
  "date_range": "YYYY-MM to YYYY-MM",
  "frequency": "monthly|weekly|daily",
  "transactional_might_be_needed": true|false,
  "needs_clarification": true|false,
  "clarification_question": "specific question to ask user, or null",
  "reasoning": "explanation of your decision",
  "confidence": 0.0 to 1.0
}

## Examples:

Question: "What were our total sales last month?"
Decision:
{
  "kpi_ids": [1, 2],  # Assuming KPI IDs for sales metrics
  "date_range": "2024-12 to 2024-12",
  "frequency": "monthly",
  "transactional_might_be_needed": false,
  "needs_clarification": false,
  "clarification_question": null,
  "reasoning": "Question asks for total sales which is available as a KPI. Date range is clear (last month).",
  "confidence": 0.95
}

Question: "Show me sales by store in California"
Decision:
{
  "kpi_ids": [],
  "date_range": "2024-12 to 2024-12",  # Assuming current context
  "frequency": "monthly",
  "transactional_might_be_needed": true,
  "needs_clarification": false,
  "clarification_question": null,
  "reasoning": "Question requires store-level detail with geographic filter. This needs transactional data, not aggregated KPIs.",
  "confidence": 0.90
}

Question: "What were sales recently?"
Decision:
{
  "kpi_ids": [1, 2],
  "date_range": "",
  "frequency": "monthly",
  "transactional_might_be_needed": false,
  "needs_clarification": true,
  "clarification_question": "What time period would you like to see? For example: last month, last quarter, or last year?",
  "reasoning": "The term 'recently' is ambiguous. Need to clarify the specific date range.",
  "confidence": 0.70
}
"""

    def determine_data_source(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        org_id: str = "default"
    ) -> DataSourceDecision:
        """
        Determine what data sources are available for the question.
        
        This method uses Claude to analyze the question against available
        metadata and make a strategic decision about data sources.
        
        Args:
            question: User's question
            context: Conversation context (date ranges, customers, etc.)
            org_id: Organization ID
            
        Returns:
            DataSourceDecision with recommendations
        """
        # Prepare context
        context = context or {}
        
        # Build prompt with metadata
        prompt = self._build_analysis_prompt(question, context)
        
        # Invoke Claude to analyze
        try:
            response = self._invoke_claude(prompt)
            decision = self._parse_decision(response)
            return decision
        except Exception as e:
            # Fallback decision on error
            return DataSourceDecision(
                kpi_ids=[],
                date_range="",
                frequency="monthly",
                transactional_might_be_needed=True,
                needs_clarification=True,
                clarification_question=f"I encountered an error analyzing your question. Could you rephrase it?",
                reasoning=f"Error during analysis: {str(e)}",
                confidence=0.0
            )

    def _build_analysis_prompt(
        self,
        question: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Build the analysis prompt with question and metadata.
        
        Args:
            question: User's question
            context: Conversation context
            
        Returns:
            Formatted prompt string
        """
        # Format KPI metadata
        kpi_list = []
        for kpi in self.kpi_metadata[:50]:  # Limit to first 50 to avoid token limits
            kpi_list.append({
                'kpi_id': kpi.kpi_id,
                'kpi_name': kpi.kpi_name,
                'definition': kpi.short_definition,
                'unit': kpi.unit,
                'group': kpi.group_name
            })
        
        # Format transactional schema
        schema_list = []
        for table in self.transactional_schema:
            schema_list.append({
                'table_name': table.table_name,
                'columns': [col.name for col in table.columns[:10]]  # First 10 columns
            })
        
        # Build prompt
        prompt = f"""Analyze the following user question and determine what data sources are available.

## User Question:
{question}

## Conversation Context:
{json.dumps(context, indent=2)}

## Available KPI Metadata:
{json.dumps(kpi_list, indent=2)}

## Available Transactional Tables:
{json.dumps(schema_list, indent=2)}

## Your Task:
Analyze the question against the available KPIs and transactional schema.
Determine:
1. Which KPI IDs (if any) could answer this question
2. What date range is needed (extract from question or context)
3. What frequency is appropriate (monthly, weekly, daily)
4. Whether transactional data might be needed for more detail
5. Whether clarification is needed

Return ONLY a valid JSON object with the decision structure specified in your instructions.
Do not include any explanation outside the JSON object.
"""
        
        return prompt

    def _invoke_claude(self, prompt: str) -> str:
        """
        Invoke Claude to analyze the question.
        
        Args:
            prompt: Analysis prompt
            
        Returns:
            Claude's response text
        """
        # Use Claude 3.5 Haiku for cost-effective analysis
        model_id = "anthropic.claude-3-5-haiku-20241022-v1:0"
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "temperature": 0.0,  # Deterministic for structured output
            "messages": [
                {
                    "role": "user",
                    "content": self._get_agent_instructions() + "\n\n" + prompt
                }
            ]
        }
        
        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
            
        except ClientError as e:
            raise Exception(f"Failed to invoke Claude: {e}")

    def _parse_decision(self, response: str) -> DataSourceDecision:
        """
        Parse Claude's response into a DataSourceDecision.
        
        Args:
            response: Claude's response text
            
        Returns:
            DataSourceDecision object
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            # Parse JSON
            data = json.loads(response)
            
            # Create decision object
            decision = DataSourceDecision(
                kpi_ids=data.get('kpi_ids', []),
                date_range=data.get('date_range', ''),
                frequency=data.get('frequency', 'monthly'),
                transactional_might_be_needed=data.get('transactional_might_be_needed', False),
                needs_clarification=data.get('needs_clarification', False),
                clarification_question=data.get('clarification_question'),
                reasoning=data.get('reasoning', ''),
                confidence=data.get('confidence', 0.5)
            )
            
            return decision
            
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            return DataSourceDecision(
                kpi_ids=[],
                date_range="",
                frequency="monthly",
                transactional_might_be_needed=True,
                needs_clarification=True,
                clarification_question="I had trouble understanding your question. Could you rephrase it?",
                reasoning=f"Failed to parse response: {str(e)}",
                confidence=0.0
            )

    def analyze_with_context(
        self,
        question: str,
        date_ranges: List[str] = None,
        customers: List[str] = None,
        kpis_mentioned: List[int] = None,
        filters: Dict[str, Any] = None,
        org_id: str = "default"
    ) -> DataSourceDecision:
        """
        Analyze question with explicit context parameters.
        
        Args:
            question: User's question
            date_ranges: Previously mentioned date ranges
            customers: Previously mentioned customers
            kpis_mentioned: Previously mentioned KPI IDs
            filters: Previously applied filters
            org_id: Organization ID
            
        Returns:
            DataSourceDecision
        """
        context = {
            'date_ranges': date_ranges or [],
            'customers': customers or [],
            'kpis_mentioned': kpis_mentioned or [],
            'filters': filters or {}
        }
        
        return self.determine_data_source(question, context, org_id)


# Convenience function for quick invocation
def analyze_data_source(
    question: str,
    context: Optional[Dict[str, Any]] = None,
    metadata_dir: str = "./metadata"
) -> DataSourceDecision:
    """
    Convenience function to analyze data source for a question.
    
    Args:
        question: User's question
        context: Conversation context
        metadata_dir: Directory containing metadata files
        
    Returns:
        DataSourceDecision
    """
    agent = DataSourceAgent(metadata_dir=metadata_dir)
    return agent.determine_data_source(question, context)
