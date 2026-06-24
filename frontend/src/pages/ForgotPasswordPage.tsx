import { useState, ChangeEvent, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { requestPasswordReset, confirmPasswordReset } from '../services/api';
import type { ApiError } from '../types';

type Step = 'email' | 'otp' | 'success';

const ForgotPasswordPage = () => {
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleRequestReset = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await requestPasswordReset(email);
      setStep('otp');
    } catch (err) {
      const apiError = err as ApiError;
      if (apiError.status === 429) {
        setError('Too many requests. Please wait a minute before trying again.');
      } else {
        setError(apiError.message || 'Failed to send reset code. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const validatePassword = (pw: string): string | null => {
    if (pw.length < 8) return 'Password must be at least 8 characters long';
    const missing = [];
    if (!/[A-Z]/.test(pw)) missing.push('one uppercase letter');
    if (!/[a-z]/.test(pw)) missing.push('one lowercase letter');
    if (!/\d/.test(pw)) missing.push('one digit');
    if (!/[^A-Za-z0-9]/.test(pw)) missing.push('one special character');
    if (missing.length > 0) return `Password must contain at least: ${missing.join(', ')}`;
    return null;
  };

  const handleConfirmReset = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    const pwError = validatePassword(newPassword);
    if (pwError) {
      setError(pwError);
      return;
    }

    setLoading(true);

    try {
      await confirmPasswordReset(email, otp, newPassword);
      setStep('success');
    } catch (err) {
      const apiError = err as ApiError;
      if (apiError.status === 429) {
        setError('Too many attempts. Please wait a minute before trying again.');
      } else {
        setError(apiError.message || 'Failed to reset password. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setError('');
    setLoading(true);
    try {
      await requestPasswordReset(email);
      setError('');
    } catch (err) {
      const apiError = err as ApiError;
      if (apiError.status === 429) {
        setError('Too many requests. Please wait a minute before trying again.');
      } else {
        setError(apiError.message || 'Failed to resend code.');
      }
    } finally {
      setLoading(false);
    }
  };

  const inputClassName =
    'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500';

  const buttonClassName = (disabled: boolean) =>
    `w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white ${
      disabled
        ? 'bg-blue-400 cursor-not-allowed'
        : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
    }`;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Feature-IQ</h2>
          {step === 'email' && (
            <p className="mt-2 text-sm text-gray-600">
              Reset your password
            </p>
          )}
          {step === 'otp' && (
            <p className="mt-2 text-sm text-gray-600">
              Enter verification code
            </p>
          )}
          {step === 'success' && (
            <p className="mt-2 text-sm text-gray-600">
              Password reset complete
            </p>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        {/* Step 1: Email Input */}
        {step === 'email' && (
          <form className="mt-8 space-y-6" onSubmit={handleRequestReset}>
            <p className="text-sm text-gray-600">
              Enter your email address and we'll send you a verification code.
            </p>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  setEmail(e.target.value);
                  setError('');
                }}
                className={inputClassName}
                placeholder="Enter your email"
              />
            </div>
            <button type="submit" disabled={loading} className={buttonClassName(loading)}>
              {loading ? 'Sending...' : 'Send Reset Code'}
            </button>
            <div className="text-center">
              <Link to="/login" className="text-sm font-medium text-blue-600 hover:text-blue-500">
                Back to Sign In
              </Link>
            </div>
          </form>
        )}

        {/* Step 2: OTP + New Password */}
        {step === 'otp' && (
          <form className="mt-8 space-y-6" onSubmit={handleConfirmReset}>
            <p className="text-sm text-gray-600">
              If <span className="font-medium">{email}</span> is registered, we sent a 6-digit code to that address. The code expires in 15 minutes.
            </p>
            <div className="space-y-4">
              <div>
                <label htmlFor="otp" className="block text-sm font-medium text-gray-700">
                  Verification Code
                </label>
                <input
                  id="otp"
                  name="otp"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  autoComplete="one-time-code"
                  required
                  value={otp}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    const val = e.target.value.replace(/\D/g, '');
                    setOtp(val);
                    setError('');
                  }}
                  className={`${inputClassName} text-center text-2xl tracking-widest font-mono`}
                  placeholder="000000"
                />
              </div>
              <div>
                <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700">
                  New Password
                </label>
                <input
                  id="newPassword"
                  name="newPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={newPassword}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    setNewPassword(e.target.value);
                    setError('');
                  }}
                  className={inputClassName}
                  placeholder="Enter new password"
                />
              </div>
              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
                  Confirm New Password
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    setConfirmPassword(e.target.value);
                    setError('');
                  }}
                  className={inputClassName}
                  placeholder="Confirm new password"
                />
              </div>
              <p className="text-xs text-gray-500">
                Min 8 characters with uppercase, lowercase, digit, and special character.
              </p>
            </div>
            <button type="submit" disabled={loading} className={buttonClassName(loading)}>
              {loading ? 'Resetting...' : 'Reset Password'}
            </button>
            <div className="flex justify-between text-sm">
              <button
                type="button"
                onClick={handleResend}
                disabled={loading}
                className="font-medium text-blue-600 hover:text-blue-500 disabled:text-gray-400"
              >
                Resend code
              </button>
              <Link to="/login" className="font-medium text-blue-600 hover:text-blue-500">
                Back to Sign In
              </Link>
            </div>
          </form>
        )}

        {/* Step 3: Success */}
        {step === 'success' && (
          <div className="mt-8 space-y-6 text-center">
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100">
              <svg className="h-8 w-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-gray-700">
              Your password has been reset successfully. You can now sign in with your new password.
            </p>
            <Link
              to="/login"
              className={`${buttonClassName(false)} inline-flex`}
            >
              Sign In
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
