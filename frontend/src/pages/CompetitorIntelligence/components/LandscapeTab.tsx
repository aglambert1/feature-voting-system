/**
 * LandscapeTab
 *
 * V2 Competitive Analysis: Displays cross-competitor landscape synthesis.
 * Shows feature opportunities with priority scores and allows idea creation.
 */

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  getLandscapeReport,
  triggerLandscapeSynthesis,
  triggerFunctionalAudit,
  exportLandscapeReportMd,
  getOpportunityIdeaStatuses,
  createIdeasFromOpportunities,
  exportOpportunitiesJson,
  getFunctionalReports,
  getAgentCompetitors,
  getProductJobs,
} from "../../../services/api";
import type {
  LandscapeReportDetail,
  BatchIdeaStatusesResponse,
  FeatureOpportunity,
  AgentCompetitor,
  FunctionalReportSummary,
  QueueJob,
} from "../../../types";
import { JobType, JobStatus } from "../../../types";
import FeatureOpportunityCard from "./FeatureOpportunityCard";

interface Props {
  productId: number;
  refreshKey?: number;
}

// Combine opportunities with high-impact gaps for sorting
interface CombinedOpportunity {
  index: number;
  opportunity: FeatureOpportunity;
  highImpactRank?: number; // If from high-impact gaps
}

