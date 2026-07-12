"""
Tests for Ideas API endpoints (Category 1B).

Covers idea CRUD, listing with visibility rules, review workflow,
comments, and publish flow.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.user import UserRole
from app.models.competitor_intelligence import CIProduct, ProductPermission, ProductPermissionLevel
from conftest import auth_headers


def _grant_admin_access(db_session, test_product, admin_user, level=ProductPermissionLevel.EDIT):
    """Grant admin_user explicit permission on test_product."""
    perm = ProductPermission(
        product_id=test_product.id,
        user_id=admin_user.id,
        permission_level=level,
        granted_by_user_id=admin_user.id,
    )
    db_session.add(perm)
    db_session.commit()


def _imported_idea(db_session, test_product, submitter_id, title="Imported Idea"):
    """Create an EXTERNAL_SUBMISSION idea with external provenance metadata."""
    idea = Idea(
        title=title,
        what_description="Synced from an external idea board",
        why_description="Because it was requested there",
        use_case_description="Used via the external system",
        product_id=test_product.id,
        submitter_id=submitter_id,
        source_type=SourceType.EXTERNAL_SUBMISSION,
        external_source="canny",
        external_id="CANNY-101",
        source_metadata={
            "external_vote_count": 55,
            "external_status": "open",
            "external_url": "https://example.canny.io/p/canny-101",
        },
        status=IdeaStatus.ACCEPTED,
        is_active=True,
    )
    db_session.add(idea)
    db_session.commit()
    db_session.refresh(idea)
    return idea


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

    def test_get_idea_by_id(self, client, voter_user, test_idea):
        resp = client.get(f"/ideas/{test_idea.id}", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_idea.id
        assert data["title"] == "Test Idea"

    def test_get_idea_not_found(self, client, voter_user):
        resp = client.get("/ideas/99999", headers=auth_headers(voter_user))
        assert resp.status_code == 404

    def test_get_idea_requires_auth(self, client, test_idea):
        resp = client.get(f"/ideas/{test_idea.id}")
        assert resp.status_code == 401

    def test_get_idea_created_here_has_no_external_provenance(self, client, voter_user, test_idea):
        resp = client.get(f"/ideas/{test_idea.id}", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "customer_submission"
        assert data["external_source"] is None
        assert data["external_vote_count"] is None

    def test_get_idea_imported_exposes_external_provenance(self, client, voter_user, test_product, voter_product_access, db_session):
        imported = _imported_idea(db_session, test_product, voter_user.id)
        resp = client.get(f"/ideas/{imported.id}", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "external_submission"
        assert data["external_source"] == "canny"
        assert data["external_vote_count"] == 55
        assert data["external_status"] == "open"
        assert data["external_url"] == "https://example.canny.io/p/canny-101"


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

    def test_list_ideas_admin_with_access(self, client, admin_user, db_session, test_product):
        _grant_admin_access(db_session, test_product, admin_user)
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

    def test_list_ideas_includes_external_provenance(self, client, voter_user, test_product, voter_product_access, test_idea, db_session):
        _imported_idea(db_session, test_product, voter_user.id, title="List Imported Idea")

        resp = client.get("/ideas/", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        imported = next(i for i in resp.json()["ideas"] if i["title"] == "List Imported Idea")
        assert imported["source_type"] == "external_submission"
        assert imported["external_source"] == "canny"
        assert imported["external_vote_count"] == 55

        created_here = next(i for i in resp.json()["ideas"] if i["title"] == "Test Idea")
        assert created_here["source_type"] == "customer_submission"
        assert created_here["external_source"] is None


class TestIdeaReview:

    def test_review_approve(self, client, admin_user, db_session, test_product):
        _grant_admin_access(db_session, test_product, admin_user)
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
        _grant_admin_access(db_session, test_product, admin_user)
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

    def test_review_invalid_action(self, client, admin_user, db_session, test_product, test_idea):
        _grant_admin_access(db_session, test_product, admin_user)
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
        _grant_admin_access(db_session, test_product, admin_user)
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

    def test_publish_already_accepted_fails(self, client, admin_user, db_session, test_product, test_idea):
        _grant_admin_access(db_session, test_product, admin_user)
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

    def test_get_idea_detail_includes_vote_counts(self, client, voter_user, test_idea):
        """Regression: the detail endpoint must include vote_counts so the
        IdeaDetailPage can render a live count without a parallel call to
        /ideas/{id}. Previously it omitted vote_counts entirely and the
        frontend read a non-existent `upvotes` field that always evaluated
        to 0."""
        resp = client.get(
            f"/ideas/{test_idea.id}/detail",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "vote_counts" in data
        assert isinstance(data["vote_counts"], dict)
        assert "upvotes" in data["vote_counts"]
        assert "total_votes" in data["vote_counts"]
        assert "user_vote" in data

    def test_get_idea_detail_not_found(self, client, voter_user):
        resp = client.get(
            "/ideas/99999/detail",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 404

    def test_get_idea_detail_includes_external_provenance(self, client, voter_user, test_product, voter_product_access, db_session):
        imported = _imported_idea(db_session, test_product, voter_user.id)
        resp = client.get(
            f"/ideas/{imported.id}/detail",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "external_submission"
        assert data["external_source"] == "canny"
        assert data["external_vote_count"] == 55
        assert data["external_status"] == "open"


class TestTriageRecommendationSourceSummary:
    """Regression: source_summary previously only counted internal Vote rows
    (via len(votes)), so a PO opening the response modal for an imported idea
    with e.g. 55 votes on Canny saw "0 votes" — the same provenance-blindness
    bug as the board view, in the screen where a PM actually acts on the idea."""

    def test_source_summary_separates_board_and_external_votes(self, client, admin_user, db_session, test_product):
        _grant_admin_access(db_session, test_product, admin_user)
        imported = _imported_idea(db_session, test_product, admin_user.id)

        resp = client.get(
            f"/ideas/{imported.id}/triage-recommendation",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
        source_summary = resp.json()["source_summary"]
        assert source_summary["board_votes"] == 0
        assert source_summary["external_source"] == "canny"
        assert source_summary["external_vote_count"] == 55
        assert "vote_count" not in source_summary

    def test_source_summary_created_here_idea_has_no_external_fields(self, client, admin_user, db_session, test_product, test_idea):
        _grant_admin_access(db_session, test_product, admin_user)

        resp = client.get(
            f"/ideas/{test_idea.id}/triage-recommendation",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
        source_summary = resp.json()["source_summary"]
        assert source_summary["board_votes"] == 0
        assert source_summary["external_source"] is None
        assert source_summary["external_vote_count"] is None
