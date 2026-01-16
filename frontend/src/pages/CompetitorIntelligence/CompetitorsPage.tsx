/**
 * CompetitorsPage
 *
 * Standalone page for managing competitors for a product.
 * Based on Stage2_CompetitorDiscovery but adapted for agent-based flow:
 * - View and select competitors for deep analysis tracking
 * - Add custom competitors
 * - Run discovery to find new competitors
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Navigation from "../../components/Navigation";
import CompetitorCard from "./components/CompetitorCard";
import AddCompetitorModal from "./components/AddCompetitorModal";
import api, {
  getAgentCompetitors,
  triggerCompetitorDiscovery,
} from "../../services/api";
import { AgentCompetitor } from "../../types";

interface LocalCompetitor {
  id: string;
  name: string;
  url: string;
  summary: string;
  relevance_score?: number;
  status?: "new" | "continuing" | "disappeared";
  status_explanation?: string;
  selected: boolean;
  discovery_source?: string;
}

export default function CompetitorsPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();

  const [competitors, setCompetitors] = useState<LocalCompetitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [productName, setProductName] = useState<string>("");
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (productId) {
      fetchProductAndCompetitors();
    }
  }, [productId]);

  const fetchProductAndCompetitors = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch product details
      const productResponse = await api.get(
        `/product-intelligence/products/${productId}`
      );
      setProductName(
        productResponse.data.product_name ||
          productResponse.data.name ||
          "Product"
      );

      // Fetch competitors
      const competitorsList = await getAgentCompetitors(parseInt(productId!));

      // Map to local format
      const mapped: LocalCompetitor[] = competitorsList.map(
        (c: AgentCompetitor) => ({
          id: c.id.toString(),
          name: c.competitor_name,
          url: c.competitor_url || "",
          summary: `${c.feature_count} features extracted`,
          selected: c.deep_analysis_enabled,
          status: c.status as "new" | "continuing" | "disappeared" | undefined,
        })
      );

      setCompetitors(mapped);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to load competitors"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDiscoverCompetitors = async () => {
    try {
      setDiscovering(true);
      setError(null);

      await triggerCompetitorDiscovery(parseInt(productId!));

      // Poll or wait a bit, then refresh
      // For now, just show a message
      setError(
        "Discovery started. This may take a few minutes. Refresh to see results."
      );

      // Refresh competitors list
      await fetchProductAndCompetitors();
    } catch (err: any) {
      setError(
        err.response?.data?.detail || err.message || "Failed to start discovery"
      );
    } finally {
      setDiscovering(false);
    }
  };

  const toggleCompetitor = (competitorId: string) => {
    setCompetitors((prev) =>
      prev.map((c) =>
        c.id === competitorId ? { ...c, selected: !c.selected } : c
      )
    );
    setHasChanges(true);
  };

  const handleAddCustom = async (_competitor: {
    name: string;
    url: string;
    summary?: string;
  }) => {
    // Note: Custom competitor addition is not yet available in the agent-based flow.
    // Users should use the session-based workflow for adding custom competitors.
    setError(
      "Custom competitor addition is coming soon. For now, use competitor discovery to find competitors."
    );
    setShowAddModal(false);
  };

  const handleSaveChanges = async () => {
    try {
      setSaving(true);
      setError(null);

      // Get current state from server once
      const currentList = await getAgentCompetitors(parseInt(productId!));
      const currentMap = new Map(
        currentList.map((c) => [c.id, c.deep_analysis_enabled])
      );

      // Update deep analysis status for each competitor that changed
      const updatePromises = competitors
        .filter((competitor) => {
          const wasEnabled = currentMap.get(parseInt(competitor.id)) || false;
          return competitor.selected !== wasEnabled;
        })
        .map(async (competitor) => {
          if (competitor.selected) {
            await api.post(
              `/product-intelligence/agents/${productId}/competitors/${competitor.id}/enable-deep-analysis`
            );
          } else {
            await api.post(
              `/product-intelligence/agents/${productId}/competitors/${competitor.id}/disable-deep-analysis`
            );
          }
        });

      await Promise.all(updatePromises);

      setHasChanges(false);
      // Navigate back to dashboard
      navigate(`/product-intelligence/products/${productId}`);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || err.message || "Failed to save changes"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleBack = () => {
    if (hasChanges) {
      if (
        window.confirm(
          "You have unsaved changes. Are you sure you want to leave?"
        )
      ) {
        navigate(`/product-intelligence/products/${productId}`);
      }
    } else {
      navigate(`/product-intelligence/products/${productId}`);
    }
  };

  const selectedCount = competitors.filter((c) => c.selected).length;

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

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={handleBack}
            className="text-blue-600 hover:text-blue-800 text-sm font-medium mb-4 flex items-center"
          >
            <svg
              className="w-4 h-4 mr-1"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back to Product Dashboard
          </button>

          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Competitors</h1>
              <p className="text-gray-600 mt-1">{productName}</p>
            </div>
            <div className="text-sm text-gray-600">
              {selectedCount} of {competitors.length} selected for deep analysis
            </div>
          </div>
        </div>

        {/* Info Box */}
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start">
            <svg
              className="w-5 h-5 text-blue-600 mr-3 flex-shrink-0 mt-0.5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clipRule="evenodd"
              />
            </svg>
            <div className="text-sm text-blue-800">
              <strong>Select competitors for deep analysis tracking.</strong>{" "}
              Selected competitors will be audited for feature gaps, positioning
              updates, and market momentum. Unselected competitors will still
              appear in your list but won't be analyzed.
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mb-6 flex gap-3">
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 border border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50"
          >
            + Add Custom Competitor
          </button>
          <button
            onClick={handleDiscoverCompetitors}
            disabled={discovering}
            className="px-4 py-2 border border-gray-600 text-gray-600 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            {discovering ? "Discovering..." : "🔍 Discover New Competitors"}
          </button>
        </div>

        {/* Competitors Grid */}
        {competitors.length === 0 ? (
          <div className="text-center py-12 px-4 bg-white rounded-lg border-2 border-dashed border-gray-300 mb-6">
            <svg
              className="mx-auto h-12 w-12 text-gray-400 mb-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              No Competitors Found
            </h3>
            <p className="text-gray-600 mb-4 max-w-md mx-auto">
              Run competitor discovery or add competitors manually to get
              started.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={handleDiscoverCompetitors}
                disabled={discovering}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {discovering ? "Discovering..." : "Discover Competitors"}
              </button>
              <button
                onClick={() => setShowAddModal(true)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                Add Manually
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {competitors.map((competitor) => (
              <CompetitorCard
                key={competitor.id}
                competitor={competitor}
                onToggle={() => toggleCompetitor(competitor.id)}
                showStatus={false}
              />
            ))}
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex justify-between border-t border-gray-200 pt-6">
          <button
            onClick={handleBack}
            className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
          >
            ← Back to Dashboard
          </button>
          <button
            onClick={handleSaveChanges}
            disabled={saving || !hasChanges}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </main>

      {/* Add Competitor Modal */}
      {showAddModal && (
        <AddCompetitorModal
          onAdd={handleAddCustom}
          onClose={() => setShowAddModal(false)}
        />
      )}
    </div>
  );
}
