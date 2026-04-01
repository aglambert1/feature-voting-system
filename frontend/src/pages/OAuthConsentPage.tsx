/**
 * OAuthConsentPage
 *
 * Handles the OAuth 2.1 consent flow for MCP clients.
 * When Claude Desktop (or another MCP client) connects, the MCP server
 * redirects the user's browser here to approve the connection.
 *
 * Flow:
 * 1. Receives txn_id from query params
 * 2. If not logged in, redirects to login with return URL
 * 3. Shows client name and requested permissions
 * 4. On approve, POSTs to MCP server with user's JWT
 * 5. Receives redirect URL, navigates to it (completes OAuth flow)
 */

import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const MCP_BASE_URL = import.meta.env.VITE_MCP_URL || 'http://localhost:8001';

interface ConsentDetails {
  txn_id: string;
  client_id: string;
  scopes: string[];
}

export default function OAuthConsentPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();

  const [details, setDetails] = useState<ConsentDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const txnId = searchParams.get('txn_id');
  const clientName = searchParams.get('client_name') || 'MCP Client';
  const state = searchParams.get('state') || '';

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      const returnUrl = window.location.pathname + window.location.search;
      navigate(`/login?redirect=${encodeURIComponent(returnUrl)}`);
    }
  }, [authLoading, user, navigate]);

  // Fetch consent details from MCP server
  useEffect(() => {
    if (!txnId || !user) return;

    const fetchDetails = async () => {
      try {
        const response = await fetch(`${MCP_BASE_URL}/oauth/consent?txn_id=${txnId}`);
        if (!response.ok) {
          const data = await response.json();
          setError(data.error || 'Failed to load consent details');
          return;
        }
        const data = await response.json();
        setDetails(data);
      } catch (err) {
        setError('Failed to connect to MCP server');
      } finally {
        setLoading(false);
      }
    };

    fetchDetails();
  }, [txnId, user]);

  const handleApprove = async () => {
    if (!txnId) return;
    setSubmitting(true);
    setError('');

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${MCP_BASE_URL}/oauth/consent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          txn_id: txnId,
          token,
          state,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.error || 'Failed to approve consent');
        return;
      }

      const data = await response.json();
      // Redirect to the client's callback URL (completes OAuth flow)
      window.location.href = data.redirect_url;
    } catch (err) {
      setError('Failed to connect to MCP server');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeny = () => {
    // Close the window or navigate away
    window.close();
    // Fallback if window.close() is blocked
    navigate('/');
  };

  if (authLoading || (user && loading)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!txnId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full">
          <h2 className="text-xl font-semibold text-red-600 mb-2">Invalid Request</h2>
          <p className="text-gray-600">No transaction ID provided.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Connect to Feature-IQ</h1>
          <p className="text-gray-500 mt-1">Authorize MCP access</p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
            {error}
          </div>
        )}

        {/* Client info */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-500 mb-1">Application</p>
          <p className="font-medium text-gray-900">{clientName}</p>

          {details && details.scopes.length > 0 && (
            <div className="mt-3">
              <p className="text-sm text-gray-500 mb-1">Requested access</p>
              <ul className="list-disc list-inside text-sm text-gray-700">
                {details.scopes.map((scope) => (
                  <li key={scope}>{scope}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* User info */}
        {user && (
          <p className="text-sm text-gray-500 mb-6 text-center">
            Signed in as <span className="font-medium text-gray-900">{user.email}</span>
          </p>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={handleDeny}
            disabled={submitting}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Deny
          </button>
          <button
            onClick={handleApprove}
            disabled={submitting || !!error}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? 'Connecting...' : 'Approve'}
          </button>
        </div>

        <p className="text-xs text-gray-400 text-center mt-4">
          This will allow the application to use Feature-IQ tools on your behalf.
        </p>
      </div>
    </div>
  );
}
