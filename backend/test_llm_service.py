#!/usr/bin/env python3
"""
Test script for LLM Service (Chunk 1).

This tests the Claude API integration without needing the full API running.

Usage:
    python test_llm_service.py
"""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.llm_service import llm_service
from app.config import settings


def test_llm_service():
    """Test the LLM service with a sample idea."""

    print("=" * 60)
    print("Testing LLM Service (Claude API)")
    print("=" * 60)
    print()

    # Check if API key is configured
    if settings.anthropic_api_key == "your-anthropic-api-key-here":
        print("❌ ERROR: ANTHROPIC_API_KEY not configured in .env")
        print()
        print("To test the LLM service:")
        print("1. Get your API key from https://console.anthropic.com/")
        print("2. Add it to backend/.env:")
        print("   ANTHROPIC_API_KEY=sk-ant-api03-xxxxx")
        print("3. Run this test again")
        return

    print(f"✓ API key configured: {settings.anthropic_api_key[:20]}...")
    print()

    # Test cases
    test_cases = [
        {
            "name": "Simple Feature Request",
            "text": "I want a dark mode toggle in the settings so I can use the app at night"
        },
        {
            "name": "Complex Feature Description",
            "text": "We need a way for users to export their data to CSV format. This would be really helpful for people who want to analyze their data in Excel or keep backups. They could click an export button and download all their information."
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {test_case['name']}")
        print(f"{'='*60}")
        print(f"\nInput text:")
        print(f"  {test_case['text']}")
        print()

        try:
            print("⏳ Calling Claude API...")
            result = llm_service.structure_idea(test_case['text'])

            print(f"✓ Success! (took {result['processing_time']}s)")
            print()
            print("Structured Output:")
            print(f"  Title: {result['title']}")
            print(f"  What:  {result['what_description'][:80]}...")
            print(f"  Why:   {result['why_description'][:80]}...")
            print(f"  Use Case: {result['use_case_description'][:80]}...")
            print()

        except Exception as e:
            print(f"✗ Error: {e}")
            print()

    print("=" * 60)
    print("LLM Service Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_llm_service()
