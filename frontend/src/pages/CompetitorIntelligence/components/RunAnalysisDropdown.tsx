/**
 * RunAnalysisDropdown
 *
 * Dropdown menu for triggering various analysis actions:
 * - Discover Competitors
 * - Reanalyze Product
 * - Run Clustering
 */

import { useState, useRef, useEffect } from 'react';
import {
  triggerCompetitorDiscovery,
  triggerProductReanalysis,
  triggerFeatureClustering,
} from '../../../services/api';
import { AgentJobResponse } from '../../../types';

interface Props {
  productId: number;
  onJobQueued?: (job: AgentJobResponse) => void;
}

interface ActionItem {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  action: () => Promise<AgentJobResponse>;
}

export default function RunAnalysisDropdown({ productId, onJobQueued }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Clear message after timeout
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const actions: ActionItem[] = [
    {
      id: 'discover',
      label: 'Discover Competitors',
      description: 'Find new competitors using AI',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      ),
      action: () => triggerCompetitorDiscovery(productId),
    },
    {
      id: 'reanalyze',
      label: 'Reanalyze Product',
      description: 'Update product analysis',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      ),
      action: () => triggerProductReanalysis(productId),
    },
    {
      id: 'clustering',
      label: 'Run Feature Clustering',
      description: 'Cluster features and calculate intensity',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      ),
      action: () => triggerFeatureClustering(productId),
    },
  ];

  const handleAction = async (item: ActionItem) => {
    setLoading(item.id);
    setMessage(null);

    try {
      const result = await item.action();
      setMessage({ type: 'success', text: result.message });
      onJobQueued?.(result);
      setIsOpen(false);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to queue job' });
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
      >
        <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        Run Analysis
        <svg className={`w-4 h-4 ml-2 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Status Message */}
      {message && (
        <div className={`absolute right-0 top-full mt-2 px-4 py-2 rounded-lg text-sm whitespace-nowrap z-20 ${
          message.type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          {message.text}
        </div>
      )}

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-72 bg-white rounded-lg shadow-lg border border-gray-200 z-10">
          <div className="py-1">
            {actions.map((item) => (
              <button
                key={item.id}
                onClick={() => handleAction(item)}
                disabled={loading !== null}
                className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-start gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span className={`flex-shrink-0 mt-0.5 ${loading === item.id ? 'animate-spin' : 'text-gray-400'}`}>
                  {loading === item.id ? (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  ) : (
                    item.icon
                  )}
                </span>
                <div>
                  <p className="text-sm font-medium text-gray-900">{item.label}</p>
                  <p className="text-xs text-gray-500">{item.description}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
