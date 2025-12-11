/**
 * IdeasPage
 *
 * Main page for browsing ideas:
 * - Fetches ideas from API
 * - Displays loading state
 * - Renders IdeaCard components
 * - Sorts by score (highest first)
 * - Empty state
 * - "Submit New Idea" button
 * - Navigation header
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { getIdeas } from '../services/api';
import IdeaCard from '../components/IdeaCard';
import Navigation from '../components/Navigation';

const IdeasPage = () => {
  const { user } = useAuth();

  // State
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Fetch ideas on mount
  useEffect(() => {
    fetchIdeas();
  }, []);

  /**
   * Fetch ideas from API
   */
  const fetchIdeas = async () => {
    try {
      setLoading(true);
      setError('');

      const data = await getIdeas();

      // Ideas are already sorted by score on backend
      setIdeas(data.ideas || []);
    } catch (err) {
      setError(err.message || 'Failed to load ideas');
      console.error('Error fetching ideas:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handle vote update - refresh ideas
   */
  const handleVoteUpdate = async (ideaId) => {
    // Refetch ideas to get updated vote counts
    // Note: In production, you might want to update just the changed idea
    // For MVP, refetching all is simpler
    await fetchIdeas();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation Header */}
      <Navigation />

      {/* Main Content */}
      <main className="main-content max-w-7xl mx-auto py-8">
        {/* Page Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-3xl font-bold text-gray-900">All Ideas</h2>
            <p className="mt-2 text-gray-600">
              Vote on ideas to help prioritize features
            </p>
          </div>

          {/* Submit Button */}
          <Link
            to="/submit"
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg shadow-sm transition-colors"
          >
            Submit New Idea
          </Link>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-gray-300 border-t-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading ideas...</p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="bg-red-50 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
            <button
              onClick={fetchIdeas}
              className="ml-4 text-red-800 underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && ideas.length === 0 && (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              No ideas yet
            </h3>
            <p className="mt-2 text-gray-600">
              Be the first to submit an idea!
            </p>
            <Link
              to="/submit"
              className="mt-6 inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg"
            >
              Submit an Idea
            </Link>
          </div>
        )}

        {/* Ideas List */}
        {!loading && !error && ideas.length > 0 && (
          <div className="space-y-4">
            {ideas.map((idea) => (
              <IdeaCard
                key={idea.id}
                idea={idea}
                onVoteUpdate={handleVoteUpdate}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default IdeasPage;
