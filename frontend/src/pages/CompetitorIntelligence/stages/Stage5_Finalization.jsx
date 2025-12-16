/**
 * Stage5_Finalization
 *
 * Final review and submission stage with:
 * - Review all approved ideas
 * - Final editing opportunity
 * - Submit to main voting system
 * - Success confirmation and navigation
 */

import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import api from '../../../services/api';

const Stage5_Finalization = ({
  sessionId,
  onBack
}) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [approvedIdeas, setApprovedIdeas] = useState([]);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [submittedIdeaIds, setSubmittedIdeaIds] = useState([]);

  useEffect(() => {
    loadApprovedIdeas();
  }, [sessionId]);

  const loadApprovedIdeas = async () => {
    setLoading(true);
    try {
      const response = await api.get(
        `/competitor-intelligence/sessions/${sessionId}/generated-ideas`
      );
      const allIdeas = response.data.ideas || [];
      const approved = allIdeas.filter((idea) => idea.user_approved);
      setApprovedIdeas(approved);
    } catch (err) {
      console.error('Failed to load ideas:', err);
      setError('Failed to load approved ideas');
    } finally {
      setLoading(false);
    }
  };

  const submitToVotingSystem = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const response = await api.post(
        `/competitor-intelligence/sessions/${sessionId}/finalize`
      );

      if (response.data.status === 'success') {
        setSuccess(true);
        setSubmittedIdeaIds(response.data.ideas.map((i) => i.idea_id));
      }
    } catch (err) {
      console.error('Failed to submit ideas:', err);
      setError(err.response?.data?.detail || 'Failed to submit ideas to voting system');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (success) {
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
            Ideas Successfully Submitted!
          </h2>
          <p className="text-gray-600 mb-8">
            {approvedIdeas.length} {approvedIdeas.length === 1 ? 'idea has' : 'ideas have'} been submitted to your voting system.
          </p>
          <div className="flex gap-4 justify-center">
            <button
              onClick={() => navigate('/ideas')}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
            >
              View Ideas in Voting System
            </button>
            <button
              onClick={() => navigate('/competitor-intelligence')}
              className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300"
            >
              Start New Analysis
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Stage 5: Final Review & Submission</h2>
        <p className="text-gray-600">
          Review all approved ideas before submitting them to your voting system.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {approvedIdeas.length === 0 ? (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-6 py-4 rounded-lg">
          <p className="font-semibold mb-2">No Ideas Approved</p>
          <p>You haven't approved any ideas yet. Go back to Stage 4 to approve ideas for submission.</p>
          <button
            onClick={onBack}
            className="mt-4 bg-yellow-600 text-white px-4 py-2 rounded hover:bg-yellow-700"
          >
            ← Back to Idea Generation
          </button>
        </div>
      ) : (
        <>
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-green-900 text-lg mb-1">
                  Ready to Submit: {approvedIdeas.length} {approvedIdeas.length === 1 ? 'Idea' : 'Ideas'}
                </p>
                <p className="text-sm text-green-700">
                  These ideas will be added to your main voting system with source_type='competitor_automated'.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-4 mb-8">
            {approvedIdeas.map((idea, index) => (
              <div key={idea.id} className="bg-white rounded-lg shadow border border-gray-200 p-6">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <div className="h-10 w-10 bg-blue-100 rounded-full flex items-center justify-center">
                      <span className="text-blue-600 font-bold">{index + 1}</span>
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-1 rounded">
                        From: {idea.competitor_name}
                      </span>
                      <span className="text-xs text-gray-500">•</span>
                      <span className="text-xs text-gray-600">{idea.feature_name}</span>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">What</h4>
                        <p className="text-gray-900">{idea.what}</p>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Why</h4>
                        <p className="text-gray-900">{idea.why}</p>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Use Case</h4>
                        <p className="text-gray-900">{idea.use_case}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-white rounded-lg shadow border border-gray-200 p-6 mb-8">
            <h3 className="font-semibold text-gray-900 mb-4">What Happens When You Submit?</h3>
            <ul className="space-y-2 text-gray-700">
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-1">✓</span>
                <span>Ideas will be added to your main voting system</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-1">✓</span>
                <span>Source type will be marked as "competitor_automated"</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-1">✓</span>
                <span>Users can view and vote on these ideas alongside manually submitted ideas</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-1">✓</span>
                <span>Full traceability: Ideas link back to competitor features and analysis sessions</span>
              </li>
            </ul>
          </div>

          <div className="flex justify-between">
            <button
              onClick={onBack}
              disabled={submitting}
              className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300 disabled:opacity-50"
            >
              ← Back to Edit Ideas
            </button>
            <button
              onClick={submitToVotingSystem}
              disabled={submitting}
              className="bg-green-600 text-white px-8 py-3 rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-semibold"
            >
              {submitting ? (
                <>
                  <span className="inline-block animate-spin mr-2">⚙️</span>
                  Submitting...
                </>
              ) : (
                `Submit ${approvedIdeas.length} ${approvedIdeas.length === 1 ? 'Idea' : 'Ideas'} to Voting System`
              )}
            </button>
          </div>
        </>
      )}
    </div>
  );
};

Stage5_Finalization.propTypes = {
  sessionId: PropTypes.number.isRequired,
  onBack: PropTypes.func.isRequired,
};

export default Stage5_Finalization;
