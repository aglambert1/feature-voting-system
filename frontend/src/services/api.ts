/**
 * API Service
 *
 * Centralized API client using axios with:
 * - Request interceptors (adds auth tokens)
 * - Response interceptors (handles errors)
 * - All API methods for backend communication
 */

import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import type {
  LoginResponse,
  User,
  RegisterData,
  IdeaListResponse,
  IdeaResponse,
  VoteResponse,
  StructureResponse,
  SubmissionData,
  ApiError,
  SimilarIdea,
  QueueJob,
  PMReviewQueueItem,
  PMReviewQueueStats,
  MonitoringConfig,
  IdeaDetail,
  IdeaComment,
  IdeaRespondRequest,
  IdeaRespondResponse,
  TriageRecommendation,
  ProductPendingCounts,
  TriageSettings,
  TriageSettingsUpdate,
  CanRespondResponse,
  // Competitive Agent types
  CompetitiveAgentConfig,
  CompetitiveAgentConfigUpdate,
  AgentCompetitor,
  AgentJobResponse,
  FeatureQueryResponse,
} from '../types';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - Add auth token to all requests
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Get token from localStorage
    const token = localStorage.getItem('access_token');

    // If token exists, add to Authorization header
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle errors globally and token refresh
api.interceptors.response.use(
  (response: AxiosResponse) => {
    // Check for refreshed token in response header (sliding session window)
    const newToken = response.headers['x-new-access-token'];
    if (newToken) {
      // Store the refreshed token - this extends the session
      localStorage.setItem('access_token', newToken);
    }

    // Return successful response data
    return response;
  },
  (error: AxiosError) => {
    // Handle specific error cases
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;

      // Check if we should skip auth redirect (e.g., for login page)
      const skipAuthRedirect = error.config?.skipAuthRedirect;

      if (status === 401 && !skipAuthRedirect) {
        // Unauthorized - clear token and redirect to login
        // (but skip redirect if this is the login request itself)
        localStorage.removeItem('access_token');
        window.location.href = '/login';
      }

      // Return error with meaningful message
      // Handle Pydantic validation errors (422) where detail is an array of error objects
      const detail = (error.response.data as any)?.detail;
      let message: string;
      if (Array.isArray(detail)) {
        // Pydantic validation error - extract the message from each error
        message = detail.map((e: { msg?: string }) => e.msg || 'Validation error').join(', ');
      } else if (typeof detail === 'string') {
        message = detail;
      } else {
        message = 'An error occurred';
      }
      const apiError: ApiError = {
        message,
        status: status,
        data: error.response.data,
      };
      return Promise.reject(apiError);
    } else if (error.request) {
      // Request made but no response received
      const apiError: ApiError = {
        message: 'Network error - please check your connection',
        status: 0,
      };
      return Promise.reject(apiError);
    } else {
      // Error setting up request
      const apiError: ApiError = {
        message: error.message || 'An unexpected error occurred',
        status: 0,
      };
      return Promise.reject(apiError);
    }
  }
);

// ============================================================================
// AUTH API METHODS
// ============================================================================

/**
 * Login user with username/email and password
 */
export const login = async (username: string, password: string): Promise<LoginResponse> => {
  // FastAPI OAuth2 expects form data
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  try {
    const response = await api.post<LoginResponse>('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      // Skip the global 401 interceptor redirect for login
      skipAuthRedirect: true,
    });

    return response.data;
  } catch (error) {
    // Handle login-specific errors with user-friendly messages
    const apiError = error as ApiError;
    if (apiError.status === 401) {
      throw new Error('Invalid username or password. Please try again.');
    }
    throw new Error(apiError.message || 'Login failed. Please try again.');
  }
};

/**
 * Register new user
 */
export const register = async (userData: RegisterData): Promise<User> => {
  const response = await api.post<User>('/auth/register', userData);
  return response.data;
};

/**
 * Get current user profile
 */
export const getCurrentUser = async (): Promise<User> => {
  const response = await api.get<User>('/auth/me');
  return response.data;
};

/**
 * Mark the current user as having seen the welcome page. Idempotent.
 */
export const markWelcomed = async (): Promise<User> => {
  const response = await api.post<User>('/auth/me/mark-welcomed');
  return response.data;
};

/**
 * Logout user (client-side only - clear token)
 */
export const logout = (): void => {
  localStorage.removeItem('access_token');
  sessionStorage.removeItem('selectedProductId');
  sessionStorage.removeItem('products');
};

// ============================================================================
// IDEAS API METHODS
// ============================================================================

interface GetIdeasParams {
  skip?: number;
  limit?: number;
  product_id?: number;
  sort_by?: 'most_votes' | 'pending_first' | 'most_recent' | 'my_ideas';
  lifecycle_status_id?: number;
}

