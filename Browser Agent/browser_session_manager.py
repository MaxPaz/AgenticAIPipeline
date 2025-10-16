"""
Browser Session Manager for Bedrock AgentCore Browser with Nova Act.

This module provides utilities for managing browser sessions using AWS Bedrock AgentCore
and Nova Act for web browsing and information extraction.
"""

import os
import sys
from typing import Optional, Dict, Any
from contextlib import contextmanager
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

logger.info("="*80)
logger.info("BROWSER SESSION MANAGER MODULE INITIALIZING")
logger.info("="*80)


class BrowserSessionManager:
    """
    Manages browser sessions for Bedrock AgentCore Browser with Nova Act integration.
    
    This class handles the creation and management of browser sessions that can be used
    for web browsing, information extraction, and automated web interactions.
    """
    
    def __init__(
        self,
        region: str = "us-west-2",
        nova_act_api_key: Optional[str] = None
    ):
        """
        Initialize the Browser Session Manager.
        
        Args:
            region: AWS region for Bedrock services (default: us-west-2)
            nova_act_api_key: API key for Nova Act (if None, reads from NOVA_ACT_API_KEY env var)
        """
        self.region = region
        self.nova_act_api_key = nova_act_api_key or os.getenv("NOVA_ACT_API_KEY")
        
        if not self.nova_act_api_key:
            logger.warning(
                "Nova Act API key not provided. Set NOVA_ACT_API_KEY environment variable "
                "or pass nova_act_api_key parameter."
            )
    
    @contextmanager
    def create_browser_session(
        self,
        starting_page: str = "https://duckduckgo.com",
        playwright_actuation: bool = True
    ):
        """
        Create a browser session using Bedrock AgentCore and Nova Act.
        
        This is a context manager that handles the lifecycle of a browser session,
        ensuring proper cleanup when the session is complete.
        
        Args:
            starting_page: Initial URL to load (default: DuckDuckGo homepage)
            playwright_actuation: Enable Playwright actuation for Nova Act (default: True)
            
        Yields:
            NovaAct instance configured with the browser session
            
        Example:
            >>> manager = BrowserSessionManager()
            >>> with manager.create_browser_session() as nova_act:
            ...     result = nova_act.act("Search for AWS Bedrock documentation")
            ...     print(result)
        """
        try:
            # Import here to avoid import errors if packages not installed
            from bedrock_agentcore.tools.browser_client import browser_session
            from nova_act import NovaAct
            
            logger.info(f"Creating browser session in region {self.region}")
            
            # Create browser session using Bedrock AgentCore
            with browser_session(self.region) as client:
                ws_url, headers = client.generate_ws_headers()
                
                logger.info("Browser session created, initializing Nova Act")
                
                # Initialize Nova Act with the browser session
                with NovaAct(
                    cdp_endpoint_url=ws_url,
                    cdp_headers=headers,
                    preview={"playwright_actuation": playwright_actuation},
                    nova_act_api_key=self.nova_act_api_key,
                    starting_page=starting_page
                ) as nova_act:
                    logger.info("Nova Act initialized successfully")
                    yield nova_act
                    
        except ImportError as e:
            logger.error(f"Failed to import required libraries: {e}")
            raise ImportError(
                "Required libraries not installed. "
                "Install with: pip install bedrock-agentcore nova-act"
            ) from e
        except Exception as e:
            logger.error(f"Error creating browser session: {e}")
            raise
    
    def test_browser_session(self) -> Dict[str, Any]:
        """
        Test browser session creation and basic functionality.
        
        Returns:
            Dict with test results including success status and any error messages
        """
        try:
            with self.create_browser_session() as nova_act:
                # Perform a simple test action
                result = nova_act.act("Get the page title")
                
                return {
                    "success": True,
                    "message": "Browser session created successfully",
                    "test_result": result,
                    "region": self.region
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Browser session test failed: {str(e)}",
                "error": str(e),
                "region": self.region
            }


class ExternalSearchTool:
    """
    Tool for searching external information using Bedrock AgentCore Browser with Nova Act.
    
    This class provides methods for searching company information, news, and other
    external data sources using automated web browsing.
    """
    
    def __init__(
        self,
        region: str = "us-west-2",
        nova_act_api_key: Optional[str] = None
    ):
        """
        Initialize the External Search Tool.
        
        Args:
            region: AWS region for Bedrock services
            nova_act_api_key: API key for Nova Act
        """
        self.session_manager = BrowserSessionManager(region, nova_act_api_key)
    
    def search_company_info(
        self,
        company_name: str,
        search_type: str = "news"
    ) -> Dict[str, Any]:
        """
        Search for external company information using Nova Act browser automation.
        
        Args:
            company_name: Name of the company to search for
            search_type: Type of search ("news", "general", "financial")
            
        Returns:
            Dict containing search results with company information
        """
        try:
            with self.session_manager.create_browser_session() as nova_act:
                # Construct search query based on type
                if search_type == "news":
                    query = f"Search for recent news about {company_name} and extract key information"
                elif search_type == "financial":
                    query = f"Search for financial information about {company_name} and extract key metrics"
                else:
                    query = f"Search for information about {company_name} and extract key details"
                
                logger.info(f"Executing search: {query}")
                result = nova_act.act(query)
                
                return {
                    "success": True,
                    "company_name": company_name,
                    "search_type": search_type,
                    "content": result,
                    "source": "Web search via Nova Act"
                }
        except Exception as e:
            logger.error(f"Error searching for company info: {e}")
            return {
                "success": False,
                "company_name": company_name,
                "search_type": search_type,
                "error": str(e),
                "source": "Web search via Nova Act"
            }
    
    def extract_web_data(
        self,
        url: str,
        extraction_instructions: str
    ) -> Dict[str, Any]:
        """
        Navigate to a URL and extract specific information.
        
        Args:
            url: URL to navigate to
            extraction_instructions: Instructions for what data to extract
            
        Returns:
            Dict containing extracted data
        """
        try:
            with self.session_manager.create_browser_session(starting_page=url) as nova_act:
                logger.info(f"Navigating to {url}")
                result = nova_act.act(extraction_instructions)
                
                return {
                    "success": True,
                    "url": url,
                    "content": result,
                    "source": f"Extracted from {url}"
                }
        except Exception as e:
            logger.error(f"Error extracting web data: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }
