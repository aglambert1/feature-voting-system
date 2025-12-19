/**
 * VoteButtons Component
 *
 * Single toggle button for upvoting:
 * - Click to upvote (shows as active +1)
 * - Click again to remove vote (shows as inactive)
 * - Optimistic UI updates
 * - Error handling and rollback
 */

import { useState } from 'react';
import { voteOnIdea } from '../services/api';

interface VoteButtonsProps {
  ideaId: number;
  currentVote: number | null;
  onVoteChange: (newVote: number | null) => void;
}

const VoteButtons = ({ ideaId, currentVote, onVoteChange }: VoteButtonsProps) => {
  const [isVoting, setIsVoting] = useState(false);
  const [error, setError] = useState('');

  const hasVoted = currentVote === 1;

  /**
   * Handle vote toggle (add or remove vote)
   */
  const handleVoteToggle = async () => {
    // Prevent double-clicking
    if (isVoting) return;

    setIsVoting(true);
    setError('');

    // Store previous vote for rollback
    const previousVote = currentVote;

    // Optimistic update - toggle between upvote and no vote
    const newVote = hasVoted ? null : 1;
    onVoteChange(newVote);

    try {
      // Call API - backend will toggle the vote (add or remove)
      await voteOnIdea(ideaId, 1);

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
    <div className="flex flex-col items-center gap-2">
      {/* Single Vote Toggle Button */}
      <button
        onClick={handleVoteToggle}
        disabled={isVoting}
        className={`
          px-4 py-2 rounded-lg font-semibold text-sm transition-all duration-200
          ${hasVoted
            ? 'bg-blue-600 text-white shadow-md hover:bg-blue-700 border-2 border-blue-600'
            : 'bg-white text-gray-700 border-2 border-gray-300 hover:border-blue-500 hover:text-blue-600 hover:shadow-sm'
          }
          ${isVoting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
        title={hasVoted ? 'Click to remove your vote' : 'Click to vote for this idea'}
      >
        <div className="flex items-center gap-1.5">
          {hasVoted ? (
            <>
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              <span>Voted</span>
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span>Vote</span>
            </>
          )}
        </div>
      </button>

      {/* Error message */}
      {error && (
        <p className="text-xs text-red-600 text-center max-w-[100px]">{error}</p>
      )}
    </div>
  );
};

export default VoteButtons;
