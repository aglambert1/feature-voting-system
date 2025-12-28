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
import { useParams, useNavigate, Link } from 'react-router-dom';
import Navigation from '../components/Navigation';
import ReviewQueueCard from '../components/ReviewQueueCard';
import MonitoringConfigPanel from '../components/MonitoringConfigPanel';
import JobStatusCard from '../components/JobStatusCard';
import {
  getReviewQueueStats,
  getMonitoringConfig,
  getProductJobs,
  triggerMonitoring,
} from '../services/api';
import type { PMReviewQueueStats, MonitoringConfig, QueueJob, ApiError } from '../types';
import { JobStatus } from '../types';

const ProductDashboardPage = () => {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();

  const [productName, setProductName] = useState<string>('');
  const [stats, setStats] = useState<PMReviewQueueStats | null>(null);
  const [monitoringConfig, setMonitoringConfig] = useState<MonitoringConfig | null>(null);
  const [recentJobs, setRecentJobs] = useState<QueueJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showMonitoringConfig, setShowMonitoringConfig] = useState(false);
  const [triggeringMonitoring, setTriggeringMonitoring] = useState(false);

  const numProductId = productId ? parseInt(productId) : null;

  const fetchDashboardData = useCallback(async () => {
    if (!numProductId) return;

    setLoading(true);
    setError('');

    try {
      const [statsData, configData, jobsData] = await Promise.all([
        getReviewQueueStats(numProductId),
        getMonitoringConfig(numProductId),
        getProductJobs(numProductId, 5),
      ]);

      setStats(statsData);
      setMonitoringConfig(configData);
      setRecentJobs(jobsData);
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
                  linkTo={`/review-queue?type=idea&product_id=${productId}`}
                />
                <ReviewQueueCard
                  title="Competitive Alerts"
                  count={stats?.by_type?.competitive_alert || 0}
                  icon="alerts"
                  linkTo={`/review-queue?type=competitive_alert&product_id=${productId}`}
                />
                <ReviewQueueCard
                  title="Reports"
                  count={stats?.by_type?.report || 0}
                  icon="reports"
                  linkTo={`/review-queue?type=report&product_id=${productId}`}
                />
              </div>
            </div>

            {/* Agent Status */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-medium text-gray-900">Agent Status</h2>
                <button
                  onClick={() => setShowMonitoringConfig(!showMonitoringConfig)}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  {showMonitoringConfig ? 'Hide Config' : 'Configure'}
                </button>
              </div>

              {/* Monitoring Status Card */}
              <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className={`inline-block w-3 h-3 rounded-full ${getMonitoringStatusColor()}`}></span>
                    <div>
                      <div className="font-medium text-gray-900">Competitive Monitor</div>
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

              {/* Monitoring Config Panel */}
              {showMonitoringConfig && (
                <MonitoringConfigPanel
                  productId={numProductId}
                  onConfigChange={(config) => setMonitoringConfig(config)}
                />
              )}
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
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={handleTriggerMonitoring}
                  disabled={triggeringMonitoring || !monitoringConfig?.monitoring_enabled}
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Run Competitive Scan
                </button>
                <Link
                  to={`/product-intelligence/products/${productId}`}
                  className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
                >
                  View Comparison
                </Link>
                <Link
                  to={`/review-queue?product_id=${productId}`}
                  className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
                >
                  Review All Items
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
