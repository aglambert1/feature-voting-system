"""
LLM Service for Claude API integration.

This service handles all interactions with the Anthropic Claude API,
including structuring freeform text into what/why/use_case format
and providing agent execution capabilities.
"""

import time
import json
from typing import Dict, Any, Optional, List, Callable
from contextvars import ContextVar
from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError

from app.config import settings
from app.models.cost_tracking import OperationType


# Context variable for tracking LLM call metadata
# Set before making LLM calls to associate costs with users/products/jobs
llm_context: ContextVar[dict] = ContextVar("llm_context", default={})


def set_llm_context(
    operation_type: OperationType,
    user_id: Optional[int] = None,
    product_id: Optional[int] = None,
    job_id: Optional[str] = None,
    db=None,
) -> None:
    """
    Set context for LLM cost tracking.

    Call this before making LLM calls to associate the cost with
    a specific user, product, and operation type.

    Args:
        operation_type: The type of LLM operation being performed
        user_id: Optional user ID who triggered the call
        product_id: Optional product ID for context
        job_id: Optional job UUID for linking to background jobs
        db: Optional database session for logging (if not provided, logging is deferred)
    """
    llm_context.set({
        "operation_type": operation_type,
        "user_id": user_id,
        "product_id": product_id,
        "job_id": job_id,
        "db": db,
    })


def clear_llm_context() -> None:
    """Clear the LLM context after calls are complete."""
    llm_context.set({})


def get_llm_context() -> dict:
    """Get the current LLM context."""
    return llm_context.get()


