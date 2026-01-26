/**
 * ProductDetailPage (Product Dashboard)
 *
 * Redesigned unified Product Dashboard with:
 * - Agent Status tiles (Idea Triage, Market Discovery, Competitive Analysis)
 * - Current Product Analysis
 * - Product Information Sources
 * - Analysis History
 */

import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { format } from 'date-fns';
import api, {
  getProductPendingCounts,
  getAgentConfig,
  getAgentCompetitors,
  getFeatureClusters,
  getTriageSettings,
  triggerCompetitorDiscovery,
  triggerCompetitiveAnalysisV2,
  getInternalFeedbackImports,
  getInternalFeedbackThemes,
  getSynthesisStatus,
  getLatestSynthesis,
  getUnreadAlertCount,
  getFunctionalReports,
  getProductJobs,
} from '../../services/api';
import Navigation from '../../components/Navigation';
import { ProductSource, ProductPendingCounts, CompetitiveAgentConfig, AgentCompetitor, FeatureCluster, TriageSettings, JobType, QueueJob, JobStatus } from '../../types';
import IdeaTriageSetupModal from './components/IdeaTriageSetupModal';
import CompetitiveIntelligenceSetupModal from './components/CompetitiveIntelligenceSetupModal';
import AgentJobStatus from '../../components/AgentJobStatus';
import FeatureQueryChat from './components/FeatureQueryChat';

interface StructuredProductData {
  core_features?: string[];
  target_users?: string;
  value_propositions?: string[];
  competitor_search_keywords?: string[];
  product_category?: string;
}

interface SourceData {
  url?: string;
  filename?: string;
  sources?: ProductSource[];
}

interface ProductDetail {
  id: number;
  product_name: string;
  product_description: string;
  product_category?: string;
  product_source_type?: string;
  product_source_data?: SourceData;
  analysis_version: number;
  structured_product_data?: StructuredProductData;
}

interface AnalysisHistory {
  id: number;
  analysis_version: number;
  created_at: string;
  tokens_used?: number;
  analyzed_structure?: StructuredProductData;
  product_description?: string;
  product_source_type?: string;
  product_source_data?: SourceData;
}

