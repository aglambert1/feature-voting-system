/**
 * Stage4_IdeaGeneration
 *
 * Idea generation stage with:
 * - AI-powered idea generation from selected features
 * - Automatic triage via IdeaTriageAgent (runs in background)
 * - Review workflow using IdeaResponseModal for ideas needing review
 * - Auto-approval support based on product settings
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../../services/api';
import IdeaResponseModal from '../../../components/IdeaResponseModal';

interface GeneratedIdea {
  id: number;
  what: string;
  why: string;
  use_case: string;
  competitor_name: string;
  feature_name: string;
  user_edited: boolean;
  // Linked Idea triage fields
  idea_id: number | null;
  triage_status: string | null;
  triage_confidence: number | null;
  triage_recommendation: string | null;
  published_for_voting: boolean;
}

interface GeneratedIdeasResponse {
  ideas: GeneratedIdea[];
  total_count: number;
  auto_approved_count: number;
  needs_review_count: number;
  pending_count: number;
  approved_count: number;
}

interface Stage4Props {
  sessionId: number;
  productId: number;
  onComplete: () => void;
  onBack: () => void;
}

const Stage4_IdeaGeneration = ({
  sessionId,
  productId,
  onComplete,
  onBack
}: Stage4Props) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [ideas, setIdeas] = useState<GeneratedIdea[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Modal state for reviewing ideas
  const [reviewingIdeaId, setReviewingIdeaId] = useState<number | null>(null);
  const [reviewingIdeaTitle, setReviewingIdeaTitle] = useState<string>('');

  const loadGeneratedIdeas = useCallback(async (): Promise<void> => {
    try {
      const response = await api.get<GeneratedIdeasResponse>(
        `/product-intelligence/sessions/${sessionId}/generated-ideas`
      );
      setIdeas(response.data.ideas || []);
    } catch (err: any) {
      console.error('Failed to load ideas:', err);
      if (err.response?.status !== 404) {
        setError('Failed to load generated ideas');
      }
    }
  }, [sessionId]);

  useEffect(() => {
    setLoading(true);
    loadGeneratedIdeas().finally(() => setLoading(false));
  }, [loadGeneratedIdeas]);

  // Poll for triage status updates while any ideas are pending
  useEffect(() => {
    const hasPending = ideas.some(i => i.triage_status === 'pending');
    if (hasPending && !generating) {
      const interval = setInterval(loadGeneratedIdeas, 3000);
      return () => clearInterval(interval);
    }
  }, [ideas, generating, loadGeneratedIdeas]);

  const generateIdeas = async (): Promise<void> => {
    setGenerating(true);
    setError(null);
    try {
      const response = await api.post<{ ideas: GeneratedIdea[] }>(
        `/product-intelligence/sessions/${sessionId}/generate-ideas`
      );
      setIdeas(response.data.ideas || []);
    } catch (err: any) {
      console.error('Failed to generate ideas:', err);
      setError(err.response?.data?.detail || 'Failed to generate ideas');
    } finally {
      setGenerating(false);
    }
  };

  const openReviewModal = (idea: GeneratedIdea): void => {
    if (idea.idea_id) {
      setReviewingIdeaId(idea.idea_id);
      // Use first sentence of "what" as title
      const firstSentence = idea.what.split('.')[0] || idea.what;
      const title = firstSentence.slice(0, 100);
      setReviewingIdeaTitle(title);
    }
  };

  const closeReviewModal = (): void => {
    setReviewingIdeaId(null);
    setReviewingIdeaTitle('');
  };

  const handleReviewSuccess = async (): Promise<void> => {
    closeReviewModal();
    await loadGeneratedIdeas();
  };

  const getTriageStatusBadge = (idea: GeneratedIdea) => {
    const status = idea.triage_status;

    if (!status || status === 'pending') {
      return (
        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600">
          <span className="animate-pulse mr-1">●</span>
          Analyzing...
        </span>
      );
    }

    switch (status) {
      case 'auto_approved':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700">
            ✓ Auto-Approved
          </span>
        );
      case 'approved':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700">
            ✓ Approved
          </span>
        );
      case 'needs_review':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-700">
            Needs Review
          </span>
        );
      case 'duplicate':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-orange-100 text-orange-700">
            Duplicate
          </span>
        );
      case 'feature_exists':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-orange-100 text-orange-700">
            Feature Exists
          </span>
        );
      case 'not_appropriate':
      case 'rejected':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-700">
            Rejected
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600">
            {status}
          </span>
        );
    }
  };

  const getActionButton = (idea: GeneratedIdea) => {
    const status = idea.triage_status;

    if (!status || status === 'pending') {
      return (
        <button
          disabled
          className="px-4 py-2 rounded font-medium bg-gray-200 text-gray-400 cursor-not-allowed"
        >
          Waiting...
        </button>
      );
    }

    if (status === 'auto_approved' || status === 'approved') {
      return (
        <button
          onClick={() => idea.idea_id && navigate(`/ideas/${idea.idea_id}`)}
          className="px-4 py-2 rounded font-medium bg-green-100 text-green-700 hover:bg-green-200"
        >
          View Idea →
        </button>
      );
    }

    if (status === 'needs_review') {
      return (
        <button
          onClick={() => openReviewModal(idea)}
          className="px-4 py-2 rounded font-medium bg-blue-600 text-white hover:bg-blue-700"
        >
          Review
        </button>
      );
    }

    // For duplicate, feature_exists, rejected - allow re-review
    return (
      <button
        onClick={() => openReviewModal(idea)}
        className="px-4 py-2 rounded font-medium bg-gray-100 text-gray-700 hover:bg-gray-200"
      >
        View Response
      </button>
    );
  };

  // Count by status
  const pendingCount = ideas.filter(i => !i.triage_status || i.triage_status === 'pending').length;
  const autoApprovedCount = ideas.filter(i => i.triage_status === 'auto_approved').length;
  const approvedCount = ideas.filter(i => i.triage_status === 'approved').length;
  const needsReviewCount = ideas.filter(i => i.triage_status === 'needs_review').length;
  const processedCount = ideas.length - pendingCount;

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Stage 4: Idea Generation & Triage</h2>
        <p className="text-gray-600">
          AI generates ideas from competitor features and analyzes them for duplicates and relevance.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {ideas.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="mb-6">
            <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold mb-2">Generate Ideas</h3>
          <p className="text-gray-600 mb-6">
            Click the button below to generate product-specific ideas from selected competitor features.
            Ideas will be automatically analyzed for duplicates and relevance.
          </p>
          <button
            onClick={generateIdeas}
            disabled={generating}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {generating ? (
              <>
                <span className="inline-block animate-spin mr-2">⚙️</span>
                Generating Ideas...
              </>
            ) : (
              'Generate Ideas'
            )}
          </button>
        </div>
      ) : (
        <>
          {/* Summary Banner */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-blue-900">
                  {ideas.length} ideas generated
                </p>
                <div className="flex gap-4 text-sm text-blue-700 mt-1">
                  {pendingCount > 0 && (
                    <span className="flex items-center gap-1">
                      <span className="animate-pulse">●</span> {pendingCount} analyzing
                    </span>
                  )}
                  {autoApprovedCount > 0 && (
                    <span>✓ {autoApprovedCount} auto-approved</span>
                  )}
                  {approvedCount > 0 && (
                    <span>✓ {approvedCount} approved</span>
                  )}
                  {needsReviewCount > 0 && (
                    <span className="text-yellow-700">⚠ {needsReviewCount} need review</span>
                  )}
                </div>
              </div>
              <button
                onClick={generateIdeas}
                disabled={generating}
                className="bg-white text-blue-600 px-4 py-2 rounded border border-blue-300 hover:bg-blue-50"
              >
                {generating ? 'Regenerating...' : 'Regenerate'}
              </button>
            </div>
          </div>

          {/* Progress indicator while triage is running */}
          {pendingCount > 0 && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-6">
              <div className="flex items-center gap-3">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-600"></div>
                <div>
                  <p className="font-medium text-purple-900">
                    AI Triage in Progress
                  </p>
                  <p className="text-sm text-purple-700">
                    Analyzing {pendingCount} {pendingCount === 1 ? 'idea' : 'ideas'} for duplicates and relevance...
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Ideas List */}
          <div className="space-y-6">
            {ideas.map((idea) => (
              <div
                key={idea.id}
                className={`bg-white rounded-lg shadow border-2 ${
                  idea.triage_status === 'auto_approved' || idea.triage_status === 'approved'
                    ? 'border-green-300'
                    : idea.triage_status === 'needs_review'
                    ? 'border-yellow-300'
                    : 'border-gray-200'
                }`}
              >
                <div className="p-6">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-1 rounded">
                          From: {idea.competitor_name}
                        </span>
                        {idea.user_edited && (
                          <span className="text-xs font-semibold bg-blue-100 text-blue-700 px-2 py-1 rounded">
                            Edited
                          </span>
                        )}
                        {getTriageStatusBadge(idea)}
                      </div>
                      <p className="text-sm text-gray-600">
                        Source: {idea.feature_name}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {getActionButton(idea)}
                    </div>
                  </div>

                  {/* Content */}
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 mb-1">What</h4>
                      <p className="text-gray-900">{idea.what}</p>
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 mb-1">Why</h4>
                      <p className="text-gray-900">{idea.why}</p>
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 mb-1">Use Case</h4>
                      <p className="text-gray-900">{idea.use_case}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Navigation */}
      <div className="flex justify-between mt-8">
        <button
          onClick={onBack}
          className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300"
        >
          ← Back to Features
        </button>
        {ideas.length > 0 && processedCount === ideas.length && (
          <button
            onClick={onComplete}
            className="bg-green-600 text-white px-8 py-3 rounded-lg hover:bg-green-700 font-semibold"
          >
            Complete Session
          </button>
        )}
      </div>

      {/* Review Modal */}
      {reviewingIdeaId && (
        <IdeaResponseModal
          ideaId={reviewingIdeaId}
          ideaTitle={reviewingIdeaTitle}
          productId={productId}
          onClose={closeReviewModal}
          onSuccess={handleReviewSuccess}
        />
      )}
    </div>
  );
};

export default Stage4_IdeaGeneration;
