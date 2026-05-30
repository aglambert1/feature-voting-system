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

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import * as api from '../services/api';
import type { User, AuthResult } from '../types';

interface AuthContextType {
  user: User | null;
  setUser: (user: User | null) => void;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<AuthResult>;
  register: (userData: {
    email: string;
    username: string;
    password: string;
    full_name?: string;
    invite_code?: string;
  }) => Promise<AuthResult>;
  logout: () => void;
  isAuthenticated: () => boolean;
}

// Create the context
const AuthContext = createContext<AuthContextType | null>(null);

/**
 * Hook to use auth context
 * Must be used within AuthProvider
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * AuthProvider component
 * Wraps the app and provides authentication state
 */
export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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
   */
  const login = async (username: string, password: string): Promise<AuthResult> => {
    try {
      setError(null);

      // Call login API
      const data = await api.login(username, password);

      // Store token
      localStorage.setItem('access_token', data.access_token);

      // Get user data
      const userData = await api.getCurrentUser();
      setUser(userData);

      // Notify other components that user logged in (e.g., ProductContext)
      window.dispatchEvent(new Event('user-logged-in'));

      return { success: true, user: userData };
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Login failed';
      setError(errorMsg);
      return { success: false, error: errorMsg };
    }
  };

  /**
   * Register new user
   */
  const register = async (userData: {
    email: string;
    username: string;
    password: string;
    full_name?: string;
    invite_code?: string;
  }): Promise<AuthResult> => {
    try {
      setError(null);

      // Call register API
      await api.register(userData);

      // Auto-login after registration
      const loginResult = await login(userData.username, userData.password);

      return loginResult;
    } catch (err: unknown) {
      const apiErr = err as { message?: string };
      const errorMsg = apiErr?.message || 'Registration failed';
      setError(errorMsg);
      return { success: false, error: errorMsg };
    }
  };

  /**
   * Logout user
   */
  const logout = (): void => {
    api.logout();
    setUser(null);
    setError(null);
  };

  /**
   * Check if user is authenticated
   */
  const isAuthenticated = (): boolean => {
    return user !== null;
  };

  // Context value
  const value: AuthContextType = {
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
