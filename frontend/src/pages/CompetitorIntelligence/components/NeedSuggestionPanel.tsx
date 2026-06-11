/**
 * NeedSuggestionPanel
 *
 * Collapsible panel shown above the need list when agents have surfaced
 * unmatched or weakly-matched signals as potential need map candidates.
 *
 * no_match  → "No existing need matched this signal. Add as a new need?"
 * weak_match → "This signal loosely matched [j2]. Confirm or add as new need."
 */

import { useState } from 'react';
import type { JobImportance, NeedSuggestion } from '../../../types';
import { approveNeedSuggestion, dismissNeedSuggestion } from '../../../services/api';

interface NeedSuggestionPanelProps {
  productId: number;
  suggestions: NeedSuggestion[];
  onRefresh: () => void;
}

const SIGNAL_LABELS: Record<string, string> = {
  idea: 'Customer idea',
  evidence: 'Evidence',
  win_loss_theme: 'Win/loss theme',
  support_theme: 'Support theme',
  synthesized_opportunity: 'Synthesis opportunity',
};

const IMPORTANCE_OPTIONS: { value: JobImportance; label: string; classes: string }[] = [
  { value: 'critical', label: 'Critical', classes: 'bg-red-100 text-red-800 border-red-300' },
  { value: 'high', label: 'High', classes: 'bg-orange-100 text-orange-800 border-orange-300' },
  { value: 'medium', label: 'Medium', classes: 'bg-blue-100 text-blue-800 border-blue-300' },
  { value: 'low', label: 'Low', classes: 'bg-gray-100 text-gray-700 border-gray-300' },
];

function SuggestionCard({
  suggestion,
  productId,
  onRefresh,
}: {
  suggestion: NeedSuggestion;
  productId: number;
  onRefresh: () => void;
}) {
  const [addingNew, setAddingNew] = useState(suggestion.match_type === 'no_match');
  const [statement, setStatement] = useState(suggestion.signal_content);
  const [importance, setImportance] = useState<JobImportance>('medium');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = async () => {
    if (!statement.trim()) { setError('Statement is required.'); return; }
    setSaving(true);
    setError(null);
    try {
      await approveNeedSuggestion(productId, suggestion.id, {
        statement: statement.trim(),
        importance,
      });
      onRefresh();
    } catch (err: any) {
      setError(err?.message ?? 'Failed to add need.');
      setSaving(false);
    }
  };

  const handleDismiss = async () => {
    setSaving(true);
    try {
      await dismissNeedSuggestion(productId, suggestion.id);
      onRefresh();
    } catch (err: any) {
      setError(err?.message ?? 'Failed to dismiss.');
      setSaving(false);
    }
  };

  const signalLabel = SIGNAL_LABELS[suggestion.signal_type] ?? suggestion.signal_type;
  const isWeakMatch = suggestion.match_type === 'weak_match';

  return (
    <div className={`border rounded-md p-4 ${isWeakMatch ? 'border-amber-200 bg-amber-50/30' : 'border-blue-200 bg-blue-50/30'}`}>
      {/* Signal source label */}
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${isWeakMatch ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'}`}>
          {isWeakMatch ? 'Weak match' : 'New need candidate'}
        </span>
        <span className="text-xs text-gray-500">{signalLabel}</span>
      </div>

      {/* Signal content */}
      <p className="text-sm text-gray-800 mb-3 line-clamp-3">{suggestion.signal_content}</p>

      {/* Weak match context */}
      {isWeakMatch && suggestion.matched_job_id && !addingNew && (
        <div className="mb-3 p-3 bg-white border border-gray-200 rounded text-sm">
          <div className="text-xs text-gray-500 mb-1">
            Matched to <span className="font-mono">{suggestion.matched_job_id}</span>
            {suggestion.matched_similarity != null && (
              <span> (similarity {(suggestion.matched_similarity * 100).toFixed(0)}%)</span>
            )}
          </div>
          <p className="text-gray-700">{suggestion.matched_job_statement}</p>
        </div>
      )}

      {error && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{error}</div>
      )}

      {/* Add-as-new-need editor */}
      {addingNew && (
        <div className="space-y-3 mb-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Need statement <span className="text-red-500">*</span>
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
            <label className="block text-xs font-medium text-gray-700 mb-1">Importance</label>
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
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        {addingNew ? (
          <>
            <button
              onClick={handleApprove}
              disabled={saving || !statement.trim()}
              className="text-sm px-3 py-1.5 text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Adding…' : 'Add to Need Map'}
            </button>
            {isWeakMatch && (
              <button
                onClick={() => setAddingNew(false)}
                disabled={saving}
                className="text-sm px-3 py-1.5 text-gray-700 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
              >
                Back
              </button>
            )}
            <button
              onClick={handleDismiss}
              disabled={saving}
              className="text-sm px-3 py-1.5 text-gray-500 hover:text-gray-700 disabled:opacity-50"
            >
              Dismiss
            </button>
          </>
        ) : (
          <>
            <button
              onClick={handleDismiss}
              disabled={saving}
              className="text-sm px-3 py-1.5 text-gray-700 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
            >
              {saving ? 'Dismissing…' : `Keep as ${suggestion.matched_job_id}`}
            </button>
            <button
              onClick={() => setAddingNew(true)}
              disabled={saving}
              className="text-sm px-3 py-1.5 text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              Add as new need
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function NeedSuggestionPanel({ productId, suggestions, onRefresh }: NeedSuggestionPanelProps) {
  const [collapsed, setCollapsed] = useState(suggestions.length === 0);

  if (suggestions.length === 0) return null;

  return (
    <section className="bg-white rounded-lg shadow mb-6 overflow-hidden">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-gray-50 transition"
      >
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold text-gray-900">Need Map Suggestions</span>
          <span className="text-xs font-medium bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">
            {suggestions.length}
          </span>
        </div>
        <span className="text-gray-400 text-sm">{collapsed ? '▶ Show' : '▼ Hide'}</span>
      </button>

      {!collapsed && (
        <div className="px-6 pb-6 space-y-4">
          <p className="text-sm text-gray-500">
            Signals that didn't confidently match an existing need. Review and add to the need map or dismiss.
          </p>
          {suggestions.map((s) => (
            <SuggestionCard
              key={s.id}
              suggestion={s}
              productId={productId}
              onRefresh={onRefresh}
            />
          ))}
        </div>
      )}
    </section>
  );
}
