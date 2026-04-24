#!/usr/bin/env python3
"""
Backfill SynthesizedOpportunity.linked_idea_id for historical reports.

Prior to the fix in tasks.py, the auto-idea-generation loop silently failed
to persist linked_idea_id on the opportunity row after creating an Idea.
This script retroactively populates linked_idea_id by matching each
opportunity to an Idea with the same title + same synthesis_report_id +
source_type=COMPETITOR_AUTOMATED.

Usage:
    cd backend
    ./venv/bin/python scripts/backfill_synthesis_linked_ideas.py --dry-run
    ./venv/bin/python scripts/backfill_synthesis_linked_ideas.py --yes
    ./venv/bin/python scripts/backfill_synthesis_linked_ideas.py --product-id 1 --yes

    --product-id  Limit to a single product (optional)
    --dry-run     Preview matches without writing
    --yes, -y     Skip confirmation prompt
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.idea import Idea, SourceType
from app.models.synthesis import SynthesizedOpportunity


def find_candidates(db, product_id=None):
    """Return list of (opp, idea) pairs needing backfill."""
    q = db.query(SynthesizedOpportunity).filter(
        SynthesizedOpportunity.linked_idea_id.is_(None)
    )
    if product_id is not None:
        q = q.filter(SynthesizedOpportunity.product_id == product_id)
    opps = q.all()

    pairs = []
    for opp in opps:
        idea = (
            db.query(Idea)
            .filter(
                Idea.product_id == opp.product_id,
                Idea.title == opp.opportunity_name[:255],
                Idea.source_type == SourceType.COMPETITOR_AUTOMATED,
            )
            .first()
        )
        if not idea:
            continue
        md = idea.source_metadata or {}
        if md.get("synthesis_report_id") != opp.synthesis_report_id:
            continue
        pairs.append((opp, idea))
    return pairs


def main():
    parser = argparse.ArgumentParser(
        description="Backfill linked_idea_id on historical SynthesizedOpportunity rows"
    )
    parser.add_argument("--product-id", type=int, help="Restrict to one product")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        pairs = find_candidates(db, args.product_id)
        if not pairs:
            print("No opportunities need backfill.")
            return 0

        print(f"Found {len(pairs)} opportunities to backfill:")
        for opp, idea in pairs:
            print(
                f"  opp.id={opp.id} report={opp.synthesis_report_id} "
                f"name={opp.opportunity_name[:60]!r} -> idea.id={idea.id}"
            )

        if args.dry_run:
            print("\n[dry-run] No changes written.")
            return 0

        if not args.yes:
            resp = input(f"\nApply {len(pairs)} updates? [y/N] ").strip().lower()
            if resp != "y":
                print("Aborted.")
                return 1

        for opp, idea in pairs:
            db.query(SynthesizedOpportunity).filter(
                SynthesizedOpportunity.id == opp.id
            ).update(
                {SynthesizedOpportunity.linked_idea_id: idea.id},
                synchronize_session=False,
            )
        db.commit()
        print(f"Backfilled {len(pairs)} rows.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
