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
            embedding: Embedding vector (1024 dimensions for voyage-3.5-lite)

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

            # Delete any existing embedding first to make this idempotent
            # (allows re-processing ideas without duplicate key errors)
            db.execute(
                text("DELETE FROM vec_ideas WHERE idea_id = :id"),
                {"id": idea_id}
            )

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
            # Only show active ideas (is_active=true means accepted for voting)
            results = db.execute(text("""
                SELECT id, title, what_description,
                       embedding <=> CAST(:query_emb AS vector) as distance
                FROM ideas
                WHERE product_id = :product_id
                  AND embedding IS NOT NULL
                  AND is_active = true
                ORDER BY embedding <=> CAST(:query_emb AS vector)
                LIMIT :limit
            """), {
                "query_emb": query_embedding,
                "product_id": product_id,
                "limit": limit
            })
        else:
            # SQLite: Use vec_distance_cosine function
            # Serialize query embedding for sqlite-vec
            # Only show active ideas (is_active=1 means accepted for voting)
            serialized_query = sqlite_vec.serialize_float32(query_embedding)
            results = db.execute(text("""
                SELECT v.idea_id, i.title, i.what_description,
                       vec_distance_cosine(v.embedding, :query_emb) as distance
                FROM vec_ideas v
                JOIN ideas i ON v.idea_id = i.id
                WHERE i.product_id = :product_id
                  AND i.is_active = 1
                ORDER BY distance ASC
                LIMIT :limit
            """), {
                "query_emb": serialized_query,
                "product_id": product_id,
                "limit": limit
            })

        return results.fetchall()

    # ============================================================================
    # Product Embedding Methods
    # ============================================================================

    @staticmethod
    def store_product_embedding(
        db: Session,
        product_id: int,
        embedding: List[float],
        chunk_index: int = 0,
        chunk_text: str = None
    ) -> None:
        """
        Store embedding for a product description (database-agnostic).

        For large product descriptions (>4000 tokens), multiple chunks can be stored
        with different chunk_index values.

        Args:
            db: SQLAlchemy database session
            product_id: ID of the product
            embedding: Embedding vector (1024 dimensions for voyage-3.5-lite)
            chunk_index: Index of chunk (0 for single embedding)
            chunk_text: Text content of this chunk (optional, for reference)

        Note:
            - PostgreSQL: Updates ci_products.embedding column (single embedding only)
            - SQLite: Inserts into vec_products virtual table (supports chunks)
        """
        if VectorService.is_postgres(db):
            # PostgreSQL: Update product embedding column
            # For now, only support single embedding (chunk_index must be 0)
            if chunk_index == 0:
                db.execute(
                    text("UPDATE ci_products SET embedding = :emb WHERE id = :id"),
                    {"id": product_id, "emb": embedding}
                )
            # Note: Chunking for PostgreSQL would require separate chunks table
        else:
            # SQLite: Insert into vec_products virtual table + product_chunks metadata table
            # Supports multiple chunks per product
            serialized_emb = sqlite_vec.serialize_float32(embedding)

            # Delete existing chunk if replacing
            # First get the vec_rowid from product_chunks
            result = db.execute(
                text("SELECT vec_rowid FROM product_chunks WHERE product_id = :id AND chunk_index = :chunk_idx"),
                {"id": product_id, "chunk_idx": chunk_index}
            ).fetchone()

            if result:
                vec_rowid = result[0]
                # Delete from vec_products using rowid
                db.execute(
                    text("DELETE FROM vec_products WHERE rowid = :rowid"),
                    {"rowid": vec_rowid}
                )
                # Delete from product_chunks
                db.execute(
                    text("DELETE FROM product_chunks WHERE product_id = :id AND chunk_index = :chunk_idx"),
                    {"id": product_id, "chunk_idx": chunk_index}
                )

            # Insert new chunk into vec_products
            db.execute(
                text("INSERT INTO vec_products(embedding) VALUES (:emb)"),
                {"emb": serialized_emb}
            )

            # Get the rowid of the inserted embedding
            vec_rowid = db.execute(text("SELECT last_insert_rowid()")).fetchone()[0]

            # Insert metadata into product_chunks
            db.execute(
                text("""
                    INSERT INTO product_chunks(product_id, chunk_index, chunk_text, vec_rowid)
                    VALUES (:id, :chunk_idx, :text, :vec_rowid)
                """),
                {"id": product_id, "chunk_idx": chunk_index, "text": chunk_text, "vec_rowid": vec_rowid}
            )

    @staticmethod
    def find_similar_in_product(
        db: Session,
        query_embedding: List[float],
        product_id: int,
        threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        Search within a product's description for similar content.

        Args:
            db: SQLAlchemy database session
            query_embedding: Query embedding vector
            product_id: Product ID to search within
            threshold: Minimum similarity score (0-1, where 1 is identical)

        Returns:
            List of tuples: (chunk_text, distance)
            Distance is cosine distance (0=identical, 2=opposite)
            Results are filtered by threshold and sorted by similarity

        Note:
            - If product description is chunked, searches across all chunks
            - If not chunked, returns single result with overall similarity
        """
        # Convert threshold to distance (distance = 2 * (1 - similarity))
        max_distance = 2 * (1 - threshold)

        if VectorService.is_postgres(db):
            # PostgreSQL: Search product embedding
            results = db.execute(text("""
                SELECT COALESCE(product_description, '') as text,
                       embedding <=> CAST(:query_emb AS vector) as distance
                FROM ci_products
                WHERE id = :product_id
                  AND embedding IS NOT NULL
                  AND (embedding <=> CAST(:query_emb AS vector)) <= :max_distance
                ORDER BY embedding <=> CAST(:query_emb AS vector)
            """), {
                "query_emb": query_embedding,
                "product_id": product_id,
                "max_distance": max_distance
            })
        else:
            # SQLite: Search all chunks for this product using JOIN
            serialized_query = sqlite_vec.serialize_float32(query_embedding)
            results = db.execute(text("""
                SELECT COALESCE(pc.chunk_text, '') as text,
                       vec_distance_cosine(vp.embedding, :query_emb) as distance
                FROM product_chunks pc
                JOIN vec_products vp ON pc.vec_rowid = vp.rowid
                WHERE pc.product_id = :product_id
                  AND vec_distance_cosine(vp.embedding, :query_emb) <= :max_distance
                ORDER BY distance ASC
            """), {
                "query_emb": serialized_query,
                "product_id": product_id,
                "max_distance": max_distance
            })

        return results.fetchall()

    @staticmethod
    def delete_product_embeddings(db: Session, product_id: int) -> None:
        """
        Delete all embeddings for a product.

        Useful when product is deleted or re-analyzed.

        Args:
            db: SQLAlchemy database session
            product_id: Product ID
        """
        if VectorService.is_postgres(db):
            # PostgreSQL: Set embedding to NULL
            db.execute(
                text("UPDATE ci_products SET embedding = NULL WHERE id = :id"),
                {"id": product_id}
            )
        else:
            # SQLite: Delete all chunks from vec_products and product_chunks
            # First get all vec_rowids for this product
            vec_rowids = db.execute(
                text("SELECT vec_rowid FROM product_chunks WHERE product_id = :id"),
                {"id": product_id}
            ).fetchall()

            # Delete from vec_products
            for (vec_rowid,) in vec_rowids:
                db.execute(
                    text("DELETE FROM vec_products WHERE rowid = :rowid"),
                    {"rowid": vec_rowid}
                )

            # Delete from product_chunks
            db.execute(
                text("DELETE FROM product_chunks WHERE product_id = :id"),
                {"id": product_id}
            )

    # ============================================================================
    # Competitor Feature Embedding Methods
    # ============================================================================

    @staticmethod
    def store_competitor_feature_embedding(
        db: Session,
        feature_id: int,
        embedding: List[float]
    ) -> None:
        """
        Store embedding for a competitor feature.

        Args:
            db: SQLAlchemy database session
            feature_id: ID of the ProductCompetitorFeature
            embedding: Embedding vector (1024 dimensions for voyage-3.5-lite)
        """
        if VectorService.is_postgres(db):
            # PostgreSQL: Update feature embedding column
            db.execute(
                text("UPDATE product_competitor_features SET embedding = :emb WHERE id = :id"),
                {"id": feature_id, "emb": embedding}
            )
        else:
            # SQLite: Insert into vec_competitor_features virtual table
            serialized_emb = sqlite_vec.serialize_float32(embedding)

            # Delete existing embedding if any
            db.execute(
                text("DELETE FROM vec_competitor_features WHERE feature_id = :id"),
                {"id": feature_id}
            )

            # Insert new embedding
            db.execute(
                text("INSERT INTO vec_competitor_features(feature_id, embedding) VALUES (:id, :emb)"),
                {"id": feature_id, "emb": serialized_emb}
            )

    @staticmethod
    def find_similar_competitor_features(
        db: Session,
        query_embedding: List[float],
        product_id: int,
        limit: int = 10,
        threshold: float = 0.5
    ) -> List[Tuple[int, str, str, int, str, float]]:
        """
        Find similar competitor features using vector similarity search.

        Args:
            db: SQLAlchemy database session
            query_embedding: Query embedding vector
            product_id: Filter by product ID (via ProductCompetitor)
            limit: Maximum number of results to return
            threshold: Minimum similarity score (0-1, where 1 is identical)

        Returns:
            List of tuples: (feature_id, feature_name, feature_description,
                           competitor_id, competitor_name, distance)
            Distance is cosine distance (0=identical, 2=opposite)
        """
        # Convert threshold to distance (distance = 2 * (1 - similarity))
        max_distance = 2 * (1 - threshold)

        if VectorService.is_postgres(db):
            # PostgreSQL: Use pgvector <=> operator
            results = db.execute(text("""
                SELECT pcf.id, pcf.feature_name, pcf.feature_description,
                       pc.id as competitor_id, pc.competitor_name,
                       pcf.embedding <=> CAST(:query_emb AS vector) as distance
                FROM product_competitor_features pcf
                JOIN product_competitors pc ON pcf.product_competitor_id = pc.id
                WHERE pc.product_id = :product_id
                  AND pc.status = 'active'
                  AND pcf.status = 'active'
                  AND pcf.embedding IS NOT NULL
                  AND (pcf.embedding <=> CAST(:query_emb AS vector)) <= :max_distance
                ORDER BY pcf.embedding <=> CAST(:query_emb AS vector)
                LIMIT :limit
            """), {
                "query_emb": query_embedding,
                "product_id": product_id,
                "max_distance": max_distance,
                "limit": limit
            })
        else:
            # SQLite: Use vec_distance_cosine function
            serialized_query = sqlite_vec.serialize_float32(query_embedding)
            results = db.execute(text("""
                SELECT pcf.id, pcf.feature_name, pcf.feature_description,
                       pc.id as competitor_id, pc.competitor_name,
                       vec_distance_cosine(v.embedding, :query_emb) as distance
                FROM vec_competitor_features v
                JOIN product_competitor_features pcf ON v.feature_id = pcf.id
                JOIN product_competitors pc ON pcf.product_competitor_id = pc.id
                WHERE pc.product_id = :product_id
                  AND pc.status = 'active'
                  AND pcf.status = 'active'
                  AND vec_distance_cosine(v.embedding, :query_emb) <= :max_distance
                ORDER BY distance ASC
                LIMIT :limit
            """), {
                "query_emb": serialized_query,
                "product_id": product_id,
                "max_distance": max_distance,
                "limit": limit
            })

        return results.fetchall()

    # ============================================================================
    # Product Feature Embedding Methods (Own Product's Features)
    # ============================================================================

    @staticmethod
    def store_product_feature_embedding(
        db: Session,
        feature_id: int,
        embedding: List[float]
    ) -> None:
        """
        Store embedding for a product's own feature (ProductFeature).

        Args:
            db: SQLAlchemy database session
            feature_id: ID of the ProductFeature
            embedding: Embedding vector (1024 dimensions for voyage-3.5-lite)
        """
        if VectorService.is_postgres(db):
            # PostgreSQL: Update feature embedding column
            db.execute(
                text("UPDATE product_features SET embedding = :emb WHERE id = :id"),
                {"id": feature_id, "emb": embedding}
            )
        else:
            # SQLite: Insert into vec_product_features virtual table
            serialized_emb = sqlite_vec.serialize_float32(embedding)

            # Delete existing embedding if any (idempotent)
            db.execute(
                text("DELETE FROM vec_product_features WHERE feature_id = :id"),
                {"id": feature_id}
            )

            # Insert new embedding
            db.execute(
                text("INSERT INTO vec_product_features(feature_id, embedding) VALUES (:id, :emb)"),
                {"id": feature_id, "emb": serialized_emb}
            )

    @staticmethod
    def find_similar_product_features(
        db: Session,
        query_embedding: List[float],
        product_id: int,
        limit: int = 5,
        threshold: float = 0.85
    ) -> List[Tuple[int, str, str, str, float]]:
        """
        Find product's own features that match a query using vector similarity.

        Used to detect when an idea describes functionality that already exists
        in the product.

        Args:
            db: SQLAlchemy database session
            query_embedding: Query embedding vector
            product_id: Product ID to search within
            limit: Maximum number of results to return
            threshold: Minimum similarity score (0-1, default 0.85 for feature detection)

        Returns:
            List of tuples: (feature_id, feature_name, feature_description,
                           source_url, distance)
            Distance is cosine distance (0=identical, 2=opposite)
        """
        # Convert threshold to distance (distance = 2 * (1 - similarity))
        max_distance = 2 * (1 - threshold)

        if VectorService.is_postgres(db):
            # PostgreSQL: Use pgvector <=> operator
            results = db.execute(text("""
                SELECT pf.id, pf.feature_name, pf.feature_description,
                       pf.source_url,
                       pf.embedding <=> CAST(:query_emb AS vector) as distance
                FROM product_features pf
                WHERE pf.product_id = :product_id
                  AND pf.status = 'active'
                  AND pf.embedding IS NOT NULL
                  AND (pf.embedding <=> CAST(:query_emb AS vector)) <= :max_distance
                ORDER BY pf.embedding <=> CAST(:query_emb AS vector)
                LIMIT :limit
            """), {
                "query_emb": query_embedding,
                "product_id": product_id,
                "max_distance": max_distance,
                "limit": limit
            })
        else:
            # SQLite: Use vec_distance_cosine function
            serialized_query = sqlite_vec.serialize_float32(query_embedding)
            results = db.execute(text("""
                SELECT pf.id, pf.feature_name, pf.feature_description,
                       pf.source_url,
                       vec_distance_cosine(v.embedding, :query_emb) as distance
                FROM vec_product_features v
                JOIN product_features pf ON v.feature_id = pf.id
                WHERE pf.product_id = :product_id
                  AND pf.status = 'active'
                  AND vec_distance_cosine(v.embedding, :query_emb) <= :max_distance
                ORDER BY distance ASC
                LIMIT :limit
            """), {
                "query_emb": serialized_query,
                "product_id": product_id,
                "max_distance": max_distance,
                "limit": limit
            })

        return results.fetchall()

    # ============================================================================
    # Bulk Delete Methods (for product removal)
    # ============================================================================

    @staticmethod
    def delete_all_product_embeddings(db: Session, product_id: int) -> dict:
        """
        Delete ALL embeddings associated with a product.

        Covers: vec_products, product_chunks, vec_competitor_features,
        vec_product_features, and vec_ideas.

        Returns:
            Dict with counts of deleted embeddings per table
        """
        counts = {}

        # 1. Product description embeddings
        if VectorService.is_postgres(db):
            db.execute(
                text("UPDATE ci_products SET embedding = NULL WHERE id = :id"),
                {"id": product_id}
            )
            counts["product_chunks"] = 1
        else:
            vec_rowids = db.execute(
                text("SELECT vec_rowid FROM product_chunks WHERE product_id = :id"),
                {"id": product_id}
            ).fetchall()
            for (vec_rowid,) in vec_rowids:
                db.execute(
                    text("DELETE FROM vec_products WHERE rowid = :rowid"),
                    {"rowid": vec_rowid}
                )
            result = db.execute(
                text("DELETE FROM product_chunks WHERE product_id = :id"),
                {"id": product_id}
            )
            counts["product_chunks"] = result.rowcount

        # 2. Competitor feature embeddings
        if VectorService.is_postgres(db):
            result = db.execute(text("""
                UPDATE product_competitor_features SET embedding = NULL
                WHERE product_competitor_id IN (
                    SELECT id FROM product_competitors WHERE product_id = :product_id
                )
            """), {"product_id": product_id})
            counts["competitor_feature_embeddings"] = result.rowcount
        else:
            result = db.execute(text("""
                DELETE FROM vec_competitor_features WHERE feature_id IN (
                    SELECT pcf.id FROM product_competitor_features pcf
                    JOIN product_competitors pc ON pcf.product_competitor_id = pc.id
                    WHERE pc.product_id = :product_id
                )
            """), {"product_id": product_id})
            counts["competitor_feature_embeddings"] = result.rowcount

        # 3. Product's own feature embeddings
        if VectorService.is_postgres(db):
            result = db.execute(text("""
                UPDATE product_features SET embedding = NULL
                WHERE product_id = :product_id
            """), {"product_id": product_id})
            counts["product_feature_embeddings"] = result.rowcount
        else:
            result = db.execute(text("""
                DELETE FROM vec_product_features WHERE feature_id IN (
                    SELECT id FROM product_features WHERE product_id = :product_id
                )
            """), {"product_id": product_id})
            counts["product_feature_embeddings"] = result.rowcount

        # 4. Idea embeddings
        if VectorService.is_postgres(db):
            result = db.execute(text("""
                UPDATE ideas SET embedding = NULL
                WHERE product_id = :product_id
            """), {"product_id": product_id})
            counts["idea_embeddings"] = result.rowcount
        else:
            result = db.execute(text("""
                DELETE FROM vec_ideas WHERE idea_id IN (
                    SELECT id FROM ideas WHERE product_id = :product_id
                )
            """), {"product_id": product_id})
            counts["idea_embeddings"] = result.rowcount

        return counts

    @staticmethod
    def count_product_embeddings(db: Session, product_id: int) -> dict:
        """
        Count all embeddings associated with a product (for dry-run preview).

        Returns:
            Dict with counts per embedding type
        """
        counts = {}

        if VectorService.is_postgres(db):
            r = db.execute(
                text("SELECT COUNT(*) FROM ci_products WHERE id = :id AND embedding IS NOT NULL"),
                {"id": product_id}
            ).scalar()
            counts["product_chunks"] = r or 0
        else:
            counts["product_chunks"] = db.execute(
                text("SELECT COUNT(*) FROM product_chunks WHERE product_id = :id"),
                {"id": product_id}
            ).scalar() or 0

        if VectorService.is_postgres(db):
            counts["competitor_feature_embeddings"] = db.execute(text("""
                SELECT COUNT(*) FROM product_competitor_features
                WHERE embedding IS NOT NULL
                  AND product_competitor_id IN (
                    SELECT id FROM product_competitors WHERE product_id = :product_id
                )
            """), {"product_id": product_id}).scalar() or 0
        else:
            counts["competitor_feature_embeddings"] = db.execute(text("""
                SELECT COUNT(*) FROM vec_competitor_features WHERE feature_id IN (
                    SELECT pcf.id FROM product_competitor_features pcf
                    JOIN product_competitors pc ON pcf.product_competitor_id = pc.id
                    WHERE pc.product_id = :product_id
                )
            """), {"product_id": product_id}).scalar() or 0

        if VectorService.is_postgres(db):
            counts["product_feature_embeddings"] = db.execute(text("""
                SELECT COUNT(*) FROM product_features
                WHERE embedding IS NOT NULL AND product_id = :product_id
            """), {"product_id": product_id}).scalar() or 0
        else:
            counts["product_feature_embeddings"] = db.execute(text("""
                SELECT COUNT(*) FROM vec_product_features WHERE feature_id IN (
                    SELECT id FROM product_features WHERE product_id = :product_id
                )
            """), {"product_id": product_id}).scalar() or 0

        if VectorService.is_postgres(db):
            counts["idea_embeddings"] = db.execute(text("""
                SELECT COUNT(*) FROM ideas
                WHERE embedding IS NOT NULL AND product_id = :product_id
            """), {"product_id": product_id}).scalar() or 0
        else:
            counts["idea_embeddings"] = db.execute(text("""
                SELECT COUNT(*) FROM vec_ideas WHERE idea_id IN (
                    SELECT id FROM ideas WHERE product_id = :product_id
                )
            """), {"product_id": product_id}).scalar() or 0

        return counts
