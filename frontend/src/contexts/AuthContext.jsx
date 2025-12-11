/**
 * AuthContext
 *
 * Provides authentication state and methods throughout the app.
 * Manages:
 * - User login/logout
 * - Token storage
 * - Current user data
 * - Authentication status
 */

import { createContext, useContext, useState, useEffect } from 'react';
import * as api from '../services/api';

// Create the context
const AuthContext = createContext(null);

/**
 * Hook to use auth context
 * Must be used within AuthProvider
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

/**
 * AuthProvider component
 * Wraps the app and provides authentication state
 */
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check if user is authenticated on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token');

      if (token) {
        try {
          // Verify token is valid by fetching current user
          const userData = await api.getCurrentUser();
          setUser(userData);
        } catch (err) {
          console.error('Failed to verify token:', err);
          // Token is invalid, clear it
          localStorage.removeItem('access_token');
        }
      }

      setLoading(false);
    };

    initAuth();
  }, []);

  /**
   * Login user
   * @param {string} username - Username or email
   * @param {string} password - Password
   */
  const login = async (username, password) => {
    try {
      setError(null);

      // Call login API
      const data = await api.login(username, password);

      // Store token
      localStorage.setItem('access_token', data.access_token);

      // Get user data
      const userData = await api.getCurrentUser();
      setUser(userData);

      return { success: true };
    } catch (err) {
      const errorMsg = err.message || 'Login failed';
      setError(errorMsg);
      return { success: false, error: errorMsg };
    }
  };

  /**
   * Register new user
   * @param {Object} userData - Registration data
   */
  const register = async (userData) => {
    try {
      setError(null);

      // Call register API
      await api.register(userData);

      // Auto-login after registration
      const loginResult = await login(userData.username, userData.password);

      return loginResult;
    } catch (err) {
      const errorMsg = err.message || 'Registration failed';
      setError(errorMsg);
      return { success: false, error: errorMsg };
    }
  };

  /**
   * Logout user
   */
  const logout = () => {
    api.logout();
    setUser(null);
    setError(null);
  };

  /**
   * Check if user is authenticated
   */
  const isAuthenticated = () => {
    return user !== null;
  };

  // Context value
  const value = {
    user,
    setUser,
    loading,
    error,
    login,
    register,
    logout,
    isAuthenticated,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthContext;
