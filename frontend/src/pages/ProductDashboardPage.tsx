/**
 * ProductDashboardPage
 *
 * Central hub for a single product's insights and actions.
 * Shows:
 * - Review queue stats (ideas, alerts, reports)
 * - Agent status (monitoring)
 * - Recent activity
 * - Quick actions
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import Navigation from '../components/Navigation';
import ReviewQueueCard from '../components/ReviewQueueCard';
import JobStatusCard from '../components/JobStatusCard';
import {
  getReviewQueueStats,
  getMonitoringConfig,
  getProductJobs,
  triggerMonitoring,
  getTriageSettings,
  updateTriageSettings,
  getIdeaFunnel,
  getCompetitorAlerts,
  markAllAlertsRead,
  getAgentCompetitors,
  triggerCompetitiveAnalysisV2,
} from '../services/api';
import type { CompetitorAlert } from '../services/api';
import type { PMReviewQueueStats, MonitoringConfig, QueueJob, ApiError, TriageSettings, IdeaFunnelData, AgentCompetitor } from '../types';
import { JobStatus } from '../types';

const ProductDashboardPage = () => {
  const { productId } = useParams<{ productId: string }>();

  const [productName, setProductName] = useState<string>('');
  const [stats, setStats] = useState<PMReviewQueueStats | null>(null);
  const [monitoringConfig, setMonitoringConfig] = useState<MonitoringConfig | null>(null);
  const [recentJobs, setRecentJobs] = useState<QueueJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [triggeringMonitoring, setTriggeringMonitoring] = useState(false);

  // Triage automation state
  const [triageSettings, setTriageSettings] = useState<TriageSettings | null>(null);
  const [savingTriageSettings, setSavingTriageSettings] = useState(false);
  const [triageError, setTriageError] = useState('');

  // Funnel and alert digest state
  const [funnelData, setFunnelData] = useState<IdeaFunnelData | null>(null);
  const [alerts, setAlerts] = useState<CompetitorAlert[]>([]);
  const [dismissingAlerts, setDismissingAlerts] = useState(false);

  // Competitive analysis state
  const [runningAnalysis, setRunningAnalysis] = useState(false);
  const [analysisMessage, setAnalysisMessage] = useState('');

  const numProductId = productId ? parseInt(productId) : null;

  const fetchDashboardData = useCallback(async () => {
    if (!numProductId) return;

    setLoading(true);
    setError('');

    try {
      const [statsData, configData, jobsData, triageData, funnelResult, alertsResult] = await Promise.all([
        getReviewQueueStats(numProductId),
        getMonitoringConfig(numProductId),
        getProductJobs(numProductId, 5),
        getTriageSettings(numProductId),
        getIdeaFunnel(numProductId).catch(() => null),
        getCompetitorAlerts(numProductId, true).catch(() => []),
      ]);

      setStats(statsData);
      setMonitoringConfig(configData);
      setRecentJobs(jobsData);
      setTriageSettings(triageData);
      setFunnelData(funnelResult);
      setAlerts(alertsResult.slice(0, 5));
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, [numProductId]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Fetch product name from context or storage
  useEffect(() => {
    const storedProducts = sessionStorage.getItem('products');
    if (storedProducts && numProductId) {
      try {
        const products = JSON.parse(storedProducts);
        const product = products.find((p: any) => p.id === numProductId);
        if (product) {
          setProductName(product.product_name);
        }
      } catch {
        // Ignore parse errors
      }
    }
  }, [numProductId]);

  const handleTriggerMonitoring = async () => {
    if (!numProductId) return;

    setTriggeringMonitoring(true);
    try {
      await triggerMonitoring(numProductId);
      // Refresh jobs to show the new job
      const jobsData = await getProductJobs(numProductId, 5);
      setRecentJobs(jobsData);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setTriggeringMonitoring(false);
    }
  };

  const handleDismissAllAlerts = async () => {
    if (!numProductId) return;
    setDismissingAlerts(true);
    try {
      await markAllAlertsRead(numProductId);
      setAlerts([]);
    } catch (err) {
      console.error('Failed to dismiss alerts:', err);
    } finally {
      setDismissingAlerts(false);
    }
  };

  const handleTriageToggle = async (enabled: boolean) => {
    if (!numProductId || !triageSettings) return;

    setSavingTriageSettings(true);
    setTriageError('');
    try {
      const updated = await updateTriageSettings(numProductId, {
        auto_enabled: enabled,
        auto_threshold: triageSettings.auto_threshold,
      });
      setTriageSettings(updated);
    } catch (err) {
      setTriageError((err as ApiError).message || 'Failed to update settings');
    } finally {
      setSavingTriageSettings(false);
    }
  };

  const handleThresholdChange = async (threshold: number) => {
    if (!numProductId || !triageSettings) return;

    setSavingTriageSettings(true);
    setTriageError('');
    try {
      const updated = await updateTriageSettings(numProductId, {
        auto_enabled: triageSettings.auto_enabled,
        auto_threshold: threshold,
      });
      setTriageSettings(updated);
    } catch (err) {
      setTriageError((err as ApiError).message || 'Failed to update settings');
    } finally {
      setSavingTriageSettings(false);
    }
  };

  const handleRunCompetitiveAnalysis = async () => {
    if (!numProductId) return;

    setRunningAnalysis(true);
    setAnalysisMessage('');
    try {
      const competitors = await getAgentCompetitors(numProductId);
      const trackedCompetitors = competitors.filter((c: AgentCompetitor) => c.tracked);

      if (trackedCompetitors.length > 0) {
        await triggerCompetitiveAnalysisV2(numProductId);
        setAnalysisMessage(`Auditing tracked competitors.`);
        const jobsData = await getProductJobs(numProductId, 5);
        setRecentJobs(jobsData);
      } else {
        setAnalysisMessage('No tracked competitors. Track competitors in the Intelligence Hub first.');
      }
    } catch (err) {
      setError((err as ApiError).message || 'Failed to start analysis');
    } finally {
      setRunningAnalysis(false);
    }
  };

  const getMonitoringStatusColor = () => {
    if (!monitoringConfig) return 'bg-gray-400';
    if (!monitoringConfig.monitoring_enabled) return 'bg-gray-400';

    // Check if there's an active monitoring job
    const hasActiveJob = recentJobs.some(
      (job) =>
        job.job_type === 'competitive_monitoring' &&
        (job.status === JobStatus.RUNNING || job.status === JobStatus.QUEUED)
    );

    if (hasActiveJob) return 'bg-blue-500 animate-pulse';
    return 'bg-green-500';
  };

  const getMonitoringStatusText = () => {
    if (!monitoringConfig) return 'Unknown';
    if (!monitoringConfig.monitoring_enabled) return 'Disabled';

    const hasActiveJob = recentJobs.some(
      (job) =>
        job.job_type === 'competitive_monitoring' &&
        (job.status === JobStatus.RUNNING || job.status === JobStatus.QUEUED)
    );

    if (hasActiveJob) return 'Running';
    return 'Active';
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (!numProductId) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <main className="max-w-7xl mx-auto py-6 px-4">
          <p className="text-red-600">Invalid product ID</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link
                to="/product-intelligence"
                className="text-gray-500 hover:text-gray-700"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {productName || 'Product Dashboard'}
                </h1>
                <p className="text-gray-600">
                  Review queues, monitoring status, and recent activity
                </p>
              </div>
            </div>
            <Link
              to={`/product-intelligence/products/${productId}/settings`}
              className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
            >
              Settings
            </Link>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-2 text-gray-500">Loading dashboard...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-600">{error}</p>
            <button
              onClick={fetchDashboardData}
              className="mt-2 text-sm text-red-700 hover:text-red-800 underline"
            >
              Try again
            </button>
          </div>
        )}

        {!loading && !error && (
          <>
            {/* Review Queues */}
            <div className="mb-8">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Review Queues</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <ReviewQueueCard
                  title="Ideas"
                  count={stats?.by_type?.idea || 0}
                  icon="ideas"
                  linkTo={`/ideas?product=${productId}&from=dashboard`}
                />
                <ReviewQueueCard
                  title="Competitive Alerts"
                  count={stats?.by_type?.competitive_alert || 0}
                  icon="alerts"
                  linkTo={`/product-intelligence/products/${productId}`}
                />
                <ReviewQueueCard
                  title="Reports"
                  count={stats?.by_type?.report || 0}
                  icon="reports"
                  linkTo={`/product-intelligence/products/${productId}`}
                />
              </div>
            </div>

            {/* Idea Funnel */}
            {funnelData && funnelData.total_submitted > 0 && (
              <div className="mb-8">
                <h2 className="text-lg font-medium text-gray-900 mb-4">Idea Lifecycle Funnel</h2>
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  {/* Funnel Bar */}
                  <div className="mb-4">
                    <div className="flex rounded-lg overflow-hidden h-10">
                      {(() => {
                        const total = funnelData.total_submitted || 1;
                        const segments = [
                          { key: 'pending', label: 'Pending', count: funnelData.status_counts.pending || 0, color: '#F59E0B' },
                          { key: 'needs_review', label: 'Needs Review', count: funnelData.status_counts.needs_review || 0, color: '#3B82F6' },
                          { key: 'accepted', label: 'Accepted', count: funnelData.status_counts.accepted || 0, color: '#10B981' },
                          ...Object.entries(funnelData.lifecycle_counts).map(([slug, count]) => ({
                            key: slug,
                            label: slug.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
                            count,
                            color: slug === 'on_roadmap' ? '#3B82F6' : slug === 'delivered' ? '#10B981' : '#8B5CF6',
                          })),
                          { key: 'rejected', label: 'Rejected', count:
                            (funnelData.status_counts.duplicate || 0) +
                            (funnelData.status_counts.feature_exists || 0) +
                            (funnelData.status_counts.not_appropriate || 0) +
                            (funnelData.status_counts.merged || 0),
                            color: '#9CA3AF' },
                        ].filter(s => s.count > 0);

                        return segments.map(seg => (
                          <div
                            key={seg.key}
                            className="flex items-center justify-center text-xs font-medium text-white min-w-[40px]"
                            style={{
                              backgroundColor: seg.color,
                              width: `${Math.max((seg.count / total) * 100, 5)}%`,
                            }}
                            title={`${seg.label}: ${seg.count}`}
                          >
                            {seg.count}
                          </div>
                        ));
                      })()}
                    </div>
                  </div>

                  {/* Legend */}
                  <div className="flex flex-wrap gap-4 text-sm">
                    {[
                      { label: 'Pending', count: funnelData.status_counts.pending || 0, color: '#F59E0B' },
                      { label: 'Needs Review', count: funnelData.status_counts.needs_review || 0, color: '#3B82F6' },
                      { label: 'Accepted', count: funnelData.status_counts.accepted || 0, color: '#10B981' },
                      ...Object.entries(funnelData.lifecycle_counts).map(([slug, count]) => ({
                        label: slug.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
                        count,
                        color: slug === 'on_roadmap' ? '#3B82F6' : slug === 'delivered' ? '#10B981' : '#8B5CF6',
                      })),
                      { label: 'Rejected/Duplicate', count:
                        (funnelData.status_counts.duplicate || 0) +
                        (funnelData.status_counts.feature_exists || 0) +
                        (funnelData.status_counts.not_appropriate || 0) +
                        (funnelData.status_counts.merged || 0),
                        color: '#9CA3AF' },
                    ].map(item => (
                      <div key={item.label} className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                        <span className="text-gray-600">{item.label}: <strong>{item.count}</strong></span>
                      </div>
                    ))}
                  </div>

                  {/* Triage Stats */}
                  <div className="mt-4 pt-4 border-t border-gray-100 text-sm text-gray-500">
                    Total submitted: {funnelData.total_submitted}
                    <span className="mx-2">|</span>
                    Auto-triaged: {funnelData.auto_triaged_count}
                    <span className="mx-2">|</span>
                    Manual: {funnelData.manual_triaged_count}
                  </div>
                </div>
              </div>
            )}

            {/* Alert Digest */}
            {alerts.length > 0 && (
              <div className="mb-8">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-medium text-gray-900">Unread Alerts</h2>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={handleDismissAllAlerts}
                      disabled={dismissingAlerts}
                      className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-50"
                    >
                      {dismissingAlerts ? 'Dismissing...' : 'Dismiss All'}
                    </button>
                    <Link
                      to={`/product-intelligence/products/${productId}/intelligence?tab=competitor-reports`}
                      className="text-sm text-blue-600 hover:text-blue-800"
                    >
                      View all alerts →
                    </Link>
                  </div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
                  {alerts.map((alert) => (
                    <div key={alert.id} className="flex items-start gap-3 p-4">
                      <span className={`mt-0.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                        alert.alert_type === 'new_competitor' ? 'bg-green-500'
                        : alert.alert_type === 'competitor_disappeared' ? 'bg-red-500'
                        : 'bg-orange-500'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-gray-900">{alert.competitor_name}</span>
                        <p className="text-sm text-gray-500 truncate">{alert.message}</p>
                      </div>
                      <span className="text-xs text-gray-400 whitespace-nowrap">
                        {formatDate(alert.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Agent Status */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-medium text-gray-900">Agent Status</h2>
              </div>

              {/* Competitive Discovery Agent Card */}
              <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className={`inline-block w-3 h-3 rounded-full ${getMonitoringStatusColor()}`}></span>
                    <div>
                      <div className="font-medium text-gray-900">Competitive Discovery Agent</div>
                      <div className="text-sm text-gray-500">
                        {getMonitoringStatusText()}
                        {monitoringConfig?.last_monitored_at && (
                          <> · Last run: {formatDate(monitoringConfig.last_monitored_at)}</>
                        )}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={handleTriggerMonitoring}
                    disabled={triggeringMonitoring || !monitoringConfig?.monitoring_enabled}
                    className="px-3 py-1.5 text-sm text-blue-600 border border-blue-600 rounded hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {triggeringMonitoring ? 'Starting...' : 'Run Now'}
                  </button>
                </div>
              </div>

              {/* Opportunity Synthesis Agent Card */}
              <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className="inline-block w-3 h-3 rounded-full bg-gray-400"></span>
                    <div>
                      <div className="font-medium text-gray-900">Opportunity Synthesis Agent</div>
                      <div className="text-sm text-gray-500">
                        Coming soon · Combines competitive, customer, and internal signals
                      </div>
                    </div>
                  </div>
                  <button
                    disabled={true}
                    className="px-3 py-1.5 text-sm text-gray-400 border border-gray-300 rounded cursor-not-allowed"
                  >
                    Run Synthesis
                  </button>
                </div>
              </div>

            </div>

            {/* Idea Triage Automation */}
            <div className="mb-8">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Idea Triage Automation</h2>
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                {triageError && (
                  <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-600 text-sm">
                    {triageError}
                  </div>
                )}

                {/* Enable Toggle */}
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => handleTriageToggle(!triageSettings?.auto_enabled)}
                      disabled={savingTriageSettings || !triageSettings}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                        triageSettings?.auto_enabled ? 'bg-blue-600' : 'bg-gray-200'
                      } ${savingTriageSettings ? 'opacity-50 cursor-not-allowed' : ''}`}
                      role="switch"
                      aria-checked={triageSettings?.auto_enabled || false}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          triageSettings?.auto_enabled ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                    <div>
                      <div className="font-medium text-gray-900">Enable automatic responses</div>
                      <div className="text-sm text-gray-500">
                        AI will automatically respond to ideas when confidence exceeds threshold
                      </div>
                    </div>
                  </div>
                  {savingTriageSettings && (
                    <div className="text-sm text-gray-500">Saving...</div>
                  )}
                </div>

                {/* Confidence Threshold Slider */}
                <div className={triageSettings?.auto_enabled ? '' : 'opacity-50 pointer-events-none'}>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-gray-700">
                      Confidence threshold
                    </label>
                    <span className="text-sm font-semibold text-blue-600">
                      {Math.round((triageSettings?.auto_threshold || 0.9) * 100)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="50"
                    max="99"
                    value={Math.round((triageSettings?.auto_threshold || 0.9) * 100)}
                    onChange={(e) => {
                      // Update local state immediately for smooth slider
                      if (triageSettings) {
                        setTriageSettings({
                          ...triageSettings,
                          auto_threshold: parseInt(e.target.value) / 100,
                        });
                      }
                    }}
                    onMouseUp={(e) => handleThresholdChange(parseInt((e.target as HTMLInputElement).value) / 100)}
                    onTouchEnd={(e) => handleThresholdChange(parseInt((e.target as HTMLInputElement).value) / 100)}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    disabled={!triageSettings?.auto_enabled || savingTriageSettings}
                  />
                  <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>50% (More auto-responses)</span>
                    <span>99% (Fewer auto-responses)</span>
                  </div>
                </div>

                {/* Info Box */}
                <div className="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-lg">
                  <div className="flex items-start space-x-3">
                    <svg className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <div className="text-sm text-blue-800">
                      <p className="font-medium mb-1">How it works</p>
                      <p>
                        When enabled, the AI will analyze each submitted idea and automatically respond
                        if it's confident about the appropriate action (accept, mark as duplicate, etc.).
                        Auto-responded ideas are marked with a robot icon and can be reviewed or changed at any time.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Recent Activity / Jobs */}
            <div className="mb-8">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h2>
              {recentJobs.length === 0 ? (
                <div className="bg-white border border-gray-200 rounded-lg p-6 text-center text-gray-500">
                  No recent activity
                </div>
              ) : (
                <div className="space-y-3">
                  {recentJobs.map((job) => (
                    <JobStatusCard
                      key={job.job_uuid}
                      jobUuid={job.job_uuid}
                      compact
                      showDetails={false}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Quick Actions */}
            <div>
              <h2 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h2>
              {analysisMessage && (
                <div className="mb-3 bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
                  {analysisMessage}
                </div>
              )}
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={handleRunCompetitiveAnalysis}
                  disabled={runningAnalysis}
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {runningAnalysis ? 'Starting...' : 'Run Competitive Analysis'}
                </button>
                <button
                  onClick={handleTriggerMonitoring}
                  disabled={triggeringMonitoring || !monitoringConfig?.monitoring_enabled}
                  className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Run Competitive Scan
                </button>
                <Link
                  to={`/product-intelligence/products/${productId}/intelligence`}
                  className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
                >
                  Intelligence Hub
                </Link>
                <Link
                  to={`/ideas?product=${productId}&from=dashboard`}
                  className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
                >
                  Review Ideas
                </Link>
              </div>
            </div>

          </>
        )}
      </main>
    </div>
  );
};

export default ProductDashboardPage;
