/**
 * CompetitiveIntelligenceSetupModal
 *
 * Modal wrapper for configuring the Competitive Intelligence Agent settings.
 * Uses the shared CompetitiveIntelligenceSettingsForm component.
 */

import { useState } from 'react';
import { updateAgentConfig } from '../../../services/api';
import { CompetitiveAgentConfig } from '../../../types';
import CompetitiveIntelligenceSettingsForm, { SettingsFormData } from './CompetitiveIntelligenceSettingsForm';

interface Props {
  productId: number;
  currentConfig: CompetitiveAgentConfig | null;
  onClose: () => void;
  onSave: (config: CompetitiveAgentConfig) => void;
}

export default function CompetitiveIntelligenceSetupModal({ productId, currentConfig, onClose, onSave }: Props) {
  const [formData, setFormData] = useState<SettingsFormData>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFormChange = (data: SettingsFormData) => {
    setFormData(data);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      const updatedConfig = await updateAgentConfig(productId, formData);
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

        <div className="p-4">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
              {error}
            </div>
          )}

          <CompetitiveIntelligenceSettingsForm
            config={currentConfig}
            onChange={handleFormChange}
            showLastRunInfo={false}
          />
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
