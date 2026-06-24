/**
 * RegisterPage
 *
 * User registration page with invite code requirement:
 * - Reads invite code from URL query param (?invite=ABC123)
 * - Validates code and shows product name
 * - If no code: shows "need invite link" message
 * - Auto-login after registration
 */

import { useState, useEffect, ChangeEvent, FormEvent } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { getInviteInfo } from '../services/api';

interface FormData {
  email: string;
  username: string;
  password: string;
  full_name: string;
  manual_code: string;
}

interface ValidationErrors {
  email?: string;
  username?: string;
  password?: string;
  full_name?: string;
  manual_code?: string;
}

const RegisterPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { register } = useAuth();

  const inviteCode = searchParams.get('invite');

  // Invite state
  const [inviteValid, setInviteValid] = useState<boolean | null>(null);
  const [productName, setProductName] = useState<string>('');
  const [inviteLoading, setInviteLoading] = useState<boolean>(!!inviteCode);
  const [inviteError, setInviteError] = useState<string>('');
  const [manualCodeMode, setManualCodeMode] = useState<boolean>(!inviteCode);
  const [validatingManualCode, setValidatingManualCode] = useState<boolean>(false);

  // Form state
  const [formData, setFormData] = useState<FormData>({
    email: '',
    username: '',
    password: '',
    full_name: '',
    manual_code: '',
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [validationErrors, setValidationErrors] = useState<ValidationErrors>({});

  // Validate invite code from URL on mount
  useEffect(() => {
    if (!inviteCode) {
      return;
    }

    const validateCode = async () => {
      try {
        const info = await getInviteInfo(inviteCode);
        setInviteValid(info.valid);
        if (info.valid && info.product_name) {
          setProductName(info.product_name);
          setManualCodeMode(false);
        } else {
          setInviteError(info.message || 'Invalid invite code');
        }
      } catch {
        setInviteValid(false);
        setInviteError('Unable to validate invite code');
      } finally {
        setInviteLoading(false);
      }
    };

    validateCode();
  }, [inviteCode]);

  // Extract invite code from input (handles full URLs like http://host/join/CODE)
  const extractCode = (input: string): string => {
    const trimmed = input.trim();
    const joinMatch = trimmed.match(/\/join\/(.+)$/);
    if (joinMatch && joinMatch[1]) return joinMatch[1];
    return trimmed;
  };

  // Validate manually entered invite code
  const handleValidateManualCode = async () => {
    const code = extractCode(formData.manual_code);
    if (!code) {
      setValidationErrors((prev) => ({ ...prev, manual_code: 'Please enter an invite code' }));
      return;
    }

    setValidatingManualCode(true);
    setInviteError('');
    try {
      const info = await getInviteInfo(code);
      if (info.valid && info.product_name) {
        setInviteValid(true);
        setProductName(info.product_name);
        setManualCodeMode(false);
      } else {
        setInviteValid(false);
        setInviteError(info.message || 'Invalid or expired invite code');
      }
    } catch {
      setInviteValid(false);
      setInviteError('Unable to validate invite code');
    } finally {
      setValidatingManualCode(false);
    }
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError('');
    setValidationErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const validateForm = (): boolean => {
    const errors: ValidationErrors = {};

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!formData.email) {
      errors.email = 'Email is required';
    } else if (!emailRegex.test(formData.email)) {
      errors.email = 'Invalid email format';
    }

    if (!formData.username) {
      errors.username = 'Username is required';
    } else if (formData.username.length < 3) {
      errors.username = 'Username must be at least 3 characters';
    }

    if (!formData.password) {
      errors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters';
    }

    if (formData.full_name && formData.full_name.length < 2) {
      errors.full_name = 'Full name must be at least 2 characters';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');

    if (!validateForm()) return;

    setLoading(true);

    try {
      const effectiveCode = inviteCode || extractCode(formData.manual_code);
      const result = await register({
        email: formData.email,
        username: formData.username,
        password: formData.password,
        full_name: formData.full_name,
        invite_code: effectiveCode || undefined,
      });

      if (result.success) {
        navigate('/');
      } else {
        setError(result.error || 'Registration failed');
      }
    } catch {
      setError('An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Loading state while validating invite
  if (inviteLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500">Validating invite...</div>
      </div>
    );
  }

  // Invalid invite code from URL (not manual mode)
  if (inviteCode && !inviteValid && !inviteLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full text-center space-y-6">
          <h2 className="text-2xl font-bold text-gray-900">Invalid Invite</h2>
          <p className="text-red-600">
            {inviteError || 'This invite link is invalid or has expired.'}
          </p>
          <div className="space-x-4">
            <Link
              to="/register"
              className="inline-block px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Enter Code Manually
            </Link>
            <Link
              to="/login"
              className="inline-block px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
            >
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Manual code entry mode or valid invite — show registration form
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-12">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Create an Account</h2>
          <p className="mt-2 text-sm text-gray-600">Join Feature-IQ</p>
        </div>

        {/* Invite banner when code is validated */}
        {inviteValid && productName && (
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4 text-center">
            <p className="text-sm text-blue-800">
              You've been invited to vote on <span className="font-semibold">{productName}</span>
            </p>
          </div>
        )}

        {/* Manual invite code entry */}
        {manualCodeMode && (
          <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
            <label htmlFor="manual_code" className="block text-sm font-medium text-gray-700 mb-1">
              Invite Code
            </label>
            <p className="text-xs text-gray-500 mb-2">
              Enter the invite code you received from a Product Owner.
            </p>
            <div className="flex gap-2">
              <input
                id="manual_code"
                name="manual_code"
                type="text"
                value={formData.manual_code}
                onChange={handleChange}
                className={`flex-1 px-3 py-2 border ${
                  validationErrors.manual_code || inviteError ? 'border-red-500' : 'border-gray-300'
                } rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm`}
                placeholder="Paste invite code"
              />
              <button
                type="button"
                onClick={handleValidateManualCode}
                disabled={validatingManualCode || !formData.manual_code.trim()}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {validatingManualCode ? 'Checking...' : 'Verify'}
              </button>
            </div>
            {validationErrors.manual_code && (
              <p className="mt-1 text-sm text-red-600">{validationErrors.manual_code}</p>
            )}
            {inviteError && (
              <p className="mt-1 text-sm text-red-600">{inviteError}</p>
            )}
          </div>
        )}

        {/* Registration form — shown after invite is validated */}
        {inviteValid && (
          <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="bg-red-50 border border-red-400 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                  Email Address *
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  className={`mt-1 block w-full px-3 py-2 border ${
                    validationErrors.email ? 'border-red-500' : 'border-gray-300'
                  } rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
                  placeholder="you@example.com"
                />
                {validationErrors.email && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.email}</p>
                )}
              </div>

              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                  Username *
                </label>
                <input
                  id="username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  required
                  value={formData.username}
                  onChange={handleChange}
                  className={`mt-1 block w-full px-3 py-2 border ${
                    validationErrors.username ? 'border-red-500' : 'border-gray-300'
                  } rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
                  placeholder="johndoe"
                />
                {validationErrors.username && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.username}</p>
                )}
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                  Password *
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={formData.password}
                  onChange={handleChange}
                  className={`mt-1 block w-full px-3 py-2 border ${
                    validationErrors.password ? 'border-red-500' : 'border-gray-300'
                  } rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
                  placeholder="Min 8 chars, upper/lower/digit/special"
                />
                {validationErrors.password && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.password}</p>
                )}
              </div>

              <div>
                <label htmlFor="full_name" className="block text-sm font-medium text-gray-700">
                  Full Name (optional)
                </label>
                <input
                  id="full_name"
                  name="full_name"
                  type="text"
                  autoComplete="name"
                  value={formData.full_name}
                  onChange={handleChange}
                  className={`mt-1 block w-full px-3 py-2 border ${
                    validationErrors.full_name ? 'border-red-500' : 'border-gray-300'
                  } rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
                  placeholder="John Doe"
                />
                {validationErrors.full_name && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.full_name}</p>
                )}
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={loading}
                className={`w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white ${
                  loading
                    ? 'bg-blue-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
                }`}
              >
                {loading ? 'Creating account...' : 'Create Account'}
              </button>
            </div>

            <div className="text-center">
              <p className="text-sm text-gray-600">
                Already have an account?{' '}
                <Link to="/login" className="font-medium text-blue-600 hover:text-blue-500">
                  Sign in here
                </Link>
              </p>
            </div>
          </form>
        )}

        {/* Sign in link when no invite validated yet */}
        {!inviteValid && (
          <div className="text-center">
            <p className="text-sm text-gray-600">
              Already have an account?{' '}
              <Link to="/login" className="font-medium text-blue-600 hover:text-blue-500">
                Sign in here
              </Link>
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default RegisterPage;
