/**
 * Stage2_CompetitorDiscovery
 *
 * AI-powered competitor discovery with differential analysis.
 * Shows discovered competitors, allows selection, and supports custom additions.
 */

import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import api from '../../../services/api';
import CompetitorCard from '../components/CompetitorCard';
import ChangeSummaryCard from '../components/ChangeSummaryCard';
import AddCompetitorModal from '../components/AddCompetitorModal';

const Stage2_CompetitorDiscovery = ({
  sessionId,
  hasPreviousAnalysis,
  onComplete,
  onBack,
  savedState,
  onStateChange,
  previousSessionId,
}) => {
  const [mode, setMode] = useState(savedState?.mode || 'loading');
  const [competitors, setCompetitors] = useState(savedState?.competitors || []);
  const [changeSummary, setChangeSummary] = useState(savedState?.changeSummary || null);
  const [researchSummary, setResearchSummary] = useState(savedState?.researchSummary || '');
  const [error, setError] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [discoveryInitiated, setDiscoveryInitiated] = useState(!!savedState);
  const [existingCompetitors, setExistingCompetitors] = useState([]);

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

  const checkExistingCompetitors = async () => {
    // First check if THIS session already has competitors (handles legacy sessions)
    console.log('[Stage2] Checking existing competitors for session:', sessionId);

    try {
      // Try to fetch competitors from the current session first
      const currentSessionResponse = await api.get(
        `/competitor-intelligence/sessions/${sessionId}/competitors`
      );

      const currentComps = currentSessionResponse.data.competitors || [];
      console.log('[Stage2] Found', currentComps.length, 'competitors in current session');

      if (currentComps.length > 0) {
        // This session already has competitors - show them immediately
        console.log('[Stage2] Using existing competitors from current session - immediate display');
        const mappedCompetitors = currentComps.map(c => ({
          ...c,
          selected: c.selected_by_user
        }));
        setCompetitors(mappedCompetitors);
        setMode('reviewing');
        return;
      }

      // No competitors in current session - check if we have a previous session to copy from
      console.log('[Stage2] No competitors in current session. previousSessionId:', previousSessionId);

      if (!previousSessionId) {
        // No previous session - run discovery
        console.log('[Stage2] No previousSessionId, starting discovery');
        discoverCompetitors();
        return;
      }

      // Fetch competitors from previous session
      console.log('[Stage2] Fetching competitors from previous session:', previousSessionId);
      const previousSessionResponse = await api.get(
        `/competitor-intelligence/sessions/${previousSessionId}/competitors`
      );

      const previousComps = previousSessionResponse.data.competitors || [];
      console.log('[Stage2] Found', previousComps.length, 'total competitors from previous session');

      if (previousComps.length > 0) {
        // Show existing competitors from previous session
        console.log('[Stage2] Using competitors from previous session - immediate display');
        const mappedCompetitors = previousComps.map(c => ({
          ...c,
          selected: c.selected_by_user
        }));
        setCompetitors(mappedCompetitors);
        setMode('reviewing');
      } else {
        // No competitors found anywhere - run discovery
        console.log('[Stage2] No existing competitors found, starting discovery');
        discoverCompetitors();
      }
    } catch (err) {
      // If fetching fails, fall back to discovery
      console.error('[Stage2] Failed to check existing competitors:', err);
      discoverCompetitors();
    }
  };

  const discoverCompetitors = async () => {
    try {
      setMode('loading');
      const response = await api.post(
        `/competitor-intelligence/sessions/${sessionId}/discover-competitors`
      );

      // Sort competitors by relevance score (highest first)
      // Map selected_by_user to selected for UI state
      const sortedCompetitors = [...response.data.competitors]
        .map(c => ({ ...c, selected: c.selected_by_user }))
        .sort((a, b) => {
          const scoreA = a.relevance_score || 0;
          const scoreB = b.relevance_score || 0;
          return scoreB - scoreA;
        });

      setCompetitors(sortedCompetitors);
      setChangeSummary(response.data.change_summary);
      setResearchSummary(response.data.research_summary);
      setMode('reviewing');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to discover competitors');
      setMode('error');
    }
  };

  const handleUseExisting = () => {
    // Map selected_by_user to selected for UI state
    const mappedCompetitors = existingCompetitors.map(c => ({
      ...c,
      selected: c.selected_by_user
    }));
    setCompetitors(mappedCompetitors);
    setMode('reviewing');
  };

  const handleRediscover = () => {
    discoverCompetitors();
  };

  const toggleCompetitor = (competitorId) => {
    setCompetitors((prev) =>
      prev.map((c) =>
        c.id === competitorId ? { ...c, selected: !c.selected } : c
      )
    );
  };

  const handleAddCustom = (competitor) => {
    // Add to local state (will be sent to backend on confirm)
    const newCompetitor = {
      id: `temp-${Date.now()}`,
      name: competitor.name,
      url: competitor.url,
      summary: competitor.summary || 'User-added competitor',
      selected: true,
      discovery_source: 'user_added',
    };
    setCompetitors((prev) => [...prev, newCompetitor]);
    setShowAddModal(false);
  };

  const handleConfirm = async () => {
    const selectedIds = competitors
      .filter((c) => c.selected && !c.id.startsWith('temp-'))
      .map((c) => c.id);

    const customCompetitors = competitors
      .filter((c) => c.selected && c.id.startsWith('temp-'))
      .map((c) => ({
        name: c.name,
        url: c.url,
        summary: c.summary,
      }));

    if (selectedIds.length === 0 && customCompetitors.length === 0) {
      alert('Please select at least one competitor');
      return;
    }

    setSubmitting(true);

    try {
      await api.post(
        `/competitor-intelligence/sessions/${sessionId}/confirm-competitors`,
        {
          selected_ids: selectedIds,
          custom_competitors: customCompetitors.length > 0 ? customCompetitors : null,
        }
      );

      onComplete();
    } catch (err) {
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
          Discovering Competitors...
        </h3>
        <p className="text-gray-600 mb-2">
          AI is researching the competitive landscape
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
                    {comp.status_change && (
                      <span className="ml-2 text-xs text-gray-500">({comp.status_change})</span>
                    )}
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

Stage2_CompetitorDiscovery.propTypes = {
  sessionId: PropTypes.string.isRequired,
  hasPreviousAnalysis: PropTypes.bool.isRequired,
  onComplete: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
  savedState: PropTypes.object,
  onStateChange: PropTypes.func,
  previousSessionId: PropTypes.number,
};

export default Stage2_CompetitorDiscovery;
