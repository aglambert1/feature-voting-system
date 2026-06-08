/**
 * JobRow
 *
 * Per-job row with view/edit toggle and inline delete confirmation.
 * Importance rendered as a 4-button pill row with color coding.
 */

import { useState } from 'react';
import { differenceInDays, parseISO } from 'date-fns';
import type { JobImportance, JtbdJob, JobUpdateRequest } from '../../../types';

interface JobRowProps {
  job: JtbdJob;
  onSave: (jobIdKey: string, patch: JobUpdateRequest) => Promise<void>;
  onDelete: (jobIdKey: string) => Promise<void>;
}

const IMPORTANCE_OPTIONS: { value: JobImportance; label: string; classes: string }[] = [
  {
    value: 'critical',
    label: 'Critical',
    classes: 'bg-red-100 text-red-800 border-red-300',
  },
  {
    value: 'high',
    label: 'High',
    classes: 'bg-orange-100 text-orange-800 border-orange-300',
  },
  {
    value: 'medium',
    label: 'Medium',
    classes: 'bg-blue-100 text-blue-800 border-blue-300',
  },
  {
    value: 'low',
    label: 'Low',
    classes: 'bg-gray-100 text-gray-700 border-gray-300',
  },
];

function importanceBadge(importance: JobImportance): string {
  return (
    IMPORTANCE_OPTIONS.find((o) => o.value === importance)?.classes ??
    'bg-gray-100 text-gray-700 border-gray-300'
  );
}

function importanceLabel(importance: JobImportance): string {
  return IMPORTANCE_OPTIONS.find((o) => o.value === importance)?.label ?? importance;
}

export default function JobRow({ job, onSave, onDelete }: JobRowProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statement, setStatement] = useState(job.statement);
  const [outcomesText, setOutcomesText] = useState((job.desired_outcomes ?? []).join('\n'));
  const [importance, setImportance] = useState<JobImportance>(job.importance);

  const startEdit = () => {
    setStatement(job.statement);
    setOutcomesText((job.desired_outcomes ?? []).join('\n'));
    setImportance(job.importance);
    setError(null);
    setIsEditing(true);
  };

  const cancelEdit = () => {
    setError(null);
    setIsEditing(false);
  };

  const handleSave = async () => {
    setError(null);
    if (!statement.trim()) {
      setError('Statement is required.');
      return;
    }
    setSaving(true);
    try {
      const desiredOutcomes = outcomesText
        .split('\n')
        .map((o) => o.trim())
        .filter((o) => o.length > 0);
      const patch: JobUpdateRequest = {};
      if (statement.trim() !== job.statement) {
        patch.statement = statement.trim();
      }
      if (
        desiredOutcomes.length !== (job.desired_outcomes ?? []).length ||
        desiredOutcomes.some((o, i) => o !== (job.desired_outcomes ?? [])[i])
      ) {
        patch.desired_outcomes = desiredOutcomes;
      }
      if (importance !== job.importance) {
        patch.importance = importance;
      }

      if (Object.keys(patch).length === 0) {
        // Nothing changed — just close the editor
        setIsEditing(false);
        return;
      }

      await onSave(job.job_id_key, patch);
      setIsEditing(false);
    } catch (err: any) {
      setError(err?.message ?? 'Failed to save job.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setError(null);
    setDeleting(true);
    try {
      await onDelete(job.job_id_key);
      // Parent will re-fetch; this row unmounts.
    } catch (err: any) {
      setError(err?.message ?? 'Failed to delete job.');
      setDeleting(false);
      setConfirmingDelete(false);
    }
  };

  const staleDays = job.updated_at ? differenceInDays(new Date(), parseISO(job.updated_at)) : null;
  const isStale = staleDays !== null && staleDays >= 90;

  return (
    <div className="bg-white border border-gray-200 rounded-md p-4">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0 flex-wrap">
          <span className="text-xs font-mono text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
            {job.job_id_key}
          </span>
          {!isEditing && (
            <span
              className={`text-xs px-2 py-0.5 rounded-full border ${importanceBadge(
                job.importance
              )}`}
            >
              {importanceLabel(job.importance)}
            </span>
          )}
          {!isEditing && (
            <span className="text-xs text-gray-400">
              {job.signal_count > 0 ? `${job.signal_count} signal${job.signal_count === 1 ? '' : 's'}` : 'No signals'}
            </span>
          )}
          {!isEditing && isStale && (
            <span className="text-xs text-amber-600" title={`Last updated ${staleDays} days ago`}>
              ● Stale
            </span>
          )}
        </div>

        {!isEditing && !confirmingDelete && (
          <div className="flex gap-2 flex-shrink-0">
            <button
              onClick={startEdit}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Edit
            </button>
            <button
              onClick={() => setConfirmingDelete(true)}
              className="text-sm text-red-600 hover:text-red-800 font-medium"
            >
              Delete
            </button>
          </div>
        )}

        {!isEditing && confirmingDelete && (
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-xs text-gray-600">Delete this job?</span>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-sm text-white bg-red-600 hover:bg-red-700 px-2 py-1 rounded disabled:opacity-50"
            >
              {deleting ? 'Deleting…' : 'Confirm'}
            </button>
            <button
              onClick={() => setConfirmingDelete(false)}
              disabled={deleting}
              className="text-sm text-gray-700 bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {!isEditing && (
        <>
          <div className="text-gray-900 text-sm mb-2 whitespace-pre-wrap">{job.statement}</div>
          {job.desired_outcomes.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
                Desired outcomes
              </div>
              <ul className="list-disc list-inside text-gray-800 text-sm space-y-0.5">
                {job.desired_outcomes.map((outcome, i) => (
                  <li key={i}>{outcome}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {isEditing && (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Statement <span className="text-red-500">*</span>
            </label>
            <textarea
              value={statement}
              onChange={(e) => setStatement(e.target.value)}
              rows={3}
              placeholder="When [situation], I want to [action], so I can [outcome]"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Desired outcomes{' '}
              <span className="text-xs font-normal text-gray-500">(one per line)</span>
            </label>
            <textarea
              value={outcomesText}
              onChange={(e) => setOutcomesText(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-mono"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Importance</label>
            <div className="flex gap-2">
              {IMPORTANCE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setImportance(opt.value)}
                  disabled={saving}
                  className={`text-xs px-3 py-1 rounded-full border transition ${
                    importance === opt.value
                      ? `${opt.classes} ring-2 ring-offset-1 ring-blue-500`
                      : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-2 justify-end pt-1">
            <button
              onClick={cancelEdit}
              disabled={saving}
              className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !statement.trim()}
              className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
