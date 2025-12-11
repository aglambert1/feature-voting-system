/**
 * ChangeSummaryCard Component
 *
 * Displays differential analysis summary showing NEW/CONTINUING/DISAPPEARED
 * competitors and significant changes in the competitive landscape.
 */

import PropTypes from 'prop-types';

const ChangeSummaryCard = ({ changeSummary }) => {
  return (
    <div className="mb-6 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
      <div className="flex items-start mb-4">
        <svg
          className="w-6 h-6 text-blue-600 mr-2 flex-shrink-0"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
            clipRule="evenodd"
          />
        </svg>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Competitive Landscape Changes
          </h3>
          <p className="text-sm text-gray-700 mb-4">
            Comparing with previous analysis
          </p>

          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="bg-white rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-600">
                {changeSummary.new_count}
              </div>
              <div className="text-xs text-gray-600">New Competitors</div>
            </div>
            <div className="bg-white rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-blue-600">
                {changeSummary.continuing_count}
              </div>
              <div className="text-xs text-gray-600">Continuing</div>
            </div>
            <div className="bg-white rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-red-600">
                {changeSummary.disappeared_count}
              </div>
              <div className="text-xs text-gray-600">Disappeared</div>
            </div>
          </div>

          {changeSummary.significant_changes.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-900 mb-2">
                Significant Changes:
              </h4>
              <ul className="space-y-1">
                {changeSummary.significant_changes.map((change, idx) => (
                  <li key={idx} className="text-sm text-gray-700 flex items-start">
                    <span className="text-blue-600 mr-2">•</span>
                    <span>{change}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

ChangeSummaryCard.propTypes = {
  changeSummary: PropTypes.shape({
    new_count: PropTypes.number.isRequired,
    continuing_count: PropTypes.number.isRequired,
    disappeared_count: PropTypes.number.isRequired,
    significant_changes: PropTypes.arrayOf(PropTypes.string).isRequired,
  }).isRequired,
};

export default ChangeSummaryCard;
