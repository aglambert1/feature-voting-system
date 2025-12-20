import React, { useState } from 'react';
import { URLFetchResponse } from '../types';
import api from '../services/api';

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

    try {
      const response = await api.post<URLFetchResponse>(
        '/product-intelligence/products/fetch-url',
        { url: url.trim() }
      );

      onFetchComplete(response.data);
      setUrl(''); // Clear input on success
    } catch (error: any) {
      onError(
        error.response?.data?.detail || 'Failed to fetch URL. Please check the URL and try again.'
      );
    } finally {
      setIsFetching(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isFetching) {
      handleFetch();
    }
  };

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
