/**
 * AgentSettingsTab
 *
 * Configuration management for the Competitive Analysis Agent.
 * Allows PO to configure:
 * - Product analysis mode/schedule
 * - Competitor discovery mode/schedule
 * - Deep analysis mode/schedule
 * - Strategic analysis toggles
 * - Intensity thresholds
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
          <h2 className="text-lg font-semibold text-gray-900">Agent Configuration</h2>
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
        {/* Product Analysis Section */}
        <section className="bg-gray-50 rounded-lg p-5">
          <h3 className="text-md font-medium text-gray-900 mb-4">Product Analysis</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Mode</label>
              <select
                value={getValue('product_analysis_mode')}
                onChange={(e) => handleChange('product_analysis_mode', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value={AgentMode.MANUAL}>Manual</option>
                <option value={AgentMode.SCHEDULED}>Scheduled</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Schedule</label>
              <select
                value={getValue('product_analysis_schedule') || ''}
                onChange={(e) => handleChange('product_analysis_schedule', e.target.value as ScheduleFrequency)}
                disabled={getValue('product_analysis_mode') === AgentMode.MANUAL}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
              >
                <option value="">Select schedule</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
          </div>
          {config?.product_analysis_last_run && (
            <p className="mt-2 text-xs text-gray-500">
              Last run: {new Date(config.product_analysis_last_run).toLocaleString()}
            </p>
          )}
        </section>

        {/* Competitor Discovery Section */}
        <section className="bg-gray-50 rounded-lg p-5">
          <h3 className="text-md font-medium text-gray-900 mb-4">Competitor Discovery</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Mode</label>
              <select
                value={getValue('competitor_discovery_mode')}
                onChange={(e) => handleChange('competitor_discovery_mode', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value={AgentMode.MANUAL}>Manual</option>
                <option value={AgentMode.SCHEDULED}>Scheduled</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Schedule</label>
              <select
                value={getValue('competitor_discovery_schedule') || ''}
                onChange={(e) => handleChange('competitor_discovery_schedule', e.target.value as ScheduleFrequency)}
                disabled={getValue('competitor_discovery_mode') === AgentMode.MANUAL}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
              >
                <option value="">Select schedule</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
          </div>
          <div className="space-y-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={getValue('alert_on_new_competitors')}
                onChange={(e) => handleChange('alert_on_new_competitors', e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Alert on new competitors</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={getValue('alert_on_disappeared_competitors')}
                onChange={(e) => handleChange('alert_on_disappeared_competitors', e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Alert on disappeared competitors</span>
            </label>
          </div>
          {config?.competitor_discovery_last_run && (
            <p className="mt-3 text-xs text-gray-500">
              Last run: {new Date(config.competitor_discovery_last_run).toLocaleString()}
            </p>
          )}
        </section>

        {/* Deep Analysis Section */}
        <section className="bg-gray-50 rounded-lg p-5">
          <h3 className="text-md font-medium text-gray-900 mb-4">Deep Analysis</h3>
          <p className="text-sm text-gray-500 mb-4">
            Deep analysis runs for competitors marked for tracking. Includes feature extraction and strategic analysis.
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

        {/* Strategic Analysis Toggles */}
        <section className="bg-gray-50 rounded-lg p-5">
          <h3 className="text-md font-medium text-gray-900 mb-4">Strategic Analysis Components</h3>
          <p className="text-sm text-gray-500 mb-4">
            Select which strategic analyses to include in deep analysis runs.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <label className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
              <input
                type="checkbox"
                checked={getValue('enable_pricing_analysis')}
                onChange={(e) => handleChange('enable_pricing_analysis', e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <div>
                <span className="text-sm font-medium text-gray-900">Pricing Analysis</span>
                <p className="text-xs text-gray-500">Pricing tiers, models, trials</p>
              </div>
            </label>
            <label className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
              <input
                type="checkbox"
                checked={getValue('enable_positioning_analysis')}
                onChange={(e) => handleChange('enable_positioning_analysis', e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <div>
                <span className="text-sm font-medium text-gray-900">Positioning Analysis</span>
                <p className="text-xs text-gray-500">Messaging, value props, audience</p>
              </div>
            </label>
            <label className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
              <input
                type="checkbox"
                checked={getValue('enable_changes_tracking')}
                onChange={(e) => handleChange('enable_changes_tracking', e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <div>
                <span className="text-sm font-medium text-gray-900">Changes Tracking</span>
                <p className="text-xs text-gray-500">Release notes, feature launches</p>
              </div>
            </label>
            <label className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
              <input
                type="checkbox"
                checked={getValue('enable_momentum_analysis')}
                onChange={(e) => handleChange('enable_momentum_analysis', e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <div>
                <span className="text-sm font-medium text-gray-900">Momentum Analysis</span>
                <p className="text-xs text-gray-500">Growth signals, customer wins</p>
              </div>
            </label>
            <label className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
              <input
                type="checkbox"
                checked={getValue('enable_financials_analysis')}
                onChange={(e) => handleChange('enable_financials_analysis', e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <div>
                <span className="text-sm font-medium text-gray-900">Financials Analysis</span>
                <p className="text-xs text-gray-500">Funding, revenue (when available)</p>
              </div>
            </label>
          </div>
        </section>

        {/* Competitive Intensity Settings */}
        <section className="bg-gray-50 rounded-lg p-5">
          <h3 className="text-md font-medium text-gray-900 mb-4">Competitive Intensity</h3>
          <p className="text-sm text-gray-500 mb-4">
            Control how features are clustered and when ideas are automatically generated.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Feature Similarity Threshold
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0.5"
                  max="0.95"
                  step="0.05"
                  value={getValue('intensity_similarity_threshold')}
                  onChange={(e) => handleChange('intensity_similarity_threshold', parseFloat(e.target.value))}
                  className="flex-1"
                />
                <span className="text-sm font-mono bg-white px-2 py-1 border border-gray-300 rounded min-w-[60px] text-center">
                  {(getValue('intensity_similarity_threshold') * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Higher = stricter matching (fewer, more precise clusters)
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Idea Generation Threshold
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="2"
                  max="10"
                  step="1"
                  value={getValue('intensity_idea_threshold')}
                  onChange={(e) => handleChange('intensity_idea_threshold', parseInt(e.target.value))}
                  className="flex-1"
                />
                <span className="text-sm font-mono bg-white px-2 py-1 border border-gray-300 rounded min-w-[60px] text-center">
                  {getValue('intensity_idea_threshold')} competitors
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Auto-generate ideas when this many competitors have similar features
              </p>
            </div>
          </div>
        </section>

        {/* Agent Enable/Disable */}
        <section className="border border-gray-200 rounded-lg p-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-md font-medium text-gray-900">Agent Status</h3>
              <p className="text-sm text-gray-500">Enable or disable all scheduled agent activities</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={getValue('enabled')}
                onChange={(e) => handleChange('enabled', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              <span className="ml-3 text-sm font-medium text-gray-900">
                {getValue('enabled') ? 'Enabled' : 'Disabled'}
              </span>
            </label>
          </div>
        </section>
      </div>
    </div>
  );
}
