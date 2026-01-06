/**
 * CompetitorsTab
 *
 * Manage competitors with deep analysis controls.
 * Lists competitors, allows enabling/disabling deep analysis,
 * and triggering per-competitor analysis.
 */

import { useState, useEffect, useCallback } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  getAgentCompetitors,
  enableDeepAnalysis,
  disableDeepAnalysis,
  triggerDeepAnalysis,
} from '../../../services/api';
import { AgentCompetitor } from '../../../types';

interface Props {
  productId: number;
  refreshKey?: number;
}

export default function CompetitorsTab({ productId, refreshKey }: Props) {
  const [competitors, setCompetitors] = useState<AgentCompetitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [filter, setFilter] = useState<'all' | 'enabled' | 'disabled'>('all');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchCompetitors = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getAgentCompetitors(productId);
      setCompetitors(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load competitors');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchCompetitors();
  }, [fetchCompetitors, refreshKey]);

  // Clear message after timeout
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const handleToggleDeepAnalysis = async (competitor: AgentCompetitor) => {
    setActionLoading(competitor.id);
    try {
      if (competitor.deep_analysis_enabled) {
        await disableDeepAnalysis(productId, competitor.id);
        setMessage({ type: 'success', text: `Deep analysis disabled for ${competitor.competitor_name}` });
      } else {
        await enableDeepAnalysis(productId, competitor.id);
        setMessage({ type: 'success', text: `Deep analysis enabled for ${competitor.competitor_name}` });
      }
      // Refresh list
      await fetchCompetitors();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Action failed' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRunDeepAnalysis = async (competitor: AgentCompetitor) => {
    setActionLoading(competitor.id);
    try {
      const result = await triggerDeepAnalysis(productId, competitor.id);
      setMessage({ type: 'success', text: result.message });
      // Refresh to show running status
      await fetchCompetitors();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to trigger analysis' });
    } finally {
      setActionLoading(null);
    }
  };

  const filteredCompetitors = competitors.filter(c => {
    if (filter === 'enabled') return c.deep_analysis_enabled;
    if (filter === 'disabled') return !c.deep_analysis_enabled;
    return true;
  });

  const enabledCount = competitors.filter(c => c.deep_analysis_enabled).length;

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
          <button onClick={fetchCompetitors} className="mt-2 text-red-600 hover:text-red-800 font-medium">
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
          <h2 className="text-lg font-semibold text-gray-900">Competitors</h2>
          <p className="text-sm text-gray-500">
            {competitors.length} competitors • {enabledCount} enabled for deep analysis
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as 'all' | 'enabled' | 'disabled')}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Competitors</option>
            <option value="enabled">Deep Analysis Enabled</option>
            <option value="disabled">Deep Analysis Disabled</option>
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

      {/* Competitors List */}
      {filteredCompetitors.length === 0 ? (
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <p className="mt-2 text-gray-500">
            {filter === 'all' ? 'No competitors discovered yet' : `No ${filter} competitors`}
          </p>
          {filter === 'all' && (
            <p className="text-sm text-gray-400 mt-1">
              Use "Run Analysis" → "Discover Competitors" to find competitors
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredCompetitors.map(competitor => (
            <div
              key={competitor.id}
              className="bg-gray-50 rounded-lg border border-gray-200 p-4"
            >
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                {/* Competitor Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <h3 className="font-medium text-gray-900 truncate">
                      {competitor.competitor_name}
                    </h3>
                    {competitor.deep_analysis_enabled && (
                      <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded-full">
                        Tracking
                      </span>
                    )}
                    {competitor.deep_analysis_status === 'running' && (
                      <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full animate-pulse">
                        Analyzing...
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 mt-1 text-sm text-gray-500">
                    {competitor.competitor_url && (
                      <a
                        href={competitor.competitor_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline truncate max-w-xs"
                      >
                        {competitor.competitor_url}
                      </a>
                    )}
                    <span>{competitor.feature_count} features</span>
                    {competitor.deep_analysis_last_run && (
                      <span>
                        Last analyzed {formatDistanceToNow(new Date(competitor.deep_analysis_last_run), { addSuffix: true })}
                      </span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggleDeepAnalysis(competitor)}
                    disabled={actionLoading === competitor.id}
                    className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
                      competitor.deep_analysis_enabled
                        ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        : 'bg-green-100 text-green-700 hover:bg-green-200'
                    } disabled:opacity-50`}
                  >
                    {actionLoading === competitor.id ? (
                      <span className="flex items-center gap-1">
                        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      </span>
                    ) : competitor.deep_analysis_enabled ? (
                      'Disable Tracking'
                    ) : (
                      'Enable Tracking'
                    )}
                  </button>
                  {competitor.deep_analysis_enabled && (
                    <button
                      onClick={() => handleRunDeepAnalysis(competitor)}
                      disabled={actionLoading === competitor.id || competitor.deep_analysis_status === 'running'}
                      className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Run Analysis
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
