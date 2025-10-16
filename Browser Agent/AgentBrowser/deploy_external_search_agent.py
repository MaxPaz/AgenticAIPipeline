"""
Deployment script for External Search Agent
Creates the Bedrock Agent with action group connected to Lambda
"""

import boto3
import json
import time
import zipfile
import io
from pathlib import Path

# AWS clients
bedrock_agent = boto3.client('bedrock-agent', region_name='us-west-2')
lambda_client = boto3.client('lambda', region_name='us-west-2')
iam_client = boto3.client('iam')
sts_client = boto3.client('sts')

# Configuration
AGENT_NAME = "ExternalSearchAgent"
AGENT_DESCRIPTION = "Agent for searching external web sources using browser automation"
MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
LAMBDA_FUNCTION_NAME = "external-search-lambda"
ACTION_GROUP_NAME = "external_search_actions"

# Get account ID
ACCOUNT_ID = sts_client.get_caller_identity()['Account']
REGION = 'us-west-2'

# Browser Agent ARN (from previous deployment)
BROWSER_AGENT_ARN = os.getenv("BROWSER_AGENT_ARN", "arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:runtime/browser_agent-ID")


def create_lambda_execution_role():
    """Create IAM role for Lambda function"""
    role_name = f"{LAMBDA_FUNCTION_NAME}-role"
    
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for External Search Lambda"
        )
        role_arn = response['Role']['Arn']
        print(f"✓ Created Lambda execution role: {role_arn}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response['Role']['Arn']
        print(f"✓ Using existing Lambda execution role: {role_arn}")
    
    # Attach policies
    policies = [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    ]
    
    for policy_arn in policies:
        try:
            iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        except:
            pass
    
    # Add inline policy for invoking Browser Agent
    inline_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:InvokeAgentRuntime"
                ],
                "Resource": BROWSER_AGENT_ARN
            }
        ]
    }
    
    try:
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="BrowserAgentInvokePolicy",
            PolicyDocument=json.dumps(inline_policy)
        )
        print("✓ Attached Browser Agent invoke policy")
    except Exception as e:
        print(f"⚠ Warning: Could not attach inline policy: {e}")
    
    # Wait for role to be available
    time.sleep(10)
    
    return role_arn


def create_lambda_function(role_arn):
    """Create or update Lambda function"""
    
    # Read Lambda code
    lambda_code_path = Path(__file__).parent / "external_search_lambda.py"
    with open(lambda_code_path, 'r') as f:
        lambda_code = f.read()
    
    # Create deployment package
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('lambda_function.py', lambda_code)
    
    zip_buffer.seek(0)
    
    try:
        # Try to create new function
        response = lambda_client.create_function(
            FunctionName=LAMBDA_FUNCTION_NAME,
            Runtime='python3.11',
            Role=role_arn,
            Handler='lambda_function.lambda_handler',
            Code={'ZipFile': zip_buffer.read()},
            Description='Lambda function to invoke Browser Agent for external search',
            Timeout=300,
            MemorySize=512,
            Environment={
                'Variables': {
                    'BROWSER_AGENT_ARN': BROWSER_AGENT_ARN
                }
            }
        )
        lambda_arn = response['FunctionArn']
        print(f"✓ Created Lambda function: {lambda_arn}")
        
    except lambda_client.exceptions.ResourceConflictException:
        # Update existing function
        zip_buffer.seek(0)
        lambda_client.update_function_code(
            FunctionName=LAMBDA_FUNCTION_NAME,
            ZipFile=zip_buffer.read()
        )
        
        lambda_client.update_function_configuration(
            FunctionName=LAMBDA_FUNCTION_NAME,
            Runtime='python3.11',
            Role=role_arn,
            Handler='lambda_function.lambda_handler',
            Timeout=300,
            MemorySize=512,
            Environment={
                'Variables': {
                    'BROWSER_AGENT_ARN': BROWSER_AGENT_ARN
                }
            }
        )
        
        response = lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
        lambda_arn = response['Configuration']['FunctionArn']
        print(f"✓ Updated Lambda function: {lambda_arn}")
    
    # Wait for function to be ready
    time.sleep(5)
    
    return lambda_arn


