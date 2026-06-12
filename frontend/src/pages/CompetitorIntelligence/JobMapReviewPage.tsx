/**
 * JobMapReviewPage
 *
 * Two-step flow for reviewing LLM-generated job map changes before committing:
 *   Step 1 — Compare & Select: side-by-side table of old vs new, PM picks per row
 *   Step 2 — Verify & Edit: full resulting map with inline edit before applying
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Navigation from '../../components/Navigation';
import {
  applyPendingJobMap,
  discardPendingJobMap,
  getJobMapComparison,
} from '../../services/api';
import type { JobMapComparison, JobMapJobEntry, JobMapPair } from '../../types';

const BULLET = '• ';

function toBulletText(items: string[]): string {
  return items.map((t) => `${BULLET}${t}`).join('\n');
}

function fromBulletText(text: string): string[] {
  return text
    .split('\n')
    .map((t) => t.replace(/^[•]\s*/, '').trim())
    .filter((t) => t.length > 0);
}

const IMPORTANCE_OPTIONS = ['critical', 'high', 'medium', 'low'] as const;
type Importance = typeof IMPORTANCE_OPTIONS[number];

const IMPORTANCE_CLASSES: Record<Importance, string> = {
  critical: 'bg-red-100 text-red-800 border-red-300',
  high: 'bg-orange-100 text-orange-800 border-orange-300',
  medium: 'bg-blue-100 text-blue-800 border-blue-300',
  low: 'bg-gray-100 text-gray-700 border-gray-300',
};

function changeBadge(type: JobMapPair['change_type']) {
  if (type === 'modified') return <span className="ml-2 text-xs font-medium text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded">Modified ●</span>;
  if (type === 'new') return <span className="ml-2 text-xs font-medium text-green-700 bg-green-100 px-1.5 py-0.5 rounded">New ✦</span>;
  if (type === 'removed') return <span className="ml-2 text-xs font-medium text-red-700 bg-red-100 px-1.5 py-0.5 rounded">Removed ✕</span>;
  return null;
}

