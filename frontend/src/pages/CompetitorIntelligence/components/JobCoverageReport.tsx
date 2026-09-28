import { useState } from 'react';
import { Link } from 'react-router-dom';
import type {
  FunctionalReportChanges,
  JobAssessment,
  JobPosition,
  UnmappedCapability,
} from '../../../types';

/**
 * Per-competitor job report — how well one competitor serves each job in the map.
 *
 * Replaces the feature comparison table. Features still appear, but only inside a job
 * and split by whose they are: they are supporting evidence for a verdict, never the
 * organising unit.
 */

interface Props {
  productId: number;
  competitorName: string;
  reportVersion: number;
  generatedAt: string;
  positioning: string | null;
  targetCustomer: string | null;
  jobAssessments: JobAssessment[];
  unmappedCapabilities: UnmappedCapability[];
  changes: FunctionalReportChanges | null;
  selfAssessmentVersion: number | null;
  selfAssessedAt: string | null;
  mapHealth: { total_jobs: number; jobs_with_independent_source: number } | null;
  /** Server decides; the UI must not re-derive it. See verdict_grounding. */
  verdictGrounding: Record<
    string,
    { shown: boolean; reason: string | null; grounded_by_human?: boolean }
  >;
  corroboratingSignals: Record<string, number>;
  onReview: (jobId: string, action: 'agree' | 'override' | 'clear', position?: JobPosition) => void;
  onExport: () => void;
  exporting?: boolean;
}

const POSITION_STYLES: Record<string, string> = {
  advantage: 'bg-green-50 text-green-800 border-green-200',
  gap: 'bg-orange-50 text-orange-800 border-orange-200',
  parity: 'bg-gray-100 text-gray-700 border-gray-200',
  differentiator: 'bg-teal-50 text-teal-800 border-teal-200',
  unknown: 'bg-transparent text-gray-500 border-gray-300 border-dashed',
};

const IMPORTANCE_STYLES: Record<string, string> = {
  critical: 'text-orange-700',
  high: 'text-gray-600',
  medium: 'text-gray-500',
  low: 'text-gray-400',
};

/** Rubric bands, not raw scores — a 7 becoming an 8 is model noise, not movement. */
function scoreToTier(score: number | null | undefined): number | null {
  if (score === null || score === undefined) return null;
  if (score <= 0 || score > 10) return null;
  return Math.floor((score + 1) / 2);
}

function TierPips({ score, mine }: { score: number | null; mine?: boolean }) {
  const tier = scoreToTier(score);
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex gap-0.5" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((i) => {
          if (tier === null) {
            return <span key={i} className="w-1.5 h-4 rounded-sm border border-dashed border-gray-400 bg-gray-50" />;
          }
          const on = i <= tier;
          const fill = on ? (mine ? 'bg-teal-700' : 'bg-gray-500') : 'bg-gray-200';
          return <span key={i} className={`w-1.5 h-4 rounded-sm ${fill}`} />;
        })}
      </div>
      <span className={`text-xs tabular-nums ${tier === null ? 'text-gray-400' : 'text-gray-600'}`}>
        {tier === null ? '—' : score}
      </span>
    </div>
  );
}

function ReviewState({ job }: { job: JobAssessment }) {
  if (job.review_stale) {
    return <span className="text-xs text-amber-700">review out of date</span>;
  }
  if (job.human_position) {
    return <span className="text-xs font-semibold text-teal-700">overridden</span>;
  }
  if (job.reviewed_at) {
    return <span className="text-xs text-green-700">&#10003; agreed</span>;
  }
  // Unreviewed is a normal resting state, not a warning — a PM may accept every
  // verdict without looking at any of them.
  return <span className="text-xs text-gray-400">not reviewed</span>;
}

