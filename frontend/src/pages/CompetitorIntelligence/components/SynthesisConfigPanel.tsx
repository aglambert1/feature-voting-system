/**
 * SynthesisConfigPanel
 *
 * Read/edit the unified SynthesisConfig: source types, auto-idea generation,
 * and the idea-priority threshold. Owns its own fetch + save and re-fetches
 * after a successful save.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getSynthesisConfig,
  putSynthesisConfig,
} from '../../../services/api';
import type {
  SynthesisConfigData,
  SynthesisSourceType,
} from '../../../types';

const ALL_SOURCES: { type: SynthesisSourceType; label: string; description: string }[] = [
  { type: 'competitive', label: 'Competitive', description: 'Competitor functional audits' },
  { type: 'customer', label: 'Customer', description: 'Submitted ideas and votes' },
  { type: 'internal', label: 'Internal', description: 'Win/loss and support themes' },
  { type: 'evidence', label: 'Evidence', description: 'Factbase research' },
];

interface SynthesisConfigPanelProps {
  productId: number;
}

export default function SynthesisConfigPanel({ productId }: SynthesisConfigPanelProps) {
  const [config, setConfig] = useState<SynthesisConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Draft state — only committed on explicit Save.
  const [draftSources, setDraftSources] = useState<SynthesisSourceType[]>([]);
  const [draftAutoIdea, setDraftAutoIdea] = useState<boolean>(true);
  const [draftThreshold, setDraftThreshold] = useState<number>(0.8);

  const loadConfig = useCallback(async () => {
    setLoadError(null);
    try {
      const resp = await getSynthesisConfig(productId);
      setConfig(resp.config);
      setDraftSources([...resp.config.included_source_types]);
      setDraftAutoIdea(resp.config.auto_generate_ideas);
      setDraftThreshold(resp.config.idea_priority_threshold);
    } catch (err: any) {
      setLoadError(err?.message ?? 'Failed to load synthesis config.');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  useEffect(() => {
    if (savedAt !== null) {
      const t = setTimeout(() => setSavedAt(null), 3000);
      return () => clearTimeout(t);
    }
  }, [savedAt]);

  const isDirty = useMemo(() => {
    if (!config) return false;
    const currentSources = new Set(config.included_source_types);
    const draftSet = new Set(draftSources);
    if (currentSources.size !== draftSet.size) return true;
    for (const s of draftSet) if (!currentSources.has(s)) return true;
    if (draftAutoIdea !== config.auto_generate_ideas) return true;
    if (Math.abs(draftThreshold - config.idea_priority_threshold) > 1e-6) return true;
    return false;
  }, [config, draftSources, draftAutoIdea, draftThreshold]);

  const toggleSource = (type: SynthesisSourceType) => {
    setDraftSources((prev) =>
      prev.includes(type) ? prev.filter((s) => s !== type) : [...prev, type]
    );
  };

  const handleSave = async () => {
    setSaveError(null);
    if (draftSources.length === 0) {
      setSaveError('Select at least one source type.');
      return;
    }
    setSaving(true);
    try {
      await putSynthesisConfig(productId, {
        source_types: draftSources,
        auto_generate_ideas: draftAutoIdea,
        idea_priority_threshold: draftThreshold,
      });
      setSavedAt(Date.now());
      await loadConfig();
    } catch (err: any) {
      setSaveError(err?.message ?? 'Failed to save config.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-4">
        <div className="animate-pulse h-20 bg-gray-100 rounded"></div>
      </div>
    );
  }

  if (loadError && !config) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-4">
        <h3 className="text-sm font-medium text-gray-900 mb-2">Synthesis configuration</h3>
        <p className="text-sm text-red-700">{loadError}</p>
      </div>
    );
  }

  const thresholdPct = Math.round(draftThreshold * 100);

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-4">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-gray-900">Synthesis configuration</h3>
          <p className="text-sm text-gray-500">
            Controls which sources feed synthesis and when auto-ideas spawn.
          </p>
        </div>
        {savedAt !== null && (
          <span className="text-xs text-green-700">Saved.</span>
        )}
      </div>

      {/* Source types */}
      <div className="mb-5">
        <label className="block text-sm font-medium text-gray-700 mb-2">Source types</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {ALL_SOURCES.map(({ type, label, description }) => {
            const checked = draftSources.includes(type);
            return (
              <label
                key={type}
                className={`flex items-start gap-2 p-3 rounded border cursor-pointer transition-colors ${
                  checked
                    ? 'border-indigo-300 bg-indigo-50'
                    : 'border-gray-200 bg-white hover:bg-gray-50'
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={checked}
                  onChange={() => toggleSource(type)}
                />
                <div>
                  <div className="text-sm font-medium text-gray-900">{label}</div>
                  <div className="text-xs text-gray-500">{description}</div>
                </div>
              </label>
            );
          })}
        </div>
      </div>

      {/* Auto-generate ideas */}
      <div className="mb-5">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={draftAutoIdea}
            onChange={(e) => setDraftAutoIdea(e.target.checked)}
          />
          <span className="text-sm font-medium text-gray-700">
            Auto-generate ideas from high-priority opportunities
          </span>
        </label>
      </div>

      {/* Threshold */}
      <div className="mb-5">
        <div className="flex items-baseline justify-between mb-1">
          <label htmlFor="idea-threshold" className="text-sm font-medium text-gray-700">
            Idea priority threshold
          </label>
          <span className="text-sm text-gray-900 tabular-nums">{thresholdPct}%</span>
        </div>
        <input
          id="idea-threshold"
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={draftThreshold}
          onChange={(e) => setDraftThreshold(parseFloat(e.target.value))}
          disabled={!draftAutoIdea}
          className="w-full"
        />
        <p className="text-xs text-gray-500 mt-1">
          Opportunities scored at or above this threshold auto-spawn ideas.
        </p>
      </div>

      {saveError && (
        <div className="mb-3 p-2 rounded border border-red-200 bg-red-50 text-sm text-red-800">
          {saveError}
        </div>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !isDirty}
          className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  );
}
