# Bedrock AgentCore Browser Session Manager

This module provides utilities for managing browser sessions using AWS Bedrock AgentCore and Nova Act for web browsing and information extraction.

## Overview

The Browser Session Manager enables:
- Automated web browsing using AWS Bedrock AgentCore
- Information extraction from websites using Nova Act
- Company information search and data gathering
- Structured web data extraction

## Components

### 1. BrowserSessionManager

Main class for managing browser sessions with Bedrock AgentCore and Nova Act.

**Features:**
- Context manager for safe browser session lifecycle
- Automatic cleanup of browser resources
- Integration with Nova Act for intelligent web interactions
- Configurable starting pages and browser settings

**Usage:**
```python
from tools.browser_session_manager import BrowserSessionManager

# Initialize manager
manager = BrowserSessionManager(
    region="us-west-2",
    nova_act_api_key="your-api-key"
)

# Use context manager for browser session
with manager.create_browser_session() as nova_act:
    result = nova_act.act("Search for AWS Bedrock documentation")
    print(result)
```

### 2. ExternalSearchTool

High-level tool for searching external information using browser automation.

**Features:**
- Company information search (news, financial, general)
- Web data extraction from specific URLs
- Structured result formatting
- Error handling and logging

**Usage:**
```python
from tools.browser_session_manager import ExternalSearchTool

# Initialize search tool
search_tool = ExternalSearchTool(
    region="us-west-2",
    nova_act_api_key="your-api-key"
)

# Search for company information
result = search_tool.search_company_info(
    company_name="Amazon",
    search_type="news"
)

if result["success"]:
    print(f"Found information: {result['content']}")
```

## Installation

### 1. Install Dependencies

```bash
pip install bedrock-agentcore nova-act
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

### 2. Configure Nova Act API Key

Add your Nova Act API key to `.env` file:
```bash
NOVA_ACT_API_KEY=your_nova_act_api_key_here
```

Or set it as an environment variable:
```bash
export NOVA_ACT_API_KEY=your_nova_act_api_key_here
```

### 3. Configure AWS Region (Optional)

Default region is `us-west-2`. To use a different region:
```bash
AWS_REGION=us-east-1
```

## Testing

Run the test suite to verify installation and configuration:

```bash
python tools/test_browser_session.py
```

The test suite includes:
1. **Browser Session Manager Test**: Verifies basic browser session creation
2. **External Search Tool Test**: Tests company information search
3. **Context Manager Test**: Tests direct usage of browser session context manager

### Expected Output

```
================================================================================
BEDROCK AGENTCORE BROWSER SESSION MANAGER - TEST SUITE
================================================================================

📋 Environment Configuration:
  AWS_REGION: us-west-2
  NOVA_ACT_API_KEY: Set

================================================================================
TEST 1: Browser Session Manager - Basic Session Creation
================================================================================

✓ BrowserSessionManager initialized
  Region: us-west-2
  Nova Act API Key: Set

📋 Running browser session test...

✅ Browser session test PASSED
  Message: Browser session created successfully
  Region: us-west-2

================================================================================
TEST SUMMARY
================================================================================
  Browser Session Manager: ✅ PASSED
  External Search Tool: ✅ PASSED
  Context Manager: ✅ PASSED

Total: 3/3 tests passed

🎉 All tests passed!
```

## API Reference

### BrowserSessionManager

#### `__init__(region: str = "us-west-2", nova_act_api_key: Optional[str] = None)`

Initialize the Browser Session Manager.

**Parameters:**
- `region`: AWS region for Bedrock services (default: "us-west-2")
- `nova_act_api_key`: API key for Nova Act (if None, reads from NOVA_ACT_API_KEY env var)

#### `create_browser_session(starting_page: str = "https://www.google.com", playwright_actuation: bool = True)`

Create a browser session using Bedrock AgentCore and Nova Act.

**Parameters:**
- `starting_page`: Initial URL to load (default: Google homepage)
- `playwright_actuation`: Enable Playwright actuation for Nova Act (default: True)

**Returns:**
- Context manager yielding NovaAct instance

#### `test_browser_session() -> Dict[str, Any]`

Test browser session creation and basic functionality.

**Returns:**
- Dict with test results including success status and any error messages

### ExternalSearchTool

#### `__init__(region: str = "us-west-2", nova_act_api_key: Optional[str] = None)`

Initialize the External Search Tool.

**Parameters:**
- `region`: AWS region for Bedrock services
- `nova_act_api_key`: API key for Nova Act

#### `search_company_info(company_name: str, search_type: str = "news") -> Dict[str, Any]`

Search for external company information using Nova Act browser automation.

**Parameters:**
- `company_name`: Name of the company to search for
- `search_type`: Type of search ("news", "general", "financial")

**Returns:**
- Dict containing search results with company information

#### `extract_web_data(url: str, extraction_instructions: str) -> Dict[str, Any]`

Navigate to a URL and extract specific information.

**Parameters:**
- `url`: URL to navigate to
- `extraction_instructions`: Instructions for what data to extract

**Returns:**
- Dict containing extracted data

## Integration with Bedrock Agents

The Browser Session Manager can be integrated with Bedrock Agents as an action group:

```python
# In your Bedrock Agent action group
def search_external_info(company_name: str, search_type: str = "news"):
    """
    Action group function for external search.
    This can be called by the Coordinator Agent when external information is needed.
    """
    search_tool = ExternalSearchTool()
    result = search_tool.search_company_info(company_name, search_type)
    return result
```

## Troubleshooting

### ImportError: No module named 'bedrock_agentcore'

Install the required dependencies:
```bash
pip install bedrock-agentcore nova-act
```

### Warning: Nova Act API key not provided

Set the NOVA_ACT_API_KEY environment variable:
```bash
export NOVA_ACT_API_KEY=your_api_key_here
```

Or add it to your `.env` file.

### Browser session test failed

Check:
1. AWS credentials are configured (`aws configure`)
2. AWS region is correct
3. Nova Act API key is valid
4. Network connectivity to AWS services

## Requirements

- Python 3.8+
- boto3 >= 1.34.0
- bedrock-agentcore >= 0.1.0
- nova-act >= 0.1.0
- python-dotenv >= 1.0.0

## Related Documentation

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/)
- [Nova Act Documentation](https://nova-act.readthedocs.io/)
- [Design Document](.kiro/specs/agentic-chat-pipeline/design.md)
- [Requirements Document](.kiro/specs/agentic-chat-pipeline/requirements.md)
