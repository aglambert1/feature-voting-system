/**
 * Stage3_FeatureExtraction
 *
 * Feature extraction stage with:
 * - Sequential feature extraction from competitors
 * - Change detection (NEW/MODIFIED/UNCHANGED/REMOVED)
 * - Feature selection for idea generation
 */

import { useState, useEffect, ChangeEvent } from 'react';
import api from '../../../services/api';
import FeatureCard from '../components/FeatureCard';
import ChangeSummaryCard from '../components/ChangeSummaryCard';

interface LinkedIdea {
  idea_id: number;
  idea_title: string;
  triage_status: string | null;
  is_locked: boolean;
}

interface Feature {
  id: string;
  name: string;
  description: string;
  category?: string;
  confidence?: number;
  source_url?: string;
  change_type?: 'new' | 'modified' | 'unchanged' | 'removed';
  change_description?: string;
  selected: boolean;
  linked_idea?: LinkedIdea | null;
}

interface FeaturesByCompetitor {
  competitor_id: number;
  competitor_name: string;
  competitor_url?: string;
  features: Feature[];
}

interface ChangeStats {
  total: number;
  new?: number;
  modified?: number;
  unchanged?: number;
  removed?: number;
}

interface ExistingCompetitor {
  session_competitor_id: number;
  product_competitor_id: number;
  competitor_name: string;
  features_count: number;
  last_extraction_session_id?: number;
  extraction_timestamp?: string;
  from_product_id?: number;
}

interface Stage3State {
  mode: string;
  features: FeaturesByCompetitor[];
  changeStats: ChangeStats | null;
  expandedCompetitors?: Set<number>;
}

interface Stage3Props {
  sessionId: string;
  hasPreviousAnalysis: boolean;
  onComplete: () => void;
  onBack: () => void;
  savedState?: Stage3State | null;
  onStateChange?: (state: Stage3State) => void;
  previousSessionId?: number | null;
}