def _log_llm_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    """
    Log LLM usage to the database if context is set.

    This is called internally after each LLM API call to record the usage.
    """
    ctx = llm_context.get()
    if not ctx or not ctx.get("db"):
        return

    try:
        from app.services.cost_tracking_service import CostTrackingService

        tracker = CostTrackingService(ctx["db"])
        tracker.log_usage(
            operation_type=ctx.get("operation_type", OperationType.OTHER),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            user_id=ctx.get("user_id"),
            product_id=ctx.get("product_id"),
            job_id=ctx.get("job_id"),
        )
    except Exception as e:
        # Don't let logging failures break the main operation
        print(f"Warning: Failed to log LLM usage: {e}")


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

    def structure_idea(self, freeform_text: str, product_context: Dict[str, any] = None) -> Dict[str, any]:
        """
        Structure freeform text into a structured idea format with product context.

        Takes natural language input and returns structured data adapted to the
        specific product, similar to competitor intelligence idea generation.

        Args:
            freeform_text: User's freeform idea description
            product_context: Optional product context for adaptation (name, description, features, etc.)

        Returns:
            Dictionary with structured idea and processing time

        Raises:
            APIError: If Claude API returns an error
            APITimeoutError: If request times out
            ValueError: If response cannot be parsed
        """
        start_time = time.time()

        # Build product-aware prompt if context provided
        if product_context:
            product_name = product_context.get('product_name', 'the product')
            product_description = product_context.get('product_description', '')
            product_category = product_context.get('product_category', '')
            core_features = product_context.get('core_features', [])
            detailed_features = product_context.get('detailed_features', [])
            target_users = product_context.get('target_users', '')
            value_propositions = product_context.get('value_propositions', [])

            # Format features for context
            core_features_str = "\n".join(f"  - {feat}" for feat in core_features) if core_features else "  (not specified)"
            detailed_features_str = ""
            if detailed_features:
                detailed_features_str = "\n".join(f"  - {feat.get('feature_name', '')}: {feat.get('feature_description', '')}" for feat in detailed_features)
            else:
                detailed_features_str = "  (not available - use core features for comparison)"
            value_props_str = "\n".join(f"  - {vp}" for vp in value_propositions) if value_propositions else "  (not specified)"

            prompt = f"""You are a product manager helping structure feature ideas for a specific product.

**Product Context:**

Product Name: {product_name}
Category: {product_category}
Description: {product_description}

Target Users: {target_users}

Core Features (existing capabilities):
{core_features_str}

Detailed Product Features (for duplicate detection):
{detailed_features_str}

Value Propositions:
{value_props_str}

**User's Idea:**

A user has submitted the following idea in their own words:

<user_idea>
{freeform_text}
</user_idea>

**Your Task:**

Structure this idea into a clear, professional format adapted to {product_name}'s specific context:

1. **FIRST:** Check if similar functionality already exists in the product's features above
2. Adapt the idea to fit {product_name}'s unique context and terminology
3. Tailor the value proposition to {product_name}'s target users: {target_users}
4. Use language consistent with {product_name}'s domain
5. Provide concrete use cases with {product_name}'s specific users

**Duplicate Detection:**
- If the idea is similar to an existing feature, still structure it but note the similarity in the "why" section
- Consider if it adds incremental value or is a true duplicate
- If it's an enhancement to existing functionality, frame it as such

**Output Format:**

Return ONLY a JSON object with these exact keys: title, what, why, use_case

1. **title**: A concise, {product_name}-specific title (5-10 words)
2. **what**: Clear description adapted to {product_name} (2-3 sentences)
3. **why**: Value proposition for {product_name}'s users (2-3 sentences, mention if similar feature exists)
4. **use_case**: Concrete example with {product_name}'s target users (2-3 sentences)

Do not include any markdown formatting, code blocks, or additional text - just the raw JSON.

Example format:
{{"title": "Enhanced Dark Mode for {product_name}", "what": "A toggle switch in settings that...", "why": "This would improve... Note: Similar to existing theme feature but adds...", "use_case": "A {target_users} working late at night..."}}"""
        else:
            # Fallback to generic prompt if no product context
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

            # Log usage for cost tracking
            _log_llm_usage(
                model=self.model,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
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

            # Log usage for cost tracking
            _log_llm_usage(
                model=message.model,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
            )

            return {
                "content": content,
                "tokens_used": tokens_used,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
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

    def call_agent_with_tools(
        self,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        tools: List[Dict[str, Any]],
        tool_executor: Callable[[str, Dict[str, Any]], Any],
        max_iterations: int = 8,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call Claude with tool use capability.

        Implements the tool-use loop:
        1. Send request with tool definitions
        2. If Claude requests a tool, execute it
        3. Send results back to Claude
        4. Repeat until Claude responds without requesting tools

        Args:
            agent_name: Name of the calling agent
            system_prompt: System message defining agent behavior
            user_prompt: User message with task details
            tools: List of tool definitions (Claude-compatible format)
            tool_executor: Function that executes tools: (tool_name, tool_input) -> result
            max_iterations: Maximum tool use cycles to prevent infinite loops
            **kwargs: Additional arguments for call_agent (temperature, max_tokens, model)

        Returns:
            Dict with final response and metadata

        Example tool definition:
            {
                "name": "web_search",
                "description": "Search the web for information",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            }
        """
        temperature = kwargs.get('temperature') or settings.temperature_default
        max_tokens = kwargs.get('max_tokens') or settings.max_tokens_default
        model = kwargs.get('model') or settings.claude_model

        # Message history for the conversation
        messages = [{"role": "user", "content": user_prompt}]
        total_tokens = 0
        iterations = 0

        try:
            while iterations < max_iterations:
                iterations += 1
                print(f"[{agent_name}] Tool use iteration {iterations}/{max_iterations}")

                # Call Claude with tools
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    tools=tools,
                    messages=messages
                )

                # Track tokens
                total_tokens += response.usage.input_tokens + response.usage.output_tokens

                # Log usage for cost tracking (log each API call in the tool loop)
                _log_llm_usage(
                    model=response.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )

                # Check stop reason
                if response.stop_reason == "end_turn":
                    # Claude is done - extract final text response
                    content = ""
                    for block in response.content:
                        if block.type == "text":
                            content += block.text

                    return {
                        "content": content,
                        "tokens_used": total_tokens,
                        "model": response.model,
                        "stop_reason": response.stop_reason,
                        "tool_calls": iterations - 1  # Number of tool calls made
                    }

                elif response.stop_reason == "tool_use":
                    # Claude wants to use a tool
                    print(f"[{agent_name}] Claude requested tool use")

                    # Add Claude's response to message history
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    # Execute all tool uses requested in this turn
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id

                            print(f"[{agent_name}] Executing tool: {tool_name} with input: {tool_input}")

                            try:
                                # Execute the tool
                                result = tool_executor(tool_name, tool_input)

                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": json.dumps(result) if not isinstance(result, str) else result
                                })

                                print(f"[{agent_name}] Tool {tool_name} executed successfully")

                            except Exception as e:
                                print(f"[{agent_name}] Tool execution error: {e}")
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": f"Error executing tool: {str(e)}",
                                    "is_error": True
                                })

                    # Add tool results to message history
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                else:
                    # Unexpected stop reason
                    print(f"[{agent_name}] Unexpected stop reason: {response.stop_reason}")
                    raise LLMServiceError(f"Unexpected stop reason: {response.stop_reason}")

            # Max iterations reached
            print(f"[{agent_name}] Max iterations reached without completion")
            raise LLMServiceError(f"Max tool use iterations ({max_iterations}) exceeded")

        except APIError as e:
            print(f"Claude API error in agent {agent_name}: {e}")
            raise LLMServiceError(f"Claude API error: {str(e)}")
        except Exception as e:
            print(f"Unexpected error in tool use for agent {agent_name}: {e}")
            raise LLMServiceError(f"Tool use error: {str(e)}")


class LLMServiceError(Exception):
    """Raised when LLM service encounters an error."""
    pass


# Create a singleton instance for reuse
llm_service = LLMService()
