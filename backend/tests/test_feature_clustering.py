"""
Unit tests for Feature Clustering Service.

Tests the clustering algorithm, intensity calculation, and cluster management.
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User, UserRole
from app.models.competitor_intelligence import (
    CIProduct, ProductCompetitor, ProductCompetitorFeature
)
from app.models.competitive_agent import (
    FeatureCluster, FeatureClusterMember, CompetitiveAgentConfig
)
from app.services.feature_clustering_service import (
    FeatureClusteringService, ClusterInfo, ClusteringResult
)


@pytest.fixture(scope="function")
def db_session():
    """Create a temporary database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    # Create sqlite-vec virtual table for testing
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_competitor_features
            USING vec0(
                feature_id INTEGER PRIMARY KEY,
                embedding FLOAT[384]
            )
        """))
        conn.commit()

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashed123",
        full_name="Test User",
        role=UserRole.ADMIN
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_product(db_session, test_user):
    """Create a test product."""
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Test Product",
        product_description="A test product for clustering tests"
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_product_with_config(db_session, test_user):
    """Create a test product with agent config."""
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Configured Product",
        product_description="A test product with agent config"
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    config = CompetitiveAgentConfig(
        product_id=product.id,
        intensity_similarity_threshold=0.80,
        intensity_idea_threshold=2,
        enabled=True
    )
    db_session.add(config)
    db_session.commit()

    return product


@pytest.fixture
def test_competitors(db_session, test_product):
    """Create test competitors."""
    competitors = []
    for i in range(4):
        competitor = ProductCompetitor(
            product_id=test_product.id,
            competitor_name=f"Competitor {chr(65 + i)}",  # A, B, C, D
            competitor_url=f"https://competitor-{chr(97 + i)}.com",
            status="active"
        )
        db_session.add(competitor)
        competitors.append(competitor)

    db_session.commit()
    for c in competitors:
        db_session.refresh(c)

    return competitors


@pytest.fixture
def test_features(db_session, test_competitors):
    """Create test features for competitors."""
    features = []

    # Features for Competitor A
    features.append(ProductCompetitorFeature(
        product_competitor_id=test_competitors[0].id,
        feature_name="AI-Powered Search",
        feature_description="Search using artificial intelligence",
        feature_category="search",
        status="active"
    ))
    features.append(ProductCompetitorFeature(
        product_competitor_id=test_competitors[0].id,
        feature_name="Real-time Collaboration",
        feature_description="Live editing with team members",
        feature_category="collaboration",
        status="active"
    ))

    # Features for Competitor B - similar to A
    features.append(ProductCompetitorFeature(
        product_competitor_id=test_competitors[1].id,
        feature_name="Smart AI Search",
        feature_description="Intelligent search with AI",
        feature_category="search",
        status="active"
    ))
    features.append(ProductCompetitorFeature(
        product_competitor_id=test_competitors[1].id,
        feature_name="Collaborative Editing",
        feature_description="Work together in real-time",
        feature_category="collaboration",
        status="active"
    ))

    # Features for Competitor C - some overlap
    features.append(ProductCompetitorFeature(
        product_competitor_id=test_competitors[2].id,
        feature_name="AI Search Engine",
        feature_description="AI-based search functionality",
        feature_category="search",
        status="active"
    ))
    features.append(ProductCompetitorFeature(
        product_competitor_id=test_competitors[2].id,
        feature_name="Export to PDF",
        feature_description="Export documents to PDF format",
        feature_category="export",
        status="active"
    ))

    # Features for Competitor D - unique
    features.append(ProductCompetitorFeature(
        product_competitor_id=test_competitors[3].id,
        feature_name="Dark Mode",
        feature_description="Dark theme for the interface",
        feature_category="ui",
        status="active"
    ))

    for f in features:
        db_session.add(f)

    db_session.commit()
    for f in features:
        db_session.refresh(f)

    return features


class TestFeatureClusteringService:
    """Tests for FeatureClusteringService."""

    def test_init(self, db_session):
        """Test service initialization."""
        service = FeatureClusteringService(db_session)
        assert service.db == db_session
        assert service._model is None  # Lazy loaded

    def test_distance_to_similarity(self, db_session):
        """Test cosine distance to similarity conversion."""
        service = FeatureClusteringService(db_session)

        # Distance 0 = similarity 1
        assert service._distance_to_similarity(0.0) == 1.0

        # Distance 2 = similarity 0 (maximum cosine distance)
        assert service._distance_to_similarity(2.0) == 0.0

        # Distance 1 = similarity 0.5
        assert service._distance_to_similarity(1.0) == 0.5

    def test_similarity_to_distance(self, db_session):
        """Test similarity to cosine distance conversion."""
        service = FeatureClusteringService(db_session)

        # Similarity 1 = distance 0
        assert service._similarity_to_distance(1.0) == 0.0

        # Similarity 0 = distance 2
        assert service._similarity_to_distance(0.0) == 2.0

        # Similarity 0.5 = distance 1
        assert service._similarity_to_distance(0.5) == 1.0

    def test_generate_cluster_name_basic(self, db_session):
        """Test cluster name generation from feature names."""
        service = FeatureClusteringService(db_session)

        feature_names = [
            "AI-Powered Search",
            "Smart AI Search",
            "AI Search Engine"
        ]

        name = service._generate_cluster_name(feature_names)

        # Should contain "AI" and "Search" as most common words
        assert "Search" in name or "search" in name.lower()

    def test_generate_cluster_name_empty(self, db_session):
        """Test cluster name generation with empty input."""
        service = FeatureClusteringService(db_session)

        name = service._generate_cluster_name([])
        assert name == "Unnamed Cluster"

    def test_generate_cluster_name_max_length(self, db_session):
        """Test cluster name respects max length."""
        service = FeatureClusteringService(db_session)

        feature_names = [
            "Very Long Feature Name With Many Words That Should Be Truncated",
            "Another Very Long Feature Name With Many Different Words"
        ]

        name = service._generate_cluster_name(feature_names, max_length=20)
        assert len(name) <= 20

    def test_generate_cluster_description(self, db_session):
        """Test cluster description generation."""
        service = FeatureClusteringService(db_session)

        feature_names = ["AI Search", "Smart Search"]
        feature_descriptions = [
            "Search using AI technology",
            "Intelligent search functionality"
        ]
        competitor_names = {"Competitor A", "Competitor B"}

        description = service._generate_cluster_description(
            feature_names, feature_descriptions, competitor_names
        )

        assert "Competitor A" in description or "Competitor B" in description
        assert "Found in:" in description

    def test_generate_cluster_description_many_competitors(self, db_session):
        """Test cluster description truncates many competitors."""
        service = FeatureClusteringService(db_session)

        feature_names = ["Feature"]
        feature_descriptions = ["A feature"]
        competitor_names = {f"Competitor {i}" for i in range(10)}

        description = service._generate_cluster_description(
            feature_names, feature_descriptions, competitor_names
        )

        assert "and 5 more" in description

    def test_cluster_features_insufficient_data(self, db_session, test_product):
        """Test clustering with insufficient features."""
        service = FeatureClusteringService(db_session)

        # No features - should return early
        result = service.cluster_features(test_product.id)

        assert result.clusters_created == 0
        assert result.features_clustered == 0

    def test_get_clusters_by_intensity_empty(self, db_session, test_product):
        """Test getting clusters when none exist."""
        service = FeatureClusteringService(db_session)

        clusters = service.get_clusters_by_intensity(test_product.id)
        assert clusters == []

    def test_get_clusters_by_intensity_with_filter(self, db_session, test_product):
        """Test getting clusters with intensity filter."""
        service = FeatureClusteringService(db_session)

        # Create some test clusters
        cluster1 = FeatureCluster(
            product_id=test_product.id,
            cluster_name="High Intensity",
            cluster_description="Many competitors",
            competitor_count=5,
            feature_count=10
        )
        cluster2 = FeatureCluster(
            product_id=test_product.id,
            cluster_name="Low Intensity",
            cluster_description="Few competitors",
            competitor_count=2,
            feature_count=3
        )
        db_session.add_all([cluster1, cluster2])
        db_session.commit()

        # Get only high intensity (>=3)
        clusters = service.get_clusters_by_intensity(test_product.id, min_intensity=3)

        assert len(clusters) == 1
        assert clusters[0]['cluster_name'] == "High Intensity"

    def test_get_high_intensity_clusters(self, db_session, test_product_with_config):
        """Test getting high intensity clusters using config threshold."""
        service = FeatureClusteringService(db_session)

        # Config sets threshold to 2
        cluster1 = FeatureCluster(
            product_id=test_product_with_config.id,
            cluster_name="High Intensity",
            competitor_count=3,
            feature_count=5,
            idea_generated=False
        )
        cluster2 = FeatureCluster(
            product_id=test_product_with_config.id,
            cluster_name="Low Intensity",
            competitor_count=1,
            feature_count=2,
            idea_generated=False
        )
        cluster3 = FeatureCluster(
            product_id=test_product_with_config.id,
            cluster_name="Already Processed",
            competitor_count=4,
            feature_count=8,
            idea_generated=True  # Should be excluded
        )
        db_session.add_all([cluster1, cluster2, cluster3])
        db_session.commit()

        clusters = service.get_high_intensity_clusters(test_product_with_config.id)

        assert len(clusters) == 1
        assert clusters[0].cluster_name == "High Intensity"

    def test_get_high_intensity_clusters_with_override(self, db_session, test_product):
        """Test getting high intensity clusters with explicit threshold."""
        service = FeatureClusteringService(db_session)

        cluster1 = FeatureCluster(
            product_id=test_product.id,
            cluster_name="Medium",
            competitor_count=2,
            feature_count=4,
            idea_generated=False
        )
        cluster2 = FeatureCluster(
            product_id=test_product.id,
            cluster_name="Low",
            competitor_count=1,
            feature_count=2,
            idea_generated=False
        )
        db_session.add_all([cluster1, cluster2])
        db_session.commit()

        # Override to threshold=2
        clusters = service.get_high_intensity_clusters(test_product.id, threshold=2)

        assert len(clusters) == 1
        assert clusters[0].cluster_name == "Medium"

    def test_mark_cluster_idea_generated(self, db_session, test_product):
        """Test marking a cluster as having generated an idea."""
        service = FeatureClusteringService(db_session)

        cluster = FeatureCluster(
            product_id=test_product.id,
            cluster_name="Test Cluster",
            competitor_count=3,
            feature_count=5,
            idea_generated=False
        )
        db_session.add(cluster)
        db_session.commit()

        service.mark_cluster_idea_generated(cluster.id, idea_id=42)

        db_session.refresh(cluster)
        assert cluster.idea_generated is True
        assert cluster.generated_idea_id == 42

    def test_mark_cluster_idea_generated_nonexistent(self, db_session):
        """Test marking nonexistent cluster doesn't raise."""
        service = FeatureClusteringService(db_session)

        # Should not raise, just do nothing
        service.mark_cluster_idea_generated(cluster_id=99999, idea_id=1)

    def test_get_cluster_feature_ids(self, db_session, test_product, test_features):
        """Test getting feature IDs from a cluster."""
        service = FeatureClusteringService(db_session)

        cluster = FeatureCluster(
            product_id=test_product.id,
            cluster_name="Test Cluster",
            competitor_count=2,
            feature_count=3
        )
        db_session.add(cluster)
        db_session.commit()

        # Add some members
        for feature in test_features[:3]:
            member = FeatureClusterMember(
                cluster_id=cluster.id,
                feature_id=feature.id,
                similarity_score=0.85
            )
            db_session.add(member)
        db_session.commit()

        feature_ids = service.get_cluster_feature_ids(cluster.id)

        assert len(feature_ids) == 3
        assert all(f.id in feature_ids for f in test_features[:3])

    def test_recalculate_cluster_intensity(self, db_session, test_product, test_competitors, test_features):
        """Test recalculating cluster intensity."""
        service = FeatureClusteringService(db_session)

        cluster = FeatureCluster(
            product_id=test_product.id,
            cluster_name="Test Cluster",
            competitor_count=0,  # Initially wrong
            feature_count=0
        )
        db_session.add(cluster)
        db_session.commit()

        # Add features from different competitors
        # test_features[0] and [1] are from Competitor A
        # test_features[2] and [3] are from Competitor B
        for feature in test_features[:4]:
            member = FeatureClusterMember(
                cluster_id=cluster.id,
                feature_id=feature.id,
                similarity_score=0.90
            )
            db_session.add(member)
        db_session.commit()

        new_count = service.recalculate_cluster_intensity(cluster.id)

        assert new_count == 2  # Two unique competitors (A and B)

        db_session.refresh(cluster)
        assert cluster.competitor_count == 2
        assert cluster.feature_count == 4


