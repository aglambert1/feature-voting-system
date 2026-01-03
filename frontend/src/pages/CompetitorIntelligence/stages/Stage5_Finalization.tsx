/**
 * Stage5_Finalization
 *
 * Session completion summary showing:
 * - Summary of all generated ideas and their triage outcomes
 * - Links to view approved ideas in voting system
 * - Links to review queue for ideas needing review
 * - Option to start new analysis
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../../services/api';

interface GeneratedIdea {
  id: number;
  what: string;
  why: string;
  use_case: string;
  competitor_name: string;
  feature_name: string;
  idea_id: number | null;
  status: string | null;
  is_active: boolean;
}

interface SessionSummary {
  session_id: number;
  ideas: GeneratedIdea[];
  total_count: number;
  accepted_count: number;
  needs_review_count: number;
  pending_count: number;
  duplicate_count: number;
}

interface Stage5Props {
  sessionId: number;
  onBack: () => void;
}

const Stage5_Finalization = ({
  sessionId,
  onBack
}: Stage5Props) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(true);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState<boolean>(false);
  const [completed, setCompleted] = useState<boolean>(false);

  useEffect(() => {
    loadSummary();
  }, [sessionId]);

  const loadSummary = async (): Promise<void> => {
    setLoading(true);
    try {
      const response = await api.get<SessionSummary>(
        `/product-intelligence/sessions/${sessionId}/generated-ideas`
      );
      setSummary(response.data);
    } catch (err: any) {
      console.error('Failed to load summary:', err);
      setError('Failed to load session summary');
    } finally {
      setLoading(false);
    }
  };

  const completeSession = async (): Promise<void> => {
    setCompleting(true);
    setError(null);
    try {
      await api.post(`/product-intelligence/sessions/${sessionId}/finalize`);
      setCompleted(true);
    } catch (err: any) {
      console.error('Failed to complete session:', err);
      setError(err.response?.data?.detail || 'Failed to complete session');
    } finally {
      setCompleting(false);
    }
  };

  const getStatusBadge = (status: string | null) => {
    switch (status) {
      case 'accepted':
        return <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-700 rounded">Accepted</span>;
      case 'needs_review':
        return <span className="px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-700 rounded">Needs Review</span>;
      case 'pending':
        return <span className="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-600 rounded">Pending</span>;
      case 'duplicate':
        return <span className="px-2 py-1 text-xs font-medium bg-orange-100 text-orange-700 rounded">Duplicate</span>;
      case 'merged':
        return <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 rounded">Merged</span>;
      case 'feature_exists':
        return <span className="px-2 py-1 text-xs font-medium bg-orange-100 text-orange-700 rounded">Feature Exists</span>;
      case 'not_appropriate':
        return <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-700 rounded">Not Appropriate</span>;
      default:
        return <span className="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-600 rounded">{status || 'Unknown'}</span>;
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-8 text-center">
          <div className="mb-6">
            <div className="mx-auto h-16 w-16 bg-green-100 rounded-full flex items-center justify-center">
              <svg className="h-10 w-10 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            Session Complete!
          </h2>
          <p className="text-gray-600 mb-2">
            {summary?.total_count || 0} ideas were generated and triaged.
          </p>
          <div className="flex justify-center gap-4 text-sm text-gray-600 mb-8">
            {(summary?.accepted_count || 0) > 0 && (
              <span className="text-green-600">
                {summary?.accepted_count || 0} accepted for voting
              </span>
            )}
            {(summary?.needs_review_count || 0) > 0 && (
              <span className="text-yellow-600">
                {summary?.needs_review_count} need review
              </span>
            )}
          </div>
          <div className="flex gap-4 justify-center">
            <button
              onClick={() => navigate('/ideas')}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
            >
              View Ideas in Voting System
            </button>
            {(summary?.needs_review_count || 0) > 0 && (
              <button
                onClick={() => navigate('/pm-review')}
                className="bg-yellow-600 text-white px-6 py-3 rounded-lg hover:bg-yellow-700"
              >
                Review Pending Ideas
              </button>
            )}
            <button
              onClick={() => navigate('/product-intelligence')}
              className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300"
            >
              Start New Analysis
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
        Failed to load session data
      </div>
    );
  }

  const acceptedCount = summary.accepted_count || 0;
  const hasPending = (summary.pending_count || 0) > 0;

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Stage 5: Session Summary</h2>
        <p className="text-gray-600">
          Review the results of idea generation and triage.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <div className="text-3xl font-bold text-gray-900">{summary.total_count}</div>
          <div className="text-sm text-gray-600">Total Ideas</div>
        </div>
        <div className="bg-green-50 rounded-lg shadow p-6 text-center border border-green-200">
          <div className="text-3xl font-bold text-green-700">{acceptedCount}</div>
          <div className="text-sm text-green-600">Accepted for Voting</div>
        </div>
        <div className="bg-yellow-50 rounded-lg shadow p-6 text-center border border-yellow-200">
          <div className="text-3xl font-bold text-yellow-700">{summary.needs_review_count || 0}</div>
          <div className="text-sm text-yellow-600">Need Review</div>
        </div>
        <div className="bg-gray-50 rounded-lg shadow p-6 text-center border border-gray-200">
          <div className="text-3xl font-bold text-gray-700">{summary.pending_count || 0}</div>
          <div className="text-sm text-gray-600">Still Processing</div>
        </div>
      </div>

      {hasPending && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-600"></div>
            <div>
              <p className="font-medium text-purple-900">
                Triage Still in Progress
              </p>
              <p className="text-sm text-purple-700">
                {summary.pending_count} {summary.pending_count === 1 ? 'idea is' : 'ideas are'} still being analyzed.
                Refresh to see updates.
              </p>
            </div>
            <button
              onClick={loadSummary}
              className="ml-auto px-3 py-1 bg-purple-100 text-purple-700 rounded hover:bg-purple-200"
            >
              Refresh
            </button>
          </div>
        </div>
      )}

      {/* Ideas List */}
      <div className="bg-white rounded-lg shadow mb-8">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">Generated Ideas</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {summary.ideas.map((idea) => (
            <div key={idea.id} className="px-6 py-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-medium bg-gray-100 text-gray-700 px-2 py-1 rounded">
                      {idea.competitor_name}
                    </span>
                    {getStatusBadge(idea.status)}
                  </div>
                  <p className="text-gray-900 mb-1">{idea.what}</p>
                  <p className="text-sm text-gray-600">Source: {idea.feature_name}</p>
                </div>
                {idea.idea_id && idea.is_active && (
                  <button
                    onClick={() => navigate(`/ideas/${idea.idea_id}`)}
                    className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                  >
                    View →
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-between">
        <button
          onClick={onBack}
          disabled={completing}
          className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300 disabled:opacity-50"
        >
          ← Back to Ideas
        </button>
        <button
          onClick={completeSession}
          disabled={completing || hasPending}
          className="bg-green-600 text-white px-8 py-3 rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-semibold"
          title={hasPending ? 'Wait for all ideas to finish processing' : ''}
        >
          {completing ? (
            <>
              <span className="inline-block animate-spin mr-2">⚙️</span>
              Completing...
            </>
          ) : (
            'Complete Session'
          )}
        </button>
      </div>
    </div>
  );
};

export default Stage5_Finalization;
