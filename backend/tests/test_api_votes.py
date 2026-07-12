"""
Tests for Votes API endpoints (Category 1B).

Covers upvoting, unvoting, and vote validation.
"""

import pytest
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.vote import Vote
from conftest import auth_headers


class TestVoting:

    def test_upvote_idea(self, client, voter_user, test_idea):
        resp = client.post(f"/ideas/{test_idea.id}/vote", json={
            "vote_value": 1
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Upvote cast"
        assert data["vote_counts"]["upvotes"] == 1
        assert data["vote_counts"]["user_vote"] == 1
        assert data["vote"]["vote_value"] == 1

    def test_unvote_removes_vote(self, client, voter_user, test_idea, db_session):
        # First vote
        vote = Vote(idea_id=test_idea.id, user_id=voter_user.id, vote_value=1)
        db_session.add(vote)
        db_session.commit()

        # Vote again to unvote
        resp = client.post(f"/ideas/{test_idea.id}/vote", json={
            "vote_value": 1
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Vote removed"
        assert data["vote_counts"]["upvotes"] == 0
        assert data["vote_counts"]["user_vote"] is None
        assert data["vote"] is None

    def test_vote_requires_auth(self, client, test_idea):
        resp = client.post(f"/ideas/{test_idea.id}/vote", json={
            "vote_value": 1
        })
        assert resp.status_code == 401

    def test_vote_idea_not_found(self, client, voter_user):
        resp = client.post("/ideas/99999/vote", json={
            "vote_value": 1
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 404

    def test_invalid_vote_value_rejected(self, client, voter_user, test_idea):
        resp = client.post(f"/ideas/{test_idea.id}/vote", json={
            "vote_value": -1
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 422  # Pydantic validator rejects

    def test_multiple_users_vote(self, client, voter_user, admin_user, db_session, test_product, test_idea):
        from app.models.competitor_intelligence import ProductPermission, ProductPermissionLevel
        perm = ProductPermission(
            product_id=test_product.id,
            user_id=admin_user.id,
            permission_level=ProductPermissionLevel.VIEW,
            granted_by_user_id=admin_user.id,
        )
        db_session.add(perm)
        db_session.commit()
        client.post(f"/ideas/{test_idea.id}/vote", json={
            "vote_value": 1
        }, headers=auth_headers(voter_user))
        resp = client.post(f"/ideas/{test_idea.id}/vote", json={
            "vote_value": 1
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp.json()["vote_counts"]["upvotes"] == 2

    def test_vote_rejected_on_imported_idea(self, client, voter_user, test_product, voter_product_access, db_session):
        imported_idea = Idea(
            title="Imported Idea",
            what_description="Synced from an external idea board",
            why_description="Because it was requested there",
            use_case_description="Used via the external system",
            product_id=test_product.id,
            source_type=SourceType.EXTERNAL_SUBMISSION,
            external_source="canny",
            external_id="CANNY-101",
            status=IdeaStatus.ACCEPTED,
            is_active=True,
        )
        db_session.add(imported_idea)
        db_session.commit()
        db_session.refresh(imported_idea)

        resp = client.post(f"/ideas/{imported_idea.id}/vote", json={
            "vote_value": 1
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Imported ideas are voted on in their source system."
