import { useState, useEffect, ChangeEvent } from 'react';

interface SourceData {
  url?: string;
  filename?: string;
}

interface SourceInputProps {
  sourceType: 'text' | 'document' | 'url';
  sourceData: SourceData | null;
  description: string;
  onSourceTypeChange: (type: 'text' | 'document' | 'url') => void;
  onSourceDataChange: (data: SourceData | null) => void;
  onDescriptionChange: (description: string) => void;
  minLength?: number;
  readOnly?: boolean;
}

/**
 * SourceInput Component
 *
 * Provides tabbed interface for selecting and entering product description source:
 * - Text: Direct textarea input
 * - URL: URL input field + textarea for pasted content
 * - Document: Filename input + textarea for pasted content
 */
export default function SourceInput({
  sourceType,
  sourceData,
  description,
  onSourceTypeChange,
  onSourceDataChange,
  onDescriptionChange,
  minLength = 10,
  readOnly = false
}: SourceInputProps) {
  const [localUrl, setLocalUrl] = useState<string>('');
  const [localFilename, setLocalFilename] = useState<string>('');

  // Initialize local state from props
  useEffect(() => {
    if (sourceData) {
      setLocalUrl(sourceData.url || '');
      setLocalFilename(sourceData.filename || '');
    }
  }, [sourceData]);

  const handleTabChange = (type: 'text' | 'document' | 'url'): void => {
    if (readOnly) return;
    onSourceTypeChange(type);
  };

  const handleUrlChange = (e: ChangeEvent<HTMLInputElement>): void => {
    const url = e.target.value;
    setLocalUrl(url);
    onSourceDataChange({ url });
  };

  const handleFilenameChange = (e: ChangeEvent<HTMLInputElement>): void => {
    const filename = e.target.value;
    setLocalFilename(filename);
    onSourceDataChange({ filename });
  };

  const tabs = [
    { id: 'text' as const, label: 'Text' },
    { id: 'url' as const, label: 'URL' },
    { id: 'document' as const, label: 'Document' }
  ];

  return (
    <div className="space-y-3">
      {/* Tab buttons */}
      <div className="flex border-b border-gray-200">
        {tabs.map(tab => (
          <button
            key={tab.id}
            type="button"
            onClick={() => handleTabChange(tab.id)}
            disabled={readOnly}
            className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
              sourceType === tab.id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } ${readOnly ? 'cursor-not-allowed' : 'cursor-pointer'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="mt-3">
        {sourceType === 'text' && (
          <div>
            <textarea
              value={description}
              onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onDescriptionChange(e.target.value)}
              placeholder="Enter product description..."
              readOnly={readOnly}
              rows={8}
              className={`w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                readOnly ? 'bg-gray-50 cursor-not-allowed' : ''
              }`}
            />
            <p className="mt-1 text-xs text-gray-500">
              Minimum {minLength} characters required
            </p>
          </div>
        )}

        {sourceType === 'url' && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                URL
              </label>
              <input
                type="url"
                value={localUrl}
                onChange={handleUrlChange}
                placeholder="https://example.com"
                readOnly={readOnly}
                className={`w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  readOnly ? 'bg-gray-50 cursor-not-allowed' : ''
                }`}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Extracted Text from URL
              </label>
              <textarea
                value={description}
                onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onDescriptionChange(e.target.value)}
                placeholder="Paste the extracted text from the URL here..."
                readOnly={readOnly}
                rows={8}
                className={`w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  readOnly ? 'bg-gray-50 cursor-not-allowed' : ''
                }`}
              />
              <p className="mt-1 text-xs text-gray-500">
                Visit the URL, copy the relevant text, and paste it here. Minimum {minLength} characters.
              </p>
            </div>
          </div>
        )}

        {sourceType === 'document' && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Document Filename
              </label>
              <input
                type="text"
                value={localFilename}
                onChange={handleFilenameChange}
                placeholder="product_brochure.pdf"
                readOnly={readOnly}
                className={`w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  readOnly ? 'bg-gray-50 cursor-not-allowed' : ''
                }`}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Extracted Text from Document
              </label>
              <textarea
                value={description}
                onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onDescriptionChange(e.target.value)}
                placeholder="Paste the extracted text from the document here..."
                readOnly={readOnly}
                rows={8}
                className={`w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  readOnly ? 'bg-gray-50 cursor-not-allowed' : ''
                }`}
              />
              <p className="mt-1 text-xs text-gray-500">
                Extract text from your document and paste it here. Minimum {minLength} characters.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
