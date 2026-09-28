import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getJobCoverage } from '../../services/api';
import Navigation from '../../components/Navigation';
import type { JobCoverageResponse, JobCoverageRow } from '../../types';

/**
 * View 3 — one job, across every tracked competitor.
 *
 * Reached from a cell or job in the coverage matrix. Answers "how is this job served
 * across the market", which the per-competitor report cannot: that one holds a
 * competitor fixed and varies the job.
 */

const POSITION_STYLES: Record<string, string> = {
  advantage: 'bg-green-50 text-green-800 border-green-200',
  gap: 'bg-orange-50 text-orange-800 border-orange-200',
  parity: 'bg-gray-100 text-gray-700 border-gray-200',
  differentiator: 'bg-teal-50 text-teal-800 border-teal-200',
  unknown: 'bg-transparent text-gray-500 border-gray-300 border-dashed',
};

function tierPips(score: number | null | undefined, mine?: boolean) {
  const tier =
    score === null || score === undefined || score <= 0 || score > 10
      ? null
      : Math.floor((score + 1) / 2);
  return (
    <div className="flex gap-0.5" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((i) =>
        tier === null ? (
          <span
            key={i}
            className="w-1.5 h-4 rounded-sm border border-dashed border-gray-400 bg-gray-50"
          />
        ) : (
          <span
            key={i}
            className={`w-1.5 h-4 rounded-sm ${
              i <= tier ? (mine ? 'bg-teal-700' : 'bg-gray-500') : 'bg-gray-200'
            }`}
          />
        )
      )}
    </div>
  );
}

