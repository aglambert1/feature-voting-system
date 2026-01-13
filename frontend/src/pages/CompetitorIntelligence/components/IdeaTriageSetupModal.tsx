/**
 * IdeaTriageSetupModal
 *
 * Modal for configuring the Idea Triage Agent settings:
 * - Enable/disable automatic responses toggle
 * - Confidence threshold slider (50-99%)
 */

import { useState } from 'react';
import { updateTriageSettings } from '../../../services/api';
import { TriageSettings } from '../../../types';

interface Props {
  productId: number;
  currentSettings: TriageSettings | null;
  onClose: () => void;
  onSave: (settings: TriageSettings) => void;
}

export default function IdeaTriageSetupModal({ productId, currentSettings, onClose, onSave }: Props) {
  const [autoEnabled, setAutoEnabled] = useState(currentSettings?.auto_enabled || false);
  const [threshold, setThreshold] = useState(Math.round((currentSettings?.auto_threshold || 0.7) * 100));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      const updatedSettings = await updateTriageSettings(productId, {
        auto_enabled: autoEnabled,
        auto_threshold: threshold / 100,
      });
      onSave(updatedSettings);
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
          <h3 className="text-lg font-semibold text-gray-900">Idea Triage Agent Setup</h3>
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

          {/* Enable/Disable Toggle */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-900">
                Automatic Responses
              </label>
              <button
                onClick={() => setAutoEnabled(!autoEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  autoEnabled ? 'bg-blue-600' : 'bg-gray-200'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    autoEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <p className="text-sm text-gray-500">
              When enabled, the agent will automatically respond to new ideas that meet the confidence threshold.
            </p>
          </div>

          {/* Confidence Threshold Slider */}
          <div>
            <label className="block text-sm font-medium text-gray-900 mb-2">
              Confidence Threshold: {threshold}%
            </label>
            <input
              type="range"
              min="50"
              max="99"
              value={threshold}
              onChange={(e) => setThreshold(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              disabled={!autoEnabled}
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>50% (More auto-responses)</span>
              <span>99% (Fewer auto-responses)</span>
            </div>
            <p className="text-sm text-gray-500 mt-2">
              Ideas with AI confidence above this threshold will receive automatic responses.
            </p>
          </div>

          {/* Info Box */}
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>How it works:</strong> When a new idea is submitted, the AI analyzes it and generates a response.
              If the AI's confidence in the response exceeds your threshold, it's sent automatically.
              Otherwise, the idea is queued for your review.
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
