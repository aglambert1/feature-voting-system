/**
 * VoteButtons Component
 *
 * Upvote/downvote buttons with:
 * - Upvote (▲) and downvote (▼) buttons
 * - Highlight user's current vote
 * - Optimistic UI updates
 * - Error handling and rollback
 */

import { useState } from 'react';
import { voteOnIdea } from '../services/api';

const VoteButtons = ({ ideaId, currentVote, onVoteChange }) => {
  const [isVoting, setIsVoting] = useState(false);
  const [error, setError] = useState('');

  /**
   * Handle vote action
   * @param {number} voteValue - 1 for upvote, -1 for downvote
   */
  const handleVote = async (voteValue) => {
    // Prevent double-clicking
    if (isVoting) return;

    setIsVoting(true);
    setError('');

    // Store previous vote for rollback
    const previousVote = currentVote;

    // Optimistic update - update UI immediately
    onVoteChange(voteValue === currentVote ? null : voteValue);

    try {
      // Call API to submit vote
      await voteOnIdea(ideaId, voteValue);

      // Success - onVoteChange already updated the UI
    } catch (err) {
      // Error - rollback to previous vote
      onVoteChange(previousVote);
      setError('Failed to vote. Please try again.');
      console.error('Vote error:', err);
    } finally {
      setIsVoting(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Upvote Button */}
      <button
        onClick={() => handleVote(1)}
        disabled={isVoting}
        className={`w-12 h-12 flex items-center justify-center rounded-md text-2xl font-bold transition-all ${
          currentVote === 1
            ? 'bg-blue-600 text-white shadow-md'
            : 'bg-white border-2 border-gray-300 text-gray-600 hover:border-blue-500 hover:text-blue-600 hover:shadow-sm'
        } ${isVoting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        title="Upvote"
      >
        ▲
      </button>

      {/* Downvote Button */}
      <button
        onClick={() => handleVote(-1)}
        disabled={isVoting}
        className={`w-12 h-12 flex items-center justify-center rounded-md text-2xl font-bold transition-all ${
          currentVote === -1
            ? 'bg-red-600 text-white shadow-md'
            : 'bg-white border-2 border-gray-300 text-gray-600 hover:border-red-500 hover:text-red-600 hover:shadow-sm'
        } ${isVoting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        title="Downvote"
      >
        ▼
      </button>

      {/* Error message */}
      {error && (
        <p className="text-xs text-red-600 mt-1">{error}</p>
      )}
    </div>
  );
};

export default VoteButtons;
