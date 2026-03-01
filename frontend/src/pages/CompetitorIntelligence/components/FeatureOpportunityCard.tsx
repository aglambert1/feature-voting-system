/**
 * FeatureOpportunityCard
 *
 * Individual card for displaying a feature opportunity with:
 * - Priority score visualization
 * - Expandable score breakdown
 * - Market context
 * - User sentiment
 * - High-impact badge
 * - Selection checkbox
 */

import { useState } from 'react';
import type { FeatureOpportunity } from '../../../types';

interface Props {
  opportunity: FeatureOpportunity;
  index: number;
  isSelected: boolean;
  onSelect: (index: number) => void;
  hasIdea: boolean;
  highImpactRank?: number;
}

export default function FeatureOpportunityCard({
  opportunity,
  index,
  isSelected,
  onSelect,
  hasIdea,
  highImpactRank,
}: Props) {
  const priorityPercent = Math.round(opportunity.priority_score * 100);
  const [showScoreDetails, setShowScoreDetails] = useState(false);

  // Determine high-impact badge color
  const getHighImpactBadge = () => {
    if (!highImpactRank) return null;
    if (highImpactRank === 1) {
      return <span className="text-xs font-medium text-red-700 bg-red-100 px-2 py-1 rounded">🔴 HIGH IMPACT</span>;
    }
    if (highImpactRank <= 3) {
      return <span className="text-xs font-medium text-yellow-700 bg-yellow-100 px-2 py-1 rounded">🟡 HIGH IMPACT</span>;
    }
    return null;
  };

  // Get priority bar color based on score
  const getPriorityBarColor = () => {
    if (priorityPercent >= 80) return 'bg-red-500';
    if (priorityPercent >= 60) return 'bg-yellow-500';
    if (priorityPercent >= 40) return 'bg-blue-500';
    return 'bg-gray-400';
  };

  // Get priority level label
  const getPriorityLevel = () => {
    if (priorityPercent >= 80) return 'Critical';
    if (priorityPercent >= 60) return 'High';
    if (priorityPercent >= 40) return 'Medium';
    return 'Low';
  };

  return (
    <div
      className={`border rounded-lg p-4 transition-colors ${
        isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'
      }`}
    >
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onSelect(index)}
          className="mt-1 w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
        />
        <div className="flex-1">
          {/* Header with title and badges */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h4 className="font-medium text-gray-900">{opportunity.feature_name}</h4>
            <div className="flex items-center gap-2">
              {getHighImpactBadge()}
              {hasIdea && (
                <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                  ✓ Idea submitted for voting
                </span>
              )}
            </div>
          </div>

          {/* Priority Score Bar */}
          <div className="mt-3 mb-2">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-gray-500">Priority:</span>
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${getPriorityBarColor()}`}
                      style={{ width: `${priorityPercent}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-gray-700">{priorityPercent}%</span>
                  <button
                    onClick={() => setShowScoreDetails(!showScoreDetails)}
                    className="text-xs text-blue-600 hover:text-blue-800 ml-1"
                  >
                    {showScoreDetails ? 'Hide details' : 'Score details'}
                  </button>
                </div>
              </div>
              <div className="text-xs text-gray-500">
                Market: {opportunity.market_context}
              </div>
            </div>
          </div>

          {/* Expandable Score Breakdown */}
          {showScoreDetails && (
            <div className="mb-4 bg-gray-50 border border-gray-200 rounded-lg p-3">
              <h5 className="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wide">Priority Score Breakdown</h5>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center justify-between bg-white rounded px-2 py-1.5">
                  <span className="text-gray-600">Priority Level</span>
                  <span className={`font-medium ${
                    priorityPercent >= 80 ? 'text-red-600' :
                    priorityPercent >= 60 ? 'text-yellow-600' :
                    priorityPercent >= 40 ? 'text-blue-600' : 'text-gray-500'
                  }`}>{getPriorityLevel()}</span>
                </div>
                <div className="flex items-center justify-between bg-white rounded px-2 py-1.5">
                  <span className="text-gray-600">Competitors</span>
                  <span className="font-medium text-gray-900">{opportunity.competitors_with_feature.length} have this</span>
                </div>
                <div className="flex items-center justify-between bg-white rounded px-2 py-1.5">
                  <span className="text-gray-600">Evidence Sources</span>
                  <span className="font-medium text-gray-900">{opportunity.source_evidence?.length || 0} sources</span>
                </div>
                <div className="flex items-center justify-between bg-white rounded px-2 py-1.5">
                  <span className="text-gray-600">Market Position</span>
                  <span className="font-medium text-gray-900">{opportunity.market_context || 'N/A'}</span>
                </div>
              </div>
              {opportunity.priority_rationale && (
                <div className="mt-2 pt-2 border-t border-gray-200">
                  <p className="text-xs text-gray-600">
                    <span className="font-medium">Reasoning:</span> {opportunity.priority_rationale}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Summary */}
          <p className="text-sm text-gray-700 mb-2">
            <span className="font-medium">Summary:</span> {opportunity.summary}
          </p>

          {/* User Value */}
          <p className="text-sm text-gray-700 mb-2">
            <span className="font-medium">User Value:</span> {opportunity.user_value}
          </p>

          {/* User Sentiment */}
          {opportunity.user_sentiment && (
            <div className="text-sm text-gray-600 mb-2">
              <span className="font-medium">User Sentiment:</span>{' '}
              <span className="text-gray-700">{opportunity.user_sentiment}</span>
            </div>
          )}

          {/* Source Evidence */}
          {opportunity.source_evidence && opportunity.source_evidence.length > 0 && (
            <div className="mt-2 text-sm">
              <span className="font-medium text-gray-600">Evidence:</span>
              <ul className="mt-1 space-y-1">
                {opportunity.source_evidence.slice(0, 2).map((evidence, i) => (
                  <li key={i} className="text-gray-500 text-xs italic pl-2 border-l-2 border-gray-200">
                    "{evidence}"
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Competitors with feature */}
          <div className="mt-3 text-sm text-gray-500">
            <span className="font-medium">Competitors with feature:</span>{' '}
            {opportunity.competitors_with_feature.join(', ')}
          </div>
        </div>
      </div>
    </div>
  );
}