export default function JobCoverageReport({
  productId,
  competitorName,
  reportVersion,
  generatedAt,
  positioning,
  targetCustomer,
  jobAssessments,
  unmappedCapabilities,
  changes,
  selfAssessmentVersion,
  selfAssessedAt,
  mapHealth,
  verdictGrounding,
  corroboratingSignals,
  onReview,
  onExport,
  exporting,
}: Props) {
  const [openJobs, setOpenJobs] = useState<Set<string>>(new Set());
  const [overriding, setOverriding] = useState<string | null>(null);

  const toggle = (jobId: string) =>
    setOpenJobs((prev) => {
      const next = new Set(prev);
      next.has(jobId) ? next.delete(jobId) : next.add(jobId);
      return next;
    });

  const changedJobs = new Map(
    (changes?.job_position_changes ?? []).map((c) => [c.job_id, c])
  );

  const productDerivedOnly =
    mapHealth && mapHealth.total_jobs > 0
      ? mapHealth.total_jobs - mapHealth.jobs_with_independent_source
      : 0;

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex justify-between items-start gap-6 flex-wrap">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">{competitorName}</h2>
          <div className="text-sm text-gray-500 flex gap-2 flex-wrap items-center mt-1">
            <span className="tabular-nums">v{reportVersion}</span>
            <span className="text-gray-300">·</span>
            <span>audited {generatedAt}</span>
            <span className="text-gray-300">·</span>
            <span>{jobAssessments.length} jobs assessed</span>
            {selfAssessmentVersion !== null && (
              <>
                <span className="text-gray-300">·</span>
                <span>
                  self-assessment <span className="tabular-nums">v{selfAssessmentVersion}</span>
                  {selfAssessedAt ? `, ${selfAssessedAt}` : ''}
                </span>
              </>
            )}
          </div>
          {changedJobs.size > 0 && (
            <div className="mt-2 flex items-center gap-2 text-sm text-teal-700 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-600" />
              Competitor scores changed since v{reportVersion - 1} — marked below
            </div>
          )}
          {positioning && (
            <p className="text-sm text-gray-600 mt-2 max-w-2xl">
              {positioning}
              {targetCustomer ? ` Target: ${targetCustomer}.` : ''}
            </p>
          )}
        </div>
        <button
          onClick={onExport}
          disabled={exporting}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          {exporting ? 'Exporting...' : 'Export .md'}
        </button>
      </div>

      {/* Map health. One line by default — this sits above every competitor report, and a
          four-line explanation repeated on each one stops being read. The reasoning is a
          click away for the first time someone meets it. */}
      {productDerivedOnly > 0 && mapHealth && (
        <details className="bg-amber-50 rounded-lg px-3 py-2 text-sm text-gray-800">
          <summary className="cursor-pointer list-none flex items-center gap-2">
            <span className="font-semibold text-amber-800">!</span>
            <b>
              {productDerivedOnly} of {mapHealth.total_jobs} jobs were written from your product
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

      {/* Scorecard */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="hidden md:grid grid-cols-[1fr_78px_78px_140px] gap-4 px-4 py-2 bg-gray-50 border-b border-gray-200 text-[0.68rem] font-semibold uppercase tracking-wider text-gray-400">
          <span>Job</span>
          <span className="text-center">Us</span>
          <span className="text-center">Them</span>
          <span>Verdict</span>
        </div>

        {jobAssessments.map((job) => {
          const open = openJobs.has(job.job_id);
          const change = changedJobs.get(job.job_id);
          const grounding = verdictGrounding[job.job_id];
          // Withholding applies to the DERIVED verdict, which depends on our ungrounded
          // score. A PM's override is an independent claim that owes nothing to that
          // score, so it survives — and must stay editable, or a withheld job would trap
          // an override with no way to clear it.
          const systemShown = grounding?.shown !== false;
          const verdictShown = systemShown || !!job.human_position;
          const displayed = job.human_position ?? job.system_position ?? 'unknown';
          const signalCount = corroboratingSignals[job.job_id] ?? 0;

          return (
            <div key={job.job_id} className="border-b border-gray-200 last:border-b-0">
              <button
                onClick={() => toggle(job.job_id)}
                aria-expanded={open}
                className="w-full grid grid-cols-1 md:grid-cols-[1fr_78px_78px_140px] gap-4 items-center px-4 py-3 text-left hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-600"
              >
                <div>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-gray-400 text-[0.6rem] transition-transform ${open ? 'rotate-90' : ''}`}>
                      &#9654;
                    </span>
                    <span className="font-mono text-sm font-semibold text-teal-700">{job.job_id}</span>
                    {change && (
                      <span
                        className={`text-[0.62rem] uppercase tracking-wider font-bold rounded px-1.5 py-0.5 ${
                          change.evidence_changed
                            ? 'text-teal-700 bg-teal-50'
                            : 'text-amber-700 bg-amber-50'
                        }`}
                      >
                        changed
                      </span>
                    )}
                  </div>
                  <p className="font-serif text-[0.925rem] leading-snug text-gray-900 max-w-xl">
                    {job.job_statement}
                  </p>
                  <div className="flex gap-2 flex-wrap mt-1.5 items-center">
                    <span
                      className={`text-[0.66rem] uppercase tracking-wide font-semibold ${
                        IMPORTANCE_STYLES[job.importance] ?? 'text-gray-400'
                      }`}
                    >
                      {job.importance}
                    </span>
                    {signalCount > 0 && (
                      // A link rather than a tooltip: the signals are the reason to
                      // trust this job at all, and the job map already lists them per
                      // job. Opening there beats duplicating the list here.
                      <Link
                        to={`/product-intelligence/products/${productId}/job-map?job=${job.job_id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="text-[0.66rem] text-teal-700 border border-teal-600 rounded px-1.5 hover:bg-teal-50"
                      >
                        {signalCount} linked signal{signalCount === 1 ? '' : 's'}
                      </Link>
                    )}
                  </div>
                </div>

                <TierPips score={verdictShown ? job.our_score : null} mine />
                <TierPips score={job.competitor_score} />

                <div className="flex flex-col gap-1 items-start">
                  <span
                    className={`text-[0.68rem] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded border ${
                      verdictShown ? POSITION_STYLES[displayed] : POSITION_STYLES.unknown
                    }`}
                  >
                    {verdictShown ? displayed : 'No verdict'}
                  </span>
                  {verdictShown ? (
                    <ReviewState job={job} />
                  ) : (
                    // Not "unassessed" — withholding requires a low-confidence score, so
                    // our side IS assessed, just not on anything independent.
                    <span className="text-xs text-gray-400">our score ungrounded</span>
                  )}
                </div>
              </button>

              {open && (
                <div className="px-4 pb-5 border-t border-dashed border-gray-200 -mt-px">
                  <div className="pt-4 space-y-4">
                    {grounding?.grounded_by_human && (
                      // The suppression note vanishing is not enough: without this the
                      // PM cannot tell their own judgement is what is holding the row
                      // up, or that it did more than fill one cell.
                      <div className="text-sm text-gray-600 bg-teal-50 border-l-2 border-teal-600 rounded-r p-2.5 max-w-2xl">
                        <b className="text-gray-900">
                          This verdict rests on your judgement, not on our scores.
                        </b>{' '}
                        Our own score for this job came only from the product
                        description, so nothing could be computed. Your call settles the
                        comparison for every competitor on this job, and counts as
                        support for the job itself in map health.
                      </div>
                    )}

                    {!systemShown && grounding?.reason && (
                      <div className="text-sm text-gray-600 bg-gray-50 border border-dashed border-gray-300 rounded p-2.5 max-w-2xl">
                        <b className="text-gray-900">
                          No verdict, because our own score for this job has nothing independent
                          behind it.
                        </b>{' '}
                        {grounding.reason} {competitorName}'s side is still reported.
                      </div>
                    )}

                    {change && (
                      <div
                        className={`text-sm text-gray-600 bg-gray-50 rounded-r p-2.5 border-l-2 ${
                          change.evidence_changed ? 'border-teal-600' : 'border-amber-500'
                        }`}
                      >
                        <b className="text-gray-900">
                          Their score moved{' '}
                          <span className="font-mono">
                            {change.old_scores.theirs} &rarr; {change.new_scores.theirs}
                          </span>{' '}
                          since the last audit
                        </b>
                        {change.evidence_changed ? (
                          <>
                            , backed by {change.new_evidence_ids.length} new source
                            {change.new_evidence_ids.length === 1 ? '' : 's'}.
                          </>
                        ) : (
                          <>
                            , with no new sources. Nothing found this time that was not available
                            last time, so this is as likely to be model variance as a real change.
                          </>
                        )}
                      </div>
                    )}

                    {job.score_rationale && (
                      <p className="text-sm text-gray-600 max-w-3xl">
                        <b className="text-gray-900">
                          {verdictShown ? 'Why:' : `Why they score ${job.competitor_score}:`}
                        </b>{' '}
                        {job.score_rationale}
                      </p>
                    )}

                    {job.features.length > 0 && (
                      <div className="grid md:grid-cols-2 gap-6">
                        {(['theirs', 'ours'] as const).map((whose) => {
                          const feats = job.features.filter((f) => f.whose === whose);
                          if (!feats.length) return null;
                          return (
                            <div key={whose}>
                              <div className="text-[0.66rem] uppercase tracking-wider font-semibold text-gray-400 mb-1.5">
                                {whose} ({feats.length})
                              </div>
                              <ul className="space-y-1">
                                {feats.map((f, i) => (
                                  <li key={i} className="text-sm text-gray-600 flex gap-2">
                                    <span
                                      className={`mt-1.5 w-1 h-1 rounded-full shrink-0 ${
                                        f.position === 'gap'
                                          ? 'bg-orange-600'
                                          : f.position === 'advantage'
                                            ? 'bg-green-700'
                                            : 'bg-gray-400'
                                      }`}
                                    />
                                    <span>{f.feature_name}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {job.outcome_coverage.length > 0 && (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm border-collapse">
                          <thead>
                            <tr className="text-[0.66rem] uppercase tracking-wider text-gray-400">
                              <th className="text-left font-semibold pb-1.5 border-b border-gray-200">
                                Desired outcome
                              </th>
                              <th className="text-left font-semibold pb-1.5 border-b border-gray-200 w-24">
                                Us
                              </th>
                              <th className="text-left font-semibold pb-1.5 border-b border-gray-200 w-24">
                                Them
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {job.outcome_coverage.map((oc, i) => (
                              <tr key={i}>
                                <td className="py-1.5 text-gray-900 border-b border-gray-100">
                                  {oc.desired_outcome}
                                </td>
                                <td className="py-1.5 text-gray-600 border-b border-gray-100">
                                  {oc.our_coverage}
                                </td>
                                <td className="py-1.5 text-gray-600 border-b border-gray-100">
                                  {oc.competitor_coverage}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {job.review_note && (
                      <div className="text-sm text-gray-600 bg-gray-50 border-l-2 border-teal-600 rounded-r p-2.5">
                        <b className="text-gray-900">
                          Your override — {job.human_position}.
                        </b>{' '}
                        {job.review_note}
                      </div>
                    )}

                    {job.review_stale && (
                      <div className="text-sm text-gray-600 bg-amber-50 border-l-2 border-amber-500 rounded-r p-2.5">
                        <b className="text-gray-900">Your review no longer applies.</b> The job read
                        &ldquo;{job.reviewed_job_statement}&rdquo; when you reviewed it. It has been
                        reworded since, so the judgement may no longer hold.
                      </div>
                    )}

                    {(
                      <div className="flex items-center gap-3 flex-wrap pt-3 border-t border-gray-200">
                        <div className="text-sm text-gray-600 flex-1 min-w-[15rem]">
                          {verdictShown ? (
                            <>
                              System says <b className="text-gray-900">{job.system_position}</b>
                              {job.confidence ? `, confidence ${job.confidence}` : ''}.
                            </>
                          ) : (
                            // Withheld jobs must still offer an override: the PM's
                            // judgement is what would ground this, so hiding the action
                            // leaves the job permanently unresolvable.
                            <>
                              No verdict can be computed. Your judgement would settle it
                              — and counts as evidence for this job.
                            </>
                          )}
                          {job.human_position && (
                            <>
                              {' '}
                              Your verdict, <b className="text-gray-900">{job.human_position}</b>, is
                              shown everywhere.
                            </>
                          )}
                        </div>

                        {overriding === job.job_id ? (
                          // Overriding means choosing a verdict, so the choice has to be
                          // offered. Previously "Override" re-submitted the system's own
                          // position, which changed nothing.
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm text-gray-600">Set to:</span>
                            {(['advantage', 'gap', 'parity', 'differentiator'] as const)
                              .filter((p) => p !== job.human_position)
                              .map((p) => (
                                <button
                                  key={p}
                                  onClick={() => {
                                    onReview(job.job_id, 'override', p);
                                    setOverriding(null);
                                  }}
                                  className={`px-2.5 py-1 text-xs uppercase tracking-wider font-bold rounded border ${POSITION_STYLES[p]}`}
                                >
                                  {p}
                                </button>
                              ))}
                            <button
                              onClick={() => setOverriding(null)}
                              className="px-2 py-1 text-sm text-gray-500 hover:text-gray-700"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <>
                            {/* Every action is named for what it does. "Change review"
                                previously submitted an agree, which silently discarded an
                                override and its note. */}
                            {!job.reviewed_at && verdictShown && (
                              <button
                                onClick={() => onReview(job.job_id, 'agree')}
                                className="px-3 py-1.5 text-sm bg-teal-700 text-white rounded-lg hover:bg-teal-800 font-medium"
                              >
                                Agree
                              </button>
                            )}
                            {job.human_position && (
                              <button
                                onClick={() => onReview(job.job_id, 'agree')}
                                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
                              >
                                Drop override, agree with system
                              </button>
                            )}
                            <button
                              onClick={() => setOverriding(job.job_id)}
                              className={
                                verdictShown
                                  ? 'px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50'
                                  : 'px-3 py-1.5 text-sm bg-teal-700 text-white rounded-lg hover:bg-teal-800 font-medium'
                              }
                            >
                              {job.human_position
                                ? 'Change override'
                                : verdictShown
                                  ? 'Override'
                                  : 'Set the verdict'}
                            </button>
                            {job.reviewed_at && (
                              <button
                                onClick={() => onReview(job.job_id, 'clear')}
                                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
                              >
                                Clear review
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Capabilities the map does not cover */}
      {unmappedCapabilities.length > 0 && (
        <div className="border border-gray-200 rounded-lg p-4">
          <h3 className="text-base font-semibold text-gray-900">Outside your job map</h3>
          <p className="text-sm text-gray-600 mt-1 max-w-3xl">
            Things {competitorName} does that no job in your map covers. Each is a candidate for
            extending the map — nothing is added automatically.
          </p>
          <div className="mt-3 space-y-3">
            {unmappedCapabilities.map((cap, i) => (
              <div key={i} className="space-y-1">
                <div className="font-semibold text-sm text-gray-900">{cap.capability}</div>
                {cap.why_unmapped && (
                  <div className="text-sm text-gray-600 max-w-3xl">{cap.why_unmapped}</div>
                )}
                {cap.suggested_job_statement && (
                  <div className="font-serif italic text-sm text-gray-600 border-l-2 border-gray-300 pl-3 max-w-2xl">
                    {cap.suggested_job_statement}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
