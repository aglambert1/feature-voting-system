/**
 * IdeaResponseModal Component
 *
 * Structured response modal for PO to respond to ideas.
 * Features:
 * - 1-click accept for agent recommendations
 * - Status selection (Approved, Duplicate, Feature Exists, Not Appropriate)
 * - Duplicate idea selector
 * - Comment textarea with agent suggestion pre-fill
 */

import { useState, useEffect, useRef } from 'react';
import {
  IdeaResponseStatus,
  TriageRecommendation,
  SimilarIdea,
} from '../types';
import { respondToIdea, getTriageRecommendation, findSimilarIdeas } from '../services/api';
import { formatDateTime } from '../utils/date';

interface IdeaResponseModalProps {
  ideaId: number;
  ideaTitle: string;
  productId: number;
  onClose: () => void;
  onSuccess: () => void;
}

const STATUS_OPTIONS: { value: IdeaResponseStatus; label: string; color: string; description: string }[] = [
  { value: 'approved', label: 'Accept', color: 'green', description: 'Approve for voting' },
  { value: 'duplicate', label: 'Duplicate', color: 'yellow', description: 'Similar idea exists' },
  { value: 'feature_exists', label: 'Feature Exists', color: 'orange', description: 'Already implemented' },
  { value: 'not_appropriate', label: 'Not Appropriate', color: 'red', description: 'Off-topic or inappropriate' },
];

