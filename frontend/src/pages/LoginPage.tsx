import { useState, useRef, useEffect, ChangeEvent, FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { mfaChallenge, getCurrentUser } from '../services/api';
import { UserRole, type User } from '../types';

const LoginPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, setUser } = useAuth();

  const redirectTo = searchParams.get('redirect');

  const [formData, setFormData] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // MFA challenge state
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState('');
  const mfaInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (mfaToken && mfaInputRef.current) {
      mfaInputRef.current.focus();
    }
  }, [mfaToken]);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError('');
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await login(formData.username, formData.password);

      if (result.mfaRequired && result.mfaToken) {
        setMfaToken(result.mfaToken);
        setLoading(false);
        return;
      }

      if (result.success && result.user) {
        navigate(redirectTo || defaultLandingFor(result.user));
      } else if (result.success) {
        navigate(redirectTo || '/');
      } else {
        setError(result.error || 'Login failed');
      }
    } catch {
      setError('An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleMfaSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!mfaToken) return;
    setError('');
    setLoading(true);

    try {
      const data = await mfaChallenge(mfaToken, mfaCode);

      if (!data.access_token) {
        setError('MFA verification failed.');
        setLoading(false);
        return;
      }

      localStorage.setItem('access_token', data.access_token);

      const userData = await getCurrentUser();
      setUser(userData);
      window.dispatchEvent(new Event('user-logged-in'));

      navigate(redirectTo || defaultLandingFor(userData));
    } catch (err) {
      const apiErr = err as { message?: string };
      setError(apiErr?.message || 'Invalid verification code.');
      setMfaCode('');
    } finally {
      setLoading(false);
    }
  };

  function defaultLandingFor(user: User): string {
    if (user.must_change_password) return '/profile?force_password_change=1';
    const isPO = user.role === UserRole.ADMIN || user.role === UserRole.PRODUCT_OWNER;
    if (isPO && !user.has_seen_welcome) return '/welcome';
    if (isPO) return '/product-intelligence';
    return '/ideas';
  }

  // MFA challenge screen
  if (mfaToken) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            <h2 className="text-3xl font-bold text-gray-900">Two-Factor Authentication</h2>
            <p className="mt-2 text-sm text-gray-600">
              Enter the 6-digit code from your authenticator app
            </p>
          </div>

          <form className="mt-8 space-y-6" onSubmit={handleMfaSubmit}>
            {error && (
              <div className="bg-red-50 border border-red-400 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}

            <div>
              <input
                ref={mfaInputRef}
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={mfaCode}
                onChange={(e) => { setMfaCode(e.target.value.replace(/\D/g, '')); setError(''); }}
                className="block w-full px-3 py-3 border border-gray-300 rounded-md shadow-sm text-center text-2xl tracking-widest font-mono focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="000000"
              />
            </div>

            <button
              type="submit"
              disabled={loading || mfaCode.length !== 6}
              className={`w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white ${
                loading || mfaCode.length !== 6
                  ? 'bg-blue-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
              }`}
            >
              {loading ? 'Verifying...' : 'Verify'}
            </button>

            <button
              type="button"
              onClick={() => { setMfaToken(null); setMfaCode(''); setError(''); }}
              className="w-full text-sm text-gray-600 hover:text-gray-800"
            >
              Back to login
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Feature-IQ</h2>
          <p className="mt-2 text-sm text-gray-600">Sign in to your account</p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-50 border border-red-400 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                Username or Email
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={formData.username}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="Enter username or email"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={formData.password}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="Enter password"
              />
            </div>
          </div>

          <div className="flex justify-end">
            <Link to="/forgot-password" className="text-sm font-medium text-blue-600 hover:text-blue-500">
              Forgot your password?
            </Link>
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
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