def create_agent_role():
    """Create IAM role for Bedrock Agent"""
    role_name = f"{AGENT_NAME}-role"
    
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for External Search Agent"
        )
        role_arn = response['Role']['Arn']
        print(f"✓ Created agent role: {role_arn}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response['Role']['Arn']
        print(f"✓ Using existing agent role: {role_arn}")
    
    # Add inline policy for invoking model
    inline_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel"],
                "Resource": f"arn:aws:bedrock:{REGION}::foundation-model/{MODEL_ID}"
            }
        ]
    }
    
    try:
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="BedrockInvokeModelPolicy",
            PolicyDocument=json.dumps(inline_policy)
        )
        print("✓ Attached Bedrock invoke model policy")
    except Exception as e:
        print(f"⚠ Warning: Could not attach inline policy: {e}")
    
    # Wait for role to be available
    time.sleep(10)
    
    return role_arn


def create_or_update_agent(agent_role_arn):
    """Create or update Bedrock Agent"""
    
    # Read instructions
    instructions_path = Path(__file__).parent / "external_search_instructions.txt"
    with open(instructions_path, 'r') as f:
        instructions = f.read()
    
    try:
        # Try to create new agent
        response = bedrock_agent.create_agent(
            agentName=AGENT_NAME,
            agentResourceRoleArn=agent_role_arn,
            description=AGENT_DESCRIPTION,
            foundationModel=MODEL_ID,
            instruction=instructions,
            idleSessionTTLInSeconds=1800
        )
        agent_id = response['agent']['agentId']
        print(f"✓ Created agent: {agent_id}")
        
    except bedrock_agent.exceptions.ConflictException:
        # List agents to find existing one
        agents = bedrock_agent.list_agents()['agentSummaries']
        agent_id = next((a['agentId'] for a in agents if a['agentName'] == AGENT_NAME), None)
        
        if agent_id:
            # Update existing agent
            bedrock_agent.update_agent(
                agentId=agent_id,
                agentName=AGENT_NAME,
                agentResourceRoleArn=agent_role_arn,
                description=AGENT_DESCRIPTION,
                foundationModel=MODEL_ID,
                instruction=instructions,
                idleSessionTTLInSeconds=1800
            )
            print(f"✓ Updated agent: {agent_id}")
        else:
            raise Exception("Agent exists but could not be found")
    
    return agent_id


def add_lambda_permission(lambda_arn, agent_id):
    """Add permission for Bedrock Agent to invoke Lambda"""
    
    statement_id = f"bedrock-agent-{agent_id}"
    
    try:
        lambda_client.add_permission(
            FunctionName=LAMBDA_FUNCTION_NAME,
            StatementId=statement_id,
            Action='lambda:InvokeFunction',
            Principal='bedrock.amazonaws.com',
            SourceArn=f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:agent/{agent_id}"
        )
        print("✓ Added Lambda permission for Bedrock Agent")
    except lambda_client.exceptions.ResourceConflictException:
        print("✓ Lambda permission already exists")


def create_action_group(agent_id, lambda_arn):
    """Create action group for the agent"""
    
    # Read OpenAPI schema
    openapi_path = Path(__file__).parent / "external_search_openapi.json"
    with open(openapi_path, 'r') as f:
        api_schema = json.load(f)
    
    try:
        # Try to create new action group
        response = bedrock_agent.create_agent_action_group(
            agentId=agent_id,
            agentVersion='DRAFT',
            actionGroupName=ACTION_GROUP_NAME,
            description="Actions for external web search and data extraction",
            actionGroupExecutor={
                'lambda': lambda_arn
            },
            apiSchema={
                'payload': json.dumps(api_schema)
            }
        )
        action_group_id = response['agentActionGroup']['actionGroupId']
        print(f"✓ Created action group: {action_group_id}")
        
    except bedrock_agent.exceptions.ConflictException:
        # List action groups to find existing one
        action_groups = bedrock_agent.list_agent_action_groups(
            agentId=agent_id,
            agentVersion='DRAFT'
        )['actionGroupSummaries']
        
        action_group_id = next(
            (ag['actionGroupId'] for ag in action_groups if ag['actionGroupName'] == ACTION_GROUP_NAME),
            None
        )
        
        if action_group_id:
            # Update existing action group
            bedrock_agent.update_agent_action_group(
                agentId=agent_id,
                agentVersion='DRAFT',
                actionGroupId=action_group_id,
                actionGroupName=ACTION_GROUP_NAME,
                description="Actions for external web search and data extraction",
                actionGroupExecutor={
                    'lambda': lambda_arn
                },
                apiSchema={
                    'payload': json.dumps(api_schema)
                }
            )
            print(f"✓ Updated action group: {action_group_id}")
        else:
            raise Exception("Action group exists but could not be found")
    
    return action_group_id


