/**
 * IdeaCard Component
 *
 * Displays a single idea with:
 * - Title and descriptions (what, why, use_case)
 * - Vote counts (score, upvotes, downvotes)
 * - VoteButtons component
 * - Expandable details with status history
 * - Timestamp
 * - Triage status badge (for PO view)
 * - Respond button (for PO view)
 */

import { useState, useEffect } from 'react';
import VoteButtons from './VoteButtons';
import { getIdeaDetail } from '../services/api';
import type { IdeaListItem, IdeaDetail } from '../types';

interface IdeaCardProps {
  idea: IdeaListItem;
  onVoteUpdate?: (ideaId: number) => void;
  // PO mode props
  showPOControls?: boolean;
  onRespond?: (ideaId: number) => void;
}

const IdeaCard = ({ idea, onVoteUpdate, showPOControls, onRespond }: IdeaCardProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [userVote, setUserVote] = useState<number | null>(idea.user_vote || null);
  const [voteTimestamp, setVoteTimestamp] = useState<string | null>(idea.user_vote_timestamp || null);
  const [ideaDetail, setIdeaDetail] = useState<IdeaDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Fetch idea detail when expanded (to get status history)
  useEffect(() => {
    if (isExpanded && !ideaDetail && !loadingDetail) {
      const fetchDetail = async () => {
        setLoadingDetail(true);
        try {
          const detail = await getIdeaDetail(idea.id);
          setIdeaDetail(detail);
        } catch (err) {
          console.error('Failed to fetch idea detail:', err);
        } finally {
          setLoadingDetail(false);
        }
      };
      fetchDetail();
    }
  }, [isExpanded, idea.id, ideaDetail, loadingDetail]);

  // Determine if voting should be disabled (only accepted ideas can be voted on)
  const isVotingDisabled = showPOControls && idea.status && idea.status !== 'accepted';

  // Get status badge config
  const getStatusBadge = () => {
    if (!idea.status) return null;

    const badges: Record<string, { label: string; className: string }> = {
      pending: { label: 'Awaiting Triage', className: 'bg-yellow-100 text-yellow-800' },
      accepted: { label: 'Accepted', className: 'bg-green-100 text-green-800' },
      duplicate: { label: 'Duplicate', className: 'bg-gray-100 text-gray-600 line-through' },
      merged: { label: 'Merged', className: 'bg-gray-100 text-gray-600' },
      feature_exists: { label: 'Feature Exists', className: 'bg-orange-100 text-orange-800' },
      not_appropriate: { label: 'Not Appropriate', className: 'bg-red-100 text-red-800' },
      needs_review: { label: 'Needs Review', className: 'bg-blue-100 text-blue-800' },
    };

    return badges[idea.status] || null;
  };

  const statusBadge = getStatusBadge();

  // Handle vote change from VoteButtons
  const handleVoteChange = (newVote: number | null) => {
    // Update local vote state
    setUserVote(newVote);

    // Update timestamp (set to current time if voting, null if unvoting)
    setVoteTimestamp(newVote ? new Date().toISOString() : null);

    // Notify parent component to refresh vote counts
    if (onVoteUpdate) {
      onVoteUpdate(idea.id);
    }
  };

  // Format date
  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Format vote status message
  const getVoteStatusMessage = (): string => {
    if (!userVote) {
      return 'No vote yet';
    }

    if (voteTimestamp) {
      const date = new Date(voteTimestamp);
      const formattedDate = date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
      return `You voted +1 on ${formattedDate}`;
    }

    return 'You voted +1';
  };

  // Truncate text to approximately 200 words
  const truncateText = (text: string | null, wordLimit = 200): string => {
    if (!text) return '';
    const words = text.split(/\s+/);
    if (words.length <= wordLimit) return text;
    return words.slice(0, wordLimit).join(' ') + '...';
  };

  // Determine if this idea should have reduced visual prominence
  // Only apply inactive styling to "final" rejection statuses, not to pending/needs_review
  const rejectedStatuses = ['duplicate', 'merged', 'feature_exists', 'not_appropriate'];
  const isRejected = idea.status && rejectedStatuses.includes(idea.status);

  // Determine if this idea is awaiting review (highlight with orange for POs)
  const awaitingReviewStatuses = ['pending', 'needs_review'];
  const isAwaitingReview = idea.status && awaitingReviewStatuses.includes(idea.status);

  // Title styling: orange for awaiting review, strikethrough for rejected, normal otherwise
  const getTitleClassName = () => {
    if (isRejected) return 'text-xl font-bold line-through text-gray-500';
    if (isAwaitingReview) return 'text-xl font-bold text-yellow-600';
    return 'text-xl font-bold text-gray-900';
  };

  return (
    <div className={`bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow ${isRejected ? 'opacity-60' : ''}`}>
      <div className="idea-card-inner">
        <div className="flex">
          {/* Vote Section */}
          <div className="vote-section flex-shrink-0">
            {isVotingDisabled ? (
              <div className="text-center text-gray-400">
                <svg className="w-6 h-6 mx-auto mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <span className="text-xs">Voting disabled</span>
              </div>
            ) : (
              <VoteButtons
                ideaId={idea.id}
                currentVote={userVote}
                onVoteChange={handleVoteChange}
              />
            )}
            {/* Total Votes Display */}
            <div className="text-center mt-2">
              <span className="text-sm font-semibold text-gray-700">
                {idea.vote_counts.total_votes}
              </span>
              <div className="text-xs text-gray-500 mt-0.5">
                {idea.vote_counts.total_votes === 1 ? 'vote' : 'votes'}
              </div>
            </div>
          </div>

          {/* Content Section */}
          <div className="flex-1 min-w-0">
            {/* Title with PO Respond Button */}
            <div className="flex items-start justify-between gap-4 mb-2">
              <h3 className={getTitleClassName()}>
                {idea.title}
              </h3>

              {/* PO Respond Button */}
              {showPOControls && onRespond && (
                <button
                  onClick={() => onRespond(idea.id)}
                  className="flex-shrink-0 px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 transition-colors"
                >
                  {idea.status === 'pending' || idea.status === 'needs_review' ? 'Respond' : 'Edit Response'}
                </button>
              )}
            </div>

            {/* Badges Row */}
            <div className="flex flex-wrap gap-2 mb-3">
              {/* Status Badge - shown for all users */}
              {statusBadge && (
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusBadge.className}`}>
                  {statusBadge.label}
                </span>
              )}

              {/* Product Badge */}
              {idea.product_name && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z" />
                  </svg>
                  {idea.product_name}
                </span>
              )}
            </div>

            {/* Duplicate link */}
            {idea.duplicate_of_idea_id && idea.duplicate_of_title && (
              <div className="mb-3 text-sm text-gray-500">
                Duplicate of: <span className="font-medium text-blue-600">#{idea.duplicate_of_idea_id} {idea.duplicate_of_title}</span>
              </div>
            )}

            {/* What Description - truncated or full */}
            <div className="mb-3">
              <p className="text-gray-700">
                {isExpanded ? idea.what_description : truncateText(idea.what_description, 200)}
              </p>
            </div>

            {/* Expandable Details - Only shown when expanded */}
            {isExpanded && (
              <div className="space-y-3 mb-3">
                {/* Why Description */}
                {idea.why_description && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900 mb-1">
                      Why is it valuable?
                    </h4>
                    <p className="text-gray-700">{idea.why_description}</p>
                  </div>
                )}

                {/* Use Case Description */}
                {idea.use_case_description && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900 mb-1">
                      How would it be used?
                    </h4>
                    <p className="text-gray-700">{idea.use_case_description}</p>
                  </div>
                )}

                {/* Category - shown in expanded view */}
                {idea.category && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900 mb-1">
                      Category
                    </h4>
                    <span className="bg-gray-100 px-3 py-1 rounded text-gray-700">
                      {idea.category}
                    </span>
                  </div>
                )}

                {/* Status History Timeline */}
                {loadingDetail ? (
                  <div className="flex items-center gap-2 text-gray-500 py-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                    <span className="text-sm">Loading history...</span>
                  </div>
                ) : ideaDetail?.status_history && ideaDetail.status_history.length > 0 && (
                  <div className="border-t border-gray-200 pt-3 mt-3">
                    <h4 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Status History
                    </h4>
                    <div className="space-y-2">
                      {ideaDetail.status_history.map((entry) => (
                        <div key={entry.id} className="flex items-start gap-2 text-sm">
                          {/* Timeline dot */}
                          <div className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${
                            entry.is_automated ? 'bg-purple-500' : 'bg-blue-500'
                          }`} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              {/* Status badge */}
                              {entry.new_status && (
                                <span className={`inline-flex items-center px-1.5 py-0.5 text-xs font-medium rounded ${
                                  entry.new_status === 'accepted' ? 'bg-green-100 text-green-800' :
                                  entry.new_status === 'pending' ? 'bg-gray-100 text-gray-800' :
                                  entry.new_status === 'needs_review' ? 'bg-yellow-100 text-yellow-800' :
                                  entry.new_status === 'duplicate' || entry.new_status === 'merged' ? 'bg-gray-100 text-gray-600' :
                                  entry.new_status === 'feature_exists' ? 'bg-orange-100 text-orange-800' :
                                  entry.new_status === 'not_appropriate' ? 'bg-red-100 text-red-800' :
                                  'bg-gray-100 text-gray-800'
                                }`}>
                                  {entry.new_status.replace(/_/g, ' ')}
                                </span>
                              )}
                              {/* Who made the change */}
                              {entry.is_automated ? (
                                <span className="text-xs text-purple-600 flex items-center gap-1">
                                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                  </svg>
                                  AI
                                </span>
                              ) : entry.changed_by_username && (
                                <span className="text-xs text-gray-500">
                                  by {entry.changed_by_username}
                                </span>
                              )}
                              {/* Confidence for AI */}
                              {entry.confidence && (
                                <span className="text-xs text-purple-600">
                                  ({entry.confidence}%)
                                </span>
                              )}
                              {/* Timestamp */}
                              <span className="text-xs text-gray-400 ml-auto">
                                {new Date(entry.created_at).toLocaleDateString()}
                              </span>
                            </div>
                            {/* Comment */}
                            {entry.comment && (
                              <p className="text-xs text-gray-600 mt-1 italic truncate" title={entry.comment}>
                                "{entry.comment}"
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Competitive Context - PO mode only */}
                {showPOControls && ideaDetail?.competitive_context && (
                  <div className="border-t border-indigo-200 pt-3 mt-3 bg-indigo-50 -mx-3 px-3 pb-3 rounded-b">
                    <h4 className="text-sm font-semibold text-indigo-900 mb-2 flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                      Competitive Context
                    </h4>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full font-medium ${
                        ideaDetail.competitive_context.priority_level === 'critical' ? 'bg-red-100 text-red-800' :
                        ideaDetail.competitive_context.priority_level === 'high' ? 'bg-orange-100 text-orange-800' :
                        ideaDetail.competitive_context.priority_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {ideaDetail.competitive_context.priority_level === 'critical' ? '🔴' :
                         ideaDetail.competitive_context.priority_level === 'high' ? '🟠' :
                         ideaDetail.competitive_context.priority_level === 'medium' ? '🟡' : '⚪'}
                        {' '}{Math.round(ideaDetail.competitive_context.priority_score * 100)}% priority
                      </span>
                      <span className="text-indigo-700">
                        {ideaDetail.competitive_context.competitors_with_feature.length}/{ideaDetail.competitive_context.total_competitors_analyzed} competitors
                      </span>
                    </div>
                    {ideaDetail.competitive_context.competitors_with_feature.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {ideaDetail.competitive_context.competitors_with_feature.slice(0, 4).map((competitor, idx) => (
                          <span key={idx} className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-indigo-100 text-indigo-800">
                            {competitor}
                          </span>
                        ))}
                        {ideaDetail.competitive_context.competitors_with_feature.length > 4 && (
                          <span className="text-xs text-indigo-500">
                            +{ideaDetail.competitive_context.competitors_with_feature.length - 4} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Expand/Collapse Button */}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              {isExpanded ? 'Show less' : 'Show more'}
            </button>

            {/* Metadata Footer - Always visible */}
            <div className="flex items-center gap-4 mt-4 text-sm">
              {/* Vote Status */}
              <span className={userVote ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                {getVoteStatusMessage()}
              </span>

              {/* Date */}
              <span className="text-gray-500">{formatDate(idea.created_at)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IdeaCard;
