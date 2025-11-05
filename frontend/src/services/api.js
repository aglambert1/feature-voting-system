/**
 * API Service
 *
 * Centralized API client using axios with:
 * - Request interceptors (adds auth tokens)
 * - Response interceptors (handles errors)
 * - All API methods for backend communication
 */

import axios from 'axios';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - Add auth token to all requests
api.interceptors.request.use(
  (config) => {
    // Get token from localStorage
    const token = localStorage.getItem('access_token');

    // If token exists, add to Authorization header
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle errors globally
api.interceptors.response.use(
  (response) => {
    // Return successful response data
    return response;
  },
  (error) => {
    // Handle specific error cases
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;

      if (status === 401) {
        // Unauthorized - clear token and redirect to login
        localStorage.removeItem('access_token');
        window.location.href = '/login';
      }

      // Return error with meaningful message
      return Promise.reject({
        message: error.response.data.detail || 'An error occurred',
        status: status,
        data: error.response.data,
      });
    } else if (error.request) {
      // Request made but no response received
      return Promise.reject({
        message: 'Network error - please check your connection',
        status: 0,
      });
    } else {
      // Error setting up request
      return Promise.reject({
        message: error.message || 'An unexpected error occurred',
        status: 0,
      });
    }
  }
);

// ============================================================================
// AUTH API METHODS
// ============================================================================

/**
 * Login user with username/email and password
 * @param {string} username - Username or email
 * @param {string} password - User password
 * @returns {Promise} - Access token and user data
 */
export const login = async (username, password) => {
  // FastAPI OAuth2 expects form data
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const response = await api.post('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });

  return response.data;
};

/**
 * Register new user
 * @param {Object} userData - User registration data
 * @returns {Promise} - Created user data
 */
export const register = async (userData) => {
  const response = await api.post('/auth/register', userData);
  return response.data;
};

/**
 * Get current user profile
 * @returns {Promise} - Current user data
 */
export const getCurrentUser = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

/**
 * Logout user (client-side only - clear token)
 */
export const logout = () => {
  localStorage.removeItem('access_token');
};

// ============================================================================
// IDEAS API METHODS
// ============================================================================

/**
 * Get all ideas with vote counts
 * @param {number} skip - Pagination offset
 * @param {number} limit - Number of items to return
 * @returns {Promise} - List of ideas
 */
export const getIdeas = async (skip = 0, limit = 100) => {
  const response = await api.get('/ideas', {
    params: { skip, limit },
  });
  return response.data;
};

/**
 * Get single idea by ID
 * @param {number} ideaId - Idea ID
 * @returns {Promise} - Idea data
 */
export const getIdea = async (ideaId) => {
  const response = await api.get(`/ideas/${ideaId}`);
  return response.data;
};

/**
 * Create new idea (direct creation - not through submission flow)
 * @param {Object} ideaData - Idea data (title, what, why, use_case)
 * @returns {Promise} - Created idea
 */
export const createIdea = async (ideaData) => {
  const response = await api.post('/ideas', ideaData);
  return response.data;
};

// ============================================================================
// VOTES API METHODS
// ============================================================================

/**
 * Vote on an idea
 * @param {number} ideaId - Idea ID
 * @param {number} voteValue - Vote value (1 for upvote, -1 for downvote)
 * @returns {Promise} - Updated vote counts
 */
export const voteOnIdea = async (ideaId, voteValue) => {
  const response = await api.post(`/ideas/${ideaId}/vote`, {
    vote_value: voteValue,
  });
  return response.data;
};

// ============================================================================
// SUBMISSIONS API METHODS
// ============================================================================

/**
 * Structure freeform text using AI
 * @param {string} freeformText - User's freeform idea text
 * @returns {Promise} - AI-structured output (what, why, use_case)
 */
export const structureText = async (freeformText) => {
  const response = await api.post('/submissions/structure', {
    freeform_text: freeformText,
  });
  return response.data;
};

/**
 * Submit structured idea
 * @param {Object} submissionData - Complete submission data
 * @returns {Promise} - Created idea
 */
export const submitIdea = async (submissionData) => {
  const response = await api.post('/submissions/submit', submissionData);
  return response.data;
};

// Export the axios instance for custom requests
export default api;
