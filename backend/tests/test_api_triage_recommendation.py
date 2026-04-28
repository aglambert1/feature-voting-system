"""Tests for GET /ideas/{id}/triage-recommendation.

Specifically guards Bug 2: the PM-facing recommendation must reflect the
correct classified status (e.g., feature_exists when an existing-feature
match was detected) regardless of whether auto-respond was enabled when
triage ran. Previously the endpoint used a crude action→status map that
lost this nuance.
"""

from app.models.idea import Idea, IdeaStatus, SourceType
from conftest import auth_headers


def _make_idea(db_session, product_id: int, **overrides) -> Idea:
    idea = Idea(
        title=overrides.get("title", "Test idea"),
        what_description=overrides.get("what_description", "what"),
        why_description=overrides.get("why_description", "why"),
        use_case_description=overrides.get("use_case_description", "use"),
        product_id=product_id,
        source_type=overrides.get("source_type", SourceType.CUSTOMER_SUBMISSION),
        status=overrides.get("status", IdeaStatus.NEEDS_REVIEW),
        is_active=False,
        triage_recommendation=overrides.get("triage_recommendation"),
        triage_confidence=overrides.get("triage_confidence"),
        triage_reasoning=overrides.get("triage_reasoning"),
        competitive_context=overrides.get("competitive_context"),
        submitter_id=overrides.get("submitter_id"),
    )
    db_session.add(idea)
    db_session.commit()
    db_session.refresh(idea)
    return idea


class TestTriageRecommendationClassification:

    def test_reject_with_existing_feature_surfaces_as_feature_exists(
        self, client, po_user, test_product, db_session
    ):
        """Bug 2 PM-facing regression: a `reject` action with `existing_feature`
        in competitive_context must show as feature_exists, not not_appropriate."""
        idea = _make_idea(
            db_session,
            test_product.id,
            triage_recommendation="reject",
            triage_confidence=0.85,
            triage_reasoning="this overlaps existing functionality",
            competitive_context={
                "existing_feature": {
                    "feature_name": "Receipt Capture",
                    "feature_description": "Photo-to-expense scan",
                    "similarity_score": 0.92,
                    "source_url": None,
                },
            },
        )
        resp = client.get(
            f"/ideas/{idea.id}/triage-recommendation",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["recommended_status"] == "feature_exists"

    def test_ambiguous_reject_surfaces_as_needs_review_not_not_appropriate(
        self, client, po_user, test_product, db_session
    ):
        """Bug 2: ambiguous rejects without explicit off-topic signals must
        default to NEEDS_REVIEW (recommended_status=None), not not_appropriate.
        The previous map blindly converted every reject to not_appropriate."""
        idea = _make_idea(
            db_session,
            test_product.id,
            triage_recommendation="reject",
            triage_confidence=0.6,
            triage_reasoning="this submission is unclear",
        )
        resp = client.get(
            f"/ideas/{idea.id}/triage-recommendation",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["recommended_status"] is None  # NEEDS_REVIEW maps to None

    def test_explicit_off_topic_reject_surfaces_as_not_appropriate(
        self, client, po_user, test_product, db_session
    ):
        """NOT_APPROPRIATE is for explicit off-topic / offensive content."""
        idea = _make_idea(
            db_session,
            test_product.id,
            triage_recommendation="reject",
            triage_confidence=0.95,
            triage_reasoning="this is off-topic for an expense management product",
        )
        resp = client.get(
            f"/ideas/{idea.id}/triage-recommendation",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["recommended_status"] == "not_appropriate"

    def test_merge_action_surfaces_as_duplicate(
        self, client, po_user, test_product, db_session
    ):
        idea = _make_idea(
            db_session,
            test_product.id,
            triage_recommendation="merge",
            triage_confidence=0.9,
            triage_reasoning="duplicate of idea #5",
        )
        resp = client.get(
            f"/ideas/{idea.id}/triage-recommendation",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["recommended_status"] == "duplicate"

    def test_approve_action_surfaces_as_approved(
        self, client, po_user, test_product, db_session
    ):
        idea = _make_idea(
            db_session,
            test_product.id,
            triage_recommendation="approve",
            triage_confidence=0.95,
            triage_reasoning="clear and actionable",
        )
        resp = client.get(
            f"/ideas/{idea.id}/triage-recommendation",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["recommended_status"] == "approved"

    def test_existing_feature_with_na_source_url_returns_null(
        self, client, po_user, test_product, db_session
    ):
        """Historical rows persisted before the write-time sanitizer may have
        source_url='N/A' (the agent echoed the placeholder from the prompt).
        The recommendation API must scrub this at read time so the frontend
        doesn't render a relative URL like localhost:5173/N/A."""
        idea = _make_idea(
            db_session,
            test_product.id,
            triage_recommendation="reject",
            triage_confidence=0.85,
            triage_reasoning="overlaps existing functionality",
            competitive_context={
                "existing_feature": {
                    "feature_name": "X",
                    "feature_description": "...",
                    "similarity_score": 0.91,
                    "source_url": "N/A",
                },
            },
        )
        resp = client.get(
            f"/ideas/{idea.id}/triage-recommendation",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        existing_feature = body.get("source_summary", {}).get("existing_feature")
        assert existing_feature is not None
        assert existing_feature["source_url"] is None
        # Other fields preserved.
        assert existing_feature["feature_name"] == "X"

    def test_existing_feature_with_valid_url_passes_through(
        self, client, po_user, test_product, db_session
    ):
        idea = _make_idea(
            db_session,
            test_product.id,
            triage_recommendation="reject",
            triage_confidence=0.95,
            triage_reasoning="overlaps existing functionality",
            competitive_context={
                "existing_feature": {
                    "feature_name": "Y",
                    "feature_description": "...",
                    "similarity_score": 0.92,
                    "source_url": "https://docs.example.com/feature-y",
                },
            },
        )
        resp = client.get(
            f"/ideas/{idea.id}/triage-recommendation",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        existing_feature = body["source_summary"]["existing_feature"]
        assert existing_feature["source_url"] == "https://docs.example.com/feature-y"
