"""
Manual test script for the agent framework.

This script tests the agent framework with real Claude API calls.
Use it to verify that the framework works end-to-end.

Usage:
    cd backend
    python scripts/test_agent_framework.py

Requirements:
    - ANTHROPIC_API_KEY must be set in .env file
    - Database must be initialized
"""

import sys
from pathlib import Path

# Add the backend directory to the path so we can import app modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.competitor_intelligence import Base
from app.services.llm_service import llm_service
from app.agents.test_agents import EchoAgent, StructuredOutputAgent


def ensure_tables_exist():
    """Ensure database tables exist."""
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables ensured")


def test_echo_agent(db: Session):
    """Test the EchoAgent with real Claude API."""
    print("\n" + "="*60)
    print("Testing EchoAgent")
    print("="*60)

    agent = EchoAgent(db=db, llm_service=llm_service)

    test_input = {
        "test_message": "Hello from test script",
        "timestamp": "2025-01-01T12:00:00",
        "nested": {
            "key": "value",
            "number": 42
        }
    }

    print(f"\nInput: {test_input}")
    print("\nCalling Claude API via EchoAgent...")

    try:
        result = agent.execute(test_input)

        print("\n✓ Success! Output:")
        print(f"  Message: {result['message']}")
        print(f"  Agent Name: {result['agent_name']}")
        print(f"  Input Received: {result['input_received']}")

        # Verify execution was logged
        from app.models.competitor_intelligence import AgentExecutionLog
        log = db.query(AgentExecutionLog).filter_by(
            agent_name="EchoAgent"
        ).order_by(AgentExecutionLog.created_at.desc()).first()

        if log:
            print(f"\n✓ Execution logged:")
            print(f"  Status: {log.status}")
            print(f"  Tokens used: {log.llm_tokens_used}")
            print(f"  Execution time: {log.execution_time_ms}ms")
            print(f"  Stage: {log.stage}")

        return True

    except Exception as e:
        print(f"\n✗ Failed: {e}")
        return False


def test_structured_output_agent(db: Session):
    """Test the StructuredOutputAgent with real Claude API."""
    print("\n" + "="*60)
    print("Testing StructuredOutputAgent")
    print("="*60)

    agent = StructuredOutputAgent(db=db, llm_service=llm_service)

    test_text = """
    I recently purchased this amazing productivity app and I'm extremely satisfied!
    The user interface is intuitive and clean. The features are well-designed and
    actually solve my daily workflow problems. Customer support was responsive when
    I had questions. The price point is very reasonable for the value provided.
    I've already recommended it to several colleagues who have also become users.
    This is exactly what I was looking for!
    """

    test_input = {"text": test_text.strip()}

    print(f"\nInput text: {test_text[:100]}...")
    print("\nCalling Claude API via StructuredOutputAgent...")

    try:
        result = agent.execute(test_input)

        print("\n✓ Success! Output:")
        print(f"  Summary: {result['summary']}")
        print(f"  Key Points:")
        for i, point in enumerate(result['key_points'], 1):
            print(f"    {i}. {point}")
        print(f"  Sentiment: {result['sentiment']}")

        # Verify execution was logged
        from app.models.competitor_intelligence import AgentExecutionLog
        log = db.query(AgentExecutionLog).filter_by(
            agent_name="StructuredOutputAgent"
        ).order_by(AgentExecutionLog.created_at.desc()).first()

        if log:
            print(f"\n✓ Execution logged:")
            print(f"  Status: {log.status}")
            print(f"  Tokens used: {log.llm_tokens_used}")
            print(f"  Execution time: {log.execution_time_ms}ms")

        return True

    except Exception as e:
        print(f"\n✗ Failed: {e}")
        return False


def test_error_handling(db: Session):
    """Test that error handling and retry logic works."""
    print("\n" + "="*60)
    print("Testing Error Handling")
    print("="*60)

    agent = EchoAgent(db=db, llm_service=llm_service)

    # Test with very short max_tokens to potentially trigger truncation
    print("\nTesting with very low max_tokens (may cause retry)...")

    try:
        result = agent.execute(
            {"test": "data"},
            max_tokens=10,  # Very low, may cause issues
            max_retries=2
        )
        print("✓ Handled low tokens gracefully")
        return True

    except Exception as e:
        print(f"✓ Error handled as expected: {type(e).__name__}")
        # This is actually expected - verify it was logged
        from app.models.competitor_intelligence import AgentExecutionLog
        log = db.query(AgentExecutionLog).filter_by(
            agent_name="EchoAgent",
            status="failure"
        ).order_by(AgentExecutionLog.created_at.desc()).first()

        if log:
            print(f"✓ Failure logged correctly:")
            print(f"  Error message: {log.error_message[:100]}...")
            return True
        return False


def main():
    """Run all agent framework tests."""
    print("="*60)
    print("AGENT FRAMEWORK MANUAL TEST")
    print("="*60)

    # Ensure tables exist
    ensure_tables_exist()

    # Create database session
    db = SessionLocal()

    try:
        results = []

        # Run tests
        results.append(("EchoAgent", test_echo_agent(db)))
        results.append(("StructuredOutputAgent", test_structured_output_agent(db)))
        results.append(("Error Handling", test_error_handling(db)))

        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for test_name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status}: {test_name}")

        print(f"\nTotal: {passed}/{total} tests passed")

        if passed == total:
            print("\n🎉 All tests passed!")
            sys.exit(0)
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
