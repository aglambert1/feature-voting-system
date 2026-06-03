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
import {
  createIdeaFromOpportunity,
  getJob,
  getLatestUnifiedReport,
  triggerUnifiedSynthesis,
} from "../../services/api";
import api from "../../services/api";
import type { LatestUnifiedReportResponse, SynthesisOpportunityDetail } from "../../types";
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
  // Persist panel expansion across navigation (e.g., clicking into an idea
  // then hitting back) so the user's collapse choice survives. Matches the
  // sessionStorage pattern established in ProductContext.
  const [configExpanded, setConfigExpanded] = useState<boolean>(() => {
    const stored = sessionStorage.getItem("synthesisHub:configExpanded");
    return stored === null ? true : stored === "true";
  });
  useEffect(() => {
    sessionStorage.setItem("synthesisHub:configExpanded", String(configExpanded));
  }, [configExpanded]);

  const [modalOpp, setModalOpp] = useState<SynthesisOpportunityDetail | null>(null);
  const [createNotice, setCreateNotice] = useState<{ ideaId: number } | null>(null);

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

  const handleDownloadMd = () => {
    if (!report || report.exists !== true || !report.report_content_md) return;
    const blob = new Blob([report.report_content_md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeName = (product?.product_name ?? `product_${numProductId}`).replace(/\s+/g, "_");
    a.download = `${safeName}_synthesis_v${report.report_version}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

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

  const handleIdeaCreated = async (ideaId: number) => {
    setModalOpp(null);
    setCreateNotice({ ideaId });
    await fetchReport();
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
                Source types and idea threshold.
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
            </div>
          )}
        </div>

        {/* Results */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-100 flex items-baseline justify-between gap-4">
            <h2 className="text-base font-semibold text-gray-900">Latest synthesis report</h2>
            <div className="flex items-center gap-3">
              {hasReport && report.generated_at && (
                <span className="text-xs text-gray-500">
                  v{report.report_version} · {format(new Date(report.generated_at), "MMM d, yyyy h:mm a")}
                </span>
              )}
            </div>
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

                {createNotice && (
                  <div className="mb-4 p-3 rounded border border-green-200 bg-green-50 text-sm text-green-800 flex items-center justify-between">
                    <span>Idea #{createNotice.ideaId} created; triage queued.</span>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => navigate(`/ideas/${createNotice.ideaId}`)}
                        className="text-green-700 hover:text-green-900 font-medium underline"
                      >
                        View idea
                      </button>
                      <button
                        onClick={() => setCreateNotice(null)}
                        className="text-green-600 hover:text-green-800"
                        aria-label="Dismiss"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                )}

                {report.opportunities_detail && report.opportunities_detail.length > 0 && (
                  <div className="mb-5">
                    <h3 className="text-sm font-medium text-gray-700 mb-2">
                      Opportunities ({report.opportunities_detail.length})
                    </h3>
                    <OpportunitiesTable
                      opportunities={report.opportunities_detail}
                      onCreateClick={(o) => setModalOpp(o)}
                      onViewIdea={(ideaId) => navigate(`/ideas/${ideaId}`)}
                    />
                  </div>
                )}

                {report.report_content_md ? (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <h3 className="text-sm font-medium text-gray-700">Report (markdown)</h3>
                      <button
                        onClick={handleDownloadMd}
                        className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                      >
                        Download .md
                      </button>
                    </div>
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

      {modalOpp && (
        <CreateIdeaModal
          opportunity={modalOpp}
          productId={numProductId}
          onClose={() => setModalOpp(null)}
          onCreated={handleIdeaCreated}
        />
      )}
    </div>
  );
}

function OpportunitiesTable({
  opportunities,
  onCreateClick,
  onViewIdea,
}: {
  opportunities: SynthesisOpportunityDetail[];
  onCreateClick: (o: SynthesisOpportunityDetail) => void;
  onViewIdea: (ideaId: number) => void;
}) {
  return (
    <div className="overflow-x-auto border border-gray-200 rounded">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th className="text-left px-3 py-2 font-medium">Opportunity</th>
            <th className="text-left px-3 py-2 font-medium">Score</th>
            <th className="text-left px-3 py-2 font-medium">Tier</th>
            <th className="text-left px-3 py-2 font-medium">Sources</th>
            <th className="text-left px-3 py-2 font-medium">Job</th>
            <th className="text-left px-3 py-2 font-medium">Idea</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {opportunities.map((o) => (
            <tr key={o.id} className="align-top">
              <td className="px-3 py-2">
                <div className="font-medium text-gray-900">{o.opportunity_name}</div>
                {o.opportunity_summary && (
                  <div className="text-xs text-gray-600 mt-0.5">{o.opportunity_summary}</div>
                )}
              </td>
              <td className="px-3 py-2 text-gray-800 whitespace-nowrap">
                {o.priority_score.toFixed(0)}
              </td>
              <td className="px-3 py-2 whitespace-nowrap">
                {o.investment_tier ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700">
                    {o.investment_tier.replace(/_/g, " ")}
                  </span>
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-1">
                  {o.sources.length > 0 ? o.sources.map((s) => (
                    <span key={s} className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-indigo-50 text-indigo-700">
                      {s}
                    </span>
                  )) : <span className="text-gray-400 text-xs">—</span>}
                </div>
              </td>
              <td className="px-3 py-2 text-xs text-gray-600 whitespace-nowrap">
                {o.job_id_key ?? <span className="text-gray-400">—</span>}
              </td>
              <td className="px-3 py-2 whitespace-nowrap">
                {o.linked_idea_id ? (
                  <button
                    type="button"
                    onClick={() => onViewIdea(o.linked_idea_id!)}
                    className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-green-100 text-green-800 hover:bg-green-200"
                    title={o.linked_idea_title ?? undefined}
                  >
                    View Idea #{o.linked_idea_id}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => onCreateClick(o)}
                    className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200"
                  >
                    + Create idea
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CreateIdeaModal({
  opportunity,
  productId,
  onClose,
  onCreated,
}: {
  opportunity: SynthesisOpportunityDetail;
  productId: number;
  onClose: () => void;
  onCreated: (ideaId: number) => void;
}) {
  const defaultUseCase = opportunity.sources.length
    ? ["Synthesized from multiple sources:", ...opportunity.sources.map((s) => `- ${s}`)].join("\n")
    : "";

  const [title, setTitle] = useState(opportunity.opportunity_name);
  const [whatDesc, setWhatDesc] = useState(opportunity.opportunity_summary ?? opportunity.opportunity_name);
  const [whyDesc, setWhyDesc] = useState(opportunity.recommended_action ?? "");
  const [useCase, setUseCase] = useState(defaultUseCase);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !whatDesc.trim()) {
      setError("Title and 'What' are required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const resp = await createIdeaFromOpportunity(productId, opportunity.id, {
        title: title.trim(),
        what_description: whatDesc.trim(),
        why_description: whyDesc.trim(),
        use_case_description: useCase.trim(),
      });
      onCreated(resp.idea_id);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? err?.message ?? "Failed to create idea.");
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Create idea from opportunity</h3>
            <p className="text-xs text-gray-500 mt-1">
              Edit the pre-filled fields as needed. Triage will run automatically.
            </p>
          </div>

          <div className="px-6 py-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={255}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">What</label>
              <textarea
                value={whatDesc}
                onChange={(e) => setWhatDesc(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Why</label>
              <textarea
                value={whyDesc}
                onChange={(e) => setWhyDesc(e.target.value)}
                rows={2}
                maxLength={1000}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Use case</label>
              <textarea
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {error && (
              <div className="p-3 rounded border border-red-200 bg-red-50 text-sm text-red-800">
                {error}
              </div>
            )}
          </div>

          <div className="px-6 py-3 border-t border-gray-200 bg-gray-50 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? "Creating…" : "Create idea"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
