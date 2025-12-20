import React, { useState } from 'react';
import { ProductSource, DocumentUploadResponse, URLFetchResponse } from '../types';
import { FileUploadZone } from './FileUploadZone';
import { URLFetchInput } from './URLFetchInput';

interface MultiSourceInputProps {
  sources: ProductSource[];
  onSourcesChange: (sources: ProductSource[]) => void;
  maxSources?: number;
}

export const MultiSourceInput: React.FC<MultiSourceInputProps> = ({
  sources,
  onSourcesChange,
  maxSources = 10,
}) => {
  const [activeTab, setActiveTab] = useState<'text' | 'url' | 'document'>('text');
  const [textInput, setTextInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());

  const totalTokens = sources.reduce((sum, s) => sum + (s.token_estimate || 0), 0);
  const TOKEN_LIMIT = 180000;
  const TOKEN_WARNING = 150000;

  const addSource = (source: ProductSource) => {
    console.log('[MultiSourceInput] addSource called with:', source);
    console.log('[MultiSourceInput] Current sources count:', sources.length);

    if (sources.length >= maxSources) {
      console.log('[MultiSourceInput] ERROR: Max sources reached');
      setError(`Maximum ${maxSources} sources allowed`);
      return;
    }

    const estimatedTokens = totalTokens + (source.token_estimate || 0);
    console.log('[MultiSourceInput] Token check:', estimatedTokens, '/', TOKEN_LIMIT);

    if (estimatedTokens > TOKEN_LIMIT) {
      console.log('[MultiSourceInput] ERROR: Token limit exceeded');
      setError(`Adding this source would exceed the ${TOKEN_LIMIT.toLocaleString()} token limit`);
      return;
    }

    console.log('[MultiSourceInput] Adding source, new count will be:', sources.length + 1);
    onSourcesChange([...sources, source]);
    setTextInput('');
    setError(null);
  };

  const removeSource = (index: number) => {
    onSourcesChange(sources.filter((_, i) => i !== index));
    setError(null);
  };

  const handleAddText = () => {
    if (!textInput.trim()) {
      setError('Please enter some text');
      return;
    }

    if (textInput.trim().length < 50) {
      setError('Text must be at least 50 characters');
      return;
    }

    const tokenEstimate = Math.floor(textInput.length / 4);

    addSource({
      type: 'text',
      content: textInput.trim(),
      extracted_text: textInput.trim(),
      token_estimate: tokenEstimate,
    });
  };

  const handleDocumentUpload = (response: DocumentUploadResponse) => {
    console.log('[MultiSourceInput] Document upload callback triggered:', response);
    addSource({
      type: 'document',
      file_id: response.file_id,
      filename: response.filename,
      extracted_text: response.extracted_text,
      size_mb: response.size_mb,
      token_estimate: response.token_estimate,
    });
  };

  const handleURLFetch = (response: URLFetchResponse) => {
    addSource({
      type: 'url',
      url: response.url,
      title: response.title,
      extracted_text: response.extracted_text,
      fetch_timestamp: response.fetch_timestamp,
      token_estimate: response.token_estimate,
    });
  };

  const getSourceLabel = (source: ProductSource, index: number): string => {
    if (source.type === 'text') {
      return `Text Description ${index + 1}`;
    } else if (source.type === 'document') {
      return source.filename || 'Document';
    } else if (source.type === 'url') {
      return source.title || source.url || 'URL';
    }
    return `Source ${index + 1}`;
  };

  const getSourcePreview = (source: ProductSource): string => {
    const text = source.extracted_text || source.content || '';
    return text.length > 150 ? text.substring(0, 150) + '...' : text;
  };

  const toggleSourceExpansion = (index: number) => {
    const newExpanded = new Set(expandedSources);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSources(newExpanded);
  };

  return (
    <div className="space-y-4">
      {/* Sources List */}
      {sources.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="block text-sm font-medium text-gray-700">
              Product Information Sources ({sources.length}/{maxSources})
            </label>
            <div className="text-xs text-gray-500">
              {totalTokens.toLocaleString()} / {TOKEN_LIMIT.toLocaleString()} tokens
              {totalTokens > TOKEN_WARNING && (
                <span className="ml-1 text-yellow-600 font-medium">
                  (approaching limit)
                </span>
              )}
            </div>
          </div>

          <div className="space-y-2">
            {sources.map((source, index) => {
              const isExpanded = expandedSources.has(index);
              const fullText = source.extracted_text || source.content || '';

              return (
                <div
                  key={index}
                  className="bg-gray-50 rounded-md border border-gray-200 overflow-hidden"
                >
                  {/* Header - Always visible, clickable to expand */}
                  <div className="flex items-start gap-3 p-3">
                    {/* Source Icon */}
                    <div className="flex-shrink-0 mt-1">
                      {source.type === 'text' && (
                        <svg
                          className="h-5 w-5 text-gray-400"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M4 6h16M4 12h16M4 18h7"
                          />
                        </svg>
                      )}
                      {source.type === 'document' && (
                        <svg
                          className="h-5 w-5 text-blue-500"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                          />
                        </svg>
                      )}
                      {source.type === 'url' && (
                        <svg
                          className="h-5 w-5 text-green-500"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"
                          />
                        </svg>
                      )}
                    </div>

                    {/* Source Content - Clickable area */}
                    <div
                      className="flex-1 min-w-0 cursor-pointer"
                      onClick={() => toggleSourceExpansion(index)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <h4 className="text-sm font-medium text-gray-900 truncate">
                          {getSourceLabel(source, index)}
                        </h4>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500 whitespace-nowrap">
                            {source.token_estimate?.toLocaleString() || 0} tokens
                          </span>
                          {/* Expand/Collapse icon */}
                          <svg
                            className={`h-4 w-4 text-gray-400 transition-transform ${
                              isExpanded ? 'transform rotate-180' : ''
                            }`}
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M19 9l-7 7-7-7"
                            />
                          </svg>
                        </div>
                      </div>

                      {!isExpanded && (
                        <p className="text-xs text-gray-600 mt-1">
                          {getSourcePreview(source)}
                        </p>
                      )}

                      {source.type === 'document' && source.size_mb !== undefined && !isExpanded && (
                        <p className="text-xs text-gray-500 mt-1">
                          {source.size_mb.toFixed(1)} MB
                        </p>
                      )}
                    </div>

                    {/* Remove Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeSource(index);
                      }}
                      className="flex-shrink-0 p-1 text-gray-400 hover:text-red-600 transition-colors"
                      title="Remove source"
                    >
                      <svg
                        className="h-5 w-5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>

                  {/* Expanded Content - Show full text when expanded */}
                  {isExpanded && (
                    <div className="px-3 pb-3 pl-11">
                      <div className="mt-2 p-3 bg-white rounded border border-gray-200 max-h-96 overflow-y-auto">
                        <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans">
                          {fullText}
                        </pre>
                      </div>

                      {/* Additional metadata when expanded */}
                      <div className="mt-2 flex gap-4 text-xs text-gray-500">
                        {source.type === 'document' && source.size_mb !== undefined && (
                          <span>File size: {source.size_mb.toFixed(1)} MB</span>
                        )}
                        {source.type === 'url' && source.url && (
                          <span>URL: {source.url}</span>
                        )}
                        {source.type === 'url' && source.fetch_timestamp && (
                          <span>Fetched: {new Date(source.fetch_timestamp).toLocaleString()}</span>
                        )}
                        <span>Characters: {fullText.length.toLocaleString()}</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Add Source Section */}
      {sources.length < maxSources && (
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">
            Add Product Information
          </label>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* Tabs */}
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => {
                  setActiveTab('text');
                  setError(null);
                }}
                className={`
                  py-2 px-1 border-b-2 font-medium text-sm whitespace-nowrap
                  ${
                    activeTab === 'text'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                Text
              </button>
              <button
                onClick={() => {
                  setActiveTab('url');
                  setError(null);
                }}
                className={`
                  py-2 px-1 border-b-2 font-medium text-sm whitespace-nowrap
                  ${
                    activeTab === 'url'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                URL
              </button>
              <button
                onClick={() => {
                  setActiveTab('document');
                  setError(null);
                }}
                className={`
                  py-2 px-1 border-b-2 font-medium text-sm whitespace-nowrap
                  ${
                    activeTab === 'document'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                Document
              </button>
            </nav>
          </div>

          {/* Tab Content */}
          <div className="pt-2">
            {activeTab === 'text' && (
              <div className="space-y-3">
                <textarea
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="Enter product description (minimum 50 characters)..."
                  rows={6}
                  className="
                    w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm
                    focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                    resize-none text-sm
                  "
                />
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">
                    {textInput.length} characters (~{Math.floor(textInput.length / 4)} tokens)
                  </span>
                  <button
                    onClick={handleAddText}
                    disabled={textInput.trim().length < 50}
                    className="
                      px-4 py-2 bg-blue-600 text-white rounded-md font-medium text-sm
                      hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                      disabled:bg-gray-300 disabled:cursor-not-allowed
                      transition-colors duration-200
                    "
                  >
                    Add Text
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'url' && (
              <URLFetchInput
                onFetchComplete={handleURLFetch}
                onError={setError}
              />
            )}

            {activeTab === 'document' && (
              <FileUploadZone
                onUploadComplete={handleDocumentUpload}
                onError={setError}
              />
            )}
          </div>
        </div>
      )}

      {sources.length >= maxSources && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
          <p className="text-sm text-yellow-800">
            Maximum number of sources ({maxSources}) reached. Remove a source to add more.
          </p>
        </div>
      )}
    </div>
  );
};
