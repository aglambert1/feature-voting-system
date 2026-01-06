/**
 * FeaturesTab
 *
 * Display feature clusters with intensity scores.
 * Shows competitive intensity and allows creating ideas from clusters.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  getFeatureClusters,
  getFeatureClusterDetail,
  createIdeaFromCluster,
} from '../../../services/api';
import { FeatureCluster, FeatureClusterDetail } from '../../../types';

interface Props {
  productId: number;
  refreshKey?: number;
}

export default function FeaturesTab({ productId, refreshKey }: Props) {
  const [clusters, setClusters] = useState<FeatureCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'high'>('all');
  const [selectedCluster, setSelectedCluster] = useState<FeatureClusterDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchClusters = useCallback(async () => {
    try {
      setLoading(true);
      const minCompetitors = filter === 'high' ? 3 : undefined;
      const data = await getFeatureClusters(productId, minCompetitors);
      setClusters(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load feature clusters');
    } finally {
      setLoading(false);
    }
  }, [productId, filter]);

  useEffect(() => {
    fetchClusters();
  }, [fetchClusters, refreshKey]);

  // Clear message after timeout
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const handleViewCluster = async (clusterId: number) => {
    setLoadingDetail(true);
    try {
      const detail = await getFeatureClusterDetail(productId, clusterId);
      setSelectedCluster(detail);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to load cluster details' });
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleCreateIdea = async (clusterId: number) => {
    setActionLoading(clusterId);
    try {
      const result = await createIdeaFromCluster(productId, clusterId);
      setMessage({ type: 'success', text: result.message });
      // Refresh to update idea_generated status
      await fetchClusters();
      if (selectedCluster?.id === clusterId) {
        setSelectedCluster(null);
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to create idea' });
    } finally {
      setActionLoading(null);
    }
  };

  const getIntensityColor = (count: number) => {
    if (count >= 5) return 'text-red-600 bg-red-100';
    if (count >= 3) return 'text-orange-600 bg-orange-100';
    return 'text-gray-600 bg-gray-100';
  };

  const getIntensityLabel = (count: number) => {
    if (count >= 5) return 'High';
    if (count >= 3) return 'Medium';
    return 'Low';
  };

  if (loading) {
    return (
      <div className="p-6 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
          <button onClick={fetchClusters} className="mt-2 text-red-600 hover:text-red-800 font-medium">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Feature Clusters</h2>
          <p className="text-sm text-gray-500">
            {clusters.length} clusters • Features grouped by similarity across competitors
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as 'all' | 'high')}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Clusters</option>
            <option value="high">High Intensity (3+)</option>
          </select>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* Clusters Grid */}
      {clusters.length === 0 ? (
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          <p className="mt-2 text-gray-500">No feature clusters found</p>
          <p className="text-sm text-gray-400 mt-1">
            Run feature extraction on competitors, then use "Run Clustering"
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {clusters.map(cluster => (
            <div
              key={cluster.id}
              className="bg-gray-50 rounded-lg border border-gray-200 p-4 hover:border-gray-300 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-gray-900 truncate">
                    {cluster.cluster_name || `Cluster #${cluster.id}`}
                  </h3>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                    {cluster.cluster_description || 'No description available'}
                  </p>
                </div>
                <span className={`ml-3 px-2 py-1 text-xs font-medium rounded-full ${getIntensityColor(cluster.competitor_count)}`}>
                  {getIntensityLabel(cluster.competitor_count)}
                </span>
              </div>

              <div className="flex items-center gap-4 text-sm text-gray-500 mb-3">
                <span className="flex items-center gap-1">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  {cluster.competitor_count} competitors
                </span>
                <span className="flex items-center gap-1">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  {cluster.feature_count} features
                </span>
              </div>

              <div className="flex items-center justify-between">
                {cluster.idea_generated ? (
                  <span className="text-sm text-green-600 flex items-center gap-1">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    Idea generated
                  </span>
                ) : (
                  <button
                    onClick={() => handleCreateIdea(cluster.id)}
                    disabled={actionLoading === cluster.id}
                    className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
                  >
                    {actionLoading === cluster.id ? 'Creating...' : 'Create Idea'}
                  </button>
                )}
                <button
                  onClick={() => handleViewCluster(cluster.id)}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  View Details
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Cluster Detail Modal */}
      {(selectedCluster || loadingDetail) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                {loadingDetail ? 'Loading...' : selectedCluster?.cluster_name || 'Cluster Details'}
              </h3>
              <button
                onClick={() => setSelectedCluster(null)}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-4 overflow-y-auto max-h-[60vh]">
              {loadingDetail ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
              ) : selectedCluster && (
                <>
                  <p className="text-gray-600 mb-4">{selectedCluster.cluster_description}</p>

                  <div className="flex items-center gap-4 mb-4 text-sm">
                    <span className={`px-2 py-1 rounded-full ${getIntensityColor(selectedCluster.competitor_count)}`}>
                      Intensity: {getIntensityLabel(selectedCluster.competitor_count)} ({selectedCluster.competitor_count} competitors)
                    </span>
                    <span className="text-gray-500">{selectedCluster.feature_count} features</span>
                  </div>

                  <h4 className="font-medium text-gray-900 mb-3">Member Features</h4>
                  <div className="space-y-2">
                    {selectedCluster.members.map((member, idx) => (
                      <div key={idx} className="bg-gray-50 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-gray-900">{member.feature_name}</span>
                          <span className="text-xs text-gray-500">{(member.similarity_score * 100).toFixed(0)}% match</span>
                        </div>
                        <p className="text-sm text-gray-600">{member.feature_description}</p>
                        <p className="text-xs text-gray-400 mt-1">From: {member.competitor_name}</p>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="flex justify-end gap-3 p-4 border-t border-gray-200">
              <button
                onClick={() => setSelectedCluster(null)}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
              >
                Close
              </button>
              {selectedCluster && !selectedCluster.idea_generated && (
                <button
                  onClick={() => handleCreateIdea(selectedCluster.id)}
                  disabled={actionLoading === selectedCluster.id}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
                >
                  {actionLoading === selectedCluster.id ? 'Creating...' : 'Create Idea from Cluster'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
