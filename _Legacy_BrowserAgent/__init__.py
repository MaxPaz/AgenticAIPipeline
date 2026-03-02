"""
Browser Agent module for external web search and information extraction.

This module provides browser automation capabilities using AWS Bedrock AgentCore
and Nova Act for intelligent web browsing and data extraction.
"""

from browser_session_manager import BrowserSessionManager, ExternalSearchTool

__all__ = [
    "BrowserSessionManager",
    "ExternalSearchTool",
]

__version__ = "0.1.0"
