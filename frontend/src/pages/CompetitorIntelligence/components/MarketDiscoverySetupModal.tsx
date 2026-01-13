/**
 * MarketDiscoverySetupModal
 *
 * Modal for configuring the Market Discovery Agent settings:
 * - Discovery mode: Manual vs Scheduled
 * - Schedule options when scheduled
 * - Auto-run after product analysis toggle
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

export default function MarketDiscoverySetupModal({ productId, currentConfig, onClose, onSave }: Props) {
  const [discoveryMode, setDiscoveryMode] = useState<'manual' | 'scheduled'>(
    (currentConfig?.competitor_discovery_mode as 'manual' | 'scheduled') || 'manual'
  );
  const [schedule, setSchedule] = useState<'daily' | 'weekly' | 'monthly'>(
    (currentConfig?.competitor_discovery_schedule as 'daily' | 'weekly' | 'monthly') || 'monthly'
  );
  const [autoRunAfterAnalysis, setAutoRunAfterAnalysis] = useState(
    currentConfig?.competitor_discovery_mode === 'scheduled'
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      const updatedConfig = await updateAgentConfig(productId, {
        competitor_discovery_mode: discoveryMode,
        competitor_discovery_schedule: schedule,
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
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Market Discovery Agent Setup</h3>
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

          {/* Discovery Mode */}
          <div>
            <label className="block text-sm font-medium text-gray-900 mb-2">
              Discovery Mode
            </label>
            <div className="space-y-2">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  checked={discoveryMode === 'manual'}
                  onChange={() => setDiscoveryMode('manual')}
                  className="h-4 w-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">Manual - Run only when triggered</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  checked={discoveryMode === 'scheduled'}
                  onChange={() => setDiscoveryMode('scheduled')}
                  className="h-4 w-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">Scheduled - Run automatically</span>
              </label>
            </div>
          </div>

          {/* Schedule Frequency */}
          {discoveryMode === 'scheduled' && (
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

          {/* Auto-run After Analysis Toggle */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-900">
                Auto-run After Product Analysis
              </label>
              <button
                onClick={() => setAutoRunAfterAnalysis(!autoRunAfterAnalysis)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  autoRunAfterAnalysis ? 'bg-blue-600' : 'bg-gray-200'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    autoRunAfterAnalysis ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <p className="text-sm text-gray-500">
              Automatically discover competitors after a product analysis completes.
            </p>
          </div>

          {/* Info Box */}
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>What it does:</strong> The Market Discovery Agent uses AI to find competitors based on your
              product's features and market positioning. It can detect new entrants and track changes in the
              competitive landscape.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-gray-200">
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
