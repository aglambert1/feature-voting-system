import { useState, useEffect, useCallback, ChangeEvent, FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api, { getCurrentUser } from '../services/api';
import { AxiosError } from 'axios';
import type { ApiError } from '../types';
import { UserRole } from '../types';

type ActiveTab = 'profile' | 'password' | 'api-keys';

interface ProfileFormData {
  email: string;
  full_name: string;
  username: string;
}

interface PasswordFormData {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

interface APIKey {
  id: number;
  key_prefix: string;
  name: string;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  is_revoked: boolean;
}

interface APIKeyCreateResponse extends APIKey {
  api_key: string;
}

export default function ProfilePage() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const initialForce = user?.must_change_password || searchParams.get('force_password_change') === '1';
  const [forcePasswordChange, setForcePasswordChange] = useState(initialForce);
  const [activeTab, setActiveTab] = useState<ActiveTab>(initialForce ? 'password' : 'profile');

  const isPO = user?.role === UserRole.PRODUCT_OWNER;

  // Profile edit state
  const [profileData, setProfileData] = useState<ProfileFormData>({
    email: '',
    full_name: '',
    username: ''
  });
  const [profileLoading, setProfileLoading] = useState<boolean>(false);
  const [profileError, setProfileError] = useState<string>('');
  const [profileSuccess, setProfileSuccess] = useState<string>('');

  // Password change state
  const [passwordData, setPasswordData] = useState<PasswordFormData>({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [passwordLoading, setPasswordLoading] = useState<boolean>(false);
  const [passwordError, setPasswordError] = useState<string>('');
  const [passwordSuccess, setPasswordSuccess] = useState<string>('');

  // API keys state
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState<boolean>(false);
  const [apiKeysError, setApiKeysError] = useState<string>('');
  const [newKeyName, setNewKeyName] = useState<string>('');
  const [creatingKey, setCreatingKey] = useState<boolean>(false);
  const [showNewKeyForm, setShowNewKeyForm] = useState<boolean>(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [revokingId, setRevokingId] = useState<number | null>(null);

  // Initialize profile data
  useEffect(() => {
    if (user) {
      setProfileData({
        email: user.email || '',
        full_name: user.full_name || '',
        username: user.username || ''
      });
    }
  }, [user]);

  const fetchApiKeys = useCallback(async () => {
    setApiKeysLoading(true);
    setApiKeysError('');
    try {
      const response = await api.get<APIKey[]>('/api-keys');
      setApiKeys(response.data);
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setApiKeysError(error.response?.data?.detail || 'Failed to load API keys');
    } finally {
      setApiKeysLoading(false);
    }
  }, []);

  // Fetch API keys when tab is selected
  useEffect(() => {
    if (activeTab === 'api-keys' && isPO) {
      fetchApiKeys();
    }
  }, [activeTab, isPO, fetchApiKeys]);

  const handleProfileSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setProfileLoading(true);
    setProfileError('');
    setProfileSuccess('');

    try {
      const response = await api.patch('/auth/me', {
        email: profileData.email,
        full_name: profileData.full_name
      });

      setUser(response.data);
      setProfileSuccess('Profile updated successfully!');
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setProfileError(error.response?.data?.detail || 'Failed to update profile');
    } finally {
      setProfileLoading(false);
    }
  };

  const handlePasswordSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setPasswordLoading(true);
    setPasswordError('');
    setPasswordSuccess('');

    // Validation
    if (passwordData.new_password !== passwordData.confirm_password) {
      setPasswordError('New passwords do not match');
      setPasswordLoading(false);
      return;
    }

    if (passwordData.new_password.length < 8) {
      setPasswordError('Password must be at least 8 characters long');
      setPasswordLoading(false);
      return;
    }

    const pw = passwordData.new_password;
    const missing = [];
    if (!/[A-Z]/.test(pw)) missing.push('one uppercase letter');
    if (!/[a-z]/.test(pw)) missing.push('one lowercase letter');
    if (!/\d/.test(pw)) missing.push('one digit');
    if (!/[^A-Za-z0-9]/.test(pw)) missing.push('one special character');
    if (missing.length > 0) {
      setPasswordError(`Password must contain at least: ${missing.join(', ')}`);
      setPasswordLoading(false);
      return;
    }

    try {
      await api.post('/auth/password/change', {
        current_password: passwordData.current_password,
        new_password: passwordData.new_password
      });

      setPasswordData({
        current_password: '',
        new_password: '',
        confirm_password: ''
      });

      if (forcePasswordChange) {
        setPasswordSuccess('Password changed successfully. Redirecting to login...');
        setForcePasswordChange(false);
        setTimeout(() => {
          logout();
          navigate('/login', { replace: true });
        }, 2000);
      } else {
        setPasswordSuccess('Password changed successfully!');
        const updatedUser = await getCurrentUser();
        setUser(updatedUser);
      }
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setPasswordError(error.response?.data?.detail || 'Failed to change password');
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleCreateKey = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setCreatingKey(true);
    setApiKeysError('');

    try {
      const response = await api.post<APIKeyCreateResponse>('/api-keys', { name: newKeyName });
      setNewlyCreatedKey(response.data.api_key);
      setNewKeyName('');
      setShowNewKeyForm(false);
      fetchApiKeys();
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setApiKeysError(error.response?.data?.detail || 'Failed to create API key');
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevokeKey = async (keyId: number) => {
    setRevokingId(keyId);
    try {
      await api.delete(`/api-keys/${keyId}`);
      fetchApiKeys();
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setApiKeysError(error.response?.data?.detail || 'Failed to revoke API key');
    } finally {
      setRevokingId(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const isExpired = (dateStr: string) => new Date(dateStr) < new Date();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>
            {!forcePasswordChange && (
              <button
                onClick={() => navigate(-1)}
                className="text-blue-600 hover:text-blue-800 transition-colors"
              >
                &larr; Back
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Forced password change banner */}
        {forcePasswordChange && (
          <div className="bg-amber-50 border border-amber-300 text-amber-800 px-4 py-3 rounded-lg mb-6 font-medium">
            Your password must be changed before you can continue. Enter your temporary password as the current password, then choose a new one.
          </div>
        )}

        {/* User Info Card */}
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <div className="flex items-center">
            <div className="h-16 w-16 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 text-2xl font-bold">
              {user?.username?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="ml-4">
              <h2 className="text-xl font-semibold text-gray-900">{user?.username}</h2>
              <p className="text-gray-600">{user?.email}</p>
              <p className="text-sm text-gray-500 mt-1">
                Role: <span className="font-medium capitalize">{user?.role}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              <button
                onClick={() => !forcePasswordChange && setActiveTab('profile')}
                disabled={forcePasswordChange}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'profile'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } ${forcePasswordChange ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                Edit Profile
              </button>
              <button
                onClick={() => setActiveTab('password')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'password'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Change Password
              </button>
              {isPO && (
                <button
                  onClick={() => !forcePasswordChange && setActiveTab('api-keys')}
                  disabled={forcePasswordChange}
                  className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === 'api-keys'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  } ${forcePasswordChange ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  API Keys
                </button>
              )}
            </nav>
          </div>

          <div className="p-6">
            {/* Edit Profile Tab */}
            {activeTab === 'profile' && (
              <form onSubmit={handleProfileSubmit}>
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Username
                    </label>
                    <input
                      type="text"
                      value={profileData.username}
                      disabled
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-100 cursor-not-allowed"
                    />
                    <p className="mt-1 text-sm text-gray-500">Username cannot be changed</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Email Address *
                    </label>
                    <input
                      type="email"
                      value={profileData.email}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setProfileData({ ...profileData, email: e.target.value })}
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Full Name
                    </label>
                    <input
                      type="text"
                      value={profileData.full_name}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setProfileData({ ...profileData, full_name: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  {profileError && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                      {profileError}
                    </div>
                  )}

                  {profileSuccess && (
                    <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
                      {profileSuccess}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={profileLoading}
                    className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-300 disabled:bg-blue-300 disabled:cursor-not-allowed transition-colors font-medium"
                  >
                    {profileLoading ? 'Updating...' : 'Update Profile'}
                  </button>
                </div>
              </form>
            )}

            {/* Change Password Tab */}
            {activeTab === 'password' && (
              <form onSubmit={handlePasswordSubmit}>
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Current Password *
                    </label>
                    <input
                      type="password"
                      value={passwordData.current_password}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setPasswordData({ ...passwordData, current_password: e.target.value })}
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      New Password *
                    </label>
                    <input
                      type="password"
                      value={passwordData.new_password}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                      required
                      minLength={8}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <p className="mt-1 text-sm text-gray-500">Min 8 characters with uppercase, lowercase, digit, and special character</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Confirm New Password *
                    </label>
                    <input
                      type="password"
                      value={passwordData.confirm_password}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                      required
                      minLength={8}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  {passwordError && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                      {passwordError}
                    </div>
                  )}

                  {passwordSuccess && (
                    <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
                      {passwordSuccess}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={passwordLoading}
                    className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-300 disabled:bg-blue-300 disabled:cursor-not-allowed transition-colors font-medium"
                  >
                    {passwordLoading ? 'Changing Password...' : 'Change Password'}
                  </button>
                </div>
              </form>
            )}

            {/* API Keys Tab */}
            {activeTab === 'api-keys' && isPO && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-1">MCP API Keys</h3>
                  <p className="text-sm text-gray-600">
                    Generate API keys to connect Claude Desktop, Cursor, or other MCP clients to Feature-IQ.
                  </p>
                </div>

                {/* Newly created key banner */}
                {newlyCreatedKey && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <p className="text-sm font-medium text-green-800 mb-2">
                      API key created. Copy it now — it won't be shown again.
                    </p>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 bg-white border border-green-300 rounded px-3 py-2 text-sm font-mono text-gray-800 break-all">
                        {newlyCreatedKey}
                      </code>
                      <button
                        onClick={() => copyToClipboard(newlyCreatedKey)}
                        className="px-3 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 whitespace-nowrap"
                      >
                        {copied ? 'Copied!' : 'Copy'}
                      </button>
                    </div>
                    <button
                      onClick={() => setNewlyCreatedKey(null)}
                      className="mt-2 text-sm text-green-700 hover:text-green-900"
                    >
                      Dismiss
                    </button>
                  </div>
                )}

                {apiKeysError && (
                  <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                    {apiKeysError}
                  </div>
                )}

                {/* Create new key */}
                {showNewKeyForm ? (
                  <form onSubmit={handleCreateKey} className="flex items-end gap-3">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Key Name</label>
                      <input
                        type="text"
                        value={newKeyName}
                        onChange={(e) => setNewKeyName(e.target.value)}
                        placeholder="e.g., Claude Desktop"
                        required
                        maxLength={100}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={creatingKey || !newKeyName.trim()}
                      className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed"
                    >
                      {creatingKey ? 'Creating...' : 'Create'}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowNewKeyForm(false); setNewKeyName(''); }}
                      className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <button
                    onClick={() => setShowNewKeyForm(true)}
                    className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    Generate New Key
                  </button>
                )}

                {/* Keys list */}
                {apiKeysLoading ? (
                  <p className="text-sm text-gray-500">Loading keys...</p>
                ) : apiKeys.length === 0 ? (
                  <p className="text-sm text-gray-500">No API keys yet.</p>
                ) : (
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                          <th className="text-left px-4 py-3 font-medium text-gray-600">Key</th>
                          <th className="text-left px-4 py-3 font-medium text-gray-600">Created</th>
                          <th className="text-left px-4 py-3 font-medium text-gray-600">Expires</th>
                          <th className="text-left px-4 py-3 font-medium text-gray-600">Last Used</th>
                          <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                          <th className="px-4 py-3"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {apiKeys.map((key) => (
                          <tr key={key.id} className={key.is_revoked ? 'bg-gray-50 opacity-60' : ''}>
                            <td className="px-4 py-3 font-medium text-gray-900">{key.name}</td>
                            <td className="px-4 py-3 font-mono text-gray-600">{key.key_prefix}...</td>
                            <td className="px-4 py-3 text-gray-600">{formatDate(key.created_at)}</td>
                            <td className={`px-4 py-3 ${isExpired(key.expires_at) ? 'text-red-600' : 'text-gray-600'}`}>
                              {formatDate(key.expires_at)}
                              {isExpired(key.expires_at) && <span className="ml-1 text-xs">(expired)</span>}
                            </td>
                            <td className="px-4 py-3 text-gray-600">
                              {key.last_used_at ? formatDate(key.last_used_at) : 'Never'}
                            </td>
                            <td className="px-4 py-3">
                              {key.is_revoked ? (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">Revoked</span>
                              ) : isExpired(key.expires_at) ? (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700">Expired</span>
                              ) : (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">Active</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-right">
                              {!key.is_revoked && (
                                <button
                                  onClick={() => handleRevokeKey(key.id)}
                                  disabled={revokingId === key.id}
                                  className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
                                >
                                  {revokingId === key.id ? 'Revoking...' : 'Revoke'}
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Setup instructions */}
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <h4 className="text-sm font-medium text-gray-800 mb-2">Claude Desktop Setup</h4>
                  <p className="text-xs text-gray-600 mb-2">
                    Add this to your Claude Desktop configuration file:
                  </p>
                  <pre className="bg-gray-900 text-gray-100 rounded p-3 text-xs overflow-x-auto">
{`{
  "mcpServers": {
    "feature-iq": {
      "url": "https://feature-iq-mcp.onrender.com/mcp",
      "headers": {
        "Authorization": "Bearer fiq_your_key_here"
      }
    }
  }
}`}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
