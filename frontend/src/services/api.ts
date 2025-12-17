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
      const apiError: ApiError = {
        message: (error.response.data as any)?.detail || 'An error occurred',
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
 * Structure freeform text using AI
 */
export const structureText = async (freeformText: string): Promise<StructureResponse> => {
  const response = await api.post<StructureResponse>('/submissions/structure', {
    freeform_text: freeformText,
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

// Export the axios instance for custom requests
export default api;
