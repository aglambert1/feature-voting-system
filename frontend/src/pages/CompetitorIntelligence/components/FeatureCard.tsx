/**
 * FeatureCard Component
 *
 * Displays a single feature with selection capability and change tracking.
 * Supports showing change types (NEW/MODIFIED/UNCHANGED/REMOVED).
 * Shows linked idea info when feature has already been converted to an idea.
 */

import { MouseEvent } from 'react';
import { Link } from 'react-router-dom';

interface LinkedIdea {
  idea_id: number;
  idea_title: string;
  triage_status: string | null;
  is_locked: boolean;  // True if idea has been triaged (not pending)
}

interface Feature {
  id: string;
  name: string;
  description: string;
  category?: string;
  confidence?: number;
  source_url?: string;
  change_type?: 'new' | 'modified' | 'unchanged' | 'removed';
  change_description?: string;
  selected: boolean;
  has_details?: boolean;
  linked_idea?: LinkedIdea | null;
}

interface FeatureCardProps {
  feature: Feature;
  onToggle: () => void;
  showChangeType: boolean;
}

const FeatureCard = ({ feature, onToggle, showChangeType }: FeatureCardProps) => {
  const getChangeTypeBadge = () => {
    if (!showChangeType || !feature.change_type) return null;

    const badges = {
      new: { bg: 'bg-green-100', text: 'text-green-800', label: 'NEW' },
      modified: { bg: 'bg-orange-100', text: 'text-orange-800', label: 'MODIFIED' },
      unchanged: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'UNCHANGED' },
      removed: { bg: 'bg-red-100', text: 'text-red-800', label: 'REMOVED' },
    };

    const badge = badges[feature.change_type];
    if (!badge) return null;

    return (
      <span
        className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}
      >
        {badge.label}
      </span>
    );
  };

  const getTriageStatusBadge = (status: string | null) => {
    if (!status) return null;
    const badges: Record<string, { bg: string; text: string; label: string }> = {
      auto_approved: { bg: 'bg-green-100', text: 'text-green-700', label: 'Auto-Approved' },
      approved: { bg: 'bg-green-100', text: 'text-green-700', label: 'Approved' },
      needs_review: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Needs Review' },
      duplicate: { bg: 'bg-orange-100', text: 'text-orange-700', label: 'Duplicate' },
      feature_exists: { bg: 'bg-orange-100', text: 'text-orange-700', label: 'Feature Exists' },
      rejected: { bg: 'bg-red-100', text: 'text-red-700', label: 'Rejected' },
      not_appropriate: { bg: 'bg-red-100', text: 'text-red-700', label: 'Not Appropriate' },
    };
    const badge = badges[status] || { bg: 'bg-gray-100', text: 'text-gray-600', label: status };
    return (
      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${badge.bg} ${badge.text}`}>
        {badge.label}
      </span>
    );
  };

  // Feature is disabled if removed OR if it has a linked idea that's been triaged (is_locked)
  const isRemoved = feature.change_type === 'removed';
  const isLocked = feature.linked_idea?.is_locked === true;
  const isDisabled = isRemoved || isLocked;

  return (
    <div
      className={`border rounded-lg p-4 transition-all ${
        isLocked
          ? 'bg-purple-50 border-purple-200 cursor-default'
          : isRemoved
          ? 'opacity-50 cursor-not-allowed bg-gray-50'
          : feature.selected
          ? 'border-blue-500 bg-blue-50 cursor-pointer'
          : 'border-gray-200 hover:border-blue-300 cursor-pointer'
      }`}
      onClick={isDisabled ? undefined : onToggle}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-start flex-1">
          {!isLocked && (
            <input
              type="checkbox"
              checked={feature.selected}
              onChange={onToggle}
              disabled={isDisabled}
              onClick={(e: MouseEvent<HTMLInputElement>) => e.stopPropagation()}
              className="mt-1 mr-3"
            />
          )}
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900 mb-1">
              {feature.name}
            </h4>
            <div className="flex flex-wrap gap-1 items-center">
              {getChangeTypeBadge()}
              {isLocked && (
                <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                  Already Added
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Show linked idea info if this feature was already converted */}
      {feature.linked_idea && (
        <div className="mb-3 p-2 bg-purple-50 border border-purple-200 rounded">
          <div className="flex items-center justify-between gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-purple-600 font-medium mb-0.5">
                {isLocked ? 'Idea already created:' : 'Pending idea:'}
              </p>
              <Link
                to={`/ideas/${feature.linked_idea.idea_id}`}
                className="text-sm text-purple-700 hover:text-purple-900 hover:underline font-medium truncate block"
                onClick={(e: MouseEvent<HTMLAnchorElement>) => e.stopPropagation()}
              >
                {feature.linked_idea.idea_title || `Idea #${feature.linked_idea.idea_id}`}
              </Link>
            </div>
            <div className="flex-shrink-0">
              {getTriageStatusBadge(feature.linked_idea.triage_status)}
            </div>
          </div>
          {!isLocked && (
            <p className="text-xs text-purple-500 mt-1">
              Pending triage - can be re-extracted if needed
            </p>
          )}
        </div>
      )}

      <p className="text-sm text-gray-700 mb-2">{feature.description}</p>

      {feature.category && (
        <div className="text-xs text-gray-600 mb-2">
          <span className="font-medium">Category:</span> {feature.category}
        </div>
      )}

      {feature.confidence !== undefined && feature.confidence !== null && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-medium text-gray-600">Confidence:</span>
          <div className="flex items-center">
            <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full ${
                  feature.confidence >= 0.8
                    ? 'bg-green-500'
                    : feature.confidence >= 0.6
                    ? 'bg-yellow-500'
                    : 'bg-orange-500'
                }`}
                style={{ width: `${feature.confidence * 100}%` }}
              ></div>
            </div>
            <span className="ml-2 text-xs font-semibold text-gray-700">
              {(feature.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}

      {feature.change_description && (
        <div className="text-xs text-gray-600 italic mt-2 pt-2 border-t border-gray-200">
          <span className="font-medium">Change:</span> {feature.change_description}
        </div>
      )}

      {feature.source_url && (
        <div className="mt-2">
          <a
            href={feature.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 hover:underline"
            onClick={(e: MouseEvent<HTMLAnchorElement>) => e.stopPropagation()}
          >
            View Source →
          </a>
        </div>
      )}
    </div>
  );
};

export default FeatureCard;
