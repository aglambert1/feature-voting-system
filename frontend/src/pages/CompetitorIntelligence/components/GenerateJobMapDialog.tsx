import { useState } from 'react';

interface GenerateJobMapDialogProps {
  hasExistingMap: boolean;
  onConfirm: (guidance: string) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

export default function GenerateJobMapDialog({
  hasExistingMap,
  onConfirm,
  onCancel,
  isSubmitting,
}: GenerateJobMapDialogProps) {
  const [guidance, setGuidance] = useState('');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">
          Generate job map from product info
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Claude will analyze your product name, description, category, and features to draft a
          customer need map.{hasExistingMap
            ? " You'll review the changes and choose which to keep before anything is committed. Your current map stays unchanged until you apply."
            : " You can edit any need after generation."}
        </p>

        <label className="block mb-1.5">
          <span className="text-sm font-medium text-gray-700">
            Context for job map generation
          </span>
          <span className="text-sm text-gray-400 ml-1">(optional)</span>
        </label>
        <textarea
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          rows={4}
          placeholder="Describe your target customer, key use cases, market segment, or anything the product description doesn't capture well — e.g. 'This is a B2B tool used by enterprise procurement teams, not consumers.'"
          value={guidance}
          onChange={(e) => setGuidance(e.target.value)}
          disabled={isSubmitting}
        />

        <div className="flex justify-end gap-3 mt-5">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(guidance.trim())}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            {isSubmitting && (
              <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            )}
            {hasExistingMap ? 'Generate and review' : 'Generate need map'}
          </button>
        </div>
      </div>
    </div>
  );
}
