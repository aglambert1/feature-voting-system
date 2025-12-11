/**
 * CompetitorCard Component
 *
 * Displays a single competitor with selection capability and status badge.
 * Supports differential analysis status indicators (NEW/CONTINUING/DISAPPEARED).
 */

import PropTypes from 'prop-types';

const CompetitorCard = ({ competitor, onToggle, showStatus }) => {
  const getStatusBadge = () => {
    if (!showStatus || !competitor.status) return null;

    const badges = {
      new: { bg: 'bg-green-100', text: 'text-green-800', label: 'NEW' },
      continuing: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'CONTINUING' },
      disappeared: { bg: 'bg-red-100', text: 'text-red-800', label: 'DISAPPEARED' },
    };

    const badge = badges[competitor.status];

    return (
      <span
        className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}
      >
        {badge.label}
      </span>
    );
  };

  return (
    <div
      className={`border rounded-lg p-4 cursor-pointer transition-all ${
        competitor.selected
          ? 'border-blue-500 bg-blue-50'
          : 'border-gray-200 hover:border-blue-300'
      }`}
      onClick={onToggle}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-start flex-1">
          <input
            type="checkbox"
            checked={competitor.selected}
            onChange={onToggle}
            onClick={(e) => e.stopPropagation()}
            className="mt-1 mr-3"
          />
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900 mb-1">
              {competitor.name}
            </h3>
            {getStatusBadge()}
          </div>
        </div>
      </div>

      <a
        href={competitor.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-blue-600 hover:underline mb-2 block"
        onClick={(e) => e.stopPropagation()}
      >
        {competitor.url}
      </a>

      <p className="text-sm text-gray-700 mb-2">{competitor.summary}</p>

      {competitor.relevance_score !== undefined && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-medium text-gray-600">Relevance:</span>
          <div className="flex items-center">
            <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full ${
                  competitor.relevance_score >= 0.8
                    ? 'bg-green-500'
                    : competitor.relevance_score >= 0.6
                    ? 'bg-yellow-500'
                    : 'bg-orange-500'
                }`}
                style={{ width: `${competitor.relevance_score * 100}%` }}
              ></div>
            </div>
            <span className="ml-2 text-xs font-semibold text-gray-700">
              {(competitor.relevance_score * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}

      {showStatus && competitor.status_explanation && (
        <p className="text-xs text-gray-600 italic">
          {competitor.status_explanation}
        </p>
      )}

      {competitor.discovery_source === 'user_added' && (
        <span className="inline-block px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded-full mt-2">
          User Added
        </span>
      )}
    </div>
  );
};

CompetitorCard.propTypes = {
  competitor: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    url: PropTypes.string.isRequired,
    summary: PropTypes.string.isRequired,
    relevance_score: PropTypes.number,
    status: PropTypes.oneOf(['new', 'continuing', 'disappeared']),
    status_explanation: PropTypes.string,
    significance: PropTypes.oneOf(['low', 'medium', 'high']),
    selected: PropTypes.bool.isRequired,
    discovery_source: PropTypes.string,
  }).isRequired,
  onToggle: PropTypes.func.isRequired,
  showStatus: PropTypes.bool.isRequired,
};

export default CompetitorCard;
