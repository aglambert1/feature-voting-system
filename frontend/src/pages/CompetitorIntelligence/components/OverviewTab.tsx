/**
 * OverviewTab
 *
 * Dashboard showing agent status, quick stats, and recent activity.
 */

import { useState, useEffect, useCallback } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  getAgentConfig,
  getAgentCompetitors,
  getFeatureClusters,
} from '../../../services/api';
import { CompetitiveAgentConfig, AgentMode } from '../../../types';

interface Props {
  productId: number;
  refreshKey?: number;
}

interface QuickStats {
  totalCompetitors: number;
  trackingCompetitors: number;
  totalFeatures: number;
  totalClusters: number;
  highIntensityClusters: number;
}

export default function OverviewTab({ productId, refreshKey }: Props) {
  const [config, setConfig] = useState<CompetitiveAgentConfig | null>(null);
  const [stats, setStats] = useState<QuickStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);

      // Fetch all data in parallel
      const [configData, competitorsData, clustersData] = await Promise.all([
        getAgentConfig(productId),
        getAgentCompetitors(productId),
        getFeatureClusters(productId),
      ]);

      setConfig(configData);

      // Calculate stats
      const totalFeatures = competitorsData.reduce((sum, c) => sum + c.feature_count, 0);
      const highIntensityClusters = clustersData.filter(c => c.competitor_count >= 3).length;

      setStats({
        totalCompetitors: competitorsData.length,
        trackingCompetitors: competitorsData.filter(c => c.deep_analysis_enabled).length,
        totalFeatures,
        totalClusters: clustersData.length,
        highIntensityClusters,
      });

      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshKey]);

  const formatSchedule = (mode: string, schedule: string | null): string => {
    if (mode === AgentMode.MANUAL || mode === 'manual') {
      return 'Manual';
    }
    return schedule ? schedule.charAt(0).toUpperCase() + schedule.slice(1) : 'Not configured';
  };

  const formatLastRun = (date: string | null): string => {
    if (!date) return 'Never';
    return formatDistanceToNow(new Date(date), { addSuffix: true });
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
          <button onClick={fetchData} className="mt-2 text-red-600 hover:text-red-800 font-medium">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Agent Status */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Agent Status</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Product Analysis */}
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-900">Product Analysis</h3>
              <span className={`w-2 h-2 rounded-full ${config?.enabled ? 'bg-green-500' : 'bg-gray-400'}`}></span>
            </div>
            <p className="text-sm text-gray-600">
              {formatSchedule(config?.product_analysis_mode || 'manual', config?.product_analysis_schedule || null)}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Last: {formatLastRun(config?.product_analysis_last_run || null)}
            </p>
          </div>

          {/* Competitor Discovery */}
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-900">Competitor Discovery</h3>
              <span className={`w-2 h-2 rounded-full ${config?.enabled ? 'bg-green-500' : 'bg-gray-400'}`}></span>
            </div>
            <p className="text-sm text-gray-600">
              {formatSchedule(config?.competitor_discovery_mode || 'manual', config?.competitor_discovery_schedule || null)}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Last: {formatLastRun(config?.competitor_discovery_last_run || null)}
            </p>
          </div>

          {/* Deep Analysis */}
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-900">Deep Analysis</h3>
              <span className={`w-2 h-2 rounded-full ${config?.enabled ? 'bg-green-500' : 'bg-gray-400'}`}></span>
            </div>
            <p className="text-sm text-gray-600">
              {formatSchedule(config?.deep_analysis_mode || 'manual', config?.deep_analysis_schedule || null)}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Last: {formatLastRun(config?.deep_analysis_last_run || null)}
            </p>
          </div>
        </div>

        {/* Strategic Analysis Toggles */}
        {config && (
          <div className="mt-4 flex flex-wrap gap-2">
            {config.enable_pricing_analysis && (
              <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">Pricing</span>
            )}
            {config.enable_positioning_analysis && (
              <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">Positioning</span>
            )}
            {config.enable_changes_tracking && (
              <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">Changes</span>
            )}
            {config.enable_momentum_analysis && (
              <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">Momentum</span>
            )}
            {config.enable_financials_analysis && (
              <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">Financials</span>
            )}
          </div>
        )}
      </section>

      {/* Quick Stats */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Stats</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <p className="text-3xl font-bold text-gray-900">{stats?.totalCompetitors || 0}</p>
            <p className="text-sm text-gray-500">Total Competitors</p>
            {stats && stats.trackingCompetitors > 0 && (
              <p className="text-xs text-green-600 mt-1">{stats.trackingCompetitors} tracking</p>
            )}
          </div>
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <p className="text-3xl font-bold text-gray-900">{stats?.totalFeatures || 0}</p>
            <p className="text-sm text-gray-500">Features Extracted</p>
          </div>
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <p className="text-3xl font-bold text-gray-900">{stats?.totalClusters || 0}</p>
            <p className="text-sm text-gray-500">Feature Clusters</p>
          </div>
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <p className="text-3xl font-bold text-orange-600">{stats?.highIntensityClusters || 0}</p>
            <p className="text-sm text-gray-500">High Intensity</p>
            <p className="text-xs text-gray-400 mt-1">3+ competitors</p>
          </div>
        </div>
      </section>

      {/* Configuration Summary */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Intensity Settings</h2>
        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium text-gray-700">Feature Similarity Threshold</p>
              <p className="text-lg font-semibold text-gray-900">
                {((config?.intensity_similarity_threshold || 0.75) * 100).toFixed(0)}%
              </p>
              <p className="text-xs text-gray-500">Higher = more precise clusters</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-700">Auto-Idea Generation Threshold</p>
              <p className="text-lg font-semibold text-gray-900">
                {config?.intensity_idea_threshold || 3} competitors
              </p>
              <p className="text-xs text-gray-500">Minimum competitors for auto-generation</p>
            </div>
          </div>
        </div>
      </section>

      {/* Getting Started (if no competitors) */}
      {stats && stats.totalCompetitors === 0 && (
        <section className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">Getting Started</h3>
          <p className="text-blue-700 mb-4">
            Start by discovering competitors for your product. Use the "Run Analysis" dropdown above.
          </p>
          <ol className="list-decimal list-inside text-sm text-blue-700 space-y-2">
            <li>Click "Run Analysis" → "Discover Competitors" to find competitors</li>
            <li>Go to the Competitors tab to enable tracking on specific competitors</li>
            <li>Run deep analysis on tracked competitors to extract features</li>
            <li>View feature clusters and competitive intensity in the Features tab</li>
          </ol>
        </section>
      )}
    </div>
  );
}
