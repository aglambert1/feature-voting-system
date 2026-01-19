/**
 * InternalFeedbackPage
 *
 * Page for importing and viewing internal feedback data (sales win/loss, support tickets).
 * This is a source for the Opportunity Synthesis Agent.
 *
 * Features:
 * - File upload for JSON import
 * - Import history table
 * - Win/loss themes display
 * - Support themes display
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Navigation from "../../components/Navigation";
import {
  uploadInternalFeedback,
  getInternalFeedbackImports,
  getInternalFeedbackThemes,
  getInternalFeedbackImportStatus,
  deleteInternalFeedbackImport,
  reprocessInternalFeedback,
} from "../../services/api";
import type {
  InternalFeedbackImport,
  WinLossTheme,
  SupportTheme,
} from "../../types";
import api from "../../services/api";

// Tab types
type TabId = "import" | "themes";

interface Tab {
  id: TabId;
  label: string;
}

const tabs: Tab[] = [
  { id: "import", label: "Import Data" },
  { id: "themes", label: "Extracted Themes" },
];

interface ProductInfo {
  id: number;
  product_name: string;
}

export default function InternalFeedbackPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();

  // Product info
  const [product, setProduct] = useState<ProductInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Tab state
  const [activeTab, setActiveTab] = useState<TabId>("import");

  // Import state
  const [imports, setImports] = useState<InternalFeedbackImport[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  // Themes state
  const [winlossThemes, setWinlossThemes] = useState<WinLossTheme[]>([]);
  const [supportThemes, setSupportThemes] = useState<SupportTheme[]>([]);
  const [themesLoading, setThemesLoading] = useState(false);

  // Polling for processing status
  const [pollingImportId, setPollingImportId] = useState<number | null>(null);

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

  // Fetch imports
  const fetchImports = useCallback(async () => {
    if (!productId) return;

    try {
      const data = await getInternalFeedbackImports(parseInt(productId, 10));
      setImports(data);

      // Check if any import is processing
      const processingImport = data.find((i) => i.status === "processing");
      if (processingImport) {
        setPollingImportId(processingImport.id);
      }
    } catch (err: any) {
      console.error("Failed to fetch imports:", err);
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

  // Initial fetch
  useEffect(() => {
    fetchProduct();
  }, [fetchProduct]);

  useEffect(() => {
    if (product) {
      fetchImports();
      fetchThemes();
    }
  }, [product, fetchImports, fetchThemes]);

  // Poll for processing status
  useEffect(() => {
    if (!pollingImportId || !productId) return;

    const interval = setInterval(async () => {
      try {
        const status = await getInternalFeedbackImportStatus(
          parseInt(productId, 10),
          pollingImportId
        );

        if (status.status === "completed" || status.status === "failed") {
          setPollingImportId(null);
          fetchImports();
          fetchThemes();
        }
      } catch (err) {
        console.error("Error polling status:", err);
        setPollingImportId(null);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [pollingImportId, productId, fetchImports, fetchThemes]);

  // Handle file upload
  const handleFileUpload = async (file: File) => {
    if (!productId) return;

    if (!file.name.endsWith(".json")) {
      setUploadError("Please upload a JSON file");
      return;
    }

    try {
      setUploading(true);
      setUploadError(null);
      const result = await uploadInternalFeedback(parseInt(productId, 10), file);
      setImports((prev) => [result, ...prev]);

      if (result.status === "processing") {
        setPollingImportId(result.id);
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

  // Handle file input change
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  };

  // Handle delete import
  const handleDeleteImport = async (importId: number) => {
    if (!productId) return;

    if (!confirm("Delete this import and all its extracted themes?")) return;

    try {
      await deleteInternalFeedbackImport(parseInt(productId, 10), importId);
      setImports((prev) => prev.filter((i) => i.id !== importId));
      fetchThemes();
    } catch (err: any) {
      alert(err.message || "Failed to delete import");
    }
  };

  // Handle reprocess
  const handleReprocess = async (importId: number) => {
    if (!productId) return;

    try {
      const result = await reprocessInternalFeedback(parseInt(productId, 10), importId);
      setImports((prev) =>
        prev.map((i) => (i.id === importId ? result : i))
      );

      if (result.status === "processing") {
        setPollingImportId(result.id);
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
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
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
                    py-4 px-1 border-b-2 font-medium text-sm
                    ${
                      isActive
                        ? "border-blue-500 text-blue-600"
                        : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                    }
                  `}
                >
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-lg shadow">
          {activeTab === "import" && (
            <div className="p-6">
              {/* Upload Area */}
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
                  accept=".json"
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
                      Drag and drop your JSON file here, or{" "}
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
                  Supports sales win/loss data and support ticket exports
                </p>

                {uploadError && (
                  <p className="mt-4 text-sm text-red-600">{uploadError}</p>
                )}
              </div>

              {/* Sample Data Info */}
              <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  Expected JSON Format
                </h3>
                <pre className="text-xs text-gray-600 overflow-x-auto">
{`{
  "deals": [
    {
      "outcome": "lost",
      "competitor_name": "Competitor A",
      "reason": "Missing time tracking",
      "deal_value": 50000,
      "notes": "..."
    }
  ],
  "support_tickets": [
    {
      "category": "feature_request",
      "subject": "Need PDF export",
      "ticket_count": 47
    }
  ]
}`}
                </pre>
              </div>

              {/* Import History */}
              {imports.length > 0 && (
                <div className="mt-8">
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
                        {imports.map((imp) => (
                          <tr key={imp.id}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {imp.filename}
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
                              {imp.deals_count} deals, {imp.tickets_count} tickets
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {formatDate(imp.imported_at)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                              {imp.status === "completed" && (
                                <button
                                  onClick={() => handleReprocess(imp.id)}
                                  className="text-blue-600 hover:text-blue-900 mr-4"
                                >
                                  Reprocess
                                </button>
                              )}
                              <button
                                onClick={() => handleDeleteImport(imp.id)}
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
            </div>
          )}

          {activeTab === "themes" && (
            <div className="p-6">
              {themesLoading ? (
                <div className="flex justify-center items-center h-32">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
              ) : winlossThemes.length === 0 && supportThemes.length === 0 ? (
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
                      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                    />
                  </svg>
                  <h3 className="mt-2 text-sm font-medium text-gray-900">
                    No themes extracted yet
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Import internal feedback data to extract themes.
                  </p>
                  <button
                    onClick={() => setActiveTab("import")}
                    className="mt-4 text-blue-600 hover:text-blue-800 font-medium"
                  >
                    Go to Import
                  </button>
                </div>
              ) : (
                <div className="space-y-8">
                  {/* Win/Loss Themes */}
                  {winlossThemes.length > 0 && (
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 mb-4">
                        Win/Loss Themes ({winlossThemes.length})
                      </h3>
                      <div className="grid gap-4">
                        {winlossThemes.map((theme) => (
                          <div
                            key={theme.id}
                            className={`
                              p-4 rounded-lg border
                              ${
                                theme.outcome === "lost"
                                  ? "border-red-200 bg-red-50"
                                  : "border-green-200 bg-green-50"
                              }
                            `}
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <h4 className="font-medium text-gray-900">
                                  {theme.theme_name}
                                </h4>
                                <div className="mt-1 flex items-center gap-3 text-sm text-gray-600">
                                  <span
                                    className={`
                                      inline-flex px-2 py-0.5 rounded text-xs font-medium
                                      ${
                                        theme.outcome === "lost"
                                          ? "bg-red-100 text-red-800"
                                          : "bg-green-100 text-green-800"
                                      }
                                    `}
                                  >
                                    {theme.outcome === "lost" ? "Lost" : "Won"}
                                  </span>
                                  <span>{theme.deal_count} deals</span>
                                  {theme.total_value && (
                                    <span>
                                      {formatCurrency(theme.total_value)}
                                    </span>
                                  )}
                                  {theme.competitor_name && (
                                    <span className="text-gray-500">
                                      vs {theme.competitor_name}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>

                            {theme.sample_reasons.length > 0 && (
                              <div className="mt-3">
                                <p className="text-xs font-medium text-gray-500 mb-1">
                                  Sample Reasons:
                                </p>
                                <ul className="text-sm text-gray-600 list-disc list-inside">
                                  {theme.sample_reasons.slice(0, 3).map((r, i) => (
                                    <li key={i}>{r}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {theme.feature_keywords.length > 0 && (
                              <div className="mt-3 flex flex-wrap gap-1">
                                {theme.feature_keywords.map((kw, i) => (
                                  <span
                                    key={i}
                                    className="inline-flex px-2 py-0.5 bg-white rounded text-xs text-gray-600 border"
                                  >
                                    {kw}
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
                        Support Themes ({supportThemes.length})
                      </h3>
                      <div className="grid gap-4">
                        {supportThemes.map((theme) => (
                          <div
                            key={theme.id}
                            className="p-4 rounded-lg border border-blue-200 bg-blue-50"
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <h4 className="font-medium text-gray-900">
                                  {theme.theme_name}
                                </h4>
                                <div className="mt-1 flex items-center gap-3 text-sm text-gray-600">
                                  <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                                    {theme.category}
                                  </span>
                                  <span>{theme.ticket_count} tickets</span>
                                  {theme.urgency_indicator && (
                                    <span
                                      className={`
                                        inline-flex px-2 py-0.5 rounded text-xs font-medium
                                        ${
                                          theme.urgency_indicator === "high"
                                            ? "bg-red-100 text-red-800"
                                            : theme.urgency_indicator === "medium"
                                            ? "bg-yellow-100 text-yellow-800"
                                            : "bg-gray-100 text-gray-800"
                                        }
                                      `}
                                    >
                                      {theme.urgency_indicator} urgency
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>

                            {theme.sample_subjects.length > 0 && (
                              <div className="mt-3">
                                <p className="text-xs font-medium text-gray-500 mb-1">
                                  Sample Subjects:
                                </p>
                                <ul className="text-sm text-gray-600 list-disc list-inside">
                                  {theme.sample_subjects.slice(0, 3).map((s, i) => (
                                    <li key={i}>{s}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {theme.feature_keywords.length > 0 && (
                              <div className="mt-3 flex flex-wrap gap-1">
                                {theme.feature_keywords.map((kw, i) => (
                                  <span
                                    key={i}
                                    className="inline-flex px-2 py-0.5 bg-white rounded text-xs text-gray-600 border"
                                  >
                                    {kw}
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
