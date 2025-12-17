/**
 * AddCompetitorModal Component
 *
 * Modal for manually adding custom competitors that weren't discovered by AI.
 * Allows users to supplement the automated discovery with known competitors.
 */

import { useState, FormEvent, ChangeEvent } from 'react';

interface AddCompetitorData {
  name: string;
  url: string;
  summary?: string;
}

interface AddCompetitorModalProps {
  onAdd: (competitor: AddCompetitorData) => void;
  onClose: () => void;
}

const AddCompetitorModal = ({ onAdd, onClose }: AddCompetitorModalProps) => {
  const [name, setName] = useState<string>('');
  const [url, setUrl] = useState<string>('');
  const [summary, setSummary] = useState<string>('');

  const handleSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    onAdd({ name, url, summary: summary || undefined });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-xl font-bold mb-4">Add Custom Competitor</h3>

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
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Summary (Optional)
            </label>
            <textarea
              value={summary}
              onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setSummary(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="Brief description of what they do..."
            />
          </div>

          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Add Competitor
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddCompetitorModal;
