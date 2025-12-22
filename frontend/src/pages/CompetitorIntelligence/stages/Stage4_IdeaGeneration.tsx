/**
 * Stage4_IdeaGeneration
 *
 * Idea generation stage with:
 * - AI-powered idea generation from selected features
 * - Inline editing of generated ideas
 * - Approval/rejection workflow
 * - Link to source competitor features
 */

import { useState, useEffect, ChangeEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../../services/api';

interface GeneratedIdea {
  id: number;
  what: string;
  why: string;
  use_case: string;
  competitor_name: string;
  feature_name: string;
  user_approved: boolean;
  user_edited: boolean;
}

interface EditForm {
  what: string;
  why: string;
  use_case: string;
}

interface Stage4Props {
  sessionId: number;
  onComplete: () => void;
  onBack: () => void;
}

const Stage4_IdeaGeneration = ({
  sessionId,
  onComplete,
  onBack
}: Stage4Props) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [ideas, setIdeas] = useState<GeneratedIdea[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditForm>({
    what: '',
    why: '',
    use_case: ''
  });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  useEffect(() => {
    loadGeneratedIdeas();
  }, [sessionId]);

  const loadGeneratedIdeas = async (): Promise<void> => {
    setLoading(true);
    try {
      const response = await api.get<{ ideas: GeneratedIdea[] }>(
        `/product-intelligence/sessions/${sessionId}/generated-ideas`
      );
      setIdeas(response.data.ideas || []);
    } catch (err: any) {
      console.error('Failed to load ideas:', err);
      // If no ideas exist yet, that's okay
      if (err.response?.status !== 404) {
        setError('Failed to load generated ideas');
      }
    } finally {
      setLoading(false);
    }
  };

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

  const startEdit = (idea: GeneratedIdea): void => {
    setEditingId(idea.id);
    setEditForm({
      what: idea.what,
      why: idea.why,
      use_case: idea.use_case
    });

    // If idea was previously approved, unapprove it when editing starts
    if (idea.user_approved) {
      toggleApproval(idea.id, true);
    }
  };

  const cancelEdit = async (idea: GeneratedIdea): Promise<void> => {
    setEditingId(null);
    setEditForm({ what: '', why: '', use_case: '' });

    // Reload to restore original approval state if user cancels
    await loadGeneratedIdeas();
  };

  const saveEdit = async (ideaId: number): Promise<void> => {
    try {
      await api.put(
        `/product-intelligence/sessions/generated-ideas/${ideaId}`,
        editForm
      );
      await loadGeneratedIdeas();
      setEditingId(null);
    } catch (err: any) {
      console.error('Failed to save edit:', err);
      setError('Failed to save changes');
    }
  };

  const toggleApproval = async (ideaId: number, currentApproval: boolean): Promise<void> => {
    try {
      await api.post(
        '/product-intelligence/sessions/generated-ideas/approve',
        {
          idea_ids: [ideaId],
          approved: !currentApproval
        }
      );
      await loadGeneratedIdeas();
    } catch (err: any) {
      console.error('Failed to toggle approval:', err);
      setError('Failed to update approval status');
    }
  };

  const submitToVotingSystem = async (): Promise<void> => {
    setSubmitting(true);
    setError(null);
    try {
      const response = await api.post(
        `/product-intelligence/sessions/${sessionId}/finalize`
      );

      if (response.data.status === 'success') {
        setSuccess(true);
      }
    } catch (err: any) {
      console.error('Failed to submit ideas:', err);
      setError(err.response?.data?.detail || 'Failed to submit ideas to voting system');
    } finally {
      setSubmitting(false);
    }
  };

  const approvedCount = ideas.filter(i => i.user_approved).length;
  const canSubmit = approvedCount > 0 && editingId === null;

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (success) {
    const approvedIdeas = ideas.filter(i => i.user_approved);
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
                          disabled={isEditing}
                          className={`px-4 py-2 rounded font-medium ${
                            isEditing
                              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                              : idea.user_approved
                              ? 'bg-green-100 text-green-700 hover:bg-green-200'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                          }`}
                          title={isEditing ? 'Save or cancel changes before approving' : ''}
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
                            onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setEditForm({ ...editForm, what: e.target.value })}
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
                            onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setEditForm({ ...editForm, why: e.target.value })}
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
                            onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setEditForm({ ...editForm, use_case: e.target.value })}
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
                            onClick={() => cancelEdit(idea)}
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
          disabled={submitting}
          className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ← Back to Features
        </button>
        <button
          onClick={submitToVotingSystem}
          disabled={!canSubmit || submitting}
          className="bg-green-600 text-white px-8 py-3 rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-semibold"
          title={editingId !== null ? 'Save or cancel changes before submitting' : !canSubmit ? 'Approve at least one idea to submit' : ''}
        >
          {submitting ? (
            <>
              <span className="inline-block animate-spin mr-2">⚙️</span>
              Submitting...
            </>
          ) : (
            `Submit ${approvedCount} ${approvedCount === 1 ? 'Idea' : 'Ideas'} to Voting System`
          )}
        </button>
      </div>
    </div>
  );
};

export default Stage4_IdeaGeneration;
