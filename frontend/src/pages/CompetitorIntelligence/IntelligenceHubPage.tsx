/**
 * IntelligenceHubPage (Competitive Intelligence)
 *
 * Main container for the Competitive Discovery Agent results.
 * This page displays outputs from the Competitive Discovery Agent.
 *
 * Tab structure:
 * - Competitor Reports: Functional audit reports per competitor
 * - Landscape Analysis: Cross-competitor feature landscape
 * - Settings: Agent configuration
 *
 * Note: The "Opportunity Synthesis Agent" (three-source synthesis) will be
 * a separate page that combines data from this system with customer ideas
 * and internal feedback.
 */

import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import Navigation from "../../components/Navigation";
import AgentSettingsTab from "./components/AgentSettingsTab";
import CompetitorReportsTab from "./components/CompetitorReportsTab";
import api from "../../services/api";

// Tab configuration (Landscape Analysis moved to SynthesisHubPage)
type TabId = "competitor-reports" | "settings";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const tabs: Tab[] = [
  {
    id: "competitor-reports",
    label: "Competitor Reports",
    icon: (
      <svg
        className="w-5 h-5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
    ),
  },
  {
    id: "settings",
    label: "Settings",
    icon: (
      <svg
        className="w-5 h-5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
        />
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

  // Get active tab from URL or default to competitor-reports
  const activeTab = (searchParams.get("tab") as TabId) || "competitor-reports";

  // Fetch product info
  const fetchProduct = useCallback(async () => {
    if (!productId) return;

    try {
      setLoading(true);
      const response = await api.get<ProductInfo>(
        `/product-intelligence/products/${productId}`
      );
      setProduct(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load product");
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
            <p className="text-red-800">{error || "Product not found"}</p>
            <button
              onClick={() => navigate("/product-intelligence")}
              className="mt-2 text-red-600 hover:text-red-800 font-medium"
            >
              &larr; Back to Products
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
            onClick={() =>
              navigate(`/product-intelligence/products/${productId}`)
            }
            className="text-blue-600 hover:text-blue-800 mb-4 font-medium"
          >
            &larr; Back to Product Dashboard
          </button>

          <h1 className="text-2xl font-bold text-gray-900">
            {product.product_name}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Competitive Intelligence · Discovery Agent Results
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="border-b border-gray-200 mb-6">
          <nav
            className="-mb-px flex space-x-8 overflow-x-auto"
            aria-label="Tabs"
          >
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={`
                    group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap
                    ${
                      isActive
                        ? "border-blue-500 text-blue-600"
                        : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                    }
                  `}
                >
                  <span
                    className={`mr-2 ${
                      isActive
                        ? "text-blue-500"
                        : "text-gray-400 group-hover:text-gray-500"
                    }`}
                  >
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
          {activeTab === "competitor-reports" && (
            <CompetitorReportsTab
              productId={numProductId}
            />
          )}
          {activeTab === "settings" && (
            <AgentSettingsTab productId={numProductId} />
          )}
        </div>
      </main>
    </div>
  );
}
