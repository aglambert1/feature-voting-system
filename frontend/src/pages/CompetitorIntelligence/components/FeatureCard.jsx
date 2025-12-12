/**
 * FeatureCard Component
 *
 * Displays a single feature with selection capability and change tracking.
 * Supports showing change types (NEW/MODIFIED/UNCHANGED/REMOVED).
 */

import PropTypes from 'prop-types';

const FeatureCard = ({ feature, onToggle, showChangeType }) => {
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

  const isDisabled = feature.change_type === 'removed';

  return (
    <div
      className={`border rounded-lg p-4 cursor-pointer transition-all ${
        isDisabled
          ? 'opacity-50 cursor-not-allowed bg-gray-50'
          : feature.selected
          ? 'border-blue-500 bg-blue-50'
          : 'border-gray-200 hover:border-blue-300'
      }`}
      onClick={isDisabled ? undefined : onToggle}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-start flex-1">
          <input
            type="checkbox"
            checked={feature.selected}
            onChange={onToggle}
            disabled={isDisabled}
            onClick={(e) => e.stopPropagation()}
            className="mt-1 mr-3"
          />
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900 mb-1">
              {feature.name}
            </h4>
            {getChangeTypeBadge()}
          </div>
        </div>
      </div>

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
            onClick={(e) => e.stopPropagation()}
          >
            View Source →
          </a>
        </div>
      )}
    </div>
  );
};

FeatureCard.propTypes = {
  feature: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    description: PropTypes.string.isRequired,
    category: PropTypes.string,
    confidence: PropTypes.number,
    source_url: PropTypes.string,
    change_type: PropTypes.oneOf(['new', 'modified', 'unchanged', 'removed']),
    change_description: PropTypes.string,
    selected: PropTypes.bool.isRequired,
    has_details: PropTypes.bool,
  }).isRequired,
  onToggle: PropTypes.func.isRequired,
  showChangeType: PropTypes.bool.isRequired,
};

export default FeatureCard;
