/**
 * AgentSettingsTab
 *
 * Competitive Intelligence Agent Configuration tab.
 * Uses the shared CompetitiveIntelligenceSettingsForm component.
 */

import { useState, useEffect, useCallback } from 'react';
import { getAgentConfig, updateAgentConfig } from '../../../services/api';
import { CompetitiveAgentConfig } from '../../../types';
import CompetitiveIntelligenceSettingsForm, { SettingsFormData } from './CompetitiveIntelligenceSettingsForm';

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
  const [formData, setFormData] = useState<SettingsFormData>({});

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

  const handleFormChange = (data: SettingsFormData) => {
    setFormData(data);
    setHasChanges(Object.keys(data).length > 0);
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
    // Force re-render of form by temporarily setting config to null
    const currentConfig = config;
    setConfig(null);
    setTimeout(() => setConfig(currentConfig), 0);
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
          <h2 className="text-lg font-semibold text-gray-900">Competitive Intelligence Settings</h2>
          <p className="text-sm text-gray-500">Configure how competitive analysis operates</p>
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

      <CompetitiveIntelligenceSettingsForm
        config={config}
        onChange={handleFormChange}
        showLastRunInfo={true}
      />
    </div>
  );
}
