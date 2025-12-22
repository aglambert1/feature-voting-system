/**
 * Stage2_CompetitorDiscovery
 *
 * AI-powered competitor discovery with differential analysis.
 * Shows discovered competitors, allows selection, and supports custom additions.
 */

import { useState, useEffect, useRef } from 'react';
import api from '../../../services/api';
import CompetitorCard from '../components/CompetitorCard';
import ChangeSummaryCard from '../components/ChangeSummaryCard';
import AddCompetitorModal from '../components/AddCompetitorModal';

interface Competitor {
  id: string;
  name: string;
  url: string;
  summary: string;
  relevance_score?: number;
  status?: 'new' | 'continuing' | 'disappeared';
  status_explanation?: string;
  selected: boolean;
  selected_by_user?: boolean;
  discovery_source?: string;
}

interface ChangeSummary {
  new_count: number;
  continuing_count: number;
  disappeared_count: number;
  significant_changes?: string[];
}

interface Stage2State {
  mode: string;
  competitors: Competitor[];
  changeSummary: ChangeSummary | null;
  researchSummary: string;
}

interface Stage2Props {
  sessionId: number;
  hasPreviousAnalysis: boolean;
  onComplete: () => void;
  onBack: () => void;
  savedState?: Stage2State | null;
  onStateChange?: (state: Stage2State) => void;
  previousSessionId?: number | null;
}

