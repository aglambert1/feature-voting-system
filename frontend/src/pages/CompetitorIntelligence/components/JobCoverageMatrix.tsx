import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { exportJobCoverage, getJobCoverage, runSelfAssessment } from '../../../services/api';
import type {
  JobCoverageCell,
  JobCoverageResponse,
  JobCoverageRow,
} from '../../../types';

/**
 * View 2 — our score beside every tracked competitor's, one row per job.
 *
 * A join over audits that have already run: no LLM call, and not gated behind synthesis,
 * which answers a different question. Synthesis weighs all evidence and recommends where
 * to invest; this reports what the audits found.
 */

interface Props {
  productId: number;
}

const POSITION_STYLES: Record<string, string> = {
  advantage: 'bg-green-50 text-green-800',
  gap: 'bg-orange-50 text-orange-800',
  parity: 'bg-gray-100 text-gray-600',
  differentiator: 'bg-teal-50 text-teal-800',
  unknown: 'text-gray-400',
};

const IMPORTANCE_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

/** Weakest coverage first within an importance band — the rows worth acting on. */
const POSITION_WEIGHT: Record<string, number> = {
  gap: 0,
  parity: 1,
  unknown: 2,
  advantage: 3,
  differentiator: 4,
};

function worstPosition(row: JobCoverageRow): number {
  const weights = row.competitors
    .filter((c) => c.assessed && c.verdict_shown !== false)
    .map((c) => POSITION_WEIGHT[(c.human_position ?? c.system_position) ?? 'unknown'] ?? 2);
  return weights.length ? Math.min(...weights) : 2;
}

function Cell({ cell }: { cell: JobCoverageCell }) {
  if (!cell.assessed) {
    return (
      <td className="px-2 py-3 text-center align-middle">
        <span className="text-xs text-gray-300">not audited</span>
      </td>
    );
  }

  // A human override stands regardless of whether our derived score is grounded: it is
  // their claim, not something computed from ours. Rendering "no verdict" above a
  // "yours" marker made the cell contradict itself.
  const verdictShown = cell.verdict_shown !== false || !!cell.human_position;
  const verdict = (cell.human_position ?? cell.system_position) ?? 'unknown';

  return (
    <td className="px-2 py-3 text-center align-middle">
      <div className="flex flex-col items-center gap-1">
        <span className="text-sm font-mono tabular-nums text-gray-900">
          {cell.competitor_score ?? '—'}
        </span>
        {verdictShown ? (
          <span
            className={`text-[0.6rem] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded ${POSITION_STYLES[verdict]}`}
          >
            {verdict}
          </span>
        ) : (
          // Their score stands: it is researched independently of our job map and is
          // unaffected by that map's weakness. Only the comparison is withheld.
          <span className="text-[0.6rem] text-gray-300" title={cell.verdict_withheld_reason ?? ''}>
            no verdict
          </span>
        )}
        {cell.human_position && (
          <span className="text-[0.55rem] uppercase tracking-wide text-teal-700">yours</span>
        )}
      </div>
    </td>
  );
}

