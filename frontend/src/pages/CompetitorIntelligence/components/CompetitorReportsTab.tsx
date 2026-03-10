/**
 * CompetitorReportsTab
 *
 * Unified tab for competitive intelligence:
 * - Market Discovery section at top for running competitor discovery
 * - Competitor management section showing ALL competitors with status badges
 * - Functional audit reports for competitors with reports
 * - Add Competitor manually option
 * - Competitor alerts display
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { format } from 'date-fns';
import {
  getFunctionalReports,
  getFunctionalReport,
  triggerFunctionalAudit,
  exportFunctionalReportMd,
  getGapIdeaStatuses,
  createIdeasFromGaps,
  exportGapsJson,
  getAgentCompetitors,
  getAgentConfig,
  triggerCompetitorDiscovery,
  updateCompetitorSelection,
  deactivateCompetitor,
  triggerCompetitiveAnalysisV2,
  getCompetitorAlerts,
  markAlertRead,
  markAllAlertsRead,
  getProductJobs,
  CompetitorAlert,
} from '../../../services/api';
import type {
  FunctionalReportSummary,
  FunctionalReportDetail,
  BatchIdeaStatusesResponse,
  AgentCompetitor,
  CompetitiveAgentConfig,
  QueueJob,
} from '../../../types';
import { JobType, JobStatus } from '../../../types';
import AgentJobStatus from '../../../components/AgentJobStatus';
import AddCompetitorModal from './AddCompetitorModal';

interface Props {
  productId: number;
  refreshKey?: number;
  onAnalysisComplete?: () => void;
}

export default function CompetitorReportsTab({ productId, refreshKey, onAnalysisComplete }: Props) {
  // Competitor data
  const [competitors, setCompetitors] = useState<AgentCompetitor[]>([]);
  const [reports, setReports] = useState<FunctionalReportSummary[]>([]);
  const [agentConfig, setAgentConfig] = useState<CompetitiveAgentConfig | null>(null);
  const [alerts, setAlerts] = useState<CompetitorAlert[]>([]);

  // Loading states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail view state
  const [selectedReport, setSelectedReport] = useState<FunctionalReportDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [gapIdeaStatuses, setGapIdeaStatuses] = useState<BatchIdeaStatusesResponse | null>(null);

  // Gap selection state
  const [selectedGaps, setSelectedGaps] = useState<Set<number>>(new Set());

  // Modal state
  const [showAddCompetitorModal, setShowAddCompetitorModal] = useState(false);

  // Action states
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Audit job tracking: map competitor_id -> job status
  const [auditJobs, setAuditJobs] = useState<Map<number, QueueJob>>(new Map());
  const prevAuditJobCount = useRef(0);

  const fetchAllData = useCallback(async () => {
    try {
      setLoading(true);
      const [competitorsData, reportsData, configData, alertsData] = await Promise.all([
        getAgentCompetitors(productId),
        getFunctionalReports(productId),
        getAgentConfig(productId).catch(() => null),
        getCompetitorAlerts(productId, true).catch(() => []),
      ]);
      setCompetitors(competitorsData);
      setReports(reportsData);
      setAgentConfig(configData);
      setAlerts(alertsData);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData, refreshKey]);

  // Track whether a V2 analysis pipeline is active (orchestration or synthesis)
  const [v2PipelineActive, setV2PipelineActive] = useState(false);

  // Check for active audit jobs and V2 pipeline jobs
  const checkAuditJobs = useCallback(async () => {
    try {
      const [auditJobsList, pipelineJobs] = await Promise.all([
        getProductJobs(productId, 20, [JobType.FUNCTIONAL_AUDIT]),
        getProductJobs(productId, 5, [JobType.SCHEDULED_DEEP_ANALYSIS, JobType.LANDSCAPE_SYNTHESIS]),
      ]);

      const jobMap = new Map<number, QueueJob>();
      for (const job of auditJobsList) {
        const competitorId = job.input_data?.competitor_id;
        if (!competitorId) continue;
        // Keep the most recent job per competitor
        if (!jobMap.has(competitorId)) {
          jobMap.set(competitorId, job);
        }
      }
      setAuditJobs(jobMap);

      // Check if any V2 pipeline jobs are still active
      const pipelineActive = pipelineJobs.some(
        j => j.status === JobStatus.PENDING || j.status === JobStatus.QUEUED || j.status === JobStatus.RUNNING
      );
      setV2PipelineActive(pipelineActive);
    } catch (err) {
      console.error('[CompetitorReportsTab] Failed to check audit jobs:', err);
    }
  }, [productId]);

  // Initial audit job check
  useEffect(() => {
    checkAuditJobs();
  }, [checkAuditJobs]);

  // Poll while any audit jobs or V2 pipeline jobs are active
  useEffect(() => {
    const hasActiveAudits = Array.from(auditJobs.values()).some(
      (j) =>
        j.status === JobStatus.PENDING ||
        j.status === JobStatus.QUEUED ||
        j.status === JobStatus.RUNNING
    );
    if (!hasActiveAudits && !v2PipelineActive) return;

    const interval = setInterval(async () => {
      await checkAuditJobs();
    }, 3000);

    return () => clearInterval(interval);
  }, [auditJobs, v2PipelineActive, checkAuditJobs]);

  // Refresh data when an audit finishes (active count decreases)
  useEffect(() => {
    const activeCount = Array.from(auditJobs.values()).filter(
      (j) =>
        j.status === JobStatus.PENDING ||
        j.status === JobStatus.QUEUED ||
        j.status === JobStatus.RUNNING
    ).length;

    if (prevAuditJobCount.current > 0 && activeCount < prevAuditJobCount.current) {
      // An audit just finished — refresh reports
      fetchAllData();
    }
    prevAuditJobCount.current = activeCount;
  }, [auditJobs, fetchAllData]);

  // Clear success message after timeout
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Helper to find report for a competitor
  const getReportForCompetitor = (competitorId: number): FunctionalReportSummary | undefined => {
    return reports.find(r => r.product_competitor_id === competitorId);
  };

  // Discovery handlers
  const handleRunDiscovery = async () => {
    try {
      setActionLoading('discovery');
      await triggerCompetitorDiscovery(productId);
      setSuccessMessage('Market Discovery started. Check back shortly for results.');
      setTimeout(fetchAllData, 2000);
    } catch (err: any) {
      setError(err.message || 'Failed to start Market Discovery');
    } finally {
      setActionLoading(null);
    }
  };

  // Competitor selection toggle (for deep analysis)
  const handleToggleDeepAnalysis = async (competitorId: number, currentEnabled: boolean) => {
    try {
      setActionLoading(`toggle-${competitorId}`);
      await updateCompetitorSelection(productId, competitorId, !currentEnabled);
      // Update local state
      setCompetitors(prev =>
        prev.map(c =>
          c.id === competitorId ? { ...c, deep_analysis_enabled: !currentEnabled } : c
        )
      );
    } catch (err: any) {
      setError(err.message || 'Failed to update competitor');
    } finally {
      setActionLoading(null);
    }
  };

  // Select/Deselect all competitors for deep analysis
  const handleSelectAllCompetitors = async () => {
    const allSelected = competitors.every(c => c.deep_analysis_enabled);
    const targetState = !allSelected;

    try {
      setActionLoading('select-all');
      await Promise.all(
        competitors
          .filter(c => c.deep_analysis_enabled !== targetState)
          .map(c => updateCompetitorSelection(productId, c.id, targetState))
      );
      setCompetitors(prev => prev.map(c => ({ ...c, deep_analysis_enabled: targetState })));
    } catch (err: any) {
      setError(err.message || 'Failed to update competitors');
    } finally {
      setActionLoading(null);
    }
  };

  // Remove (deactivate) a competitor from the list
  const [confirmRemove, setConfirmRemove] = useState<number | null>(null);

  const handleRemoveCompetitor = async (competitorId: number) => {
    try {
      setActionLoading(`remove-${competitorId}`);
      await deactivateCompetitor(productId, competitorId);
      setCompetitors(prev => prev.filter(c => c.id !== competitorId));
      setConfirmRemove(null);
      setSuccessMessage('Competitor removed from list');
    } catch (err: any) {
      setError(err.message || 'Failed to remove competitor');
    } finally {
      setActionLoading(null);
    }
  };

  // Alert handlers
  const handleDismissAlert = async (alertId: number) => {
    try {
      await markAlertRead(productId, alertId);
      setAlerts(prev => prev.filter(a => a.id !== alertId));
    } catch (err: any) {
      setError(err.message || 'Failed to dismiss alert');
    }
  };

  const handleDismissAllAlerts = async () => {
    try {
      await markAllAlertsRead(productId);
      setAlerts([]);
    } catch (err: any) {
      setError(err.message || 'Failed to dismiss alerts');
    }
  };

  // Report handlers
  const handleViewReport = async (competitorId: number) => {
    try {
      setDetailLoading(true);
      const [report, statuses] = await Promise.all([
        getFunctionalReport(productId, competitorId),
        getGapIdeaStatuses(productId, competitorId),
      ]);
      setSelectedReport(report);
      setGapIdeaStatuses(statuses);
      setSelectedGaps(new Set());
    } catch (err: any) {
      setError(err.message || 'Failed to load report');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedReport(null);
    setGapIdeaStatuses(null);
    setSelectedGaps(new Set());
  };

  const handleRunAudit = async (competitorId: number, competitorName: string) => {
    try {
      setActionLoading(`audit-${competitorId}`);
      await triggerFunctionalAudit(productId, competitorId);
      setSuccessMessage(`Functional audit started for ${competitorName}`);
      checkAuditJobs();
    } catch (err: any) {
      setError(err.message || 'Failed to start audit');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRunAuditsAndSynthesize = async () => {
    const selectedForAnalysis = competitors.filter(c => c.deep_analysis_enabled);
    if (selectedForAnalysis.length === 0) {
      setError('No competitors selected for deep analysis');
      return;
    }

    try {
      setActionLoading('batch-audit');
      await triggerCompetitiveAnalysisV2(productId);
      setSuccessMessage(`Competitive analysis started for ${selectedForAnalysis.length} competitors (audits + landscape synthesis)`);
      checkAuditJobs();
      // Switch to landscape tab when analysis completes
      if (onAnalysisComplete) {
        // Poll for completion and switch tab
        const pollForCompletion = setInterval(async () => {
          const jobs = await getProductJobs(productId, 10, [JobType.SCHEDULED_DEEP_ANALYSIS]);
          const active = jobs.filter(
            j => j.status === JobStatus.PENDING || j.status === JobStatus.QUEUED || j.status === JobStatus.RUNNING
          );
          if (active.length === 0) {
            clearInterval(pollForCompletion);
            onAnalysisComplete();
          }
        }, 5000);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to start analysis');
    } finally {
      setActionLoading(null);
    }
  };

  const handleExportMd = async (competitorId: number, competitorName: string) => {
    try {
      setActionLoading(`export-${competitorId}`);
      const markdown = await exportFunctionalReportMd(productId, competitorId);

      // Create blob and download
      const blob = new Blob([markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${competitorName.replace(/\s+/g, '_')}_functional_audit.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || 'Failed to export report');
    } finally {
      setActionLoading(null);
    }
  };

  const handleGapSelection = (gapIndex: number) => {
    setSelectedGaps(prev => {
      const next = new Set(prev);
      if (next.has(gapIndex)) {
        next.delete(gapIndex);
      } else {
        next.add(gapIndex);
      }
      return next;
    });
  };

  const handleSelectAllGaps = () => {
    if (!selectedReport) return;
    const allGapIndices = selectedReport.gaps_deep_dive.map((_, i) => i);
    if (selectedGaps.size === allGapIndices.length) {
      setSelectedGaps(new Set());
    } else {
      setSelectedGaps(new Set(allGapIndices));
    }
  };

  const handleCreateIdeasFromGaps = async () => {
    if (!selectedReport || selectedGaps.size === 0) return;

    try {
      setActionLoading('create-ideas');
      const gapIndices = Array.from(selectedGaps);
      await createIdeasFromGaps(productId, selectedReport.product_competitor_id, gapIndices);
      setSuccessMessage(`Ideas created for ${gapIndices.length} gap(s)`);

      // Refresh idea statuses
      const statuses = await getGapIdeaStatuses(productId, selectedReport.product_competitor_id);
      setGapIdeaStatuses(statuses);
      setSelectedGaps(new Set());
    } catch (err: any) {
      setError(err.message || 'Failed to create ideas');
    } finally {
      setActionLoading(null);
    }
  };

  const handleExportGapsJson = async () => {
    if (!selectedReport || selectedGaps.size === 0) return;

    try {
      setActionLoading('export-json');
      const gapIndices = Array.from(selectedGaps);
      const data = await exportGapsJson(productId, selectedReport.product_competitor_id, gapIndices);

      // Create blob and download
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedReport.competitor_name.replace(/\s+/g, '_')}_gaps.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || 'Failed to export gaps');
    } finally {
      setActionLoading(null);
    }
  };

  const getIdeaStatusForGap = (gapIndex: number) => {
    if (!gapIdeaStatuses) return null;
    return gapIdeaStatuses.statuses[gapIndex];
  };

  const countSelectedWithExistingIdeas = () => {
    if (!gapIdeaStatuses) return 0;
    return Array.from(selectedGaps).filter(idx => gapIdeaStatuses.statuses[idx]?.idea_created).length;
  };

  // Stats
  const totalCompetitors = competitors.length;
  const selectedForAnalysis = competitors.filter(c => c.deep_analysis_enabled).length;
  const competitorsWithReports = reports.length;
  const activeAuditCount = Array.from(auditJobs.values()).filter(
    (j) =>
      j.status === JobStatus.PENDING ||
      j.status === JobStatus.QUEUED ||
      j.status === JobStatus.RUNNING
  ).length;

  if (loading) {
    return (
      <div className="p-6 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // Detail View (viewing a specific report)
  if (selectedReport) {
    return (
      <div className="p-6">
        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <button
              onClick={handleCloseDetail}
              className="text-blue-600 hover:text-blue-800 mb-2 font-medium text-sm"
            >
              &larr; Back to Competitors
            </button>
            <h2 className="text-lg font-semibold text-gray-900">
              Functional Audit: {selectedReport.competitor_name}
            </h2>
            <p className="text-sm text-gray-500">
              Generated: {new Date(selectedReport.generated_at).toLocaleString()} | Version {selectedReport.report_version}
            </p>
          </div>
          <button
            onClick={() => handleExportMd(selectedReport.product_competitor_id, selectedReport.competitor_name)}
            disabled={actionLoading === `export-${selectedReport.product_competitor_id}`}
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            {actionLoading === `export-${selectedReport.product_competitor_id}` ? 'Exporting...' : 'Export .md'}
          </button>
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

        {/* Competitor Context */}
        {selectedReport.competitor_context && (
          <section className="mb-6">
            <h3 className="text-md font-medium text-gray-900 mb-3">Competitor Context</h3>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              <p><span className="font-medium">Primary Focus:</span> {selectedReport.competitor_context.positioning}</p>
              <p><span className="font-medium">Target Market:</span> {selectedReport.competitor_context.target_customer}</p>
              <p><span className="font-medium">Key Differentiator:</span> {selectedReport.competitor_context.core_differentiation}</p>
            </div>
          </section>
        )}

        {/* Feature Comparison Table */}
        {selectedReport.functional_comparison.length > 0 && (
          <section className="mb-6">
            <h3 className="text-md font-medium text-gray-900 mb-3">Feature Comparison</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Feature</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Your Product</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{selectedReport.competitor_name}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Notes</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {selectedReport.functional_comparison.map((comp, idx) => (
                    <tr key={idx}>
                      <td className="px-4 py-3 text-sm text-gray-900">{comp.competitor_feature_name}</td>
                      <td className="px-4 py-3 text-sm">
                        {comp.mapping_status === 'Gap' ? (
                          <span className="text-red-600">&#10007;</span>
                        ) : comp.mapping_status === 'Advantage' ? (
                          <span className="text-green-600">&#10003; {comp.our_equivalent}</span>
                        ) : (
                          <span className="text-gray-600">&#10003; {comp.our_equivalent || ''}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">&#10003;</td>
                      <td className="px-4 py-3 text-sm text-gray-500">{comp.notes || comp.functional_description?.slice(0, 50)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Gap Analysis with Selection */}
        {selectedReport.gaps_deep_dive.length > 0 && (
          <section className="mb-6">
            <h3 className="text-md font-medium text-gray-900 mb-3">Gap Analysis</h3>
            <p className="text-sm text-gray-500 mb-4">
              Select gaps to create ideas for voting or export to another system.
            </p>

            <div className="flex items-center gap-4 mb-4">
              <button
                onClick={handleSelectAllGaps}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                {selectedGaps.size === selectedReport.gaps_deep_dive.length ? 'Deselect All' : 'Select All'}
              </button>
              <span className="text-sm text-gray-500">
                {selectedGaps.size} of {selectedReport.gaps_deep_dive.length} gaps selected
              </span>
            </div>

            <div className="space-y-3">
              {selectedReport.gaps_deep_dive.map((gap, idx) => {
                const ideaStatus = getIdeaStatusForGap(idx);
                const hasIdea = ideaStatus?.idea_created;

                return (
                  <div
                    key={idx}
                    className={`border rounded-lg p-4 ${selectedGaps.has(idx) ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}
                  >
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={selectedGaps.has(idx)}
                        onChange={() => handleGapSelection(idx)}
                        className="mt-1 w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h4 className="font-medium text-gray-900">{gap.feature_name}</h4>
                          {hasIdea && (
                            <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                              Idea submitted for voting
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-700 mt-1">
                          <span className="font-medium">User Problem:</span> {gap.user_problem}
                        </p>
                        {gap.evidence && (
                          <p className="text-sm text-gray-500 mt-1">
                            <span className="font-medium">Evidence:</span> {gap.evidence}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Action Box */}
            {selectedGaps.size > 0 && (
              <div className="mt-4 bg-gray-50 border border-gray-200 rounded-lg p-4">
                <p className="text-sm text-gray-700 mb-3">
                  {selectedGaps.size} gap{selectedGaps.size !== 1 ? 's' : ''} selected
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={handleCreateIdeasFromGaps}
                    disabled={actionLoading === 'create-ideas'}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-sm disabled:opacity-50"
                  >
                    {actionLoading === 'create-ideas' ? 'Creating...' : 'Create Ideas for Voting'}
                  </button>
                  <button
                    onClick={handleExportGapsJson}
                    disabled={actionLoading === 'export-json'}
                    className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm disabled:opacity-50"
                  >
                    {actionLoading === 'export-json' ? 'Exporting...' : 'Export Selected as JSON'}
                  </button>
                </div>
                {countSelectedWithExistingIdeas() > 0 && (
                  <p className="text-xs text-gray-500 mt-2">
                    Note: {countSelectedWithExistingIdeas()} selected gap{countSelectedWithExistingIdeas() !== 1 ? 's' : ''} already
                    {countSelectedWithExistingIdeas() !== 1 ? ' have' : ' has'} an idea - will be skipped for idea creation but included in export.
                  </p>
                )}
              </div>
            )}
          </section>
        )}

        {/* Technical Constraints */}
        {selectedReport.technical_constraints && (
          <section className="mb-6">
            <h3 className="text-md font-medium text-gray-900 mb-3">Technical Constraints</h3>
            <div className="bg-gray-50 rounded-lg p-4 space-y-3">
              {selectedReport.technical_constraints.integrations && selectedReport.technical_constraints.integrations.length > 0 && (
                <div>
                  <span className="font-medium">Integrations:</span>
                  <span className="text-sm text-gray-700 ml-2">
                    {selectedReport.technical_constraints.integrations.join(', ')}
                  </span>
                </div>
              )}
              {selectedReport.technical_constraints.api_capabilities && (
                <div>
                  <span className="font-medium">API Capabilities:</span>
                  <p className="text-sm text-gray-700 mt-1">{selectedReport.technical_constraints.api_capabilities}</p>
                </div>
              )}
              {selectedReport.technical_constraints.platform_requirements && (
                <div>
                  <span className="font-medium">Platform Requirements:</span>
                  <p className="text-sm text-gray-700 mt-1">{selectedReport.technical_constraints.platform_requirements}</p>
                </div>
              )}
              {selectedReport.technical_constraints.notes && (
                <div>
                  <span className="font-medium">Additional Notes:</span>
                  <p className="text-sm text-gray-700 mt-1">{selectedReport.technical_constraints.notes}</p>
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    );
  }

  // Main List View
  return (
    <div className="p-6 space-y-6">
      {/* Alerts Section */}
      {alerts.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-yellow-800 flex items-center gap-2">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              Alerts
            </h3>
            <button
              onClick={handleDismissAllAlerts}
              className="text-sm text-yellow-700 hover:text-yellow-900"
            >
              Dismiss All
            </button>
          </div>
          <div className="space-y-2">
            {alerts.map(alert => (
              <div key={alert.id} className="flex items-center justify-between bg-white rounded p-3 border border-yellow-100">
                <div>
                  <span className="text-sm font-medium text-gray-900">{alert.message}</span>
                  <span className="text-xs text-gray-500 ml-2">
                    {format(new Date(alert.created_at), 'MMM d, h:mm a')}
                  </span>
                </div>
                <button
                  onClick={() => handleDismissAlert(alert.id)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Market Discovery Section */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-gray-900">Market Discovery</h3>
            <p className="text-sm text-gray-500 mt-1">
              Discover competitors in your market space using AI.
            </p>
          </div>
          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
            agentConfig?.competitor_discovery_mode === 'scheduled' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
          }`}>
            {agentConfig?.competitor_discovery_mode === 'scheduled'
              ? `Scheduled (${agentConfig.competitor_discovery_schedule})`
              : 'Manual'}
          </span>
        </div>

        {/* Job Status */}
        <AgentJobStatus
          productId={productId}
          jobTypes={[JobType.COMPETITOR_DISCOVERY]}
          onJobComplete={fetchAllData}
          className="mb-4"
        />

        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            {totalCompetitors > 0 ? (
              <span>Found: {totalCompetitors} competitors</span>
            ) : (
              <span>No competitors discovered yet</span>
            )}
          </div>
          <button
            onClick={handleRunDiscovery}
            disabled={actionLoading === 'discovery'}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-sm disabled:opacity-50"
          >
            {actionLoading === 'discovery' ? 'Starting...' : 'Discover Competitors'}
          </button>
        </div>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-600 hover:text-red-800">×</button>
        </div>
      )}

      {successMessage && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
          {successMessage}
        </div>
      )}

      {/* Competitor Reports Section */}
      <div className="bg-white border border-gray-200 rounded-lg">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-gray-900">Competitor Reports</h3>
              <p className="text-sm text-gray-500 mt-1">
                Manage competitors and run functional audits.
              </p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-500">
                {totalCompetitors} total | {competitorsWithReports} with reports | {selectedForAnalysis} selected
              </span>
              {totalCompetitors > 0 && (
                <button
                  onClick={handleSelectAllCompetitors}
                  disabled={actionLoading === 'select-all'}
                  className="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50"
                >
                  {actionLoading === 'select-all'
                    ? 'Updating...'
                    : competitors.every(c => c.deep_analysis_enabled)
                    ? 'Deselect All'
                    : 'Select All'}
                </button>
              )}
            </div>
          </div>

          {/* Actions bar */}
          <div className="flex gap-3 mt-4">
            <button
              onClick={() => setShowAddCompetitorModal(true)}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm"
            >
              Add Competitor
            </button>
            <button
              onClick={handleRunAuditsAndSynthesize}
              disabled={actionLoading === 'batch-audit' || selectedForAnalysis === 0 || activeAuditCount > 0}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-sm disabled:opacity-50"
            >
              {actionLoading === 'batch-audit'
                ? 'Starting...'
                : activeAuditCount > 0
                ? `Audits Running (${activeAuditCount})`
                : `Run Audits and Synthesize Selected (${selectedForAnalysis})`}
            </button>
          </div>
        </div>

        {/* Competitor List */}
        {competitors.length === 0 ? (
          <div className="p-8 text-center">
            <div className="text-4xl mb-4">🔍</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Competitors Yet</h3>
            <p className="text-gray-500 mb-4">
              Run market discovery above to find competitors, or add one manually.
            </p>
            <button
              onClick={() => setShowAddCompetitorModal(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-sm"
            >
              Add Competitor
            </button>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {competitors.map((competitor) => {
              const report = getReportForCompetitor(competitor.id);
              const hasReport = !!report;
              const auditJob = auditJobs.get(competitor.id);
              const isAuditActive = auditJob && (
                auditJob.status === JobStatus.PENDING ||
                auditJob.status === JobStatus.QUEUED ||
                auditJob.status === JobStatus.RUNNING
              );

              return (
                <div key={competitor.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      {/* Selection for deep analysis */}
                      <input
                        type="checkbox"
                        checked={competitor.deep_analysis_enabled}
                        onChange={() => handleToggleDeepAnalysis(competitor.id, competitor.deep_analysis_enabled)}
                        disabled={actionLoading === `toggle-${competitor.id}`}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        title="Enable for deep analysis"
                      />

                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-gray-900">{competitor.competitor_name}</h4>
                          {/* Status badges */}
                          {hasReport && !isAuditActive && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded">
                              Report Available
                            </span>
                          )}
                          {competitor.deep_analysis_enabled && !hasReport && !isAuditActive && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded">
                              Selected for Analysis
                            </span>
                          )}
                          {!competitor.deep_analysis_enabled && !isAuditActive && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded">
                              Not Selected
                            </span>
                          )}
                          {/* Audit job status badge */}
                          {isAuditActive && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded flex items-center gap-1">
                              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
                              {auditJob.status === JobStatus.RUNNING
                                ? 'Auditing...'
                                : auditJob.status === JobStatus.QUEUED
                                ? 'Queued'
                                : 'Starting...'}
                            </span>
                          )}
                        </div>
                        {/* Audit progress bar */}
                        {isAuditActive && auditJob.status === JobStatus.RUNNING && (
                          <div className="mt-1 flex items-center gap-2">
                            <div className="w-32 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-300 ${
                                  auditJob.progress_percent > 0 ? 'bg-blue-500' : 'bg-blue-400 animate-pulse'
                                }`}
                                style={{ width: auditJob.progress_percent > 0 ? `${auditJob.progress_percent}%` : '100%' }}
                              />
                            </div>
                            {auditJob.progress_message && (
                              <span className="text-xs text-gray-500 truncate max-w-48">
                                {auditJob.progress_message}
                              </span>
                            )}
                          </div>
                        )}
                        {competitor.competitor_url && (
                          <a
                            href={competitor.competitor_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:text-blue-800"
                          >
                            {competitor.competitor_url}
                          </a>
                        )}
                      </div>
                    </div>

                    {/* Stats and Actions */}
                    <div className="flex items-center gap-4">
                      {hasReport && (
                        <>
                          <div className="text-center">
                            <div className="text-lg font-semibold text-gray-900">{report.features_compared}</div>
                            <div className="text-xs text-gray-500">Features</div>
                          </div>
                          <div className="text-center">
                            <div className="text-lg font-semibold text-gray-900">{report.gaps_identified}</div>
                            <div className="text-xs text-gray-500">Gaps</div>
                          </div>
                        </>
                      )}

                      <div className="flex gap-2">
                        {hasReport && (
                          <button
                            onClick={() => handleViewReport(competitor.id)}
                            disabled={detailLoading}
                            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                          >
                            View
                          </button>
                        )}
                        <button
                          onClick={() => handleRunAudit(competitor.id, competitor.competitor_name)}
                          disabled={actionLoading === `audit-${competitor.id}` || !!isAuditActive}
                          className="px-3 py-1.5 text-sm border border-gray-300 text-gray-700 rounded hover:bg-gray-50 disabled:opacity-50"
                        >
                          {actionLoading === `audit-${competitor.id}` ? 'Starting...' : isAuditActive ? 'In Progress' : 'Audit'}
                        </button>
                        {confirmRemove === competitor.id ? (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleRemoveCompetitor(competitor.id)}
                              disabled={actionLoading === `remove-${competitor.id}`}
                              className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                            >
                              {actionLoading === `remove-${competitor.id}` ? '...' : 'Confirm'}
                            </button>
                            <button
                              onClick={() => setConfirmRemove(null)}
                              className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setConfirmRemove(competitor.id)}
                            className="px-2 py-1.5 text-sm text-gray-400 hover:text-red-600 rounded hover:bg-red-50"
                            title="Remove competitor"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Add Competitor Modal */}
      {showAddCompetitorModal && (
        <AddCompetitorModal
          productId={productId}
          onAdd={() => {
            setShowAddCompetitorModal(false);
            fetchAllData();
            setSuccessMessage('Competitor added successfully');
          }}
          onClose={() => setShowAddCompetitorModal(false)}
        />
      )}
    </div>
  );
}