class TestClusterInfo:
    """Tests for ClusterInfo dataclass."""

    def test_cluster_info_creation(self):
        """Test creating ClusterInfo."""
        info = ClusterInfo(
            feature_ids=[1, 2, 3],
            competitor_ids={10, 20},
            competitor_names={"Comp A", "Comp B"},
            centroid=[0.1, 0.2, 0.3],
            feature_names=["Feature 1", "Feature 2"],
            feature_descriptions=["Desc 1", "Desc 2"]
        )

        assert len(info.feature_ids) == 3
        assert len(info.competitor_ids) == 2
        assert len(info.competitor_names) == 2


class TestClusteringResult:
    """Tests for ClusteringResult dataclass."""

    def test_clustering_result_creation(self):
        """Test creating ClusteringResult."""
        result = ClusteringResult(
            clusters_created=5,
            clusters_updated=2,
            features_clustered=50,
            high_intensity_clusters=3,
            execution_time_ms=150
        )

        assert result.clusters_created == 5
        assert result.clusters_updated == 2
        assert result.features_clustered == 50
        assert result.high_intensity_clusters == 3
        assert result.execution_time_ms == 150


class TestClusteringWithMockedEmbeddings:
    """Tests that use mocked embeddings to test clustering logic."""

    @patch.object(FeatureClusteringService, 'get_features_with_embeddings')
    def test_cluster_features_creates_clusters(self, mock_get_features, db_session, test_product):
        """Test that clustering creates appropriate clusters."""
        service = FeatureClusteringService(db_session)

        # Mock embeddings - 3 groups of similar vectors
        # Group 1: AI Search (features 1, 2, 3)
        # Group 2: Collaboration (features 4, 5)
        # Group 3: Export (feature 6)
        features = [
            {'feature_id': 1, 'feature_name': 'AI Search', 'feature_description': 'AI search',
             'feature_category': 'search', 'competitor_id': 1, 'competitor_name': 'Comp A'},
            {'feature_id': 2, 'feature_name': 'Smart Search', 'feature_description': 'Smart search',
             'feature_category': 'search', 'competitor_id': 2, 'competitor_name': 'Comp B'},
            {'feature_id': 3, 'feature_name': 'AI Search Engine', 'feature_description': 'AI engine',
             'feature_category': 'search', 'competitor_id': 3, 'competitor_name': 'Comp C'},
            {'feature_id': 4, 'feature_name': 'Real-time Collab', 'feature_description': 'Collab',
             'feature_category': 'collab', 'competitor_id': 1, 'competitor_name': 'Comp A'},
            {'feature_id': 5, 'feature_name': 'Team Collaboration', 'feature_description': 'Team work',
             'feature_category': 'collab', 'competitor_id': 2, 'competitor_name': 'Comp B'},
            {'feature_id': 6, 'feature_name': 'Export to PDF', 'feature_description': 'PDF export',
             'feature_category': 'export', 'competitor_id': 3, 'competitor_name': 'Comp C'},
        ]

        # Create embeddings that will cluster correctly
        # Using simple vectors for testing
        np.random.seed(42)
        base_search = np.random.rand(384)
        base_collab = np.random.rand(384)
        base_export = np.random.rand(384)

        embeddings = np.array([
            base_search + np.random.rand(384) * 0.1,  # Similar to search
            base_search + np.random.rand(384) * 0.1,
            base_search + np.random.rand(384) * 0.1,
            base_collab + np.random.rand(384) * 0.1,  # Similar to collab
            base_collab + np.random.rand(384) * 0.1,
            base_export,  # Unique
        ])

        mock_get_features.return_value = (features, embeddings)

        result = service.cluster_features(test_product.id, similarity_threshold=0.7)

        assert result.clusters_created > 0
        assert result.features_clustered == 6

        # Verify clusters were created in DB
        clusters = db_session.query(FeatureCluster).filter(
            FeatureCluster.product_id == test_product.id
        ).all()
        assert len(clusters) > 0

    @patch.object(FeatureClusteringService, 'get_features_with_embeddings')
    def test_cluster_features_single_feature(self, mock_get_features, db_session, test_product):
        """Test clustering with single feature returns early."""
        service = FeatureClusteringService(db_session)

        features = [
            {'feature_id': 1, 'feature_name': 'Only Feature', 'feature_description': 'Desc',
             'feature_category': 'cat', 'competitor_id': 1, 'competitor_name': 'Comp A'}
        ]
        embeddings = np.random.rand(1, 384)

        mock_get_features.return_value = (features, embeddings)

        result = service.cluster_features(test_product.id)

        assert result.clusters_created == 0
        assert result.features_clustered == 1

    @patch.object(FeatureClusteringService, 'get_features_with_embeddings')
    def test_cluster_features_respects_threshold(self, mock_get_features, db_session, test_product):
        """Test that clustering respects similarity threshold."""
        service = FeatureClusteringService(db_session)

        features = [
            {'feature_id': i, 'feature_name': f'Feature {i}', 'feature_description': f'Desc {i}',
             'feature_category': 'cat', 'competitor_id': i, 'competitor_name': f'Comp {i}'}
            for i in range(5)
        ]

        # Create dissimilar embeddings
        np.random.seed(123)
        embeddings = np.random.rand(5, 384)

        mock_get_features.return_value = (features, embeddings)

        # High threshold should create more clusters (less merging)
        result_high = service.cluster_features(test_product.id, similarity_threshold=0.95)
        clusters_high = db_session.query(FeatureCluster).filter(
            FeatureCluster.product_id == test_product.id
        ).count()

        # Clear for next test
        db_session.query(FeatureClusterMember).delete()
        db_session.query(FeatureCluster).filter(
            FeatureCluster.product_id == test_product.id
        ).delete()
        db_session.commit()

        # Low threshold should create fewer clusters (more merging)
        result_low = service.cluster_features(test_product.id, similarity_threshold=0.3)
        clusters_low = db_session.query(FeatureCluster).filter(
            FeatureCluster.product_id == test_product.id
        ).count()

        # With dissimilar vectors, high threshold = more clusters
        assert clusters_high >= clusters_low


class TestGetClustersWithMembers:
    """Tests for getting clusters with member details."""

    def test_get_clusters_with_members(self, db_session, test_product, test_competitors, test_features):
        """Test getting clusters with member feature details."""
        service = FeatureClusteringService(db_session)

        cluster = FeatureCluster(
            product_id=test_product.id,
            cluster_name="Test Cluster",
            cluster_description="A test cluster",
            competitor_count=2,
            feature_count=2
        )
        db_session.add(cluster)
        db_session.commit()

        # Add members
        for feature in test_features[:2]:
            member = FeatureClusterMember(
                cluster_id=cluster.id,
                feature_id=feature.id,
                similarity_score=0.85
            )
            db_session.add(member)
        db_session.commit()

        clusters = service.get_clusters_by_intensity(
            test_product.id,
            min_intensity=1,
            include_members=True
        )

        assert len(clusters) == 1
        assert 'members' in clusters[0]
        assert len(clusters[0]['members']) == 2

        member = clusters[0]['members'][0]
        assert 'feature_id' in member
        assert 'feature_name' in member
        assert 'competitor_name' in member
        assert 'similarity_score' in member
