"""
Migration script to generate and store embeddings for existing ideas.

This script backfills embeddings for ideas that were created before
the semantic search feature was implemented. It can be run multiple
times safely (uses INSERT OR REPLACE for idempotency).

Usage:
    cd backend
    python migrate_embeddings.py

Prerequisites:
    - voyageai installed (pip install voyageai)
    - VOYAGE_API_KEY set in .env
    - sqlite-vec extension loaded
    - Database with existing ideas

Process:
    1. Calls Voyage AI API to generate embeddings (voyage-3.5-lite, 1024 dimensions)
    2. Fetches all active ideas from database
    3. Generates embeddings for each idea (title + what + why)
    4. Stores embeddings in vec_ideas virtual table
    5. Commits in batches for performance

Safety:
    - Uses INSERT OR REPLACE (idempotent - safe to re-run)
    - Continues on individual errors (one failure doesn't stop migration)
    - Batched commits every 10 ideas
    - Progress reporting
"""

from sqlalchemy import text
from app.database import SessionLocal
from app.models.idea import Idea, IdeaStatus
from app.services.embedding_service import generate_embedding


def migrate_embeddings():
    """
    Generate embeddings for all existing active ideas.

    This function:
    - Creates vec_ideas virtual table if not exists
    - Fetches all active ideas
    - Generates embeddings using Voyage AI API
    - Stores embeddings in database
    - Reports progress and statistics
    """
    db = SessionLocal()

    try:
        # Ensure vec_ideas table exists
        print("Checking vec_ideas virtual table...")
        db.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_ideas
            USING vec0(
                idea_id INTEGER PRIMARY KEY,
                embedding FLOAT[1024]
            )
        """))
        db.commit()
        print("✓ vec_ideas table ready\n")

        # Get all active ideas
        print("Fetching active ideas from database...")
        ideas = db.query(Idea).filter(Idea.status == IdeaStatus.ACTIVE).all()
        total_ideas = len(ideas)
        print(f"✓ Found {total_ideas} active ideas to process\n")

        if total_ideas == 0:
            print("No ideas to migrate. Exiting.")
            return

        # Process each idea
        print("Generating and storing embeddings...\n")
        success_count = 0
        error_count = 0
        batch_size = 10

        for i, idea in enumerate(ideas, 1):
            try:
                # Combine text (same logic as submission endpoint)
                # title + what + why (exclude use_case for brevity)
                combined_text = f"{idea.title}. {idea.what_description} {idea.why_description}"

                # Generate embedding via Voyage AI API
                embedding = generate_embedding(combined_text, input_type="document")

                # Store embedding (INSERT OR REPLACE for idempotency)
                db.execute(
                    text("INSERT OR REPLACE INTO vec_ideas(idea_id, embedding) VALUES (:id, :emb)"),
                    {"id": idea.id, "emb": embedding}
                )

                success_count += 1

                # Progress reporting
                if i % batch_size == 0:
                    db.commit()
                    print(f"  Processed {i}/{total_ideas} ideas ({success_count} successful, {error_count} errors)")

            except Exception as e:
                error_count += 1
                print(f"  ✗ Error processing idea {idea.id} ('{idea.title}'): {e}")
                continue

        # Final commit
        db.commit()
        print(f"\n{'='*60}")
        print(f"✓ Migration complete!")
        print(f"  Total ideas: {total_ideas}")
        print(f"  Successfully embedded: {success_count}")
        print(f"  Errors: {error_count}")
        print(f"  Success rate: {success_count/total_ideas*100:.1f}%")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"✗ Migration failed: {e}")
        print(f"{'='*60}\n")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Embedding Migration Script")
    print("="*60 + "\n")

    try:
        migrate_embeddings()
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        exit(1)