export default function LandscapeTab({ productId, refreshKey }: Props) {
  const [report, setReport] = useState<LandscapeReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ideaStatuses, setIdeaStatuses] =
    useState<BatchIdeaStatusesResponse | null>(null);
  const [functionalReportCount, setFunctionalReportCount] = useState<number>(0);
  const [totalFunctionalReports, setTotalFunctionalReports] =
    useState<number>(0);

  // Competitors data for warning modal
  const [competitors, setCompetitors] = useState<AgentCompetitor[]>([]);
  const [functionalReports, setFunctionalReports] = useState<
    FunctionalReportSummary[]
  >([]);

  // Selection state
  const [selectedOpportunities, setSelectedOpportunities] = useState<
    Set<number>
  >(new Set());

  // Action states
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Warning modal state
  const [showWarningModal, setShowWarningModal] = useState(false);
  const [competitorsWithoutReports, setCompetitorsWithoutReports] = useState<
    AgentCompetitor[]
  >([]);
  const [competitorsToAudit, setCompetitorsToAudit] = useState<Set<number>>(
    new Set()
  );

  // Job polling state
  const [activeJobs, setActiveJobs] = useState<QueueJob[]>([]);
  const pendingSynthesisAfterAudits = useRef(false);

  // Collapsible sections
  const [showMatrix, setShowMatrix] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [reportData, reportsData, competitorsData] = await Promise.all([
        getLandscapeReport(productId),
        getFunctionalReports(productId),
        getAgentCompetitors(productId),
      ]);
      setReport(reportData);
      setFunctionalReportCount(reportData?.competitor_count || 0);
      setTotalFunctionalReports(reportsData.length);
      setFunctionalReports(reportsData);
      setCompetitors(competitorsData);

      if (reportData) {
        const statuses = await getOpportunityIdeaStatuses(productId);
        setIdeaStatuses(statuses);
      }
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load landscape report");
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshKey]);

  // Build competitor name -> URL map for source traceability links
  const competitorUrls = useMemo(() => {
    const map: Record<string, string> = {};
    for (const c of competitors) {
      if (c.competitor_url) {
        map[c.competitor_name] = c.competitor_url;
      }
    }
    return map;
  }, [competitors]);

  // Check for active jobs on initial load
  const checkForActiveJobs = useCallback(async () => {
    try {
      const jobs = await getProductJobs(productId, 10, [
        JobType.FUNCTIONAL_AUDIT,
        JobType.LANDSCAPE_SYNTHESIS,
        JobType.SCHEDULED_DEEP_ANALYSIS,
      ]);
      const active = jobs.filter(
        (j) =>
          j.status === JobStatus.PENDING ||
          j.status === JobStatus.QUEUED ||
          j.status === JobStatus.RUNNING
      );
      setActiveJobs(active);
    } catch (err) {
      console.error("[LandscapeTab] Failed to check active jobs:", err);
    }
  }, [productId]);

  useEffect(() => {
    checkForActiveJobs();
  }, [checkForActiveJobs]);

  // Poll for job completion while jobs are active
  useEffect(() => {
    if (activeJobs.length === 0) return;

    const interval = setInterval(async () => {
      try {
        const jobs = await getProductJobs(productId, 10, [
          JobType.FUNCTIONAL_AUDIT,
          JobType.LANDSCAPE_SYNTHESIS,
          JobType.SCHEDULED_DEEP_ANALYSIS,
        ]);
        const active = jobs.filter(
          (j) =>
            j.status === JobStatus.PENDING ||
            j.status === JobStatus.QUEUED ||
            j.status === JobStatus.RUNNING
        );

        const hadAudits = activeJobs.some(
          (j) => j.job_type === JobType.FUNCTIONAL_AUDIT
        );
        const auditsNowDone =
          hadAudits &&
          !active.some((j) => j.job_type === JobType.FUNCTIONAL_AUDIT);

        setActiveJobs(active);

        // Auto-trigger synthesis when audits complete
        if (auditsNowDone && pendingSynthesisAfterAudits.current) {
          pendingSynthesisAfterAudits.current = false;
          try {
            await triggerLandscapeSynthesis(productId);
            setSuccessMessage("Audits complete — landscape synthesis started automatically");
            // Re-check to pick up the new synthesis job
            await checkForActiveJobs();
          } catch (err: any) {
            setError(err.message || "Failed to auto-start synthesis");
          }
          return;
        }

        if (active.length === 0) {
          // All jobs done — refresh data
          setSuccessMessage("Analysis complete");
          fetchData();
        }
      } catch (err) {
        console.error("[LandscapeTab] Failed to poll jobs:", err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [activeJobs, productId, fetchData, checkForActiveJobs]);

  // Clear success message after timeout
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Functional reports for selected (deep_analysis_enabled) competitors only
  const selectedFunctionalReports = useMemo(() => {
    const selectedCompetitorIds = new Set(
      competitors.filter((c) => c.deep_analysis_enabled).map((c) => c.id)
    );
    return functionalReports.filter((r) =>
      selectedCompetitorIds.has(r.product_competitor_id)
    );
  }, [competitors, functionalReports]);

  // Check if any selected competitors are missing reports
  const getCompetitorsWithoutReports = (): AgentCompetitor[] => {
    const reportCompetitorIds = new Set(
      functionalReports.map((r) => r.product_competitor_id)
    );
    return competitors.filter(
      (c) => c.deep_analysis_enabled && !reportCompetitorIds.has(c.id)
    );
  };

  const handleRunSynthesisClick = () => {
    const missing = getCompetitorsWithoutReports();
    if (missing.length > 0) {
      setCompetitorsWithoutReports(missing);
      // Default: select all for audit
      setCompetitorsToAudit(new Set(missing.map((c) => c.id)));
      setShowWarningModal(true);
    } else {
      handleRunSynthesisOnly();
    }
  };

  const toggleCompetitorAudit = (competitorId: number) => {
    setCompetitorsToAudit((prev) => {
      const next = new Set(prev);
      if (next.has(competitorId)) {
        next.delete(competitorId);
      } else {
        next.add(competitorId);
      }
      return next;
    });
  };

  const handleSelectAllForAudit = () => {
    if (competitorsToAudit.size === competitorsWithoutReports.length) {
      setCompetitorsToAudit(new Set());
    } else {
      setCompetitorsToAudit(
        new Set(competitorsWithoutReports.map((c) => c.id))
      );
    }
  };

  const handleRunSynthesisOnly = async () => {
    setShowWarningModal(false);
    try {
      setActionLoading("synthesis");
      await triggerLandscapeSynthesis(productId);
      setSuccessMessage("Landscape synthesis started");
      checkForActiveJobs();
    } catch (err: any) {
      setError(err.message || "Failed to start synthesis");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRunAuditsThenSynthesize = async () => {
    setShowWarningModal(false);
    try {
      setActionLoading("audits-then-synthesis");

      if (competitorsToAudit.size > 0) {
        // Run audits for selected competitors only (not V2 which audits ALL)
        const auditPromises = Array.from(competitorsToAudit).map(
          (competitorId) => triggerFunctionalAudit(productId, competitorId)
        );
        await Promise.all(auditPromises);
        pendingSynthesisAfterAudits.current = true;
        setSuccessMessage(
          `Auditing ${competitorsToAudit.size} competitor(s). Synthesis will run automatically when audits complete.`
        );
        // Start polling for job progress
        checkForActiveJobs();
      } else {
        // None selected for audit - just run synthesis
        await triggerLandscapeSynthesis(productId);
        setSuccessMessage(
          "Landscape synthesis started (skipping competitors without reports)"
        );
        checkForActiveJobs();
      }
    } catch (err: any) {
      setError(err.message || "Failed to start analysis");
    } finally {
      setActionLoading(null);
    }
  };

  const handleExportMd = async () => {
    if (!report) return;

    try {
      setActionLoading("export-md");
      const markdown = await exportLandscapeReportMd(productId);

      const blob = new Blob([markdown], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `landscape_synthesis_${
        new Date().toISOString().split("T")[0]
      }.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || "Failed to export report");
    } finally {
      setActionLoading(null);
    }
  };

  const handleOpportunitySelection = (index: number) => {
    setSelectedOpportunities((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const handleSelectAllOpportunities = () => {
    if (!report) return;
    const allIndices = report.feature_opportunities.map((_, i) => i);
    if (selectedOpportunities.size === allIndices.length) {
      setSelectedOpportunities(new Set());
    } else {
      setSelectedOpportunities(new Set(allIndices));
    }
  };

  const handleCreateIdeas = async () => {
    if (!report || selectedOpportunities.size === 0) return;

    try {
      setActionLoading("create-ideas");
      const indices = Array.from(selectedOpportunities);
      await createIdeasFromOpportunities(productId, indices);
      setSuccessMessage(`Ideas created for ${indices.length} opportunity(ies)`);

      // Refresh idea statuses
      const statuses = await getOpportunityIdeaStatuses(productId);
      setIdeaStatuses(statuses);
      setSelectedOpportunities(new Set());
    } catch (err: any) {
      setError(err.message || "Failed to create ideas");
    } finally {
      setActionLoading(null);
    }
  };

  const handleExportJson = async () => {
    if (!report || selectedOpportunities.size === 0) return;

    try {
      setActionLoading("export-json");
      const indices = Array.from(selectedOpportunities);
      const data = await exportOpportunitiesJson(productId, indices);

      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `feature_opportunities_${
        new Date().toISOString().split("T")[0]
      }.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || "Failed to export opportunities");
    } finally {
      setActionLoading(null);
    }
  };

  const getIdeaStatusForOpportunity = (index: number) => {
    if (!ideaStatuses) return null;
    return ideaStatuses.statuses[index];
  };

  const countSelectedWithExistingIdeas = () => {
    if (!ideaStatuses) return 0;
    return Array.from(selectedOpportunities).filter(
      (idx) => ideaStatuses.statuses[idx]?.idea_created
    ).length;
  };

  // Combine and sort opportunities (high-impact first)
  const getSortedOpportunities = (): CombinedOpportunity[] => {
    if (!report) return [];

    return report.feature_opportunities
      .map((opp, index) => ({
        index,
        opportunity: opp,
        highImpactRank:
          report.high_impact_gaps.findIndex(
            (g) =>
              g.feature_name.toLowerCase() === opp.feature_name.toLowerCase()
          ) + 1 || undefined,
      }))
      .sort((a, b) => {
        // High impact first
        if (a.highImpactRank && !b.highImpactRank) return -1;
        if (!a.highImpactRank && b.highImpactRank) return 1;
        if (a.highImpactRank && b.highImpactRank)
          return a.highImpactRank - b.highImpactRank;
        // Then by priority score
        return b.opportunity.priority_score - a.opportunity.priority_score;
      });
  };

  if (loading) {
    return (
      <div className="p-6 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // Empty State
  if (!report) {
    return (
      <div className="p-6 text-center py-12">
        <div className="text-4xl mb-4">🌍</div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          No Landscape Analysis Available
        </h3>
        <p className="text-gray-500 mb-4 max-w-md mx-auto">
          The landscape analysis synthesizes all competitor reports into
          actionable feature opportunities. Run competitive analysis first.
        </p>
        {totalFunctionalReports > 0 && (
          <p className="text-sm text-gray-500 mb-4">
            Status: {functionalReportCount} of {totalFunctionalReports}{" "}
            competitor reports available
          </p>
        )}

        {/* Active Job Progress Banner */}
        {activeJobs.length > 0 && (
          <div className="mb-4 mx-auto max-w-md bg-blue-50 border border-blue-200 rounded-lg p-3 text-left">
            <div className="flex items-center gap-2">
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent"></div>
              <span className="text-sm font-medium text-blue-800">
                Analysis in progress
              </span>
            </div>
            <div className="mt-2 space-y-1">
              {activeJobs.map((job) => (
                <div key={job.id} className="text-xs text-blue-700">
                  {job.job_type === JobType.FUNCTIONAL_AUDIT
                    ? `Functional audit: ${job.input_data?.competitor_name || "competitor"}`
                    : job.job_type === JobType.LANDSCAPE_SYNTHESIS
                    ? "Landscape synthesis"
                    : job.job_type === JobType.SCHEDULED_DEEP_ANALYSIS
                    ? "Competitive analysis orchestration"
                    : job.job_type}
                  {" — "}
                  <span className="capitalize">{job.progress_message || job.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {successMessage && (
          <div className="mb-4 mx-auto max-w-md bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
            {successMessage}
          </div>
        )}

        <div className="flex gap-3 justify-center">
          <button
            onClick={handleRunSynthesisClick}
            disabled={
              actionLoading === "synthesis" ||
              actionLoading === "audits-then-synthesis" ||
              totalFunctionalReports === 0 ||
              activeJobs.length > 0
            }
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
          >
            {actionLoading === "synthesis" ||
            actionLoading === "audits-then-synthesis"
              ? "Starting..."
              : activeJobs.length > 0
              ? "Analysis Running..."
              : "Run Landscape Analysis"}
          </button>
        </div>
        {totalFunctionalReports > 0 && activeJobs.length === 0 && (
          <p className="text-xs text-gray-500 mt-2">
            Uses existing competitor reports for synthesis.
          </p>
        )}
      </div>
    );
  }

  const sortedOpportunities = getSortedOpportunities();

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">
          Landscape Analysis
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          Cross-competitor synthesis identifying feature opportunities and
          market gaps.
        </p>
      </div>

      {/* Report Metadata */}
      <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">
              Based on:{" "}
              <span className="font-medium">
                {report.competitor_count} competitor report{report.competitor_count !== 1 ? "s" : ""}
                {report.source_competitor_names && report.source_competitor_names.length > 0 && (
                  <> for {report.source_competitor_names.join(", ")}</>
                )}
              </span>{" "}
              &bull; Generated: {new Date(report.generated_at).toLocaleString()}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRunSynthesisClick}
              disabled={
                actionLoading === "synthesis" ||
                actionLoading === "audits-then-synthesis" ||
                activeJobs.length > 0
              }
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {actionLoading === "synthesis" ||
              actionLoading === "audits-then-synthesis"
                ? "Starting..."
                : activeJobs.length > 0
                ? "Analysis Running..."
                : "Re-run Synthesis"}
            </button>
            <button
              onClick={handleExportMd}
              disabled={actionLoading === "export-md"}
              className="px-3 py-1.5 text-sm border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
            >
              {actionLoading === "export-md"
                ? "Exporting..."
                : "Export Report .md"}
            </button>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="mb-6 flex gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-gray-900">
            {report.feature_cluster_matrix.length}
          </div>
          <div className="text-sm text-gray-500">Feature Clusters</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-gray-900">
            {report.feature_opportunities.length}
          </div>
          <div className="text-sm text-gray-500">Opportunities</div>
        </div>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
          {successMessage}
        </div>
      )}

      {/* Active Job Progress Banner */}
      {activeJobs.length > 0 && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="flex items-center gap-2">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent"></div>
            <span className="text-sm font-medium text-blue-800">
              Analysis in progress
            </span>
          </div>
          <div className="mt-2 space-y-1">
            {activeJobs.map((job) => (
              <div key={job.id} className="text-xs text-blue-700">
                {job.job_type === JobType.FUNCTIONAL_AUDIT
                  ? `Functional audit: ${job.input_data?.competitor_name || "competitor"}`
                  : job.job_type === JobType.LANDSCAPE_SYNTHESIS
                  ? "Landscape synthesis"
                  : job.job_type === JobType.SCHEDULED_DEEP_ANALYSIS
                  ? "Competitive analysis orchestration"
                  : job.job_type}
                {" — "}
                <span className="capitalize">{job.progress_message || job.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Executive Summary */}
      {report.analysis_summary && (
        <section className="mb-6">
          <h3 className="text-md font-medium text-gray-900 mb-3">
            Executive Summary
          </h3>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-700">{report.analysis_summary}</p>
          </div>
        </section>
      )}

      {/* Feature Opportunities */}
      <section className="mb-6">
        <h3 className="text-md font-medium text-gray-900 mb-3">
          Feature Opportunities
        </h3>
        <p className="text-sm text-gray-500 mb-4">
          Select opportunities to create ideas for customer voting, or export to
          another system.
        </p>

        <div className="flex items-center gap-4 mb-4">
          <button
            onClick={handleSelectAllOpportunities}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            {selectedOpportunities.size === report.feature_opportunities.length
              ? "Deselect All"
              : "Select All"}
          </button>
          <span className="text-sm text-gray-500">
            {selectedOpportunities.size} of{" "}
            {report.feature_opportunities.length} opportunities selected
          </span>
        </div>

        <div className="space-y-4">
          {sortedOpportunities.map(({ index, opportunity, highImpactRank }) => {
            const ideaStatus = getIdeaStatusForOpportunity(index);
            const hasIdea = ideaStatus?.idea_created;

            return (
              <FeatureOpportunityCard
                key={index}
                opportunity={opportunity}
                index={index}
                isSelected={selectedOpportunities.has(index)}
                onSelect={handleOpportunitySelection}
                hasIdea={hasIdea || false}
                highImpactRank={highImpactRank}
                competitorUrls={competitorUrls}
              />
            );
          })}
        </div>

        {/* Action Box */}
        {selectedOpportunities.size > 0 && (
          <div className="mt-4 bg-gray-50 border border-gray-200 rounded-lg p-4">
            <p className="text-sm text-gray-700 mb-3">
              {selectedOpportunities.size} opportunity
              {selectedOpportunities.size !== 1 ? "ies" : "y"} selected
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleCreateIdeas}
                disabled={actionLoading === "create-ideas"}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-sm disabled:opacity-50"
              >
                {actionLoading === "create-ideas"
                  ? "Creating..."
                  : "Create Ideas for Voting"}
              </button>
              <button
                onClick={handleExportJson}
                disabled={actionLoading === "export-json"}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm disabled:opacity-50"
              >
                {actionLoading === "export-json"
                  ? "Exporting..."
                  : "Export Selected as JSON"}
              </button>
            </div>
            {countSelectedWithExistingIdeas() > 0 && (
              <p className="text-xs text-gray-500 mt-2">
                Note: {countSelectedWithExistingIdeas()} selected item
                {countSelectedWithExistingIdeas() !== 1 ? "s" : ""} already{" "}
                {countSelectedWithExistingIdeas() !== 1 ? "have" : "has"} an
                idea - will be skipped for idea creation but included in export.
              </p>
            )}
          </div>
        )}
      </section>

      {/* Innovation Whitespace */}
      {report.innovation_whitespace && (
        <section className="mb-6">
          <h3 className="text-md font-medium text-gray-900 mb-3">
            Innovation Whitespace
          </h3>
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <p className="text-sm text-purple-800">
              {report.innovation_whitespace}
            </p>
          </div>
        </section>
      )}

      {/* Feature Cluster Matrix (Collapsible) */}
      {report.feature_cluster_matrix.length > 0 && (
        <section className="mb-6">
          <button
            onClick={() => setShowMatrix(!showMatrix)}
            className="flex items-center justify-between w-full text-left"
          >
            <h3 className="text-md font-medium text-gray-900">
              Feature Cluster Matrix
            </h3>
            <span className="text-sm text-gray-500">
              {showMatrix ? "Collapse ▲" : "Expand ▼"}
            </span>
          </button>

          {showMatrix && (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Feature
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Prevalence
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Our Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Competitors
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {report.feature_cluster_matrix.map((entry, idx) => (
                    <tr key={idx}>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {entry.feature_category}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            entry.prevalence === "Table Stakes"
                              ? "bg-red-100 text-red-700"
                              : entry.prevalence === "Common"
                              ? "bg-yellow-100 text-yellow-700"
                              : entry.prevalence === "Emerging"
                              ? "bg-blue-100 text-blue-700"
                              : "bg-purple-100 text-purple-700"
                          }`}
                        >
                          {entry.prevalence}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span
                          className={`font-medium ${
                            entry.our_status === "Gap"
                              ? "text-red-600"
                              : entry.our_status === "Have"
                              ? "text-green-600"
                              : "text-yellow-600"
                          }`}
                        >
                          {entry.our_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {entry.competitors_with_feature.slice(0, 3).join(", ")}
                        {entry.competitors_with_feature.length > 3 &&
                          ` +${entry.competitors_with_feature.length - 3}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Warning Modal for Missing Reports */}
      {showWarningModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white p-6 pb-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                Competitors Without Analysis
              </h3>
              <p className="text-sm text-gray-600 mt-1">
                {competitorsWithoutReports.length} competitor
                {competitorsWithoutReports.length !== 1 ? "s have" : " has"} not
                been audited yet. Select which to audit before running
                synthesis.
              </p>
            </div>

            <div className="p-6 pt-4">
              {/* Competitor List with Checkboxes */}
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    Competitors to Audit
                  </span>
                  <button
                    onClick={handleSelectAllForAudit}
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    {competitorsToAudit.size ===
                    competitorsWithoutReports.length
                      ? "Deselect All"
                      : "Select All"}
                  </button>
                </div>
                <div className="border border-gray-200 rounded-lg divide-y divide-gray-200 max-h-48 overflow-y-auto">
                  {competitorsWithoutReports.map((c) => (
                    <label
                      key={c.id}
                      className="flex items-center gap-3 p-3 hover:bg-gray-50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={competitorsToAudit.has(c.id)}
                        onChange={() => toggleCompetitorAudit(c.id)}
                        className="h-4 w-4 text-blue-600 rounded"
                      />
                      <div className="flex-1 min-w-0">
                        <span className="text-sm text-gray-900 block truncate">
                          {c.competitor_name}
                        </span>
                        {c.competitor_url && (
                          <span className="text-xs text-gray-500 block truncate">
                            {c.competitor_url}
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">
                        No report
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Summary */}
              <div className="bg-gray-50 rounded-lg p-3 mb-4">
                <p className="text-sm text-gray-700">
                  <span className="font-medium">{competitorsToAudit.size}</span>{" "}
                  competitor{competitorsToAudit.size !== 1 ? "s" : ""} will be
                  audited
                  {competitorsWithoutReports.length - competitorsToAudit.size >
                    0 && (
                    <>
                      ,{" "}
                      <span className="font-medium">
                        {competitorsWithoutReports.length -
                          competitorsToAudit.size}
                      </span>{" "}
                      will be skipped
                    </>
                  )}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {selectedFunctionalReports.length} existing report
                  {selectedFunctionalReports.length !== 1 ? "s" : ""} will be included
                  in synthesis
                </p>
              </div>

              {/* Actions */}
              <div className="space-y-3">
                {competitorsToAudit.size > 0 ? (
                  <>
                    <button
                      onClick={handleRunAuditsThenSynthesize}
                      disabled={actionLoading === "audits-then-synthesis"}
                      className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
                    >
                      {actionLoading === "audits-then-synthesis"
                        ? "Starting..."
                        : `Audit ${competitorsToAudit.size} Selected & Synthesize ${selectedFunctionalReports.length + competitorsToAudit.size}`}
                    </button>
                    <p className="text-xs text-gray-500 text-center">
                      Queues audits for selected competitors, then
                      automatically runs synthesis when complete.
                    </p>
                  </>
                ) : (
                  <>
                    <button
                      onClick={handleRunSynthesisOnly}
                      disabled={actionLoading === "synthesis"}
                      className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
                    >
                      {actionLoading === "synthesis"
                        ? "Starting..."
                        : `Skip & Synthesize ${selectedFunctionalReports.length}`}
                    </button>
                    <p className="text-xs text-gray-500 text-center">
                      Skip all unaudited competitors and synthesize using
                      existing reports only.
                    </p>
                  </>
                )}

                {competitorsToAudit.size > 0 && (
                  <>
                    <button
                      onClick={handleRunSynthesisOnly}
                      disabled={actionLoading === "synthesis"}
                      className="w-full px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium disabled:opacity-50"
                    >
                      {actionLoading === "synthesis"
                        ? "Starting..."
                        : `Skip & Synthesize ${selectedFunctionalReports.length}`}
                    </button>
                  </>
                )}

                <button
                  onClick={() => setShowWarningModal(false)}
                  className="w-full px-4 py-2 text-gray-500 hover:text-gray-700 font-medium"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
