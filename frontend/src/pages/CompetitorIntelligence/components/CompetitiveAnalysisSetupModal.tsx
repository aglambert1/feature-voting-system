/**
 * CompetitiveAnalysisSetupModal
 *
 * Modal for configuring the Competitive Analysis Agent settings:
 * - Analysis mode: Manual vs Scheduled
 * - Schedule options when scheduled
 * - Strategic analysis component checkboxes (Pricing, Positioning, Changes, Momentum, Financials)
 * - Feature similarity threshold slider
 * - Idea generation threshold slider
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

export default function CompetitiveAnalysisSetupModal({ productId, currentConfig, onClose, onSave }: Props) {
  const [analysisMode, setAnalysisMode] = useState<'manual' | 'scheduled'>(
    (currentConfig?.deep_analysis_mode as 'manual' | 'scheduled') || 'manual'
  );
  const [schedule, setSchedule] = useState<'daily' | 'weekly' | 'monthly'>(
    (currentConfig?.deep_analysis_schedule as 'daily' | 'weekly' | 'monthly') || 'weekly'
  );

  // Strategic analysis toggles
  const [pricingEnabled, setPricingEnabled] = useState(currentConfig?.enable_pricing_analysis ?? true);
  const [positioningEnabled, setPositioningEnabled] = useState(currentConfig?.enable_positioning_analysis ?? true);
  const [changesEnabled, setChangesEnabled] = useState(currentConfig?.enable_changes_tracking ?? true);
  const [momentumEnabled, setMomentumEnabled] = useState(currentConfig?.enable_momentum_analysis ?? true);
  const [financialsEnabled, setFinancialsEnabled] = useState(currentConfig?.enable_financials_analysis ?? false);

  // Thresholds
  const [similarityThreshold, setSimilarityThreshold] = useState(
    Math.round((currentConfig?.intensity_similarity_threshold || 0.7) * 100)
  );
  const [ideaThreshold, setIdeaThreshold] = useState(
    currentConfig?.intensity_idea_threshold || 3
  );

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      const updatedConfig = await updateAgentConfig(productId, {
        deep_analysis_mode: analysisMode,
        deep_analysis_schedule: schedule,
        enable_pricing_analysis: pricingEnabled,
        enable_positioning_analysis: positioningEnabled,
        enable_changes_tracking: changesEnabled,
        enable_momentum_analysis: momentumEnabled,
        enable_financials_analysis: financialsEnabled,
        intensity_similarity_threshold: similarityThreshold / 100,
        intensity_idea_threshold: ideaThreshold,
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
          <h3 className="text-lg font-semibold text-gray-900">Competitive Analysis Agent Setup</h3>
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

          {/* Analysis Mode */}
          <div>
            <label className="block text-sm font-medium text-gray-900 mb-2">
              Analysis Mode
            </label>
            <div className="space-y-2">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  checked={analysisMode === 'manual'}
                  onChange={() => setAnalysisMode('manual')}
                  className="h-4 w-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">Manual - Run only when triggered</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  checked={analysisMode === 'scheduled'}
                  onChange={() => setAnalysisMode('scheduled')}
                  className="h-4 w-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">Scheduled - Run automatically</span>
              </label>
            </div>
          </div>

          {/* Schedule Frequency */}
          {analysisMode === 'scheduled' && (
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Run Frequency
              </label>
              <select
                value={schedule}
                onChange={(e) => setSchedule(e.target.value as 'daily' | 'weekly' | 'monthly')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
          )}

          {/* Strategic Analysis Components */}
          <div>
            <label className="block text-sm font-medium text-gray-900 mb-3">
              Strategic Analysis Components
            </label>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={pricingEnabled}
                  onChange={(e) => setPricingEnabled(e.target.checked)}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <div>
                  <span className="text-sm text-gray-900">Pricing Analysis</span>
                  <p className="text-xs text-gray-500">Track competitor pricing models, tiers, and trials</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={positioningEnabled}
                  onChange={(e) => setPositioningEnabled(e.target.checked)}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <div>
                  <span className="text-sm text-gray-900">Positioning Analysis</span>
                  <p className="text-xs text-gray-500">Analyze messaging, value props, and target audience</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={changesEnabled}
                  onChange={(e) => setChangesEnabled(e.target.checked)}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <div>
                  <span className="text-sm text-gray-900">Changes Tracking</span>
                  <p className="text-xs text-gray-500">Monitor release notes and feature launches</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={momentumEnabled}
                  onChange={(e) => setMomentumEnabled(e.target.checked)}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <div>
                  <span className="text-sm text-gray-900">Momentum Analysis</span>
                  <p className="text-xs text-gray-500">Track growth signals and customer wins</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={financialsEnabled}
                  onChange={(e) => setFinancialsEnabled(e.target.checked)}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <div>
                  <span className="text-sm text-gray-900">Financials Analysis</span>
                  <p className="text-xs text-gray-500">Track funding, revenue (when available)</p>
                </div>
              </label>
            </div>
          </div>

          {/* Feature Similarity Threshold */}
          <div>
            <label className="block text-sm font-medium text-gray-900 mb-2">
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
              <span>50% (Looser matching)</span>
              <span>95% (Stricter matching)</span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Controls how similar features must be to cluster together.
            </p>
          </div>

          {/* Idea Generation Threshold */}
          <div>
            <label className="block text-sm font-medium text-gray-900 mb-2">
              Auto-Idea Threshold: {ideaThreshold} competitors
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
            <p className="text-xs text-gray-500 mt-1">
              When this many competitors have a similar feature, auto-generate an idea.
            </p>
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
