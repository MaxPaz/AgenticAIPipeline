"""
AWS Configuration Module

This module handles AWS service configuration including Bedrock, Lambda, and other AWS services.
"""

import os
from typing import Optional
import boto3
from botocore.config import Config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class AWSConfig:
    """AWS Configuration class for managing AWS service clients."""
    
    def __init__(self):
        # AWS credentials will be picked up from:
        # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        # 2. AWS CLI configuration (~/.aws/credentials)
        # 3. IAM role (if running on EC2/ECS)
        self.region = os.getenv('AWS_REGION', 'us-west-2')
        
        # Bedrock configuration (optional at this stage)
        self.bedrock_agent_id = os.getenv('BEDROCK_AGENT_ID')
        self.bedrock_agent_alias_id = os.getenv('BEDROCK_AGENT_ALIAS_ID')
        
        # Lambda configuration (optional at this stage)
        self.sql_executor_lambda_arn = os.getenv('SQL_EXECUTOR_LAMBDA_ARN')
        
        # Configure boto3 with retry logic
        self.boto_config = Config(
            region_name=self.region,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            }
        )
    
    def get_bedrock_agent_runtime_client(self):
        """Get Bedrock Agent Runtime client."""
        return boto3.client(
            'bedrock-agent-runtime',
            region_name=self.region,
            config=self.boto_config
        )
    
    def get_bedrock_runtime_client(self):
        """Get Bedrock Runtime client for direct model invocation."""
        return boto3.client(
            'bedrock-runtime',
            region_name=self.region,
            config=self.boto_config
        )
    
    def get_lambda_client(self):
        """Get Lambda client for SQL execution."""
        return boto3.client(
            'lambda',
            region_name=self.region,
            config=self.boto_config
        )
    
    def get_dynamodb_client(self):
        """Get DynamoDB client for memory storage."""
        return boto3.client(
            'dynamodb',
            region_name=self.region,
            config=self.boto_config
        )
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """
        Validate that required configuration is present.
        
        Returns:
            Tuple of (is_valid, list_of_missing_configs)
        """
        missing = []
        warnings = []
        
        # Check if AWS credentials are available (via CLI or env vars)
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials is None:
                missing.append('AWS Credentials (configure via aws configure or environment variables)')
        except Exception:
            missing.append('AWS Credentials')
        
        # These are optional at initial setup stage
        if not self.bedrock_agent_id:
            warnings.append('BEDROCK_AGENT_ID (optional for now)')
        if not self.bedrock_agent_alias_id:
            warnings.append('BEDROCK_AGENT_ALIAS_ID (optional for now)')
        
        return len(missing) == 0, missing, warnings


# Global config instance
aws_config = AWSConfig()
