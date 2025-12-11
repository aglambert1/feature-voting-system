import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

export default function ProfilePage() {
  const { user, setUser } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');

  // Profile edit state
  const [profileData, setProfileData] = useState({
    email: '',
    full_name: '',
    username: ''
  });
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState('');
  const [profileSuccess, setProfileSuccess] = useState('');

  // Password change state
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');

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

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setProfileLoading(true);
    setProfileError('');
    setProfileSuccess('');

    try {
      // Note: This endpoint needs to be created in the backend
      const response = await api.patch('/auth/me', {
        email: profileData.email,
        full_name: profileData.full_name
      });

      setUser(response.data);
      setProfileSuccess('Profile updated successfully!');
    } catch (err) {
      setProfileError(err.response?.data?.detail || 'Failed to update profile');
    } finally {
      setProfileLoading(false);
    }
  };

  const handlePasswordSubmit = async (e) => {
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

    try {
      await api.post('/auth/password/change', {
        current_password: passwordData.current_password,
        new_password: passwordData.new_password
      });

      setPasswordSuccess('Password changed successfully!');
      setPasswordData({
        current_password: '',
        new_password: '',
        confirm_password: ''
      });
    } catch (err) {
      setPasswordError(err.response?.data?.detail || 'Failed to change password');
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>
            <a
              href="/ideas"
              className="text-blue-600 hover:text-blue-800 transition-colors"
            >
              ← Back to Ideas
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
                onClick={() => setActiveTab('profile')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'profile'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
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
                      onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
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
                      onChange={(e) => setProfileData({ ...profileData, full_name: e.target.value })}
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
                      onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
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
                      onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                      required
                      minLength={8}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <p className="mt-1 text-sm text-gray-500">Minimum 8 characters</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Confirm New Password *
                    </label>
                    <input
                      type="password"
                      value={passwordData.confirm_password}
                      onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
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
          </div>
        </div>
      </main>
    </div>
  );
}
