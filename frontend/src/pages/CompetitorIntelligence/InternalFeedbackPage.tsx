/**
 * InternalFeedbackPage
 *
 * Page for importing and viewing internal feedback data (sales win/loss, support tickets).
 * This is a source for the Opportunity Synthesis Agent.
 *
 * Features:
 * - Unified file upload supporting both structured data and activity streams
 * - Auto-detection of file type based on content
 * - Combined import history table
 * - Win/loss themes display
 * - Support themes display
 * - Activity insights display
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import Navigation from "../../components/Navigation";
import {
  uploadInternalFeedback,
  getInternalFeedbackImports,
  getInternalFeedbackThemes,
  getInternalFeedbackImportStatus,
  deleteInternalFeedbackImport,
  reprocessInternalFeedback,
  uploadActivityData,
  getActivityImports,
  getActivityImportStatus,
  getActivityInsights,
  deleteActivityImport,
  reprocessActivityImport,
} from "../../services/api";
import type {
  InternalFeedbackImport,
  WinLossTheme,
  SupportTheme,
  ActivityImport,
  DealActivityInsight,
  SupportActivityInsight,
} from "../../types";
import api from "../../services/api";
import { formatDateTime } from "../../utils/date";

// Tab types - simplified to just import and themes
type TabId = "import" | "themes";

interface Tab {
  id: TabId;
  label: string;
  description: string;
}

const tabs: Tab[] = [
  { id: "import", label: "Import Data", description: "Upload CRM exports and activity data" },
  { id: "themes", label: "Extracted Themes", description: "Merged insights from all sources" },
];

interface ProductInfo {
  id: number;
  product_name: string;
}

// Unified import record type for display
interface UnifiedImport {
  id: number;
  type: "structured" | "activity";
  filename: string;
  format_type: string;
  status: string;
  imported_at: string;
  data_summary: string;
  error_message?: string | null;
}

export default function InternalFeedbackPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Product info
  const [product, setProduct] = useState<ProductInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Tab state - initialize from URL param if present
  const initialTab = searchParams.get("tab") === "themes" ? "themes" : "import";
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);

  // Unified upload state
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  // Combined imports (both structured and activity)
  const [structuredImports, setStructuredImports] = useState<InternalFeedbackImport[]>([]);
  const [activityImports, setActivityImports] = useState<ActivityImport[]>([]);
  const [dealInsights, setDealInsights] = useState<DealActivityInsight[]>([]);
  const [supportInsights, setSupportInsights] = useState<SupportActivityInsight[]>([]);

  // Themes state
  const [winlossThemes, setWinlossThemes] = useState<WinLossTheme[]>([]);
  const [supportThemes, setSupportThemes] = useState<SupportTheme[]>([]);
  const [themesLoading, setThemesLoading] = useState(false);

  // Polling for processing status
  const [pollingStructuredId, setPollingStructuredId] = useState<number | null>(null);
  const [pollingActivityId, setPollingActivityId] = useState<number | null>(null);

  // Fetch product info
  const fetchProduct = useCallback(async () => {
    if (!productId) return;

    try {
      setLoading(true);
      const response = await api.get<ProductInfo>(
        `/product-intelligence/products/${productId}`
      );
      setProduct(response.data);
    } catch (err: any) {
      console.error("Failed to fetch product:", err);
      setError(err.message || "Failed to load product");
    } finally {
      setLoading(false);
    }
  }, [productId]);

  // Fetch structured imports
  const fetchStructuredImports = useCallback(async () => {
    if (!productId) return;

    try {
      const data = await getInternalFeedbackImports(parseInt(productId, 10));
      setStructuredImports(data);

      // Check if any import is processing
      const processingImport = data.find((i) => i.status === "processing");
      if (processingImport) {
        setPollingStructuredId(processingImport.id);
      }
    } catch (err: any) {
      console.error("Failed to fetch structured imports:", err);
    }
  }, [productId]);

  // Fetch themes
  const fetchThemes = useCallback(async () => {
    if (!productId) return;

    try {
      setThemesLoading(true);
      const data = await getInternalFeedbackThemes(parseInt(productId, 10));
      setWinlossThemes(data.winloss_themes);
      setSupportThemes(data.support_themes);
    } catch (err: any) {
      console.error("Failed to fetch themes:", err);
    } finally {
      setThemesLoading(false);
    }
  }, [productId]);

  // Fetch activity imports
  const fetchActivityImports = useCallback(async () => {
    if (!productId) return;

    try {
      const data = await getActivityImports(parseInt(productId, 10));
      setActivityImports(data);

      // Check if any import is processing
      const processingImport = data.find((i) => i.status === "processing");
      if (processingImport) {
        setPollingActivityId(processingImport.id);
      }
    } catch (err: any) {
      console.error("Failed to fetch activity imports:", err);
    }
  }, [productId]);

  // Fetch activity insights
  const fetchActivityInsights = useCallback(async () => {
    if (!productId) return;

    try {
      const data = await getActivityInsights(parseInt(productId, 10));
      setDealInsights(data.deal_insights);
      setSupportInsights(data.support_insights);
    } catch (err: any) {
      console.error("Failed to fetch activity insights:", err);
    }
  }, [productId]);

  // Initial fetch
  useEffect(() => {
    fetchProduct();
  }, [fetchProduct]);

  useEffect(() => {
    if (product) {
      fetchStructuredImports();
      fetchThemes();
      fetchActivityImports();
      fetchActivityInsights();
    }
  }, [product, fetchStructuredImports, fetchThemes, fetchActivityImports, fetchActivityInsights]);

  // Poll for structured import processing status
  useEffect(() => {
    if (!pollingStructuredId || !productId) return;

    const interval = setInterval(async () => {
      try {
        const status = await getInternalFeedbackImportStatus(
          parseInt(productId, 10),
          pollingStructuredId
        );

        if (status.themes_extracted || status.status === "failed") {
          setPollingStructuredId(null);
          fetchStructuredImports();
          fetchThemes();
        }
      } catch (err) {
        console.error("Error polling status:", err);
        setPollingStructuredId(null);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [pollingStructuredId, productId, fetchStructuredImports, fetchThemes]);

  // Poll for activity import processing status
  useEffect(() => {
    if (!pollingActivityId || !productId) return;

    const interval = setInterval(async () => {
      try {
        const status = await getActivityImportStatus(
          parseInt(productId, 10),
          pollingActivityId
        );

        if (status.status === "completed" || status.status === "failed") {
          setPollingActivityId(null);
          fetchActivityImports();
          fetchActivityInsights();
        }
      } catch (err) {
        console.error("Error polling activity status:", err);
        setPollingActivityId(null);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [pollingActivityId, productId, fetchActivityImports, fetchActivityInsights]);

  // Detect file type and handle upload
  const detectFileType = async (file: File): Promise<"structured" | "activity" | "unknown"> => {
    const filename = file.name.toLowerCase();

    // Markdown files are always activity data
    if (filename.endsWith(".md") || filename.endsWith(".markdown")) {
      return "activity";
    }

    // For JSON files, peek at content
    if (filename.endsWith(".json")) {
      try {
        const text = await file.text();
        const data = JSON.parse(text);

        // Check for activity indicators: deals with activities array
        if (data.deals && Array.isArray(data.deals) && data.deals.length > 0) {
          const firstDeal = data.deals[0];
          if (firstDeal.activities && Array.isArray(firstDeal.activities)) {
            return "activity";
          }
          // Check for structured indicators: deals with reason field
          if (firstDeal.reason || firstDeal.id) {
            return "structured";
          }
        }

        // Default JSON to structured if it has the expected structure
        if (data.deals || data.support_tickets) {
          return "structured";
        }
      } catch {
        // Parse error - let backend handle it
        return "unknown";
      }
    }

    return "unknown";
  };

  // Handle unified file upload
  const handleFileUpload = async (file: File) => {
    if (!productId) return;

    const validExtensions = [".json", ".md", ".markdown"];
    const isValid = validExtensions.some((ext) =>
      file.name.toLowerCase().endsWith(ext)
    );

    if (!isValid) {
      setUploadError("Please upload a JSON or Markdown file");
      return;
    }

    try {
      setUploading(true);
      setUploadError(null);

      const fileType = await detectFileType(file);

      if (fileType === "activity" || file.name.toLowerCase().endsWith(".md") || file.name.toLowerCase().endsWith(".markdown")) {
        // Activity data
        const result = await uploadActivityData(parseInt(productId, 10), file);
        setActivityImports((prev) => [result, ...prev]);
        if (result.status === "processing") {
          setPollingActivityId(result.id);
        }
      } else {
        // Structured data (default for JSON without activities)
        const result = await uploadInternalFeedback(parseInt(productId, 10), file);
        setStructuredImports((prev) => [result, ...prev]);
        if (result.status === "processing") {
          setPollingStructuredId(result.id);
        }
      }
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload file");
    } finally {
      setUploading(false);
    }
  };

  // Handle drag and drop
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  };

  // Handle delete structured import
  const handleDeleteStructured = async (importId: number) => {
    if (!productId) return;
    if (!confirm("Delete this import and all its extracted themes?")) return;

    try {
      await deleteInternalFeedbackImport(parseInt(productId, 10), importId);
      setStructuredImports((prev) => prev.filter((i) => i.id !== importId));
      fetchThemes();
    } catch (err: any) {
      alert(err.message || "Failed to delete import");
    }
  };

  // Handle reprocess structured
  const handleReprocessStructured = async (importId: number) => {
    if (!productId) return;

    try {
      const result = await reprocessInternalFeedback(parseInt(productId, 10), importId);
      setStructuredImports((prev) =>
        prev.map((i) => (i.id === importId ? result : i))
      );
      if (result.status === "processing") {
        setPollingStructuredId(result.id);
      }
    } catch (err: any) {
      alert(err.message || "Failed to reprocess import");
    }
  };

  // Handle delete activity import
  const handleDeleteActivity = async (importId: number) => {
    if (!productId) return;
    if (!confirm("Delete this import and all its extracted insights?")) return;

    try {
      await deleteActivityImport(parseInt(productId, 10), importId);
      setActivityImports((prev) => prev.filter((i) => i.id !== importId));
      fetchActivityInsights();
    } catch (err: any) {
      alert(err.message || "Failed to delete import");
    }
  };

  // Handle reprocess activity
  const handleReprocessActivity = async (importId: number) => {
    if (!productId) return;

    try {
      const result = await reprocessActivityImport(parseInt(productId, 10), importId);
      setActivityImports((prev) =>
        prev.map((i) => (i.id === importId ? result : i))
      );
      if (result.status === "processing") {
        setPollingActivityId(result.id);
      }
    } catch (err: any) {
      alert(err.message || "Failed to reprocess import");
    }
  };

  // Format currency
  const formatCurrency = (value: number | null) => {
    if (value === null) return "N/A";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  // Format date

  // Build unified import list sorted by date
  const unifiedImports: UnifiedImport[] = [
    ...structuredImports.map((i) => ({
      id: i.id,
      type: "structured" as const,
      filename: i.filename,
      format_type: "JSON",
      status: i.status,
      imported_at: i.imported_at,
      data_summary: `${i.deals_count} deals, ${i.tickets_count} tickets`,
      error_message: i.error_message,
    })),
    ...activityImports.map((i) => ({
      id: i.id,
      type: "activity" as const,
      filename: i.filename,
      format_type: i.format_type.toUpperCase(),
      status: i.status,
      imported_at: i.imported_at,
      data_summary: `${i.deals_count} deals, ${i.activities_count} activities`,
      error_message: i.error_message,
    })),
  ].sort((a, b) => new Date(b.imported_at).getTime() - new Date(a.imported_at).getTime());

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

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate(`/product-intelligence/products/${productId}`)}
            className="text-blue-600 hover:text-blue-800 mb-4 font-medium"
          >
            &larr; Back to Product Dashboard
          </button>

          <h1 className="text-2xl font-bold text-gray-900">
            Internal Feedback
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {product.product_name} - Sales Win/Loss &amp; Support Data
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8" aria-label="Tabs">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    py-4 px-1 border-b-2 font-medium text-sm group
                    ${
                      isActive
                        ? "border-blue-500 text-blue-600"
                        : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                    }
                  `}
                >
                  <span>{tab.label}</span>
                  <span className={`block text-xs font-normal ${isActive ? "text-blue-400" : "text-gray-400"}`}>
                    {tab.description}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-lg shadow">
          {activeTab === "import" && (
            <div className="p-6">
              {/* Unified Upload Area */}
              <div
                className={`
                  border-2 border-dashed rounded-lg p-8 text-center
                  ${dragActive ? "border-blue-500 bg-blue-50" : "border-gray-300"}
                  ${uploading ? "opacity-50 pointer-events-none" : ""}
                `}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json,.md,.markdown"
                  onChange={handleFileChange}
                  className="hidden"
                />

                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>

                <p className="mt-4 text-sm text-gray-600">
                  {uploading ? (
                    "Uploading..."
                  ) : (
                    <>
                      Drag and drop your file here, or{" "}
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="text-blue-600 hover:text-blue-800 font-medium"
                      >
                        browse
                      </button>
                    </>
                  )}
                </p>
                <p className="mt-2 text-xs text-gray-500">
                  Supports JSON (structured or activity) and Markdown (activity) files
                </p>

                {uploadError && (
                  <p className="mt-4 text-sm text-red-600">{uploadError}</p>
                )}
              </div>

              {/* Import History - MOVED ABOVE FORMAT EXAMPLES */}
              {unifiedImports.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">
                    Import History
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            File
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Type
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Status
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Data
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Imported
                          </th>
                          <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {unifiedImports.map((imp) => (
                          <tr key={`${imp.type}-${imp.id}`}>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="text-sm text-gray-900">{imp.filename}</div>
                              <div className="text-xs text-gray-500">{imp.format_type}</div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span
                                className={`
                                  inline-flex px-2 py-1 text-xs font-medium rounded-full
                                  ${imp.type === "structured"
                                    ? "bg-blue-100 text-blue-800"
                                    : "bg-purple-100 text-purple-800"}
                                `}
                              >
                                {imp.type === "structured" ? "Structured" : "Activity"}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span
                                className={`
                                  inline-flex px-2 py-1 text-xs font-medium rounded-full
                                  ${
                                    imp.status === "completed"
                                      ? "bg-green-100 text-green-800"
                                      : imp.status === "processing"
                                      ? "bg-yellow-100 text-yellow-800"
                                      : imp.status === "failed"
                                      ? "bg-red-100 text-red-800"
                                      : "bg-gray-100 text-gray-800"
                                  }
                                `}
                              >
                                {imp.status === "processing" && (
                                  <svg
                                    className="animate-spin -ml-0.5 mr-1.5 h-3 w-3"
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
                                )}
                                {imp.status}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {imp.data_summary}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {formatDateTime(imp.imported_at)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                              {(imp.status === "completed" || imp.status === "failed") && (
                                <button
                                  onClick={() =>
                                    imp.type === "structured"
                                      ? handleReprocessStructured(imp.id)
                                      : handleReprocessActivity(imp.id)
                                  }
                                  className={`mr-4 ${
                                    imp.type === "structured"
                                      ? "text-blue-600 hover:text-blue-900"
                                      : "text-purple-600 hover:text-purple-900"
                                  }`}
                                >
                                  Reprocess
                                </button>
                              )}
                              <button
                                onClick={() =>
                                  imp.type === "structured"
                                    ? handleDeleteStructured(imp.id)
                                    : handleDeleteActivity(imp.id)
                                }
                                className="text-red-600 hover:text-red-900"
                              >
                                Delete
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Data Summary */}
              {(structuredImports.length > 0 || activityImports.length > 0) && (
                <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <h3 className="text-sm font-medium text-blue-900 mb-2">
                    Data Sources Summary
                  </h3>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-blue-700 font-medium">
                        {structuredImports.filter(i => i.status === "completed").length}
                      </span>
                      <span className="text-blue-600 ml-1">structured imports</span>
                    </div>
                    <div>
                      <span className="text-purple-700 font-medium">
                        {activityImports.filter(i => i.status === "completed").length}
                      </span>
                      <span className="text-purple-600 ml-1">activity imports</span>
                    </div>
                    <div>
                      <span className="text-blue-700 font-medium">{dealInsights.length}</span>
                      <span className="text-blue-600 ml-1">deal insights</span>
                    </div>
                    <div>
                      <span className="text-purple-700 font-medium">{supportInsights.length}</span>
                      <span className="text-purple-600 ml-1">support insights</span>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-blue-600">
                    Insights are merged and displayed in the Extracted Themes tab.
                  </p>
                </div>
              )}

              {/* Expected Formats - MOVED BELOW IMPORT HISTORY */}
              <div className="mt-6">
                <h3 className="text-sm font-medium text-gray-900 mb-3">
                  Supported Formats
                </h3>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="text-xs font-medium text-gray-700 mb-2 flex items-center">
                      <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-800 mr-2">
                        Structured
                      </span>
                      JSON - Win/Loss Reasons
                    </h4>
                    <pre className="text-xs text-gray-600 overflow-x-auto">
{`{
  "deals": [{
    "id": "deal-1",
    "outcome": "lost",
    "competitor_name": "Competitor A",
    "reason": "Missing integration",
    "deal_value": 50000
  }],
  "support_tickets": [{
    "id": "ticket-1",
    "category": "feature_request",
    "subject": "Need PDF export"
  }]
}`}
                    </pre>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="text-xs font-medium text-gray-700 mb-2 flex items-center">
                      <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-purple-100 text-purple-800 mr-2">
                        Activity
                      </span>
                      JSON or Markdown - Raw Activities
                    </h4>
                    <pre className="text-xs text-gray-600 overflow-x-auto">
{`## Deal: Acme Corp
- **Outcome:** Lost
- **Competitor:** Competitor X

### Activities

#### Call - 2026-01-10
Customer mentioned they need
better Salesforce integration...`}
                    </pre>
                  </div>
                </div>
                <p className="mt-3 text-xs text-gray-500">
                  The system auto-detects file type. Structured data extracts themes from reasons/categories.
                  Activity data uses AI to analyze call notes, emails, and meeting logs for deeper insights.
                </p>
              </div>
            </div>
          )}

          {activeTab === "themes" && (
            <div className="p-6">
              {themesLoading ? (
                <div className="flex justify-center items-center h-32">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
              ) : winlossThemes.length === 0 && supportThemes.length === 0 && dealInsights.length === 0 && supportInsights.length === 0 ? (
                <div className="text-center py-12">
                  <svg
                    className="mx-auto h-12 w-12 text-gray-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                    />
                  </svg>
                  <h3 className="mt-4 text-sm font-medium text-gray-900">
                    No themes extracted yet
                  </h3>
                  <p className="mt-2 text-sm text-gray-500">
                    Import internal feedback data to extract win/loss and support themes.
                  </p>
                </div>
              ) : (
                <div className="space-y-8">
                  {/* Win/Loss Themes */}
                  {winlossThemes.length > 0 && (
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 mb-4">
                        Win/Loss Themes
                      </h3>
                      <div className="space-y-4">
                        {winlossThemes.map((theme, idx) => (
                          <div
                            key={idx}
                            className={`p-4 rounded-lg border ${
                              theme.outcome === "lost"
                                ? "bg-red-50 border-red-200"
                                : theme.outcome === "won"
                                ? "bg-green-50 border-green-200"
                                : "bg-gray-50 border-gray-200"
                            }`}
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <h4 className="font-medium text-gray-900">
                                  {theme.theme_name}
                                </h4>
                                <p className="text-sm text-gray-600 mt-1">
                                  {theme.deal_count} deals &middot;{" "}
                                  {formatCurrency(theme.total_value)} total value
                                  {theme.competitor_name && (
                                    <> &middot; vs {theme.competitor_name}</>
                                  )}
                                </p>
                              </div>
                              <span
                                className={`
                                  px-2 py-1 text-xs font-medium rounded-full
                                  ${
                                    theme.outcome === "lost"
                                      ? "bg-red-100 text-red-800"
                                      : theme.outcome === "won"
                                      ? "bg-green-100 text-green-800"
                                      : "bg-gray-100 text-gray-800"
                                  }
                                `}
                              >
                                {theme.outcome}
                              </span>
                            </div>
                            {theme.sample_reasons && theme.sample_reasons.length > 0 && (
                              <div className="mt-3 text-sm text-gray-600">
                                <p className="font-medium text-gray-700 mb-1">
                                  Sample reasons:
                                </p>
                                <ul className="list-disc list-inside space-y-1">
                                  {theme.sample_reasons.slice(0, 3).map((reason, rIdx) => (
                                    <li key={rIdx} className="truncate">
                                      {reason}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {theme.feature_keywords && theme.feature_keywords.length > 0 && (
                              <div className="mt-3 flex flex-wrap gap-1">
                                {theme.feature_keywords.map((keyword, kIdx) => (
                                  <span
                                    key={kIdx}
                                    className="px-2 py-0.5 text-xs bg-gray-200 text-gray-700 rounded"
                                  >
                                    {keyword}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Support Themes */}
                  {supportThemes.length > 0 && (
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 mb-4">
                        Support Themes
                      </h3>
                      <div className="space-y-4">
                        {supportThemes.map((theme, idx) => (
                          <div
                            key={idx}
                            className={`p-4 rounded-lg border ${
                              theme.urgency_indicator === "high"
                                ? "bg-orange-50 border-orange-200"
                                : "bg-blue-50 border-blue-200"
                            }`}
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <h4 className="font-medium text-gray-900">
                                  {theme.theme_name}
                                </h4>
                                <p className="text-sm text-gray-600 mt-1">
                                  {theme.ticket_count} tickets &middot; {theme.category}
                                </p>
                              </div>
                              <span
                                className={`
                                  px-2 py-1 text-xs font-medium rounded-full
                                  ${
                                    theme.urgency_indicator === "high"
                                      ? "bg-orange-100 text-orange-800"
                                      : theme.urgency_indicator === "medium"
                                      ? "bg-yellow-100 text-yellow-800"
                                      : "bg-gray-100 text-gray-800"
                                  }
                                `}
                              >
                                {theme.urgency_indicator} urgency
                              </span>
                            </div>
                            {theme.sample_subjects && theme.sample_subjects.length > 0 && (
                              <div className="mt-3 text-sm text-gray-600">
                                <p className="font-medium text-gray-700 mb-1">
                                  Sample tickets:
                                </p>
                                <ul className="list-disc list-inside space-y-1">
                                  {theme.sample_subjects.slice(0, 3).map((subject, sIdx) => (
                                    <li key={sIdx} className="truncate">
                                      {subject}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {theme.feature_keywords && theme.feature_keywords.length > 0 && (
                              <div className="mt-3 flex flex-wrap gap-1">
                                {theme.feature_keywords.map((keyword, kIdx) => (
                                  <span
                                    key={kIdx}
                                    className="px-2 py-0.5 text-xs bg-gray-200 text-gray-700 rounded"
                                  >
                                    {keyword}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Deal Activity Insights */}
                  {dealInsights.length > 0 && (
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 mb-4">
                        Deal Activity Insights
                        <span className="ml-2 text-sm font-normal text-purple-600">
                          (from CRM activities)
                        </span>
                      </h3>
                      <div className="space-y-4">
                        {dealInsights.map((insight, idx) => (
                          <div
                            key={idx}
                            className={`p-4 rounded-lg border ${
                              insight.deal_outcome === "lost"
                                ? "bg-red-50 border-red-200"
                                : insight.deal_outcome === "won"
                                ? "bg-green-50 border-green-200"
                                : "bg-purple-50 border-purple-200"
                            }`}
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <h4 className="font-medium text-gray-900">
                                  {insight.theme_name}
                                </h4>
                                <p className="text-sm text-gray-600 mt-1">
                                  {insight.deal_name && <>{insight.deal_name} &middot; </>}
                                  {insight.activity_count} activities
                                  {insight.deal_value && (
                                    <> &middot; {formatCurrency(insight.deal_value)}</>
                                  )}
                                  {insight.competitor_mentioned && (
                                    <> &middot; vs {insight.competitor_mentioned}</>
                                  )}
                                </p>
                              </div>
                              <div className="flex gap-2">
                                <span
                                  className={`
                                    px-2 py-1 text-xs font-medium rounded-full
                                    ${
                                      insight.sentiment === "negative"
                                        ? "bg-red-100 text-red-800"
                                        : insight.sentiment === "positive"
                                        ? "bg-green-100 text-green-800"
                                        : "bg-gray-100 text-gray-800"
                                    }
                                  `}
                                >
                                  {insight.sentiment}
                                </span>
                                <span
                                  className={`
                                    px-2 py-1 text-xs font-medium rounded-full
                                    ${
                                      insight.deal_outcome === "lost"
                                        ? "bg-red-100 text-red-800"
                                        : insight.deal_outcome === "won"
                                        ? "bg-green-100 text-green-800"
                                        : "bg-gray-100 text-gray-800"
                                    }
                                  `}
                                >
                                  {insight.deal_outcome}
                                </span>
                              </div>
                            </div>
                            {insight.sample_quotes && insight.sample_quotes.length > 0 && (
                              <div className="mt-3 text-sm text-gray-600">
                                <p className="font-medium text-gray-700 mb-1">
                                  Sample quotes:
                                </p>
                                <ul className="list-disc list-inside space-y-1">
                                  {insight.sample_quotes.slice(0, 3).map((quote, qIdx) => (
                                    <li key={qIdx} className="truncate italic">
                                      "{quote}"
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {insight.feature_keywords && insight.feature_keywords.length > 0 && (
                              <div className="mt-3 flex flex-wrap gap-1">
                                {insight.feature_keywords.map((keyword, kIdx) => (
                                  <span
                                    key={kIdx}
                                    className="px-2 py-0.5 text-xs bg-purple-200 text-purple-700 rounded"
                                  >
                                    {keyword}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Support Activity Insights */}
                  {supportInsights.length > 0 && (
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 mb-4">
                        Support Activity Insights
                        <span className="ml-2 text-sm font-normal text-purple-600">
                          (from CRM activities)
                        </span>
                      </h3>
                      <div className="space-y-4">
                        {supportInsights.map((insight, idx) => (
                          <div
                            key={idx}
                            className={`p-4 rounded-lg border ${
                              insight.urgency_level === "high"
                                ? "bg-orange-50 border-orange-200"
                                : "bg-purple-50 border-purple-200"
                            }`}
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <h4 className="font-medium text-gray-900">
                                  {insight.theme_name}
                                </h4>
                                <p className="text-sm text-gray-600 mt-1">
                                  {insight.ticket_count} tickets &middot; {insight.category}
                                  {insight.accounts_affected && insight.accounts_affected.length > 0 && (
                                    <> &middot; {insight.accounts_affected.length} accounts affected</>
                                  )}
                                </p>
                              </div>
                              <span
                                className={`
                                  px-2 py-1 text-xs font-medium rounded-full
                                  ${
                                    insight.urgency_level === "high"
                                      ? "bg-orange-100 text-orange-800"
                                      : insight.urgency_level === "medium"
                                      ? "bg-yellow-100 text-yellow-800"
                                      : "bg-gray-100 text-gray-800"
                                  }
                                `}
                              >
                                {insight.urgency_level} urgency
                              </span>
                            </div>
                            {insight.sample_quotes && insight.sample_quotes.length > 0 && (
                              <div className="mt-3 text-sm text-gray-600">
                                <p className="font-medium text-gray-700 mb-1">
                                  Sample quotes:
                                </p>
                                <ul className="list-disc list-inside space-y-1">
                                  {insight.sample_quotes.slice(0, 3).map((quote, qIdx) => (
                                    <li key={qIdx} className="truncate italic">
                                      "{quote}"
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {insight.feature_keywords && insight.feature_keywords.length > 0 && (
                              <div className="mt-3 flex flex-wrap gap-1">
                                {insight.feature_keywords.map((keyword, kIdx) => (
                                  <span
                                    key={kIdx}
                                    className="px-2 py-0.5 text-xs bg-purple-200 text-purple-700 rounded"
                                  >
                                    {keyword}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