/**
 * Get all ideas with vote counts (paginated)
 */
export const getIdeas = async (params: GetIdeasParams = {}): Promise<IdeaListResponse> => {
  // Set defaults if not provided
  const queryParams = {
    skip: params.skip || 0,
    limit: params.limit || 20,  // Default to 20 ideas per page
    ...params
  };

  const response = await api.get<IdeaListResponse>('/ideas', {
    params: queryParams,
  });
  return response.data;
};

/**
 * Find similar ideas using semantic search
 *
 * @param query - Text to search for similar ideas
 * @param productId - Product ID to filter by
 * @param options - Optional axios config (e.g., signal for AbortController)
 * @returns List of similar ideas with similarity scores
 */
export const findSimilarIdeas = async (
  query: string,
  productId: number,
  options?: { signal?: AbortSignal }
): Promise<SimilarIdea[]> => {
  const response = await api.get<SimilarIdea[]>('/ideas/similar', {
    params: {
      q: query,
      product_id: productId,
      limit: 5,
      threshold: 0.7,
    },
    signal: options?.signal,
  });
  return response.data;
};

// ============================================================================
// VOTES API METHODS
// ============================================================================

/**
 * Vote on an idea
 */
export const voteOnIdea = async (ideaId: number, voteValue: number): Promise<VoteResponse> => {
  const response = await api.post<VoteResponse>(`/ideas/${ideaId}/vote`, {
    vote_value: voteValue,
  });
  return response.data;
};

// ============================================================================
// SUBMISSIONS API METHODS
// ============================================================================

/**
 * Structure freeform text using AI with product context
 */
export const structureText = async (freeformText: string, productId: number): Promise<StructureResponse> => {
  const response = await api.post<StructureResponse>('/submissions/structure', {
    freeform_text: freeformText,
    product_id: productId,
  });
  return response.data;
};

/**
 * Submit structured idea
 */
export const submitIdea = async (submissionData: SubmissionData): Promise<IdeaResponse> => {
  const response = await api.post<IdeaResponse>('/submissions/submit', submissionData);
  return response.data;
};

// ============================================================================
// PRODUCTS API METHODS
// ============================================================================

// ============================================================================
// COMPETITORS API METHODS
// ============================================================================

/**
 * Deactivate competitor (soft delete - hides from list, preserves reports)
 */
export const deactivateCompetitor = async (productId: number, competitorId: number): Promise<void> => {
  await api.post(`/product-intelligence/agents/${productId}/competitors/${competitorId}/deactivate`);
};

// ============================================================================
// FEATURES API METHODS
// ============================================================================

// ============================================================================
// ANALYSIS SESSIONS API METHODS
// ============================================================================

// ============================================================================
// USERS API METHODS (Admin only)
// ============================================================================

// ============================================================================
// QUEUE JOBS API METHODS (Phase 1-4)
// ============================================================================

/**
 * Get job by UUID
 */
export const getJob = async (jobUuid: string): Promise<QueueJob> => {
  const response = await api.get<QueueJob>(`/product-intelligence/jobs/${jobUuid}`);
  return response.data;
};

/**
 * Get jobs for a product
 * @param productId - Product ID
 * @param limit - Maximum number of jobs to return (default 10, max 100)
 * @param jobTypes - Optional array of job types to filter by
 */
export const getProductJobs = async (
  productId: number,
  limit: number = 10,
  jobTypes?: string[]
): Promise<QueueJob[]> => {
  // If job types provided, make multiple requests and combine
  // (API only supports single job_type filter)
  if (jobTypes && jobTypes.length > 0) {
    const allJobs: QueueJob[] = [];
    for (const jobType of jobTypes) {
      try {
        const response = await api.get<QueueJob[]>(`/product-intelligence/products/${productId}/jobs`, {
          params: { limit, job_type: jobType },
        });
        allJobs.push(...response.data);
      } catch {
        // Ignore errors for individual job types
      }
    }
    // Sort by created_at descending and dedupe
    const seen = new Set<number>();
    return allJobs
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .filter(job => {
        if (seen.has(job.id)) return false;
        seen.add(job.id);
        return true;
      });
  }

  const response = await api.get<QueueJob[]>(`/product-intelligence/products/${productId}/jobs`, {
    params: { limit },
  });
  return response.data;
};

// ============================================================================
// PM REVIEW QUEUE API METHODS (Phase 4)
// ============================================================================

/**
 * Get queue stats for a product
 */
export const getReviewQueueStats = async (productId: number): Promise<PMReviewQueueStats> => {
  const response = await api.get<PMReviewQueueStats>(`/pm-review/stats/${productId}`);
  return response.data;
};

/**
 * Start review of queue item
 */
