"""
AI Agents package.

This package contains the base agent framework and all specialized agents
for the competitor intelligence system.
"""

from app.agents.base_agent import BaseAgent, AgentExecutionError
from app.agents.test_agents import EchoAgent, StructuredOutputAgent
from app.agents.product_analyzer import ProductAnalyzerAgent
from app.agents.intensity_idea_generator import IntensityIdeaGeneratorAgent
from app.agents.pricing_analyzer import PricingAnalyzerAgent
from app.agents.positioning_analyzer import PositioningAnalyzerAgent
from app.agents.changes_tracker import ChangesTrackerAgent
from app.agents.momentum_analyzer import MomentumAnalyzerAgent
from app.agents.financials_analyzer import FinancialsAnalyzerAgent

__all__ = [
    "BaseAgent",
    "AgentExecutionError",
    "EchoAgent",
    "StructuredOutputAgent",
    "ProductAnalyzerAgent",
    "IntensityIdeaGeneratorAgent",
    # Strategic Analysis Agents
    "PricingAnalyzerAgent",
    "PositioningAnalyzerAgent",
    "ChangesTrackerAgent",
    "MomentumAnalyzerAgent",
    "FinancialsAnalyzerAgent",
]
