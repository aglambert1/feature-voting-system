/**
 * SynthesisHubPage
 *
 * Unified synthesis hub: configure sources + competitor inclusion, trigger a
 * run, and view the latest report (analysis summary + markdown body).
 *
 * The legacy landscape/opportunity tab + flat opportunity list were removed in
 * PR #33's JTBD redesign; this page now reflects the unified SynthesisReport
 * shape.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { format } from "date-fns";
import Navigation from "../../components/Navigation";
import SynthesisConfigPanel from "./components/SynthesisConfigPanel";
import SynthesisCompetitorList from "./components/SynthesisCompetitorList";
import {
  getJob,
  getLatestUnifiedReport,
  triggerUnifiedSynthesis,
} from "../../services/api";
import api from "../../services/api";
import type { LatestUnifiedReportResponse } from "../../types";
import { JobStatus } from "../../types";

interface ProductInfo {
  id: number;
  product_name: string;
}

export default function SynthesisHubPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const numProductId = productId ? parseInt(productId, 10) : NaN;

  const [product, setProduct] = useState<ProductInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [report, setReport] = useState<LatestUnifiedReportResponse | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  const [runningJobUuid, setRunningJobUuid] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const [configExpanded, setConfigExpanded] = useState(true);

  const pollTimer = useRef<number | null>(null);

  const fetchProduct = useCallback(async () => {
    if (!Number.isFinite(numProductId)) return;
    try {
      setLoading(true);
      const resp = await api.get<ProductInfo>(
        `/product-intelligence/products/${numProductId}`
      );
      setProduct(resp.data);
      setError(null);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load product.");
    } finally {
      setLoading(false);
    }
  }, [numProductId]);

  const fetchReport = useCallback(async () => {
    if (!Number.isFinite(numProductId)) return;
    try {
      const r = await getLatestUnifiedReport(numProductId);
      setReport(r);
      setReportError(null);
    } catch (err: any) {
      setReportError(err?.message ?? "Failed to load synthesis report.");
    }
  }, [numProductId]);

  useEffect(() => {
    fetchProduct();
    fetchReport();
  }, [fetchProduct, fetchReport]);

  // Poll the running job; on terminal state, refresh the report.
  useEffect(() => {
    if (!runningJobUuid) return;

    const poll = async () => {
      try {
        const job = await getJob(runningJobUuid);
        if (
          job.status === JobStatus.SUCCESS ||
          job.status === JobStatus.FAILURE ||
          job.status === JobStatus.CANCELLED
        ) {
          setRunningJobUuid(null);
          if (job.status === JobStatus.FAILURE) {
            setRunError(job.error_message ?? "Synthesis failed.");
          } else if (job.status === JobStatus.SUCCESS) {
            await fetchReport();
          }
        }
      } catch (err) {
        console.error("Synthesis poll failed:", err);
      }
    };

    pollTimer.current = window.setInterval(poll, 3000);
    return () => {
      if (pollTimer.current) {
        clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    };
  }, [runningJobUuid, fetchReport]);

  const handleRun = async () => {
    if (!Number.isFinite(numProductId)) return;
    setRunError(null);
    try {
      const resp = await triggerUnifiedSynthesis(numProductId);
      setRunningJobUuid(resp.job_uuid);
    } catch (err: any) {
      setRunError(err?.message ?? "Failed to start synthesis.");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="animate-pulse h-8 bg-gray-200 rounded w-1/4" />
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

  const isRunning = runningJobUuid !== null;
  const hasReport = report?.exists === true;

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
                Configure sources, pick competitors, and run a unified synthesis report.
              </p>
            </div>
            <button
              onClick={handleRun}
              disabled={isRunning}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isRunning ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Running…
                </>
              ) : hasReport ? "Re-run Synthesis" : "Run Synthesis"}
            </button>
          </div>
        </div>

        {runError && (
          <div className="mb-4 p-3 rounded border border-red-200 bg-red-50 text-sm text-red-800">
            {runError}
          </div>
        )}

        {/* Configuration section (collapsible, open by default) */}
        <div className="mb-6">
          <button
            type="button"
            onClick={() => setConfigExpanded((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-3 bg-white rounded-lg shadow text-left hover:bg-gray-50"
            aria-expanded={configExpanded}
          >
            <div>
              <h2 className="text-base font-semibold text-gray-900">Configuration</h2>
              <p className="text-xs text-gray-500">
                Source types, idea threshold, and competitor inclusion.
              </p>
            </div>
            <svg
              className={`w-5 h-5 text-gray-400 transition-transform ${configExpanded ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {configExpanded && Number.isFinite(numProductId) && (
            <div className="mt-3">
              <SynthesisConfigPanel productId={numProductId} />
              <SynthesisCompetitorList productId={numProductId} />
            </div>
          )}
        </div>

        {/* Results */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-100 flex items-baseline justify-between">
            <h2 className="text-base font-semibold text-gray-900">Latest synthesis report</h2>
            {hasReport && report.generated_at && (
              <span className="text-xs text-gray-500">
                v{report.report_version} · {format(new Date(report.generated_at), "MMM d, yyyy h:mm a")}
              </span>
            )}
          </div>

          <div className="px-6 py-5">
            {isRunning && (
              <div className="flex items-center gap-3 text-sm text-blue-800 bg-blue-50 border border-blue-200 rounded px-3 py-2 mb-4">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>Synthesizing… the report will refresh when the job completes.</span>
              </div>
            )}

            {reportError && (
              <div className="p-3 rounded border border-red-200 bg-red-50 text-sm text-red-800">
                {reportError}
              </div>
            )}

            {!reportError && !hasReport && !isRunning && (
              <div className="text-sm text-gray-500">
                {report && !report.exists
                  ? report.message
                  : "No synthesis report yet. Configure sources above, then click Run Synthesis."}
              </div>
            )}

            {hasReport && (
              <>
                {report.analysis_summary && (
                  <div className="mb-5">
                    <h3 className="text-sm font-medium text-gray-700 mb-1">Analysis summary</h3>
                    <p className="text-sm text-gray-800 whitespace-pre-wrap">
                      {report.analysis_summary}
                    </p>
                  </div>
                )}

                {report.included_source_types && report.included_source_types.length > 0 && (
                  <div className="mb-5">
                    <h3 className="text-sm font-medium text-gray-700 mb-1">Included sources</h3>
                    <div className="flex flex-wrap gap-1">
                      {report.included_source_types.map((s) => (
                        <span
                          key={s}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-indigo-100 text-indigo-800"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {report.report_content_md ? (
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-1">Report</h3>
                    <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-gray-800 bg-gray-50 border border-gray-200 rounded p-3 max-h-[600px] overflow-auto">
                      {report.report_content_md}
                    </pre>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">
                    Report content is not available (the job may have returned no narrative).
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
