"""
LLM Service for Claude API integration.

This service handles all interactions with the Anthropic Claude API,
including structuring freeform text into what/why/use_case format
and providing agent execution capabilities.
"""

import time
import json
from typing import Dict, Any, Optional
from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError

from app.config import settings


class LLMService:
    """
    Service for interacting with Claude API.

    Handles text structuring and error handling.
    """

    def __init__(self):
        """Initialize the Anthropic client."""
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        # Use Claude 3 Haiku (fast and cost-effective for structuring tasks)
        self.model = "claude-3-haiku-20240307"

    def structure_idea(self, freeform_text: str) -> Dict[str, any]:
        """
        Structure freeform text into a structured idea format.

        Takes natural language input and returns structured data with:
        - title: Short, descriptive title
        - what_description: What the feature is
        - why_description: Why it's valuable
        - use_case_description: How it would be used

        Args:
            freeform_text: User's freeform idea description

        Returns:
            Dictionary with structured idea and processing time

        Raises:
            APIError: If Claude API returns an error
            APITimeoutError: If request times out
            ValueError: If response cannot be parsed
        """
        start_time = time.time()

        # Construct the prompt for Claude
        prompt = f"""You are a product manager helping structure feature ideas.

A user has submitted the following idea in their own words:

<user_idea>
{freeform_text}
</user_idea>

Please structure this idea into a clear, professional format with four components:

1. **Title**: A concise, descriptive title (5-8 words max)
2. **What**: A clear description of what the feature is (2-3 sentences)
3. **Why**: Explanation of why this feature would be valuable (2-3 sentences)
4. **Use Case**: A concrete example of how someone would use this feature (2-3 sentences)

Return ONLY a JSON object with these exact keys: title, what, why, use_case
Do not include any markdown formatting, code blocks, or additional text - just the raw JSON.

Example format:
{{"title": "Dark Mode Toggle", "what": "A toggle switch in settings that...", "why": "This would improve...", "use_case": "A user working late at night..."}}"""

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract the response text
            response_text = message.content[0].text.strip()

            # Parse JSON response
            try:
                structured_data = json.loads(response_text)
            except json.JSONDecodeError:
                # If Claude wrapped response in markdown code blocks, clean it
                if response_text.startswith("```"):
                    # Remove code block markers
                    response_text = response_text.strip("`").strip()
                    if response_text.startswith("json"):
                        response_text = response_text[4:].strip()
                    structured_data = json.loads(response_text)
                else:
                    raise ValueError(f"Could not parse Claude response as JSON: {response_text}")

            # Validate required fields
            required_fields = ["title", "what", "why", "use_case"]
            missing_fields = [field for field in required_fields if field not in structured_data]
            if missing_fields:
                raise ValueError(f"Missing required fields in response: {missing_fields}")

            # Calculate processing time
            processing_time = time.time() - start_time

            # Return structured data with metadata
            return {
                "title": structured_data["title"],
                "what_description": structured_data["what"],
                "why_description": structured_data["why"],
                "use_case_description": structured_data["use_case"],
                "processing_time": round(processing_time, 2)
            }

        except APITimeoutError as e:
            print(f"Claude API timeout: {e}")
            raise Exception("AI processing timed out. Please try again.")

        except APIError as e:
            print(f"Claude API error: {e}")
            raise Exception(f"AI processing failed: {str(e)}")

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Response was: {response_text}")
            raise ValueError("AI returned invalid format. Please try again.")

        except Exception as e:
            print(f"Unexpected error in structure_idea: {e}")
            raise Exception(f"Unexpected error during AI processing: {str(e)}")

    def call_agent(
        self,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call Claude API for agent execution.

        This method is designed for AI agent use cases where system prompts
        define agent behavior and user prompts contain task details.

        Args:
            agent_name: Name of the calling agent (for logging/debugging)
            system_prompt: System message defining agent behavior
            user_prompt: User message with task details
            temperature: Sampling temperature (0.0-1.0), defaults to config value
            max_tokens: Maximum tokens in response, defaults to config value
            model: Model to use, defaults to config value

        Returns:
            Dict with:
                - content: The text response from Claude
                - tokens_used: Total tokens (input + output)
                - model: The model used
                - stop_reason: Why generation stopped

        Raises:
            LLMServiceError: If API call fails
        """
        # Use config defaults if not specified
        temperature = temperature if temperature is not None else settings.temperature_default
        max_tokens = max_tokens if max_tokens is not None else settings.max_tokens_default
        model = model or settings.claude_model

        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )

            # Extract text content
            content = ""
            for block in message.content:
                if block.type == "text":
                    content += block.text

            # Calculate tokens used
            tokens_used = message.usage.input_tokens + message.usage.output_tokens

            return {
                "content": content,
                "tokens_used": tokens_used,
                "model": message.model,
                "stop_reason": message.stop_reason
            }

        except RateLimitError:
            # Re-raise RateLimitError so call_with_retry can handle it
            raise
        except APIError as e:
            print(f"Claude API error in agent {agent_name}: {e}")
            raise LLMServiceError(f"Claude API error: {str(e)}")
        except Exception as e:
            print(f"Unexpected error calling Claude for agent {agent_name}: {e}")
            raise LLMServiceError(f"Unexpected error calling Claude: {str(e)}")

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses rough approximation: 1 token ≈ 4 characters.
        This is a quick estimation method - actual token counts may vary.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        return len(text) // 4

    def call_with_retry(
        self,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call Claude with automatic retry on rate limits.

        Uses exponential backoff: waits 1s, 2s, 4s, etc. between retries.

        Args:
            agent_name: Name of the calling agent
            system_prompt: System message
            user_prompt: User message
            max_retries: Maximum number of retry attempts
            **kwargs: Additional arguments passed to call_agent()

        Returns:
            Same as call_agent()

        Raises:
            LLMServiceError: If all retries fail
        """
        for attempt in range(max_retries):
            try:
                return self.call_agent(
                    agent_name=agent_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    **kwargs
                )
            except RateLimitError:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                    print(f"Rate limit hit for {agent_name}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Rate limit hit for {agent_name}, all retries exhausted")
                    raise LLMServiceError("Rate limit exceeded after all retries")


class LLMServiceError(Exception):
    """Raised when LLM service encounters an error."""
    pass


# Create a singleton instance for reuse
llm_service = LLMService()