export default function IdeaResponseModal({
  ideaId,
  ideaTitle,
  productId,
  onClose,
  onSuccess,
}: IdeaResponseModalProps) {
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Recommendation from agent
  const [recommendation, setRecommendation] = useState<TriageRecommendation | null>(null);

  // Form state
  const [selectedStatus, setSelectedStatus] = useState<IdeaResponseStatus | null>(null);
  const [initialStatus, setInitialStatus] = useState<IdeaResponseStatus | null>(null);
  const [comment, setComment] = useState('');
  const [duplicateOfIdeaId, setDuplicateOfIdeaId] = useState<number | null>(null);

  // Similar ideas for duplicate selection
  const [similarIdeas, setSimilarIdeas] = useState<SimilarIdea[]>([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);
  const similarFetchedRef = useRef(false);

  // Source summary drill-down toggles
  const [showVoters, setShowVoters] = useState(false);
  const [showCompetitors, setShowCompetitors] = useState(false);
  const [showExistingFeature, setShowExistingFeature] = useState(false);
  // Default expanded when no linkage exists (needs PM attention); collapsed when linked
  const [needExpanded, setNeedExpanded] = useState(false);

  // Track if the current form values match the AI recommendation
  const [isUsingAiRecommendation, setIsUsingAiRecommendation] = useState(false);

  // Fetch recommendation and similar ideas on mount
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Fetch agent recommendation (also includes current response if already responded)
        const rec = await getTriageRecommendation(ideaId);
        setRecommendation(rec);
        // Expand by default only when no linkage — needs PM attention
        setNeedExpanded(!rec.job_linkage);

        // If already responded, show the current response in the form
        if (rec.current_response && rec.current_response.status) {
          setSelectedStatus(rec.current_response.status);
          setInitialStatus(rec.current_response.status);  // Track initial for comparison
          setComment(rec.current_response.comment || '');
          if (rec.duplicate_of_idea_id) {
            setDuplicateOfIdeaId(rec.duplicate_of_idea_id);
          }
          setIsUsingAiRecommendation(false);
        }
        // Otherwise, pre-fill form if recommendation exists (AI recommendation mode)
        else if (rec.has_recommendation) {
          // Pre-select status only if agent made a specific recommendation
          // (agent can recommend "review" which means "you decide" - no status pre-selected)
          if (rec.recommended_status) {
            setSelectedStatus(rec.recommended_status);
          }
          setInitialStatus(null);  // No initial response
          // Always pre-fill the suggested comment if available
          setComment(rec.suggested_comment || '');
          if (rec.duplicate_of_idea_id) {
            setDuplicateOfIdeaId(rec.duplicate_of_idea_id);
          }
          // Show AI recommendation context if we have reasoning or suggested comment
          setIsUsingAiRecommendation(!!rec.reasoning || !!rec.suggested_comment);
        }

        // If recommendation has similar ideas, use those
        if (rec.similar_ideas && rec.similar_ideas.length > 0) {
          setSimilarIdeas(rec.similar_ideas.map(s => ({
            id: s.id,
            title: s.title,
            what_description: '',
            similarity_score: s.similarity_score,
          })));
        }
      } catch (err) {
        console.error('Failed to fetch recommendation:', err);
        // Not critical - continue without recommendation
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ideaId]);

  // Fetch similar ideas when status changes to 'duplicate'
  useEffect(() => {
    if (selectedStatus === 'duplicate' && !similarFetchedRef.current) {
      similarFetchedRef.current = true;
      const fetchSimilar = async () => {
        setLoadingSimilar(true);
        try {
          const ideas = await findSimilarIdeas(ideaTitle, productId);
          setSimilarIdeas(ideas.filter(idea => idea.id !== ideaId));
        } catch (err) {
          console.error('Failed to fetch similar ideas:', err);
        } finally {
          setLoadingSimilar(false);
        }
      };
      fetchSimilar();
    }
  }, [selectedStatus, ideaTitle, productId, ideaId]);

  const handleSubmit = async () => {
    if (!selectedStatus) {
      setError('Please select a status');
      return;
    }

    if (!comment.trim()) {
      setError('Please provide a comment');
      return;
    }

    if (selectedStatus === 'duplicate' && !duplicateOfIdeaId) {
      setError('Please select the original idea this is a duplicate of');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await respondToIdea(ideaId, {
        status: selectedStatus,
        comment: comment.trim(),
        duplicate_of_idea_id: selectedStatus === 'duplicate' ? duplicateOfIdeaId! : undefined,
      });
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Failed to submit response');
    } finally {
      setSubmitting(false);
    }
  };

  // Handle status change - clear comment when changing from existing status
  const handleStatusChange = (newStatus: IdeaResponseStatus) => {
    if (newStatus !== selectedStatus) {
      // If there was an existing response (initialStatus set), clear the comment
      // This forces PO to provide a new comment when changing status
      if (initialStatus !== null && newStatus !== initialStatus) {
        setComment('');
      }
      setSelectedStatus(newStatus);
      // Clear duplicate selection if not duplicate status
      if (newStatus !== 'duplicate') {
        setDuplicateOfIdeaId(null);
      }
      // Clear AI recommendation indicator if status differs from recommendation
      if (recommendation?.recommended_status && newStatus !== recommendation.recommended_status) {
        setIsUsingAiRecommendation(false);
      }
    }
  };

  // Handle comment change - clear AI recommendation indicator if comment differs
  const handleCommentChange = (newComment: string) => {
    setComment(newComment);
    // If comment differs from AI suggestion, clear the indicator
    if (recommendation?.suggested_comment && newComment !== recommendation.suggested_comment) {
      setIsUsingAiRecommendation(false);
    }
  };

  const getStatusButtonClass = (status: IdeaResponseStatus) => {
    const isSelected = selectedStatus === status;
    const baseClass = 'px-4 py-2 rounded-lg font-medium text-sm transition-colors flex items-center gap-2';

    if (isSelected) {
      switch (status) {
        case 'approved':
          return `${baseClass} bg-green-600 text-white`;
        case 'duplicate':
          return `${baseClass} bg-yellow-500 text-white`;
        case 'feature_exists':
          return `${baseClass} bg-orange-500 text-white`;
        case 'not_appropriate':
          return `${baseClass} bg-red-600 text-white`;
      }
    }

    return `${baseClass} bg-gray-100 text-gray-700 hover:bg-gray-200`;
  };

  const confidencePercent = recommendation?.confidence
    ? Math.round(recommendation.confidence * 100)
    : null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose}></div>

      {/* Modal */}
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Respond to Idea</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4">
            {/* Idea title */}
            <div className="mb-6">
              <p className="text-sm text-gray-500">Responding to:</p>
              <p className="text-lg font-medium text-gray-900">{ideaTitle}</p>
            </div>

            {loading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : (
              <>
                {/* Current Response Info (when editing) */}
                {recommendation?.current_response && (
                  <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 p-2 bg-blue-100 rounded-lg">
                        <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </div>
                      <div className="flex-1">
                        <div className="font-medium text-blue-900 mb-1">Editing Previous Response</div>
                        <p className="text-sm text-blue-700">
                          This idea was previously responded to. You can modify the response below.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Source Summary Section */}
                {recommendation?.source_summary && (
                  <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
                    <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                      Source Summary
                    </h3>

                    <div className="grid grid-cols-2 gap-4">
                      {/* Votes Summary */}
                      <div>
                        <button
                          onClick={() => setShowVoters(!showVoters)}
                          className="w-full text-left p-3 bg-white rounded-lg border border-gray-200 hover:border-blue-300 transition-colors"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-600">Votes</span>
                            <svg
                              className={`w-4 h-4 text-gray-400 transition-transform ${showVoters ? 'rotate-180' : ''}`}
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                          <div className="mt-1">
                            <span className="text-2xl font-bold text-gray-900">
                              {recommendation.source_summary.vote_count}
                            </span>
                            <span className="text-sm text-gray-500 ml-1">
                              upvotes
                            </span>
                          </div>
                        </button>

                        {/* Voter drill-down */}
                        {showVoters && recommendation.source_summary.voters.length > 0 && (
                          <div className="mt-2 p-3 bg-white rounded-lg border border-gray-200">
                            <p className="text-xs text-gray-500 mb-2">Voters who upvoted:</p>
                            <div className="flex flex-wrap gap-1">
                              {recommendation.source_summary.voters.map((voter) => (
                                <span
                                  key={voter.id}
                                  className="inline-flex items-center px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full"
                                >
                                  {voter.username}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {showVoters && recommendation.source_summary.voters.length === 0 && (
                          <div className="mt-2 p-3 bg-white rounded-lg border border-gray-200">
                            <p className="text-xs text-gray-500">No votes yet</p>
                          </div>
                        )}
                      </div>

                      {/* Competitors Summary */}
                      <div>
                        <button
                          onClick={() => setShowCompetitors(!showCompetitors)}
                          className="w-full text-left p-3 bg-white rounded-lg border border-gray-200 hover:border-blue-300 transition-colors"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-600">Competitors</span>
                            <svg
                              className={`w-4 h-4 text-gray-400 transition-transform ${showCompetitors ? 'rotate-180' : ''}`}
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                          <div className="mt-1">
                            <span className="text-2xl font-bold text-gray-900">
                              {recommendation.source_summary.competitors_with_feature.length}
                            </span>
                            <span className="text-sm text-gray-500 ml-1">
                              have this feature
                            </span>
                          </div>
                          {recommendation.source_summary.competitive_urgency && (
                            <div className="mt-1">
                              <span className={`text-xs px-2 py-0.5 rounded-full ${
                                recommendation.source_summary.competitive_urgency === 'high'
                                  ? 'bg-red-100 text-red-800'
                                  : recommendation.source_summary.competitive_urgency === 'medium'
                                  ? 'bg-yellow-100 text-yellow-800'
                                  : 'bg-green-100 text-green-800'
                              }`}>
                                {recommendation.source_summary.competitive_urgency} urgency
                              </span>
                            </div>
                          )}
                        </button>

                        {/* Competitor drill-down */}
                        {showCompetitors && recommendation.source_summary.competitors_with_feature.length > 0 && (
                          <div className="mt-2 p-3 bg-white rounded-lg border border-gray-200">
                            <p className="text-xs text-gray-500 mb-2">Competitors with this feature:</p>
                            <div className="space-y-1">
                              {recommendation.source_summary.competitors_with_feature.map((competitor, index) => (
                                <div
                                  key={index}
                                  className="flex items-center gap-2 text-sm"
                                >
                                  <svg className="w-4 h-4 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                  </svg>
                                  <span className="text-gray-700">{competitor}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {showCompetitors && recommendation.source_summary.competitors_with_feature.length === 0 && (
                          <div className="mt-2 p-3 bg-white rounded-lg border border-gray-200">
                            <p className="text-xs text-gray-500">No competitors found with this feature</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Existing Feature Match Alert */}
                    {recommendation.source_summary.existing_feature && (
                      <div className="mt-4">
                        <button
                          onClick={() => setShowExistingFeature(!showExistingFeature)}
                          className="w-full text-left p-3 bg-orange-50 rounded-lg border border-orange-200 hover:border-orange-300 transition-colors"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <svg className="w-5 h-5 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                              </svg>
                              <span className="text-sm font-medium text-orange-800">Similar Existing Feature Detected</span>
                            </div>
                            <svg
                              className={`w-4 h-4 text-orange-400 transition-transform ${showExistingFeature ? 'rotate-180' : ''}`}
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                          <p className="mt-1 text-sm text-orange-700">
                            This idea may overlap with: <strong>{recommendation.source_summary.existing_feature.feature_name}</strong>
                          </p>
                        </button>

                        {/* Existing feature details */}
                        {showExistingFeature && (
                          <div className="mt-2 p-3 bg-white rounded-lg border border-orange-200">
                            <div className="space-y-2">
                              <div>
                                <p className="text-xs text-gray-500 mb-1">Feature Name</p>
                                <p className="text-sm font-medium text-gray-900">
                                  {recommendation.source_summary.existing_feature.feature_name}
                                </p>
                              </div>
                              {recommendation.source_summary.existing_feature.feature_description && (
                                <div>
                                  <p className="text-xs text-gray-500 mb-1">Description</p>
                                  <p className="text-sm text-gray-700">
                                    {recommendation.source_summary.existing_feature.feature_description}
                                  </p>
                                </div>
                              )}
                              {(() => {
                                const url = recommendation.source_summary.existing_feature.source_url;
                                const isHttpUrl =
                                  typeof url === 'string' &&
                                  /^https?:\/\//i.test(url.trim());
                                if (!isHttpUrl) return null;
                                return (
                                  <div>
                                    <p className="text-xs text-gray-500 mb-1">Documentation</p>
                                    <a
                                      href={url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-sm text-blue-600 hover:text-blue-800 underline"
                                    >
                                      View documentation →
                                    </a>
                                  </div>
                                );
                              })()}
                              <div className="pt-2 border-t border-gray-100">
                                <p className="text-xs text-orange-600">
                                  <strong>Note:</strong> If competitor features offer additional capabilities beyond what exists today,
                                  consider accepting this idea as an enhancement rather than marking as "Feature Exists".
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Customer Need linkage — collapsible */}
                <div className="mb-6 border border-gray-200 rounded-lg overflow-hidden">
                  {/* Collapsed header — always visible */}
                  <button
                    type="button"
                    onClick={() => setNeedExpanded(e => !e)}
                    className="w-full flex items-center justify-between gap-2 px-4 py-2.5 bg-gray-50 hover:bg-gray-100 text-left transition"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex-shrink-0">Customer Need</span>
                      {recommendation?.job_linkage ? (
                        <>
                          <span className="text-xs font-mono bg-white border border-gray-200 text-gray-600 px-1.5 py-0.5 rounded flex-shrink-0">
                            {recommendation.job_linkage.job_id_key}
                          </span>
                          <span className="text-xs text-gray-500 truncate">
                            {recommendation.job_linkage.job_statement ?? ''}
                          </span>
                        </>
                      ) : (
                        <span className="text-xs text-amber-600 font-medium">No match — review needed</span>
                      )}
                    </div>
                    <span className="text-gray-400 text-xs flex-shrink-0">{needExpanded ? '▲' : '▼'}</span>
                  </button>

                  {/* Expanded detail */}
                  {needExpanded && (
                    <div className="px-4 py-3 bg-white border-t border-gray-200">
                      {recommendation?.job_linkage ? (
                        <p className="text-sm text-gray-800 mb-3">
                          {recommendation.job_linkage.job_statement ?? recommendation.job_linkage.job_id_key}
                        </p>
                      ) : (
                        <p className="text-sm text-gray-500 italic mb-3">
                          No customer need matched this idea. Visit the Job Map to assign one or add a new need.
                        </p>
                      )}
                      <a
                        href={`/product-intelligence/products/${productId}/job-map?returnTo=idea/${ideaId}`}
                        className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                      >
                        {recommendation?.job_linkage ? 'Review in Job Map →' : 'Open Job Map →'}
                      </a>
                    </div>
                  )}
                </div>

                {/* AI Agent Recommendation Banner - visible when form is pre-filled with AI recommendation */}
                {isUsingAiRecommendation && recommendation?.has_recommendation && (
                  <div className="mb-6 p-3 bg-purple-50 border border-purple-200 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="flex-shrink-0 p-1.5 bg-purple-100 rounded-lg">
                        <svg className="w-4 h-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-purple-900 text-sm">AI Agent Recommendation</span>
                          {confidencePercent && (
                            <span className="text-xs px-2 py-0.5 bg-purple-200 text-purple-800 rounded-full">
                              {confidencePercent}% confident
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-purple-700 mt-0.5">
                          {recommendation.recommended_status
                            ? 'Form pre-filled with AI suggestion. Edit as needed — your response replaces the recommendation.'
                            : 'AI recommends PM review. Comment pre-filled — please select a status and edit as needed.'}
                        </p>
                      </div>
                      {recommendation.reasoning && (
                        <details className="flex-shrink-0">
                          <summary className="text-xs text-purple-600 cursor-pointer hover:text-purple-800 underline">
                            View reasoning
                          </summary>
                          <div className="absolute right-6 mt-1 w-80 p-3 bg-white rounded-lg border border-purple-200 shadow-lg z-10">
                            <p className="text-sm text-gray-600">
                              {recommendation.reasoning}
                            </p>
                          </div>
                        </details>
                      )}
                    </div>
                  </div>
                )}

                {/* Response Form - Always shown */}
                <>
                  {/* Status Selection */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-700 mb-3">
                      Select Response Status
                      {isUsingAiRecommendation && recommendation?.recommended_status && (
                        <span className="ml-2 text-xs text-purple-600 font-normal">
                          (AI suggested: {
                            recommendation.recommended_status === 'approved' ? 'Accept' :
                            recommendation.recommended_status === 'duplicate' ? 'Duplicate' :
                            recommendation.recommended_status === 'feature_exists' ? 'Feature Exists' :
                            'Not Appropriate'
                          })
                        </span>
                      )}
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {STATUS_OPTIONS.map((option) => (
                        <button
                          key={option.value}
                          onClick={() => handleStatusChange(option.value)}
                          className={getStatusButtonClass(option.value)}
                          title={option.description}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>

                    {/* Duplicate Selector */}
                    {selectedStatus === 'duplicate' && (
                      <div className="mb-6">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Select Original Idea
                        </label>
                        {loadingSimilar ? (
                          <div className="flex items-center gap-2 text-gray-500">
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                            Finding similar ideas...
                          </div>
                        ) : similarIdeas.length > 0 ? (
                          <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-200 rounded-lg p-2">
                            {similarIdeas.map((idea) => (
                              <label
                                key={idea.id}
                                className={`flex items-center p-2 rounded cursor-pointer transition-colors ${
                                  duplicateOfIdeaId === idea.id
                                    ? 'bg-blue-50 border border-blue-200'
                                    : 'hover:bg-gray-50 border border-transparent'
                                }`}
                              >
                                <input
                                  type="radio"
                                  name="duplicateOf"
                                  value={idea.id}
                                  checked={duplicateOfIdeaId === idea.id}
                                  onChange={() => setDuplicateOfIdeaId(idea.id)}
                                  className="mr-3"
                                />
                                <div className="flex-1">
                                  <p className="text-sm font-medium text-gray-900">{idea.title}</p>
                                  <p className="text-xs text-gray-500">
                                    {Math.round(idea.similarity_score * 100)}% similar
                                  </p>
                                </div>
                              </label>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500">No similar ideas found</p>
                        )}
                      </div>
                    )}

                  {/* Comment */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Response Comment <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      value={comment}
                      onChange={(e) => handleCommentChange(e.target.value)}
                      placeholder="Explain your response to the submitter..."
                      rows={4}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </>

                {/* Status History Timeline */}
                {recommendation?.status_history && recommendation.status_history.length > 0 && (
                  <div className="mb-6 border-t border-gray-200 pt-4">
                    <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Status History
                    </h3>
                    <div className="space-y-3">
                      {recommendation.status_history.map((entry, index) => (
                        <div
                          key={entry.id}
                          className={`relative pl-6 pb-3 ${
                            index < recommendation.status_history!.length - 1 ? 'border-l-2 border-gray-200' : ''
                          }`}
                        >
                          {/* Timeline dot */}
                          <div className={`absolute left-0 top-0 -translate-x-1/2 w-3 h-3 rounded-full ${
                            entry.is_automated ? 'bg-purple-500' : 'bg-blue-500'
                          }`} />

                          {/* Entry content */}
                          <div className="bg-gray-50 rounded-lg p-3">
                            <div className="flex items-center justify-between mb-1">
                              <div className="flex items-center gap-2">
                                {/* Status change badge */}
                                {entry.new_status && (
                                  <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded ${
                                    entry.new_status === 'approved' || entry.new_status === 'auto_approved' ? 'bg-green-100 text-green-800' :
                                    entry.new_status === 'pending' ? 'bg-gray-100 text-gray-800' :
                                    entry.new_status === 'needs_review' ? 'bg-yellow-100 text-yellow-800' :
                                    entry.new_status === 'duplicate' ? 'bg-yellow-100 text-yellow-800' :
                                    entry.new_status === 'feature_exists' ? 'bg-orange-100 text-orange-800' :
                                    entry.new_status === 'not_appropriate' ? 'bg-red-100 text-red-800' :
                                    'bg-gray-100 text-gray-800'
                                  }`}>
                                    {entry.new_status.replace('_', ' ')}
                                  </span>
                                )}

                                {/* Automated/Manual indicator */}
                                {entry.is_automated ? (
                                  <span className="text-xs text-purple-600 flex items-center gap-1">
                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                    </svg>
                                    AI Agent
                                  </span>
                                ) : entry.changed_by_username && (
                                  <span className="text-xs text-gray-500">
                                    by {entry.changed_by_username}
                                  </span>
                                )}

                                {/* Confidence if automated */}
                                {entry.confidence && (
                                  <span className="text-xs text-purple-600">
                                    ({entry.confidence}% confidence)
                                  </span>
                                )}
                              </div>

                              {/* Timestamp */}
                              <span className="text-xs text-gray-400">
                                {formatDateTime(entry.created_at)}
                              </span>
                            </div>

                            {/* Source of change */}
                            <div className="text-xs text-gray-500 mb-1">
                              {entry.change_source === 'submission' && 'Idea submitted'}
                              {entry.change_source === 'agent_triage' && 'Agent triage analysis'}
                              {entry.change_source === 'po_response' && 'PO response'}
                              {entry.change_source === 'po_edit' && 'PO edited response'}
                            </div>

                            {/* Comment if present */}
                            {entry.comment && (
                              <p className="text-sm text-gray-600 italic mt-2">
                                "{entry.comment}"
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Error */}
                {error && (
                  <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
                    {error}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          {!loading && (
            <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg font-medium hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting || !selectedStatus || !comment.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Submitting...' : 'Submit Response'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
