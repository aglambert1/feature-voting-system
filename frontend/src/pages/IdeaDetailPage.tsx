/**
 * IdeaDetailPage Component
 *
 * Displays detailed view of a single idea including:
 * - Full idea description
 * - Voting capability (for approved ideas)
 * - Review capability (for PO/admin on needs_review ideas)
 * - Comments section with ability to add comments
 * - Status history
 * - Duplicate relationship info
 * - Vote counts
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import Navigation from '../components/Navigation';
import VoteButtons from '../components/VoteButtons';
import IdeaResponseModal from '../components/IdeaResponseModal';
import { getIdeaDetail, addIdeaComment, checkCanRespond } from '../services/api';
import { IdeaDetail, UserRole } from '../types';
import { useAuth } from '../contexts/AuthContext';

export default function IdeaDetailPage() {
  const { ideaId } = useParams<{ ideaId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [idea, setIdea] = useState<IdeaDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Comment form state
  const [newComment, setNewComment] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);

  // Voting state
  const [userVote, setUserVote] = useState<number | null>(null);

  // Review modal state
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [canRespond, setCanRespond] = useState(false);

  const fetchIdea = useCallback(async () => {
    if (!ideaId) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getIdeaDetail(parseInt(ideaId));
      setIdea(data);
      setUserVote((data as any).user_vote ?? null);

      // Check if user can respond (PO/admin)
      try {
        const respondCheck = await checkCanRespond(parseInt(ideaId));
        setCanRespond(respondCheck.can_respond);
      } catch {
        setCanRespond(false);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load idea details');
    } finally {
      setLoading(false);
    }
  }, [ideaId]);

  useEffect(() => {
    fetchIdea();
  }, [fetchIdea]);

  const handleAddComment = async () => {
    if (!newComment.trim() || !ideaId) return;

    setSubmittingComment(true);
    setCommentError(null);

    try {
      const comment = await addIdeaComment(parseInt(ideaId), newComment.trim());
      // Add new comment to the list
      setIdea(prev => prev ? {
        ...prev,
        comments: [...prev.comments, comment]
      } : null);
      setNewComment('');
    } catch (err: any) {
      setCommentError(err.response?.data?.detail || 'Failed to add comment');
    } finally {
      setSubmittingComment(false);
    }
  };

  const getStatusBadgeClass = (status: string | undefined) => {
    switch (status) {
      case 'accepted':
        return 'bg-green-100 text-green-800';
      case 'pending':
      case 'needs_review':
        return 'bg-yellow-100 text-yellow-800';
      case 'duplicate':
      case 'merged':
        return 'bg-orange-100 text-orange-800';
      case 'feature_exists':
        return 'bg-blue-100 text-blue-800';
      case 'not_appropriate':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !idea) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error || 'Idea not found'}</p>
            <button
              onClick={() => navigate('/ideas')}
              className="mt-4 text-red-600 hover:text-red-800 underline"
            >
              Back to Ideas
            </button>
          </div>
        </div>
      </div>
    );
  }

  const canComment = idea.is_active;
  const canVote = idea.status === 'accepted';
  const needsReview = idea.status === 'needs_review' || idea.status === 'pending';

  // Handle vote change
  const handleVoteChange = (newVote: number | null) => {
    setUserVote(newVote);
    // Refresh idea to get updated vote counts
    fetchIdea();
  };

  // Handle review modal close with success
  const handleReviewSuccess = () => {
    setShowReviewModal(false);
    fetchIdea();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Back link */}
        <Link
          to="/ideas"
          className="inline-flex items-center text-gray-600 hover:text-gray-900 mb-6"
        >
          <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Ideas
        </Link>

        {/* Main idea card */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          {/* Header with voting */}
          <div className="flex items-start gap-4 mb-4">
            {/* Vote section (for approved ideas) */}
            {canVote && (
              <div className="flex flex-col items-center">
                <div className="text-2xl font-bold text-gray-900">{(idea as any).upvotes ?? 0}</div>
                <div className="text-xs text-gray-500 mb-2">votes</div>
                <VoteButtons
                  ideaId={idea.id}
                  currentVote={userVote}
                  onVoteChange={handleVoteChange}
                />
              </div>
            )}

            {/* Title and metadata */}
            <div className="flex-1">
              <div className="flex items-start justify-between">
                <div>
                  <h1 className="text-2xl font-bold text-gray-900 mb-2">{idea.title}</h1>
                  <div className="flex items-center gap-3 text-sm text-gray-500">
                    <span>Submitted by {idea.submitter_username || 'Unknown'}</span>
                    <span>•</span>
                    <span>{formatDate(idea.created_at)}</span>
                    {idea.product_name && (
                      <>
                        <span>•</span>
                        <span className="text-blue-600">{idea.product_name}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusBadgeClass(idea.status)}`}>
                    {(idea.status || 'unknown').replace('_', ' ')}
                  </span>
                  {/* Review button for PO/admin */}
                  {canRespond && needsReview && (
                    <button
                      onClick={() => setShowReviewModal(true)}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
                    >
                      Review
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Duplicate notice */}
          {idea.duplicate_of_idea_id && (
            <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded-lg">
              <div className="flex items-center gap-2 text-orange-800">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                <span>
                  Marked as duplicate of{' '}
                  <Link
                    to={`/ideas/${idea.duplicate_of_idea_id}`}
                    className="font-medium underline hover:text-orange-900"
                  >
                    {idea.duplicate_of_title || `Idea #${idea.duplicate_of_idea_id}`}
                  </Link>
                </span>
              </div>
            </div>
          )}

          {/* Description sections */}
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-1">What</h3>
              <p className="text-gray-900">{idea.what_description}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-1">Why</h3>
              <p className="text-gray-900">{idea.why_description}</p>
            </div>
            {idea.use_case_description && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-1">Use Case</h3>
                <p className="text-gray-900">{idea.use_case_description}</p>
              </div>
            )}
          </div>

          {/* Category and metadata */}
          <div className="mt-6 pt-4 border-t border-gray-200">
            <div className="flex flex-wrap gap-4 text-sm">
              {idea.category && (
                <div>
                  <span className="text-gray-500">Category:</span>{' '}
                  <span className="text-gray-900">{idea.category}</span>
                </div>
              )}
              <div>
                <span className="text-gray-500">Source:</span>{' '}
                <span className="text-gray-900">{idea.source_type.replace('_', ' ')}</span>
              </div>
              {idea.reviewer_username && (
                <div>
                  <span className="text-gray-500">Reviewed by:</span>{' '}
                  <span className="text-gray-900">{idea.reviewer_username}</span>
                  {idea.reviewed_at && (
                    <span className="text-gray-400 ml-1">
                      on {formatDate(idea.reviewed_at)}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Review notes */}
          {idea.review_notes && (
            <div className="mt-4 p-3 bg-gray-50 rounded-lg">
              <h3 className="text-sm font-medium text-gray-700 mb-1">Review Notes</h3>
              <p className="text-gray-900">{idea.review_notes}</p>
            </div>
          )}

          {/* Competitive Context - PO/Admin only */}
          {idea.competitive_context && (user?.role === UserRole.ADMIN || user?.role === UserRole.PRODUCT_OWNER) && (
            <div className="mt-4 p-4 bg-indigo-50 border border-indigo-200 rounded-lg">
              <h3 className="text-sm font-medium text-indigo-900 mb-3 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Competitive Context
              </h3>
              <div className="space-y-3">
                {/* Priority Score */}
                <div className="flex items-center gap-3">
                  <span className="text-sm text-indigo-700">Priority Score:</span>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    idea.competitive_context.priority_level === 'critical' ? 'bg-red-100 text-red-800' :
                    idea.competitive_context.priority_level === 'high' ? 'bg-orange-100 text-orange-800' :
                    idea.competitive_context.priority_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {idea.competitive_context.priority_level === 'critical' ? '🔴' :
                     idea.competitive_context.priority_level === 'high' ? '🟠' :
                     idea.competitive_context.priority_level === 'medium' ? '🟡' : '⚪'}
                    {' '}{Math.round(idea.competitive_context.priority_score * 100)}% ({idea.competitive_context.priority_level})
                  </span>
                </div>

                {/* Competitors */}
                <div>
                  <span className="text-sm text-indigo-700">Competitors with feature:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {idea.competitive_context.competitors_with_feature.map((competitor, idx) => (
                      <span key={idx} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-indigo-100 text-indigo-800">
                        {competitor}
                      </span>
                    ))}
                  </div>
                  <span className="text-xs text-indigo-500 mt-1 block">
                    {idea.competitive_context.competitors_with_feature.length} of {idea.competitive_context.total_competitors_analyzed} competitors analyzed
                  </span>
                </div>

                {/* Market Context */}
                {idea.competitive_context.market_context && (
                  <div>
                    <span className="text-sm text-indigo-700">Market Context:</span>
                    <p className="text-sm text-indigo-900 mt-1">{idea.competitive_context.market_context}</p>
                  </div>
                )}

                {/* Evidence count */}
                {idea.competitive_context.source_evidence_count > 0 && (
                  <div className="text-xs text-indigo-500">
                    Based on {idea.competitive_context.source_evidence_count} source evidence quote{idea.competitive_context.source_evidence_count > 1 ? 's' : ''} from competitor analysis
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Comments section */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
            </svg>
            Comments ({idea.comments.length})
          </h2>

          {/* Comment list */}
          <div className="space-y-4 mb-6">
            {idea.comments.length === 0 ? (
              <p className="text-gray-500 text-center py-4">No comments yet</p>
            ) : (
              idea.comments.map((comment) => (
                <div
                  key={comment.id}
                  className={`p-4 rounded-lg ${
                    comment.is_system_generated
                      ? 'bg-purple-50 border border-purple-100'
                      : 'bg-gray-50 border border-gray-100'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    {comment.is_system_generated ? (
                      <span className="text-xs px-2 py-0.5 bg-purple-200 text-purple-800 rounded-full">
                        System
                      </span>
                    ) : (
                      <span className="font-medium text-gray-900">{comment.username}</span>
                    )}
                    <span className="text-xs text-gray-500">
                      {formatDate(comment.created_at)}
                    </span>
                  </div>
                  <p className="text-gray-700">{comment.comment_text}</p>
                </div>
              ))
            )}
          </div>

          {/* Add comment form */}
          {canComment ? (
            <div className="border-t border-gray-200 pt-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Add a comment</h3>
              <textarea
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Share your thoughts..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              {commentError && (
                <p className="mt-2 text-sm text-red-600">{commentError}</p>
              )}
              <div className="flex justify-end mt-2">
                <button
                  onClick={handleAddComment}
                  disabled={submittingComment || !newComment.trim()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submittingComment ? 'Posting...' : 'Post Comment'}
                </button>
              </div>
            </div>
          ) : (
            <div className="border-t border-gray-200 pt-4 text-center text-gray-500">
              <p>Comments are only available on active ideas</p>
            </div>
          )}
        </div>

        {/* Status History */}
        {idea.status_history && idea.status_history.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mt-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Status History
            </h2>

            <div className="space-y-3">
              {idea.status_history.map((entry, index) => (
                <div
                  key={entry.id}
                  className={`relative pl-6 pb-3 ${
                    index < idea.status_history.length - 1 ? 'border-l-2 border-gray-200' : ''
                  }`}
                >
                  <div className={`absolute left-0 top-0 -translate-x-1/2 w-3 h-3 rounded-full ${
                    entry.is_automated ? 'bg-purple-500' : 'bg-blue-500'
                  }`} />

                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${getStatusBadgeClass(entry.new_status ?? undefined)}`}>
                          {(entry.new_status ?? 'unknown').replace('_', ' ')}
                        </span>
                        {entry.is_automated ? (
                          <span className="text-xs text-purple-600">AI Agent</span>
                        ) : entry.changed_by_username && (
                          <span className="text-xs text-gray-500">by {entry.changed_by_username}</span>
                        )}
                        {entry.confidence && (
                          <span className="text-xs text-purple-600">({entry.confidence}% confidence)</span>
                        )}
                      </div>
                      <span className="text-xs text-gray-400">{formatDate(entry.created_at)}</span>
                    </div>
                    {entry.comment && (
                      <p className="text-sm text-gray-600 mt-1 italic">"{entry.comment}"</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Review Modal */}
      {showReviewModal && idea && (
        <IdeaResponseModal
          ideaId={idea.id}
          ideaTitle={idea.title}
          productId={idea.product_id}
          onClose={() => setShowReviewModal(false)}
          onSuccess={handleReviewSuccess}
        />
      )}
    </div>
  );
}