export default function JobDetailPage() {
  const { productId, jobId } = useParams<{ productId: string; jobId: string }>();
  const numProductId = Number(productId);
  const [data, setData] = useState<JobCoverageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getJobCoverage(numProductId)
      .then(setData)
      .catch((e) => setError(e.message || 'Failed to load job coverage'))
      .finally(() => setLoading(false));
  }, [numProductId]);

  if (loading) return <><Navigation /><div className="p-8 text-sm text-gray-500">Loading...</div></>;
  if (error) {
    return (
      <>
        <Navigation />
        <div className="p-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
            {error}
          </div>
        </div>
      </>
    );
  }
  if (!data) return null;

  const row: JobCoverageRow | undefined = data.jobs.find((j) => j.job_id === jobId);
  if (!row) {
    return (
      <>
        <Navigation />
        <div className="p-8 max-w-3xl mx-auto">
        <Link
          to={`/product-intelligence/products/${productId}/intelligence?tab=job-coverage`}
          className="text-sm text-teal-700 hover:underline"
        >
          &larr; Back to job coverage
        </Link>
        <div className="mt-4 bg-amber-50 rounded-lg p-4 text-sm text-gray-800">
          <b>Job “{jobId}” is not in this product's map.</b>
          <p className="text-gray-600 mt-1">
            It may have been removed or renamed since this link was made.
          </p>
        </div>
        </div>
      </>
    );
  }

  const byId = new Map(data.competitors.map((c) => [c.competitor_id, c]));

  const ourScoreGrounded = row.our_score_grounded;
  const provenanceType = row.provenance?.type ?? 'unknown';
  const provenanceLabel: Record<string, string> = {
    product_derived: 'written from the product description',
    signal_derived: 'proposed by a customer signal',
    competitor_derived: 'proposed by a competitor capability',
    pm_authored: 'written by hand',
    unknown: 'origin not recorded',
  };

  return (
    <>
      <Navigation />
      <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <Link
          to={`/product-intelligence/products/${productId}/intelligence?tab=job-coverage`}
          className="text-sm text-teal-700 hover:underline"
        >
          &larr; Back to job coverage
        </Link>
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          <span className="font-mono text-base font-semibold text-teal-700">{row.job_id}</span>
          <span
            className={`text-[0.66rem] uppercase tracking-wide font-semibold ${
              row.importance === 'critical' ? 'text-orange-700' : 'text-gray-500'
            }`}
          >
            {row.importance}
          </span>
          {row.serve_intent === 'out_of_target' && (
            <span className="text-xs text-gray-500 border border-gray-300 rounded px-1.5">
              out of target
            </span>
          )}
        </div>
        <p className="font-serif text-lg leading-snug text-gray-900 mt-2 max-w-2xl">
          {row.job_statement}
        </p>
        <p className="text-sm text-gray-500 mt-2">
          {provenanceLabel[provenanceType]}
          {row.corroborating_signals > 0 ? (
            <>
              {' · '}
              <Link
                to={`/product-intelligence/products/${productId}/job-map?job=${row.job_id}`}
                className="text-teal-700 hover:underline"
              >
                {row.corroborating_signals} linked signal
                {row.corroborating_signals === 1 ? '' : 's'}
              </Link>
            </>
          ) : (
            ' · no linked signals'
          )}
        </p>
      </div>

      {/* Us first: every verdict below is relative to this number, so it has to be
          legible before any of them are. */}
      <div className="border border-gray-200 rounded-lg p-4">
        <div className="flex items-center gap-4">
          <div className="w-32 shrink-0">
            <div className="text-[0.66rem] uppercase tracking-wider font-semibold text-gray-400">
              Us
            </div>
            <div className="flex items-center gap-2 mt-1">
              {tierPips(ourScoreGrounded ? row.our_score : null, true)}
              <span
                className={`font-mono tabular-nums text-sm ${
                  ourScoreGrounded ? 'text-gray-900' : 'text-gray-300'
                }`}
              >
                {ourScoreGrounded ? (row.our_score ?? '—') : '—'}
              </span>
            </div>
          </div>
          <div className="text-sm text-gray-600 flex-1">
            {row.our_score === null ? (
              <>
                Not assessed. Competitor scores below are real, but how we compare cannot be
                stated without our own side scored against this job.
              </>
            ) : !ourScoreGrounded ? (
              <>
                {row.our_score_withheld_reason} Competitor scores below stand on their
                own research.
              </>
            ) : (
              <>
                Confidence {row.our_confidence ?? 'unknown'}
                {data.self_assessment.evidence_based === false && (
                  <>
                    {' '}
                    — and this assessment had no independent evidence to work from, so read it
                    as the product's own claim rather than a measurement.
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-[0.66rem] uppercase tracking-wider font-semibold text-gray-400">
          Competitors
        </div>
        {row.competitors.map((cell) => {
          const col = byId.get(cell.competitor_id);
          const verdictShown = cell.verdict_shown !== false;
          const verdict = (cell.human_position ?? cell.system_position) ?? 'unknown';
          return (
            <div
              key={cell.competitor_id}
              className="border border-gray-200 rounded-lg p-4 flex items-start gap-4 flex-wrap"
            >
              <div className="w-40 shrink-0">
                <div className="font-medium text-sm text-gray-900">{col?.competitor_name}</div>
                <div
                  className={`text-xs ${col?.stale ? 'text-amber-700' : 'text-gray-400'}`}
                >
                  {col?.audited
                    ? `${col.stale ? '⚠ ' : ''}audited ${col.audit_age_days}d ago`
                    : 'not audited'}
                </div>
              </div>

              {cell.assessed ? (
                <>
                  <div className="flex items-center gap-2 w-28 shrink-0">
                    {tierPips(cell.competitor_score)}
                    <span className="font-mono tabular-nums text-sm text-gray-900">
                      {cell.competitor_score ?? '—'}
                    </span>
                  </div>
                  <div className="flex flex-col gap-1 items-start">
                    <span
                      className={`text-[0.68rem] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded border ${
                        verdictShown ? POSITION_STYLES[verdict] : POSITION_STYLES.unknown
                      }`}
                    >
                      {verdictShown ? verdict : 'No verdict'}
                    </span>
                    {cell.human_position && (
                      <span className="text-xs text-teal-700 font-semibold">your verdict</span>
                    )}
                    {cell.review_stale && (
                      <span className="text-xs text-amber-700">review out of date</span>
                    )}
                  </div>
                  <div className="text-sm text-gray-600 flex-1 min-w-[14rem]">
                    {!verdictShown && cell.verdict_withheld_reason}
                    {verdictShown && cell.review_note && (
                      <>
                        <b className="text-gray-900">Your note:</b> {cell.review_note}
                      </>
                    )}
                  </div>
                  <Link
                    to={`/product-intelligence/products/${productId}/intelligence?tab=competitor-reports`}
                    className="text-sm text-teal-700 hover:underline shrink-0"
                  >
                    Full report &rarr;
                  </Link>
                </>
              ) : (
                <div className="text-sm text-gray-400 flex-1">
                  No audit yet, so nothing is known about how they serve this job.
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
    </>
  );
}
