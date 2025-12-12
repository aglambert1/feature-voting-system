"""
Test search functionality for CompetitorResearcherAgent.

This script tests:
1. Tool use loop works correctly
2. Brave Search API integration
3. JSON extraction with explanatory text
4. Rate limiting behavior
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from sqlalchemy.orm import Session
from app.database import engine, Base
from app.agents.competitor_researcher import CompetitorResearcherAgent
from app.services.llm_service import LLMService
from app.services.search_service import get_search_service

def test_search_functionality():
    """Test competitor discovery with search enabled."""

    # Create database session
    Base.metadata.create_all(bind=engine)
    db = Session(bind=engine)

    try:
        # Initialize services
        llm_service = LLMService()
        search_service = get_search_service()

        print("\n" + "="*80)
        print("SEARCH FUNCTIONALITY TEST")
        print("="*80)

        # Check if search is available
        print(f"\n✓ Search Service Available: {search_service.is_available()}")

        if not search_service.is_available():
            print("✗ Search is not available. Check BRAVE_API_KEY in .env")
            return

        # Create agent
        agent = CompetitorResearcherAgent(
            db=db,
            llm_service=llm_service,
            session_id=None,
            product_id=None
        )

        # Test input
        test_input = {
            'product_name': 'Smart Heated Slippers',
            'product_category': 'Smart Footwear / Heated Apparel',
            'core_features': [
                'Wireless heating',
                'App control',
                'Temperature regulation',
                'Battery powered'
            ],
            'target_users': 'Cold-sensitive individuals, people with poor circulation',
            'competitor_search_keywords': [
                'heated slippers',
                'smart footwear',
                'warming slippers',
                'temperature controlled footwear'
            ]
        }

        print(f"\n✓ Test Product: {test_input['product_name']}")
        print(f"✓ Category: {test_input['product_category']}")
        print(f"✓ Tools Available: {len(agent.get_tools())} tool(s)")

        print("\n" + "-"*80)
        print("EXECUTING AGENT (this may take 30-60 seconds)...")
        print("-"*80)

        # Execute agent
        result = agent.execute(test_input)

        # Display results
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)

        competitors = result.get('competitors', [])
        research_summary = result.get('research_summary', '')

        print(f"\n✓ Competitors Found: {len(competitors)}")
        print(f"\n✓ Research Summary:\n{research_summary}")

        if competitors:
            print(f"\n✓ Competitor Details:")
            for i, comp in enumerate(competitors, 1):
                print(f"\n{i}. {comp.get('name', 'Unknown')}")
                print(f"   URL: {comp.get('url', 'N/A')}")
                print(f"   Relevance: {comp.get('relevance_score', 0.0):.2f}")
                print(f"   Summary: {comp.get('summary', 'N/A')[:100]}...")
        else:
            print("\n✗ No competitors found (this might be due to rate limiting or search issues)")

        print("\n" + "="*80)
        print("TEST COMPLETE")
        print("="*80)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_search_functionality()
