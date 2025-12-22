# Module 3: Base Agent Infrastructure

## Objective
Create a reusable framework for all AI agents that provides consistent execution, logging, error handling, and integration with the Claude API.

## Dependencies
- **Requires**: Module 1 (Database Schema - agent_execution_logs table)
- **Uses**: Existing `LLMService` in `app/services/llm_service.py`

## Scope
- Base agent abstract class
- LLM service extensions for agent-specific calls
- Automatic execution logging
- Token usage tracking
- Error handling and retry logic
- JSON response parsing and validation
- Unit tests with mock agents

## Architecture Overview

```
BaseAgent (Abstract Class)
    ├─→ Input validation
    ├─→ Prompt construction
    ├─→ Call LLMService
    ├─→ Parse JSON response
    ├─→ Validate output
    ├─→ Log execution to database
    └─→ Error handling with retry

LLMService (Extended)
    ├─→ call_agent() method
    ├─→ Token counting
    ├─→ Rate limiting
    └─→ Response parsing
```

## Implementation

### 1. Base Agent Class

Location: `app/agents/base_agent.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ValidationError
import json
import time
from sqlalchemy.orm import Session
from app.models.competitor_intelligence import AgentExecutionLog
from app.services.llm_service import LLMService

class BaseAgent(ABC):
    """
    Abstract base class for all AI agents.
    
    Provides:
    - Automatic execution logging
    - Structured input/output
    - Error handling and retry logic
    - Token usage tracking
    - JSON response parsing
    """
    
    def __init__(
        self, 
        db: Session,
        llm_service: LLMService,
        session_id: Optional[UUID] = None,
        product_id: Optional[UUID] = None
    ):
        self.db = db
        self.llm_service = llm_service
        self.session_id = session_id
        self.product_id = product_id
        self.agent_name = self.__class__.__name__
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Define the agent's system prompt.
        Should describe the agent's role and capabilities.
        """
        pass
    
    @abstractmethod
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """
        Build the user prompt from input data.
        Should format input into a clear prompt for the LLM.
        """
        pass
    
    @abstractmethod
    def get_output_schema(self) -> Type[BaseModel]:
        """
        Define the expected output schema as a Pydantic model.
        Used for validation and type safety.
        """
        pass
    
    @abstractmethod
    def get_stage(self) -> str:
        """
        Define which stage this agent operates in.
        Examples: "product_analysis", "competitor_discovery", "feature_extraction"
        """
        pass
    
    async def execute(
        self, 
        input_data: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Execute the agent with automatic logging and error handling.
        
        Args:
            input_data: Input dictionary for the agent
            temperature: LLM temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            max_retries: Number of retry attempts on failure
            
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
                
                # Call LLM
                response = await self.llm_service.call_agent(
                    agent_name=self.agent_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Parse and validate output
                output_data = self._parse_and_validate_output(response['content'])
                
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
                    temperature = min(temperature + 0.1, 1.0)
                    continue
                    
            except json.JSONDecodeError as e:
                last_error = f"Invalid JSON response: {str(e)}"
                if attempt < max_retries - 1:
                    continue
                    
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                if attempt < max_retries - 1:
                    continue
        
        # All retries failed - log error
        execution_time_ms = int((time.time() - start_time) * 1000)
        self._log_execution(
            input_data=input_data,
            output_data=None,
            tokens_used=0,
            execution_time_ms=execution_time_ms,
            status="error",
            error_message=last_error
        )
        
        raise AgentExecutionError(
            f"Agent {self.agent_name} failed after {max_retries} attempts: {last_error}"
        )
    
    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """
        Validate input data structure.
        Override in subclass for custom validation.
        """
        if not isinstance(input_data, dict):
            raise ValueError("Input data must be a dictionary")
    
    def _parse_and_validate_output(self, response_content: str) -> Dict[str, Any]:
        """
        Parse LLM response and validate against schema.
        """
        # Extract JSON from response (handle markdown code blocks)
        json_str = self._extract_json(response_content)
        
        # Parse JSON
        output_dict = json.loads(json_str)
        
        # Validate against Pydantic schema
        schema_class = self.get_output_schema()
        validated = schema_class(**output_dict)
        
        # Return as dict
        return validated.model_dump()
    
    def _extract_json(self, content: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks.
        """
        content = content.strip()
        
        # Check for markdown code block
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json
        elif content.startswith("```"):
            content = content[3:]  # Remove ```
            
        if content.endswith("```"):
            content = content[:-3]  # Remove trailing ```
            
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
        """
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


class AgentExecutionError(Exception):
    """Raised when agent execution fails after all retries"""
    pass
```

### 2. LLM Service Extensions

Location: `app/services/llm_service.py` (extend existing class)

```python
# Add these methods to your existing LLMService class

from typing import Dict, Any
import anthropic
from app.config import settings

class LLMService:
    """
    Service for interacting with LLM APIs.
    (Assumes this class already exists - we're adding agent-specific methods)
    """
    
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
        self.default_model = "claude-sonnet-4-5-20250929"
    
    async def call_agent(
        self,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call Claude API for agent execution.
        
        Args:
            agent_name: Name of the calling agent (for logging)
            system_prompt: System message defining agent behavior
            user_prompt: User message with task details
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            model: Model to use (default: claude-sonnet-4-5)
            
        Returns:
            Dict with 'content' and 'tokens_used'
        """
        try:
            message = self.client.messages.create(
                model=model or self.default_model,
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
            
        except anthropic.APIError as e:
            raise LLMServiceError(f"Claude API error: {str(e)}")
        except Exception as e:
            raise LLMServiceError(f"Unexpected error calling Claude: {str(e)}")
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Uses rough approximation: 1 token ≈ 4 characters
        """
        return len(text) // 4
    
    async def call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call Claude with automatic retry on rate limits.
        """
        import time
        
        for attempt in range(max_retries):
            try:
                return await self.call_agent(
                    agent_name="retry_wrapper",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    **kwargs
                )
            except anthropic.RateLimitError:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    time.sleep(wait_time)
                    continue
                raise


class LLMServiceError(Exception):
    """Raised when LLM service encounters an error"""
    pass
```

### 3. Configuration

Location: `app/config.py` (add if not exists)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Existing settings...
    
    # LLM Configuration
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-5-20250929"
    MAX_TOKENS_DEFAULT: int = 4000
    TEMPERATURE_DEFAULT: float = 0.7
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 4. Example Test Agent

Location: `app/agents/test_agents.py`

```python
from typing import Dict, Any, Type
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent

class EchoAgentOutput(BaseModel):
    """Output schema for EchoAgent"""
    message: str = Field(..., description="The echoed message")
    input_received: Dict[str, Any] = Field(..., description="Copy of input")
    agent_name: str = Field(..., description="Name of this agent")

class EchoAgent(BaseAgent):
    """
    Simple test agent that echoes input back.
    Used for testing the agent framework.
    """
    
    def get_system_prompt(self) -> str:
        return """You are a test agent called EchoAgent. 
Your job is to return the input you receive in a structured format.
Always respond with valid JSON matching the specified schema."""
    
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        return f"""
Please echo back the following input in JSON format:

Input: {input_data}

Return a JSON object with:
- message: "Echo successful"
- input_received: (copy of the input)
- agent_name: "EchoAgent"
"""
    
    def get_output_schema(self) -> Type[BaseModel]:
        return EchoAgentOutput
    
    def get_stage(self) -> str:
        return "testing"


class StructuredOutputAgent(BaseAgent):
    """
    Test agent that generates structured output from text.
    Demonstrates typical agent pattern.
    """
    
    def get_system_prompt(self) -> str:
        return """You are a text analysis agent.
You extract key information from text and return it in structured format.
Always respond with valid JSON."""
    
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        text = input_data.get("text", "")
        return f"""
Analyze the following text and extract key information:

Text: {text}

Return a JSON object with:
- summary: A brief summary (1-2 sentences)
- key_points: List of 3-5 key points
- sentiment: "positive", "negative", or "neutral"
"""
    
    def get_output_schema(self) -> Type[BaseModel]:
        class StructuredOutput(BaseModel):
            summary: str
            key_points: list[str]
            sentiment: str
        
        return StructuredOutput
    
    def get_stage(self) -> str:
        return "testing"
```

## Testing Requirements

### Unit Tests

Location: `tests/test_base_agent.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.agents.base_agent import BaseAgent, AgentExecutionError
from app.agents.test_agents import EchoAgent, EchoAgentOutput
from app.services.llm_service import LLMService

@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing"""
    service = Mock(spec=LLMService)
    service.call_agent = AsyncMock()
    return service

@pytest.fixture
def echo_agent(db_session, mock_llm_service):
    """Create EchoAgent for testing"""
    return EchoAgent(
        db=db_session,
        llm_service=mock_llm_service
    )

@pytest.mark.asyncio
async def test_agent_successful_execution(echo_agent, mock_llm_service):
    """Test successful agent execution"""
    # Mock LLM response
    mock_llm_service.call_agent.return_value = {
        "content": '''```json
{
    "message": "Echo successful",
    "input_received": {"test": "data"},
    "agent_name": "EchoAgent"
}
```''',
        "tokens_used": 100
    }
    
    # Execute agent
    result = await echo_agent.execute({"test": "data"})
    
    # Verify output
    assert result["message"] == "Echo successful"
    assert result["input_received"] == {"test": "data"}
    assert result["agent_name"] == "EchoAgent"
    
    # Verify LLM was called
    mock_llm_service.call_agent.assert_called_once()

@pytest.mark.asyncio
async def test_agent_retry_on_invalid_json(echo_agent, mock_llm_service):
    """Test that agent retries on invalid JSON"""
    # First call returns invalid JSON
    # Second call returns valid JSON
    mock_llm_service.call_agent.side_effect = [
        {"content": "Invalid JSON {", "tokens_used": 50},
        {
            "content": '{"message": "Echo successful", "input_received": {}, "agent_name": "EchoAgent"}',
            "tokens_used": 100
        }
    ]
    
    # Should succeed on retry
    result = await echo_agent.execute({"test": "data"})
    assert result["message"] == "Echo successful"
    
    # Verify retry happened
    assert mock_llm_service.call_agent.call_count == 2

@pytest.mark.asyncio
async def test_agent_fails_after_max_retries(echo_agent, mock_llm_service):
    """Test that agent fails after max retries"""
    # Always return invalid JSON
    mock_llm_service.call_agent.return_value = {
        "content": "Invalid JSON",
        "tokens_used": 50
    }
    
    # Should raise exception
    with pytest.raises(AgentExecutionError):
        await echo_agent.execute({"test": "data"}, max_retries=3)
    
    # Verify retries
    assert mock_llm_service.call_agent.call_count == 3

@pytest.mark.asyncio
async def test_agent_logs_execution(echo_agent, mock_llm_service, db_session):
    """Test that agent logs execution to database"""
    from app.models.competitor_intelligence import AgentExecutionLog
    
    mock_llm_service.call_agent.return_value = {
        "content": '{"message": "Echo successful", "input_received": {}, "agent_name": "EchoAgent"}',
        "tokens_used": 100
    }
    
    await echo_agent.execute({"test": "data"})
    
    # Check log was created
    log = db_session.query(AgentExecutionLog).filter_by(
        agent_name="EchoAgent"
    ).first()
    
    assert log is not None
    assert log.status == "success"
    assert log.llm_tokens_used == 100
    assert log.stage == "testing"
    assert log.input_data == {"test": "data"}

@pytest.mark.asyncio
async def test_agent_extracts_json_from_markdown(echo_agent, mock_llm_service):
    """Test JSON extraction from markdown code blocks"""
    # Test various markdown formats
    test_cases = [
        '```json\n{"message": "test", "input_received": {}, "agent_name": "EchoAgent"}\n```',
        '```\n{"message": "test", "input_received": {}, "agent_name": "EchoAgent"}\n```',
        '{"message": "test", "input_received": {}, "agent_name": "EchoAgent"}',
    ]
    
    for content in test_cases:
        mock_llm_service.call_agent.return_value = {
            "content": content,
            "tokens_used": 100
        }
        
        result = await echo_agent.execute({"test": "data"})
        assert result["message"] == "test"

def test_agent_output_validation():
    """Test that output schema validation works"""
    # Valid output
    valid_data = {
        "message": "test",
        "input_received": {"key": "value"},
        "agent_name": "EchoAgent"
    }
    output = EchoAgentOutput(**valid_data)
    assert output.message == "test"
    
    # Invalid output (missing required field)
    with pytest.raises(Exception):  # Pydantic ValidationError
        EchoAgentOutput(message="test")
```

### Integration Tests

Location: `tests/test_llm_service.py`

```python
import pytest
from unittest.mock import Mock, patch
from app.services.llm_service import LLMService, LLMServiceError

@pytest.mark.asyncio
async def test_llm_service_call_agent():
    """Test calling Claude API through LLMService"""
    service = LLMService()
    
    # Mock the Anthropic client
    with patch.object(service, 'client') as mock_client:
        # Setup mock response
        mock_message = Mock()
        mock_message.content = [Mock(type="text", text="Test response")]
        mock_message.usage.input_tokens = 50
        mock_message.usage.output_tokens = 100
        mock_message.model = "claude-sonnet-4-5-20250929"
        mock_message.stop_reason = "end_turn"
        
        mock_client.messages.create.return_value = mock_message
        
        # Call the service
        result = await service.call_agent(
            agent_name="TestAgent",
            system_prompt="You are a test agent",
            user_prompt="Test prompt"
        )
        
        # Verify result
        assert result["content"] == "Test response"
        assert result["tokens_used"] == 150
        assert result["model"] == "claude-sonnet-4-5-20250929"

@pytest.mark.asyncio
async def test_llm_service_handles_api_error():
    """Test that LLMService handles API errors"""
    service = LLMService()
    
    with patch.object(service, 'client') as mock_client:
        # Simulate API error
        import anthropic
        mock_client.messages.create.side_effect = anthropic.APIError("API Error")
        
        # Should raise LLMServiceError
        with pytest.raises(LLMServiceError):
            await service.call_agent(
                agent_name="TestAgent",
                system_prompt="Test",
                user_prompt="Test"
            )

def test_token_counting():
    """Test token count estimation"""
    service = LLMService()
    
    text = "This is a test sentence with approximately twenty tokens in it."
    count = service.count_tokens(text)
    
    # Should be roughly text length / 4
    assert count > 0
    assert count == len(text) // 4
```

### Manual Testing

Create a test script: `scripts/test_agent_framework.py`

```python
import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.llm_service import LLMService
from app.agents.test_agents import EchoAgent

async def test_echo_agent():
    """Manually test the EchoAgent with real Claude API"""
    db = SessionLocal()
    llm_service = LLMService()
    
    try:
        agent = EchoAgent(db=db, llm_service=llm_service)
        
        print("Testing EchoAgent...")
        result = await agent.execute({
            "test_message": "Hello from test script",
            "timestamp": "2024-01-01"
        })
        
        print("Success! Output:")
        print(result)
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_echo_agent())
```

Run with:
```bash
python scripts/test_agent_framework.py
```

## Acceptance Criteria

**Core Framework:**
- [ ] `BaseAgent` class created with all required methods
- [ ] Agents can execute with automatic logging
- [ ] Agents retry on failures (up to max_retries)
- [ ] Agents parse JSON responses (including markdown blocks)
- [ ] Agents validate output against Pydantic schemas
- [ ] Agents track token usage
- [ ] Agents measure execution time

**LLM Service:**
- [ ] `LLMService.call_agent()` method works
- [ ] Claude API integration functional
- [ ] Error handling for API failures
- [ ] Token counting works
- [ ] Retry logic with exponential backoff

**Logging:**
- [ ] All executions logged to `agent_execution_logs` table
- [ ] Success and error cases both logged
- [ ] Input/output data captured
- [ ] Token usage tracked
- [ ] Execution time recorded

**Testing:**
- [ ] `EchoAgent` test agent works
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Manual test script runs successfully
- [ ] Mock fixtures work correctly

**Documentation:**
- [ ] Code is well-commented
- [ ] Docstrings for all public methods
- [ ] Example usage in test agents

## Files to Create/Modify

**New Files:**
- `app/agents/__init__.py`
- `app/agents/base_agent.py`
- `app/agents/test_agents.py`
- `tests/test_base_agent.py`
- `tests/test_llm_service.py`
- `scripts/test_agent_framework.py`

**Modified Files:**
- `app/services/llm_service.py` (extend with agent methods)
- `app/config.py` (add LLM settings if needed)

**Environment Variables:**
Add to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-5-20250929
```

## Usage Example

Once Module 3 is complete, creating new agents in future modules will follow this pattern:

```python
from app.agents.base_agent import BaseAgent
from pydantic import BaseModel
from typing import Dict, Any, Type

class MyAgentOutput(BaseModel):
    result: str
    confidence: float

class MyAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return "You are MyAgent. You do X."
    
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        return f"Process this: {input_data}"
    
    def get_output_schema(self) -> Type[BaseModel]:
        return MyAgentOutput
    
    def get_stage(self) -> str:
        return "my_stage"

# Usage:
agent = MyAgent(db=db, llm_service=llm_service)
result = await agent.execute({"data": "test"})
```

## Estimated Time
**1-2 days** including testing

## Next Module
After completing this module, proceed to **Module 4: Product Analysis Agent**

---

**Note:** This module creates the foundation that all future agents (Modules 4-7) will build upon. Take time to test thoroughly as issues here will affect all subsequent modules.