export const startReviewQueueItem = async (itemId: number): Promise<PMReviewQueueItem> => {
  const response = await api.post<PMReviewQueueItem>(`/pm-review/queue/${itemId}/start-review`);
  return response.data;
};

/**
 * Approve queue item
 */
export const approveQueueItem = async (itemId: number, notes?: string): Promise<PMReviewQueueItem> => {
  const response = await api.post<PMReviewQueueItem>(`/pm-review/queue/${itemId}/approve`, {
    notes,
  });
  return response.data;
};

/**
 * Reject queue item
 */
export const rejectQueueItem = async (itemId: number, notes?: string): Promise<PMReviewQueueItem> => {
  const response = await api.post<PMReviewQueueItem>(`/pm-review/queue/${itemId}/reject`, {
    notes,
  });
  return response.data;
};

/**
 * Defer queue item
 */
export const deferQueueItem = async (itemId: number, notes?: string): Promise<PMReviewQueueItem> => {
  const response = await api.post<PMReviewQueueItem>(`/pm-review/queue/${itemId}/defer`, {
    notes,
  });
  return response.data;
};

// ============================================================================
// MONITORING API METHODS (Phase 4)
// ============================================================================

/**
 * Get monitoring config for a product
 */
export const getMonitoringConfig = async (productId: number): Promise<MonitoringConfig> => {
  const response = await api.get<MonitoringConfig>(`/monitoring/config/${productId}`);
  return response.data;
};

/**
 * Trigger manual monitoring for a product
 */
export const triggerMonitoring = async (
  productId: number,
  forceFull: boolean = false
): Promise<{ job_uuid: string; status: string }> => {
  const response = await api.post<{ job_uuid: string; status: string }>(
    `/monitoring/trigger/${productId}`,
    null,
    { params: { force_full: forceFull } }
  );
  return response.data;
};

// ============================================================================
// IDEA RESPONSE WORKFLOW API METHODS (Plan Phase 2)
// ============================================================================

/**
 * Get detailed idea information including comments and triage details
 */
export const getIdeaDetail = async (ideaId: number): Promise<IdeaDetail> => {
  const response = await api.get<IdeaDetail>(`/ideas/${ideaId}/detail`);
  return response.data;
};

/**
 * Respond to an idea (PO workflow)
 */
export const respondToIdea = async (
  ideaId: number,
  request: IdeaRespondRequest
): Promise<IdeaRespondResponse> => {
  const response = await api.post<IdeaRespondResponse>(`/ideas/${ideaId}/respond`, request);
  return response.data;
};

/**
 * Add a comment to an idea
 */
export const addIdeaComment = async (ideaId: number, commentText: string): Promise<IdeaComment> => {
  const response = await api.post<IdeaComment>(`/ideas/${ideaId}/comments`, {
    comment_text: commentText,
  });
  return response.data;
};

/**
 * Get triage recommendation for an idea
 */
export const getTriageRecommendation = async (ideaId: number): Promise<TriageRecommendation> => {
  const response = await api.get<TriageRecommendation>(`/ideas/${ideaId}/triage-recommendation`);
  return response.data;
};

/**
 * Check if user can respond to an idea
 */
export const checkCanRespond = async (ideaId: number): Promise<CanRespondResponse> => {
  const response = await api.get<CanRespondResponse>(`/ideas/${ideaId}/can-respond`);
  return response.data;
};

// ============================================================================
// PRODUCT PENDING COUNTS API METHODS (Plan Phase 1)
// ============================================================================

/**
 * Get pending counts for a product
 */
export const getProductPendingCounts = async (productId: number): Promise<ProductPendingCounts> => {
  const response = await api.get<ProductPendingCounts>(
    `/product-intelligence/products/${productId}/pending-counts`
  );
  return response.data;
};

// ============================================================================
// TRIAGE AUTOMATION SETTINGS API METHODS (Plan Phase 8)
// ============================================================================

/**
 * Get triage automation settings for a product
 */
export const getTriageSettings = async (productId: number): Promise<TriageSettings> => {
  const response = await api.get<TriageSettings>(
    `/product-intelligence/products/${productId}/triage-settings`
  );
  return response.data;
};

/**
 * Update triage automation settings for a product
 */
export const updateTriageSettings = async (
  productId: number,
  settings: TriageSettingsUpdate
): Promise<TriageSettings> => {
  const response = await api.put<TriageSettings>(
    `/product-intelligence/products/${productId}/triage-settings`,
    settings
  );
  return response.data;
};

// ============================================================================
// FEATURE QUERY API (Chat Interface)
// ============================================================================

/**
 * Query if a feature exists in a product.
 *
 * Uses the same similarity detection logic as the Idea Triage Agent,
 * ensuring consistent results between asking "Does feature X exist?"
 * and submitting an idea for feature X.
 */
