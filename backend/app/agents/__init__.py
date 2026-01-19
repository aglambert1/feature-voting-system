"""
AI Agents package.

This package contains the base agent framework and all specialized agents
for the competitor intelligence system.

V2 Architecture:
- ProductAnalyzerAgent: Analyzes our product features
- CompetitiveAgent: Discovers competitors and runs functional audits
- SynthesisAgent: Synthesizes opportunities across sources
- InternalDiscoveryAgent: Extracts themes from internal feedback
- IntensityIdeaGeneratorAgent: Generates ideas from feature clusters
"""

from app.agents.base_agent import BaseAgent, AgentExecutionError
from app.agents.test_agents import EchoAgent, StructuredOutputAgent
from app.agents.product_analyzer import ProductAnalyzerAgent
from app.agents.intensity_idea_generator import IntensityIdeaGeneratorAgent

__all__ = [
    "BaseAgent",
    "AgentExecutionError",
    "EchoAgent",
    "StructuredOutputAgent",
    "ProductAnalyzerAgent",
    "IntensityIdeaGeneratorAgent",
]
