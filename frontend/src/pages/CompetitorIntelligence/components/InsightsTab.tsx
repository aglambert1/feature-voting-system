/**
 * InsightsTab
 *
 * Display strategic analysis results across all competitors:
 * - Pricing comparison
 * - Positioning insights
 * - Recent changes
 * - Momentum indicators
 */

import { useState, useEffect, useCallback } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  getAgentCompetitors,
  getPricingAnalysis,
  getPositioningAnalysis,
  getMomentumAnalysis,
  getChangeEvents,
} from '../../../services/api';
import {
  AgentCompetitor,
  PricingAnalysis,
  PositioningAnalysis,
  MomentumAnalysis,
  ChangeEvent,
} from '../../../types';

interface Props {
  productId: number;
  refreshKey?: number;
}

interface CompetitorInsights {
  competitor: AgentCompetitor;
  pricing: PricingAnalysis | null;
  positioning: PositioningAnalysis | null;
  momentum: MomentumAnalysis | null;
  recentChanges: ChangeEvent[];
}

export default function InsightsTab({ productId, refreshKey }: Props) {
  const [insights, setInsights] = useState<CompetitorInsights[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedView, setSelectedView] = useState<'pricing' | 'positioning' | 'momentum' | 'changes'>('pricing');

  const fetchInsights = useCallback(async () => {
    try {
      setLoading(true);

      // First get all competitors with deep analysis enabled
      const competitors = await getAgentCompetitors(productId, true);

      // Fetch insights for each competitor (in parallel per competitor)
      const insightsPromises = competitors.map(async (competitor) => {
        const [pricing, positioning, momentum, changes] = await Promise.all([
          getPricingAnalysis(productId, competitor.id).catch(() => null),
          getPositioningAnalysis(productId, competitor.id).catch(() => null),
          getMomentumAnalysis(productId, competitor.id).catch(() => null),
          getChangeEvents(productId, competitor.id, 5).catch(() => []),
        ]);

        return {
          competitor,
          pricing,
          positioning,
          momentum,
          recentChanges: changes,
        };
      });

      const results = await Promise.all(insightsPromises);
      setInsights(results);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load insights');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights, refreshKey]);

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
          <button onClick={fetchInsights} className="mt-2 text-red-600 hover:text-red-800 font-medium">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (insights.length === 0) {
    return (
      <div className="p-6">
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p className="mt-2 text-gray-500">No strategic insights available</p>
          <p className="text-sm text-gray-400 mt-1">
            Enable deep analysis on competitors and run strategic analysis to see insights
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* View Toggle */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
        {[
          { id: 'pricing', label: 'Pricing' },
          { id: 'positioning', label: 'Positioning' },
          { id: 'momentum', label: 'Momentum' },
          { id: 'changes', label: 'Recent Changes' },
        ].map((view) => (
          <button
            key={view.id}
            onClick={() => setSelectedView(view.id as typeof selectedView)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              selectedView === view.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {view.label}
          </button>
        ))}
      </div>

      {/* Pricing View */}
      {selectedView === 'pricing' && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Competitor</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Free Tier</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Trial</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Enterprise</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tiers</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {insights.map(({ competitor, pricing }) => (
                <tr key={competitor.id}>
                  <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {competitor.competitor_name}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                    {pricing?.pricing_model || '-'}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap text-center">
                    {pricing ? (
                      pricing.has_free_tier ? (
                        <span className="text-green-600">✓</span>
                      ) : (
                        <span className="text-gray-400">✗</span>
                      )
                    ) : '-'}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap text-center text-sm">
                    {pricing ? (
                      pricing.has_trial ? (
                        <span className="text-green-600">{pricing.trial_days ? `${pricing.trial_days}d` : '✓'}</span>
                      ) : (
                        <span className="text-gray-400">✗</span>
                      )
                    ) : '-'}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap text-center">
                    {pricing ? (
                      pricing.has_enterprise ? (
                        <span className="text-green-600">✓</span>
                      ) : (
                        <span className="text-gray-400">✗</span>
                      )
                    ) : '-'}
                  </td>
                  <td className="px-4 py-4 text-sm text-gray-500">
                    {pricing?.pricing_tiers ? (
                      <span>{pricing.pricing_tiers.length} tiers</span>
                    ) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Positioning View */}
      {selectedView === 'positioning' && (
        <div className="space-y-4">
          {insights.map(({ competitor, positioning }) => (
            <div key={competitor.id} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <h3 className="font-medium text-gray-900 mb-2">{competitor.competitor_name}</h3>
              {positioning ? (
                <div className="space-y-3">
                  {positioning.tagline && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Tagline</p>
                      <p className="text-sm text-gray-900 italic">"{positioning.tagline}"</p>
                    </div>
                  )}
                  {positioning.market_segment && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Market Segment</p>
                      <p className="text-sm text-gray-700">{positioning.market_segment}</p>
                    </div>
                  )}
                  {positioning.target_audience && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Target Audience</p>
                      <p className="text-sm text-gray-700">{positioning.target_audience}</p>
                    </div>
                  )}
                  {positioning.value_propositions && positioning.value_propositions.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase mb-1">Value Propositions</p>
                      <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                        {positioning.value_propositions.slice(0, 3).map((vp, idx) => (
                          <li key={idx}>{vp}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-400">No positioning data available</p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Momentum View */}
      {selectedView === 'momentum' && (
        <div className="space-y-4">
          {insights.map(({ competitor, momentum }) => (
            <div key={competitor.id} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">{competitor.competitor_name}</h3>
                {momentum && (
                  <span className={`px-2 py-1 rounded-full text-sm font-medium ${getMomentumColor(momentum.momentum_trend)}`}>
                    {getMomentumIcon(momentum.momentum_trend)} {momentum.momentum_trend}
                  </span>
                )}
              </div>
              {momentum ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-500">Score:</span>
                    <div className="flex-1 bg-gray-200 rounded-full h-2 max-w-xs">
                      <div
                        className="bg-blue-600 h-2 rounded-full"
                        style={{ width: `${momentum.momentum_score * 100}%` }}
                      ></div>
                    </div>
                    <span className="text-gray-700">{(momentum.momentum_score * 100).toFixed(0)}%</span>
                  </div>
                  {momentum.customer_growth_trend && (
                    <p className="text-sm text-gray-600">
                      Customer Growth: <span className="font-medium">{momentum.customer_growth_trend}</span>
                    </p>
                  )}
                  {momentum.release_velocity && (
                    <p className="text-sm text-gray-600">
                      Release Velocity: <span className="font-medium">{momentum.release_velocity}</span>
                    </p>
                  )}
                  {momentum.analysis_summary && (
                    <p className="text-sm text-gray-500 mt-2">{momentum.analysis_summary}</p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-400">No momentum data available</p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Changes View */}
      {selectedView === 'changes' && (
        <div className="space-y-4">
          {insights.flatMap(({ competitor, recentChanges }) =>
            recentChanges.map((change) => (
              <div key={change.id} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <span className="text-xs text-gray-500">{competitor.competitor_name}</span>
                    <h3 className="font-medium text-gray-900">{change.event_title}</h3>
                  </div>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                    change.impact_level === 'major' ? 'bg-red-100 text-red-700' :
                    change.impact_level === 'minor' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-gray-100 text-gray-700'
                  }`}>
                    {change.impact_level}
                  </span>
                </div>
                {change.event_description && (
                  <p className="text-sm text-gray-600 mb-2">{change.event_description}</p>
                )}
                <div className="flex items-center gap-3 text-xs text-gray-400">
                  <span>{change.event_type}</span>
                  <span>•</span>
                  <span>{change.source_type}</span>
                  <span>•</span>
                  <span>{formatDistanceToNow(new Date(change.detected_at), { addSuffix: true })}</span>
                </div>
              </div>
            ))
          )}
          {insights.every(i => i.recentChanges.length === 0) && (
            <div className="text-center py-8">
              <p className="text-gray-500">No recent changes detected</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
