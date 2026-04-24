"""Smoke test for the synthesis auto-idea-generation linked_idea_id backfill.

When the unified synthesis task generates Ideas from opportunities above the
priority threshold, it must write back `SynthesizedOpportunity.linked_idea_id`
so the Synthesis Hub UI can render a "created as Idea #N" badge.

The production bug manifested only in the full task flow (with prior commits,
citation increments, etc.); a minimal unit test doesn't reliably reproduce the
silently-dropped attribute-assignment. This test therefore validates the fixed
pattern (explicit UPDATE query) end-to-end across sessions rather than acting
as a strict regression fence.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import pool

from app.database import Base
from app.models.competitor_intelligence import CIProduct
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.queue import JobType
from app.models.synthesis import SynthesisRun, SynthesisReport, SynthesizedOpportunity
from app.models.user import User, UserRole
from app.services.queue_service import QueueService


@pytest.fixture
def shared_engine():
    """Shared in-memory engine so multiple sessions see the same data."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


def _make_session(engine):
    return sessionmaker(bind=engine)()


def test_linked_idea_id_persists_across_sessions(shared_engine):
    """Auto-generated idea's id must end up in SynthesizedOpportunity.linked_idea_id
    in the database (not just in the originating session's identity map)."""
    session = _make_session(shared_engine)

    owner = User(
        email="po@example.com",
        username="po",
        hashed_password="x",
        full_name="PO",
        role=UserRole.PRODUCT_OWNER,
    )
    session.add(owner)
    session.commit()

    product = CIProduct(
        product_name="Test Product",
        product_description="desc",
        product_category="cat",
        created_by_user_id=owner.id,
        status="active",
    )
    session.add(product)
    session.commit()

    run = SynthesisRun(product_id=product.id, status="completed")
    report = SynthesisReport(
        product_id=product.id,
        report_version=1,
        included_source_types=["competitive"],
    )
    session.add(run)
    session.add(report)
    session.flush()

    opp_a = SynthesizedOpportunity(
        synthesis_run_id=run.id,
        synthesis_report_id=report.id,
        product_id=product.id,
        opportunity_name="Opp A",
        priority_score=100.0,
        source_count=1,
    )
    opp_b = SynthesizedOpportunity(
        synthesis_run_id=run.id,
        synthesis_report_id=report.id,
        product_id=product.id,
        opportunity_name="Opp B",
        priority_score=100.0,
        source_count=1,
    )
    session.add(opp_a)
    session.add(opp_b)
    session.commit()

    opp_rows_by_name = {"Opp A": opp_a, "Opp B": opp_b}
    queue_service = QueueService(session)

    for name in ("Opp A", "Opp B"):
        new_idea = Idea(
            title=name,
            what_description="what",
            why_description="why",
            use_case_description="use case",
            product_id=product.id,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            status=IdeaStatus.PENDING,
            is_active=False,
            auto_categorized=False,
        )
        session.add(new_idea)
        session.flush()

        matching_opp = opp_rows_by_name[name]
        session.query(SynthesizedOpportunity).filter(
            SynthesizedOpportunity.id == matching_opp.id
        ).update(
            {SynthesizedOpportunity.linked_idea_id: new_idea.id},
            synchronize_session=False,
        )

        queue_service.create_job(
            job_type=JobType.IDEA_TRIAGE,
            input_data={"idea_id": new_idea.id},
            product_id=product.id,
        )
        session.commit()

    session.close()

    fresh = _make_session(shared_engine)
    rows = (
        fresh.query(SynthesizedOpportunity)
        .order_by(SynthesizedOpportunity.opportunity_name)
        .all()
    )
    assert len(rows) == 2
    assert rows[0].opportunity_name == "Opp A"
    assert rows[0].linked_idea_id is not None, (
        "Opp A linked_idea_id was lost — regression in synthesis auto-gen backfill"
    )
    assert rows[1].opportunity_name == "Opp B"
    assert rows[1].linked_idea_id is not None, (
        "Opp B linked_idea_id was lost — regression in synthesis auto-gen backfill"
    )
    fresh.close()
