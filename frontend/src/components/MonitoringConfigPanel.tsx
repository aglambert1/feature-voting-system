/**
 * MonitoringConfigPanel Component
 *
 * Configuration panel for competitive monitoring settings.
 * Allows users to:
 * - Enable/disable monitoring
 * - Set monitoring frequency
 * - Configure alert preferences
 * - Trigger manual monitoring
 */

import { useState, useEffect, useCallback } from 'react';
import {
  getMonitoringConfig,
  updateMonitoringConfig,
  enableMonitoring,
  disableMonitoring,
  triggerMonitoring,
} from '../services/api';
import type { MonitoringConfig, ApiError } from '../types';
import JobStatusCard from './JobStatusCard';

interface MonitoringConfigPanelProps {
  productId: number;
  onConfigChange?: (config: MonitoringConfig) => void;
}

const MonitoringConfigPanel = ({ productId, onConfigChange }: MonitoringConfigPanelProps) => {
  const [config, setConfig] = useState<MonitoringConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [activeJobUuid, setActiveJobUuid] = useState<string | null>(null);

  // Form state
  const [frequency, setFrequency] = useState<'daily' | 'weekly' | 'biweekly' | 'monthly'>('weekly');
  const [alertNewFeatures, setAlertNewFeatures] = useState(true);
  const [alertRemovedFeatures, setAlertRemovedFeatures] = useState(true);
  const [alertNewCompetitors, setAlertNewCompetitors] = useState(true);
  const [minChangeThreshold, setMinChangeThreshold] = useState(1);
  const [autoGenerateIdeas, setAutoGenerateIdeas] = useState(false);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const configData = await getMonitoringConfig(productId);
      setConfig(configData);

      // Update form state
      setFrequency(configData.monitoring_frequency);
      setAlertNewFeatures(configData.alert_on_new_features);
      setAlertRemovedFeatures(configData.alert_on_removed_features);
      setAlertNewCompetitors(configData.alert_on_new_competitors);
      setMinChangeThreshold(configData.min_feature_change_threshold);
      setAutoGenerateIdeas(configData.auto_generate_ideas);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleToggleEnabled = async () => {
    if (!config) return;

    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const newConfig = config.monitoring_enabled
        ? await disableMonitoring(productId)
        : await enableMonitoring(productId);

      setConfig(newConfig);
      setSuccess(`Monitoring ${newConfig.monitoring_enabled ? 'enabled' : 'disabled'}`);
      if (onConfigChange) onConfigChange(newConfig);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveConfig = async () => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const newConfig = await updateMonitoringConfig(productId, {
        monitoring_frequency: frequency,
        alert_on_new_features: alertNewFeatures,
        alert_on_removed_features: alertRemovedFeatures,
        alert_on_new_competitors: alertNewCompetitors,
        min_feature_change_threshold: minChangeThreshold,
        auto_generate_ideas: autoGenerateIdeas,
      });

      setConfig(newConfig);
      setSuccess('Configuration saved successfully');
      if (onConfigChange) onConfigChange(newConfig);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerMonitoring = async () => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const result = await triggerMonitoring(productId);
      setActiveJobUuid(result.job_uuid);
      setSuccess('Monitoring job started');
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center space-x-2">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
          <span className="text-gray-500">Loading monitoring configuration...</span>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <p className="text-red-600">{error || 'Failed to load configuration'}</p>
        <button
          onClick={fetchConfig}
          className="mt-2 text-sm text-red-700 hover:text-red-800 underline"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Competitive Monitoring</h2>
            <p className="text-sm text-gray-500">
              Automatically track competitor changes and generate alerts
            </p>
          </div>
          <button
            onClick={handleToggleEnabled}
            disabled={saving}
            className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
              config.monitoring_enabled ? 'bg-blue-600' : 'bg-gray-200'
            } ${saving ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                config.monitoring_enabled ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded text-red-600 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="mx-6 mt-4 p-3 bg-green-50 border border-green-200 rounded text-green-600 text-sm">
          {success}
        </div>
      )}

      {/* Active Job Status */}
      {activeJobUuid && (
        <div className="mx-6 mt-4">
          <JobStatusCard
            jobUuid={activeJobUuid}
            onComplete={() => {
              setActiveJobUuid(null);
              fetchConfig();
            }}
            onError={() => setActiveJobUuid(null)}
            showDetails
          />
        </div>
      )}

      {/* Configuration Form */}
      <div className="p-6 space-y-6">
        {/* Monitoring Status */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Status:</span>
              <span className={`ml-2 font-medium ${config.monitoring_enabled ? 'text-green-600' : 'text-gray-500'}`}>
                {config.monitoring_enabled ? 'Active' : 'Disabled'}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Last Monitored:</span>
              <span className="ml-2">{formatDate(config.last_monitored_at)}</span>
            </div>
            <div>
              <span className="text-gray-500">Next Scheduled:</span>
              <span className="ml-2">{formatDate(config.next_scheduled_at)}</span>
            </div>
            <div>
              <span className="text-gray-500">Frequency:</span>
              <span className="ml-2 capitalize">{config.monitoring_frequency}</span>
            </div>
          </div>
        </div>

        {/* Frequency */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Monitoring Frequency
          </label>
          <select
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as typeof frequency)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="biweekly">Bi-weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>

        {/* Alert Preferences */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Alert Preferences
          </label>
          <div className="space-y-3">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={alertNewFeatures}
                onChange={(e) => setAlertNewFeatures(e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <span className="ml-2 text-sm text-gray-700">
                Alert on new features discovered
              </span>
            </label>
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={alertRemovedFeatures}
                onChange={(e) => setAlertRemovedFeatures(e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <span className="ml-2 text-sm text-gray-700">
                Alert on features removed
              </span>
            </label>
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={alertNewCompetitors}
                onChange={(e) => setAlertNewCompetitors(e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <span className="ml-2 text-sm text-gray-700">
                Alert on new competitors discovered
              </span>
            </label>
          </div>
        </div>

        {/* Minimum Change Threshold */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Minimum Feature Changes to Alert
          </label>
          <input
            type="number"
            min="1"
            max="10"
            value={minChangeThreshold}
            onChange={(e) => setMinChangeThreshold(parseInt(e.target.value) || 1)}
            className="w-24 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="mt-1 text-xs text-gray-500">
            Only generate alerts when at least this many features change
          </p>
        </div>

        {/* Auto-generate Ideas */}
        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={autoGenerateIdeas}
              onChange={(e) => setAutoGenerateIdeas(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <span className="ml-2 text-sm text-gray-700">
              Auto-generate ideas from new competitor features
            </span>
          </label>
          <p className="mt-1 ml-6 text-xs text-gray-500">
            When enabled, new competitor features will be converted to ideas for voting
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-between">
        <button
          onClick={handleTriggerMonitoring}
          disabled={saving || !config.monitoring_enabled}
          className="px-4 py-2 text-sm text-blue-600 border border-blue-600 rounded hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Run Monitoring Now
        </button>
        <button
          onClick={handleSaveConfig}
          disabled={saving}
          className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>
    </div>
  );
};

export default MonitoringConfigPanel;
