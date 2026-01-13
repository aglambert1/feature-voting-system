import React, { useState } from 'react';
import { URLFetchResponse } from '../types';
import api from '../services/api';

interface NoContentErrorDetail {
  error: 'no_content';
  message: string;
  meta_info: {
    title?: string;
    description?: string;
    keywords?: string;
    og_title?: string;
    og_description?: string;
  };
  has_meta: boolean;
}

interface URLFetchInputProps {
  onFetchComplete: (response: URLFetchResponse) => void;
  onError: (error: string) => void;
}

export const URLFetchInput: React.FC<URLFetchInputProps> = ({
  onFetchComplete,
  onError,
}) => {
  const [url, setUrl] = useState('');
  const [isFetching, setIsFetching] = useState(false);
  const [noContentError, setNoContentError] = useState<{ url: string; detail: NoContentErrorDetail } | null>(null);

  const handleFetch = async () => {
    if (!url.trim()) {
      onError('Please enter a URL');
      return;
    }

    // Basic URL validation
    try {
      new URL(url);
    } catch {
      onError('Please enter a valid URL (e.g., https://example.com)');
      return;
    }

    setIsFetching(true);
    setNoContentError(null);

    try {
      const response = await api.post<URLFetchResponse>(
        '/product-intelligence/products/fetch-url',
        { url: url.trim() }
      );

      onFetchComplete(response.data);
      setUrl(''); // Clear input on success
    } catch (error: any) {
      // Check for 422 no_content error (SPA/JavaScript page)
      // The axios interceptor transforms the error, so we check error.data.detail
      const errorData = error.data || error.response?.data;
      const detail = errorData?.detail;

      if (error.status === 422 && detail?.error === 'no_content') {
        setNoContentError({
          url: url.trim(),
          detail: detail
        });
      } else {
        // Handle both string and object detail formats
        const errorMessage = typeof detail === 'string'
          ? detail
          : detail?.message || error.message || 'Failed to fetch URL. Please check the URL and try again.';
        onError(errorMessage);
      }
    } finally {
      setIsFetching(false);
    }
  };

  const handleFetchMetaOnly = async () => {
    if (!noContentError) return;

    setIsFetching(true);

    try {
      const response = await api.post<URLFetchResponse>(
        '/product-intelligence/products/fetch-url-meta',
        { url: noContentError.url }
      );

      onFetchComplete(response.data);
      setUrl('');
      setNoContentError(null);
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      const errorMessage = typeof detail === 'string'
        ? detail
        : 'Failed to fetch meta tags.';
      onError(errorMessage);
      setNoContentError(null);
    } finally {
      setIsFetching(false);
    }
  };

  const handleSkip = () => {
    setNoContentError(null);
    setUrl('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isFetching) {
      handleFetch();
    }
  };

  // Show fallback options when no content found
  if (noContentError) {
    const { detail } = noContentError;
    const metaTitle = detail.meta_info?.title || detail.meta_info?.og_title;
    const metaDesc = detail.meta_info?.description || detail.meta_info?.og_description;

    return (
      <div className="w-full space-y-3">
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-md">
          <div className="flex items-start gap-2">
            <svg className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex-1">
              <h4 className="text-sm font-medium text-amber-800">
                Unable to Extract Page Content
              </h4>
              <p className="mt-1 text-sm text-amber-700">
                {detail.message}
              </p>

              {detail.has_meta && (
                <div className="mt-3 p-3 bg-white rounded border border-amber-100">
                  <p className="text-xs font-medium text-gray-600 mb-2">
                    Available meta information:
                  </p>
                  {metaTitle && (
                    <p className="text-sm text-gray-800 font-medium">{metaTitle}</p>
                  )}
                  {metaDesc && (
                    <p className="text-sm text-gray-600 mt-1">{metaDesc}</p>
                  )}
                </div>
              )}

              <div className="mt-4 flex gap-2">
                {detail.has_meta && (
                  <button
                    onClick={handleFetchMetaOnly}
                    disabled={isFetching}
                    className="
                      px-3 py-1.5 bg-amber-600 text-white rounded text-sm font-medium
                      hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500
                      disabled:bg-gray-300 disabled:cursor-not-allowed
                    "
                  >
                    {isFetching ? 'Fetching...' : 'Use Meta Tags'}
                  </button>
                )}
                <button
                  onClick={handleSkip}
                  disabled={isFetching}
                  className="
                    px-3 py-1.5 bg-gray-200 text-gray-700 rounded text-sm font-medium
                    hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400
                    disabled:cursor-not-allowed
                  "
                >
                  Skip URL
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        URL to Fetch
      </label>

      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="https://example.com/product-docs"
          disabled={isFetching}
          className="
            flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
            disabled:bg-gray-100 disabled:cursor-not-allowed
            text-sm
          "
        />

        <button
          onClick={handleFetch}
          disabled={isFetching || !url.trim()}
          className="
            px-4 py-2 bg-blue-600 text-white rounded-md font-medium
            hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
            disabled:bg-gray-300 disabled:cursor-not-allowed
            transition-colors duration-200
            text-sm whitespace-nowrap
          "
        >
          {isFetching ? (
            <span className="flex items-center gap-2">
              <svg
                className="animate-spin h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              Fetching...
            </span>
          ) : (
            'Fetch Content'
          )}
        </button>
      </div>

      <p className="text-xs text-gray-500">
        Fetches and extracts text content from web pages. Timeout: 10s, max 3 redirects.
      </p>
    </div>
  );
};
