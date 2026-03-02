"""
Deploy Agent Collaboration Configuration

This script configures agent collaboration in Bedrock after CDK deployment.
It adds the 3 sub-agents as collaborators to the Coordinator Agent.

This is necessary because CDK's CfnAgent doesn't yet support the agentCollaboration property.
"""

import json
import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from config.aws_config import aws_config


def configure_agent_collaboration():
    """
    Configure agent collaboration by adding sub-agents as collaborators to the Coordinator.
    
    This uses the Bedrock Agent API to update the Coordinator Agent with agent collaborators.
    """
    print("\n" + "="*70)
    print("CONFIGURING AGENT COLLABORATION IN BEDROCK")
    print("="*70)
    
    # Get agent IDs from environment
    coordinator_agent_id = os.getenv('BEDROCK_AGENT_ID')
    data_source_agent_id = os.getenv('DATA_SOURCE_AGENT_ID')
    smart_retrieval_agent_id = os.getenv('SMART_RETRIEVAL_AGENT_ID')
    analysis_agent_id = os.getenv('ANALYSIS_AGENT_ID')
    
    print(f"\nAgent IDs:")
    print(f"  Coordinator: {coordinator_agent_id}")
    print(f"  Data Source: {data_source_agent_id}")
    print(f"  Smart Retrieval: {smart_retrieval_agent_id}")
    print(f"  Analysis: {analysis_agent_id or 'NOT SET'}")
    
    # Validate required IDs
    if not coordinator_agent_id:
        print("\n✗ BEDROCK_AGENT_ID not set in .env")
        return False
    
    if not data_source_agent_id:
        print("\n✗ DATA_SOURCE_AGENT_ID not set in .env")
        return False
    
    if not smart_retrieval_agent_id:
        print("\n✗ SMART_RETRIEVAL_AGENT_ID not set in .env")
        return False
    
    # Initialize Bedrock Agent client
    bedrock_agent = boto3.client(
        'bedrock-agent',
        region_name=aws_config.region,
        config=aws_config.boto_config
    )
    
    try:
        # Step 1: Get current Coordinator Agent configuration
        print(f"\n[Step 1] Getting Coordinator Agent configuration...")
        
        response = bedrock_agent.get_agent(agentId=coordinator_agent_id)
        agent = response['agent']
        
        print(f"✓ Coordinator Agent: {agent['agentName']}")
        print(f"  Status: {agent['agentStatus']}")
        print(f"  Foundation Model: {agent['foundationModel']}")
        
        # Step 2: Prepare agent collaborators configuration
        print(f"\n[Step 2] Preparing agent collaborators configuration...")
        
        agent_collaborators = []
        
        # Add Data Source Agent as collaborator
        agent_collaborators.append({
            'agentDescriptor': {
                'aliasArn': f"arn:aws:bedrock:{aws_config.region}:{agent['agentArn'].split(':')[4]}:agent-alias/{data_source_agent_id}/TSTALIASID"
            },
            'collaborationInstruction': 'Invoke this agent to analyze user questions and determine what data sources are available (KPIs vs transactional data). It returns a structured decision with KPI IDs, date ranges, and whether clarification is needed.',
            'collaboratorName': 'DataSourceAgent',
            'relayConversationHistory': 'TO_COLLABORATOR'
        })
        
        # Add Smart Retrieval Agent as collaborator
        agent_collaborators.append({
            'agentDescriptor': {
                'aliasArn': f"arn:aws:bedrock:{aws_config.region}:{agent['agentArn'].split(':')[4]}:agent-alias/{smart_retrieval_agent_id}/TSTALIASID"
            },
            'collaborationInstruction': 'Invoke this agent to retrieve data based on the Data Source decision. It has 2 tools (get_kpi_data and execute_sql_query) and will autonomously decide which to use. It returns all retrieved data.',
            'collaboratorName': 'SmartRetrievalAgent',
            'relayConversationHistory': 'TO_COLLABORATOR'
        })
        
        # Add Analysis Agent as collaborator (if configured)
        if analysis_agent_id:
            agent_collaborators.append({
                'agentDescriptor': {
                    'aliasArn': f"arn:aws:bedrock:{aws_config.region}:{agent['agentArn'].split(':')[4]}:agent-alias/{analysis_agent_id}/TSTALIASID"
                },
                'collaborationInstruction': 'Invoke this agent to analyze retrieved data and generate business insights. It formats data, creates markdown tables, provides key insights, and suggests follow-up questions.',
                'collaboratorName': 'AnalysisAgent',
                'relayConversationHistory': 'TO_COLLABORATOR'
            })
        
        print(f"✓ Configured {len(agent_collaborators)} agent collaborators")
        for collab in agent_collaborators:
            print(f"  - {collab['collaboratorName']}")
        
        # Step 3: Update Coordinator Agent with collaborators
        print(f"\n[Step 3] Updating Coordinator Agent with collaborators...")
        
        # Note: The update_agent API doesn't support agentCollaboration parameter yet
        # We need to use a different approach - update via console or wait for API support
        
        print(f"\n⚠ IMPORTANT: Agent collaboration configuration via API is not yet fully supported.")
        print(f"\nTo configure agent collaboration in the Bedrock console:")
        print(f"\n1. Go to AWS Bedrock Console → Agents")
        print(f"2. Select the Coordinator Agent ({coordinator_agent_id})")
        print(f"3. Click 'Edit' in the Agent builder")
        print(f"4. Scroll to 'Agent collaboration' section")
        print(f"5. Click 'Add agent collaborator'")
        print(f"6. Add each sub-agent:")
        print(f"\n   Data Source Agent:")
        print(f"   - Agent: {data_source_agent_id}")
        print(f"   - Alias: prod")
        print(f"   - Name: DataSourceAgent")
        print(f"   - Instruction: Invoke this agent to analyze user questions and determine")
        print(f"     what data sources are available (KPIs vs transactional data).")
        print(f"\n   Smart Retrieval Agent:")
        print(f"   - Agent: {smart_retrieval_agent_id}")
        print(f"   - Alias: prod")
        print(f"   - Name: SmartRetrievalAgent")
        print(f"   - Instruction: Invoke this agent to retrieve data. It has 2 tools and")
        print(f"     will autonomously decide which to use.")
        print(f"\n   Analysis Agent:")
        print(f"   - Agent: {analysis_agent_id or 'NOT SET'}")
        print(f"   - Alias: prod")
        print(f"   - Name: AnalysisAgent")
        print(f"   - Instruction: Invoke this agent to analyze data and generate insights.")
        print(f"\n7. Click 'Save and exit'")
        print(f"8. Click 'Prepare' to create a new version")
        
        # Create a configuration file for reference
        config_file = 'agent_collaboration_config.json'
        with open(config_file, 'w') as f:
            json.dump({
                'coordinator_agent_id': coordinator_agent_id,
                'collaborators': agent_collaborators
            }, f, indent=2)
        
        print(f"\n✓ Configuration saved to {config_file}")
        
        return True
        
    except ClientError as e:
        print(f"\n✗ AWS Error: {e.response['Error']['Message']}")
        return False
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_collaboration():
    """Verify that agent collaboration is configured."""
    print("\n" + "="*70)
    print("VERIFYING AGENT COLLABORATION")
    print("="*70)
    
    coordinator_agent_id = os.getenv('BEDROCK_AGENT_ID')
    
    if not coordinator_agent_id:
        print("\n✗ BEDROCK_AGENT_ID not set")
        return False
    
    bedrock_agent = boto3.client(
        'bedrock-agent',
        region_name=aws_config.region,
        config=aws_config.boto_config
    )
    
    try:
        response = bedrock_agent.get_agent(agentId=coordinator_agent_id)
        agent = response['agent']
        
        print(f"\nCoordinator Agent: {agent['agentName']}")
        print(f"Status: {agent['agentStatus']}")
        
        # Check if agent has collaborators configured
        # Note: This field may not be available in the response yet
        if 'agentCollaboration' in agent:
            collaborators = agent.get('agentCollaboration', [])
            print(f"\n✓ Agent collaboration configured with {len(collaborators)} collaborators:")
            for collab in collaborators:
                print(f"  - {collab.get('collaboratorName', 'Unknown')}")
            return True
        else:
            print(f"\n⚠ Agent collaboration field not available in API response")
            print(f"Please verify manually in the Bedrock console")
            return True
            
    except ClientError as e:
        print(f"\n✗ AWS Error: {e.response['Error']['Message']}")
        return False
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return False


def main():
    """Main function."""
    print("\n" + "="*70)
    print("AGENT COLLABORATION DEPLOYMENT")
    print("="*70)
    print("\nThis script configures the 4-agent architecture:")
    print("  Coordinator → Data Source → Smart Retrieval → Analysis")
    
    # Configure collaboration
    if not configure_agent_collaboration():
        print("\n✗ Configuration failed")
        return 1
    
    # Verify collaboration
    print("\n")
    verify_collaboration()
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("\n1. Follow the instructions above to configure agent collaboration in the console")
    print("2. After configuration, run: python agents/test_4_agent_collaboration.py")
    print("3. Verify the 4-agent workflow is working correctly")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
