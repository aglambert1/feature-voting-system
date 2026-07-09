/**
 * JobStatusCard Component
 *
 * Displays the status of a background queue job with:
 * - Progress bar
 * - Status indicator
 * - Progress message
 * - Auto-polling for running jobs
 */

import type { QueueJob } from '../types';
import { JobStatus, JobType } from '../types';
import { isJobActive, useJobStatusPolling } from '../hooks/useJobPolling';
import { parseUTCTimestamp } from '../utils/date';

interface JobStatusCardProps {
  jobUuid: string;
  onComplete?: (job: QueueJob) => void;
  onError?: (job: QueueJob) => void;
  showDetails?: boolean;
  compact?: boolean;
}

const JobStatusCard = ({
  jobUuid,
  onComplete,
  onError,
  showDetails = false,
  compact = false,
}: JobStatusCardProps) => {
  const { job, loading, error } = useJobStatusPolling(jobUuid, { onComplete, onError });

  const getStatusColor = (status: JobStatus) => {
    switch (status) {
      case JobStatus.SUCCESS:
        return 'bg-green-500';
      case JobStatus.FAILURE:
        return 'bg-red-500';
      case JobStatus.RUNNING:
        return 'bg-blue-500';
      case JobStatus.QUEUED:
      case JobStatus.PENDING:
        return 'bg-yellow-500';
      case JobStatus.CANCELLED:
        return 'bg-gray-500';
      default:
        return 'bg-gray-400';
    }
  };

  const getStatusText = (status: JobStatus) => {
    switch (status) {
      case JobStatus.SUCCESS:
        return 'Completed';
      case JobStatus.FAILURE:
        return 'Failed';
      case JobStatus.RUNNING:
        return 'Running';
      case JobStatus.QUEUED:
        return 'Queued';
      case JobStatus.PENDING:
        return 'Pending';
      case JobStatus.CANCELLED:
        return 'Cancelled';
      default:
        return status;
    }
  };

  const getJobTypeLabel = (jobType: JobType) => {
    switch (jobType) {
      case JobType.PRODUCT_ANALYSIS:
        return 'Product Analysis';
      case JobType.COMPETITOR_DISCOVERY:
        return 'Competitor Discovery';
      case JobType.FEATURE_EXTRACTION:
        return 'Feature Extraction';
      case JobType.IDEA_GENERATION:
        return 'Idea Generation';
      case JobType.IDEA_TRIAGE:
        return 'Idea Triage';
      case JobType.COMPETITIVE_MONITORING:
        return 'Competitive Monitoring';
      case JobType.FULL_WORKFLOW:
        return 'Full Workflow';
      default:
        return jobType;
    }
  };

  if (loading) {
    return (
      <div className={`bg-white border border-gray-200 rounded-lg ${compact ? 'p-3' : 'p-4'}`}>
        <div className="flex items-center space-x-2">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          <span className="text-gray-500 text-sm">Loading job status...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`bg-red-50 border border-red-200 rounded-lg ${compact ? 'p-3' : 'p-4'}`}>
        <p className="text-red-600 text-sm">{error}</p>
      </div>
    );
  }

  if (!job) {
    return null;
  }

  const isActive = isJobActive(job);

  return (
    <div className={`bg-white border border-gray-200 rounded-lg ${compact ? 'p-3' : 'p-4'} transition-all`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className={`inline-block w-2 h-2 rounded-full ${getStatusColor(job.status)} ${isActive ? 'animate-pulse' : ''}`}></span>
          <span className={`font-medium ${compact ? 'text-sm' : ''}`}>
            {getJobTypeLabel(job.job_type)}
          </span>
        </div>
        <span className={`text-sm px-2 py-0.5 rounded-full ${
          job.status === JobStatus.SUCCESS ? 'bg-green-100 text-green-700' :
          job.status === JobStatus.FAILURE ? 'bg-red-100 text-red-700' :
          job.status === JobStatus.RUNNING ? 'bg-blue-100 text-blue-700' :
          'bg-gray-100 text-gray-700'
        }`}>
          {getStatusText(job.status)}
        </span>
      </div>

      {/* Progress bar */}
      {isActive && (
        <div className="mb-2">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${job.progress_percent || 0}%` }}
            ></div>
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-xs text-gray-500">{job.progress_message || 'Processing...'}</span>
            <span className="text-xs text-gray-500">{Math.round(job.progress_percent || 0)}%</span>
          </div>
        </div>
      )}

      {/* Error message */}
      {job.status === JobStatus.FAILURE && job.error_message && (
        <div className="mt-2 p-2 bg-red-50 rounded text-sm text-red-600">
          {job.error_message}
        </div>
      )}

      {/* Details */}
      {showDetails && !compact && (
        <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-500 space-y-1">
          <div className="flex justify-between">
            <span>Job ID:</span>
            <span className="font-mono">{job.job_uuid.substring(0, 8)}...</span>
          </div>
          {job.started_at && (
            <div className="flex justify-between">
              <span>Started:</span>
              <span>{parseUTCTimestamp(job.started_at).toLocaleTimeString()}</span>
            </div>
          )}
          {job.completed_at && (
            <div className="flex justify-between">
              <span>Completed:</span>
              <span>{parseUTCTimestamp(job.completed_at).toLocaleTimeString()}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default JobStatusCard;