export const queryProductFeatures = async (
  productId: number,
  query: string,
  options?: {
    includeSimilar?: boolean;
    threshold?: number;
  }
): Promise<FeatureQueryResponse> => {
  const response = await api.post<FeatureQueryResponse>(
    `/product-intelligence/products/${productId}/feature-query`,
    {
      query,
      include_similar: options?.includeSimilar ?? true,
      similarity_threshold: options?.threshold ?? 0.85,
    }
  );
  return response.data;
};

// ============================================================================
// COMPETITIVE AGENTS API METHODS (Agent-Centric Architecture)
// ============================================================================

/**
 * Get agent configuration for a product
 */
export const getAgentConfig = async (productId: number): Promise<CompetitiveAgentConfig> => {
  const response = await api.get<CompetitiveAgentConfig>(
    `/product-intelligence/agents/${productId}/config`
  );
  return response.data;
};

/**
 * Update agent configuration for a product
 */
export const updateAgentConfig = async (
  productId: number,
  config: CompetitiveAgentConfigUpdate
): Promise<CompetitiveAgentConfig> => {
  const response = await api.put<CompetitiveAgentConfig>(
    `/product-intelligence/agents/${productId}/config`,
    config
  );
  return response.data;
};

// --- Product-Level Triggers ---

/**
 * Trigger competitor discovery for a product
 */
export const triggerCompetitorDiscovery = async (productId: number): Promise<AgentJobResponse> => {
  const response = await api.post<AgentJobResponse>(
    `/product-intelligence/agents/${productId}/discover-competitors`
  );
  return response.data;
};

// --- Competitor Management ---

/**
 * List competitors with tracking and audit status
 */
export const getAgentCompetitors = async (
  productId: number,
  tracked?: boolean
): Promise<AgentCompetitor[]> => {
  const response = await api.get<AgentCompetitor[]>(
    `/product-intelligence/agents/${productId}/competitors`,
    { params: tracked !== undefined ? { tracked } : {} }
  );
  return response.data;
};

/**
 * Set competitor tracked status
 */
export const updateCompetitorTracked = async (
  productId: number,
  competitorId: number,
  tracked: boolean
): Promise<AgentCompetitor> => {
  const response = await api.patch<AgentCompetitor>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/tracked`,
    { tracked }
  );
  return response.data;
};

/**
 * Add a competitor manually
 */
export const addCompetitorManually = async (
  productId: number,
  competitorName: string,
  competitorUrl: string
): Promise<{
  id: number;
  competitor_name: string;
  competitor_url: string;
  tracked: boolean;
  message: string;
}> => {
  const response = await api.post(
    `/product-intelligence/agents/${productId}/competitors/add`,
    {
      competitor_name: competitorName,
      competitor_url: competitorUrl,
    }
  );
  return response.data;
};

// --- Competitor Alerts ---

export interface CompetitorAlert {
  id: number;
  product_id: number;
  alert_type: 'new_competitor' | 'competitor_disappeared' | 'competitor_change';
  competitor_id: number | null;
  competitor_name: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

/**
 * Get competitor alerts for a product
 */
export const getCompetitorAlerts = async (
  productId: number,
  unreadOnly: boolean = false
): Promise<CompetitorAlert[]> => {
  const response = await api.get<CompetitorAlert[]>(
    `/product-intelligence/agents/${productId}/alerts`,
    { params: { unread_only: unreadOnly } }
  );
  return response.data;
};

/**
 * Get unread alert count
 */
export const getUnreadAlertCount = async (
  productId: number
): Promise<{ unread_count: number }> => {
  const response = await api.get<{ unread_count: number }>(
    `/product-intelligence/agents/${productId}/alerts/count`
  );
  return response.data;
};

/**
 * Mark an alert as read
 */
export const markAlertRead = async (
  productId: number,
  alertId: number
): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>(
    `/product-intelligence/agents/${productId}/alerts/${alertId}/read`
  );
  return response.data;
};

/**
 * Mark all alerts as read
 */
export const markAllAlertsRead = async (
  productId: number
): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>(
    `/product-intelligence/agents/${productId}/alerts/read-all`
  );
  return response.data;
};

// --- Per-Competitor Feature Review ---

// ============================================================================
// V2 COMPETITIVE ANALYSIS API METHODS
// ============================================================================

// Import V2 types at runtime (they're already in types.ts)
import type {
  FunctionalReportSummary,
  FunctionalReportDetail,
  BatchIdeaStatusesResponse,
} from '../types';

/**
 * Get all functional reports for a product
 */
export const getFunctionalReports = async (productId: number): Promise<FunctionalReportSummary[]> => {
  const response = await api.get<FunctionalReportSummary[]>(
    `/product-intelligence/agents/${productId}/functional-reports`
  );
  return response.data;
};

/**
 * Get functional report detail for a competitor
 */
export const getFunctionalReport = async (
  productId: number,
  competitorId: number
): Promise<FunctionalReportDetail | null> => {
  const response = await api.get<FunctionalReportDetail | null>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/functional-report`
  );
  return response.data;
};

