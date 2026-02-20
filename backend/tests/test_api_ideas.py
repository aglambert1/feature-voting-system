"""
Tests for Ideas API endpoints (Category 1B).

Covers idea CRUD, listing with visibility rules, review workflow,
comments, and publish flow.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.user import UserRole
from app.models.competitor_intelligence import CIProduct
from tests.conftest import auth_headers


class TestCreateIdea:

    def test_create_idea_success(self, client, voter_user, test_product):
        resp = client.post("/ideas/", json={
            "title": "Add dark mode",
            "what_description": "Add a dark mode theme to the application",
            "why_description": "Reduces eye strain for users working at night",
            "use_case_description": "User toggles dark mode in settings to switch theme",
            "product_id": test_product.id,
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Add dark mode"
        assert data["status"] == "pending"
        assert data["vote_counts"]["upvotes"] == 0

    def test_create_idea_requires_auth(self, client, test_product):
        resp = client.post("/ideas/", json={
            "title": "Add dark mode",
            "what_description": "Add a dark mode theme to the application",
            "why_description": "Reduces eye strain for users working at night",
            "use_case_description": "User toggles dark mode in settings to switch theme",
            "product_id": test_product.id,
        })
        assert resp.status_code == 401

    def test_create_idea_short_title_rejected(self, client, voter_user, test_product):
        resp = client.post("/ideas/", json={
            "title": "Ab",
            "what_description": "A description of the feature",
            "why_description": "Because it is useful for everyone",
            "use_case_description": "User does this thing with the feature",
            "product_id": test_product.id,
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 422

    def test_create_idea_missing_product_id(self, client, voter_user):
        resp = client.post("/ideas/", json={
            "title": "Add dark mode",
            "what_description": "A description of the feature",
            "why_description": "Because it is useful for everyone",
            "use_case_description": "User does this thing with the feature",
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 422


class TestGetIdea:

    def test_get_idea_by_id(self, client, test_idea):
        resp = client.get(f"/ideas/{test_idea.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_idea.id
        assert data["title"] == "Test Idea"

    def test_get_idea_not_found(self, client):
        resp = client.get("/ideas/99999")
        assert resp.status_code == 404

    def test_get_idea_no_auth_required(self, client, test_idea):
        resp = client.get(f"/ideas/{test_idea.id}")
        assert resp.status_code == 200


class TestListIdeas:

    def test_list_ideas_returns_active(self, client, voter_user, test_idea):
        resp = client.get("/ideas/", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        titles = [i["title"] for i in data["ideas"]]
        assert "Test Idea" in titles

    def test_list_ideas_filter_by_product(self, client, voter_user, test_idea, test_product):
        resp = client.get(
            f"/ideas/?product_id={test_product.id}",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 200
        for idea in resp.json()["ideas"]:
            assert idea["product_id"] == test_product.id

    def test_list_ideas_nonexistent_product(self, client, voter_user):
        resp = client.get(
            "/ideas/?product_id=99999",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 404

    def test_list_ideas_admin_sees_all(self, client, admin_user, db_session, test_product):
        pending = Idea(
            title="Pending Idea",
            what_description="A pending feature idea",
            why_description="It would be useful for testing",
            use_case_description="Used in test scenarios to verify visibility",
            product_id=test_product.id,
            submitter_id=admin_user.id,
            source_type=SourceType.CUSTOMER_SUBMISSION,
            status=IdeaStatus.PENDING,
            is_active=False,
        )
        db_session.add(pending)
        db_session.commit()

        resp = client.get("/ideas/", headers=auth_headers(admin_user))
        titles = [i["title"] for i in resp.json()["ideas"]]
        assert "Pending Idea" in titles

    def test_list_ideas_voter_sees_own_pending(self, client, voter_user, db_session, test_product):
        pending = Idea(
            title="My Pending Idea",
            what_description="A feature I submitted that is pending",
            why_description="It would be useful for testing",
            use_case_description="Used in test scenarios to verify visibility",
            product_id=test_product.id,
            submitter_id=voter_user.id,
            source_type=SourceType.CUSTOMER_SUBMISSION,
            status=IdeaStatus.PENDING,
            is_active=False,
        )
        db_session.add(pending)
        db_session.commit()

        resp = client.get("/ideas/", headers=auth_headers(voter_user))
        titles = [i["title"] for i in resp.json()["ideas"]]
        assert "My Pending Idea" in titles


class TestIdeaReview:

    def test_review_approve(self, client, admin_user, db_session, test_product):
        idea = Idea(
            title="Reviewable Idea",
            what_description="A feature that needs review first",
            why_description="It needs approval before voting",
            use_case_description="Used in test scenarios to verify review flow",
            product_id=test_product.id,
            submitter_id=admin_user.id,
            source_type=SourceType.CUSTOMER_SUBMISSION,
            status=IdeaStatus.NEEDS_REVIEW,
            is_active=False,
        )
        db_session.add(idea)
        db_session.commit()
        db_session.refresh(idea)

        resp = client.post(f"/ideas/{idea.id}/review", json={
            "action": "approve",
            "notes": "Looks good"
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_review_reject(self, client, admin_user, db_session, test_product):
        idea = Idea(
            title="Rejectable Idea",
            what_description="A feature that should be rejected",
            why_description="It does not fit our roadmap direction",
            use_case_description="Used in test scenarios to verify rejection flow",
            product_id=test_product.id,
            submitter_id=admin_user.id,
            source_type=SourceType.CUSTOMER_SUBMISSION,
            status=IdeaStatus.NEEDS_REVIEW,
            is_active=False,
        )
        db_session.add(idea)
        db_session.commit()
        db_session.refresh(idea)

        resp = client.post(f"/ideas/{idea.id}/review", json={
            "action": "reject",
            "notes": "Not aligned with roadmap"
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_appropriate"

    def test_review_invalid_action(self, client, admin_user, test_idea):
        resp = client.post(f"/ideas/{test_idea.id}/review", json={
            "action": "invalid_action",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 400

    def test_review_not_found(self, client, admin_user):
        resp = client.post("/ideas/99999/review", json={
            "action": "approve",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 404


class TestPublishIdea:

    def test_publish_pending_idea(self, client, admin_user, db_session, test_product):
        idea = Idea(
            title="Publishable Idea",
            what_description="A feature that can be published for voting",
            why_description="It has been reviewed and approved",
            use_case_description="Used in test scenarios to verify publish flow",
            product_id=test_product.id,
            submitter_id=admin_user.id,
            source_type=SourceType.CUSTOMER_SUBMISSION,
            status=IdeaStatus.PENDING,
            is_active=False,
        )
        db_session.add(idea)
        db_session.commit()
        db_session.refresh(idea)

        resp = client.post(f"/ideas/{idea.id}/publish", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"
        assert resp.json()["is_active"] is True

    def test_publish_already_accepted_fails(self, client, admin_user, test_idea):
        resp = client.post(f"/ideas/{test_idea.id}/publish", headers=auth_headers(admin_user))
        assert resp.status_code == 400


class TestIdeaComments:

    def test_add_comment(self, client, voter_user, test_idea):
        resp = client.post(f"/ideas/{test_idea.id}/comments", json={
            "comment_text": "Great idea, I would use this!"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 200
        assert resp.json()["comment_text"] == "Great idea, I would use this!"
        assert resp.json()["username"] == "voter"

    def test_add_comment_requires_auth(self, client, test_idea):
        resp = client.post(f"/ideas/{test_idea.id}/comments", json={
            "comment_text": "No auth comment"
        })
        assert resp.status_code == 401

    def test_add_comment_not_found(self, client, voter_user):
        resp = client.post("/ideas/99999/comments", json={
            "comment_text": "Comment on missing idea"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 404

    def test_get_comments(self, client, voter_user, test_idea, db_session):
        from app.models.idea_comment import IdeaComment
        comment = IdeaComment(
            idea_id=test_idea.id,
            user_id=voter_user.id,
            comment_text="Existing comment",
            is_system_generated=False,
        )
        db_session.add(comment)
        db_session.commit()

        resp = client.get(
            f"/ideas/{test_idea.id}/comments",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert resp.json()[0]["comment_text"] == "Existing comment"


class TestIdeaDetail:

    def test_get_idea_detail(self, client, voter_user, test_idea):
        resp = client.get(
            f"/ideas/{test_idea.id}/detail",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_idea.id
        assert data["title"] == "Test Idea"
        assert "comments" in data
        assert "status_history" in data

    def test_get_idea_detail_not_found(self, client, voter_user):
        resp = client.get(
            "/ideas/99999/detail",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 404