function JobSummary({ job, muted }: { job: JobMapJobEntry; muted?: boolean }) {
  const cls = muted ? 'text-gray-400' : 'text-gray-800';
  const impCls = IMPORTANCE_CLASSES[job.importance as Importance] ?? IMPORTANCE_CLASSES.medium;
  return (
    <div className={`text-xs ${cls}`}>
      <div className="flex items-center gap-1.5 mb-1">
        <span className="font-mono bg-gray-100 px-1 py-0.5 rounded text-gray-500">{job.job_id_key}</span>
        <span className={`px-1.5 py-0.5 rounded border text-xs ${impCls}`}>{job.importance}</span>
      </div>
      <p className="text-sm leading-snug">{job.statement}</p>
      {job.desired_outcomes.length > 0 && (
        <ul className="mt-1 space-y-0.5 list-disc list-inside text-xs text-gray-500">
          {job.desired_outcomes.slice(0, 3).map((o, i) => <li key={i}>{o}</li>)}
          {job.desired_outcomes.length > 3 && <li className="text-gray-400">+{job.desired_outcomes.length - 3} more</li>}
        </ul>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Step 1: Compare & Select
// ─────────────────────────────────────────────────────────────────

function CompareStep({
  pairs,
  selections,
  onSelect,
  onNext,
  onDiscard,
  discarding,
}: {
  pairs: JobMapPair[];
  selections: Record<string, 'old' | 'new' | 'drop'>;
  onSelect: (id: string, choice: 'old' | 'new' | 'drop') => void;
  onNext: () => void;
  onDiscard: () => void;
  discarding: boolean;
}) {
  const actionable = pairs.filter(p => p.change_type !== 'unchanged');
  const unchangedCount = pairs.length - actionable.length;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Compare Changes</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Select which version to keep for each need. Unchanged needs are accepted automatically.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onDiscard}
            disabled={discarding}
            className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
          >
            {discarding ? 'Discarding…' : 'Discard pending'}
          </button>
          <button
            type="button"
            onClick={onNext}
            className="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700"
          >
            Verify New Job Map →
          </button>
        </div>
      </div>

      <div className="border border-gray-200 rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="text-left px-4 py-2 w-5/12">Your version (current)</th>
              <th className="text-left px-4 py-2 w-5/12">Generated version</th>
              <th className="text-left px-4 py-2 w-2/12">Keep</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {actionable.map(pair => {
              const sel = selections[pair.id] ?? pair.default_selection;
              return (
                <tr key={pair.id} className="align-top">
                  <td className="px-4 py-3">
                    {pair.old ? (
                      <div className={sel === 'old' ? '' : 'opacity-50'}>
                        <JobSummary job={pair.old} />
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400 italic">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {pair.new ? (
                      <div className={sel === 'new' ? '' : 'opacity-50'}>
                        <div className="flex items-center">
                          <JobSummary job={pair.new} />
                          {changeBadge(pair.change_type)}
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center">
                        <span className="text-xs text-gray-400 italic">—</span>
                        {changeBadge(pair.change_type)}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1.5">
                      {pair.old && (
                        <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                          <input
                            type="radio"
                            name={pair.id}
                            checked={sel === 'old'}
                            onChange={() => onSelect(pair.id, 'old')}
                          />
                          Yours
                        </label>
                      )}
                      {pair.new && (
                        <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                          <input
                            type="radio"
                            name={pair.id}
                            checked={sel === 'new'}
                            onChange={() => onSelect(pair.id, 'new')}
                          />
                          {pair.old ? 'New' : 'Keep'}
                        </label>
                      )}
                      {pair.change_type === 'removed' && (
                        <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                          <input
                            type="radio"
                            name={pair.id}
                            checked={sel === 'drop'}
                            onChange={() => onSelect(pair.id, 'drop')}
                          />
                          Drop
                        </label>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {unchangedCount > 0 && (
        <p className="mt-3 text-xs text-gray-400 text-center">
          {unchangedCount} unchanged need{unchangedCount !== 1 ? 's' : ''} accepted automatically
        </p>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Step 2: Verify & Edit
// ─────────────────────────────────────────────────────────────────

interface FinalJob {
  pairId: string;
  choice: 'old' | 'new' | 'drop';
  oldJobIdKey?: string;
  job: JobMapJobEntry;
  source: 'unchanged' | 'old' | 'new';
  // edited overrides
  statement: string;
  outcomesText: string;
  importance: string;
  editing: boolean;
}

function VerifyStep({
  jobs,
  onUpdateJob,
  onRemoveJob,
  onApply,
  onBack,
  onDiscard,
  applying,
  discarding,
}: {
  jobs: FinalJob[];
  onUpdateJob: (pairId: string, updates: Partial<Pick<FinalJob, 'statement' | 'outcomesText' | 'importance' | 'editing'>>) => void;
  onRemoveJob: (pairId: string) => void;
  onApply: () => void;
  onBack: () => void;
  onDiscard: () => void;
  applying: boolean;
  discarding: boolean;
}) {
  const sourceBadge = (source: FinalJob['source']) => {
    if (source === 'unchanged') return <span className="text-xs text-gray-400">[unchanged]</span>;
    if (source === 'old') return <span className="text-xs text-amber-600">[your version]</span>;
    return <span className="text-xs text-green-600">[new]</span>;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Verify New Job Map</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            This is your resulting need map. Edit any statement before committing.
          </p>
        </div>
        <div className="flex gap-3">
          <button type="button" onClick={onBack} className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900">
            ← Back to comparison
          </button>
          <button
            type="button"
            onClick={onDiscard}
            disabled={discarding || applying}
            className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
          >
            Discard pending
          </button>
          <button
            type="button"
            onClick={onApply}
            disabled={applying || discarding}
            className="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            {applying && <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            {applying ? 'Applying…' : 'Apply Job Map'}
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {jobs.map(fj => (
          <div key={fj.pairId} className="bg-white border border-gray-200 rounded-lg p-4">
            {fj.editing ? (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Statement</label>
                  <textarea
                    value={fj.statement}
                    onChange={e => onUpdateJob(fj.pairId, { statement: e.target.value })}
                    rows={3}
                    placeholder="When [situation], I want to [action], so I can [outcome]"
                    className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Desired outcomes (one per line)</label>
                  <textarea
                    value={fj.outcomesText}
                    onChange={e => onUpdateJob(fj.pairId, { outcomesText: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Importance</label>
                  <div className="flex gap-2">
                    {IMPORTANCE_OPTIONS.map(imp => (
                      <button
                        key={imp}
                        type="button"
                        onClick={() => onUpdateJob(fj.pairId, { importance: imp })}
                        className={`text-xs px-3 py-1 rounded-full border transition ${
                          fj.importance === imp
                            ? `${IMPORTANCE_CLASSES[imp]} ring-2 ring-offset-1 ring-blue-500`
                            : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        {imp.charAt(0).toUpperCase() + imp.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => onUpdateJob(fj.pairId, { editing: false })}
                  className="text-xs text-blue-600 hover:text-blue-800"
                >
                  Done editing
                </button>
              </div>
            ) : (
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-mono text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">{fj.job.job_id_key}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${IMPORTANCE_CLASSES[fj.importance as Importance] ?? ''}`}>
                      {fj.importance}
                    </span>
                    {sourceBadge(fj.source)}
                  </div>
                  <p className="text-sm text-gray-800">{fj.statement}</p>
                  {fromBulletText(fj.outcomesText).length > 0 && (
                    <ul className="mt-1 list-disc list-inside text-xs text-gray-500 space-y-0.5">
                      {fromBulletText(fj.outcomesText).map((o, i) => <li key={i}>{o}</li>)}
                    </ul>
                  )}
                </div>
                <div className="flex flex-col gap-1.5 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => onUpdateJob(fj.pairId, { editing: true })}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Edit
                  </button>
                  {jobs.length > 1 && (
                    <button
                      type="button"
                      onClick={() => onRemoveJob(fj.pairId)}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────

export default function JobMapReviewPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [comparison, setComparison] = useState<JobMapComparison | null>(null);
  const [selections, setSelections] = useState<Record<string, 'old' | 'new' | 'drop'>>({});
  const [step, setStep] = useState<'compare' | 'verify'>('compare');
  const [finalJobs, setFinalJobs] = useState<FinalJob[]>([]);
  const [applying, setApplying] = useState(false);
  const [discarding, setDiscarding] = useState(false);

  const numProductId = productId ? parseInt(productId, 10) : NaN;

  useEffect(() => {
    if (!Number.isFinite(numProductId)) return;
    getJobMapComparison(numProductId)
      .then(data => {
        setComparison(data);
        const defaults: Record<string, 'old' | 'new' | 'drop'> = {};
        data.pairs.forEach(p => { defaults[p.id] = p.default_selection; });
        setSelections(defaults);
      })
      .catch(e => setError(e?.message ?? 'Failed to load comparison.'))
      .finally(() => setLoading(false));
  }, [numProductId]);

  const handleSelect = useCallback((id: string, choice: 'old' | 'new' | 'drop') => {
    setSelections(prev => ({ ...prev, [id]: choice }));
  }, []);

  const buildFinalJobs = useCallback(() => {
    if (!comparison) return;
    const jobs: FinalJob[] = [];
    comparison.pairs.forEach(pair => {
      const choice = selections[pair.id] ?? pair.default_selection;
      if (choice === 'drop') return;

      // Unchanged pairs always keep the existing row — never re-insert with the same key.
      const effectiveChoice: 'old' | 'new' | 'drop' =
        pair.change_type === 'unchanged' ? 'old' : choice;

      const job = effectiveChoice === 'old' ? pair.old : pair.new;
      if (!job) return;

      const source: FinalJob['source'] =
        pair.change_type === 'unchanged' ? 'unchanged' :
        effectiveChoice === 'old' ? 'old' : 'new';

      jobs.push({
        pairId: pair.id,
        choice: effectiveChoice,
        oldJobIdKey: pair.old?.job_id_key,
        job,
        source,
        statement: job.statement,
        outcomesText: toBulletText(job.desired_outcomes),
        importance: job.importance,
        editing: false,
      });
    });
    // Deduplicate by job_id_key — keep the first (matched/kept) entry, drop unmatched "new"
    // entries with the same key. This handles cases where the comparison returns both a
    // matched pair and a separate "new" pair that happen to share the same key.
    const seenKeys = new Set<string>();
    const deduped = jobs.filter(fj => {
      if (seenKeys.has(fj.job.job_id_key)) return false;
      seenKeys.add(fj.job.job_id_key);
      return true;
    });

    setFinalJobs(deduped);
    setStep('verify');
  }, [comparison, selections]);

  const handleUpdateJob = useCallback((pairId: string, updates: Partial<FinalJob>) => {
    setFinalJobs(prev => prev.map(fj => fj.pairId === pairId ? { ...fj, ...updates } : fj));
  }, []);

  const handleRemoveJob = useCallback((pairId: string) => {
    setFinalJobs(prev => prev.filter(fj => fj.pairId !== pairId));
  }, []);

  const handleApply = async () => {
    setApplying(true);
    try {
      const payloadSelections = finalJobs.map(fj => {
        const desiredOutcomes = fromBulletText(fj.outcomesText);
        const wasEdited =
          fj.statement !== fj.job.statement ||
          fj.importance !== fj.job.importance ||
          desiredOutcomes.join('|') !== fj.job.desired_outcomes.join('|');
        // If the PM edited a kept-old job, treat it as 'new' so the backend
        // deletes-and-reinserts with the edited content. Pure 'old' choices
        // are left untouched (no DB write needed).
        const effectiveChoice = fj.choice === 'old' && wasEdited ? 'new' : fj.choice;
        return {
          pair_id: fj.pairId,
          choice: effectiveChoice,
          old_job_id_key: fj.oldJobIdKey ?? fj.job.job_id_key,
          new_job_data: effectiveChoice === 'new' ? fj.job : undefined,
          statement: fj.statement,
          desired_outcomes: desiredOutcomes,
          importance: fj.importance,
        };
      });
      // Add dropped pairs: from step-1 explicit drops, plus jobs removed in step-2 verify
      const includedPairIds = new Set(finalJobs.map(fj => fj.pairId));
      comparison?.pairs.forEach(pair => {
        if (includedPairIds.has(pair.id)) return; // already in payload
        // Either explicitly dropped in step 1, or removed via "Remove" in step 2
        if (pair.old?.job_id_key) {
          payloadSelections.push({
            pair_id: pair.id,
            choice: 'drop',
            old_job_id_key: pair.old.job_id_key,
            new_job_data: undefined,
            statement: '',
            desired_outcomes: [],
            importance: 'medium',
          });
        }
      });
      await applyPendingJobMap(numProductId, payloadSelections);
      navigate(`/product-intelligence/products/${productId}/job-map`);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to apply job map.');
      setApplying(false);
    }
  };

  const handleDiscard = async () => {
    setDiscarding(true);
    try {
      await discardPendingJobMap(numProductId);
      navigate(`/product-intelligence/products/${productId}/job-map`);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to discard.');
      setDiscarding(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="mb-6">
          <Link
            to={`/product-intelligence/products/${productId}/job-map`}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            ← Back to Need Map
          </Link>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{error}</div>
        )}

        {loading && (
          <div className="flex justify-center items-center h-40">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
          </div>
        )}

        {!loading && comparison && step === 'compare' && (
          <CompareStep
            pairs={comparison.pairs}
            selections={selections}
            onSelect={handleSelect}
            onNext={buildFinalJobs}
            onDiscard={handleDiscard}
            discarding={discarding}
          />
        )}

        {!loading && step === 'verify' && (
          <VerifyStep
            jobs={finalJobs}
            onUpdateJob={handleUpdateJob}
            onRemoveJob={handleRemoveJob}
            onApply={handleApply}
            onBack={() => setStep('compare')}
            onDiscard={handleDiscard}
            applying={applying}
            discarding={discarding}
          />
        )}
      </div>
    </div>
  );
}
