/**
 * Stage3_FeatureExtraction
 *
 * Feature extraction stage with:
 * - Sequential feature extraction from competitors
 * - Change detection (NEW/MODIFIED/UNCHANGED/REMOVED)
 * - Feature selection for idea generation
 */

import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import api from '../../../services/api';
import FeatureCard from '../components/FeatureCard';
import ChangeSummaryCard from '../components/ChangeSummaryCard';

const Stage3_FeatureExtraction = ({
  sessionId,
  hasPreviousAnalysis,
  onComplete,
  onBack,
}) => {
  const [mode, setMode] = useState('loading');
  const [featuresByCompetitor, setFeaturesByCompetitor] = useState([]);
  const [changeStats, setChangeStats] = useState(null);
  const [showOnlyChanges, setShowOnlyChanges] = useState(hasPreviousAnalysis);
  const [error, setError] = useState(null);

  useEffect(() => {
    extractFeatures();
  }, []);

  const extractFeatures = async () => {
    try {
      setMode('loading');

      // Start extraction
      await api.post(
        `/competitor-intelligence/sessions/${sessionId}/extract-features`
      );

      // Load extracted features
      const response = await api.get(
        `/competitor-intelligence/sessions/${sessionId}/features`
      );

      setFeaturesByCompetitor(response.data.features_by_competitor || []);
      setChangeStats(response.data.change_stats);
      setMode('reviewing');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to extract features');
      setMode('error');
    }
  };

  const toggleFeatureSelection = (competitorId, featureId) => {
    setFeaturesByCompetitor((prev) =>
      prev.map((comp) => {
        if (comp.competitor_id === competitorId) {
          return {
            ...comp,
            features: comp.features.map((f) =>
              f.id === featureId ? { ...f, selected: !f.selected } : f
            ),
          };
        }
        return comp;
      })
    );
  };

  const handleConfirmSelection = async () => {
    // Collect all selected feature IDs
    const selectedIds = [];
    featuresByCompetitor.forEach((comp) => {
      comp.features.forEach((f) => {
        if (f.selected) {
          selectedIds.push(parseInt(f.id));
        }
      });
    });

    if (selectedIds.length === 0) {
      alert('Please select at least one feature');
      return;
    }

    try {
      await api.post(
        `/competitor-intelligence/sessions/${sessionId}/select-features`,
        { feature_ids: selectedIds }
      );

      onComplete();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to confirm selection');
    }
  };

  if (mode === 'loading') {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Extracting Features...
        </h3>
        <p className="text-gray-600 mb-2">
          AI is analyzing competitors and extracting features
        </p>
        <p className="text-sm text-gray-500">
          ⏱️ This typically takes 1-3 minutes depending on number of competitors
        </p>
      </div>
    );
  }

  if (mode === 'error') {
    return (
      <div className="text-center py-12">
        <div className="text-red-600 mb-4">
          <svg
            className="mx-auto h-12 w-12"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Extraction Failed
        </h3>
        <p className="text-gray-600 mb-4">{error}</p>
        <button
          onClick={extractFeatures}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  const totalSelected = featuresByCompetitor.reduce(
    (sum, comp) => sum + comp.features.filter((f) => f.selected).length,
    0
  );

  // Filter features if showing only changes
  const displayCompetitors = featuresByCompetitor.map((comp) => {
    if (showOnlyChanges && hasPreviousAnalysis) {
      return {
        ...comp,
        features: comp.features.filter(
          (f) => f.change_type === 'new' || f.change_type === 'modified'
        ),
      };
    }
    return comp;
  });

  return (
    <div>
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-2xl font-bold mb-2">Feature Extraction</h2>
          <p className="text-gray-600">
            Review and select features for idea generation
          </p>
        </div>
        <div className="text-sm text-gray-600">{totalSelected} features selected</div>
      </div>

      {hasPreviousAnalysis && changeStats && (
        <ChangeSummaryCard
          changeStats={changeStats}
          title="Feature Change Summary"
        />
      )}

      {hasPreviousAnalysis && (
        <div className="mb-4 flex items-center">
          <input
            type="checkbox"
            id="show_only_changes"
            checked={showOnlyChanges}
            onChange={(e) => setShowOnlyChanges(e.target.checked)}
            className="mr-2"
          />
          <label htmlFor="show_only_changes" className="text-sm text-gray-700">
            Show only new/modified features
          </label>
        </div>
      )}

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <div className="space-y-6 mb-6">
        {displayCompetitors.map((competitor) => (
          <div key={competitor.competitor_id} className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                {competitor.competitor_name}
              </h3>
              {competitor.competitor_url && (
                <a
                  href={competitor.competitor_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline"
                >
                  {competitor.competitor_url}
                </a>
              )}
              <p className="text-sm text-gray-600 mt-1">
                {competitor.features.length} features extracted
              </p>
            </div>
            <div className="p-6">
              {competitor.features.length === 0 ? (
                <p className="text-center text-gray-500 py-4">
                  {showOnlyChanges
                    ? 'No new or modified features'
                    : 'No features extracted'}
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {competitor.features.map((feature) => (
                    <FeatureCard
                      key={feature.id}
                      feature={feature}
                      onToggle={() =>
                        toggleFeatureSelection(competitor.competitor_id, feature.id)
                      }
                      showChangeType={hasPreviousAnalysis}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
        >
          ← Back
        </button>
        <button
          onClick={handleConfirmSelection}
          disabled={totalSelected === 0}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Generate Ideas ({totalSelected}) →
        </button>
      </div>
    </div>
  );
};

Stage3_FeatureExtraction.propTypes = {
  sessionId: PropTypes.string.isRequired,
  hasPreviousAnalysis: PropTypes.bool.isRequired,
  onComplete: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
};

export default Stage3_FeatureExtraction;
