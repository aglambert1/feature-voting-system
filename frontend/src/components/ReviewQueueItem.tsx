/**
 * ReviewQueueItem Component
 *
 * Individual item in the PM review queue with:
 * - Title and summary
 * - Status and priority badges
 * - Action buttons (approve, reject, defer)
 * - Metadata display
 */

import { useState } from 'react';
import type { PMReviewQueueItem, ApiError } from '../types';
import { ReviewQueueType, ReviewQueueStatus, ReviewQueuePriority, AlertType } from '../types';
import {
  approveQueueItem,
  rejectQueueItem,
  deferQueueItem,
  startReviewQueueItem,
} from '../services/api';

interface ReviewQueueItemProps {
  item: PMReviewQueueItem;
  onUpdate: (updatedItem: PMReviewQueueItem) => void;
  onError: (error: string) => void;
}

const ReviewQueueItem = ({ item, onUpdate, onError }: ReviewQueueItemProps) => {
  const [loading, setLoading] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const [notes, setNotes] = useState('');

  const handleAction = async (
    action: 'approve' | 'reject' | 'defer' | 'start-review'
  ) => {
    setLoading(true);
    try {
      let updatedItem: PMReviewQueueItem;
      switch (action) {
        case 'approve':
          updatedItem = await approveQueueItem(item.id, notes || undefined);
          break;
        case 'reject':
          updatedItem = await rejectQueueItem(item.id, notes || undefined);
          break;
        case 'defer':
          updatedItem = await deferQueueItem(item.id, notes || undefined);
          break;
        case 'start-review':
          updatedItem = await startReviewQueueItem(item.id);
          break;
      }
      onUpdate(updatedItem);
      setShowNotes(false);
      setNotes('');
    } catch (err) {
      onError((err as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  const getQueueTypeLabel = (type: ReviewQueueType) => {
    switch (type) {
      case ReviewQueueType.IDEA:
        return 'Idea';
      case ReviewQueueType.COMPETITIVE_ALERT:
        return 'Alert';
      case ReviewQueueType.REPORT:
        return 'Report';
      default:
        return type;
    }
  };

  const getQueueTypeColor = (type: ReviewQueueType) => {
    switch (type) {
      case ReviewQueueType.IDEA:
        return 'bg-purple-100 text-purple-700';
      case ReviewQueueType.COMPETITIVE_ALERT:
        return 'bg-orange-100 text-orange-700';
      case ReviewQueueType.REPORT:
        return 'bg-blue-100 text-blue-700';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  const getPriorityColor = (priority: ReviewQueuePriority) => {
    switch (priority) {
      case ReviewQueuePriority.URGENT:
        return 'bg-red-100 text-red-700';
      case ReviewQueuePriority.HIGH:
        return 'bg-orange-100 text-orange-700';
      case ReviewQueuePriority.NORMAL:
        return 'bg-gray-100 text-gray-700';
      case ReviewQueuePriority.LOW:
        return 'bg-gray-50 text-gray-500';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  const getAlertSeverityIcon = (severity: string | null) => {
    if (!severity) return null;
    switch (severity) {
      case 'critical':
        return <span className="text-red-600">●</span>;
      case 'warning':
        return <span className="text-yellow-600">●</span>;
      case 'info':
        return <span className="text-blue-600">●</span>;
      default:
        return null;
    }
  };

  const getAlertTypeLabel = (alertType: AlertType | null) => {
    if (!alertType) return null;
    switch (alertType) {
      case AlertType.NEW_COMPETITOR:
        return 'New Competitor';
      case AlertType.COMPETITOR_REMOVED:
        return 'Competitor Removed';
      case AlertType.MAJOR_FEATURE_LAUNCH:
        return 'New Features';
      case AlertType.FEATURE_REMOVED:
        return 'Features Removed';
      case AlertType.PRICING_CHANGE:
        return 'Pricing Change';
      case AlertType.TREND_DETECTED:
        return 'Trend Detected';
      default:
        return alertType;
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffHours < 1) {
      return 'Just now';
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else if (diffDays < 7) {
      return `${diffDays}d ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const isPending = item.status === ReviewQueueStatus.PENDING;
  const isInReview = item.status === ReviewQueueStatus.IN_REVIEW;
  const canTakeAction = isPending || isInReview;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <span className={`text-xs px-2 py-0.5 rounded-full ${getQueueTypeColor(item.queue_type)}`}>
              {getQueueTypeLabel(item.queue_type)}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${getPriorityColor(item.priority)}`}>
              {item.priority}
            </span>
            {item.alert_severity && (
              <span className="flex items-center space-x-1 text-xs">
                {getAlertSeverityIcon(item.alert_severity)}
                <span className="capitalize">{item.alert_severity}</span>
              </span>
            )}
          </div>
          <h3 className="font-medium text-gray-900">{item.title}</h3>
        </div>
        <span className="text-xs text-gray-500">{formatDate(item.created_at)}</span>
      </div>

      {/* Summary */}
      {item.summary && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-2">{item.summary}</p>
      )}

      {/* Alert type for competitive alerts */}
      {item.alert_type && (
        <div className="text-sm text-gray-600 mb-3">
          <span className="font-medium">Alert Type:</span> {getAlertTypeLabel(item.alert_type)}
        </div>
      )}

      {/* Metadata */}
      {item.metadata && Object.keys(item.metadata).length > 0 && (
        <div className="text-xs text-gray-500 mb-3 p-2 bg-gray-50 rounded">
          {item.queue_type === ReviewQueueType.COMPETITIVE_ALERT && item.metadata.competitor_name && (
            <div>
              <span className="font-medium">Competitor:</span> {item.metadata.competitor_name}
            </div>
          )}
          {item.metadata.new_features_count > 0 && (
            <div className="text-green-600">+{item.metadata.new_features_count} new features</div>
          )}
          {item.metadata.removed_features_count > 0 && (
            <div className="text-red-600">-{item.metadata.removed_features_count} removed features</div>
          )}
          {item.queue_type === ReviewQueueType.IDEA && item.metadata.confidence && (
            <div>
              <span className="font-medium">Confidence:</span> {Math.round(item.metadata.confidence * 100)}%
            </div>
          )}
          {item.metadata.recommendation && (
            <div>
              <span className="font-medium">Recommendation:</span> {item.metadata.recommendation}
            </div>
          )}
        </div>
      )}

      {/* Notes input */}
      {showNotes && (
        <div className="mb-3">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add notes (optional)..."
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={2}
          />
        </div>
      )}

      {/* Actions */}
      {canTakeAction && (
        <div className="flex items-center space-x-2 pt-2 border-t border-gray-100">
          {isPending && (
            <button
              onClick={() => handleAction('start-review')}
              disabled={loading}
              className="px-3 py-1.5 text-sm text-gray-700 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
            >
              Start Review
            </button>
          )}
          {isInReview && (
            <>
              <button
                onClick={() => {
                  if (showNotes) {
                    handleAction('approve');
                  } else {
                    setShowNotes(true);
                  }
                }}
                disabled={loading}
                className="px-3 py-1.5 text-sm text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50"
              >
                {loading ? 'Processing...' : 'Approve'}
              </button>
              <button
                onClick={() => {
                  if (showNotes) {
                    handleAction('reject');
                  } else {
                    setShowNotes(true);
                  }
                }}
                disabled={loading}
                className="px-3 py-1.5 text-sm text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50"
              >
                Reject
              </button>
              <button
                onClick={() => {
                  if (showNotes) {
                    handleAction('defer');
                  } else {
                    setShowNotes(true);
                  }
                }}
                disabled={loading}
                className="px-3 py-1.5 text-sm text-gray-700 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
              >
                Defer
              </button>
              {showNotes && (
                <button
                  onClick={() => {
                    setShowNotes(false);
                    setNotes('');
                  }}
                  className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700"
                >
                  Cancel
                </button>
              )}
            </>
          )}
        </div>
      )}

      {/* Completed status */}
      {!canTakeAction && (
        <div className="text-sm text-gray-500 pt-2 border-t border-gray-100">
          <span className="capitalize">{item.status}</span>
          {item.reviewed_at && (
            <span> on {new Date(item.reviewed_at).toLocaleDateString()}</span>
          )}
          {item.review_notes && (
            <div className="mt-1 text-xs italic">"{item.review_notes}"</div>
          )}
        </div>
      )}
    </div>
  );
};

export default ReviewQueueItem;
