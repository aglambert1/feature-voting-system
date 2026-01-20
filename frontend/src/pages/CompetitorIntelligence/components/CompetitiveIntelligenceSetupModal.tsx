/**
 * CompetitiveIntelligenceSetupModal
 *
 * Combined modal for configuring the Competitive Intelligence Agent settings:
 * - Unified schedule (Manual vs Scheduled) for full pipeline
 * - Advanced option for separate discovery vs analysis schedules
 * - Feature similarity threshold slider
 * - Idea generation threshold slider
 * - Alert settings
 */

import { useState } from 'react';
import { updateAgentConfig } from '../../../services/api';
import { CompetitiveAgentConfig } from '../../../types';

interface Props {
  productId: number;
  currentConfig: CompetitiveAgentConfig | null;
  onClose: () => void;
  onSave: (config: CompetitiveAgentConfig) => void;
}

export default function CompetitiveIntelligenceSetupModal({ productId, currentConfig, onClose, onSave }: Props) {
  // Unified mode - determines if any scheduling is enabled
  const [mode, setMode] = useState<'manual' | 'scheduled'>(() => {
    // If either is scheduled, consider it scheduled
    if (currentConfig?.competitor_discovery_mode === 'scheduled' || currentConfig?.deep_analysis_mode === 'scheduled') {
      return 'scheduled';
    }
    return 'manual';
  });

  // Unified schedule (used when not using separate schedules)
  const [unifiedSchedule, setUnifiedSchedule] = useState<'daily' | 'weekly' | 'monthly'>(
    (currentConfig?.deep_analysis_schedule as 'daily' | 'weekly' | 'monthly') || 'weekly'
  );

  // Advanced scheduling
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [useSeparateSchedules, setUseSeparateSchedules] = useState(() => {
    // If schedules are different, assume separate schedules were used
    return currentConfig?.competitor_discovery_schedule !== currentConfig?.deep_analysis_schedule &&
           currentConfig?.competitor_discovery_mode === 'scheduled' &&
           currentConfig?.deep_analysis_mode === 'scheduled';
  });
  const [discoverySchedule, setDiscoverySchedule] = useState<'daily' | 'weekly' | 'monthly'>(
    (currentConfig?.competitor_discovery_schedule as 'daily' | 'weekly' | 'monthly') || 'monthly'
  );
  const [analysisSchedule, setAnalysisSchedule] = useState<'daily' | 'weekly' | 'monthly'>(
    (currentConfig?.deep_analysis_schedule as 'daily' | 'weekly' | 'monthly') || 'weekly'
  );

  // Thresholds
  const [similarityThreshold, setSimilarityThreshold] = useState(
    Math.round((currentConfig?.intensity_similarity_threshold || 0.75) * 100)
  );
  const [ideaThreshold, setIdeaThreshold] = useState(
    currentConfig?.intensity_idea_threshold || 3
  );

  // Alerts
  const [alertOnNewCompetitors, setAlertOnNewCompetitors] = useState(
    currentConfig?.alert_on_new_competitors ?? true
  );
  const [alertOnDisappearedCompetitors, setAlertOnDisappearedCompetitors] = useState(
    currentConfig?.alert_on_disappeared_competitors ?? true
  );

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      // Determine schedules based on mode and advanced settings
      let discoveryMode: 'manual' | 'scheduled' = mode;
      let analysisMode: 'manual' | 'scheduled' = mode;
      let finalDiscoverySchedule = unifiedSchedule;
      let finalAnalysisSchedule = unifiedSchedule;

      if (mode === 'scheduled' && useSeparateSchedules) {
        finalDiscoverySchedule = discoverySchedule;
        finalAnalysisSchedule = analysisSchedule;
      }

      const updatedConfig = await updateAgentConfig(productId, {
        competitor_discovery_mode: discoveryMode,
        competitor_discovery_schedule: finalDiscoverySchedule,
        deep_analysis_mode: analysisMode,
        deep_analysis_schedule: finalAnalysisSchedule,
        intensity_similarity_threshold: similarityThreshold / 100,
        intensity_idea_threshold: ideaThreshold,
        alert_on_new_competitors: alertOnNewCompetitors,
        alert_on_disappeared_competitors: alertOnDisappearedCompetitors,
      });
      onSave(updatedConfig);
    } catch (err: any) {
      setError(err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white flex items-center justify-between p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Competitive Intelligence Setup</h3>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-4 space-y-6">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
              {error}
            </div>
          )}

          {/* Schedule Section */}
          <div className="p-4 bg-gray-50 rounded-lg space-y-4">
            <h4 className="font-medium text-gray-900">Schedule</h4>

            {/* Mode */}
            <div className="space-y-2">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  checked={mode === 'manual'}
                  onChange={() => setMode('manual')}
                  className="h-4 w-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">Manual - Run analysis only when triggered</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  checked={mode === 'scheduled'}
                  onChange={() => setMode('scheduled')}
                  className="h-4 w-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">Scheduled - Run automatically</span>
              </label>
            </div>

            {/* Schedule Frequency (when scheduled) */}
            {mode === 'scheduled' && !useSeparateSchedules && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Frequency
                </label>
                <select
                  value={unifiedSchedule}
                  onChange={(e) => setUnifiedSchedule(e.target.value as 'daily' | 'weekly' | 'monthly')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Full pipeline runs: Discovery → Audits → Landscape Synthesis
                </p>
              </div>
            )}

            {/* Advanced Scheduling Toggle */}
            {mode === 'scheduled' && (
              <div>
                <button
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800"
                >
                  <svg
                    className={`w-4 h-4 transform transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  Advanced scheduling options
                </button>

                {showAdvanced && (
                  <div className="mt-3 ml-6 space-y-3 border-l-2 border-gray-200 pl-4">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useSeparateSchedules}
                        onChange={(e) => setUseSeparateSchedules(e.target.checked)}
                        className="h-4 w-4 text-blue-600 rounded"
                      />
                      <span className="text-sm text-gray-700">Use separate schedules for discovery and analysis</span>
                    </label>

                    {useSeparateSchedules && (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Market Discovery
                          </label>
                          <select
                            value={discoverySchedule}
                            onChange={(e) => setDiscoverySchedule(e.target.value as 'daily' | 'weekly' | 'monthly')}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                          >
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="monthly">Monthly</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Competitive Analysis
                          </label>
                          <select
                            value={analysisSchedule}
                            onChange={(e) => setAnalysisSchedule(e.target.value as 'daily' | 'weekly' | 'monthly')}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                          >
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="monthly">Monthly</option>
                          </select>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Analysis Settings Section */}
          <div className="p-4 bg-gray-50 rounded-lg space-y-4">
            <h4 className="font-medium text-gray-900">Analysis Settings</h4>

            {/* Feature Similarity Threshold */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Feature Similarity Threshold: {similarityThreshold}%
              </label>
              <input
                type="range"
                min="50"
                max="95"
                value={similarityThreshold}
                onChange={(e) => setSimilarityThreshold(parseInt(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>50% (Looser)</span>
                <span>95% (Stricter)</span>
              </div>
            </div>

            {/* Idea Generation Threshold */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Auto-generate ideas when: {ideaThreshold} competitors have similar features
              </label>
              <input
                type="range"
                min="2"
                max="10"
                value={ideaThreshold}
                onChange={(e) => setIdeaThreshold(parseInt(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>2 (More ideas)</span>
                <span>10 (Fewer ideas)</span>
              </div>
            </div>
          </div>

          {/* Alerts Section */}
          <div className="p-4 bg-gray-50 rounded-lg space-y-3">
            <h4 className="font-medium text-gray-900">Alerts</h4>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={alertOnNewCompetitors}
                onChange={(e) => setAlertOnNewCompetitors(e.target.checked)}
                className="h-4 w-4 text-blue-600 rounded"
              />
              <span className="text-sm text-gray-700">Alert on new competitors discovered</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={alertOnDisappearedCompetitors}
                onChange={(e) => setAlertOnDisappearedCompetitors(e.target.checked)}
                className="h-4 w-4 text-blue-600 rounded"
              />
              <span className="text-sm text-gray-700">Alert on competitor changes</span>
            </label>
          </div>
        </div>

        <div className="sticky bottom-0 bg-white flex justify-end gap-3 p-4 border-t border-gray-200">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
