/**
 * SynthesisCompetitorList
 *
 * Per-competitor inclusion toggles for unified synthesis. Each toggle
 * auto-saves on flip and the list re-fetches after each write.
 *
 * The report-freshness pill is a PO-focused signal: if synthesis runs and a
 * competitor has no CompetitorFunctionalReport, the synthesis task will
 * auto-trigger an audit and defer the run (see backend tasks.py).
 */

import { useCallback, useEffect, useState } from 'react';
import {
  getSynthesisCompetitorsCfg,
  patchCompetitorSynthesisInclusion,
} from '../../../services/api';
import type { SynthesisCompetitorConfigEntry } from '../../../types';

interface SynthesisCompetitorListProps {
  productId: number;
  // Bumped by the parent SynthesisHubPage whenever a synthesis run finishes
  // (or starts) — tells this component to re-fetch so freshly-completed
  // audits flip from "Audit running" to "Report ready" without a manual
  // browser reload.
  reloadKey?: number;
}

type FreshnessState =
  | { label: string; classes: string };

function reportFreshness(entry: SynthesisCompetitorConfigEntry): FreshnessState {
  // `has_report` is the canonical "synthesis has data" signal because older
  // reports predate `audit_status`. Treat it as the primary source of truth.
  if (entry.has_report) {
    return { label: 'Report ready', classes: 'bg-green-100 text-green-800' };
  }
  const status = (entry.audit_status || '').toLowerCase();
  if (status === 'running' || status === 'queued' || status === 'pending') {
    return { label: 'Audit running', classes: 'bg-blue-100 text-blue-800' };
  }
  if (status === 'failed') {
    return { label: 'Audit failed — retry on next run', classes: 'bg-red-100 text-red-800' };
  }
  return {
    label: 'No report yet — will be audited',
    classes: 'bg-amber-100 text-amber-800',
  };
}

export default function SynthesisCompetitorList({
  productId,
  reloadKey,
}: SynthesisCompetitorListProps) {
  const [competitors, setCompetitors] = useState<SynthesisCompetitorConfigEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; message: string } | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const resp = await getSynthesisCompetitorsCfg(productId);
      setCompetitors(resp.competitors);
    } catch (err: any) {
      setLoadError(err?.message ?? 'Failed to load competitors.');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    load();
    // reloadKey is intentionally part of the dependency list so a parent-
    // initiated bump triggers a fresh fetch even when productId is unchanged.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, reloadKey]);

  const handleToggle = async (entry: SynthesisCompetitorConfigEntry) => {
    setRowError(null);
    setPendingId(entry.competitor_id);
    try {
      await patchCompetitorSynthesisInclusion(
        productId,
        entry.competitor_id,
        !entry.synthesis_included,
      );
      await load();
    } catch (err: any) {
      setRowError({
        id: entry.competitor_id,
        message: err?.message ?? 'Failed to update.',
      });
    } finally {
      setPendingId(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-4">
        <div className="animate-pulse h-20 bg-gray-100 rounded"></div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-4">
        <h3 className="text-base font-semibold text-gray-900 mb-2">Competitors in synthesis</h3>
        <p className="text-sm text-red-700">{loadError}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-4">
      <div className="mb-4">
        <h3 className="text-base font-semibold text-gray-900">Competitors in synthesis</h3>
        <p className="text-sm text-gray-500">
          Toggle which competitors contribute to unified synthesis. Missing reports are
          audited automatically on the next run; the run defers until audits complete.
        </p>
      </div>

      {competitors.length === 0 ? (
        <p className="text-sm text-gray-500 italic">No active competitors yet.</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {competitors.map((c) => {
            const freshness = reportFreshness(c);
            const isPending = pendingId === c.competitor_id;
            const hasRowError = rowError?.id === c.competitor_id;
            return (
              <li
                key={c.competitor_id}
                className="py-3 flex items-center justify-between gap-3"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900 truncate">
                      {c.competitor_name}
                    </span>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${freshness.classes}`}
                    >
                      {freshness.label}
                    </span>
                  </div>
                  {c.competitor_url && (
                    <a
                      href={c.competitor_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-gray-500 hover:text-indigo-600 truncate block"
                    >
                      {c.competitor_url}
                    </a>
                  )}
                  {hasRowError && (
                    <p className="text-xs text-red-700 mt-1">{rowError!.message}</p>
                  )}
                </div>
                <label className="inline-flex items-center cursor-pointer select-none gap-2">
                  <span className="text-xs text-gray-600">
                    {c.synthesis_included ? 'Included' : 'Excluded'}
                  </span>
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={c.synthesis_included}
                    disabled={isPending}
                    onChange={() => handleToggle(c)}
                  />
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
