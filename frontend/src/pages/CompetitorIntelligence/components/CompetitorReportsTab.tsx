/**
 * CompetitorReportsTab
 *
 * V2 Competitive Analysis: Displays functional audit reports for each competitor.
 * Includes per-gap idea creation and JSON export functionality.
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  getFunctionalReports,
  getFunctionalReport,
  triggerFunctionalAudit,
  exportFunctionalReportMd,
  getGapIdeaStatuses,
  createIdeasFromGaps,
  exportGapsJson,
} from '../../../services/api';
import type {
  FunctionalReportSummary,
  FunctionalReportDetail,
  BatchIdeaStatusesResponse,
} from '../../../types';

interface Props {
  productId: number;
  refreshKey?: number;
}

export default function CompetitorReportsTab({ productId, refreshKey }: Props) {
  const [reports, setReports] = useState<FunctionalReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail view state
  const [selectedReport, setSelectedReport] = useState<FunctionalReportDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [gapIdeaStatuses, setGapIdeaStatuses] = useState<BatchIdeaStatusesResponse | null>(null);

  // Gap selection state
  const [selectedGaps, setSelectedGaps] = useState<Set<number>>(new Set());

  // Action states
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchReports = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getFunctionalReports(productId);
      setReports(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load reports');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports, refreshKey]);

  // Clear success message after timeout
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

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
      fetchReports();
    } catch (err: any) {
      setError(err.message || 'Failed to start audit');
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

  if (loading) {
    return (
      <div className="p-6 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // Detail View
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
              &larr; Back to Reports
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

  // List View
  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Competitor Reports</h2>
        <p className="text-sm text-gray-500 mt-1">
          Functional audits compare each competitor's features against your product.
        </p>
        <Link
          to={`/product-intelligence/products/${productId}/competitors`}
          className="text-sm text-blue-600 hover:text-blue-800 mt-2 inline-block"
        >
          Manage competitors in Market Discovery &rarr;
        </Link>
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

      {reports.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-4xl mb-4">📊</div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Competitor Reports Available</h3>
          <p className="text-gray-500 mb-4">
            Run competitive analysis to generate functional audit reports for each of your tracked competitors.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {reports.map((report) => (
            <div
              key={report.id}
              className="bg-gray-50 border border-gray-200 rounded-lg p-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <h3 className="font-medium text-gray-900">{report.competitor_name}</h3>
                  {report.competitor_url && (
                    <a
                      href={report.competitor_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      {report.competitor_url}
                    </a>
                  )}
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <div className="text-lg font-semibold text-gray-900">{report.features_compared}</div>
                    <div className="text-xs text-gray-500">Features</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-gray-900">{report.gaps_identified}</div>
                    <div className="text-xs text-gray-500">Gaps</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm text-gray-500">
                      {new Date(report.generated_at).toLocaleDateString()}
                    </div>
                    <div className="text-xs text-gray-500">Updated</div>
                  </div>
                </div>
              </div>

              <div className="flex gap-2 mt-4 justify-end">
                <button
                  onClick={() => handleViewReport(report.product_competitor_id)}
                  disabled={detailLoading}
                  className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  View Report
                </button>
                <button
                  onClick={() => handleRunAudit(report.product_competitor_id, report.competitor_name)}
                  disabled={actionLoading === `audit-${report.product_competitor_id}`}
                  className="px-3 py-1.5 text-sm border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
                >
                  {actionLoading === `audit-${report.product_competitor_id}` ? 'Running...' : 'Run Audit'}
                </button>
                <button
                  onClick={() => handleExportMd(report.product_competitor_id, report.competitor_name)}
                  disabled={actionLoading === `export-${report.product_competitor_id}`}
                  className="px-3 py-1.5 text-sm border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
                >
                  Export .md
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info Box */}
      <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          <span className="font-medium">Tip:</span> Full competitive analysis (all competitors + landscape synthesis)
          is triggered from the Competitive Analysis Agent card on the Product Dashboard.
        </p>
      </div>
    </div>
  );
}