export default function JobCoverageMatrix({ productId }: Props) {
  const [data, setData] = useState<JobCoverageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [assessing, setAssessing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getJobCoverage(productId)
      .then(setData)
      .catch((e) => setError(e.message || 'Failed to load job coverage'))
      .finally(() => setLoading(false));
  }, [productId]);

  const handleExport = async () => {
    try {
      setExporting(true);
      const md = await exportJobCoverage(productId);
      const blob = new Blob([md], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${(data?.product_name ?? 'product').replace(/\s+/g, '_')}_job_coverage.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e.message || 'Failed to export');
    } finally {
      setExporting(false);
    }
  };

  const handleSelfAssess = async () => {
    try {
      setAssessing(true);
      await runSelfAssessment(productId);
      setMessage(
        'Self-assessment queued. Existing audits refresh automatically when it finishes — ' +
          'no need to re-run them.'
      );
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Failed to start self-assessment');
    } finally {
      setAssessing(false);
    }
  };

  if (loading) return <div className="p-6 text-sm text-gray-500">Loading job coverage...</div>;
  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
          {error}
        </div>
      </div>
    );
  }
  if (!data) return null;

  const { jobs, competitors, map_health: health, self_assessment: self } = data;

  if (!jobs.length) {
    return (
      <div className="p-6">
        <div className="bg-amber-50 rounded-lg p-4 text-sm text-gray-800 max-w-2xl">
          <b>No job map yet.</b>
          <p className="text-gray-600 mt-1">
            Coverage is organised around the jobs your customers are trying to do. Build a job
            map first, then audits and this comparison become possible.
          </p>
          <Link
            to={`/product-intelligence/products/${productId}/job-map`}
            className="inline-block mt-3 px-3 py-1.5 text-sm bg-teal-700 text-white rounded-lg hover:bg-teal-800"
          >
            Build the job map
          </Link>
        </div>
      </div>
    );
  }

  const sorted = [...jobs].sort((a, b) => {
    const imp =
      (IMPORTANCE_ORDER[a.importance ?? 'medium'] ?? 2) -
      (IMPORTANCE_ORDER[b.importance ?? 'medium'] ?? 2);
    return imp !== 0 ? imp : worstPosition(a) - worstPosition(b);
  });

  const productDerivedOnly = health.total_jobs - health.jobs_with_independent_source;
  const staleCount = competitors.filter((c) => c.stale).length;
  const unaudited = competitors.filter((c) => !c.audited).length;

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-start gap-6 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Job coverage</h2>
          <p className="text-sm text-gray-500 mt-1">
            {competitors.length} tracked competitor{competitors.length === 1 ? '' : 's'}
            {unaudited > 0 && ` · ${unaudited} not yet audited`}
            {staleCount > 0 && ` · ${staleCount} audit${staleCount === 1 ? '' : 's'} over 30 days old`}
            {' · sorted by importance, then weakest coverage'}
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          {exporting ? 'Exporting...' : 'Export .md'}
        </button>
      </div>

      {message && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
          {message}
        </div>
      )}

      {/* Our column is missing entirely without a self-assessment, and every verdict with
          it — position needs both sides. Offer the fix rather than just the symptom. */}
      {!self.exists && (
        <div className="bg-amber-50 rounded-lg p-3 text-sm text-gray-800 flex items-start gap-3 flex-wrap">
          <span className="font-semibold text-amber-800">!</span>
          <div className="flex-1 min-w-[18rem]">
            <b>No self-assessment yet, so no comparison can be made.</b>
            <p className="text-gray-600 mt-1">
              Competitor scores below are real. How we compare needs our own side scored
              against the same job map.
            </p>
          </div>
          <button
            onClick={handleSelfAssess}
            disabled={assessing}
            className="px-3 py-1.5 text-sm bg-teal-700 text-white rounded-lg hover:bg-teal-800 disabled:opacity-50"
          >
            {assessing ? 'Starting...' : 'Assess our product'}
          </button>
        </div>
      )}

      {self.exists && self.evidence_based === false && (
        <details className="bg-amber-50 rounded-lg px-3 py-2 text-sm text-gray-800">
          <summary className="cursor-pointer list-none flex items-center gap-2">
            <span className="font-semibold text-amber-800">!</span>
            <b>Our scores rest only on the product description.</b>
            <span className="text-gray-500 text-xs underline underline-offset-2">
              Why this matters
            </span>
          </summary>
          <p className="text-gray-600 mt-2">
            The job map was generated from that same description, so scoring against it mostly
            confirms the product does what it says. Importing support tickets or win/loss notes,
            or adding evidence, gives the assessment something independent to work from.
          </p>
        </details>
      )}

      {productDerivedOnly > 0 && (
        <details className="bg-amber-50 rounded-lg px-3 py-2 text-sm text-gray-800">
          <summary className="cursor-pointer list-none flex items-center gap-2">
            <span className="font-semibold text-amber-800">!</span>
            <b>
              {productDerivedOnly} of {health.total_jobs} jobs were written from your product
              description.
            </b>
            <span className="text-gray-500 text-xs underline underline-offset-2">
              Why this matters
            </span>
          </summary>
          <p className="text-gray-600 mt-2">
            A product always scores well against jobs derived from its own marketing. Jobs added
            from customer signal, lost deals, or competitor research make these scores mean more.
            Where our side has nothing behind it, no verdict is shown — the competitor's score
            still is.
          </p>
        </details>
      )}

      <div className="border border-gray-200 rounded-lg overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-2 text-[0.68rem] font-semibold uppercase tracking-wider text-gray-400 min-w-[18rem]">
                Job
              </th>
              <th className="px-2 py-2 text-[0.68rem] font-semibold uppercase tracking-wider text-gray-400 w-20">
                Us
              </th>
              {competitors.map((c) => (
                <th key={c.competitor_id} className="px-2 py-2 w-24 align-bottom">
                  <div className="text-[0.68rem] font-semibold uppercase tracking-wider text-gray-500 truncate">
                    {c.competitor_name}
                  </div>
                  {/* Staleness belongs to the audit, so it belongs in the competitor's
                      column header — not on a job row, where it would read as the job
                      being stale. */}
                  <div
                    className={`text-[0.6rem] font-normal normal-case tracking-normal ${
                      c.stale ? 'text-amber-700' : 'text-gray-400'
                    }`}
                  >
                    {c.audited
                      ? `${c.stale ? '⚠ ' : ''}${c.audit_age_days}d ago`
                      : 'not audited'}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => {
              // Server-decided: our score is grounded by evidence, by non-low
              // confidence, or by a PM having judged this job on any competitor.
              const rowGrounded = row.our_score_grounded;
              return (
              <tr key={row.job_id} className="border-b border-gray-200 last:border-b-0">
                <td className="px-4 py-3 align-top">
                  <Link
                    to={`/product-intelligence/products/${productId}/job-coverage/${row.job_id}`}
                    className="group"
                  >
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-mono text-sm font-semibold text-teal-700 group-hover:underline">
                        {row.job_id}
                      </span>
                      <span
                        className={`text-[0.62rem] uppercase tracking-wide font-semibold ${
                          row.importance === 'critical' ? 'text-orange-700' : 'text-gray-400'
                        }`}
                      >
                        {row.importance}
                      </span>
                      {row.serve_intent === 'out_of_target' && (
                        <span className="text-[0.6rem] text-gray-500 border border-gray-300 rounded px-1">
                          out of target
                        </span>
                      )}
                    </div>
                    <p className="font-serif text-sm leading-snug text-gray-900 max-w-lg group-hover:text-teal-800">
                      {row.job_statement}
                    </p>
                  </Link>
                </td>
                <td className="px-2 py-3 text-center align-middle">
                  {/* Grounding is per job, not per competitor, so when the verdict is
                      withheld the score behind it is exactly the one we just said not to
                      trust. Showing it here while View 1 hides it would state the number
                      plainly in one place and disown it in the other. */}
                  <span
                    className={`text-sm font-mono tabular-nums ${
                      rowGrounded ? 'text-gray-900' : 'text-gray-300'
                    }`}
                  >
                    {rowGrounded ? (row.our_score ?? '—') : '—'}
                  </span>
                  {row.corroborating_signals > 0 && (
                    <div className="text-[0.55rem] text-teal-700">
                      {row.corroborating_signals} signal
                      {row.corroborating_signals === 1 ? '' : 's'}
                    </div>
                  )}
                </td>
                {competitors.map((c) => {
                  const cell = row.competitors.find((x) => x.competitor_id === c.competitor_id);
                  return cell ? (
                    <Cell key={c.competitor_id} cell={cell} />
                  ) : (
                    <td key={c.competitor_id} />
                  );
                })}
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-400">
        Click a job to see it across every competitor.
      </p>
    </div>
  );
}
