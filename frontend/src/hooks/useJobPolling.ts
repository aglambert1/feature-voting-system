/**
 * Shared job-polling hooks.
 *
 * Two variants cover the app's polling needs:
 * - useProductJobPolling: poll a product's jobs by type until none are active
 * - useJobStatusPolling: poll a single job by UUID until it finishes
 *
 * Both poll every 2s (configurable) and keep callbacks in refs so callers
 * don't need to memoize them.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { getJob, getProductJobs } from '../services/api';
import type { ApiError, QueueJob } from '../types';
import { JobStatus, JobType } from '../types';

/** True while a job is pending, queued, or running. */
export const isJobActive = (job: QueueJob): boolean =>
  job.status === JobStatus.PENDING ||
  job.status === JobStatus.QUEUED ||
  job.status === JobStatus.RUNNING;

/** True once a job has succeeded or failed. */
export const isJobFinished = (job: QueueJob): boolean =>
  job.status === JobStatus.SUCCESS || job.status === JobStatus.FAILURE;

interface ProductJobPollingOptions {
  productId: number | null;
  jobTypes: JobType[];
  /** Max jobs fetched per poll (default 10). */
  limit?: number;
  /** Poll interval in ms (default 2000). */
  intervalMs?: number;
  /**
   * Fired once per active→idle transition with the most recent finished job
   * (null if none was found).
   */
  onComplete?: (lastCompleted: QueueJob | null) => void;
}

interface ProductJobPollingResult {
  activeJob: QueueJob | null;
  lastCompletedJob: QueueJob | null;
  loading: boolean;
  /** Re-fetch immediately — call after starting a new job so polling picks it up. */
  refresh: () => Promise<void>;
}

export function useProductJobPolling({
  productId,
  jobTypes,
  limit = 10,
  intervalMs = 2000,
  onComplete,
}: ProductJobPollingOptions): ProductJobPollingResult {
  const [activeJob, setActiveJob] = useState<QueueJob | null>(null);
  const [lastCompletedJob, setLastCompletedJob] = useState<QueueJob | null>(null);
  const [loading, setLoading] = useState(true);

  // Track the previous active state so onComplete fires only on a genuine
  // active→idle transition, and keep the callback in a ref so its identity
  // never restarts the polling effect.
  const wasActiveRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);

  // Key job types by value, not identity, so inline arrays don't churn the effect.
  const jobTypesKey = JSON.stringify(jobTypes);

  const refresh = useCallback(async () => {
    if (productId === null) return;
    const types = JSON.parse(jobTypesKey) as JobType[];
    try {
      const jobs = await getProductJobs(productId, limit, types);
      const relevantJobs = jobs.filter(j => types.includes(j.job_type as JobType));

      const active = relevantJobs.find(isJobActive) || null;
      const completed = relevantJobs.find(isJobFinished) || null;

      setActiveJob(active);
      setLastCompletedJob(completed);

      const justCompleted = !active && wasActiveRef.current;
      if (justCompleted && onCompleteRef.current) {
        onCompleteRef.current(completed);
      }
      wasActiveRef.current = !!active;
    } catch (err) {
      console.error('Failed to fetch job status:', err);
    } finally {
      setLoading(false);
    }
  }, [productId, jobTypesKey, limit]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll only while there's an active job.
  useEffect(() => {
    if (!activeJob) return;
    const interval = setInterval(refresh, intervalMs);
    return () => clearInterval(interval);
  }, [activeJob, refresh, intervalMs]);

  return { activeJob, lastCompletedJob, loading, refresh };
}

interface JobStatusPollingOptions {
  /** Poll interval in ms (default 2000). */
  intervalMs?: number;
  /** Fired on each fetch that sees SUCCESS (matches JobStatusCard semantics). */
  onComplete?: (job: QueueJob) => void;
  /** Fired on each fetch that sees FAILURE. */
  onError?: (job: QueueJob) => void;
}

interface JobStatusPollingResult {
  job: QueueJob | null;
  loading: boolean;
  error: string;
}

export function useJobStatusPolling(
  jobUuid: string | null,
  { intervalMs = 2000, onComplete, onError }: JobStatusPollingOptions = {},
): JobStatusPollingResult {
  const [job, setJob] = useState<QueueJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);
  useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  const fetchJob = useCallback(async () => {
    if (!jobUuid) return;
    try {
      const jobData = await getJob(jobUuid);
      setJob(jobData);

      if (jobData.status === JobStatus.SUCCESS) {
        onCompleteRef.current?.(jobData);
      } else if (jobData.status === JobStatus.FAILURE) {
        onErrorRef.current?.(jobData);
      }
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, [jobUuid]);

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  // Poll only while the job is active.
  useEffect(() => {
    if (!job || !isJobActive(job)) return;
    const interval = setInterval(fetchJob, intervalMs);
    return () => clearInterval(interval);
  }, [fetchJob, job, intervalMs]);

  return { job, loading, error };
}
