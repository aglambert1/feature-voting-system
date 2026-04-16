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
  IdeaCreate,
  VoteResponse,
  StructureResponse,
  SubmissionData,
  ApiError,
  Product,
  ProductCreate,
  Competitor,
  CompetitorCreate,
  Feature,
  FeatureCreate,
  AnalysisSession,
  SimilarIdea,
  QueueJob,
  PMReviewQueueItem,
  PMReviewQueueResponse,
  PMReviewQueueStats,
  MonitoringConfig,
  MonitoringConfigUpdate,
  CompetitorSnapshotsResponse,
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
  CompetitorFeature,
  AgentJobResponse,
  CreateIdeasRequest,
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
 * Get single idea by ID
 */
export const getIdea = async (ideaId: number): Promise<IdeaResponse> => {
  const response = await api.get<IdeaResponse>(`/ideas/${ideaId}`);
  return response.data;
};

/**
 * Create new idea (direct creation - not through submission flow)
 */
export const createIdea = async (ideaData: IdeaCreate): Promise<IdeaResponse> => {
  const response = await api.post<IdeaResponse>('/ideas', ideaData);
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

/**
 * Get all products
 */
export const getProducts = async (): Promise<Product[]> => {
  const response = await api.get<Product[]>('/products');
  return response.data;
};

/**
 * Get single product by ID
 */
export const getProduct = async (productId: number): Promise<Product> => {
  const response = await api.get<Product>(`/products/${productId}`);
  return response.data;
};

/**
 * Create new product
 */
export const createProduct = async (productData: ProductCreate): Promise<Product> => {
  const response = await api.post<Product>('/products', productData);
  return response.data;
};

/**
 * Update product
 */
export const updateProduct = async (productId: number, productData: ProductCreate): Promise<Product> => {
  const response = await api.put<Product>(`/products/${productId}`, productData);
  return response.data;
};

/**
 * Delete product
 */
export const deleteProduct = async (productId: number): Promise<void> => {
  await api.delete(`/products/${productId}`);
};

// ============================================================================
// COMPETITORS API METHODS
// ============================================================================

/**
 * Get competitors for a product
 */
export const getCompetitors = async (productId: number): Promise<Competitor[]> => {
  const response = await api.get<Competitor[]>(`/products/${productId}/competitors`);
  return response.data;
};

/**
 * Create competitor
 */
export const createCompetitor = async (productId: number, competitorData: CompetitorCreate): Promise<Competitor> => {
  const response = await api.post<Competitor>(`/products/${productId}/competitors`, competitorData);
  return response.data;
};

/**
 * Delete competitor
 */
export const deleteCompetitor = async (productId: number, competitorId: number): Promise<void> => {
  await api.delete(`/products/${productId}/competitors/${competitorId}`);
};

/**
 * Deactivate competitor (soft delete - hides from list, preserves reports)
 */
export const deactivateCompetitor = async (productId: number, competitorId: number): Promise<void> => {
  await api.post(`/product-intelligence/agents/${productId}/competitors/${competitorId}/deactivate`);
};

// ============================================================================
// FEATURES API METHODS
// ============================================================================

/**
 * Get features for a product
 */
export const getFeatures = async (productId: number): Promise<Feature[]> => {
  const response = await api.get<Feature[]>(`/products/${productId}/features`);
  return response.data;
};

/**
 * Create feature
 */
export const createFeature = async (productId: number, featureData: FeatureCreate): Promise<Feature> => {
  const response = await api.post<Feature>(`/products/${productId}/features`, featureData);
  return response.data;
};

/**
 * Delete feature
 */
export const deleteFeature = async (productId: number, featureId: number): Promise<void> => {
  await api.delete(`/products/${productId}/features/${featureId}`);
};

// ============================================================================
// ANALYSIS SESSIONS API METHODS
// ============================================================================

/**
 * Get or create analysis session for a product
 */
export const getOrCreateSession = async (productId: number): Promise<AnalysisSession> => {
  const response = await api.get<AnalysisSession>(`/products/${productId}/session`);
  return response.data;
};

/**
 * Update analysis session
 */
export const updateSession = async (
  productId: number,
  stage: number,
  sessionData: Record<string, any>
): Promise<AnalysisSession> => {
  const response = await api.put<AnalysisSession>(`/products/${productId}/session`, {
    stage,
    session_data: sessionData,
  });
  return response.data;
};

// ============================================================================
// USERS API METHODS (Admin only)
// ============================================================================

/**
 * Get all users (Admin only)
 */
export const getUsers = async (): Promise<User[]> => {
  const response = await api.get<User[]>('/users');
  return response.data;
};

/**
 * Create user (Admin only)
 */
export const createUser = async (userData: RegisterData): Promise<User> => {
  const response = await api.post<User>('/users', userData);
  return response.data;
};

/**
 * Update user role (Admin only)
 */
export const updateUserRole = async (userId: number, role: string): Promise<User> => {
  const response = await api.put<User>(`/users/${userId}/role`, { role });
  return response.data;
};

/**
 * Toggle user active status (Admin only)
 */
export const toggleUserActive = async (userId: number): Promise<User> => {
  const response = await api.put<User>(`/users/${userId}/toggle-active`);
  return response.data;
};

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

/**
 * Cancel a job
 */
export const cancelJob = async (jobUuid: string): Promise<QueueJob> => {
  const response = await api.post<QueueJob>(`/product-intelligence/jobs/${jobUuid}/cancel`);
  return response.data;
};

// ============================================================================
// PM REVIEW QUEUE API METHODS (Phase 4)
// ============================================================================

interface GetQueueParams {
  product_id?: number;
  queue_type?: string;
  status?: string;
  priority?: string;
  offset?: number;
  limit?: number;
}

/**
 * Get PM review queue items
 */
export const getReviewQueue = async (params: GetQueueParams = {}): Promise<PMReviewQueueResponse> => {
  const response = await api.get<PMReviewQueueResponse>('/pm-review/queue', { params });
  return response.data;
};

/**
 * Get single queue item by ID
 */
export const getReviewQueueItem = async (itemId: number): Promise<PMReviewQueueItem> => {
  const response = await api.get<PMReviewQueueItem>(`/pm-review/queue/${itemId}`);
  return response.data;
};

/**
 * Get queue stats for a product
 */
export const getReviewQueueStats = async (productId: number): Promise<PMReviewQueueStats> => {
  const response = await api.get<PMReviewQueueStats>(`/pm-review/stats/${productId}`);
  return response.data;
};

/**
 * Assign queue item to user
 */
export const assignQueueItem = async (itemId: number, userId: number | null): Promise<PMReviewQueueItem> => {
  const response = await api.post<PMReviewQueueItem>(`/pm-review/queue/${itemId}/assign`, {
    user_id: userId,
  });
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

/**
 * Batch approve queue items
 */
export const batchApproveQueueItems = async (itemIds: number[], notes?: string): Promise<{ updated: number }> => {
  const response = await api.post<{ updated: number }>('/pm-review/queue/batch/approve', {
    item_ids: itemIds,
    notes,
  });
  return response.data;
};

/**
 * Batch reject queue items
 */
export const batchRejectQueueItems = async (itemIds: number[], notes?: string): Promise<{ updated: number }> => {
  const response = await api.post<{ updated: number }>('/pm-review/queue/batch/reject', {
    item_ids: itemIds,
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
 * Update monitoring config
 */
export const updateMonitoringConfig = async (
  productId: number,
  config: MonitoringConfigUpdate
): Promise<MonitoringConfig> => {
  const response = await api.put<MonitoringConfig>(`/monitoring/config/${productId}`, config);
  return response.data;
};

/**
 * Enable monitoring for a product
 */
export const enableMonitoring = async (productId: number): Promise<MonitoringConfig> => {
  const response = await api.post<MonitoringConfig>(`/monitoring/config/${productId}/enable`);
  return response.data;
};

/**
 * Disable monitoring for a product
 */
export const disableMonitoring = async (productId: number): Promise<MonitoringConfig> => {
  const response = await api.post<MonitoringConfig>(`/monitoring/config/${productId}/disable`);
  return response.data;
};

/**
 * Get competitor snapshots for a product
 */
export const getCompetitorSnapshots = async (
  productId: number,
  params: { competitor_id?: number; has_changes?: boolean; limit?: number } = {}
): Promise<CompetitorSnapshotsResponse> => {
  const response = await api.get<CompetitorSnapshotsResponse>(`/monitoring/snapshots/${productId}`, {
    params,
  });
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
 * Get comments for an idea
 */
export const getIdeaComments = async (ideaId: number): Promise<IdeaComment[]> => {
  const response = await api.get<IdeaComment[]>(`/ideas/${ideaId}/comments`);
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

/**
 * Trigger product reanalysis
 */
export const triggerProductReanalysis = async (productId: number): Promise<AgentJobResponse> => {
  const response = await api.post<AgentJobResponse>(
    `/product-intelligence/agents/${productId}/reanalyze-product`
  );
  return response.data;
};

// --- Competitor Management ---

/**
 * List competitors with deep analysis status
 */
export const getAgentCompetitors = async (
  productId: number,
  deepAnalysisEnabled?: boolean
): Promise<AgentCompetitor[]> => {
  const response = await api.get<AgentCompetitor[]>(
    `/product-intelligence/agents/${productId}/competitors`,
    { params: deepAnalysisEnabled !== undefined ? { deep_analysis_enabled: deepAnalysisEnabled } : {} }
  );
  return response.data;
};

/**
 * Enable deep analysis for a competitor
 */
export const enableDeepAnalysis = async (
  productId: number,
  competitorId: number
): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/enable-deep-analysis`
  );
  return response.data;
};

/**
 * Disable deep analysis for a competitor
 */
export const disableDeepAnalysis = async (
  productId: number,
  competitorId: number
): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/disable-deep-analysis`
  );
  return response.data;
};

/**
 * Update competitor selection (enable/disable deep analysis)
 */
export const updateCompetitorSelection = async (
  productId: number,
  competitorId: number,
  enabled: boolean
): Promise<{ message: string }> => {
  if (enabled) {
    return enableDeepAnalysis(productId, competitorId);
  } else {
    return disableDeepAnalysis(productId, competitorId);
  }
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
  deep_analysis_enabled: boolean;
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

/**
 * List features for a competitor
 */
export const getCompetitorFeatures = async (
  productId: number,
  competitorId: number
): Promise<CompetitorFeature[]> => {
  const response = await api.get<CompetitorFeature[]>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/features`
  );
  return response.data;
};

/**
 * Create an idea from a single feature
 */
export const createIdeaFromFeature = async (
  productId: number,
  competitorId: number,
  featureId: number
): Promise<AgentJobResponse> => {
  const response = await api.post<AgentJobResponse>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/features/${featureId}/create-idea`
  );
  return response.data;
};

/**
 * Create ideas from multiple features
 */
export const createIdeasFromFeatures = async (
  productId: number,
  competitorId: number,
  request: CreateIdeasRequest
): Promise<AgentJobResponse[]> => {
  const response = await api.post<AgentJobResponse[]>(
    `/product-intelligence/agents/${productId}/competitors/${competitorId}/features/create-ideas`,
    request
  );
  return response.data;
};

// ============================================================================
// V2 COMPETITIVE ANALYSIS API METHODS
// ============================================================================

// Import V2 types at runtime (they're already in types.ts)
import type {
  FunctionalReportSummary,
  FunctionalReportDetail,
  LandscapeReportDetail,
  BatchIdeaStatusesResponse,
  FeatureOpportunitiesExport,
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
 * Get landscape report for a product
 */
export const getLandscapeReport = async (productId: number): Promise<LandscapeReportDetail | null> => {
  const response = await api.get<LandscapeReportDetail | null>(
    `/product-intelligence/agents/${productId}/landscape-report`
  );
  return response.data;
};

/**
 * Trigger landscape synthesis
 */
export const triggerLandscapeSynthesis = async (productId: number): Promise<AgentJobResponse> => {
  const response = await api.post<AgentJobResponse>(
    `/product-intelligence/agents/${productId}/run-landscape-synthesis`
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

/**
 * Export landscape report as markdown
 */
export const exportLandscapeReportMd = async (productId: number): Promise<string> => {
  const response = await api.get<string>(
    `/product-intelligence/agents/${productId}/landscape-report/export`,
    { headers: { Accept: 'text/markdown' } }
  );
  return response.data;
};

/**
 * Get idea statuses for all opportunities
 */
export const getOpportunityIdeaStatuses = async (productId: number): Promise<BatchIdeaStatusesResponse> => {
  const response = await api.get<BatchIdeaStatusesResponse>(
    `/product-intelligence/agents/${productId}/landscape-report/idea-statuses`
  );
  return response.data;
};

/**
 * Create ideas from selected opportunities
 */
export const createIdeasFromOpportunities = async (
  productId: number,
  opportunityIndices: number[]
): Promise<AgentJobResponse[]> => {
  const response = await api.post<AgentJobResponse[]>(
    `/product-intelligence/agents/${productId}/landscape-report/create-ideas`,
    { opportunity_indices: opportunityIndices }
  );
  return response.data;
};

/**
 * Export selected opportunities as JSON
 */
export const exportOpportunitiesJson = async (
  productId: number,
  opportunityIndices: number[]
): Promise<FeatureOpportunitiesExport> => {
  const response = await api.post<FeatureOpportunitiesExport>(
    `/product-intelligence/agents/${productId}/landscape-report/export-json`,
    { opportunity_indices: opportunityIndices }
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
 * Get a single import by ID
 */
export const getInternalFeedbackImport = async (
  productId: number,
  importId: number
): Promise<InternalFeedbackImport> => {
  const response = await api.get<InternalFeedbackImport>(
    `/internal-feedback/${productId}/imports/${importId}`
  );
  return response.data;
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
// SYNTHESIS API
// ============================================================================

import type {
  SynthesisStatusResponse,
  SynthesisRun,
  SynthesisResultsResponse,
} from '../types';

/**
 * Get synthesis status and available sources
 */
export const getSynthesisStatus = async (
  productId: number
): Promise<SynthesisStatusResponse> => {
  const response = await api.get<SynthesisStatusResponse>(
    `/synthesis/${productId}/status`
  );
  return response.data;
};

/**
 * Trigger a new synthesis run
 */
export const triggerSynthesis = async (
  productId: number
): Promise<SynthesisRun> => {
  const response = await api.post<SynthesisRun>(
    `/synthesis/${productId}/run`
  );
  return response.data;
};

/**
 * Get all synthesis runs for a product
 */
export const getSynthesisRuns = async (
  productId: number
): Promise<{ runs: SynthesisRun[]; total: number }> => {
  const response = await api.get<{ runs: SynthesisRun[]; total: number }>(
    `/synthesis/${productId}/runs`
  );
  return response.data;
};

/**
 * Get full synthesis results including opportunities
 */
export const getSynthesisResults = async (
  productId: number,
  runId: number
): Promise<SynthesisResultsResponse> => {
  const response = await api.get<SynthesisResultsResponse>(
    `/synthesis/${productId}/runs/${runId}`
  );
  return response.data;
};

/**
 * Get the latest completed synthesis results
 */
export const getLatestSynthesis = async (
  productId: number
): Promise<SynthesisResultsResponse> => {
  const response = await api.get<SynthesisResultsResponse>(
    `/synthesis/${productId}/latest`
  );
  return response.data;
};

/**
 * Helper to trigger file download from blob
 */
const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

/**
 * Export synthesis results as JSON
 * Makes authenticated request and triggers download
 */
export const exportSynthesisJson = async (
  productId: number,
  runId: number,
  productName?: string
): Promise<void> => {
  try {
    const response = await api.get(
      `/synthesis/${productId}/runs/${runId}/export/json`,
      { responseType: 'blob' }
    );

    const filename = productName
      ? `synthesis_${productName.replace(/\s+/g, '_')}_${runId}.json`
      : `synthesis_${productId}_${runId}.json`;

    downloadBlob(response.data, filename);
  } catch (error) {
    console.error('Export JSON failed:', error);
    throw error;
  }
};

/**
 * Export synthesis results as CSV
 * Makes authenticated request and triggers download
 */
export const exportSynthesisCsv = async (
  productId: number,
  runId: number,
  productName?: string
): Promise<void> => {
  try {
    const response = await api.get(
      `/synthesis/${productId}/runs/${runId}/export/csv`,
      { responseType: 'blob' }
    );

    const filename = productName
      ? `synthesis_${productName.replace(/\s+/g, '_')}_${runId}.csv`
      : `synthesis_${productId}_${runId}.csv`;

    downloadBlob(response.data, filename);
  } catch (error) {
    console.error('Export CSV failed:', error);
    throw error;
  }
};

/**
 * Create an idea from a synthesized opportunity
 */
export const createIdeaFromOpportunity = async (
  productId: number,
  opportunityId: number,
  additionalDescription?: string
): Promise<{ idea_id: number; title: string; status: string }> => {
  const response = await api.post(
    `/synthesis/${productId}/opportunities/${opportunityId}/create-idea`,
    { additional_description: additionalDescription }
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

export const getEvidenceDetail = async (
  productId: number,
  evidenceId: number
): Promise<EvidenceDetail> => {
  const response = await api.get<EvidenceDetail>(
    `/product-intelligence/products/${productId}/evidence/${evidenceId}`
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
  jobIdKey: string
): Promise<{ product_id: number; removed_job_id: string; job_map_version: number; message: string }> => {
  const response = await api.delete<{
    product_id: number;
    removed_job_id: string;
    job_map_version: number;
    message: string;
  }>(
    `/product-intelligence/products/${productId}/jobs/${jobIdKey}`
  );
  return response.data;
};

// Export the axios instance for custom requests
export default api;
