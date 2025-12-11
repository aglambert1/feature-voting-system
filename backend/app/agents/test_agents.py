"""
Test agents for validating the agent framework.

These agents are used for testing and demonstrating the agent pattern.
They should not be used in production.
"""

from typing import Dict, Any, Type, List
from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent


class EchoAgentOutput(BaseModel):
    """Output schema for EchoAgent."""
    message: str = Field(..., description="The echoed message")
    input_received: Dict[str, Any] = Field(..., description="Copy of input")
    agent_name: str = Field(..., description="Name of this agent")


class EchoAgent(BaseAgent):
    """
    Simple test agent that echoes input back.

    Used for testing the agent framework. Returns the input in a structured
    format to verify that the agent execution pipeline works correctly.

    Example:
        agent = EchoAgent(db=db, llm_service=llm_service)
        result = agent.execute({"test": "data"})
        # result = {"message": "Echo successful", "input_received": {...}, ...}
    """

    def get_system_prompt(self) -> str:
        """Define EchoAgent behavior."""
        return """You are a test agent called EchoAgent.
Your job is to return the input you receive in a structured format.
Always respond with valid JSON matching the specified schema.
Do not include any markdown formatting or code blocks - just the raw JSON."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build prompt with input data."""
        return f"""Please echo back the following input in JSON format:

Input: {input_data}

Return a JSON object with these exact keys:
- message: "Echo successful"
- input_received: (exact copy of the input above)
- agent_name: "EchoAgent"

Example format:
{{"message": "Echo successful", "input_received": {{"test": "data"}}, "agent_name": "EchoAgent"}}"""

    def get_output_schema(self) -> Type[BaseModel]:
        """Return the output schema."""
        return EchoAgentOutput

    def get_stage(self) -> str:
        """Return the stage name."""
        return "testing"


class StructuredOutputAgentOutput(BaseModel):
    """Output schema for StructuredOutputAgent."""
    summary: str = Field(..., description="Brief summary of the text")
    key_points: List[str] = Field(..., description="List of 3-5 key points")
    sentiment: str = Field(..., description="Sentiment: positive, negative, or neutral")


class StructuredOutputAgent(BaseAgent):
    """
    Test agent that generates structured output from text.

    Demonstrates a typical agent pattern where unstructured input (text)
    is converted into structured output (summary, key points, sentiment).

    Example:
        agent = StructuredOutputAgent(db=db, llm_service=llm_service)
        result = agent.execute({"text": "This is a great product..."})
        # result = {"summary": "...", "key_points": [...], "sentiment": "positive"}
    """

    def get_system_prompt(self) -> str:
        """Define StructuredOutputAgent behavior."""
        return """You are a text analysis agent.
You extract key information from text and return it in structured format.
Always respond with valid JSON.
Do not include any markdown formatting or code blocks - just the raw JSON."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build prompt with text to analyze."""
        text = input_data.get("text", "")
        return f"""Analyze the following text and extract key information:

Text: {text}

Return a JSON object with:
- summary: A brief summary (1-2 sentences)
- key_points: List of 3-5 key points (as an array of strings)
- sentiment: Either "positive", "negative", or "neutral"

Example format:
{{"summary": "This text discusses...", "key_points": ["Point 1", "Point 2", "Point 3"], "sentiment": "positive"}}"""

    def get_output_schema(self) -> Type[BaseModel]:
        """Return the output schema."""
        return StructuredOutputAgentOutput

    def get_stage(self) -> str:
        """Return the stage name."""
        return "testing"