def prepare_agent(agent_id):
    """Prepare agent (create version)"""
    
    response = bedrock_agent.prepare_agent(agentId=agent_id)
    print(f"✓ Prepared agent: {response['agentStatus']}")
    
    # Wait for preparation to complete
    max_attempts = 30
    for attempt in range(max_attempts):
        response = bedrock_agent.get_agent(agentId=agent_id)
        status = response['agent']['agentStatus']
        
        if status == 'PREPARED':
            print("✓ Agent preparation complete")
            break
        elif status == 'FAILED':
            raise Exception("Agent preparation failed")
        
        print(f"  Waiting for agent preparation... ({attempt + 1}/{max_attempts})")
        time.sleep(10)
    
    return agent_id


def create_agent_alias(agent_id):
    """Create or update agent alias"""
    
    alias_name = "live"
    
    try:
        response = bedrock_agent.create_agent_alias(
            agentId=agent_id,
            agentAliasName=alias_name,
            description="Live version of External Search Agent"
        )
        alias_id = response['agentAlias']['agentAliasId']
        print(f"✓ Created agent alias: {alias_id}")
        
    except bedrock_agent.exceptions.ConflictException:
        # List aliases to find existing one
        aliases = bedrock_agent.list_agent_aliases(agentId=agent_id)['agentAliasSummaries']
        alias_id = next((a['agentAliasId'] for a in aliases if a['agentAliasName'] == alias_name), None)
        
        if alias_id:
            # Update existing alias
            bedrock_agent.update_agent_alias(
                agentId=agent_id,
                agentAliasId=alias_id,
                agentAliasName=alias_name,
                description="Live version of External Search Agent"
            )
            print(f"✓ Updated agent alias: {alias_id}")
        else:
            raise Exception("Alias exists but could not be found")
    
    return alias_id


def main():
    """Main deployment function"""
    
    print("="*80)
    print("DEPLOYING EXTERNAL SEARCH AGENT")
    print("="*80)
    
    try:
        # Step 1: Create Lambda execution role
        print("\n1. Creating Lambda execution role...")
        lambda_role_arn = create_lambda_execution_role()
        
        # Step 2: Create Lambda function
        print("\n2. Creating Lambda function...")
        lambda_arn = create_lambda_function(lambda_role_arn)
        
        # Step 3: Create agent role
        print("\n3. Creating agent role...")
        agent_role_arn = create_agent_role()
        
        # Step 4: Create or update agent
        print("\n4. Creating/updating agent...")
        agent_id = create_or_update_agent(agent_role_arn)
        
        # Step 5: Add Lambda permission
        print("\n5. Adding Lambda permission...")
        add_lambda_permission(lambda_arn, agent_id)
        
        # Step 6: Create action group
        print("\n6. Creating action group...")
        action_group_id = create_action_group(agent_id, lambda_arn)
        
        # Step 7: Prepare agent
        print("\n7. Preparing agent...")
        prepare_agent(agent_id)
        
        # Step 8: Create alias
        print("\n8. Creating agent alias...")
        alias_id = create_agent_alias(agent_id)
        
        print("\n" + "="*80)
        print("✓ DEPLOYMENT COMPLETE!")
        print("="*80)
        print(f"\nAgent ID: {agent_id}")
        print(f"Agent Alias ID: {alias_id}")
        print(f"Lambda Function: {lambda_arn}")
        print(f"\nTest the agent with:")
        print(f"  python test_external_search_agent.py")
        print("="*80)
        
        return agent_id, alias_id
        
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        raise


if __name__ == "__main__":
    main()
