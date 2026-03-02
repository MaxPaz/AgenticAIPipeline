"""
Analysis Agent Package

This package contains the Analysis Agent implementation for interpreting
query results and generating business-aware insights.
"""

from .analysis_agent import AnalysisAgent, AnalysisResult, analyze_data

__all__ = ['AnalysisAgent', 'AnalysisResult', 'analyze_data']
