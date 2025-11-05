/**
 * IdeaCard Component
 *
 * Displays a single idea with:
 * - Title and descriptions (what, why, use_case)
 * - Vote counts (score, upvotes, downvotes)
 * - VoteButtons component
 * - Expandable details
 * - Timestamp
 */

import { useState } from 'react';
import VoteButtons from './VoteButtons';

const IdeaCard = ({ idea, onVoteUpdate }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [userVote, setUserVote] = useState(idea.user_vote || null);

  // Handle vote change from VoteButtons
  const handleVoteChange = (newVote) => {
    // Update local vote state
    setUserVote(newVote);

    // Notify parent component to refresh vote counts
    if (onVoteUpdate) {
      onVoteUpdate(idea.id);
    }
  };

  // Format date
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Truncate text to approximately 200 words
  const truncateText = (text, wordLimit = 200) => {
    if (!text) return '';
    const words = text.split(/\s+/);
    if (words.length <= wordLimit) return text;
    return words.slice(0, wordLimit).join(' ') + '...';
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow">
      <div className="idea-card-inner">
        <div className="flex">
          {/* Vote Section */}
          <div className="vote-section flex-shrink-0">
            <VoteButtons
              ideaId={idea.id}
              currentVote={userVote}
              onVoteChange={handleVoteChange}
            />
            {/* Score Display */}
            <div className="text-center mt-2">
              <span className="text-sm font-semibold text-gray-700">
                {idea.vote_counts.score}
              </span>
            </div>
          </div>

          {/* Content Section */}
          <div className="flex-1 min-w-0">
            {/* Title */}
            <h3 className="text-xl font-bold text-gray-900 mb-2">
              {idea.title}
            </h3>

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
            <div className="flex items-center gap-4 mt-4 text-sm text-gray-500">
              {/* Vote Stats */}
              <span>
                {idea.vote_counts.upvotes} upvotes • {idea.vote_counts.downvotes} downvotes
              </span>

              {/* Date */}
              <span>{formatDate(idea.created_at)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IdeaCard;
