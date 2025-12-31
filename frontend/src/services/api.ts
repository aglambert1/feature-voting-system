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

// Response interceptor - Handle errors globally
api.interceptors.response.use(
  (response: AxiosResponse) => {
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
};

// ============================================================================
// IDEAS API METHODS
// ============================================================================

interface GetIdeasParams {
  skip?: number;
  limit?: number;
  product_id?: number;
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
 */
export const getProductJobs = async (productId: number, limit: number = 10): Promise<QueueJob[]> => {
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

// Export the axios instance for custom requests
export default api;
