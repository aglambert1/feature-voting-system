/**
 * AgentSettingsTab
 *
 * V2 Competitive Analysis Agent Configuration.
 * Simplified settings - only competitive analysis mode/schedule.
 *
 * Removed in V2:
 * - Product analysis (not an agent - triggered on product info upload)
 * - Competitor discovery (moved to Market Discovery Agent)
 * - Strategic analysis toggles (pricing, positioning, etc.)
 * - Intensity thresholds (V2 uses LLM-based priority scoring)
 * - Agent Status toggle (redundant - if mode=manual, scheduled activities don't occur)
 */

import { useState, useEffect, useCallback } from 'react';
import { getAgentConfig, updateAgentConfig } from '../../../services/api';
import { CompetitiveAgentConfig, CompetitiveAgentConfigUpdate, AgentMode, ScheduleFrequency } from '../../../types';

interface Props {
  productId: number;
}

export default function AgentSettingsTab({ productId }: Props) {
  const [config, setConfig] = useState<CompetitiveAgentConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Form state
  const [formData, setFormData] = useState<CompetitiveAgentConfigUpdate>({});

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getAgentConfig(productId);
      setConfig(data);
      setFormData({});
      setHasChanges(false);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load configuration');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Clear success message after timeout
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  const handleChange = (field: keyof CompetitiveAgentConfigUpdate, value: unknown) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setHasChanges(true);
    setSuccessMessage(null);
  };

  const handleSave = async () => {
    if (!hasChanges) return;

    setSaving(true);
    setError(null);

    try {
      const updated = await updateAgentConfig(productId, formData);
      setConfig(updated);
      setFormData({});
      setHasChanges(false);
      setSuccessMessage('Configuration saved successfully');
    } catch (err: any) {
      setError(err.message || 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setFormData({});
    setHasChanges(false);
  };

  // Helper to get current value (pending change or saved)
  const getValue = <K extends keyof CompetitiveAgentConfig>(field: K): CompetitiveAgentConfig[K] => {
    if (field in formData) {
      return formData[field as keyof CompetitiveAgentConfigUpdate] as CompetitiveAgentConfig[K];
    }
    return config?.[field] as CompetitiveAgentConfig[K];
  };

  if (loading) {
    return (
      <div className="p-6 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error && !config) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
          <button onClick={fetchConfig} className="mt-2 text-red-600 hover:text-red-800 font-medium">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header with Save Button */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Competitive Analysis Agent Settings</h2>
          <p className="text-sm text-gray-500">Configure how the competitive analysis agent operates</p>
        </div>
        <div className="flex items-center gap-3">
          {hasChanges && (
            <button
              onClick={handleReset}
              className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
            >
              Reset
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            className={`px-4 py-2 rounded-lg font-medium ${
              hasChanges
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            }`}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {successMessage && (
        <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
          {successMessage}
        </div>
      )}

      <div className="space-y-8">
        {/* Competitive Analysis Section - V2 Simplified */}
        <section className="bg-gray-50 rounded-lg p-5">
          <h3 className="text-md font-medium text-gray-900 mb-2">Competitive Analysis</h3>
          <p className="text-sm text-gray-500 mb-4">
            Runs functional audits for each competitor, then synthesizes landscape opportunities across all competitors.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Mode</label>
              <select
                value={getValue('deep_analysis_mode')}
                onChange={(e) => handleChange('deep_analysis_mode', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value={AgentMode.MANUAL}>Manual</option>
                <option value={AgentMode.SCHEDULED}>Scheduled</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Schedule</label>
              <select
                value={getValue('deep_analysis_schedule') || ''}
                onChange={(e) => handleChange('deep_analysis_schedule', e.target.value as ScheduleFrequency)}
                disabled={getValue('deep_analysis_mode') === AgentMode.MANUAL}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
              >
                <option value="">Select schedule</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
          </div>
          {config?.deep_analysis_last_run && (
            <p className="text-xs text-gray-500">
              Last run: {new Date(config.deep_analysis_last_run).toLocaleString()}
            </p>
          )}
        </section>

        {/* Info Box */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="font-medium text-blue-800 mb-2">About V2 Competitive Analysis</h4>
          <ul className="text-sm text-blue-700 space-y-1 list-disc list-inside">
            <li>Functional audits analyze each competitor's features against your product</li>
            <li>Landscape synthesis identifies feature opportunities across all competitors</li>
            <li>Priority scores are calculated using Market Gravity (prevalence + user demand)</li>
            <li>Create ideas from opportunities to add them to your customer voting queue</li>
          </ul>
        </div>

        {/* Link to other agent settings */}
        <div className="text-sm text-gray-500 space-y-2">
          <p>
            <span className="font-medium">Competitor Discovery:</span> Configure in the Market Discovery Agent settings.
          </p>
          <p>
            <span className="font-medium">Product Analysis:</span> Triggered automatically when you update product information.
          </p>
        </div>
      </div>
    </div>
  );
}
