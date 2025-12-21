/**
 * SourceChangeWarning Component
 *
 * Modal warning displayed when product source documentation has changed
 * since the last analysis. Prompts user to re-analyze before discovering competitors.
 */

interface SourceChangeWarningProps {
  onReanalyze: () => void;
  onContinueAnyway: () => void;
  onCancel: () => void;
}

const SourceChangeWarning = ({ onReanalyze, onContinueAnyway, onCancel }: SourceChangeWarningProps) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <div className="flex items-start gap-3">
          <div className="text-yellow-500 text-2xl flex-shrink-0">⚠️</div>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-gray-900">Product Information Changed</h3>
            <p className="text-sm text-gray-600 mt-2">
              Your product documentation sources have changed since the last analysis.
              We recommend re-analyzing your product to ensure accurate competitor discovery.
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-2">
          <button
            onClick={onReanalyze}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium min-h-[44px]"
          >
            Re-analyze Product First (Recommended)
          </button>
          <button
            onClick={onContinueAnyway}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium text-gray-700 min-h-[44px]"
          >
            Continue with Current Analysis
          </button>
          <button
            onClick={onCancel}
            className="w-full px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors min-h-[44px]"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export default SourceChangeWarning;
