"""
Feature Clustering Service for competitive intensity analysis.

This service groups semantically similar features across competitors
to calculate competitive intensity and trigger idea generation.

V2 Architecture: Uses CompetitorFunctionalReport.functional_comparison
as the source of competitor features, instead of ProductCompetitorFeature.

The clustering algorithm:
1. Extracts features from CompetitorFunctionalReport.functional_comparison
2. Generates embeddings on-the-fly for semantic clustering
3. Uses agglomerative clustering with cosine distance
4. Creates/updates FeatureCluster records with intensity metrics
5. Identifies high-intensity clusters for idea generation

Phase: Agent-Centric Competitive Intelligence Restructuring
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist, squareform

from app.models.competitive_agent import FeatureCluster, FeatureClusterMember
from app.models.competitor_intelligence import ProductCompetitor, CIProduct
from app.models.competitive_reports import CompetitorFunctionalReport
from app.services.similarity_detector import get_embedding_model


@dataclass
class FeatureInfo:
    """Information about a feature from functional report."""
    feature_key: str  # Unique identifier: "{competitor_id}_{feature_name_hash}"
    competitor_id: int
    competitor_name: str
    feature_name: str
    feature_description: str
    feature_category: str
    mapping_status: str  # Gap, Parity, Advantage, Differentiator
    report_id: int


@dataclass
class ClusterInfo:
    """Information about a computed cluster before persisting."""
    feature_keys: List[str]  # Changed from feature_ids to feature_keys
    competitor_ids: Set[int]
    competitor_names: Set[str]
    centroid: List[float]
    feature_names: List[str]
    feature_descriptions: List[str]
    features: List[FeatureInfo]  # Full feature info for creating members


@dataclass
class ClusteringResult:
    """Result of a clustering operation."""
    clusters_created: int
    clusters_updated: int
    features_clustered: int
    high_intensity_clusters: int  # Clusters meeting threshold
    execution_time_ms: int


class FeatureClusteringService:
    """
    Service for clustering competitor features and calculating competitive intensity.

    Competitive intensity is measured by how many unique competitors have a
    similar feature. High-intensity features (many competitors) suggest
    table-stakes capabilities that should be prioritized.
    """

    def __init__(self, db: Session):
        self.db = db
        self._model = None

    @property
    def embedding_model(self):
        """Get the embedding model (lazy-loaded)."""
        if self._model is None:
            self._model = get_embedding_model()
        return self._model

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        embedding = self.embedding_model.encode(text, show_progress_bar=False)
        return embedding.tolist()

    def _distance_to_similarity(self, distance: float) -> float:
        """Convert cosine distance to similarity score."""
        return 1.0 - (distance / 2.0)

    def _similarity_to_distance(self, similarity: float) -> float:
        """Convert similarity score to cosine distance."""
        return 2.0 * (1.0 - similarity)

    def get_features_with_embeddings(
        self,
        product_id: int
    ) -> Tuple[List[FeatureInfo], np.ndarray]:
        """
        Extract features from CompetitorFunctionalReport and generate embeddings.

        V2 Architecture: Reads from functional_comparison JSON arrays in
        CompetitorFunctionalReport instead of ProductCompetitorFeature table.

        Args:
            product_id: Product ID to get features for

        Returns:
            Tuple of (feature_info_list, embeddings_matrix)
            - feature_info_list: List of FeatureInfo objects
            - embeddings_matrix: numpy array of shape (n_features, embedding_dim)
        """
        import hashlib

        # Get all functional reports for this product
        reports = self.db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_id == product_id
        ).all()

        if not reports:
            return [], np.array([])

        features = []
        embeddings = []

        for report in reports:
            # Get competitor info
            competitor = self.db.query(ProductCompetitor).filter(
                ProductCompetitor.id == report.product_competitor_id
            ).first()

            if not competitor:
                continue

            # Extract features from functional_comparison
            functional_comparison = report.functional_comparison or []

            for feature_data in functional_comparison:
                feature_name = feature_data.get('competitor_feature_name', '')
                feature_description = feature_data.get('functional_description', '')
                feature_category = feature_data.get('feature_category', '')
                mapping_status = feature_data.get('mapping_status', '')

                # Only include features where competitor has the feature
                # Gap = competitor has it, we don't
                # Parity = both have it
                # Differentiator = unique workflow they offer
                if mapping_status not in ['Gap', 'Parity', 'Differentiator']:
                    continue

                if not feature_name:
                    continue

                # Generate unique key for this feature
                feature_key = f"{competitor.id}_{hashlib.md5(feature_name.encode()).hexdigest()[:8]}"

                # Generate embedding for the feature
                feature_text = f"{feature_name}\n{feature_description}"
                embedding = self.generate_embedding(feature_text)

                features.append(FeatureInfo(
                    feature_key=feature_key,
                    competitor_id=competitor.id,
                    competitor_name=competitor.competitor_name,
                    feature_name=feature_name,
                    feature_description=feature_description,
                    feature_category=feature_category,
                    mapping_status=mapping_status,
                    report_id=report.id
                ))
                embeddings.append(embedding)

        return features, np.array(embeddings) if embeddings else np.array([])

    def cluster_features(
        self,
        product_id: int,
        similarity_threshold: float = 0.75,
        min_cluster_size: int = 1
    ) -> ClusteringResult:
        """
        Cluster all competitor features for a product using agglomerative clustering.

        Algorithm:
        1. Get all features with embeddings
        2. Compute pairwise cosine distances
        3. Apply agglomerative clustering with given threshold
        4. Create/update FeatureCluster records
        5. Calculate intensity (unique competitors per cluster)

        Args:
            product_id: Product to cluster features for
            similarity_threshold: Minimum similarity to be in same cluster (0-1)
            min_cluster_size: Minimum features to form a cluster

        Returns:
            ClusteringResult with statistics
        """
        start_time = datetime.utcnow()

        # Get features and embeddings
        features, embeddings = self.get_features_with_embeddings(product_id)

        if len(features) < 2:
            # Not enough features to cluster
            return ClusteringResult(
                clusters_created=0,
                clusters_updated=0,
                features_clustered=len(features),
                high_intensity_clusters=0,
                execution_time_ms=0
            )

        # Compute pairwise cosine distances
        # Note: pdist expects distance (not similarity), so we convert threshold
        distance_threshold = self._similarity_to_distance(similarity_threshold)

        # Calculate condensed distance matrix using cosine distance
        distances = pdist(embeddings, metric='cosine')

        # Apply agglomerative clustering
        # We use 'average' linkage which works well for semantic clustering
        linkage_matrix = linkage(distances, method='average', metric='cosine')

        # Cut the dendrogram at the threshold distance
        cluster_labels = fcluster(linkage_matrix, t=distance_threshold, criterion='distance')

        # Group features by cluster
        cluster_groups: Dict[int, ClusterInfo] = {}

        for idx, label in enumerate(cluster_labels):
            feature = features[idx]  # This is now a FeatureInfo object

            if label not in cluster_groups:
                cluster_groups[label] = ClusterInfo(
                    feature_keys=[],
                    competitor_ids=set(),
                    competitor_names=set(),
                    centroid=[],
                    feature_names=[],
                    feature_descriptions=[],
                    features=[]
                )

            cluster = cluster_groups[label]
            cluster.feature_keys.append(feature.feature_key)
            cluster.competitor_ids.add(feature.competitor_id)
            cluster.competitor_names.add(feature.competitor_name)
            cluster.feature_names.append(feature.feature_name)
            cluster.feature_descriptions.append(feature.feature_description)
            cluster.features.append(feature)

        # Calculate centroids for each cluster
        for label, cluster in cluster_groups.items():
            cluster_indices = [i for i, l in enumerate(cluster_labels) if l == label]
            cluster_embeddings = embeddings[cluster_indices]
            centroid = np.mean(cluster_embeddings, axis=0)
            cluster.centroid = centroid.tolist()

        # Filter out clusters below minimum size
        valid_clusters = {
            label: cluster for label, cluster in cluster_groups.items()
            if len(cluster.feature_keys) >= min_cluster_size
        }

        # Get config for intensity threshold
        config = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        intensity_threshold = 3  # Default
        if config and config.competitive_agent_config:
            intensity_threshold = config.competitive_agent_config.intensity_idea_threshold

        # Clear existing clusters for this product
        self.db.query(FeatureClusterMember).filter(
            FeatureClusterMember.cluster_id.in_(
                self.db.query(FeatureCluster.id).filter(
                    FeatureCluster.product_id == product_id
                )
            )
        ).delete(synchronize_session=False)

        self.db.query(FeatureCluster).filter(
            FeatureCluster.product_id == product_id
        ).delete(synchronize_session=False)

        # Create new clusters
        clusters_created = 0
        high_intensity_count = 0

        for label, cluster_info in valid_clusters.items():
            # Generate cluster name from most common words in feature names
            cluster_name = self._generate_cluster_name(cluster_info.feature_names)
            cluster_description = self._generate_cluster_description(
                cluster_info.feature_names,
                cluster_info.feature_descriptions,
                cluster_info.competitor_names
            )

            # Create cluster record
            feature_cluster = FeatureCluster(
                product_id=product_id,
                cluster_name=cluster_name,
                cluster_description=cluster_description,
                centroid_embedding=cluster_info.centroid,
                competitor_count=len(cluster_info.competitor_ids),
                feature_count=len(cluster_info.feature_keys),
                idea_generated=False,
                generated_idea_id=None
            )
            self.db.add(feature_cluster)
            self.db.flush()  # Get the ID

            # Track high-intensity clusters
            if len(cluster_info.competitor_ids) >= intensity_threshold:
                high_intensity_count += 1

            # Create cluster members from V2 feature data
            for feature_info in cluster_info.features:
                # Calculate similarity to centroid
                feature_idx = next(
                    i for i, f in enumerate(features)
                    if f.feature_key == feature_info.feature_key
                )
                feature_embedding = embeddings[feature_idx]
                centroid_array = np.array(cluster_info.centroid)
                similarity = 1.0 - np.dot(feature_embedding, centroid_array) / (
                    np.linalg.norm(feature_embedding) * np.linalg.norm(centroid_array)
                )
                # Convert from cosine distance to similarity
                similarity = self._distance_to_similarity(similarity)

                # V2: Store feature data directly in the member record
                member = FeatureClusterMember(
                    cluster_id=feature_cluster.id,
                    feature_key=feature_info.feature_key,
                    competitor_id=feature_info.competitor_id,
                    feature_name=feature_info.feature_name,
                    feature_description=feature_info.feature_description,
                    feature_category=feature_info.feature_category,
                    mapping_status=feature_info.mapping_status,
                    source_report_id=feature_info.report_id,
                    similarity_score=float(similarity)
                )
                self.db.add(member)

            clusters_created += 1

        self.db.commit()

        end_time = datetime.utcnow()
        execution_time = int((end_time - start_time).total_seconds() * 1000)

        return ClusteringResult(
            clusters_created=clusters_created,
            clusters_updated=0,  # We replaced all clusters
            features_clustered=len(features),
            high_intensity_clusters=high_intensity_count,
            execution_time_ms=execution_time
        )

    def _generate_cluster_name(self, feature_names: List[str], max_length: int = 100) -> str:
        """
        Generate a representative name for a cluster based on feature names.

        Uses the most common meaningful words from feature names.
        """
        # Common stop words to filter out
        stop_words = {
            'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'that',
            'this', 'these', 'those', 'which', 'who', 'whom', 'what', 'when',
            'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
            'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'support',
            'management', 'feature', 'features', 'tool', 'tools', 'system'
        }

        # Count word frequency
        word_counts: Dict[str, int] = {}
        for name in feature_names:
            words = name.lower().split()
            for word in words:
                # Clean word of punctuation
                word = ''.join(c for c in word if c.isalnum())
                if word and word not in stop_words and len(word) > 2:
                    word_counts[word] = word_counts.get(word, 0) + 1

        if not word_counts:
            # Fallback to first feature name
            return feature_names[0][:max_length] if feature_names else "Unnamed Cluster"

        # Get top words
        sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
        top_words = [w[0].title() for w in sorted_words[:4]]

        name = ' '.join(top_words)
        return name[:max_length]

    def _generate_cluster_description(
        self,
        feature_names: List[str],
        feature_descriptions: List[str],
        competitor_names: Set[str]
    ) -> str:
        """
        Generate a description for a cluster.

        Summarizes what the cluster represents based on member features.
        """
        competitors_str = ', '.join(sorted(competitor_names)[:5])
        if len(competitor_names) > 5:
            competitors_str += f' and {len(competitor_names) - 5} more'

        # Use the longest/most descriptive feature description
        descriptions = [d for d in feature_descriptions if d]
        if descriptions:
            best_desc = max(descriptions, key=len)
            if len(best_desc) > 200:
                best_desc = best_desc[:197] + '...'
        else:
            best_desc = feature_names[0] if feature_names else ''

        return f"{best_desc} (Found in: {competitors_str})"

    def get_clusters_by_intensity(
        self,
        product_id: int,
        min_intensity: int = 1,
        include_members: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get clusters for a product, optionally filtered by minimum intensity.

        Args:
            product_id: Product to get clusters for
            min_intensity: Minimum competitor count to include
            include_members: Whether to include member features in response

        Returns:
            List of cluster info dicts sorted by intensity (highest first)
        """
        clusters = self.db.query(FeatureCluster).filter(
            FeatureCluster.product_id == product_id,
            FeatureCluster.competitor_count >= min_intensity
        ).order_by(FeatureCluster.competitor_count.desc()).all()

        result = []
        for cluster in clusters:
            cluster_dict = cluster.to_dict()

            if include_members:
                members = self.db.query(FeatureClusterMember).filter(
                    FeatureClusterMember.cluster_id == cluster.id
                ).all()

                member_info = []
                for member in members:
                    # V2: Feature data is stored directly in the member record
                    competitor = self.db.query(ProductCompetitor).filter(
                        ProductCompetitor.id == member.competitor_id
                    ).first()

                    member_info.append({
                        'feature_key': member.feature_key,
                        'feature_name': member.feature_name,
                        'feature_description': member.feature_description,
                        'feature_category': member.feature_category,
                        'mapping_status': member.mapping_status,
                        'competitor_id': member.competitor_id,
                        'competitor_name': competitor.competitor_name if competitor else None,
                        'similarity_score': member.similarity_score
                    })

                cluster_dict['members'] = member_info

            result.append(cluster_dict)

        return result

    def get_high_intensity_clusters(
        self,
        product_id: int,
        threshold: Optional[int] = None
    ) -> List[FeatureCluster]:
        """
        Get clusters that meet the intensity threshold for idea generation.

        Args:
            product_id: Product to check
            threshold: Override threshold (uses config if not provided)

        Returns:
            List of FeatureCluster objects meeting threshold
        """
        if threshold is None:
            # Get from product config
            from app.models.competitive_agent import CompetitiveAgentConfig
            config = self.db.query(CompetitiveAgentConfig).filter(
                CompetitiveAgentConfig.product_id == product_id
            ).first()
            threshold = config.intensity_idea_threshold if config else 3

        return self.db.query(FeatureCluster).filter(
            FeatureCluster.product_id == product_id,
            FeatureCluster.competitor_count >= threshold,
            FeatureCluster.idea_generated == False  # Only unprocessed clusters
        ).order_by(FeatureCluster.competitor_count.desc()).all()

    def mark_cluster_idea_generated(
        self,
        cluster_id: int,
        idea_id: int
    ) -> None:
        """
        Mark a cluster as having had an idea generated from it.

        Args:
            cluster_id: Cluster ID
            idea_id: ID of the generated idea
        """
        cluster = self.db.query(FeatureCluster).filter(
            FeatureCluster.id == cluster_id
        ).first()

        if cluster:
            cluster.idea_generated = True
            cluster.generated_idea_id = idea_id
            self.db.commit()

    def get_cluster_feature_keys(self, cluster_id: int) -> List[str]:
        """
        Get all feature keys in a cluster.

        V2: Returns feature_key strings instead of integer feature_id.

        Args:
            cluster_id: Cluster ID

        Returns:
            List of feature keys
        """
        members = self.db.query(FeatureClusterMember).filter(
            FeatureClusterMember.cluster_id == cluster_id
        ).all()

        return [m.feature_key for m in members]

    # Legacy compatibility alias
    def get_cluster_feature_ids(self, cluster_id: int) -> List[str]:
        """Legacy alias for get_cluster_feature_keys. Returns feature keys."""
        return self.get_cluster_feature_keys(cluster_id)

    def recalculate_cluster_intensity(self, cluster_id: int) -> int:
        """
        Recalculate the competitor count for a cluster.

        V2: Uses competitor_id stored directly in member records.

        Args:
            cluster_id: Cluster to recalculate

        Returns:
            New competitor count
        """
        members = self.db.query(FeatureClusterMember).filter(
            FeatureClusterMember.cluster_id == cluster_id
        ).all()

        # V2: competitor_id is stored directly on the member
        competitor_ids = set(m.competitor_id for m in members)

        cluster = self.db.query(FeatureCluster).filter(
            FeatureCluster.id == cluster_id
        ).first()

        if cluster:
            cluster.competitor_count = len(competitor_ids)
            cluster.feature_count = len(members)
            self.db.commit()

        return len(competitor_ids)

    def generate_ideas_for_high_intensity_clusters(
        self,
        product_id: int,
        threshold: Optional[int] = None,
        llm_service: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate ideas from high-intensity clusters and submit to triage.

        This method:
        1. Gets all clusters meeting the intensity threshold
        2. For each cluster, generates an idea using IntensityIdeaGeneratorAgent
        3. Creates an Idea record with proper traceability
        4. Submits the idea to the Idea Triage workflow

        Args:
            product_id: Product to generate ideas for
            threshold: Minimum competitor count (uses config if not provided)
            llm_service: LLM service for agent calls (required if generating)

        Returns:
            List of generated idea dicts with status information
        """
        from app.agents.intensity_idea_generator import IntensityIdeaGeneratorAgent
        from app.models.idea import Idea, SourceType, IdeaStatus
        from app.models.competitor_intelligence import CIProduct, ProductCompetitor

        # Get high-intensity clusters
        clusters = self.get_high_intensity_clusters(product_id, threshold)

        if not clusters:
            return []

        # Get product context
        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            return []

        # Get total competitor count for urgency calculation
        total_competitors = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == 'active'
        ).count()

        product_context = {
            'product_name': product.product_name,
            'product_category': product.product_category or '',
            'product_description': product.product_description or ''
        }

        results = []

        for cluster in clusters:
            try:
                # Check if an idea already exists for this cluster's feature set
                # This prevents duplicates when re-running competitive analysis
                cluster_feature_ids = set(self.get_cluster_feature_ids(cluster.id))

                # Look for existing ideas with overlapping source features
                existing_idea = self.db.query(Idea).filter(
                    Idea.product_id == product_id,
                    Idea.source_type == SourceType.COMPETITOR_AUTOMATED,
                    Idea.source_feature_ids.isnot(None)
                ).all()

                # Check for significant overlap (>50% of features match)
                skip_cluster = False
                for idea in existing_idea:
                    if idea.source_feature_ids:
                        existing_feature_ids = set(idea.source_feature_ids)
                        overlap = len(cluster_feature_ids & existing_feature_ids)
                        overlap_ratio = overlap / max(len(cluster_feature_ids), 1)
                        if overlap_ratio > 0.5:
                            # Already have an idea covering most of these features
                            results.append({
                                'cluster_id': cluster.id,
                                'cluster_name': cluster.cluster_name,
                                'status': 'skipped',
                                'reason': f'Existing idea {idea.id} covers {overlap_ratio*100:.0f}% of cluster features',
                                'existing_idea_id': idea.id
                            })
                            # Mark cluster as processed to prevent future attempts
                            self.mark_cluster_idea_generated(cluster.id, idea.id)
                            skip_cluster = True
                            break

                if skip_cluster:
                    continue

                # Get cluster member details
                members_info = self.get_clusters_by_intensity(
                    product_id,
                    min_intensity=cluster.competitor_count,
                    include_members=True
                )

                # Find this cluster's data
                cluster_data = next(
                    (c for c in members_info if c['id'] == cluster.id),
                    None
                )

                if not cluster_data:
                    continue

                # Build input for the agent
                features = [
                    {
                        'competitor_name': m.get('competitor_name', 'Unknown'),
                        'feature_name': m.get('feature_name', 'Unknown'),
                        'feature_description': m.get('feature_description', '')
                    }
                    for m in cluster_data.get('members', [])
                ]

                # Get unique competitor names for this cluster
                unique_competitor_names = list(set(
                    f.get('competitor_name') for f in features
                    if f.get('competitor_name') and f.get('competitor_name') != 'Unknown'
                ))

                agent_input = {
                    'cluster_name': cluster.cluster_name,
                    'cluster_description': cluster.cluster_description or '',
                    'competitor_count': len(unique_competitor_names),  # Use actual unique count
                    'total_competitors': total_competitors,
                    'features': features,
                    'product_context': product_context
                }

                # Generate the idea using the agent
                if llm_service is None:
                    # Skip if no LLM service (for testing without actual LLM calls)
                    results.append({
                        'cluster_id': cluster.id,
                        'cluster_name': cluster.cluster_name,
                        'status': 'skipped',
                        'reason': 'No LLM service provided'
                    })
                    continue

                agent = IntensityIdeaGeneratorAgent(
                    db=self.db,
                    llm_service=llm_service,
                    product_id=product_id
                )

                idea_output = agent.execute(agent_input)

                # Create the Idea record
                idea = Idea(
                    title=idea_output['title'],
                    what_description=idea_output['what_description'],
                    why_description=idea_output['why_description'],
                    use_case_description=idea_output['use_case_description'],
                    source_type=SourceType.COMPETITOR_AUTOMATED,
                    source_metadata={
                        'generation_type': 'competitive_intensity',
                        'cluster_id': cluster.id,
                        'cluster_name': cluster.cluster_name,
                        'competitor_count': len(unique_competitor_names),
                        'competitor_names': unique_competitor_names,  # Unique competitor names for triage
                        'total_competitors': total_competitors,
                        'competitive_urgency': idea_output.get('competitive_urgency', 'medium'),
                        'differentiation_opportunities': idea_output.get('differentiation_opportunities', [])
                    },
                    product_id=product_id,
                    category=idea_output.get('category'),
                    auto_categorized=True,
                    status=IdeaStatus.PENDING,  # Will be triaged
                    is_active=False,  # Pending = not visible yet
                    triage_confidence=idea_output.get('confidence'),
                    competitive_context={
                        'competitors_with_feature': unique_competitor_names,  # Deduplicated list
                        'competitive_urgency': idea_output.get('competitive_urgency', 'medium'),
                        'urgency_reasoning': idea_output.get('urgency_reasoning', '')
                    },
                    source_cluster_id=cluster.id,
                    source_feature_ids=self.get_cluster_feature_ids(cluster.id)
                )

                self.db.add(idea)
                self.db.commit()
                self.db.refresh(idea)

                # Mark cluster as processed
                self.mark_cluster_idea_generated(cluster.id, idea.id)

                results.append({
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.cluster_name,
                    'status': 'generated',
                    'idea_id': idea.id,
                    'idea_title': idea.title
                })

            except Exception as e:
                results.append({
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.cluster_name,
                    'status': 'error',
                    'error': str(e)
                })

        return results

    def get_cluster_details_for_idea_generation(
        self,
        cluster_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get all details needed to generate an idea from a cluster.

        Useful for manual idea generation from a specific cluster.

        Args:
            cluster_id: Cluster ID

        Returns:
            Dict with cluster info, member features, and product context
        """
        from app.models.competitor_intelligence import CIProduct, ProductCompetitor

        cluster = self.db.query(FeatureCluster).filter(
            FeatureCluster.id == cluster_id
        ).first()

        if not cluster:
            return None

        # Get product
        product = self.db.query(CIProduct).filter(
            CIProduct.id == cluster.product_id
        ).first()

        if not product:
            return None

        # Get total competitors
        total_competitors = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == cluster.product_id,
            ProductCompetitor.status == 'active'
        ).count()

        # Get cluster members with details
        clusters_info = self.get_clusters_by_intensity(
            cluster.product_id,
            min_intensity=1,
            include_members=True
        )

        cluster_data = next(
            (c for c in clusters_info if c['id'] == cluster_id),
            None
        )

        if not cluster_data:
            return None

        features = [
            {
                'competitor_name': m.get('competitor_name', 'Unknown'),
                'feature_name': m.get('feature_name', 'Unknown'),
                'feature_description': m.get('feature_description', '')
            }
            for m in cluster_data.get('members', [])
        ]

        return {
            'cluster_name': cluster.cluster_name,
            'cluster_description': cluster.cluster_description or '',
            'competitor_count': cluster.competitor_count,
            'total_competitors': total_competitors,
            'features': features,
            'product_context': {
                'product_name': product.product_name,
                'product_category': product.product_category or '',
                'product_description': product.product_description or ''
            }
        }
