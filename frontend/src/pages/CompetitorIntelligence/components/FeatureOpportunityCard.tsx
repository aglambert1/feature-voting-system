/**
 * FeatureOpportunityCard
 *
 * Individual card for displaying a feature opportunity with:
 * - Priority score visualization
 * - Market context
 * - User sentiment
 * - High-impact badge
 * - Selection checkbox
 */

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
          <div className="mt-3 mb-4">
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
                </div>
              </div>
              <div className="text-xs text-gray-500">
                Market: {opportunity.market_context}
              </div>
            </div>
          </div>

          {/* Why this score / Priority Rationale */}
          {opportunity.priority_rationale && (
            <p className="text-sm text-gray-600 mb-3">
              <span className="font-medium">Why this score:</span> {opportunity.priority_rationale}
            </p>
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
