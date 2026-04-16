/**
 * JobMapEditorPage
 *
 * View and edit a product's JTBD job map:
 * - Target customer profile (single form card)
 * - Hierarchical jobs by category (functional / emotional / social)
 * - Add / edit / delete individual jobs
 *
 * Mutation strategy: after every successful write we re-fetch the whole map
 * so `job_map_version`, `job_map_last_updated`, and `has_embedding` stay in
 * sync without merge logic.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { format } from 'date-fns';
import {
  addJob,
  deleteJob,
  getJobMap,
  updateJob,
  updateTargetCustomer,
} from '../../services/api';
import Navigation from '../../components/Navigation';
import type {
  JobCategory,
  JobCreateRequest,
  JobMapResponse,
  JobUpdateRequest,
  JtbdJob,
  TargetCustomerProfile,
} from '../../types';
import TargetCustomerCard from './components/TargetCustomerCard';
import JobRow from './components/JobRow';
import AddJobForm from './components/AddJobForm';

interface ActionMessage {
  type: 'success' | 'error';
  text: string;
}

interface JobCategorySectionProps {
  category: JobCategory;
  title: string;
  subtitle: string;
  jobs: JtbdJob[];
  onAddJob: (body: JobCreateRequest) => Promise<void>;
  onSaveJob: (jobIdKey: string, patch: JobUpdateRequest) => Promise<void>;
  onDeleteJob: (jobIdKey: string) => Promise<void>;
}

function JobCategorySection({
  category,
  title,
  subtitle,
  jobs,
  onAddJob,
  onSaveJob,
  onDeleteJob,
}: JobCategorySectionProps) {
  const isEmpty = jobs.length === 0;
  return (
    <section className="bg-white rounded-lg shadow p-6 mb-6">
      <header className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        <p className="text-sm text-gray-500">{subtitle}</p>
      </header>

      {isEmpty && (
        <p className="text-sm text-gray-500 italic mb-3">
          No {category} jobs yet. Add the first one below.
        </p>
      )}

      {!isEmpty && (
        <div className="space-y-3 mb-3">
          {jobs.map((job) => (
            <JobRow
              key={job.job_id_key}
              job={job}
              onSave={onSaveJob}
              onDelete={onDeleteJob}
            />
          ))}
        </div>
      )}

      <AddJobForm
        category={category}
        existingJobs={jobs}
        alwaysExpanded={isEmpty}
        onAdd={onAddJob}
      />
    </section>
  );
}

export default function JobMapEditorPage() {
  const { productId } = useParams<{ productId: string }>();
  const numProductId = productId ? parseInt(productId, 10) : NaN;

  const [data, setData] = useState<JobMapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<ActionMessage | null>(null);

  const fetchJobMap = useCallback(async () => {
    if (!Number.isFinite(numProductId)) return;
    try {
      const result = await getJobMap(numProductId);
      setData(result);
      setError(null);
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load job map.');
    } finally {
      setLoading(false);
    }
  }, [numProductId]);

  useEffect(() => {
    fetchJobMap();
  }, [fetchJobMap]);

  // Auto-clear action messages
  useEffect(() => {
    if (actionMessage) {
      const timer = setTimeout(() => setActionMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [actionMessage]);

  const handleSaveTargetCustomer = async (profile: TargetCustomerProfile) => {
    await updateTargetCustomer(numProductId, profile);
    setActionMessage({ type: 'success', text: 'Target customer profile saved.' });
    await fetchJobMap();
  };

  const handleAddJob = async (body: JobCreateRequest) => {
    await addJob(numProductId, body);
    setActionMessage({ type: 'success', text: `Added ${body.job_id}.` });
    await fetchJobMap();
  };

  const handleSaveJob = async (jobIdKey: string, patch: JobUpdateRequest) => {
    await updateJob(numProductId, jobIdKey, patch);
    setActionMessage({ type: 'success', text: `Updated ${jobIdKey}.` });
    await fetchJobMap();
  };

  const handleDeleteJob = async (jobIdKey: string) => {
    await deleteJob(numProductId, jobIdKey);
    setActionMessage({ type: 'success', text: `Deleted ${jobIdKey}.` });
    await fetchJobMap();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="p-4 bg-red-50 border border-red-200 rounded text-red-700">{error}</div>
          <Link
            to={`/product-intelligence/products/${productId}`}
            className="mt-4 inline-block text-sm text-blue-600 hover:text-blue-800"
          >
            ← Back to product
          </Link>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const functionalJobs = data.jobs.filter((j) => j.job_type === 'functional');
  const emotionalJobs = data.jobs.filter((j) => j.job_type === 'emotional');
  const socialJobs = data.jobs.filter((j) => j.job_type === 'social');

  const lastUpdated = data.job_map_last_updated
    ? format(new Date(data.job_map_last_updated), 'MMM d, yyyy h:mm a')
    : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            to={`/product-intelligence/products/${productId}`}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            ← Back to {data.product_name}
          </Link>
          <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
            <h1 className="text-2xl font-bold text-gray-900">Jobs-to-be-Done Map</h1>
            <div className="text-xs text-gray-500 flex items-center gap-3">
              <span>
                Version <strong>{data.job_map_version}</strong>
              </span>
              {lastUpdated && <span>Last updated {lastUpdated}</span>}
            </div>
          </div>
          <p className="text-sm text-gray-600 mt-1">
            Define who this product is for and the functional, emotional, and social jobs they
            hire it to do. Jobs are used by competitive analysis, idea triage, and synthesis.
          </p>
        </div>

        {/* Action message */}
        {actionMessage && (
          <div
            className={`mb-4 p-3 rounded border text-sm ${
              actionMessage.type === 'success'
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-red-50 border-red-200 text-red-800'
            }`}
          >
            {actionMessage.text}
          </div>
        )}

        {/* Target customer */}
        <TargetCustomerCard
          profile={data.target_customer_profile}
          onSave={handleSaveTargetCustomer}
        />

        {/* Jobs by category */}
        <JobCategorySection
          category="functional"
          title="Functional Jobs"
          subtitle="The practical tasks customers want to accomplish."
          jobs={functionalJobs}
          onAddJob={handleAddJob}
          onSaveJob={handleSaveJob}
          onDeleteJob={handleDeleteJob}
        />

        <JobCategorySection
          category="emotional"
          title="Emotional Jobs"
          subtitle="How customers want to feel as they do the job."
          jobs={emotionalJobs}
          onAddJob={handleAddJob}
          onSaveJob={handleSaveJob}
          onDeleteJob={handleDeleteJob}
        />

        <JobCategorySection
          category="social"
          title="Social Jobs"
          subtitle="How customers want to be perceived by others."
          jobs={socialJobs}
          onAddJob={handleAddJob}
          onSaveJob={handleSaveJob}
          onDeleteJob={handleDeleteJob}
        />
      </div>
    </div>
  );
}
