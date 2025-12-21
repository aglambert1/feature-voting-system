/**
 * SessionSelectorModal Component
 *
 * Modal for selecting which previous session to compare against when running differential analysis.
 * Shows list of previous sessions with metadata (competitors count, features count, dates).
 * Includes mobile-responsive design with full-screen on mobile and overlay on desktop.
 */

import { useState } from 'react';

export interface SessionSummary {
  id: number;
  session_number: number;
  session_name: string | null;
  analysis_version: number | null;
  stage_completed: string | null;
  created_at: string;
  completed_at: string | null;
  competitors_count: number;
  features_count: number;
  has_competitors: boolean;
  has_features: boolean;
}

interface SessionSelectorModalProps {
  sessions: SessionSummary[];
  currentSessionId?: number | null;  // NEW: ID of current session (most recent)
  onSelect: (sessionId: number | null) => void;  // null = no comparison (full analysis)
  onCancel: () => void;
}

const SessionSelectorModal = ({ sessions, currentSessionId, onSelect, onCancel }: SessionSelectorModalProps) => {
  // Default to most recent session with competitors (excluding current)
  const previousSessions = sessions.filter(s => s.id !== currentSessionId);
  const currentSession = sessions.find(s => s.id === currentSessionId);
  const defaultSessionId = currentSession?.id || previousSessions.find(s => s.has_competitors)?.id || previousSessions[0]?.id || null;
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(defaultSessionId);

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    // Mobile: shorter format
    if (window.innerWidth < 640) {
      if (diffDays === 0) return 'Today';
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays}d ago`;
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
    }

    // Desktop: full format with year
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const getStatusBadge = (session: SessionSummary) => {
    if (!session.has_competitors) {
      return (
        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
          No competitors selected
        </span>
      );
    }
    if (session.has_features) {
      return (
        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
          ✓ Complete
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
        ✓ Has competitors
      </span>
    );
  };

  const handleSelect = () => {
    if (selectedSessionId !== null) {
      onSelect(selectedSessionId);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-0 sm:p-4 z-50">
      <div className="bg-white w-full h-full sm:h-auto sm:max-h-[80vh] sm:w-full sm:max-w-2xl sm:rounded-lg overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-4 sm:p-6 border-b bg-gray-50">
          <h2 className="text-lg sm:text-xl font-bold text-gray-900">Select Previous Analysis to Compare</h2>
          <p className="text-sm text-gray-600 mt-1">
            Choose which previous competitor analysis to compare against
          </p>
        </div>

        {/* Scrollable session list */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          {sessions.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p>No previous competitor analyses found.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Current session option */}
              {currentSession && (
                <div className="pb-4 border-b border-gray-200">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Current Analysis</h3>
                  <button
                    onClick={() => setSelectedSessionId(currentSession.id)}
                    className={`w-full p-4 border-2 rounded-lg text-left transition-all min-h-[44px] sm:min-h-0 ${
                      selectedSessionId === currentSession.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0">
                      <div className="flex items-center gap-2">
                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                          selectedSessionId === currentSession.id
                            ? 'border-blue-500 bg-blue-500'
                            : 'border-gray-300'
                        }`}>
                          {selectedSessionId === currentSession.id && (
                            <div className="w-2 h-2 bg-white rounded-full"></div>
                          )}
                        </div>
                        <div>
                          <span className="font-semibold text-blue-600">
                            Analysis #{currentSession.session_number}
                          </span>
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded ml-2">
                            Most Recent
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="mt-2 ml-7 text-sm text-gray-600">
                      Compare against the current analysis to find new competitors since last discovery
                    </div>
                  </button>
                </div>
              )}

              {/* Previous analyses */}
              {previousSessions.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Previous Analyses</h3>
                  <div className="space-y-3">
                    {previousSessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => setSelectedSessionId(session.id)}
                  className={`w-full p-4 border-2 rounded-lg text-left transition-all min-h-[44px] sm:min-h-0 ${
                    selectedSessionId === session.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-blue-300'
                  } ${!session.has_competitors ? 'opacity-75' : ''}`}
                >
                  {/* Session info - stack on mobile, inline on desktop */}
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0">
                    <div className="flex items-center gap-2">
                      {/* Radio indicator */}
                      <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                        selectedSessionId === session.id
                          ? 'border-blue-500 bg-blue-500'
                          : 'border-gray-300'
                      }`}>
                        {selectedSessionId === session.id && (
                          <div className="w-2 h-2 bg-white rounded-full"></div>
                        )}
                      </div>

                      <div>
                        <span className="font-semibold text-gray-900">
                          Analysis #{session.session_number}
                        </span>
                        <span className="text-sm text-gray-600 ml-2">
                          {formatDate(session.created_at)}
                        </span>
                      </div>
                    </div>

                    <div className="ml-7 sm:ml-0">
                      {getStatusBadge(session)}
                    </div>
                  </div>

                  {/* Metadata - always stacked */}
                  <div className="mt-2 ml-7 text-sm">
                    <span className={session.competitors_count === 0 ? 'text-gray-400' : 'text-gray-600'}>
                      <span className="font-medium">{session.competitors_count}</span> competitor{session.competitors_count !== 1 ? 's' : ''}
                    </span>
                    {session.has_features && (
                      <>
                        <span className="text-gray-400"> • </span>
                        <span className="text-gray-600">
                          <span className="font-medium">{session.features_count}</span> feature{session.features_count !== 1 ? 's' : ''}
                        </span>
                      </>
                    )}
                  </div>

                  {/* Warning for sessions without competitors */}
                  {!session.has_competitors && (
                    <div className="mt-2 ml-7 text-xs text-yellow-700 bg-yellow-50 p-2 rounded border border-yellow-200">
                      ⚠ This analysis has no competitors. All discovered competitors will show as NEW.
                    </div>
                  )}
                </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer buttons - stack on mobile */}
        <div className="p-4 sm:p-6 border-t bg-gray-50 flex flex-col sm:flex-row gap-3 sm:justify-end">
          <button
            onClick={onCancel}
            className="w-full sm:w-auto px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors font-medium text-gray-700 min-h-[44px] sm:min-h-0"
          >
            Cancel
          </button>
          <button
            onClick={handleSelect}
            disabled={selectedSessionId === null}
            className={`w-full sm:w-auto px-6 py-2 rounded-lg font-medium min-h-[44px] sm:min-h-0 ${
              selectedSessionId === null
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700 transition-colors'
            }`}
          >
            Compare Selected
          </button>
        </div>
      </div>
    </div>
  );
};

export default SessionSelectorModal;
