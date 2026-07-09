/**
 * AgentJobStatus Component
 *
 * Displays job status for an agent: running state with progress,
 * or last completed/failed time.
 */

import { format, formatDistanceToNow } from 'date-fns';
import { JobStatus, JobType } from '../types';
import { useProductJobPolling } from '../hooks/useJobPolling';
import { parseUTCTimestamp } from '../utils/date';

interface AgentJobStatusProps {
  productId: number;
  jobTypes: JobType[];
  onJobComplete?: () => void;
  className?: string;
}

export default function AgentJobStatus({
  productId,
  jobTypes,
  onJobComplete,
  className = ''
}: AgentJobStatusProps) {
  const { activeJob, lastCompletedJob, loading } = useProductJobPolling({
    productId,
    jobTypes,
    onComplete: () => onJobComplete?.(),
  });

  if (loading) {
    return null;
  }

  // Show active job status
  if (activeJob) {
    const statusLabel = activeJob.status === JobStatus.RUNNING
      ? 'Running'
      : activeJob.status === JobStatus.QUEUED
        ? 'Queued'
        : 'Starting';

    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
          <span className="text-xs font-medium text-blue-600">
            {statusLabel}
          </span>
        </div>
        {activeJob.status === JobStatus.RUNNING && activeJob.progress_percent > 0 && (
          <div className="flex-1 max-w-24">
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${activeJob.progress_percent}%` }}
              />
            </div>
          </div>
        )}
        {activeJob.progress_message && (
          <span className="text-xs text-gray-500 truncate max-w-32">
            {activeJob.progress_message}
          </span>
        )}
      </div>
    );
  }

  // Show last completed job
  if (lastCompletedJob?.completed_at) {
    const completedDate = parseUTCTimestamp(lastCompletedJob.completed_at);
    const isSuccess = lastCompletedJob.status === JobStatus.SUCCESS;
    const timeAgo = formatDistanceToNow(completedDate, { addSuffix: true });

    return (
      <div className={`flex items-center gap-1.5 ${className}`}>
        {isSuccess ? (
          <>
            <svg className="w-3.5 h-3.5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span
              className="text-xs text-gray-500"
              title={`Completed ${format(completedDate, 'MMM d, yyyy h:mm a')}`}
            >
              Last run {timeAgo}
            </span>
          </>
        ) : (
          <>
            <svg className="w-3.5 h-3.5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <span
              className="text-xs text-red-600"
              title={lastCompletedJob.error_message || `Failed ${format(completedDate, 'MMM d, yyyy h:mm a')}`}
            >
              Failed {timeAgo}
            </span>
          </>
        )}
      </div>
    );
  }

  // No job history
  return (
    <div className={`text-xs text-gray-400 ${className}`}>
      Never run
    </div>
  );
}
