/**
 * IntelligenceHubPage
 *
 * Main container for the agent-centric competitive intelligence system.
 * Replaces the session-based workflow with a tabbed interface:
 * - Overview: Dashboard with status and alerts
 * - Competitors: Manage competitors and deep analysis
 * - Features: Feature clusters and intensity
 * - Insights: Strategic analysis results
 * - Settings: Agent configuration
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import Navigation from '../../components/Navigation';
import AgentSettingsTab from './components/AgentSettingsTab';
import CompetitorsTab from './components/CompetitorsTab';
import FeaturesTab from './components/FeaturesTab';
import OverviewTab from './components/OverviewTab';
import InsightsTab from './components/InsightsTab';
import RunAnalysisDropdown from './components/RunAnalysisDropdown';
import api from '../../services/api';

// Tab configuration
type TabId = 'overview' | 'competitors' | 'features' | 'insights' | 'settings';

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const tabs: Tab[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
  },
  {
    id: 'competitors',
    label: 'Competitors',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    ),
  },
  {
    id: 'features',
    label: 'Features',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
  {
    id: 'insights',
    label: 'Insights',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    id: 'settings',
    label: 'Agent Settings',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
];

interface ProductInfo {
  id: number;
  product_name: string;
  product_description: string;
  analysis_version: number;
}

export default function IntelligenceHubPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [product, setProduct] = useState<ProductInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Get active tab from URL or default to overview
  const activeTab = (searchParams.get('tab') as TabId) || 'overview';

  // Fetch product info
  const fetchProduct = useCallback(async () => {
    if (!productId) return;

    try {
      setLoading(true);
      const response = await api.get<ProductInfo>(`/product-intelligence/products/${productId}`);
      setProduct(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load product');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchProduct();
  }, [fetchProduct]);

  const handleTabChange = (tabId: TabId) => {
    setSearchParams({ tab: tabId });
  };

  const handleJobQueued = () => {
    // Trigger refresh of child components
    setRefreshKey(prev => prev + 1);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 py-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error || 'Product not found'}</p>
            <button
              onClick={() => navigate('/product-intelligence')}
              className="mt-2 text-red-600 hover:text-red-800 font-medium"
            >
              ← Back to Products
            </button>
          </div>
        </main>
      </div>
    );
  }

  const numProductId = parseInt(productId!, 10);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/product-intelligence')}
            className="text-blue-600 hover:text-blue-800 mb-4 font-medium"
          >
            ← Back to Products
          </button>

          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {product.product_name}
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                Competitive Intelligence Hub
              </p>
            </div>

            <RunAnalysisDropdown
              productId={numProductId}
              onJobQueued={handleJobQueued}
            />
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8 overflow-x-auto" aria-label="Tabs">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={`
                    group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap
                    ${isActive
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }
                  `}
                >
                  <span className={`mr-2 ${isActive ? 'text-blue-500' : 'text-gray-400 group-hover:text-gray-500'}`}>
                    {tab.icon}
                  </span>
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-lg shadow">
          {activeTab === 'overview' && (
            <OverviewTab productId={numProductId} refreshKey={refreshKey} />
          )}
          {activeTab === 'competitors' && (
            <CompetitorsTab productId={numProductId} refreshKey={refreshKey} />
          )}
          {activeTab === 'features' && (
            <FeaturesTab productId={numProductId} refreshKey={refreshKey} />
          )}
          {activeTab === 'insights' && (
            <InsightsTab productId={numProductId} refreshKey={refreshKey} />
          )}
          {activeTab === 'settings' && (
            <AgentSettingsTab productId={numProductId} />
          )}
        </div>
      </main>
    </div>
  );
}
