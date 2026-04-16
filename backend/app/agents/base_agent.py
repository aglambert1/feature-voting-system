"""
Base Agent class for all AI agents.

This module provides the abstract base class that all AI agents inherit from,
providing automatic execution logging, error handling, and structured I/O.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type, List
import json
import time
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, ValidationError

from app.models.competitor_intelligence import AgentExecutionLog
from app.models.cost_tracking import OperationType
from app.services.llm_service import LLMService, LLMServiceError, set_llm_context, clear_llm_context


# Map agent stages to operation types for cost tracking
STAGE_TO_OPERATION_TYPE = {
    "product_analysis": OperationType.PRODUCT_ANALYSIS,
    "competitor_discovery": OperationType.COMPETITOR_DISCOVERY,
    "feature_extraction": OperationType.COMPETITOR_FEATURE_EXTRACTION,
    "gap_analysis": OperationType.GAP_ANALYSIS,
    "functional_audit": OperationType.FUNCTIONAL_AUDIT,
    "unified_synthesis": OperationType.OPPORTUNITY_SYNTHESIS,
    "activity_insight": OperationType.ACTIVITY_INSIGHT,
    "internal_discovery": OperationType.INTERNAL_DISCOVERY,
    "idea_generation": OperationType.IDEA_STRUCTURING,
    "job_map_extraction": OperationType.PRODUCT_ANALYSIS,
}


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents.

    Provides:
    - Automatic execution logging to database
    - Structured input/output validation
    - Error handling and retry logic
    - Token usage tracking
    - JSON response parsing with markdown support

    Usage:
        class MyAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are MyAgent..."

            def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
                return f"Process: {input_data}"

            def get_output_schema(self) -> Type[BaseModel]:
                return MyAgentOutput

            def get_stage(self) -> str:
                return "my_stage"

        agent = MyAgent(db=db, llm_service=llm_service)
        result = agent.execute({"data": "test"})
    """

    def __init__(
        self,
        db: Session,
        llm_service: LLMService,
        session_id: Optional[int] = None,
        product_id: Optional[int] = None,
        user_id: Optional[int] = None,
        job_id: Optional[str] = None
    ):
        """
        Initialize the agent.

        Args:
            db: SQLAlchemy database session
            llm_service: LLM service for API calls
            session_id: Optional competitor analysis session ID
            product_id: Optional product ID
            user_id: Optional user ID for cost tracking
            job_id: Optional job UUID for cost tracking
        """
        self.db = db
        self.llm_service = llm_service
        self.session_id = session_id
        self.product_id = product_id
        self.user_id = user_id
        self.job_id = job_id
        self.agent_name = self.__class__.__name__

    def get_operation_type(self) -> OperationType:
        """
        Get the operation type for cost tracking.

        Maps the agent stage to an OperationType enum value.
        Override in subclass for custom mapping.

        Returns:
            OperationType enum value
        """
        stage = self.get_stage()
        return STAGE_TO_OPERATION_TYPE.get(stage, OperationType.OTHER)

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Define the agent's system prompt.

        Should describe the agent's role, capabilities, and output format.

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """
        Build the user prompt from input data.

        Should format input into a clear prompt for the LLM.

        Args:
            input_data: Dictionary of input parameters

        Returns:
            User prompt string
        """
        pass

    def build_concise_user_prompt(self, input_data: Dict[str, Any]) -> Optional[str]:
        """
        Build a concise version of the user prompt for truncation recovery.

        Called when the full response was truncated (stop_reason == 'max_tokens').
        Return a modified prompt that instructs the LLM to produce shorter output.
        Return None if this agent does not support concise recovery (default).

        Args:
            input_data: Same input_data passed to build_user_prompt

        Returns:
            Concise prompt string, or None to disable recovery
        """
        return None

    @abstractmethod
    def get_output_schema(self) -> Type[BaseModel]:
        """
        Define the expected output schema as a Pydantic model.

        Used for validation and type safety.

        Returns:
            Pydantic model class
        """
        pass

    @abstractmethod
    def get_stage(self) -> str:
        """
        Define which stage this agent operates in.

        Examples: "product_analysis", "competitor_discovery", "feature_extraction"

        Returns:
            Stage name string
        """
        pass

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Optional: Define tools that this agent can use.

        Override this method to provide tool definitions for tool-enabled agents.
        If this returns a non-empty list, the agent will use Claude's tool use API.

        Returns:
            List of tool definitions (Claude API format), or empty list if no tools
        """
        return []

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Optional: Execute a tool by name.

        Override this method to handle tool execution.
        Only called if get_tools() returns a non-empty list.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            Tool execution result (will be sent back to Claude)

        Raises:
            NotImplementedError: If tool execution is not implemented
        """
        raise NotImplementedError(
            f"Agent {self.agent_name} defined tools but did not implement execute_tool()"
        )

    def execute(
        self,
        input_data: Dict[str, Any],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Execute the agent with automatic logging and error handling.

        This method:
        1. Validates input
        2. Builds prompts
        3. Calls LLM via LLMService
        4. Parses and validates output
        5. Logs execution to database
        6. Handles errors with retry logic

        Args:
            input_data: Input dictionary for the agent
            temperature: LLM temperature (0.0-1.0), uses config default if None
            max_tokens: Maximum tokens in response, uses config default if None
            max_retries: Number of retry attempts on failure (default: 3)

        Returns:
            Validated output dictionary

        Raises:
            AgentExecutionError: If execution fails after all retries
        """
        start_time = time.time()
        last_error = None

        for attempt in range(max_retries):
            try:
                # Validate input
                self._validate_input(input_data)

                # Build prompts
                system_prompt = self.get_system_prompt()
                user_prompt = self.build_user_prompt(input_data)

                # Check if agent uses tools
                tools = self.get_tools()
                print(f"[{self.agent_name}] get_tools() returned: {len(tools)} tools")

                # Set LLM context for cost tracking
                set_llm_context(
                    operation_type=self.get_operation_type(),
                    user_id=self.user_id,
                    product_id=self.product_id,
                    job_id=self.job_id,
                    db=self.db,
                )

                # Call LLM (with or without tools)
                if tools:
                    # Use tool-enabled call
                    print(f"[{self.agent_name}] Using tool-enabled execution with {len(tools)} tools")
                    response = self.llm_service.call_agent_with_tools(
                        agent_name=self.agent_name,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        tools=tools,
                        tool_executor=self.execute_tool,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                else:
                    # Standard call without tools
                    response = self.llm_service.call_agent(
                        agent_name=self.agent_name,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )

                # Check for truncated response before parsing
                if response.get('stop_reason') == 'max_tokens':
                    tokens_used = response.get('output_tokens', 'unknown')
                    print(
                        f"[{self.agent_name}] Response truncated: hit max_tokens limit "
                        f"(output_tokens={tokens_used}, max_tokens={max_tokens}). "
                        f"Attempting concise recovery..."
                    )

                    # Log truncation event for monitoring
                    self._log_execution(
                        input_data=input_data,
                        output_data={"output_tokens": tokens_used, "max_tokens": max_tokens},
                        tokens_used=response.get('tokens_used', 0),
                        execution_time_ms=int((time.time() - start_time) * 1000),
                        status="truncation_recovery",
                        error_message=(
                            f"Response truncated at {tokens_used} output tokens "
                            f"(max_tokens={max_tokens}). Attempting concise retry."
                        )
                    )

                    # Ask subclass for a concise prompt
                    concise_prompt = self.build_concise_user_prompt(input_data)
                    if concise_prompt is None:
                        raise AgentExecutionError(
                            f"Agent {self.agent_name} response was truncated (output hit "
                            f"max_tokens={max_tokens}) and does not support concise recovery. "
                            f"The product description may be too detailed for the current "
                            f"token budget. Try using a shorter product description or "
                            f"contact support to increase the limit."
                        )

                    # Single recovery attempt with concise prompt
                    print(f"[{self.agent_name}] Retrying with concise prompt...")

                    set_llm_context(
                        operation_type=self.get_operation_type(),
                        user_id=self.user_id,
                        product_id=self.product_id,
                        job_id=self.job_id,
                        db=self.db,
                    )

                    recovery_response = self.llm_service.call_agent(
                        agent_name=self.agent_name,
                        system_prompt=system_prompt,
                        user_prompt=concise_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )

                    if recovery_response.get('stop_reason') == 'max_tokens':
                        raise AgentExecutionError(
                            f"Agent {self.agent_name} response was truncated even with "
                            f"concise prompt (max_tokens={max_tokens}). The product "
                            f"description is too large for the current token budget."
                        )

                    # Parse recovery response
                    output_data = self._parse_and_validate_output(recovery_response['content'])

                    # Inject warning so downstream consumers know features were pruned
                    output_data['_warnings'] = [
                        "This analysis was condensed to fit within processing limits. "
                        "Some detailed features may have shorter descriptions or fewer "
                        "entries than a full extraction would produce."
                    ]

                    clear_llm_context()

                    # Log successful recovery
                    total_tokens = response.get('tokens_used', 0) + recovery_response.get('tokens_used', 0)
                    self._log_execution(
                        input_data=input_data,
                        output_data=output_data,
                        tokens_used=total_tokens,
                        execution_time_ms=int((time.time() - start_time) * 1000),
                        status="success_after_truncation_recovery"
                    )

                    print(f"[{self.agent_name}] Concise recovery successful.")
                    return output_data

                # Parse and validate output
                output_data = self._parse_and_validate_output(response['content'])

                # Clear LLM context after successful call
                clear_llm_context()

                # Log successful execution
                execution_time_ms = int((time.time() - start_time) * 1000)
                self._log_execution(
                    input_data=input_data,
                    output_data=output_data,
                    tokens_used=response.get('tokens_used', 0),
                    execution_time_ms=execution_time_ms,
                    status="success"
                )

                return output_data

            except ValidationError as e:
                last_error = f"Output validation failed: {str(e)}"
                if attempt < max_retries - 1:
                    # Retry with slightly higher temperature for more flexibility
                    temperature = min((temperature or 0.7) + 0.1, 1.0)
                    continue

            except json.JSONDecodeError as e:
                # Log the raw response content for debugging
                raw_content = response.get('content', '') if 'response' in locals() else 'No response'
                print(f"[BaseAgent] JSON decode error. Raw content (first 500 chars): {raw_content[:500]}")
                last_error = f"Invalid JSON response: {str(e)}"
                if attempt < max_retries - 1:
                    continue

            except LLMServiceError as e:
                last_error = f"LLM service error: {str(e)}"
                if attempt < max_retries - 1:
                    continue

            except AgentExecutionError:
                # Don't retry AgentExecutionErrors (e.g., truncation recovery failures)
                # — retrying with the full prompt would just truncate again
                raise

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                if attempt < max_retries - 1:
                    continue

        # Clear LLM context after failed execution
        clear_llm_context()

        # All retries failed - log error
        execution_time_ms = int((time.time() - start_time) * 1000)
        self._log_execution(
            input_data=input_data,
            output_data=None,
            tokens_used=0,
            execution_time_ms=execution_time_ms,
            status="failure",
            error_message=last_error
        )

        raise AgentExecutionError(
            f"Agent {self.agent_name} failed after {max_retries} attempts: {last_error}"
        )

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """
        Validate input data structure.

        Override in subclass for custom validation.

        Args:
            input_data: Input dictionary to validate

        Raises:
            ValueError: If input is invalid
        """
        if not isinstance(input_data, dict):
            raise ValueError("Input data must be a dictionary")

    def _parse_and_validate_output(self, response_content: str) -> Dict[str, Any]:
        """
        Parse LLM response and validate against schema.

        Handles:
        - Extracting JSON from markdown code blocks
        - Parsing JSON
        - Validating against Pydantic schema

        Args:
            response_content: Raw response from LLM

        Returns:
            Validated output dictionary

        Raises:
            json.JSONDecodeError: If JSON parsing fails
            ValidationError: If validation fails
        """
        # Extract JSON from response (handle markdown code blocks)
        json_str = self._extract_json(response_content)

        # Debug: log if extraction didn't fully clean the content
        if json_str.startswith('`'):
            print(f"[BaseAgent] Warning: extracted JSON still has backticks. First 100 chars: {json_str[:100]}")

        # Parse JSON
        output_dict = json.loads(json_str)

        # Validate against Pydantic schema
        schema_class = self.get_output_schema()
        validated = schema_class(**output_dict)

        # Return as dict with JSON serialization mode to convert HttpUrl to strings
        return validated.model_dump(mode='json')

    def _extract_json(self, content: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks and explanatory text.

        Supports:
        - ```json ... ```
        - ``` ... ```
        - Raw JSON
        - Explanatory text before JSON

        Args:
            content: Raw response content

        Returns:
            Extracted JSON string
        """
        content = content.strip()

        # Check for markdown code block with json language tag
        if "```json" in content:
            # Find and extract content between ```json and closing ```
            start = content.find("```json") + 7
            # Skip any whitespace/newlines after ```json
            while start < len(content) and content[start] in ' \t\n\r':
                start += 1
            end = content.find("```", start)
            if end != -1:
                content = content[start:end]
        elif "```" in content:
            # Find and extract content between ``` and closing ```
            start = content.find("```") + 3
            # Skip any whitespace/newlines after ```
            while start < len(content) and content[start] in ' \t\n\r':
                start += 1
            end = content.find("```", start)
            if end != -1:
                content = content[start:end]

        content = content.strip()

        # If content still has explanatory text before JSON, find the first { or [
        if not content.startswith("{") and not content.startswith("["):
            # Find first occurrence of { or [
            json_start = min(
                (content.find("{") if content.find("{") != -1 else len(content)),
                (content.find("[") if content.find("[") != -1 else len(content))
            )
            if json_start < len(content):
                content = content[json_start:]

        return content.strip()

    def _log_execution(
        self,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]],
        tokens_used: int,
        execution_time_ms: int,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log agent execution to database.

        Creates an AgentExecutionLog record with execution details.

        Args:
            input_data: Input provided to agent
            output_data: Output produced by agent (None if failed)
            tokens_used: Number of LLM tokens used
            execution_time_ms: Execution time in milliseconds
            status: "success" or "failure"
            error_message: Error message if status is "failure"
        """
        try:
            log = AgentExecutionLog(
                session_id=self.session_id,
                product_id=self.product_id,
                agent_name=self.agent_name,
                stage=self.get_stage(),
                input_data=input_data,
                output_data=output_data,
                llm_tokens_used=tokens_used,
                execution_time_ms=execution_time_ms,
                status=status,
                error_message=error_message
            )

            self.db.add(log)
            self.db.commit()
        except SQLAlchemyError as e:
            # Log the error but don't fail the agent execution
            print(f"Failed to log agent execution: {e}")
            self.db.rollback()


class AgentExecutionError(Exception):
    """Raised when agent execution fails after all retries."""
    pass