const Stage2_CompetitorDiscovery = ({
  sessionId,
  hasPreviousAnalysis,
  onComplete,
  onBack,
  savedState,
  onStateChange,
  previousSessionId,
}: Stage2Props) => {
  const [mode, setMode] = useState<string>(savedState?.mode || 'loading');
  const [competitors, setCompetitors] = useState<Competitor[]>(savedState?.competitors || []);
  const [changeSummary, setChangeSummary] = useState<ChangeSummary | null>(savedState?.changeSummary || null);
  const [researchSummary, setResearchSummary] = useState<string>(savedState?.researchSummary || '');
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [discoveryInitiated, setDiscoveryInitiated] = useState<boolean>(!!savedState);
  const [existingCompetitors, _setExistingCompetitors] = useState<Competitor[]>([]);
  const [featuresAvailability, setFeaturesAvailability] = useState<Record<string, { has_features: boolean; competitor_name: string }>>({});
  const copyingRef = useRef<boolean>(false);

  // Persist state changes to parent
  useEffect(() => {
    if (onStateChange) {
      onStateChange({
        mode,
        competitors,
        changeSummary,
        researchSummary
      });
    }
  }, [mode, competitors, changeSummary, researchSummary, onStateChange]);

  useEffect(() => {
    // Only fetch if we don't have saved state
    if (!savedState && !discoveryInitiated) {
      setDiscoveryInitiated(true);
      checkExistingCompetitors();
    }
  }, [savedState, discoveryInitiated]);

  // Refresh features availability when component mounts or when returning from Stage 3
  useEffect(() => {
    // If we have competitors (either from savedState or loaded), fetch their feature availability
    if (competitors.length > 0 && mode === 'reviewing') {
      console.log('[Stage2] Refreshing features availability for', competitors.length, 'competitors');
      fetchFeaturesAvailability();
    }
  }, [sessionId]); // Only run on mount or when sessionId changes

  const fetchFeaturesAvailability = async (): Promise<void> => {
    try {
      const response = await api.get<{
        competitors_availability: Record<string, { has_features: boolean; competitor_name: string }>;
      }>(`/product-intelligence/sessions/${sessionId}/competitors-feature-availability`);

      setFeaturesAvailability(response.data.competitors_availability);
      console.log('[Stage2] Features availability loaded:', response.data.competitors_availability);

      // Debug: Log which competitors have features vs which don't
      const withFeatures = Object.entries(response.data.competitors_availability)
        .filter(([_, data]) => data.has_features)
        .map(([id, data]) => `${data.competitor_name} (ID: ${id})`);
      const withoutFeatures = Object.entries(response.data.competitors_availability)
        .filter(([_, data]) => !data.has_features)
        .map(([id, data]) => `${data.competitor_name} (ID: ${id})`);

      console.log('[Stage2] Competitors WITH features:', withFeatures);
      console.log('[Stage2] Competitors WITHOUT features:', withoutFeatures);
    } catch (err: any) {
      console.error('[Stage2] Failed to fetch features availability:', err);
      // Non-critical, continue without it
    }
  };

  const checkExistingCompetitors = async (): Promise<void> => {
    // First check if THIS session already has competitors (handles legacy sessions)
    console.log('[Stage2] Checking existing competitors for session:', sessionId);

    try {
      // Try to fetch competitors from the current session first
      const currentSessionResponse = await api.get<{ competitors: Competitor[] }>(
        `/product-intelligence/sessions/${sessionId}/competitors`
      );

      const currentComps = currentSessionResponse.data.competitors || [];
      console.log('[Stage2] Found', currentComps.length, 'competitors in current session');

      if (currentComps.length > 0) {
        // This session already has competitors - show them immediately
        console.log('[Stage2] Using existing competitors from current session - immediate display');
        const mappedCompetitors = currentComps.map(c => ({
          ...c,
          selected: c.selected_by_user ?? false
        }));
        setCompetitors(mappedCompetitors);
        setMode('reviewing');
        await fetchFeaturesAvailability();
        return;
      }

      // No competitors in current session - check if we have a previous session to copy from
      console.log('[Stage2] No competitors in current session. previousSessionId:', previousSessionId);

      if (!previousSessionId || hasPreviousAnalysis) {
        // No previous session OR this is differential analysis - run discovery
        // For differential analysis, we always want to discover NEW competitors rather than copying old ones
        console.log('[Stage2] No previousSessionId or differential analysis mode, starting discovery');
        discoverCompetitors();
        return;
      }

      // Copy competitors from previous session to current session (non-differential sessions only)
      // Guard against multiple calls (React StrictMode runs effects twice)
      if (copyingRef.current) {
        console.log('[Stage2] Copy already in progress, skipping duplicate call');
        return;
      }

      copyingRef.current = true;
      console.log('[Stage2] Copying competitors from previous session:', previousSessionId, 'to current session:', sessionId);

      const copyResponse = await api.post<{ copied_count: number; skipped_count: number }>(
        `/product-intelligence/sessions/${sessionId}/copy-competitors/${previousSessionId}`
      );

      console.log('[Stage2] Copy result:', copyResponse.data);
      copyingRef.current = false;

      if (copyResponse.data.copied_count > 0 || copyResponse.data.skipped_count > 0) {
        // Competitors were copied (or already existed), fetch and display them
        console.log('[Stage2] Fetching copied competitors from current session');
        const currentSessionResponse = await api.get<{ competitors: Competitor[] }>(
          `/product-intelligence/sessions/${sessionId}/competitors`
        );

        const copiedComps = currentSessionResponse.data.competitors || [];
        console.log('[Stage2] Found', copiedComps.length, 'competitors after copy');

        if (copiedComps.length > 0) {
          const mappedCompetitors = copiedComps.map(c => ({
            ...c,
            selected: c.selected_by_user ?? false
          }));
          setCompetitors(mappedCompetitors);
          setMode('reviewing');
          await fetchFeaturesAvailability();
        } else {
          // Shouldn't happen, but fallback to discovery
          console.log('[Stage2] No competitors after copy, starting discovery');
          discoverCompetitors();
        }
      } else {
        // No competitors to copy - run discovery
        console.log('[Stage2] No competitors to copy, starting discovery');
        discoverCompetitors();
      }
    } catch (err: any) {
      // If fetching fails, fall back to discovery
      console.error('[Stage2] Failed to check existing competitors:', err);
      copyingRef.current = false; // Reset on error
      discoverCompetitors();
    }
  };

  const discoverCompetitors = async (): Promise<void> => {
    try {
      setMode('loading');
      const response = await api.post<{ competitors: Competitor[]; change_summary?: ChangeSummary; research_summary?: string }>(
        `/product-intelligence/sessions/${sessionId}/discover-competitors`
      );

      // Sort competitors by relevance score (highest first)
      // Map selected_by_user to selected for UI state
      // User-added competitors are now preserved by the backend and included in the response
      const sortedCompetitors = [...response.data.competitors]
        .map(c => ({ ...c, selected: c.selected_by_user ?? false }))
        .sort((a, b) => {
          const scoreA = a.relevance_score || 0;
          const scoreB = b.relevance_score || 0;
          return scoreB - scoreA;
        });

      setCompetitors(sortedCompetitors);
      setChangeSummary(response.data.change_summary || null);
      setResearchSummary(response.data.research_summary || '');
      setMode('reviewing');
      await fetchFeaturesAvailability();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to discover competitors');
      setMode('error');
    }
  };

  const handleUseExisting = async (): Promise<void> => {
    // Map selected_by_user to selected for UI state
    const mappedCompetitors = existingCompetitors.map(c => ({
      ...c,
      selected: c.selected_by_user ?? false
    }));
    setCompetitors(mappedCompetitors);
    setMode('reviewing');
    await fetchFeaturesAvailability();
  };

  const handleRediscover = (): void => {
    discoverCompetitors();
  };

  const toggleCompetitor = (competitorId: string): void => {
    setCompetitors((prev) =>
      prev.map((c) =>
        c.id === competitorId ? { ...c, selected: !c.selected } : c
      )
    );
  };

  const handleAddCustom = async (competitor: { name: string; url: string; summary?: string }): Promise<void> => {
    try {
      // Save to backend immediately so it persists across navigation/rediscovery
      const response = await api.post<Competitor>(
        `/product-intelligence/sessions/${sessionId}/competitors/add-custom`,
        {
          name: competitor.name,
          url: competitor.url,
          summary: competitor.summary || 'User-added competitor'
        }
      );

      // Add the returned competitor (with real ID) to local state
      const newCompetitor: Competitor = {
        ...response.data,
        selected: true
      };
      setCompetitors((prev) => [...prev, newCompetitor]);
      setShowAddModal(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add custom competitor');
    }
  };

  const handleDeleteCompetitor = async (competitorId: string): Promise<void> => {
    // Delete from backend (all competitors are now persisted immediately)
    try {
      await api.delete(`/product-intelligence/sessions/${sessionId}/competitors/${competitorId}`);
      setCompetitors((prev) => prev.filter((c) => c.id !== competitorId));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete competitor');
    }
  };

  const handleConfirm = async (): Promise<void> => {
    // All competitors (including user-added) now have real IDs from the database
    const selectedIds = competitors
      .filter((c) => c.selected)
      .map((c) => parseInt(c.id));

    if (selectedIds.length === 0) {
      alert('Please select at least one competitor');
      return;
    }

    setSubmitting(true);

    try {
      await api.post(
        `/product-intelligence/sessions/${sessionId}/confirm-competitors`,
        {
          selected_ids: selectedIds,
          custom_competitors: null, // No longer needed - custom competitors are already in DB
        }
      );

      onComplete();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to confirm competitors');
    } finally {
      setSubmitting(false);
    }
  };

  if (mode === 'loading') {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          {hasPreviousAnalysis ? 'Discovering New Competitors...' : 'Discovering Competitors...'}
        </h3>
        <p className="text-gray-600 mb-2">
          {hasPreviousAnalysis
            ? 'AI is researching new competitors and comparing with previous analysis'
            : 'AI is researching the competitive landscape'}
        </p>
        <p className="text-sm text-gray-500">
          ⏱️ This typically takes 30-60 seconds
        </p>
      </div>
    );
  }

  if (mode === 'error') {
    return (
      <div className="text-center py-12">
        <div className="text-red-600 mb-4">
          <svg
            className="mx-auto h-12 w-12"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Discovery Failed
        </h3>
        <p className="text-gray-600 mb-4">{error}</p>
        <button
          onClick={discoverCompetitors}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (mode === 'choice') {
    const selectedCount = existingCompetitors.filter(c => c.selected_by_user).length;
    const previewCompetitors = existingCompetitors.filter(c => c.selected_by_user).slice(0, 3);

    return (
      <div>
        <h2 className="text-2xl font-bold mb-4">Competitor Discovery</h2>
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start">
            <svg className="w-6 h-6 text-blue-600 mr-3 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div className="text-sm text-blue-800">
              <strong>Existing Competitors Found:</strong> You have {selectedCount} competitor{selectedCount !== 1 ? 's' : ''} from a previous analysis session.
            </div>
          </div>
        </div>

        <div className="space-y-4 mb-6">
          {/* Use Existing Option */}
          <div className="border-2 border-gray-200 rounded-lg p-6 hover:border-blue-300 transition-colors">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center">
                <svg className="w-6 h-6 text-blue-600 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <h3 className="text-lg font-semibold text-gray-900">
                  Use Existing Competitors ({selectedCount})
                </h3>
              </div>
            </div>
            <p className="text-gray-600 mb-4">
              Continue with your previously selected competitors without running a new discovery.
            </p>

            {/* Preview */}
            {previewCompetitors.length > 0 && (
              <div className="mb-4 space-y-2">
                {previewCompetitors.map(comp => (
                  <div key={comp.id} className="flex items-center text-sm">
                    <span className="w-2 h-2 bg-blue-500 rounded-full mr-2"></span>
                    <span className="font-medium">{comp.name}</span>
                  </div>
                ))}
                {selectedCount > 3 && (
                  <div className="text-sm text-gray-500 ml-4">
                    ... and {selectedCount - 3} more
                  </div>
                )}
              </div>
            )}

            <button
              onClick={handleUseExisting}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
            >
              Continue with Existing →
            </button>
          </div>

          {/* Discover New Option */}
          <div className="border-2 border-gray-200 rounded-lg p-6 hover:border-blue-300 transition-colors">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center">
                <svg className="w-6 h-6 text-blue-600 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <h3 className="text-lg font-semibold text-gray-900">
                  Discover New Competitors
                </h3>
              </div>
            </div>
            <p className="text-gray-600 mb-4">
              Run AI-powered discovery to find competitors in the current competitive landscape.
              {hasPreviousAnalysis && (
                <span className="block mt-1 text-sm">
                  Will perform differential analysis to identify NEW/CONTINUING/DISAPPEARED competitors.
                </span>
              )}
            </p>
            <div className="mb-4 flex items-center text-sm text-gray-500">
              <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Takes 30-60 seconds
            </div>

            <button
              onClick={handleRediscover}
              className="w-full px-4 py-2 border-2 border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50 font-medium"
            >
              Run New Discovery
            </button>
          </div>
        </div>

        <div className="flex justify-start">
          <button
            onClick={onBack}
            className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
          >
            ← Back
          </button>
        </div>
      </div>
    );
  }

  const selectedCount = competitors.filter((c) => c.selected).length;

  return (
    <div>
      <div className="flex justify-between items-start mb-6">
        <div className="flex-1">
          <h2 className="text-2xl font-bold mb-2">Competitor Discovery</h2>
          <p className="text-gray-600 mb-2">{researchSummary}</p>
          {competitors.length > 0 && (
            <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-amber-600 mr-2 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <div className="text-sm text-amber-800">
                  <strong>Note:</strong> Competitors are suggested based on AI knowledge. Please review and verify URLs before proceeding. Deselect any competitors with incorrect information.
                </div>
              </div>
            </div>
          )}
        </div>
        <div className="text-sm text-gray-600 ml-4">
          {selectedCount} of {competitors.length} selected
        </div>
      </div>

      {hasPreviousAnalysis && changeSummary && (
        <ChangeSummaryCard changeSummary={changeSummary} />
      )}

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <div className="mb-6 flex gap-3">
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 border border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50"
        >
          + Add Custom Competitor
        </button>
        <button
          onClick={discoverCompetitors}
          className="px-4 py-2 border border-gray-600 text-gray-600 rounded-lg hover:bg-gray-50"
        >
          🔄 Re-discover Competitors
        </button>
      </div>

      {competitors.length === 0 ? (
        <div className="text-center py-12 px-4 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300 mb-6">
          <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 12h.01M12 12h.01M12 12h.01M12 12h.01" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Competitors Found</h3>
          <p className="text-gray-600 mb-4 max-w-md mx-auto">
            The AI couldn't identify verified competitors based on its knowledge. This might be a very niche product or may need more specific details.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => setShowAddModal(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Add Competitors Manually
            </button>
            <button
              onClick={onBack}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              Refine Product Description
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {competitors.map((competitor) => (
            <CompetitorCard
              key={competitor.id}
              competitor={competitor}
              onToggle={() => toggleCompetitor(competitor.id)}
              showStatus={hasPreviousAnalysis}
              onDelete={() => handleDeleteCompetitor(competitor.id)}
              hasFeatures={featuresAvailability[competitor.id]?.has_features ?? false}
            />
          ))}
        </div>
      )}

      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
        >
          ← Back
        </button>
        <button
          onClick={handleConfirm}
          disabled={submitting || selectedCount === 0}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {submitting ? 'Confirming...' : `Extract Features (${selectedCount}) →`}
        </button>
      </div>

      {showAddModal && (
        <AddCompetitorModal
          onAdd={handleAddCustom}
          onClose={() => setShowAddModal(false)}
        />
      )}
    </div>
  );
};

export default Stage2_CompetitorDiscovery;
