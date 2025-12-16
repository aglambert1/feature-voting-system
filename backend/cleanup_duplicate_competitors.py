"""
Cleanup script to remove duplicate SessionCompetitor records.

Duplicates are identified as multiple SessionCompetitor records in the same session
with the same product_competitor_id (or same competitor_name if no product_competitor_id).

Keeps the oldest record and deletes the rest.
"""

import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.competitor_intelligence import SessionCompetitor
from sqlalchemy import func

def cleanup_duplicates():
    db = SessionLocal()

    try:
        # Get all sessions
        sessions = db.query(SessionCompetitor.session_id).distinct().all()

        total_deleted = 0

        for (session_id,) in sessions:
            # Get competitors for this session
            competitors = db.query(SessionCompetitor).filter(
                SessionCompetitor.session_id == session_id
            ).all()

            # Group by product_competitor_id or name
            seen = {}
            to_delete = []

            for comp in competitors:
                # Use product_competitor_id as key if available, otherwise use name
                key = comp.product_competitor_id if comp.product_competitor_id else f"name:{comp.competitor_name}"

                if key in seen:
                    # Duplicate found - mark for deletion (keep the first one seen)
                    to_delete.append(comp)
                    print(f"  Session {session_id}: Duplicate '{comp.competitor_name}' (ID: {comp.id}) will be deleted")
                else:
                    # First occurrence - keep it
                    seen[key] = comp

            if to_delete:
                print(f"Session {session_id}: Removing {len(to_delete)} duplicate(s)")
                for comp in to_delete:
                    db.delete(comp)
                total_deleted += len(to_delete)

        # Commit all deletions
        db.commit()

        print(f"\n✅ Cleanup complete! Deleted {total_deleted} duplicate SessionCompetitor records")

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🧹 Starting duplicate SessionCompetitor cleanup...")
    print()
    cleanup_duplicates()