/**
 * Trigger functional audit for a single competitor
 */
export const triggerFunctionalAudit = async (
  productId: number,
  competitorId: number
): Promise<AgentJobResponse> => {
  const response = await api.post<AgentJobResponse>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/functional-audit`
  );
  return response.data;
};

/**
 * Export functional report as markdown
 */
export const exportFunctionalReportMd = async (
  productId: number,
  competitorId: number
): Promise<string> => {
  const response = await api.get<string>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/functional-report/export`,
    { headers: { Accept: 'text/markdown' } }
  );
  return response.data;
};

/**
 * Get idea statuses for all gaps of a competitor
 */
export const getGapIdeaStatuses = async (
  productId: number,
  competitorId: number
): Promise<BatchIdeaStatusesResponse> => {
  const response = await api.get<BatchIdeaStatusesResponse>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/gaps/idea-statuses`
  );
  return response.data;
};

/**
 * Create ideas from selected gaps
 */
export const createIdeasFromGaps = async (
  productId: number,
  competitorId: number,
  gapIndices: number[]
): Promise<AgentJobResponse[]> => {
  const response = await api.post<AgentJobResponse[]>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/gaps/create-ideas`,
    { gap_indices: gapIndices }
  );
  return response.data;
};

/**
 * Export selected gaps as JSON
 */
