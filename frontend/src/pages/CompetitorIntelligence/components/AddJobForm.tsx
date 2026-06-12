/**
 * AddJobForm
 *
 * Inline add-job form. `job_id_key` is auto-generated as j{n} (next available
 * index across all jobs) and displayed read-only — POs never edit it.
 */

import { useState } from 'react';
import type { JobCreateRequest, JobImportance, JtbdJob } from '../../../types';

const BULLET = '• ';

function fromBulletText(text: string): string[] {
  return text
    .split('\n')
    .map((t) => t.replace(/^[•]\s*/, '').trim())
    .filter((t) => t.length > 0);
}

function bulletKeyDown(
  e: React.KeyboardEvent<HTMLTextAreaElement>,
  value: string,
  setValue: (v: string) => void
) {
  if (e.key !== 'Enter') return;
  e.preventDefault();
  const el = e.currentTarget;
  const start = el.selectionStart;
  const end = el.selectionEnd;
  const next = `${value.slice(0, start)}\n${BULLET}${value.slice(end)}`;
  setValue(next);
  requestAnimationFrame(() => {
    el.selectionStart = el.selectionEnd = start + 1 + BULLET.length;
  });
}

interface AddJobFormProps {
  existingJobs: JtbdJob[];
  /** When true, the form is rendered expanded; when false, starts collapsed behind a button. */
  alwaysExpanded: boolean;
  onAdd: (body: JobCreateRequest) => Promise<void>;
}

const IMPORTANCE_OPTIONS: { value: JobImportance; label: string; classes: string }[] = [
  { value: 'critical', label: 'Critical', classes: 'bg-red-100 text-red-800 border-red-300' },
  { value: 'high', label: 'High', classes: 'bg-orange-100 text-orange-800 border-orange-300' },
  { value: 'medium', label: 'Medium', classes: 'bg-blue-100 text-blue-800 border-blue-300' },
  { value: 'low', label: 'Low', classes: 'bg-gray-100 text-gray-700 border-gray-300' },
];

/**
 * Compute the next available job_id_key across all existing jobs.
 * Keys that can't be parsed are ignored. Deletions leave gaps on purpose —
 * external references (evidence, ideas) may still cite a removed key.
 */
function nextJobIdKey(existing: JtbdJob[]): string {
  const maxIndex = existing
    .map((j) => {
      const m = j.job_id_key.match(/^j(\d+)$/);
      return m && m[1] ? parseInt(m[1], 10) : 0;
    })
    .reduce((a, b) => Math.max(a, b), 0);
  return `j${maxIndex + 1}`;
}

export default function AddJobForm({ existingJobs, alwaysExpanded, onAdd }: AddJobFormProps) {
  const [isOpen, setIsOpen] = useState(alwaysExpanded);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statement, setStatement] = useState('');
  const [outcomesText, setOutcomesText] = useState('');
  const [importance, setImportance] = useState<JobImportance>('medium');

  const resetForm = () => {
    setStatement('');
    setOutcomesText('');
    setImportance('medium');
    setError(null);
  };

  const handleCancel = () => {
    resetForm();
    if (!alwaysExpanded) setIsOpen(false);
  };

  const handleAdd = async () => {
    setError(null);
    if (!statement.trim()) {
      setError('Statement is required.');
      return;
    }
    setSaving(true);
    try {
      const desiredOutcomes = fromBulletText(outcomesText);
      const body: JobCreateRequest = {
        job_id: nextJobIdKey(existingJobs),
        statement: statement.trim(),
        desired_outcomes: desiredOutcomes,
        importance,
      };
      await onAdd(body);
      resetForm();
      if (!alwaysExpanded) setIsOpen(false);
    } catch (err: any) {
      setError(err?.message ?? 'Failed to add job.');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="w-full text-sm text-blue-600 hover:text-blue-800 font-medium border border-dashed border-gray-300 hover:border-blue-400 rounded-md py-2 transition"
      >
        + Add need
      </button>
    );
  }

  const nextId = nextJobIdKey(existingJobs);

  return (
    <div className="bg-blue-50/40 border border-blue-200 rounded-md p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-mono text-gray-600 bg-white border border-gray-200 px-2 py-0.5 rounded">
          {nextId}
        </span>
        <span className="text-sm font-medium text-gray-700">New customer need</span>
      </div>

      {error && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

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
            <span className="text-xs font-normal text-gray-500">(one per line, optional)</span>
          </label>
          <textarea
            value={outcomesText}
            onChange={(e) => setOutcomesText(e.target.value)}
            onFocus={() => { if (!outcomesText) setOutcomesText(BULLET); }}
            onKeyDown={(e) => bulletKeyDown(e, outcomesText, setOutcomesText)}
            rows={3}
            placeholder={`${BULLET}Reduce time spent on...`}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
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
            onClick={handleCancel}
            disabled={saving}
            className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleAdd}
            disabled={saving || !statement.trim()}
            className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Adding…' : 'Add need'}
          </button>
        </div>
      </div>
    </div>
  );
}
