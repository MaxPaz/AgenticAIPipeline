"""
Smart Retrieval Agent

This module implements the Smart Retrieval Agent as a Bedrock sub-agent that
autonomously retrieves data from KPIs and/or transactional databases.

The Smart Retrieval Agent:
- Receives DataSourceDecision from Data Source Agent
- Has 2 action groups (tools):
  1. get_kpi_data - Retrieves pre-calculated KPI data from XBR
  2. execute_sql_query - Executes SQL against transactional database
- Autonomously decides which tools to call
- Validates data sufficiency
- Adapts and retrieves more data if needed
"""

import json
import os
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from config.aws_config import aws_config
from tools.metadata_loader import MetadataLoader


@dataclass
class RetrievalResult:
    """
    Result from Smart Retrieval Agent containing all retrieved data.
    """
    kpi_data: Optional[List[Dict[str, Any]]]  # KPI data if retrieved
    transactional_data: Optional[List[Dict[str, Any]]]  # Transactional data if retrieved
    data_sources_used: List[str]  # ["KPI", "Transactional", "Both"]
    notes: str  # Explanation of what was retrieved and why
    sql_query: Optional[str]  # SQL query if used
    success: bool  # Whether retrieval was successful
    error_message: Optional[str]  # Error message if failed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


class SmartRetrievalAgent:
    """
    Smart Retrieval Agent that autonomously retrieves data.
    
    This Bedrock sub-agent:
    - Receives DataSourceDecision from Data Source Agent
    - Decides which tools to call (KPI, SQL, or both)
    - Validates data sufficiency
    - Adapts strategy if data is insufficient
    - Returns all collected data
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        agent_alias_id: Optional[str] = None,
        region: Optional[str] = None,
        metadata_dir: str = "./metadata"
    ):
        """
        Initialize the Smart Retrieval Agent.
        
        Args:
            agent_id: Bedrock Agent ID
            agent_alias_id: Bedrock Agent Alias ID
            region: AWS region
            metadata_dir: Directory containing metadata files
        """
        self.agent_id = agent_id or os.getenv('SMART_RETRIEVAL_AGENT_ID')
        self.agent_alias_id = agent_alias_id or os.getenv('SMART_RETRIEVAL_AGENT_ALIAS_ID')
        self.region = region or aws_config.region
        
        # Initialize Bedrock clients
        self.bedrock_agent_runtime = aws_config.get_bedrock_agent_runtime_client()
        
        # Initialize metadata loader
        self.metadata_loader = MetadataLoader(metadata_dir)

    def retrieve_data(
        self,
        data_source_decision: Dict[str, Any],
        question: str,
        org_id: str = "default"
    ) -> RetrievalResult:
        """
        Retrieve data based on DataSourceDecision.
        
        This method invokes the Smart Retrieval Agent which will autonomously
        decide which tools to call.
        
        Args:
            data_source_decision: Decision from Data Source Agent
            question: Original user question
            org_id: Organization ID
            
        Returns:
            RetrievalResult with all retrieved data
        """
        if not self.agent_id or not self.agent_alias_id:
            return RetrievalResult(
                kpi_data=None,
                transactional_data=None,
                data_sources_used=[],
                notes="Agent not configured",
                sql_query=None,
                success=False,
                error_message="SMART_RETRIEVAL_AGENT_ID or SMART_RETRIEVAL_AGENT_ALIAS_ID not set"
            )
        
        # Prepare input for agent
        input_data = {
            "question": question,
            "data_source_decision": data_source_decision,
            "org_id": org_id
        }
        
        try:
            # Invoke Smart Retrieval Agent
            import uuid
            session_id = str(uuid.uuid4())
            
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=json.dumps(input_data)
            )
            
            # Collect response and trace data
            completion = ""
            traces = []
            action_group_results = []
            
            for event in response.get('completion', []):
                if 'chunk' in event and 'bytes' in event['chunk']:
                    completion += event['chunk']['bytes'].decode('utf-8')
                
                # Collect trace data to extract action group results
                if 'trace' in event:
                    trace = event['trace']
                    traces.append(trace)
                    
                    # Extract action group invocations from trace
                    if 'trace' in trace:
                        trace_data = trace['trace']
                        if 'orchestrationTrace' in trace_data:
                            orch_trace = trace_data['orchestrationTrace']
                            if 'observation' in orch_trace:
                                observation = orch_trace['observation']
                                if 'actionGroupInvocationOutput' in observation:
                                    ag_output = observation['actionGroupInvocationOutput']
                                    action_group_results.append(ag_output)
            
            # Try to extract data from action group results first
            kpi_data = None
            transactional_data = None
            data_sources_used = []
            sql_query = None
            notes = []
            
            for ag_result in action_group_results:
                if 'text' in ag_result:
                    try:
                        ag_data = json.loads(ag_result['text'])
                        
                        # Check if this is KPI data
                        if 'kpi_data' in ag_data:
                            kpi_data = ag_data['kpi_data']
                            data_sources_used.append('KPI')
                            notes.append(f"Retrieved {len(kpi_data)} KPI records")
                        
                        # Check if this is SQL execution result
                        if 'data' in ag_data and ag_data.get('success'):
                            transactional_data = ag_data['data']
                            data_sources_used.append('Transactional')
                            notes.append(f"Retrieved {len(transactional_data)} transactional records")
                            if 'sql_query' in ag_data:
                                sql_query = ag_data['sql_query']
                    except json.JSONDecodeError:
                        pass
            
            # If we got data from action groups, return it
            if kpi_data or transactional_data:
                return RetrievalResult(
                    kpi_data=kpi_data,
                    transactional_data=transactional_data,
                    data_sources_used=list(set(data_sources_used)),
                    notes="; ".join(notes),
                    sql_query=sql_query,
                    success=True,
                    error_message=None
                )
            
            # Otherwise try to parse JSON from completion
            import re
            json_match = re.search(r'\{.*\}', completion, re.DOTALL)
            if json_match:
                try:
                    result_data = json.loads(json_match.group())
                    return RetrievalResult(
                        kpi_data=result_data.get('kpi_data'),
                        transactional_data=result_data.get('transactional_data'),
                        data_sources_used=result_data.get('data_sources_used', []),
                        notes=result_data.get('notes', ''),
                        sql_query=result_data.get('sql_query'),
                        success=True,
                        error_message=None
                    )
                except json.JSONDecodeError:
                    pass
            
            # If no structured data found, return the completion as notes
            return RetrievalResult(
                kpi_data=None,
                transactional_data=None,
                data_sources_used=[],
                notes=completion if completion else "Agent completed but returned no structured data",
                sql_query=None,
                success=False,
                error_message="Could not extract structured data from agent response"
            )
                
        except Exception as e:
            return RetrievalResult(
                kpi_data=None,
                transactional_data=None,
                data_sources_used=[],
                notes="",
                sql_query=None,
                success=False,
                error_message=str(e)
            )


# Convenience function
def retrieve_data(
    data_source_decision: Dict[str, Any],
    question: str,
    org_id: str = "default"
) -> RetrievalResult:
    """
    Convenience function to retrieve data.
    
    Args:
        data_source_decision: Decision from Data Source Agent
        question: Original user question
        org_id: Organization ID
        
    Returns:
        RetrievalResult
    """
    agent = SmartRetrievalAgent()
    return agent.retrieve_data(data_source_decision, question, org_id)
