"""
Smart Retrieval Agent Package

This package implements the Smart Retrieval Agent - a Bedrock sub-agent that
autonomously retrieves data from KPIs and/or transactional databases.
"""

from .smart_retrieval_agent import SmartRetrievalAgent, RetrievalResult

__all__ = ['SmartRetrievalAgent', 'RetrievalResult']
