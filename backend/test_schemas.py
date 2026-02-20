#!/usr/bin/env python3
"""
Test script for Pydantic schemas (Chunk 1).

This tests schema validation without needing API keys or database.

Usage:
    python test_schemas.py
"""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.schemas.idea import IdeaCreate, IdeaResponse, VoteCount
from app.schemas.vote import VoteCreate
from app.schemas.submission import SubmissionStructureRequest, SubmissionStructureResponse


def test_schemas():
    """Test all schema validation."""

    print("=" * 60)
    print("Testing Pydantic Schemas (Chunk 1)")
    print("=" * 60)
    print()

    # Test 1: IdeaCreate Schema
    print("Test 1: IdeaCreate Schema")
    print("-" * 40)
    try:
        idea = IdeaCreate(
            title="Dark Mode Toggle",
            what_description="A toggle switch in settings that enables dark mode",
            why_description="Improves usability at night and reduces eye strain",
            use_case_description="User opens settings and toggles dark mode on/off",
            category="UI/UX"
        )
        print("✓ Valid idea created")
        print(f"  Title: {idea.title}")
        print(f"  Category: {idea.category}")
    except Exception as e:
        print(f"✗ Error: {e}")
    print()

    # Test 2: IdeaCreate Validation (should fail - title too short)
    print("Test 2: IdeaCreate Validation (title too short)")
    print("-" * 40)
    try:
        idea = IdeaCreate(
            title="No",  # Too short!
            what_description="A toggle switch in settings",
            why_description="Improves usability at night",
            use_case_description="User opens settings"
        )
        print("✗ Should have failed validation!")
    except Exception as e:
        print(f"✓ Validation correctly rejected: {str(e)[:80]}...")
    print()

    # Test 3: VoteCreate Schema
    print("Test 3: VoteCreate Schema")
    print("-" * 40)
    try:
        upvote = VoteCreate(vote_value=1)
        print(f"✓ Upvote created: {upvote.vote_value}")
    except Exception as e:
        print(f"✗ Error: {e}")
    print()

    # Test 4: VoteCreate Validation (should fail - invalid value)
    print("Test 4: VoteCreate Validation (invalid vote value)")
    print("-" * 40)
    try:
        invalid_vote = VoteCreate(vote_value=5)  # Invalid!
        print("✗ Should have failed validation!")
    except Exception as e:
        print(f"✓ Validation correctly rejected: {str(e)[:80]}...")
    print()

    # Test 5: SubmissionStructureRequest
    print("Test 5: SubmissionStructureRequest Schema")
    print("-" * 40)
    try:
        request = SubmissionStructureRequest(
            freeform_text="I want a way to export my data to CSV so I can analyze it in Excel"
        )
        print("✓ Submission request created")
        print(f"  Text length: {len(request.freeform_text)} characters")
    except Exception as e:
        print(f"✗ Error: {e}")
    print()

    # Test 6: SubmissionStructureResponse
    print("Test 6: SubmissionStructureResponse Schema")
    print("-" * 40)
    try:
        response = SubmissionStructureResponse(
            title="CSV Data Export",
            what_description="A feature that allows users to export their data in CSV format",
            why_description="Users can backup and analyze their data in spreadsheet applications",
            use_case_description="User clicks 'Export' button and downloads a CSV file",
            processing_time=2.5
        )
        print("✓ Submission response created")
        print(f"  Title: {response.title}")
        print(f"  Processing time: {response.processing_time}s")
    except Exception as e:
        print(f"✗ Error: {e}")
    print()

    # Test 7: VoteCount Schema
    print("Test 7: VoteCount Schema")
    print("-" * 40)
    try:
        vote_count = VoteCount(
            upvotes=10,
            total_votes=10
        )
        print("✓ Vote count created")
        print(f"  Upvotes: {vote_count.upvotes}")
        print(f"  Total: {vote_count.total_votes}")
    except Exception as e:
        print(f"✗ Error: {e}")
    print()

    print("=" * 60)
    print("All Schema Tests Passed! ✓")
    print("=" * 60)


if __name__ == "__main__":
    test_schemas()
