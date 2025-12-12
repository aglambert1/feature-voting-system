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
}) => {
  const [mode, setMode] = useState('loading');
  const [competitors, setCompetitors] = useState([]);
  const [changeSummary, setChangeSummary] = useState(null);
  const [researchSummary, setResearchSummary] = useState('');
  const [error, setError] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [discoveryInitiated, setDiscoveryInitiated] = useState(false);

  useEffect(() => {
    // Only discover once - prevent double discovery in React StrictMode
    if (!discoveryInitiated) {
      setDiscoveryInitiated(true);
      discoverCompetitors();
    }
  }, [discoveryInitiated]);

  const discoverCompetitors = async () => {
    try {
      setMode('loading');
      const response = await api.post(
        `/competitor-intelligence/sessions/${sessionId}/discover-competitors`
      );

      // Sort competitors by relevance score (highest first)
      const sortedCompetitors = [...response.data.competitors].sort((a, b) => {
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

      <div className="mb-6">
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 border border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50"
        >
          + Add Custom Competitor
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
};

export default Stage2_CompetitorDiscovery;
