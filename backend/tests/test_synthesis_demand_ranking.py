"""Tests for _gather_customer_ideas — synthesis demand ranking over board votes
(internal Vote rows) and external_vote_count metadata from imported ideas.
The two are kept separate in the returned shape (board_votes/external_votes/
external_source) and never summed — they're different, non-comparable
populations. A combined value is used only internally to rank/cut the top 50."""

import pytest

from app.models.competitor_intelligence import CIProduct
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.user import User, UserRole
from app.models.vote import Vote
from app.queue.synthesis_tasks import _gather_customer_ideas


@pytest.fixture
def po(db_session):
    user = User(
        email="rank-po@example.com", username="rankpo",
        hashed_password="x", full_name="Rank PO", role=UserRole.PRODUCT_OWNER,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def product(db_session, po):
    p = CIProduct(
        product_name="Rank Product", product_description="D",
        created_by_user_id=po.id, status="active",
    )
    db_session.add(p)
    db_session.commit()
    return p


def _accepted_idea(db_session, product, po, title, source_metadata=None,
                   source_type=SourceType.CUSTOMER_SUBMISSION, external_source=None):
    idea = Idea(
        title=title, what_description="d", why_description="w",
        use_case_description="u", product_id=product.id, submitter_id=po.id,
        source_type=source_type, source_metadata=source_metadata,
        external_source=external_source,
        status=IdeaStatus.ACCEPTED, is_active=True,
    )
    db_session.add(idea)
    db_session.commit()
    return idea


class TestGatherCustomerIdeas:
    def test_external_votes_outrank_internal_in_ranking(self, db_session, product, po):
        internal = _accepted_idea(db_session, product, po, "Internal favorite")
        for i in range(3):
            voter = User(
                email=f"v{i}@example.com", username=f"v{i}",
                hashed_password="x", full_name=f"V{i}", role=UserRole.VOTER,
            )
            db_session.add(voter)
            db_session.flush()
            db_session.add(Vote(idea_id=internal.id, user_id=voter.id, vote_value=1))
        imported = _accepted_idea(
            db_session, product, po, "Imported heavyweight",
            source_metadata={"external_vote_count": 40, "external_status": "open"},
            source_type=SourceType.EXTERNAL_SUBMISSION,
            external_source="canny",
        )
        db_session.commit()

        ideas = _gather_customer_ideas(db_session, product.id)
        # Ranking (top-50 cut) still uses a combined key internally, so the
        # heavier imported idea sorts first — but the returned shape never
        # exposes a summed count.
        assert [i["title"] for i in ideas] == ["Imported heavyweight", "Internal favorite"]

        imported_result = ideas[0]
        assert imported_result["board_votes"] == 0
        assert imported_result["external_votes"] == 40
        assert imported_result["external_source"] == "canny"

        internal_result = ideas[1]
        assert internal_result["board_votes"] == 3
        assert internal_result["external_votes"] == 0
        assert internal_result["external_source"] is None

    def test_no_votes_anywhere_ranks_zero(self, db_session, product, po):
        _accepted_idea(db_session, product, po, "Quiet idea")
        ideas = _gather_customer_ideas(db_session, product.id)
        assert ideas[0]["board_votes"] == 0
        assert ideas[0]["external_votes"] == 0

    def test_board_and_external_votes_kept_separate_not_summed(self, db_session, product, po):
        idea = _accepted_idea(
            db_session, product, po, "Both worlds",
            source_metadata={"external_vote_count": 5},
            source_type=SourceType.EXTERNAL_SUBMISSION,
            external_source="canny",
        )
        voter = User(
            email="both@example.com", username="both",
            hashed_password="x", full_name="B", role=UserRole.VOTER,
        )
        db_session.add(voter)
        db_session.flush()
        db_session.add(Vote(idea_id=idea.id, user_id=voter.id, vote_value=1))
        db_session.commit()

        ideas = _gather_customer_ideas(db_session, product.id)
        assert ideas[0]["board_votes"] == 1
        assert ideas[0]["external_votes"] == 5
        assert ideas[0]["external_source"] == "canny"
        # No summed field should be exposed in the returned dict.
        assert "vote_count" not in ideas[0]
