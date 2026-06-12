/**
 * JobMapEditorPage
 *
 * View and edit a product's customer need map:
 * - Target customer profile (single form card)
 * - Flat list of customer needs (no JTBD category grouping)
 * - Add / edit / delete individual needs
 *
 * Mutation strategy: after every successful write we re-fetch the whole map
 * so `job_map_version`, `job_map_last_updated`, and `has_embedding` stay in
 * sync without merge logic.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { format } from 'date-fns';
import {
  addJob,
  deleteJob,
  extractJobMap,
  getJobMap,
  getNeedSuggestions,
  setMainJob,
  updateJob,
  updateTargetCustomer,
} from '../../services/api';
import Navigation from '../../components/Navigation';
import AgentJobStatus from '../../components/AgentJobStatus';
import type {
  JobCreateRequest,
  JobMapResponse,
  JobUpdateRequest,
  NeedSuggestion,
  TargetCustomerProfile,
} from '../../types';
import { JobType } from '../../types';
import TargetCustomerCard from './components/TargetCustomerCard';
import JobRow from './components/JobRow';
import AddJobForm from './components/AddJobForm';
import GenerateJobMapDialog from './components/GenerateJobMapDialog';
import NeedSuggestionPanel from './components/NeedSuggestionPanel';

interface ActionMessage {
  type: 'success' | 'error';
  text: string;
}

export default function JobMapEditorPage() {
  const { productId } = useParams<{ productId: string }>();
  const numProductId = productId ? parseInt(productId, 10) : NaN;
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get('returnTo'); // e.g. "idea/47"
  const returnIdeaId = returnTo?.startsWith('idea/') ? returnTo.slice(5) : null;

  const [data, setData] = useState<JobMapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<ActionMessage | null>(null);
  const [showGenerateDialog, setShowGenerateDialog] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [suggestions, setSuggestions] = useState<NeedSuggestion[]>([]);
  const [mainJobText, setMainJobText] = useState('');
  const [editingMainJob, setEditingMainJob] = useState(false);
  const [savingMainJob, setSavingMainJob] = useState(false);

  const fetchJobMap = useCallback(async () => {
    if (!Number.isFinite(numProductId)) return;
    try {
      const result = await getJobMap(numProductId);
      setData(result);
      setMainJobText((result.job_map as any)?.main_job ?? '');
      setError(null);
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load job map.');
    } finally {
      setLoading(false);
    }
  }, [numProductId]);

  const fetchSuggestions = useCallback(async () => {
    if (!Number.isFinite(numProductId)) return;
    try {
      const result = await getNeedSuggestions(numProductId);
      setSuggestions(result.suggestions);
    } catch {
      // Non-critical — suggestions panel simply stays empty
    }
  }, [numProductId]);

  useEffect(() => {
    fetchJobMap();
    fetchSuggestions();
  }, [fetchJobMap, fetchSuggestions]);

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

  const handleDeleteJob = async (jobIdKey: string, relink: boolean) => {
    await deleteJob(numProductId, jobIdKey, relink);
    setActionMessage({ type: 'success', text: `Deleted ${jobIdKey}.` });
    await fetchJobMap();
  };

  const handleSaveMainJob = async () => {
    if (!mainJobText.trim()) return;
    setSavingMainJob(true);
    try {
      await setMainJob(numProductId, mainJobText.trim());
      setEditingMainJob(false);
      setActionMessage({ type: 'success', text: 'Main job saved.' });
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err?.message ?? 'Failed to save main job.' });
    } finally {
      setSavingMainJob(false);
    }
  };

  const handleSuggestionRefresh = async () => {
    await Promise.all([fetchJobMap(), fetchSuggestions()]);
  };

  const handleGenerateConfirm = async (guidance: string) => {
    setIsGenerating(true);
    try {
      await extractJobMap(numProductId, guidance || undefined);
      setShowGenerateDialog(false);
      setActionMessage({ type: 'success', text: 'Need map generation queued. The map will update when complete.' });
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err?.message ?? 'Failed to queue need map generation.' });
      setShowGenerateDialog(false);
    } finally {
      setIsGenerating(false);
    }
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
          {returnIdeaId && (
            <Link
              to={`/ideas?openModal=${returnIdeaId}`}
              className="mt-1 flex items-center gap-1.5 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-1.5 hover:bg-amber-100 w-fit"
            >
              ← Back to Idea #{returnIdeaId}
            </Link>
          )}
          <div className="mt-2 flex flex-wrap items-start justify-between gap-2">
            <h1 className="text-2xl font-bold text-gray-900">Customer Need Map</h1>
            <div className="flex flex-col items-end gap-1">
              <button
                type="button"
                onClick={() => setShowGenerateDialog(true)}
                className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700"
              >
                Generate from product info
              </button>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <AgentJobStatus
                  productId={numProductId}
                  jobTypes={[JobType.JOB_MAP_EXTRACTION]}
                  onJobComplete={fetchJobMap}
                />
                {!data.has_pending_map && (
                  <>
                    <span>
                      Version <strong>{data.job_map_version}</strong>
                    </span>
                    {lastUpdated && <span>Last updated {lastUpdated}</span>}
                  </>
                )}
              </div>
            </div>
          </div>
          <p className="text-sm text-gray-600 mt-1">
            Define what your customers are trying to accomplish. Each need is used by competitive
            analysis, idea triage, and synthesis to surface evidence and gaps.
          </p>
        </div>

        {/* Pending map banner */}
        {data.has_pending_map && (
          <div className="mb-4 p-3 rounded border border-amber-300 bg-amber-50 flex items-center justify-between gap-3">
            <div>
              <span className="text-sm font-medium text-amber-900">⚠ Pending changes from regeneration</span>
              <span className="text-xs text-amber-700 ml-2">Your current map is unchanged — review before applying.</span>
            </div>
            <button
              type="button"
              onClick={() => navigate(`/product-intelligence/products/${productId}/job-map/review`)}
              className="flex-shrink-0 px-3 py-1.5 text-xs font-medium text-white bg-amber-600 rounded hover:bg-amber-700"
            >
              Review changes →
            </button>
          </div>
        )}

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

        {/* Main job */}
        <section className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-1">Main Job</h2>
              <p className="text-xs text-gray-400 mb-2">The overarching outcome your customers are trying to achieve.</p>
              {editingMainJob ? (
                <div className="space-y-2">
                  <textarea
                    value={mainJobText}
                    onChange={(e) => setMainJobText(e.target.value)}
                    placeholder="e.g. Help operations teams close deals faster"
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm resize-y"
                    disabled={savingMainJob}
                    onKeyDown={(e) => { if (e.key === 'Escape') setEditingMainJob(false); }}
                    autoFocus
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={handleSaveMainJob}
                      disabled={savingMainJob || !mainJobText.trim()}
                      className="text-sm px-3 py-1 text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                      {savingMainJob ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      onClick={() => { setEditingMainJob(false); setMainJobText((data.job_map as any)?.main_job ?? ''); }}
                      disabled={savingMainJob}
                      className="text-sm px-3 py-1 text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-gray-800 text-sm">
                  {mainJobText || <span className="text-gray-400 italic">Not set — click Edit to define the main job</span>}
                </p>
              )}
            </div>
            {!editingMainJob && (
              <button
                onClick={() => setEditingMainJob(true)}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium flex-shrink-0"
              >
                Edit
              </button>
            )}
          </div>
        </section>

        {/* Need map suggestions */}
        <NeedSuggestionPanel
          productId={numProductId}
          suggestions={suggestions}
          onRefresh={handleSuggestionRefresh}
        />

        {/* Customer needs — flat list */}
        <section className="bg-white rounded-lg shadow p-6 mb-6">
          <header className="mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Customer Needs</h2>
            <p className="text-sm text-gray-500">
              What your customers are trying to accomplish, and why it matters to them.
              Signal count reflects ideas, evidence, and feedback linked to each need.
            </p>
          </header>

          {data.jobs.length === 0 && (
            <p className="text-sm text-gray-500 italic mb-3">
              No needs defined yet. Add the first one below, or generate from product info.
            </p>
          )}

          {data.jobs.length > 0 && (
            <div className="space-y-3 mb-3">
              {data.jobs.map((job) => (
                <JobRow
                  key={job.job_id_key}
                  job={job}
                  productId={numProductId}
                  returnIdeaId={returnIdeaId}
                  onSave={handleSaveJob}
                  onDelete={handleDeleteJob}
                />
              ))}
            </div>
          )}

          <AddJobForm
            existingJobs={data.jobs}
            alwaysExpanded={data.jobs.length === 0}
            onAdd={handleAddJob}
          />
        </section>
      </div>

      {showGenerateDialog && (
        <GenerateJobMapDialog
          hasExistingMap={data.jobs.length > 0}
          onConfirm={handleGenerateConfirm}
          onCancel={() => setShowGenerateDialog(false)}
          isSubmitting={isGenerating}
        />
      )}
    </div>
  );
}
