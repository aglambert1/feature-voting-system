"""
Vector service for database-agnostic embedding operations.

This service abstracts vector storage and search operations to work
with both SQLite (development) and PostgreSQL (production).
"""

from typing import List, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
import sqlite_vec


class VectorService:
    """Database-agnostic vector operations."""

    @staticmethod
    def is_postgres(db: Session) -> bool:
        """
        Check if using PostgreSQL database.

        Args:
            db: SQLAlchemy database session

        Returns:
            True if PostgreSQL, False if SQLite
        """
        return 'postgresql' in str(db.bind.url)

    @staticmethod
    def store_embedding(db: Session, idea_id: int, embedding: List[float]) -> None:
        """
        Store embedding for an idea (database-agnostic).

        Args:
            db: SQLAlchemy database session
            idea_id: ID of the idea
            embedding: Embedding vector (384 dimensions for all-MiniLM-L6-v2)

        Note:
            - PostgreSQL: Updates idea.embedding column directly
            - SQLite: Inserts into vec_ideas virtual table
        """
        if VectorService.is_postgres(db):
            # PostgreSQL: Update idea.embedding column
            db.execute(
                text("UPDATE ideas SET embedding = :emb WHERE id = :id"),
                {"id": idea_id, "emb": embedding}
            )
        else:
            # SQLite: Insert into vec_ideas virtual table
            # Serialize embedding for sqlite-vec
            serialized_emb = sqlite_vec.serialize_float32(embedding)
            db.execute(
                text("INSERT INTO vec_ideas(idea_id, embedding) VALUES (:id, :emb)"),
                {"id": idea_id, "emb": serialized_emb}
            )

    @staticmethod
    def find_similar(
        db: Session,
        query_embedding: List[float],
        product_id: int,
        limit: int = 5
    ) -> List[Tuple[int, str, str, float]]:
        """
        Find similar ideas using vector similarity search (database-agnostic).

        Args:
            db: SQLAlchemy database session
            query_embedding: Query embedding vector
            product_id: Filter by product ID
            limit: Maximum number of results to return

        Returns:
            List of tuples: (idea_id, title, what_description, distance)
            Distance is cosine distance (0=identical, 2=opposite)

        Note:
            - PostgreSQL: Uses pgvector <=> operator
            - SQLite: Uses vec_distance_cosine function
        """
        if VectorService.is_postgres(db):
            # PostgreSQL: Use pgvector <=> operator
            results = db.execute(text("""
                SELECT id, title, what_description,
                       embedding <=> :query_emb::vector as distance
                FROM ideas
                WHERE UPPER(status) = 'ACTIVE'
                  AND product_id = :product_id
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> :query_emb::vector
                LIMIT :limit
            """), {
                "query_emb": query_embedding,
                "product_id": product_id,
                "limit": limit
            })
        else:
            # SQLite: Use vec_distance_cosine function
            # Serialize query embedding for sqlite-vec
            serialized_query = sqlite_vec.serialize_float32(query_embedding)
            results = db.execute(text("""
                SELECT v.idea_id, i.title, i.what_description,
                       vec_distance_cosine(v.embedding, :query_emb) as distance
                FROM vec_ideas v
                JOIN ideas i ON v.idea_id = i.id
                WHERE UPPER(i.status) = 'ACTIVE'
                  AND i.product_id = :product_id
                ORDER BY distance ASC
                LIMIT :limit
            """), {
                "query_emb": serialized_query,
                "product_id": product_id,
                "limit": limit
            })

        return results.fetchall()