const Stage3_FeatureExtraction = ({
  sessionId,
  hasPreviousAnalysis,
  onComplete,
  onBack,
  savedState,
  onStateChange,
  previousSessionId: _previousSessionId,
}: Stage3Props) => {
  const [mode, setMode] = useState<string>(savedState?.mode || 'loading');
  const [featuresByCompetitor, setFeaturesByCompetitor] = useState<FeaturesByCompetitor[]>(savedState?.features || []);
  const [changeStats, setChangeStats] = useState<ChangeStats | null>(savedState?.changeStats || null);
  const [showOnlyChanges, setShowOnlyChanges] = useState<boolean>(hasPreviousAnalysis);
  const [error, setError] = useState<string | null>(null);
  const [existingFeatures, setExistingFeatures] = useState<ExistingCompetitor[]>([]);
  const [totalSelectedCompetitors, setTotalSelectedCompetitors] = useState<number>(0);
  const [expandedCompetitors, setExpandedCompetitors] = useState<Set<number>>(
    savedState?.expandedCompetitors || new Set(featuresByCompetitor.map(c => c.competitor_id))
  );

  // Save state when it changes
  useEffect(() => {
    if (onStateChange) {
      onStateChange({
        mode,
        features: featuresByCompetitor,
        changeStats,
        expandedCompetitors,
      });
    }
  }, [mode, featuresByCompetitor, changeStats, expandedCompetitors, onStateChange]);

  useEffect(() => {
    // If we have saved state, don't re-extract
    if (savedState?.features && savedState.features.length > 0) {
      console.log('[Stage3] Restored from saved state');
      return;
    }

    // Check for existing features from previous session
    checkExistingFeatures();
  }, []);

  const checkExistingFeatures = async (): Promise<void> => {
    console.log('[Stage3] Checking if selected competitors have existing features from any previous session');

    try {
      // Check which selected competitors have extractable features
      const response = await api.get<{ competitors_with_features: ExistingCompetitor[]; total_selected: number; with_features: number }>(
        `/product-intelligence/sessions/${sessionId}/competitors/feature-availability`
      );

      const { competitors_with_features, total_selected, with_features } = response.data;
      console.log(`[Stage3] ${with_features} of ${total_selected} competitors have existing features`);

      // Store total selected count for UI calculations
      setTotalSelectedCompetitors(total_selected);

      if (with_features > 0) {
        // Some competitors have existing features - show choice UI
        console.log('[Stage3] Showing choice UI - some competitors have reusable features');
        setExistingFeatures(competitors_with_features);
        setMode('choice');
      } else {
        // No existing features for any selected competitor - extract all
        console.log('[Stage3] No existing features for any competitor, starting extraction');
        extractFeatures();
      }
    } catch (err: any) {
      console.error('[Stage3] Failed to check feature availability:', err);
      // Fall back to extraction
      extractFeatures();
    }
  };

  const handleUseExisting = (): void => {
    console.log('[Stage3] Using existing features - backend will reuse and only extract missing');
    // Pass reuse_existing=true to skip AI extraction for competitors with existing features
    extractFeatures(true);
  };

  const handleReExtract = (): void => {
    console.log('[Stage3] Re-extracting features');
    extractFeatures(false);
  };

  const extractFeatures = async (reuseExisting: boolean = false): Promise<void> => {
    try {
      setMode('loading');

      // Start extraction with reuse parameter
      await api.post(
        `/product-intelligence/sessions/${sessionId}/extract-features?reuse_existing=${reuseExisting}`
      );

      // Load extracted features
      const response = await api.get<{ features_by_competitor: FeaturesByCompetitor[]; change_stats?: ChangeStats }>(
        `/product-intelligence/sessions/${sessionId}/features`
      );

      setFeaturesByCompetitor(response.data.features_by_competitor || []);
      setChangeStats(response.data.change_stats || null);
      setMode('reviewing');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to extract features');
      setMode('error');
    }
  };

  const toggleFeatureSelection = (competitorId: number, featureId: string): void => {
    setFeaturesByCompetitor((prev) =>
      prev.map((comp) => {
        if (comp.competitor_id === competitorId) {
          return {
            ...comp,
            features: comp.features.map((f) =>
              f.id === featureId ? { ...f, selected: !f.selected } : f
            ),
          };
        }
        return comp;
      })
    );
  };

  const toggleCompetitorExpanded = (competitorId: number): void => {
    setExpandedCompetitors((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(competitorId)) {
        newSet.delete(competitorId);
      } else {
        newSet.add(competitorId);
      }
      return newSet;
    });
  };

  const handleConfirmSelection = async (): Promise<void> => {
    // Collect all selected feature IDs (excluding locked features - already added as ideas)
    const selectedIds: number[] = [];
    featuresByCompetitor.forEach((comp) => {
      comp.features.forEach((f) => {
        if (f.selected && !f.linked_idea?.is_locked) {
          selectedIds.push(parseInt(f.id));
        }
      });
    });

    if (selectedIds.length === 0) {
      alert('Please select at least one feature');
      return;
    }

    try {
      // First, select the features
      await api.post(
        `/product-intelligence/sessions/${sessionId}/select-features`,
        { feature_ids: selectedIds }
      );

      // Then immediately trigger idea generation
      setMode('generating-ideas');
      await api.post(
        `/product-intelligence/sessions/${sessionId}/generate-ideas`
      );

      // Navigate to Stage 4 to show generated ideas
      onComplete();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate ideas');
      setMode('reviewing');
    }
  };

  if (mode === 'choice') {
    const totalFeatures = existingFeatures.reduce((sum, comp) => sum + (comp.features_count || 0), 0);
    const competitorsNeedingExtraction = totalSelectedCompetitors - existingFeatures.length;
    const isInstant = competitorsNeedingExtraction === 0;

    return (
      <div>
        <h2 className="text-2xl font-bold mb-4">Feature Extraction - Reuse Available</h2>

        {/* Info banner */}
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start">
            <svg className="w-6 h-6 text-blue-600 mr-3 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-semibold text-blue-900">
                Smart Feature Reuse Available
              </p>
              <p className="text-sm text-blue-700 mt-1">
                {existingFeatures.length} competitor(s) have been previously analyzed with {totalFeatures} total feature(s). You can reuse these to save time.
              </p>
            </div>
          </div>
        </div>

        {/* Detailed competitor status */}
        <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Competitor Analysis Status:</h4>
          <div className="space-y-2">
            {existingFeatures.map((comp) => {
              const extractionDate = comp.extraction_timestamp
                ? new Date(comp.extraction_timestamp).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })
                : null;

              return (
                <div key={comp.session_competitor_id} className="flex items-center justify-between p-3 bg-white rounded border border-gray-200 hover:border-blue-300 transition-colors">
                  <div className="flex items-center flex-1">
                    <svg className="w-5 h-5 text-green-500 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900">{comp.competitor_name}</p>
                      {comp.from_product_id && (
                        <p className="text-xs text-blue-600">
                          From another product (cross-product reuse)
                        </p>
                      )}
                      {extractionDate && (
                        <p className="text-xs text-gray-500">
                          Extracted: {extractionDate}
                        </p>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-green-600 font-medium whitespace-nowrap ml-2">
                    ✓ {comp.features_count} features
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-4 mb-6">
          {/* Smart Reuse Option (Recommended) */}
          <div className="border-2 border-green-500 rounded-lg p-6 bg-green-50">
            <div className="flex items-start mb-3">
              <span className="px-2 py-1 bg-green-600 text-white text-xs font-semibold rounded mr-3">RECOMMENDED</span>
              <h3 className="text-lg font-semibold text-gray-900">
                Use Existing Features{isInstant ? ' (Instant)' : ''}
              </h3>
            </div>
            <p className="text-gray-700 mb-3">
              Reuse the {totalFeatures} feature(s) from these {existingFeatures.length} competitor(s).
              {competitorsNeedingExtraction > 0 && (
                <> The other {competitorsNeedingExtraction} selected competitor{competitorsNeedingExtraction !== 1 ? 's' : ''} will be analyzed with AI extraction.</>
              )}
            </p>
            <div className="flex items-center text-sm text-green-700 mb-4">
              <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
              </svg>
              <span className="font-medium">
                {isInstant
                  ? 'Instant - all competitors have existing features'
                  : `Instant for ${existingFeatures.length} • AI extraction for ${competitorsNeedingExtraction} competitor${competitorsNeedingExtraction !== 1 ? 's' : ''}`
                }
              </span>
            </div>

            <button
              onClick={handleUseExisting}
              className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
            >
              Use Existing + Extract Missing →
            </button>
          </div>

          {/* Re-extract Option */}
          <div className="border-2 border-gray-200 rounded-lg p-6 hover:border-blue-300 transition-colors">
            <h3 className="text-lg font-semibold mb-2">Re-Extract All Features</h3>
            <p className="text-gray-600 mb-2">
              Run AI-powered feature extraction to analyze all competitors and extract fresh features, ignoring existing data.
            </p>
            <div className="text-sm text-orange-600 mb-4">
              ⏱️ Takes 1-3 minutes depending on number of competitors
            </div>

            <button
              onClick={handleReExtract}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Run New Feature Extraction
            </button>
          </div>
        </div>

        {/* Back button */}
        <div className="mt-6 flex justify-start">
          <button
            onClick={onBack}
            className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            ← Back to Competitor Selection
          </button>
        </div>
      </div>
    );
  }

  if (mode === 'loading') {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Extracting Features...
        </h3>
        <p className="text-gray-600 mb-2">
          AI is analyzing competitors and extracting features
        </p>
        <p className="text-sm text-gray-500">
          ⏱️ This typically takes 1-3 minutes depending on number of competitors
        </p>
      </div>
    );
  }

  if (mode === 'generating-ideas') {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Generating Ideas...
        </h3>
        <p className="text-gray-600 mb-2">
          AI is adapting competitor features into product-specific ideas
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
          Extraction Failed
        </h3>
        <p className="text-gray-600 mb-4">{error}</p>
        <button
          onClick={() => extractFeatures()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  // Count selected features (excluding locked ones - already added to ideas)
  const totalSelected = featuresByCompetitor.reduce(
    (sum, comp) => sum + comp.features.filter((f) => f.selected && !f.linked_idea?.is_locked).length,
    0
  );

  // Count locked features (already added as ideas)
  const totalLocked = featuresByCompetitor.reduce(
    (sum, comp) => sum + comp.features.filter((f) => f.linked_idea?.is_locked).length,
    0
  );

  // Filter features if showing only changes
  const displayCompetitors = featuresByCompetitor.map((comp) => {
    if (showOnlyChanges && hasPreviousAnalysis) {
      return {
        ...comp,
        features: comp.features.filter(
          (f) => f.change_type === 'new' || f.change_type === 'modified'
        ),
      };
    }
    return comp;
  });

  return (
    <div>
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-2xl font-bold mb-2">Feature Extraction</h2>
          <p className="text-gray-600">
            Review and select features for idea generation
          </p>
        </div>
        <div className="text-sm text-right">
          <div className="text-gray-600">{totalSelected} features selected</div>
          {totalLocked > 0 && (
            <div className="text-purple-600">{totalLocked} already added as ideas</div>
          )}
        </div>
      </div>

      {hasPreviousAnalysis && changeStats && (
        <ChangeSummaryCard
          changeStats={changeStats}
          title="Feature Change Summary"
        />
      )}

      {hasPreviousAnalysis && (
        <div className="mb-4 flex items-center">
          <input
            type="checkbox"
            id="show_only_changes"
            checked={showOnlyChanges}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setShowOnlyChanges(e.target.checked)}
            className="mr-2"
          />
          <label htmlFor="show_only_changes" className="text-sm text-gray-700">
            Show only new/modified features
          </label>
        </div>
      )}

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <div className="space-y-4 mb-6">
        {displayCompetitors.map((competitor) => {
          const isExpanded = expandedCompetitors.has(competitor.competitor_id);
          // Count selected features excluding those already linked to ideas
          const selectedCount = competitor.features.filter(f => f.selected && !f.linked_idea).length;

          return (
            <div key={competitor.competitor_id} className="bg-white rounded-lg shadow">
              {/* Competitor Header - Always visible, clickable to expand/collapse */}
              <button
                onClick={() => toggleCompetitorExpanded(competitor.competitor_id)}
                className="w-full text-left px-6 py-4 border-b border-gray-200 hover:bg-gray-50 transition-colors flex items-center justify-between"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <span className={`transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
                      ▶
                    </span>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">
                        {competitor.competitor_name}
                      </h3>
                      {competitor.competitor_url && (
                        <a
                          href={competitor.competitor_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {competitor.competitor_url}
                        </a>
                      )}
                    </div>
                  </div>
                </div>
                <div className="text-sm text-gray-600 whitespace-nowrap ml-4">
                  {selectedCount > 0 && (
                    <span className="font-semibold text-blue-600 mr-4">
                      {selectedCount} selected
                    </span>
                  )}
                  <span>{competitor.features.length} features</span>
                </div>
              </button>

              {/* Features Section - Expandable */}
              {isExpanded && (
                <div className="p-6 border-t border-gray-100">
                  {competitor.features.length === 0 ? (
                    <p className="text-center text-gray-500 py-4">
                      {showOnlyChanges
                        ? 'No new or modified features'
                        : 'No features extracted'}
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {competitor.features.map((feature) => (
                        <FeatureCard
                          key={feature.id}
                          feature={feature}
                          onToggle={() =>
                            toggleFeatureSelection(competitor.competitor_id, feature.id)
                          }
                          showChangeType={hasPreviousAnalysis}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
        >
          ← Back
        </button>
        <button
          onClick={handleConfirmSelection}
          disabled={totalSelected === 0}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Generate Ideas ({totalSelected}) →
        </button>
      </div>
    </div>
  );
};

export default Stage3_FeatureExtraction;