export default function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  // Core product data
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistory[]>([]);
  const [sources, setSources] = useState<ProductSource[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeAnalysisJob, setActiveAnalysisJob] = useState<QueueJob | null>(null);

  // Agent-related state
  const [pendingCounts, setPendingCounts] = useState<ProductPendingCounts | null>(null);
  const [agentConfig, setAgentConfig] = useState<CompetitiveAgentConfig | null>(null);
  const [competitors, setCompetitors] = useState<AgentCompetitor[]>([]);
  const [clusters, setClusters] = useState<FeatureCluster[]>([]);
  const [triageSettings, setTriageSettings] = useState<TriageSettings | null>(null);

  // Internal feedback state
  const [internalFeedbackStats, setInternalFeedbackStats] = useState<{
    importCount: number;
    winlossThemeCount: number;
    supportThemeCount: number;
    lastImportDate: string | null;
  }>({ importCount: 0, winlossThemeCount: 0, supportThemeCount: 0, lastImportDate: null });

  // Synthesis state
  const [synthesisStats, setSynthesisStats] = useState<{
    hasRun: boolean;
    status: string;
    opportunityCount: number;
    threeWayMatches: number;
    twoWayMatches: number;
    lastRunDate: string | null;
    sourcesAvailable: number;
  }>({
    hasRun: false,
    status: 'none',
    opportunityCount: 0,
    threeWayMatches: 0,
    twoWayMatches: 0,
    lastRunDate: null,
    sourcesAvailable: 0
  });

  // UI state
  const [expandedVersions, setExpandedVersions] = useState<Set<number>>(new Set());
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());

  // Modal state
  const [showIdeaTriageSetup, setShowIdeaTriageSetup] = useState(false);
  const [showCompetitiveIntelligenceSetup, setShowCompetitiveIntelligenceSetup] = useState(false);
  const [showNoCompetitorsWarning, setShowNoCompetitorsWarning] = useState(false);

  // Competitive intelligence stats
  const [unreadAlertCount, setUnreadAlertCount] = useState(0);
  const [functionalReportCount, setFunctionalReportCount] = useState(0);

  // Action state
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Fetch synthesis stats (can be called independently when synthesis job completes)
  const fetchSynthesisStats = useCallback(async () => {
    if (!productId) return;
    const numProductId = parseInt(productId);

    try {
      const [synthesisStatusRes, synthesisResultsRes] = await Promise.all([
        getSynthesisStatus(numProductId).catch(() => null),
        getLatestSynthesis(numProductId).catch(() => null)
      ]);

      const sourcesAvailable = [
        synthesisStatusRes?.sources_available?.competitive,
        synthesisStatusRes?.sources_available?.customer,
        synthesisStatusRes?.sources_available?.internal
      ].filter(Boolean).length;

      if (synthesisResultsRes && synthesisResultsRes.run && synthesisResultsRes.run.status !== 'none') {
        setSynthesisStats({
          hasRun: true,
          status: synthesisResultsRes.run.status,
          opportunityCount: synthesisResultsRes.opportunities?.length || 0,
          threeWayMatches: synthesisResultsRes.run.summary_stats?.three_way_matches || 0,
          twoWayMatches: synthesisResultsRes.run.summary_stats?.two_way_matches || 0,
          lastRunDate: synthesisResultsRes.run.completed_at || synthesisResultsRes.run.created_at,
          sourcesAvailable
        });
      } else {
        setSynthesisStats({
          hasRun: false,
          status: 'none',
          opportunityCount: 0,
          threeWayMatches: 0,
          twoWayMatches: 0,
          lastRunDate: null,
          sourcesAvailable
        });
      }
    } catch (err) {
      console.error('Failed to fetch synthesis stats:', err);
    }
  }, [productId]);

  // Fetch all data
  const fetchAllData = useCallback(async () => {
    if (!productId) return;
    const numProductId = parseInt(productId);

    try {
      setLoading(true);

      // Fetch product details
      const productResponse = await api.get<ProductDetail>(`/product-intelligence/products/${productId}`);
      setProduct(productResponse.data);

      // Parse sources
      const loadedSources = parseProductSources(productResponse.data);
      setSources(loadedSources);

      // Parallel fetch of additional data
      const [
        pendingCountsRes,
        agentConfigRes,
        competitorsRes,
        clustersRes,
        triageRes,
        historyRes,
        internalImportsRes,
        internalThemesRes,
        synthesisStatusRes,
        synthesisResultsRes,
        alertCountRes,
        functionalReportsRes,
        analysisJobsRes
      ] = await Promise.all([
        getProductPendingCounts(numProductId).catch(() => null),
        getAgentConfig(numProductId).catch(() => null),
        getAgentCompetitors(numProductId).catch(() => []),
        getFeatureClusters(numProductId).catch(() => []),
        getTriageSettings(numProductId).catch(() => null),
        productResponse.data.analysis_version > 0
          ? api.get<AnalysisHistory[]>(`/product-intelligence/products/${productId}/analysis-history`).then(r => r.data)
          : Promise.resolve([]),
        getInternalFeedbackImports(numProductId).catch(() => []),
        getInternalFeedbackThemes(numProductId).catch(() => ({ import_id: 0, winloss_themes: [], support_themes: [], analysis_summary: null })),
        getSynthesisStatus(numProductId).catch(() => null),
        getLatestSynthesis(numProductId).catch(() => null),
        getUnreadAlertCount(numProductId).catch(() => ({ count: 0 })),
        getFunctionalReports(numProductId).catch(() => []),
        getProductJobs(numProductId, 5, [JobType.PRODUCT_ANALYSIS]).catch(() => [])
      ]);

      setPendingCounts(pendingCountsRes);
      setAgentConfig(agentConfigRes);
      setCompetitors(competitorsRes);
      setClusters(clustersRes);
      setTriageSettings(triageRes);
      setAnalysisHistory(historyRes);
      setUnreadAlertCount(alertCountRes?.count || 0);
      setFunctionalReportCount(functionalReportsRes?.length || 0);

      // Check for active analysis job
      const activeAnalysis = analysisJobsRes.find((j: QueueJob) =>
        j.status === JobStatus.PENDING ||
        j.status === JobStatus.QUEUED ||
        j.status === JobStatus.RUNNING
      );
      setActiveAnalysisJob(activeAnalysis || null);

      // Set internal feedback stats
      setInternalFeedbackStats({
        importCount: internalImportsRes.length,
        winlossThemeCount: internalThemesRes.winloss_themes.length,
        supportThemeCount: internalThemesRes.support_themes.length,
        lastImportDate: internalImportsRes.length > 0 ? internalImportsRes[0].imported_at : null
      });

      // Set synthesis stats
      const sourcesAvailable = [
        synthesisStatusRes?.sources_available?.competitive,
        synthesisStatusRes?.sources_available?.customer,
        synthesisStatusRes?.sources_available?.internal
      ].filter(Boolean).length;

      if (synthesisResultsRes && synthesisResultsRes.run && synthesisResultsRes.run.status !== 'none') {
        setSynthesisStats({
          hasRun: true,
          status: synthesisResultsRes.run.status,
          opportunityCount: synthesisResultsRes.opportunities?.length || 0,
          threeWayMatches: synthesisResultsRes.run.summary_stats?.three_way_matches || 0,
          twoWayMatches: synthesisResultsRes.run.summary_stats?.two_way_matches || 0,
          lastRunDate: synthesisResultsRes.run.completed_at || synthesisResultsRes.run.created_at,
          sourcesAvailable
        });
      } else {
        setSynthesisStats({
          hasRun: false,
          status: 'none',
          opportunityCount: 0,
          threeWayMatches: 0,
          twoWayMatches: 0,
          lastRunDate: null,
          sourcesAvailable
        });
      }

    } catch (err: any) {
      setError(err.message || err.data?.detail || 'Failed to load product');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData, location.key]);

  // Poll for active analysis job completion
  useEffect(() => {
    if (!activeAnalysisJob || !productId) return;

    const interval = setInterval(async () => {
      try {
        const jobs = await getProductJobs(parseInt(productId), 5, [JobType.PRODUCT_ANALYSIS]);
        const active = jobs.find(j =>
          j.status === JobStatus.PENDING ||
          j.status === JobStatus.QUEUED ||
          j.status === JobStatus.RUNNING
        );

        if (active) {
          setActiveAnalysisJob(active);
        } else {
          // Job completed - refresh all data
          setActiveAnalysisJob(null);
          fetchAllData();
        }
      } catch (err) {
        console.error('[ProductDetail] Failed to poll analysis job:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeAnalysisJob, productId, fetchAllData]);

  // Clear action message after timeout
  useEffect(() => {
    if (actionMessage) {
      const timer = setTimeout(() => setActionMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [actionMessage]);

  const parseProductSources = (productData: ProductDetail): ProductSource[] => {
    if (!productData || !productData.product_source_data) {
      if (productData?.product_description) {
        return [{
          type: 'text',
          content: productData.product_description,
          extracted_text: productData.product_description,
          token_estimate: Math.floor(productData.product_description.length / 4),
        }];
      }
      return [];
    }

    const sourceData = productData.product_source_data as any;
    if (sourceData.sources && Array.isArray(sourceData.sources)) {
      return sourceData.sources;
    }

    if (productData.product_description) {
      return [{
        type: 'text',
        content: productData.product_description,
        extracted_text: productData.product_description,
        token_estimate: Math.floor(productData.product_description.length / 4),
      }];
    }

    return [];
  };

  const handleChangeSources = () => {
    navigate(`/product-intelligence/products/${productId}/analyze`);
  };

  const handleRunMarketDiscovery = async () => {
    if (!productId) return;
    setRunningAction('market-discovery');
    setShowNoCompetitorsWarning(false);
    try {
      await triggerCompetitorDiscovery(parseInt(productId));
      setActionMessage({ type: 'success', text: 'Market Discovery started. Check back shortly for results.' });
      // Refresh data after a delay
      setTimeout(fetchAllData, 2000);
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message || 'Failed to start Market Discovery' });
    } finally {
      setRunningAction(null);
    }
  };

  const handleRunAllNow = async () => {
    if (!productId) return;

    // Check if any competitors are selected for deep analysis
    const selectedForAnalysis = competitors.filter(c => c.deep_analysis_enabled).length;
    if (selectedForAnalysis === 0) {
      setShowNoCompetitorsWarning(true);
      return;
    }

    // Run full pipeline: discovery → analysis → synthesis
    setRunningAction('run-all');
    try {
      // First trigger discovery, then analysis (V2 includes synthesis)
      await triggerCompetitorDiscovery(parseInt(productId));
      await triggerCompetitiveAnalysisV2(parseInt(productId));
      setActionMessage({ type: 'success', text: 'Full competitive intelligence pipeline started: Discovery → Functional Audits → Landscape Synthesis' });
      setTimeout(fetchAllData, 2000);
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail || err.message || 'Failed to start competitive intelligence pipeline';
      setActionMessage({ type: 'error', text: errorDetail });
    } finally {
      setRunningAction(null);
    }
  };

  const toggleVersionExpanded = (versionId: number) => {
    setExpandedVersions(prev => {
      const newSet = new Set(prev);
      if (newSet.has(versionId)) {
        newSet.delete(versionId);
      } else {
        newSet.add(versionId);
      }
      return newSet;
    });
  };

  const toggleSourceExpansion = (index: number) => {
    setExpandedSources(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const getSourceLabel = (source: ProductSource, index: number): string => {
    if (source.type === 'text') return `Text Description ${index + 1}`;
    if (source.type === 'document') return source.filename || 'Document';
    if (source.type === 'url') return source.title || source.url || 'URL';
    return `Source ${index + 1}`;
  };

  // Calculate stats
  const totalCompetitors = competitors.length;
  const newCompetitors = competitors.filter(c => (c as any).is_new).length;
  const trackingCompetitors = competitors.filter(c => c.deep_analysis_enabled).length;
  const totalFeatures = competitors.reduce((sum, c) => sum + (c.feature_count || 0), 0);
  const totalClusters = clusters.length;
  const ideasFromClusters = clusters.filter(c => c.idea_generated).length;

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

  if (error || !product) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 py-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error || 'Product not found'}</p>
          </div>
        </main>
      </div>
    );
  }

  const currentAnalysis = product.structured_product_data;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/product-intelligence')}
            className="text-blue-600 hover:text-blue-800 mb-4 font-medium"
          >
            ← All Products
          </button>

          <div className="flex justify-between items-start">
            <h1 className="text-3xl font-bold text-gray-900">
              {product.product_name}
            </h1>
            <button
              onClick={handleChangeSources}
              className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium"
            >
              Change Sources
            </button>
          </div>
        </div>

        {/* Action Message */}
        {actionMessage && (
          <div className={`mb-6 p-4 rounded-lg ${
            actionMessage.type === 'success' ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-red-50 border border-red-200 text-red-800'
          }`}>
            {actionMessage.text}
          </div>
        )}

        {/* Agent Status Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* Idea Triage Agent Tile */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Idea Triage Agent</h3>
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                triageSettings?.auto_enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
              }`}>
                {triageSettings?.auto_enabled ? 'Automatic' : 'Recommendations'}
              </span>
            </div>

            <div className="space-y-3">
              <div className="text-sm text-gray-600">
                {pendingCounts && (pendingCounts.ideas_pending > 0 || pendingCounts.ideas_needs_review > 0) ? (
                  <Link
                    to={`/ideas?product_id=${productId}`}
                    className="text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {(pendingCounts.ideas_pending || 0) + (pendingCounts.ideas_needs_review || 0)} {
                      (pendingCounts.ideas_pending || 0) + (pendingCounts.ideas_needs_review || 0) === 1 ? 'idea' : 'ideas'
                    } awaiting review →
                  </Link>
                ) : (
                  <span className="text-gray-500">No ideas awaiting review</span>
                )}
              </div>

              <div className="text-sm text-gray-500">
                Automatic Responses: {triageSettings?.auto_enabled ? 'On' : 'Off'}
                {triageSettings?.auto_enabled && ` (${Math.round((triageSettings.auto_threshold || 0) * 100)}% threshold)`}
              </div>

              <button
                onClick={() => setShowIdeaTriageSetup(true)}
                className="w-full px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors font-medium"
              >
                Setup
              </button>
            </div>
          </div>

          {/* Competitive Intelligence Agent Tile (Combined) */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-gray-900">Competitive Intelligence Agent</h3>
                {unreadAlertCount > 0 && (
                  <span className="flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 text-xs font-medium rounded-full">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
                    </svg>
                    {unreadAlertCount}
                  </span>
                )}
              </div>
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                agentConfig?.competitor_discovery_mode === 'scheduled' || agentConfig?.deep_analysis_mode === 'scheduled'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {agentConfig?.competitor_discovery_mode === 'scheduled' || agentConfig?.deep_analysis_mode === 'scheduled'
                  ? 'Scheduled'
                  : 'Manual'}
              </span>
            </div>

            <div className="space-y-3">
              {/* Job Status - shows all competitive intelligence jobs */}
              <AgentJobStatus
                productId={parseInt(productId!)}
                jobTypes={[
                  JobType.COMPETITOR_DISCOVERY,
                  JobType.FEATURE_CLUSTERING,
                  JobType.DEEP_ANALYSIS,
                  JobType.SCHEDULED_DEEP_ANALYSIS
                ]}
                onJobComplete={fetchAllData}
              />

              {/* Stats */}
              <div className="text-sm text-gray-600">
                {totalCompetitors} competitors discovered
              </div>

              <div className="text-sm text-gray-500">
                {trackingCompetitors} selected for deep analysis
              </div>

              <div className="text-sm text-gray-500">
                {functionalReportCount} functional reports available
              </div>

              {/* Actions */}
              <div className="pt-2 border-t border-gray-100">
                <Link
                  to={`/product-intelligence/products/${productId}/intelligence?tab=competitor-reports`}
                  className="text-blue-600 hover:text-blue-800 font-medium text-sm"
                >
                  View Reports →
                </Link>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleRunAllNow}
                  disabled={runningAction === 'run-all' || runningAction === 'market-discovery'}
                  className="flex-1 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
                >
                  {runningAction === 'run-all' || runningAction === 'market-discovery' ? 'Running...' : 'Run All Now'}
                </button>
                <button
                  onClick={() => setShowCompetitiveIntelligenceSetup(true)}
                  className="px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors font-medium"
                >
                  Setup
                </button>
              </div>
            </div>
          </div>

          {/* Internal Discovery Agent Tile */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Internal Discovery Agent</h3>
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                internalFeedbackStats.importCount > 0 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
              }`}>
                {internalFeedbackStats.importCount > 0 ? 'Data Imported' : 'No Data'}
              </span>
            </div>

            <div className="space-y-3">
              <div className="text-sm text-gray-600">
                {internalFeedbackStats.importCount > 0 ? (
                  <Link
                    to={`/product-intelligence/products/${productId}/internal-feedback`}
                    className="text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {internalFeedbackStats.winlossThemeCount + internalFeedbackStats.supportThemeCount} themes extracted →
                  </Link>
                ) : (
                  <span className="text-gray-500">Import sales win/loss and support data</span>
                )}
              </div>

              <div className="text-sm text-gray-500">
                {internalFeedbackStats.winlossThemeCount} win/loss themes; {internalFeedbackStats.supportThemeCount} support themes
              </div>

              {internalFeedbackStats.lastImportDate && (
                <div className="text-sm text-gray-500">
                  Last import: {format(new Date(internalFeedbackStats.lastImportDate), 'MMM d, yyyy')}
                </div>
              )}

              <div className="flex gap-2">
                <Link
                  to={`/product-intelligence/products/${productId}/internal-feedback${internalFeedbackStats.importCount > 0 ? '?tab=themes' : ''}`}
                  className="flex-1 px-3 py-2 text-sm text-center bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                >
                  {internalFeedbackStats.importCount > 0 ? 'View Themes' : 'Import Data'}
                </Link>
              </div>
            </div>
          </div>

          {/* Opportunity Synthesis Agent Tile */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Opportunity Synthesis Agent</h3>
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                synthesisStats.hasRun && synthesisStats.status === 'completed'
                  ? 'bg-green-100 text-green-800'
                  : synthesisStats.sourcesAvailable > 0
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-gray-100 text-gray-600'
              }`}>
                {synthesisStats.hasRun && synthesisStats.status === 'completed'
                  ? `${synthesisStats.opportunityCount} Opportunities`
                  : synthesisStats.sourcesAvailable > 0
                    ? `${synthesisStats.sourcesAvailable}/3 Sources`
                    : 'No Sources'}
              </span>
            </div>

            {/* Job Status - shows running progress */}
            <AgentJobStatus
              productId={parseInt(productId!, 10)}
              jobTypes={[JobType.OPPORTUNITY_SYNTHESIS]}
              onJobComplete={() => {
                // Refresh synthesis stats when job completes
                fetchSynthesisStats();
              }}
              className="mb-3"
            />

            <div className="space-y-3">
              <div className="text-sm text-gray-600">
                {synthesisStats.hasRun && synthesisStats.status === 'completed' ? (
                  <Link
                    to={`/product-intelligence/products/${productId}/synthesis`}
                    className="text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {synthesisStats.threeWayMatches} three-way, {synthesisStats.twoWayMatches} two-way matches →
                  </Link>
                ) : (
                  <span className="text-gray-500">
                    Combines competitive, customer, and internal signals
                  </span>
                )}
              </div>

              <div className="text-sm text-gray-500">
                {synthesisStats.sourcesAvailable}/3 sources available for synthesis
              </div>

              {synthesisStats.lastRunDate && (
                <div className="text-sm text-gray-500">
                  Last run: {format(new Date(synthesisStats.lastRunDate), 'MMM d, yyyy')}
                </div>
              )}

              <div className="flex gap-2">
                <Link
                  to={`/product-intelligence/products/${productId}/synthesis`}
                  className={`flex-1 px-3 py-2 text-sm text-center rounded-lg font-medium transition-colors ${
                    synthesisStats.sourcesAvailable > 0
                      ? 'bg-purple-600 text-white hover:bg-purple-700'
                      : 'bg-gray-200 text-gray-500 cursor-not-allowed pointer-events-none'
                  }`}
                >
                  {synthesisStats.hasRun ? 'View Synthesis' : 'Run Synthesis'}
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Current Product Analysis */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Product Analysis
            </h2>
            <AgentJobStatus
              productId={parseInt(productId!)}
              jobTypes={[JobType.PRODUCT_ANALYSIS]}
              onJobComplete={fetchAllData}
            />
          </div>
        {currentAnalysis && (
          <>
            <div className="space-y-4">
              {currentAnalysis.core_features && currentAnalysis.core_features.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Core Features ({currentAnalysis.core_features.length})
                  </label>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {currentAnalysis.core_features.map((feature, idx) => (
                      <div key={idx} className="flex items-start gap-2 text-gray-700">
                        <svg className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {currentAnalysis.target_users && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Target Users
                  </label>
                  <p className="text-gray-700">{currentAnalysis.target_users}</p>
                </div>
              )}

              {currentAnalysis.value_propositions && currentAnalysis.value_propositions.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Value Propositions
                  </label>
                  <ul className="space-y-2">
                    {currentAnalysis.value_propositions.map((vp, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-gray-700">
                        <svg className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        <span>{vp}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {currentAnalysis.competitor_search_keywords && currentAnalysis.competitor_search_keywords.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Competitor Search Keywords
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {currentAnalysis.competitor_search_keywords.map((keyword, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1 bg-gray-100 text-gray-700 text-sm rounded-full"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
        {!currentAnalysis && (
          <p className="text-gray-500 text-sm">
            No analysis yet. Click "Change Sources" to add product information and run analysis.
          </p>
        )}
        </div>

        {/* Feature Query Chat */}
        {product && product.structured_product_data && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <FeatureQueryChat
              productId={product.id}
              productName={product.product_name}
            />
          </div>
        )}

        {/* Product Information Sources */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Product Information Sources
            </h2>
            <button
              onClick={handleChangeSources}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              Change Sources
            </button>
          </div>

          {sources.length > 0 ? (
            <div className="space-y-2">
              {sources.map((source, index) => {
                const isExpanded = expandedSources.has(index);
                const fullText = source.extracted_text || source.content || '';

                return (
                  <div
                    key={index}
                    className="bg-gray-50 rounded-md border border-gray-200 overflow-hidden"
                  >
                    <div
                      className="flex items-center gap-3 p-3 cursor-pointer"
                      onClick={() => toggleSourceExpansion(index)}
                    >
                      <div className="flex-shrink-0">
                        {source.type === 'text' && (
                          <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
                          </svg>
                        )}
                        {source.type === 'document' && (
                          <svg className="h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                          </svg>
                        )}
                        {source.type === 'url' && (
                          <svg className="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                          </svg>
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-medium text-gray-900 truncate">
                          {getSourceLabel(source, index)}
                        </h4>
                        {source.url && (
                          <p className="text-xs text-gray-500 truncate">{source.url}</p>
                        )}
                      </div>

                      <span className="text-xs text-gray-500">
                        {source.token_estimate?.toLocaleString() || 0} tokens
                      </span>

                      <svg
                        className={`h-4 w-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>

                    {isExpanded && (
                      <div className="px-3 pb-3 pl-11">
                        <div className="p-3 bg-white rounded border border-gray-200 max-h-60 overflow-y-auto">
                          <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans">
                            {fullText}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No product information sources configured</p>
          )}
        </div>

        {/* Analysis History */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Analysis History ({analysisHistory.length}{activeAnalysisJob ? ' + 1 in progress' : ''})
          </h2>

          {/* Active Analysis Job */}
          {activeAnalysisJob && (
            <div className="mb-4 border border-blue-200 bg-blue-50 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-blue-900">
                      Version {(product?.analysis_version || 0) + 1}
                      <span className="ml-2 text-xs text-blue-600 font-semibold">(Analyzing...)</span>
                    </h3>
                  </div>
                  <p className="text-sm text-blue-700">
                    {activeAnalysisJob.status === JobStatus.RUNNING
                      ? activeAnalysisJob.progress_message || 'Running analysis...'
                      : activeAnalysisJob.status === JobStatus.QUEUED
                        ? 'Queued, waiting to start...'
                        : 'Starting analysis...'}
                  </p>
                  {activeAnalysisJob.status === JobStatus.RUNNING && activeAnalysisJob.progress_percent > 0 && (
                    <div className="mt-2 h-1.5 bg-blue-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all duration-300"
                        style={{ width: `${activeAnalysisJob.progress_percent}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {analysisHistory.length === 0 && !activeAnalysisJob ? (
            <div className="text-center py-8">
              <p className="text-gray-500 mb-4">No analyses yet</p>
              <button
                onClick={handleChangeSources}
                className="text-blue-600 hover:text-blue-800 font-medium"
              >
                Add sources and run analysis
              </button>
            </div>
          ) : analysisHistory.length > 0 ? (
            <div className="space-y-4">
              {analysisHistory.map((analysis) => {
                const isExpanded = expandedVersions.has(analysis.id);
                const historySources = analysis.product_source_data?.sources || [];

                return (
                  <div
                    key={analysis.id}
                    className="border border-gray-200 rounded-lg overflow-hidden"
                  >
                    <div
                      className="flex justify-between items-start p-4 cursor-pointer hover:bg-gray-50"
                      onClick={() => toggleVersionExpanded(analysis.id)}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-gray-900">
                            Version {analysis.analysis_version}
                            {analysis.analysis_version === product.analysis_version && (
                              <span className="ml-2 text-xs text-green-600 font-semibold">(Current)</span>
                            )}
                          </h3>
                        </div>
                        <p className="text-sm text-gray-500">
                          {format(new Date(analysis.created_at), 'MMM d, yyyy h:mm a')}
                        </p>
                        {historySources.length > 0 && (
                          <p className="text-xs text-gray-500 mt-1">
                            {historySources.length} {historySources.length === 1 ? 'source' : 'sources'}
                            {historySources.filter(s => s.url).length > 0 && (
                              <span className="ml-1">
                                ({historySources.filter(s => s.url).map(s => s.title || s.url).slice(0, 2).join(', ')}
                                {historySources.filter(s => s.url).length > 2 && '...'})
                              </span>
                            )}
                          </p>
                        )}
                      </div>
                      <svg
                        className={`h-5 w-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>

                    {isExpanded && (
                      <div className="border-t border-gray-200 p-4 bg-gray-50">
                        {/* Sources for this version */}
                        {historySources.length > 0 && (
                          <div className="mb-4">
                            <h4 className="text-sm font-medium text-gray-700 mb-2">Sources Used</h4>
                            <div className="space-y-1">
                              {historySources.map((source, idx) => (
                                <div key={idx} className="text-sm text-gray-600 flex items-center gap-2">
                                  <span className="font-medium">{source.type}:</span>
                                  {source.url ? (
                                    <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate">
                                      {source.title || source.url}
                                    </a>
                                  ) : source.filename ? (
                                    <span>{source.filename}</span>
                                  ) : (
                                    <span>Text description</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Analysis structure */}
                        {analysis.analyzed_structure && (
                          <div className="space-y-2">
                            <h4 className="text-sm font-medium text-gray-700">Analysis Results</h4>
                            <p className="text-sm text-gray-600">
                              {analysis.analyzed_structure.core_features?.length || 0} features •{' '}
                              {analysis.analyzed_structure.value_propositions?.length || 0} value props •{' '}
                              {analysis.analyzed_structure.competitor_search_keywords?.length || 0} keywords
                            </p>
                          </div>
                        )}

                        {/* Full description if available */}
                        {analysis.product_description && (
                          <div className="mt-4">
                            <h4 className="text-sm font-medium text-gray-700 mb-2">Consolidated Product Info</h4>
                            <div className="p-3 bg-white rounded border border-gray-200 max-h-60 overflow-y-auto">
                              <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans">
                                {analysis.product_description}
                              </pre>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      </main>

      {/* Setup Modals */}
      {showIdeaTriageSetup && (
        <IdeaTriageSetupModal
          productId={parseInt(productId!)}
          currentSettings={triageSettings}
          onClose={() => setShowIdeaTriageSetup(false)}
          onSave={(settings) => {
            setTriageSettings(settings);
            setShowIdeaTriageSetup(false);
          }}
        />
      )}

      {showCompetitiveIntelligenceSetup && (
        <CompetitiveIntelligenceSetupModal
          productId={parseInt(productId!)}
          currentConfig={agentConfig}
          onClose={() => setShowCompetitiveIntelligenceSetup(false)}
          onSave={(config) => {
            setAgentConfig(config);
            setShowCompetitiveIntelligenceSetup(false);
          }}
        />
      )}

      {/* Warning modal when no competitors selected */}
      {showNoCompetitorsWarning && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">
              No Competitors Selected
            </h3>
            <p className="text-gray-600 mb-6">
              No competitors are currently selected for deep analysis. Would you like to run market discovery first to find competitors?
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={handleRunMarketDiscovery}
                disabled={runningAction === 'market-discovery'}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
              >
                {runningAction === 'market-discovery' ? 'Running...' : 'Run Discovery Only'}
              </button>
              <button
                onClick={() => setShowNoCompetitorsWarning(false)}
                className="w-full px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
