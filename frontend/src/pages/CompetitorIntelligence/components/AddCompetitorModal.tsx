/**
 * AddCompetitorModal Component
 *
 * Modal for manually adding custom competitors that weren't discovered by AI.
 * Allows users to supplement the automated discovery with known competitors.
 * Calls the backend API to create the competitor and auto-enables deep analysis.
 */

import { useState, FormEvent, ChangeEvent } from 'react';
import { addCompetitorManually } from '../../../services/api';

interface AddCompetitorModalProps {
  productId: number;
  onAdd: () => void;  // Callback to refresh list after successful add
  onClose: () => void;
}

const AddCompetitorModal = ({ productId, onAdd, onClose }: AddCompetitorModalProps) => {
  const [name, setName] = useState<string>('');
  const [url, setUrl] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      await addCompetitorManually(productId, name, url);
      onAdd();
      onClose();
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to add competitor';
      setError(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-xl font-bold mb-4">Add Competitor Manually</h3>

        <p className="text-sm text-gray-600 mb-4">
          Add a competitor not found via market discovery. The competitor will be automatically
          selected for deep analysis.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Competitor Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., Competitor Inc."
              required
              minLength={2}
              disabled={saving}
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Website URL *
            </label>
            <input
              type="url"
              value={url}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setUrl(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="https://competitor.com"
              required
              disabled={saving}
            />
          </div>

          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Adding...' : 'Add Competitor'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddCompetitorModal;
