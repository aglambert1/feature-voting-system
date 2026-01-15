/**
 * FeatureQueryChat Component
 *
 * A chat-like interface for querying whether features exist in a product.
 * Uses the same similarity detection logic as the Idea Triage Agent,
 * ensuring consistent results.
 */

import { useState, useRef, useEffect, FormEvent, KeyboardEvent } from 'react';
import { queryProductFeatures } from '../../../services/api';
import { FeatureQueryResponse } from '../../../types';

interface Message {
  id: string;
  type: 'user' | 'system';
  content: string;
  timestamp: Date;
  response?: FeatureQueryResponse;
}

interface FeatureQueryChatProps {
  productId: number;
  productName: string;
}

const SystemMessage = ({ message }: { message: Message }) => {
  const response = message.response;
  const confidencePercent = response ? Math.round(response.confidence * 100) : 0;

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%]">
        <div className="bg-gray-100 rounded-lg p-4 mb-2">
          {/* Best match indicator - shows % match for highest rated feature */}
          {response && (
            <div className="mb-3">
              <span
                className={`inline-flex items-center gap-1.5 text-sm font-medium px-2 py-1 rounded ${
                  confidencePercent >= 85
                    ? 'bg-green-100 text-green-700'
                    : confidencePercent >= 70
                    ? 'bg-yellow-100 text-yellow-700'
                    : confidencePercent >= 50
                    ? 'bg-orange-100 text-orange-700'
                    : 'bg-gray-200 text-gray-600'
                }`}
              >
                Best match: {confidencePercent}%
              </span>
            </div>
          )}

          {/* AI Response */}
          <p className="text-gray-800 whitespace-pre-wrap">{message.content}</p>
        </div>

        <p className="text-xs text-gray-400 mt-2">
          {message.timestamp.toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
};

const UserMessage = ({ message }: { message: Message }) => (
  <div className="flex justify-end">
    <div className="max-w-[85%]">
      <div className="bg-blue-600 text-white rounded-lg p-3">
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
      <p className="text-xs text-gray-400 mt-1 text-right">
        {message.timestamp.toLocaleTimeString()}
      </p>
    </div>
  </div>
);

const FeatureQueryChat = ({ productId, productName }: FeatureQueryChatProps) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll chat container to bottom when new messages arrive
  // Uses scrollTop on container instead of scrollIntoView to prevent page scroll
  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();

    const query = input.trim();
    if (!query || query.length < 10) {
      setError('Please enter at least 10 characters to describe the feature.');
      return;
    }

    setError(null);

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: query,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await queryProductFeatures(productId, query);

      // Add system response
      const systemMessage: Message = {
        id: `system-${Date.now()}`,
        type: 'system',
        content: response.response_text,
        timestamp: new Date(),
        response,
      };
      setMessages((prev) => [...prev, systemMessage]);
    } catch (err) {
      console.error('Feature query error:', err);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        type: 'system',
        content: 'Sorry, there was an error processing your query. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-[500px] border border-gray-200 rounded-lg bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <div>
          <h3 className="font-medium text-gray-900">Feature Query</h3>
          <p className="text-xs text-gray-500">
            Ask if a feature exists in {productName}
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            Clear chat
          </button>
        )}
      </div>

      {/* Messages area */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-gray-500">
            <svg
              className="w-12 h-12 text-gray-300 mb-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <p className="font-medium mb-1">No queries yet</p>
            <p className="text-sm">
              Describe a feature to check if it exists in {productName}
            </p>
            <div className="mt-4 text-xs text-gray-400">
              <p>Example queries:</p>
              <p className="italic mt-1">"Does this product support dark mode?"</p>
              <p className="italic">"Real-time collaboration and commenting"</p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) =>
              message.type === 'user' ? (
                <UserMessage key={message.id} message={message} />
              ) : (
                <SystemMessage key={message.id} message={message} />
              )
            )}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-gray-500">
                    <svg
                      className="animate-spin h-4 w-4"
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
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    <span className="text-sm">Searching features...</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 p-4">
        {error && (
          <p className="text-sm text-red-600 mb-2">{error}</p>
        )}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe a feature to check if it exists..."
            className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={1}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || input.trim().length < 10}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <svg
                className="animate-spin h-4 w-4"
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
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            ) : (
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            )}
          </button>
        </form>
        <p className="text-xs text-gray-400 mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
};

export default FeatureQueryChat;