export const exportGapsJson = async (
  productId: number,
  competitorId: number,
  gapIndices: number[]
): Promise<any> => {
  const response = await api.post(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/gaps/export-json`,
    { gap_indices: gapIndices }
  );
  return response.data;
};

/**
 * Trigger full V2 competitive analysis
 */
export const triggerCompetitiveAnalysisV2 = async (productId: number): Promise<AgentJobResponse> => {
  const response = await api.post<AgentJobResponse>(
    `/product-intelligence/agents/${productId}/run-competitive-analysis-v2`
  );
  return response.data;
};

// ============================================================================
// INTERNAL FEEDBACK API METHODS (Phase 2 - Internal Discovery Agent)
// ============================================================================

import type {
  InternalFeedbackImport,
  InternalFeedbackThemes,
  ImportStatusResponse,
  ActivityImport,
  ActivityInsights,
  ActivityImportStatusResponse,
} from '../types';

/**
 * Upload internal feedback JSON file
 */
export const uploadInternalFeedback = async (
  productId: number,
  file: File
): Promise<InternalFeedbackImport> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post<InternalFeedbackImport>(
    `/internal-feedback/${productId}/import`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};

/**
 * Get all imports for a product
 */
export const getInternalFeedbackImports = async (
  productId: number
): Promise<InternalFeedbackImport[]> => {
  const response = await api.get<{ imports: InternalFeedbackImport[]; total: number }>(
    `/internal-feedback/${productId}/imports`
  );
  return response.data.imports;
};

/**
 * Get import status (for polling during processing)
 */
export const getInternalFeedbackImportStatus = async (
  productId: number,
  importId: number
): Promise<ImportStatusResponse> => {
  const response = await api.get<ImportStatusResponse>(
    `/internal-feedback/${productId}/imports/${importId}/status`
  );
  return response.data;
};

/**
 * Get all extracted themes for a product
 */
export const getInternalFeedbackThemes = async (
  productId: number
): Promise<InternalFeedbackThemes> => {
  const response = await api.get<InternalFeedbackThemes>(
    `/internal-feedback/${productId}/themes`
  );
  return response.data;
};

/**
 * Delete an import and its themes
 */
export const deleteInternalFeedbackImport = async (
  productId: number,
  importId: number
): Promise<void> => {
  await api.delete(`/internal-feedback/${productId}/imports/${importId}`);
};

/**
 * Reprocess an import (re-run theme extraction)
 */
export const reprocessInternalFeedback = async (
  productId: number,
  importId: number
): Promise<InternalFeedbackImport> => {
  const response = await api.post<InternalFeedbackImport>(
    `/internal-feedback/${productId}/imports/${importId}/reprocess`
  );
  return response.data;
};

// ============================================================================
// ACTIVITY IMPORT API METHODS (CRM Activity Stream Analysis)
// ============================================================================

/**
 * Upload activity data file (JSON or Markdown)
 */
export const uploadActivityData = async (
  productId: number,
  file: File
): Promise<ActivityImport> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post<ActivityImport>(
    `/internal-feedback/${productId}/activity-import`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};

/**
 * Get all activity imports for a product
 */
export const getActivityImports = async (
  productId: number
): Promise<ActivityImport[]> => {
  const response = await api.get<{ imports: ActivityImport[]; total: number }>(
    `/internal-feedback/${productId}/activity-imports`
  );
  return response.data.imports;
};

/**
 * Get activity import status (for polling)
 */
export const getActivityImportStatus = async (
  productId: number,
  importId: number
): Promise<ActivityImportStatusResponse> => {
  const response = await api.get<ActivityImportStatusResponse>(
    `/internal-feedback/${productId}/activity-imports/${importId}/status`
  );
  return response.data;
};

/**
 * Get activity insights for a product
 */
export const getActivityInsights = async (
  productId: number
): Promise<ActivityInsights> => {
  const response = await api.get<ActivityInsights>(
    `/internal-feedback/${productId}/activity-insights`
  );
  return response.data;
};

/**
 * Delete an activity import
 */
export const deleteActivityImport = async (
  productId: number,
  importId: number
): Promise<void> => {
  await api.delete(`/internal-feedback/${productId}/activity-imports/${importId}`);
};

/**
 * Reprocess an activity import
 */
export const reprocessActivityImport = async (
  productId: number,
  importId: number
): Promise<ActivityImport> => {
  const response = await api.post<ActivityImport>(
    `/internal-feedback/${productId}/activity-imports/${importId}/reprocess`
  );
  return response.data;
};

// ============================================================================
// UNIFIED SYNTHESIS API (replaces the pre-PR-#33 /synthesis/* routes)
// ============================================================================

import type {
  UnifiedSynthesisRunResponse,
  LatestUnifiedReportResponse,
  OpportunityCreateIdeaRequest,
  OpportunityCreateIdeaResponse,
} from '../types';

export const triggerUnifiedSynthesis = async (
  productId: number
): Promise<UnifiedSynthesisRunResponse> => {
  const response = await api.post<UnifiedSynthesisRunResponse>(
    `/products/${productId}/synthesis/run`
  );
  return response.data;
};

export const getLatestUnifiedReport = async (
  productId: number
): Promise<LatestUnifiedReportResponse> => {
  const response = await api.get<LatestUnifiedReportResponse>(
    `/products/${productId}/synthesis/latest`
  );
  return response.data;
};

export const createIdeaFromOpportunity = async (
  productId: number,
  opportunityId: number,
  payload: OpportunityCreateIdeaRequest
): Promise<OpportunityCreateIdeaResponse> => {
  const response = await api.post<OpportunityCreateIdeaResponse>(
    `/products/${productId}/synthesis/opportunities/${opportunityId}/create-idea`,
    payload
  );
  return response.data;
};

// --- Idea Lifecycle Status CRUD (Admin) ---

import type { IdeaLifecycleStatus, IdeaFunnelData } from '../types';

export const getLifecycleStatuses = async (): Promise<IdeaLifecycleStatus[]> => {
  const response = await api.get<IdeaLifecycleStatus[]>('/admin/idea-lifecycle-statuses');
  return response.data;
};

export const createLifecycleStatus = async (data: { name: string; color: string }): Promise<IdeaLifecycleStatus> => {
  const response = await api.post<IdeaLifecycleStatus>('/admin/idea-lifecycle-statuses', data);
  return response.data;
};

export const updateLifecycleStatus = async (
  id: number,
  data: { name?: string; color?: string; position?: number; is_active?: boolean }
): Promise<IdeaLifecycleStatus> => {
  const response = await api.put<IdeaLifecycleStatus>(`/admin/idea-lifecycle-statuses/${id}`, data);
  return response.data;
};

export const deleteLifecycleStatus = async (id: number): Promise<void> => {
  await api.delete(`/admin/idea-lifecycle-statuses/${id}`);
};

// --- Idea Funnel ---

export const getIdeaFunnel = async (productId: number): Promise<IdeaFunnelData> => {
  const response = await api.get<IdeaFunnelData>(
    `/product-intelligence/products/${productId}/idea-funnel`
  );
  return response.data;
};

// ============================================================================
// INVITE CODE API METHODS
// ============================================================================

import type { InviteCodeInfo, InviteCode, ProductMember, UserProduct } from '../types';

export const getInviteInfo = async (code: string): Promise<InviteCodeInfo> => {
  const response = await api.get<InviteCodeInfo>(`/invites/${code}/info`);
  return response.data;
};

export const redeemInviteCode = async (code: string): Promise<{ product_id: number; product_name: string; message: string }> => {
  const response = await api.post('/invites/redeem', { code });
  return response.data;
};

export const createInviteCode = async (
  productId: number,
  options?: { max_uses?: number; expires_at?: string }
): Promise<InviteCode> => {
  const response = await api.post<InviteCode>(
    `/products/${productId}/invite-codes`,
    options || {}
  );
  return response.data;
};

export const getInviteCodes = async (productId: number): Promise<InviteCode[]> => {
  const response = await api.get<InviteCode[]>(`/products/${productId}/invite-codes`);
  return response.data;
};

export const deactivateInviteCode = async (productId: number, codeId: number): Promise<void> => {
  await api.delete(`/products/${productId}/invite-codes/${codeId}`);
};

export const getProductMembers = async (productId: number): Promise<ProductMember[]> => {
  const response = await api.get<ProductMember[]>(`/products/${productId}/members`);
  return response.data;
};

// ============================================================================
// ADMIN PRODUCT ASSIGNMENT API METHODS
// ============================================================================

export const getUserProducts = async (userId: number): Promise<UserProduct[]> => {
  const response = await api.get<UserProduct[]>(`/auth/users/${userId}/products`);
  return response.data;
};

export const setUserProducts = async (userId: number, productIds: number[]): Promise<UserProduct[]> => {
  const response = await api.put<UserProduct[]>(`/auth/users/${userId}/products`, { product_ids: productIds });
  return response.data;
};

// ============================================================================
// EVIDENCE / FACTBASE API METHODS
// ============================================================================

import type { EvidenceDetail, EvidenceListResponse, CreateEvidenceRequest, CompetitorSuggestion } from '../types';

export const getEvidence = async (
  productId: number,
  competitorId?: number,
  evidenceType?: string,
  limit: number = 50,
  offset: number = 0
): Promise<EvidenceListResponse> => {
  const params: Record<string, string | number> = { limit, offset };
  if (competitorId !== undefined) params.competitor_id = competitorId;
  if (evidenceType) params.evidence_type = evidenceType;
  const response = await api.get<EvidenceListResponse>(
    `/product-intelligence/products/${productId}/evidence`,
    { params }
  );
  return response.data;
};

export const createEvidence = async (
  productId: number,
  data: CreateEvidenceRequest
): Promise<EvidenceDetail> => {
  const response = await api.post<EvidenceDetail>(
    `/product-intelligence/products/${productId}/evidence`,
    data
  );
  return response.data;
};

export const deleteEvidence = async (
  productId: number,
  evidenceId: number
): Promise<{ message: string; id: number }> => {
  const response = await api.delete<{ message: string; id: number }>(
    `/product-intelligence/products/${productId}/evidence/${evidenceId}`
  );
  return response.data;
};

export const suggestCompetitorForEvidence = async (
  productId: number,
  title: string,
  content: string
): Promise<CompetitorSuggestion> => {
  const response = await api.post<CompetitorSuggestion>(
    `/product-intelligence/products/${productId}/evidence/suggest-competitor`,
    { title, content }
  );
  return response.data;
};

// ============================================================================
// JTBD JOB MAP API METHODS
// ============================================================================

import type {
  JobMapResponse,
  TargetCustomerProfile,
  JobCreateRequest,
  JobUpdateRequest,
  JtbdJob,
} from '../types';

export const extractJobMap = async (
  productId: number,
  guidance?: string
): Promise<AgentJobResponse> => {
  const params = guidance ? `?guidance=${encodeURIComponent(guidance)}` : '';
  const response = await api.post<AgentJobResponse>(
    `/product-intelligence/products/${productId}/extract-job-map${params}`
  );
  return response.data;
};

export const getJobMap = async (
  productId: number
): Promise<JobMapResponse> => {
  const response = await api.get<JobMapResponse>(
    `/product-intelligence/products/${productId}/job-map`
  );
  return response.data;
};

export const updateTargetCustomer = async (
  productId: number,
  profile: TargetCustomerProfile
): Promise<{ target_customer_profile: TargetCustomerProfile; message: string }> => {
  const response = await api.put<{
    target_customer_profile: TargetCustomerProfile;
    message: string;
  }>(
    `/product-intelligence/products/${productId}/target-customer`,
    profile
  );
  return response.data;
};

export const addJob = async (
  productId: number,
  body: JobCreateRequest
): Promise<JtbdJob & { job_map_version: number }> => {
  const response = await api.post<JtbdJob & { job_map_version: number }>(
    `/product-intelligence/products/${productId}/jobs`,
    body
  );
  return response.data;
};

export const updateJob = async (
  productId: number,
  jobIdKey: string,
  body: JobUpdateRequest
): Promise<JtbdJob & { job_map_version: number }> => {
  const response = await api.put<JtbdJob & { job_map_version: number }>(
    `/product-intelligence/products/${productId}/jobs/${jobIdKey}`,
    body
  );
  return response.data;
};

export const deleteJob = async (
  productId: number,
  jobIdKey: string,
  relink: boolean = true
): Promise<{ product_id: number; removed_job_id: string; job_map_version: number; message: string }> => {
  const response = await api.delete<{
    product_id: number;
    removed_job_id: string;
    job_map_version: number;
    message: string;
  }>(
    `/product-intelligence/products/${productId}/jobs/${jobIdKey}?relink=${relink}`
  );
  return response.data;
};

export const getJobMapComparison = async (
  productId: number
): Promise<import('../types').JobMapComparison> => {
  const response = await api.get<import('../types').JobMapComparison>(
    `/product-intelligence/products/${productId}/job-map/pending-comparison`
  );
  return response.data;
};

export const applyPendingJobMap = async (
  productId: number,
  selections: Array<{
    pair_id: string;
    choice: 'old' | 'new' | 'drop';
    old_job_id_key?: string;
    new_job_data?: import('../types').JobMapJobEntry;
    statement?: string;
    desired_outcomes?: string[];
    importance?: string;
  }>
): Promise<{ product_id: number; job_map_version: number; message: string }> => {
  const response = await api.post<{ product_id: number; job_map_version: number; message: string }>(
    `/product-intelligence/products/${productId}/job-map/apply-pending`,
    { selections }
  );
  return response.data;
};

export const discardPendingJobMap = async (
  productId: number
): Promise<{ product_id: number; message: string }> => {
  const response = await api.delete<{ product_id: number; message: string }>(
    `/product-intelligence/products/${productId}/job-map/pending`
  );
  return response.data;
};

export const getJobSignals = async (
  productId: number,
  jobIdKey: string
): Promise<import('../types').JobSignals> => {
  const response = await api.get<import('../types').JobSignals>(
    `/product-intelligence/products/${productId}/jobs/${jobIdKey}/signals`
  );
  return response.data;
};

export const linkIdeaToJob = async (
  ideaId: number,
  jobIdKey: string | null
): Promise<{ idea_id: number; job_id_key: string | null; job_statement: string | null }> => {
  const response = await api.post<{ idea_id: number; job_id_key: string | null; job_statement: string | null }>(
    `/ideas/${ideaId}/link-job`,
    { job_id_key: jobIdKey }
  );
  return response.data;
};

export const setMainJob = async (
  productId: number,
  mainJob: string
): Promise<{ product_id: number; main_job: string; job_map_version: number }> => {
  const response = await api.put<{ product_id: number; main_job: string; job_map_version: number }>(
    `/product-intelligence/products/${productId}/main-job`,
    { main_job: mainJob }
  );
  return response.data;
};

export const getNeedSuggestions = async (
  productId: number
): Promise<{ product_id: number; suggestions: import('../types').NeedSuggestion[]; count: number }> => {
  const response = await api.get<{ product_id: number; suggestions: import('../types').NeedSuggestion[]; count: number }>(
    `/product-intelligence/products/${productId}/need-suggestions`
  );
  return response.data;
};

export const approveNeedSuggestion = async (
  productId: number,
  suggestionId: number,
  body: { statement: string; desired_outcomes?: string[]; importance?: string }
): Promise<{ new_job_id_key: string; statement: string; job_map_version: number }> => {
  const response = await api.post<{ new_job_id_key: string; statement: string; job_map_version: number }>(
    `/product-intelligence/products/${productId}/need-suggestions/${suggestionId}/approve`,
    body
  );
  return response.data;
};

export const dismissNeedSuggestion = async (
  productId: number,
  suggestionId: number
): Promise<{ suggestion_id: number; status: string }> => {
  const response = await api.post<{ suggestion_id: number; status: string }>(
    `/product-intelligence/products/${productId}/need-suggestions/${suggestionId}/dismiss`,
    {}
  );
  return response.data;
};

// ============================================================================
// UNIFIED SYNTHESIS CONFIG API METHODS
// ============================================================================
// These sit on the /products router (unified_synthesis.py) — distinct from
// the legacy /synthesis/... routes above.

import type {
  SynthesisConfigResponse,
  SynthesisConfigPutRequest,
  SynthesisConfigData,
  SynthesisCompetitorsConfigResponse,
} from '../types';

export const getSynthesisConfig = async (
  productId: number
): Promise<SynthesisConfigResponse> => {
  const response = await api.get<SynthesisConfigResponse>(
    `/products/${productId}/synthesis-config`
  );
  return response.data;
};

export const putSynthesisConfig = async (
  productId: number,
  body: SynthesisConfigPutRequest
): Promise<{ created: boolean; config: SynthesisConfigData }> => {
  const response = await api.put<{ created: boolean; config: SynthesisConfigData }>(
    `/products/${productId}/synthesis-config`,
    body
  );
  return response.data;
};

export const getSynthesisCompetitorsCfg = async (
  productId: number
): Promise<SynthesisCompetitorsConfigResponse> => {
  const response = await api.get<SynthesisCompetitorsConfigResponse>(
    `/products/${productId}/synthesis/competitors`
  );
  return response.data;
};


// Export the axios instance for custom requests
export default api;
