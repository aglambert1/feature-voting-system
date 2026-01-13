/**
 * CompetitiveReportPage
 *
 * Hybrid layout competitive report page:
 * 1. Feature Clusters section with intensity badges and idea creation
 * 2. Strategic Insights Summary (cross-competitor comparison tabs)
 * 3. Per-Competitor Details (accordions with full strategic insights and features)
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import Navigation from '../../components/Navigation';
import api, {
  getAgentCompetitors,
  getFeatureClusters,
  getFeatureClusterDetail,
  createIdeaFromCluster,
  getCompetitorFeatures,
  createIdeasFromFeatures,
  getPricingAnalysis,
  getPositioningAnalysis,
  getMomentumAnalysis,
  getChangeEvents,
} from '../../services/api';
import {
  AgentCompetitor,
  FeatureCluster,
  FeatureClusterDetail,
  CompetitorFeature,
  PricingAnalysis,
  PositioningAnalysis,
  MomentumAnalysis,
  ChangeEvent,
} from '../../types';

interface CompetitorData {
  competitor: AgentCompetitor;
  features: CompetitorFeature[];
  pricing: PricingAnalysis | null;
  positioning: PositioningAnalysis | null;
  momentum: MomentumAnalysis | null;
  recentChanges: ChangeEvent[];
  expanded: boolean;
  selectedFeatures: Set<number>;
}

export default function CompetitiveReportPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();

  // State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [productName, setProductName] = useState<string>('');
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  // Feature Clusters
  const [clusters, setClusters] = useState<FeatureCluster[]>([]);
  const [selectedCluster, setSelectedCluster] = useState<FeatureClusterDetail | null>(null);
  const [loadingClusterDetail, setLoadingClusterDetail] = useState(false);
  const [clusterActionLoading, setClusterActionLoading] = useState<number | null>(null);

  // Competitor Data
  const [competitorData, setCompetitorData] = useState<CompetitorData[]>([]);
  const [insightsTab, setInsightsTab] = useState<'pricing' | 'positioning' | 'momentum'>('pricing');

  // Messages
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [featureActionLoading, setFeatureActionLoading] = useState(false);

  useEffect(() => {
    if (productId) {
      fetchReportData();
    }
  }, [productId]);

  // Clear message after timeout
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const fetchReportData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const pid = parseInt(productId!);

      // Fetch product details
      const productResponse = await api.get(`/product-intelligence/products/${pid}`);
      setProductName(productResponse.data.product_name || productResponse.data.name || 'Product');
      setLastUpdated(productResponse.data.last_analyzed_at || null);

      // Fetch clusters
      const clustersData = await getFeatureClusters(pid);
      setClusters(clustersData);

      // Fetch competitors with deep analysis enabled
      const competitors = await getAgentCompetitors(pid, true);

      // Fetch detailed data for each competitor
      const competitorPromises = competitors.map(async (competitor) => {
        const [features, pricing, positioning, momentum, changes] = await Promise.all([
          getCompetitorFeatures(pid, competitor.id).catch(() => []),
          getPricingAnalysis(pid, competitor.id).catch(() => null),
          getPositioningAnalysis(pid, competitor.id).catch(() => null),
          getMomentumAnalysis(pid, competitor.id).catch(() => null),
          getChangeEvents(pid, competitor.id, 5).catch(() => []),
        ]);

        return {
          competitor,
          features,
          pricing,
          positioning,
          momentum,
          recentChanges: changes,
          expanded: false,
          selectedFeatures: new Set<number>(),
        };
      });

      const results = await Promise.all(competitorPromises);
      setCompetitorData(results);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load report data');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  const handleViewClusterDetail = async (clusterId: number) => {
    setLoadingClusterDetail(true);
    try {
      const detail = await getFeatureClusterDetail(parseInt(productId!), clusterId);
      setSelectedCluster(detail);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to load cluster details' });
    } finally {
      setLoadingClusterDetail(false);
    }
  };

  const handleCreateIdeaFromCluster = async (clusterId: number) => {
    setClusterActionLoading(clusterId);
    try {
      const result = await createIdeaFromCluster(parseInt(productId!), clusterId);
      setMessage({ type: 'success', text: result.message });
      // Refresh clusters to update idea_generated status
      const updated = await getFeatureClusters(parseInt(productId!));
      setClusters(updated);
      if (selectedCluster?.id === clusterId) {
        setSelectedCluster(null);
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to create idea' });
    } finally {
      setClusterActionLoading(null);
    }
  };

  const toggleCompetitorExpanded = (competitorId: number) => {
    setCompetitorData(prev =>
      prev.map(cd =>
        cd.competitor.id === competitorId
          ? { ...cd, expanded: !cd.expanded }
          : cd
      )
    );
  };

  const toggleFeatureSelection = (competitorId: number, featureId: number) => {
    setCompetitorData(prev =>
      prev.map(cd => {
        if (cd.competitor.id === competitorId) {
          const newSelected = new Set(cd.selectedFeatures);
          if (newSelected.has(featureId)) {
            newSelected.delete(featureId);
          } else {
            newSelected.add(featureId);
          }
          return { ...cd, selectedFeatures: newSelected };
        }
        return cd;
      })
    );
  };

  const handleCreateIdeasFromFeatures = async (competitorId: number) => {
    const competitorItem = competitorData.find(cd => cd.competitor.id === competitorId);
    if (!competitorItem || competitorItem.selectedFeatures.size === 0) return;

    setFeatureActionLoading(true);
    try {
      const featureIds = Array.from(competitorItem.selectedFeatures);
      const result = await createIdeasFromFeatures(parseInt(productId!), competitorId, { feature_ids: featureIds });
      const successCount = result.filter(r => r.job_id).length;
      setMessage({ type: 'success', text: `Created ${successCount} idea${successCount !== 1 ? 's' : ''} successfully` });
      // Clear selection
      setCompetitorData(prev =>
        prev.map(cd =>
          cd.competitor.id === competitorId
            ? { ...cd, selectedFeatures: new Set<number>() }
            : cd
        )
      );
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to create ideas' });
    } finally {
      setFeatureActionLoading(false);
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

  const getMomentumColor = (trend: string) => {
    if (trend === 'rising') return 'text-green-600 bg-green-100';
    if (trend === 'declining') return 'text-red-600 bg-red-100';
    return 'text-gray-600 bg-gray-100';
  };

  const getMomentumIcon = (trend: string) => {
    if (trend === 'rising') return '↑';
    if (trend === 'declining') return '↓';
    return '→';
  };

  const handleBack = () => {
    navigate(`/product-intelligence/products/${productId}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={handleBack}
            className="text-blue-600 hover:text-blue-800 text-sm font-medium mb-4 flex items-center"
          >
            <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Product Dashboard
          </button>

          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Competitive Report</h1>
              <p className="text-gray-600 mt-1">{productName}</p>
            </div>
            {lastUpdated && (
              <span className="text-sm text-gray-500">
                Last updated: {formatDistanceToNow(new Date(lastUpdated), { addSuffix: true })}
              </span>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {message && (
          <div className={`mb-4 p-3 rounded-lg text-sm ${
            message.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}>
            {message.text}
          </div>
        )}

        {/* Section 1: Feature Clusters */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Feature Clusters</h2>
          {clusters.length === 0 ? (
            <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <p className="mt-2 text-gray-500">No feature clusters found</p>
              <p className="text-sm text-gray-400 mt-1">
                Run competitive analysis to extract features and create clusters
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {clusters.map(cluster => (
                <div
                  key={cluster.id}
                  className="bg-white rounded-lg border border-gray-200 p-4 hover:border-gray-300 transition-colors"
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
                    <span>{cluster.competitor_count} competitors</span>
                    <span>{cluster.feature_count} features</span>
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
                        onClick={() => handleCreateIdeaFromCluster(cluster.id)}
                        disabled={clusterActionLoading === cluster.id}
                        className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
                      >
                        {clusterActionLoading === cluster.id ? 'Creating...' : 'Create Idea'}
                      </button>
                    )}
                    <button
                      onClick={() => handleViewClusterDetail(cluster.id)}
                      className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                      View Details
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Section 2: Strategic Insights Summary */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Strategic Insights Summary</h2>

          {competitorData.length === 0 ? (
            <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
              <p className="text-gray-500">No competitors with deep analysis enabled</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              {/* Tabs */}
              <div className="flex border-b border-gray-200">
                {[
                  { id: 'pricing', label: 'Pricing Comparison' },
                  { id: 'positioning', label: 'Positioning Comparison' },
                  { id: 'momentum', label: 'Momentum Comparison' },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setInsightsTab(tab.id as typeof insightsTab)}
                    className={`px-4 py-3 text-sm font-medium ${
                      insightsTab === tab.id
                        ? 'border-b-2 border-blue-600 text-blue-600'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="p-4">
                {/* Pricing Tab */}
                {insightsTab === 'pricing' && (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Competitor</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Model</th>
                          <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Free Tier</th>
                          <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Trial</th>
                          <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Enterprise</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tiers</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {competitorData.map(({ competitor, pricing }) => (
                          <tr key={competitor.id}>
                            <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              {competitor.competitor_name}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                              {pricing?.pricing_model || '-'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-center">
                              {pricing ? (
                                pricing.has_free_tier ? <span className="text-green-600">✓</span> : <span className="text-gray-400">✗</span>
                              ) : '-'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-center text-sm">
                              {pricing ? (
                                pricing.has_trial ? (
                                  <span className="text-green-600">{pricing.trial_days ? `${pricing.trial_days}d` : '✓'}</span>
                                ) : <span className="text-gray-400">✗</span>
                              ) : '-'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-center">
                              {pricing ? (
                                pricing.has_enterprise ? <span className="text-green-600">✓</span> : <span className="text-gray-400">✗</span>
                              ) : '-'}
                            </td>
                            <td className="px-4 py-4 text-sm text-gray-500">
                              {pricing?.pricing_tiers ? `${pricing.pricing_tiers.length} tiers` : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Positioning Tab */}
                {insightsTab === 'positioning' && (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Competitor</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tagline</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Market Segment</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Target Audience</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {competitorData.map(({ competitor, positioning }) => (
                          <tr key={competitor.id}>
                            <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              {competitor.competitor_name}
                            </td>
                            <td className="px-4 py-4 text-sm text-gray-500 max-w-xs truncate">
                              {positioning?.tagline ? `"${positioning.tagline}"` : '-'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                              {positioning?.market_segment || '-'}
                            </td>
                            <td className="px-4 py-4 text-sm text-gray-500 max-w-xs truncate">
                              {positioning?.target_audience || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Momentum Tab */}
                {insightsTab === 'momentum' && (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Competitor</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trend</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Growth</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Release Velocity</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {competitorData.map(({ competitor, momentum }) => (
                          <tr key={competitor.id}>
                            <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              {competitor.competitor_name}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap">
                              {momentum ? (
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getMomentumColor(momentum.momentum_trend)}`}>
                                  {getMomentumIcon(momentum.momentum_trend)} {momentum.momentum_trend}
                                </span>
                              ) : '-'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                              {momentum ? `${(momentum.momentum_score * 100).toFixed(0)}%` : '-'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                              {momentum?.customer_growth_trend || '-'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                              {momentum?.release_velocity || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>

        {/* Section 3: Per-Competitor Details (Accordions) */}
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Competitor Details</h2>

          {competitorData.length === 0 ? (
            <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
              <p className="text-gray-500">No competitors with deep analysis enabled</p>
            </div>
          ) : (
            <div className="space-y-4">
              {competitorData.map((cd) => (
                <div key={cd.competitor.id} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                  {/* Accordion Header */}
                  <button
                    onClick={() => toggleCompetitorExpanded(cd.competitor.id)}
                    className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-3">
                      <svg
                        className={`w-5 h-5 text-gray-400 transition-transform ${cd.expanded ? 'rotate-90' : ''}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                      <span className="font-medium text-gray-900">{cd.competitor.competitor_name}</span>
                      <span className="text-sm text-gray-500">({cd.features.length} features)</span>
                    </div>
                    {cd.momentum && (
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getMomentumColor(cd.momentum.momentum_trend)}`}>
                        {getMomentumIcon(cd.momentum.momentum_trend)} {cd.momentum.momentum_trend}
                      </span>
                    )}
                  </button>

                  {/* Accordion Content */}
                  {cd.expanded && (
                    <div className="border-t border-gray-200 p-4">
                      {/* Strategic Insights */}
                      <div className="mb-6">
                        <h4 className="font-medium text-gray-900 mb-3">Strategic Insights</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* Pricing */}
                          <div className="bg-gray-50 rounded-lg p-3">
                            <p className="text-xs font-medium text-gray-500 uppercase mb-2">Pricing</p>
                            {cd.pricing ? (
                              <div className="text-sm text-gray-700 space-y-1">
                                <p>Model: {cd.pricing.pricing_model || 'N/A'}</p>
                                <p>Free tier: {cd.pricing.has_free_tier ? 'Yes' : 'No'}</p>
                                <p>Trial: {cd.pricing.has_trial ? (cd.pricing.trial_days ? `${cd.pricing.trial_days} days` : 'Yes') : 'No'}</p>
                                {cd.pricing.pricing_tiers && <p>{cd.pricing.pricing_tiers.length} pricing tiers</p>}
                              </div>
                            ) : (
                              <p className="text-sm text-gray-400">No data available</p>
                            )}
                          </div>

                          {/* Positioning */}
                          <div className="bg-gray-50 rounded-lg p-3">
                            <p className="text-xs font-medium text-gray-500 uppercase mb-2">Positioning</p>
                            {cd.positioning ? (
                              <div className="text-sm text-gray-700 space-y-1">
                                {cd.positioning.tagline && <p className="italic">"{cd.positioning.tagline}"</p>}
                                {cd.positioning.market_segment && <p>Segment: {cd.positioning.market_segment}</p>}
                                {cd.positioning.target_audience && <p>Target: {cd.positioning.target_audience}</p>}
                              </div>
                            ) : (
                              <p className="text-sm text-gray-400">No data available</p>
                            )}
                          </div>

                          {/* Momentum */}
                          <div className="bg-gray-50 rounded-lg p-3">
                            <p className="text-xs font-medium text-gray-500 uppercase mb-2">Momentum</p>
                            {cd.momentum ? (
                              <div className="text-sm text-gray-700 space-y-1">
                                <p>Trend: {cd.momentum.momentum_trend} ({(cd.momentum.momentum_score * 100).toFixed(0)}%)</p>
                                {cd.momentum.customer_growth_trend && <p>Growth: {cd.momentum.customer_growth_trend}</p>}
                                {cd.momentum.analysis_summary && <p className="text-gray-500 text-xs mt-1">{cd.momentum.analysis_summary}</p>}
                              </div>
                            ) : (
                              <p className="text-sm text-gray-400">No data available</p>
                            )}
                          </div>

                          {/* Recent Changes */}
                          <div className="bg-gray-50 rounded-lg p-3">
                            <p className="text-xs font-medium text-gray-500 uppercase mb-2">Recent Changes</p>
                            {cd.recentChanges.length > 0 ? (
                              <div className="space-y-2">
                                {cd.recentChanges.slice(0, 3).map(change => (
                                  <div key={change.id} className="text-sm">
                                    <span className={`inline-block px-1.5 py-0.5 text-xs rounded mr-1 ${
                                      change.impact_level === 'major' ? 'bg-red-100 text-red-700' :
                                      change.impact_level === 'minor' ? 'bg-yellow-100 text-yellow-700' :
                                      'bg-gray-100 text-gray-700'
                                    }`}>
                                      {change.impact_level}
                                    </span>
                                    <span className="text-gray-700">{change.event_title}</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-gray-400">No recent changes</p>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Features */}
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="font-medium text-gray-900">Features ({cd.features.length})</h4>
                          {cd.selectedFeatures.size > 0 && (
                            <button
                              onClick={() => handleCreateIdeasFromFeatures(cd.competitor.id)}
                              disabled={featureActionLoading}
                              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
                            >
                              {featureActionLoading ? 'Creating...' : `Create Ideas from Selected (${cd.selectedFeatures.size})`}
                            </button>
                          )}
                        </div>

                        {cd.features.length === 0 ? (
                          <p className="text-sm text-gray-400">No features extracted yet</p>
                        ) : (
                          <div className="space-y-2 max-h-96 overflow-y-auto">
                            {cd.features.map(feature => (
                              <div
                                key={feature.id}
                                className={`flex items-start gap-3 p-3 rounded-lg border ${
                                  cd.selectedFeatures.has(feature.id)
                                    ? 'bg-blue-50 border-blue-200'
                                    : 'bg-gray-50 border-gray-200'
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={cd.selectedFeatures.has(feature.id)}
                                  onChange={() => toggleFeatureSelection(cd.competitor.id, feature.id)}
                                  className="mt-1 h-4 w-4 text-blue-600 rounded"
                                />
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium text-gray-900">{feature.feature_name}</span>
                                    {feature.status === 'new' && (
                                      <span className="px-1.5 py-0.5 text-xs bg-green-100 text-green-700 rounded">NEW</span>
                                    )}
                                    {feature.status === 'modified' && (
                                      <span className="px-1.5 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">MODIFIED</span>
                                    )}
                                    {feature.cluster_name && (
                                      <span className="px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
                                        {feature.cluster_name}
                                      </span>
                                    )}
                                  </div>
                                  {feature.feature_description && (
                                    <p className="text-sm text-gray-600 mt-1">{feature.feature_description}</p>
                                  )}
                                  {feature.feature_category && (
                                    <span className="text-xs text-gray-400">{feature.feature_category}</span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      {/* Cluster Detail Modal */}
      {(selectedCluster || loadingClusterDetail) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                {loadingClusterDetail ? 'Loading...' : selectedCluster?.cluster_name || 'Cluster Details'}
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
              {loadingClusterDetail ? (
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
                  onClick={() => handleCreateIdeaFromCluster(selectedCluster.id)}
                  disabled={clusterActionLoading === selectedCluster.id}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
                >
                  {clusterActionLoading === selectedCluster.id ? 'Creating...' : 'Create Idea from Cluster'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
