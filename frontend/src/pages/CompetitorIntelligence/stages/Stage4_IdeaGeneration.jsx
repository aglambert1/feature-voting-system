/**
 * Stage4_IdeaGeneration
 *
 * Idea generation stage with:
 * - AI-powered idea generation from selected features
 * - Inline editing of generated ideas
 * - Approval/rejection workflow
 * - Link to source competitor features
 */

import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import api from '../../../services/api';

const Stage4_IdeaGeneration = ({
  sessionId,
  onComplete,
  onBack
}) => {
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [ideas, setIdeas] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({
    what: '',
    why: '',
    use_case: ''
  });
  const [error, setError] = useState(null);

  useEffect(() => {
    loadGeneratedIdeas();
  }, [sessionId]);

  const loadGeneratedIdeas = async () => {
    setLoading(true);
    try {
      const response = await api.get(
        `/product-intelligence/sessions/${sessionId}/generated-ideas`
      );
      setIdeas(response.data.ideas || []);
    } catch (err) {
      console.error('Failed to load ideas:', err);
      // If no ideas exist yet, that's okay
      if (err.response?.status !== 404) {
        setError('Failed to load generated ideas');
      }
    } finally {
      setLoading(false);
    }
  };

  const generateIdeas = async () => {
    setGenerating(true);
    setError(null);
    try {
      const response = await api.post(
        `/product-intelligence/sessions/${sessionId}/generate-ideas`
      );
      setIdeas(response.data.ideas || []);
    } catch (err) {
      console.error('Failed to generate ideas:', err);
      setError(err.response?.data?.detail || 'Failed to generate ideas');
    } finally {
      setGenerating(false);
    }
  };

  const startEdit = (idea) => {
    setEditingId(idea.id);
    setEditForm({
      what: idea.what,
      why: idea.why,
      use_case: idea.use_case
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm({ what: '', why: '', use_case: '' });
  };

  const saveEdit = async (ideaId) => {
    try {
      await api.put(
        `/product-intelligence/sessions/generated-ideas/${ideaId}`,
        editForm
      );
      await loadGeneratedIdeas();
      setEditingId(null);
    } catch (err) {
      console.error('Failed to save edit:', err);
      setError('Failed to save changes');
    }
  };

  const toggleApproval = async (ideaId, currentApproval) => {
    try {
      await api.post(
        '/product-intelligence/sessions/generated-ideas/approve',
        {
          idea_ids: [ideaId],
          approved: !currentApproval
        }
      );
      await loadGeneratedIdeas();
    } catch (err) {
      console.error('Failed to toggle approval:', err);
      setError('Failed to update approval status');
    }
  };

  const approvedCount = ideas.filter(i => i.user_approved).length;
  const canProceed = approvedCount > 0;

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
        <h2 className="text-2xl font-bold mb-2">Stage 4: Idea Generation</h2>
        <p className="text-gray-600">
          AI adapts competitor features into product-specific ideas for your voting system.
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
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-blue-900">
                  {ideas.length} ideas generated • {approvedCount} approved
                </p>
                <p className="text-sm text-blue-700">
                  Review and edit ideas below. Approved ideas will be submitted to your voting system.
                </p>
              </div>
              <button
                onClick={generateIdeas}
                disabled={generating}
                className="bg-white text-blue-600 px-4 py-2 rounded border border-blue-300 hover:bg-blue-50"
              >
                Regenerate
              </button>
            </div>
          </div>

          <div className="space-y-6">
            {ideas.map((idea) => {
              const isEditing = editingId === idea.id;

              return (
                <div
                  key={idea.id}
                  className={`bg-white rounded-lg shadow border-2 ${
                    idea.user_approved ? 'border-green-300' : 'border-gray-200'
                  }`}
                >
                  <div className="p-6">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-1 rounded">
                            From: {idea.competitor_name}
                          </span>
                          {idea.user_edited && (
                            <span className="text-xs font-semibold bg-blue-100 text-blue-700 px-2 py-1 rounded">
                              Edited
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">
                          Source: {idea.feature_name}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleApproval(idea.id, idea.user_approved)}
                          className={`px-4 py-2 rounded font-medium ${
                            idea.user_approved
                              ? 'bg-green-100 text-green-700 hover:bg-green-200'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                          }`}
                        >
                          {idea.user_approved ? '✓ Approved' : 'Approve'}
                        </button>
                      </div>
                    </div>

                    {/* Content */}
                    {isEditing ? (
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            What (What is this feature?)
                          </label>
                          <textarea
                            value={editForm.what}
                            onChange={(e) => setEditForm({ ...editForm, what: e.target.value })}
                            rows={3}
                            className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Why (Why is it valuable?)
                          </label>
                          <textarea
                            value={editForm.why}
                            onChange={(e) => setEditForm({ ...editForm, why: e.target.value })}
                            rows={3}
                            className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Use Case (How would users use it?)
                          </label>
                          <textarea
                            value={editForm.use_case}
                            onChange={(e) => setEditForm({ ...editForm, use_case: e.target.value })}
                            rows={3}
                            className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => saveEdit(idea.id)}
                            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                          >
                            Save Changes
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
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
                        <button
                          onClick={() => startEdit(idea)}
                          className="text-blue-600 hover:text-blue-700 font-medium text-sm"
                        >
                          ✏️ Edit Idea
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
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
        <button
          onClick={onComplete}
          disabled={!canProceed}
          className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Continue to Review ({approvedCount} approved) →
        </button>
      </div>
    </div>
  );
};

Stage4_IdeaGeneration.propTypes = {
  sessionId: PropTypes.number.isRequired,
  onComplete: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
};

export default Stage4_IdeaGeneration;
