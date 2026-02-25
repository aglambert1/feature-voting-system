/**
 * JoinPage
 *
 * Landing page for invite code redemption.
 * Route: /join/:code
 *
 * - If authenticated: redeems the code automatically and redirects to /ideas
 * - If not authenticated: shows product info with options to log in or register
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { redeemInviteCode, getInviteInfo } from '../services/api';

const JoinPage = () => {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();

  const [status, setStatus] = useState<'loading' | 'invite_info' | 'redeeming' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState<string>('');
  const [productName, setProductName] = useState<string>('');

  // Validate invite code on mount (for both authed and unauthed users)
  useEffect(() => {
    if (authLoading) return;
    if (!code) {
      setStatus('error');
      setMessage('No invite code provided');
      return;
    }

    const processInvite = async () => {
      try {
        // Always validate the code first
        const info = await getInviteInfo(code);

        if (!info.valid) {
          setStatus('error');
          setMessage(info.message || 'This invite link is invalid or has expired.');
          return;
        }

        if (info.product_name) {
          setProductName(info.product_name);
        }

        if (!user) {
          // Not logged in — show landing page with login/register options
          setStatus('invite_info');
          return;
        }

        // Logged in — redeem the code
        setStatus('redeeming');
        const result = await redeemInviteCode(code);
        setStatus('success');
        setMessage(result.message);
        setProductName(result.product_name);

        // Refresh product list
        window.dispatchEvent(new Event('user-logged-in'));

        // Redirect to ideas after brief delay
        setTimeout(() => {
          navigate('/ideas', { replace: true });
        }, 2000);
      } catch (err: unknown) {
        setStatus('error');
        const apiError = err as { message?: string };
        setMessage(apiError.message || 'Failed to process invite code');
      }
    };

    processInvite();
  }, [code, user, authLoading, navigate]);

  if (authLoading || status === 'loading' || status === 'redeeming') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
          <p className="text-gray-500">
            {productName ? `Joining ${productName}...` : 'Processing invite...'}
          </p>
        </div>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full text-center space-y-6">
          <div className="bg-green-50 border border-green-200 rounded-md p-6">
            <h2 className="text-xl font-bold text-green-800">{message}</h2>
            <p className="mt-2 text-sm text-green-600">Redirecting to ideas...</p>
          </div>
        </div>
      </div>
    );
  }

  // Unauthenticated user with valid invite — show landing page
  if (status === 'invite_info') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full space-y-6">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900">You've Been Invited</h2>
            {productName && (
              <p className="mt-2 text-gray-600">
                You're invited to vote on <span className="font-semibold">{productName}</span>
              </p>
            )}
          </div>

          <div className="bg-white rounded-lg shadow p-6 space-y-4">
            <div>
              <p className="text-sm font-medium text-gray-700 mb-3">
                Already have an account?
              </p>
              <Link
                to={`/login?redirect=/join/${code}`}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
              >
                Log In to Add Product
              </Link>
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">or</span>
              </div>
            </div>

            <div>
              <p className="text-sm font-medium text-gray-700 mb-3">
                New to Feature-IQ?
              </p>
              <Link
                to={`/register?invite=${code}`}
                className="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Create an Account
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full text-center space-y-6">
        <h2 className="text-2xl font-bold text-gray-900">Invite Error</h2>
        <p className="text-red-600">{message}</p>
        <div className="space-x-4">
          <Link
            to="/login"
            className="inline-block px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
          >
            Go to Login
          </Link>
        </div>
      </div>
    </div>
  );
};

export default JoinPage;
