/**
 * SynthesisHubPage
 *
 * Page for viewing and managing opportunity synthesis results.
 * Combines competitive intelligence, customer feedback, and internal feedback
 * to identify prioritized product opportunities.
 *
 * Features:
 * - Source availability status
 * - Run synthesis button
 * - Prioritized opportunities list
 * - Three-way / two-way match indicators
 * - Evidence from each source
 * - Export to JSON/CSV
 * - Create idea from opportunity
 */

import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Navigation from "../../components/Navigation";
import {
  getSynthesisStatus,
  triggerSynthesis,
  getLatestSynthesis,
  getSynthesisResults,
  exportSynthesisJson,
  exportSynthesisCsv,
  createIdeaFromOpportunity,
} from "../../services/api";
import type {
  SynthesisStatusResponse,
  SynthesisRun,
  SynthesizedOpportunity,
} from "../../types";
import api from "../../services/api";

interface ProductInfo {
  id: number;
  product_name: string;
}

export default function SynthesisHubPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();

  // Product info
  const [product, setProduct] = useState<ProductInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Synthesis state
  const [status, setStatus] = useState<SynthesisStatusResponse | null>(null);
  const [currentRun, setCurrentRun] = useState<SynthesisRun | null>(null);
  const [opportunities, setOpportunities] = useState<SynthesizedOpportunity[]>([]);
  const [synthesizing, setSynthesizing] = useState(false);
  const [synthError, setSynthError] = useState<string | null>(null);

  // Polling for processing status
  const [pollingRunId, setPollingRunId] = useState<number | null>(null);

  // Expanded opportunity card
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Creating idea modal
  const [creatingIdeaFor, setCreatingIdeaFor] = useState<number | null>(null);
  const [additionalDescription, setAdditionalDescription] = useState("");
  const [createIdeaLoading, setCreateIdeaLoading] = useState(false);

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

  // Fetch synthesis status
  const fetchStatus = useCallback(async () => {
    if (!productId) return;

    try {
      const data = await getSynthesisStatus(parseInt(productId, 10));
      setStatus(data);
    } catch (err: any) {
      console.error("Failed to load synthesis status:", err);
    }
  }, [productId]);

  // Fetch latest synthesis results
  const fetchLatestResults = useCallback(async () => {
    if (!productId) return;

    try {
      const data = await getLatestSynthesis(parseInt(productId, 10));
      if (data.run.status !== "none") {
        setCurrentRun(data.run);
        setOpportunities(data.opportunities);

        // If there's a processing run, start polling
        if (data.run.status === "processing" || data.run.status === "pending") {
          setSynthesizing(true);
          setPollingRunId(data.run.id);
        }
      }
    } catch (err: any) {
      console.error("Failed to load synthesis results:", err);
    }
  }, [productId]);

  // Poll for synthesis progress
  useEffect(() => {
    if (!pollingRunId || !productId) return;

    const interval = setInterval(async () => {
      try {
        const data = await getSynthesisResults(parseInt(productId, 10), pollingRunId);
        setCurrentRun(data.run);

        if (data.run.status === "completed") {
          setOpportunities(data.opportunities);
          setPollingRunId(null);
          setSynthesizing(false);
          fetchStatus(); // Refresh status
        } else if (data.run.status === "failed") {
          setSynthError(data.run.error_message || "Synthesis failed");
          setPollingRunId(null);
          setSynthesizing(false);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [pollingRunId, productId, fetchStatus]);

  // Initial load
  useEffect(() => {
    fetchProduct();
    fetchStatus();
    fetchLatestResults();
  }, [fetchProduct, fetchStatus, fetchLatestResults]);

  // Handle run synthesis
  const handleRunSynthesis = async () => {
    if (!productId) return;

    try {
      setSynthesizing(true);
      setSynthError(null);
      const run = await triggerSynthesis(parseInt(productId, 10));
      setCurrentRun(run);
      setPollingRunId(run.id);
    } catch (err: any) {
      setSynthError(err.message || "Failed to start synthesis");
      setSynthesizing(false);
    }
  };

  // Handle create idea
  const handleCreateIdea = async () => {
    if (!productId || !creatingIdeaFor) return;

    try {
      setCreateIdeaLoading(true);
      const result = await createIdeaFromOpportunity(
        parseInt(productId, 10),
        creatingIdeaFor,
        additionalDescription || undefined
      );

      // Update the opportunity in the list
      setOpportunities((prev) =>
        prev.map((o) =>
          o.id === creatingIdeaFor ? { ...o, linked_idea_id: result.idea_id } : o
        )
      );

      setCreatingIdeaFor(null);
      setAdditionalDescription("");
    } catch (err: any) {
      alert(err.message || "Failed to create idea");
    } finally {
      setCreateIdeaLoading(false);
    }
  };

  // Get match type badge
  const getMatchBadge = (sourceCount: number) => {
    if (sourceCount >= 3) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
          Three-Way Match
        </span>
      );
    } else if (sourceCount === 2) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
          Two-Way Match
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
        Single Source
      </span>
    );
  };

  // Get action badge
  const getActionBadge = (action: string | null) => {
    const colors: Record<string, string> = {
      high_priority: "bg-red-100 text-red-800",
      investigate: "bg-blue-100 text-blue-800",
      monitor: "bg-gray-100 text-gray-600",
      quick_win: "bg-green-100 text-green-800",
    };
    const labels: Record<string, string> = {
      high_priority: "High Priority",
      investigate: "Investigate",
      monitor: "Monitor",
      quick_win: "Quick Win",
    };
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
          colors[action || "monitor"] || colors.monitor
        }`}
      >
        {labels[action || "monitor"] || action}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
            <button
              onClick={() => navigate("/product-intelligence")}
              className="mt-2 text-red-600 hover:text-red-800"
            >
              Back to Products
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate(`/product-intelligence/products/${productId}`)}
            className="text-sm text-gray-500 hover:text-gray-700 mb-2 flex items-center"
          >
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to {product?.product_name}
          </button>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Opportunity Synthesis</h1>
              <p className="text-gray-600 mt-1">
                Combining competitive, customer, and internal signals
              </p>
            </div>
            <div className="flex space-x-3">
              {currentRun && currentRun.status === "completed" && (
                <>
                  <button
                    onClick={() => exportSynthesisJson(parseInt(productId!, 10), currentRun.id, product?.product_name)}
                    className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    JSON
                  </button>
                  <button
                    onClick={() => exportSynthesisCsv(parseInt(productId!, 10), currentRun.id, product?.product_name)}
                    className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    CSV
                  </button>
                </>
              )}
              <button
                onClick={handleRunSynthesis}
                disabled={synthesizing}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {synthesizing ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Running Synthesis...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Run Synthesis
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Error message */}
        {synthError && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{synthError}</p>
          </div>
        )}

        {/* Source Status */}
        {status && (
          <div className="bg-white rounded-lg shadow mb-6 p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Available Sources</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Competitive */}
              <div className={`p-4 rounded-lg border-2 ${status.sources_available.competitive ? "border-green-200 bg-green-50" : "border-gray-200 bg-gray-50"}`}>
                <div className="flex items-center mb-2">
                  {status.sources_available.competitive ? (
                    <svg className="w-5 h-5 text-green-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-gray-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                  )}
                  <span className="font-medium text-gray-900">Competitive</span>
                </div>
                <p className="text-sm text-gray-600">
                  {status.sources_available.competitive_detail || "No landscape analysis available"}
                </p>
              </div>

              {/* Customer */}
              <div className={`p-4 rounded-lg border-2 ${status.sources_available.customer ? "border-green-200 bg-green-50" : "border-gray-200 bg-gray-50"}`}>
                <div className="flex items-center mb-2">
                  {status.sources_available.customer ? (
                    <svg className="w-5 h-5 text-green-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-gray-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                  )}
                  <span className="font-medium text-gray-900">Customer</span>
                </div>
                <p className="text-sm text-gray-600">
                  {status.sources_available.customer_detail || "No customer ideas submitted"}
                </p>
              </div>

              {/* Internal */}
              <div className={`p-4 rounded-lg border-2 ${status.sources_available.internal ? "border-green-200 bg-green-50" : "border-gray-200 bg-gray-50"}`}>
                <div className="flex items-center mb-2">
                  {status.sources_available.internal ? (
                    <svg className="w-5 h-5 text-green-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-gray-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                  )}
                  <span className="font-medium text-gray-900">Internal</span>
                </div>
                <p className="text-sm text-gray-600">
                  {status.sources_available.internal_detail || "No internal feedback imported"}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Processing Status */}
        {currentRun && currentRun.status === "processing" && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
            <div className="flex items-center">
              <svg className="animate-spin h-5 w-5 text-blue-600 mr-3" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <div>
                <p className="text-blue-800 font-medium">Synthesis in progress...</p>
                <p className="text-blue-600 text-sm">Analyzing sources and identifying opportunities</p>
              </div>
            </div>
          </div>
        )}

        {/* Summary Stats */}
        {currentRun && currentRun.status === "completed" && currentRun.summary_stats && (
          <div className="bg-white rounded-lg shadow mb-6 p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Synthesis Summary</h2>
            {currentRun.analysis_summary && (
              <p className="text-gray-600 mb-4">{currentRun.analysis_summary}</p>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <p className="text-3xl font-bold text-red-600">{currentRun.summary_stats.three_way_matches}</p>
                <p className="text-sm text-gray-500">Three-Way Matches</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-yellow-600">{currentRun.summary_stats.two_way_matches}</p>
                <p className="text-sm text-gray-500">Two-Way Matches</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-gray-600">{currentRun.summary_stats.single_source}</p>
                <p className="text-sm text-gray-500">Single Source</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-indigo-600">{currentRun.summary_stats.total_opportunities}</p>
                <p className="text-sm text-gray-500">Total</p>
              </div>
            </div>
          </div>
        )}

        {/* Opportunities List */}
        {opportunities.length > 0 ? (
          <div className="space-y-4">
            <h2 className="text-lg font-medium text-gray-900">Prioritized Opportunities</h2>
            {opportunities.map((opp) => (
              <div
                key={opp.id}
                className="bg-white rounded-lg shadow overflow-hidden"
              >
                {/* Header */}
                <div
                  className="p-4 cursor-pointer hover:bg-gray-50"
                  onClick={() => setExpandedId(expandedId === opp.id ? null : opp.id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        {getMatchBadge(opp.source_count)}
                        {getActionBadge(opp.recommended_action)}
                        {opp.linked_idea_id && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                            Idea Created
                          </span>
                        )}
                      </div>
                      <h3 className="text-lg font-medium text-gray-900">{opp.opportunity_name}</h3>
                      {opp.opportunity_summary && (
                        <p className="text-gray-600 text-sm mt-1">{opp.opportunity_summary}</p>
                      )}
                    </div>
                    <div className="flex items-center space-x-4 ml-4">
                      <div className="text-right">
                        <p className="text-2xl font-bold text-indigo-600">{Math.round(opp.priority_score)}</p>
                        <p className="text-xs text-gray-500">Priority</p>
                      </div>
                      <svg
                        className={`w-5 h-5 text-gray-400 transition-transform ${expandedId === opp.id ? "rotate-180" : ""}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>
                </div>

                {/* Expanded Content */}
                {expandedId === opp.id && (
                  <div className="border-t border-gray-200 p-4 bg-gray-50">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      {/* Competitive Evidence */}
                      <div className={`p-3 rounded-lg ${opp.competitive_evidence ? "bg-blue-50 border border-blue-200" : "bg-gray-100 border border-gray-200"}`}>
                        <h4 className="font-medium text-gray-900 mb-2">Competitive</h4>
                        {opp.competitive_evidence ? (
                          <div className="text-sm">
                            <p className="text-gray-700">
                              <strong>{opp.competitive_evidence.competitor_count}</strong> competitors have this
                            </p>
                            {opp.competitive_evidence.prevalence && (
                              <p className="text-gray-600">Prevalence: {opp.competitive_evidence.prevalence}</p>
                            )}
                            {opp.competitive_evidence.competitors && opp.competitive_evidence.competitors.length > 0 && (
                              <p className="text-gray-600 mt-1">
                                {opp.competitive_evidence.competitors.slice(0, 3).join(", ")}
                                {opp.competitive_evidence.competitors.length > 3 && ` +${opp.competitive_evidence.competitors.length - 3} more`}
                              </p>
                            )}
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500">No competitive signal</p>
                        )}
                      </div>

                      {/* Customer Evidence */}
                      <div className={`p-3 rounded-lg ${opp.customer_evidence ? "bg-green-50 border border-green-200" : "bg-gray-100 border border-gray-200"}`}>
                        <h4 className="font-medium text-gray-900 mb-2">Customer</h4>
                        {opp.customer_evidence ? (
                          <div className="text-sm">
                            <p className="text-gray-700">
                              <strong>{opp.customer_evidence.vote_count}</strong> votes
                            </p>
                            <p className="text-gray-600 truncate" title={opp.customer_evidence.idea_title}>
                              "{opp.customer_evidence.idea_title}"
                            </p>
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500">No customer signal</p>
                        )}
                      </div>

                      {/* Internal Evidence */}
                      <div className={`p-3 rounded-lg ${opp.internal_evidence ? "bg-orange-50 border border-orange-200" : "bg-gray-100 border border-gray-200"}`}>
                        <h4 className="font-medium text-gray-900 mb-2">Internal</h4>
                        {opp.internal_evidence ? (
                          <div className="text-sm space-y-1">
                            {opp.internal_evidence.winloss && (
                              <p className="text-gray-700">
                                <strong>{opp.internal_evidence.winloss.deal_count}</strong> deals (${opp.internal_evidence.winloss.total_value.toLocaleString()})
                              </p>
                            )}
                            {opp.internal_evidence.support && (
                              <p className="text-gray-700">
                                <strong>{opp.internal_evidence.support.ticket_count}</strong> support tickets
                              </p>
                            )}
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500">No internal signal</p>
                        )}
                      </div>
                    </div>

                    {/* Keywords */}
                    {opp.feature_keywords && opp.feature_keywords.length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-sm font-medium text-gray-700 mb-1">Keywords</h4>
                        <div className="flex flex-wrap gap-1">
                          {opp.feature_keywords.map((keyword, i) => (
                            <span key={i} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-200 text-gray-700">
                              {keyword}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex justify-end space-x-3">
                      {opp.customer_evidence && (
                        <button
                          onClick={() => navigate(`/ideas/${opp.customer_evidence!.idea_id}`)}
                          className="text-sm text-indigo-600 hover:text-indigo-800"
                        >
                          View Related Idea
                        </button>
                      )}
                      {!opp.linked_idea_id && (
                        <button
                          onClick={() => setCreatingIdeaFor(opp.id)}
                          className="inline-flex items-center px-3 py-1.5 border border-indigo-600 rounded text-sm font-medium text-indigo-600 hover:bg-indigo-50"
                        >
                          Create Idea
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : currentRun && currentRun.status === "completed" ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Opportunities Found</h3>
            <p className="text-gray-600">
              The synthesis completed but no opportunities were identified.
              Try adding more source data.
            </p>
          </div>
        ) : !synthesizing && (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Ready to Synthesize</h3>
            <p className="text-gray-600 mb-4">
              Click "Run Synthesis" to combine your competitive, customer, and internal data
              into prioritized opportunities.
            </p>
            <button
              onClick={handleRunSynthesis}
              disabled={synthesizing}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
            >
              Run Synthesis
            </button>
          </div>
        )}

        {/* Create Idea Modal */}
        {creatingIdeaFor !== null && (
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Create Idea from Opportunity</h3>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Additional Description (optional)
                </label>
                <textarea
                  value={additionalDescription}
                  onChange={(e) => setAdditionalDescription(e.target.value)}
                  rows={3}
                  className="w-full border border-gray-300 rounded-md p-2 text-sm"
                  placeholder="Add any additional context for this idea..."
                />
              </div>
              <div className="flex justify-end space-x-3">
                <button
                  onClick={() => {
                    setCreatingIdeaFor(null);
                    setAdditionalDescription("");
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateIdea}
                  disabled={createIdeaLoading}
                  className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  {createIdeaLoading ? "Creating..." : "Create Idea"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
