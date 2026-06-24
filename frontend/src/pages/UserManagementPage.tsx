import { useState, useEffect, ChangeEvent, FormEvent } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Navigation from '../components/Navigation';
import api from '../services/api';
import { getUserProducts, setUserProducts, adminResetPassword, unlockUser, getUserLoginHistory } from '../services/api';
import type { User, UserProduct, ProductListItem, LoginEvent } from '../types';
import { AxiosError } from 'axios';
import type { ApiError } from '../types';

interface CreateFormData {
  username: string;
  email: string;
  full_name: string;
  password: string;
  role: string;
  product_ids: number[];
}

export default function UserManagementPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [allProducts, setAllProducts] = useState<ProductListItem[]>([]);
  const [userProductsMap, setUserProductsMap] = useState<Record<number, UserProduct[]>>({});
  const [editingProductsUserId, setEditingProductsUserId] = useState<number | null>(null);
  const [editingProductIds, setEditingProductIds] = useState<number[]>([]);
  const [editingPermissionLevels, setEditingPermissionLevels] = useState<Record<number, string>>({});
  const [adminOwnedProductIds, setAdminOwnedProductIds] = useState<Set<number>>(new Set());
  const [createFormData, setCreateFormData] = useState<CreateFormData>({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'voter',
    product_ids: [],
  });

  // Password reset state
  const [resetPasswordResult, setResetPasswordResult] = useState<{username: string; temporary_password: string} | null>(null);
  const [resetPasswordCopied, setResetPasswordCopied] = useState(false);

  // Login history modal state
  const [loginHistoryUserId, setLoginHistoryUserId] = useState<number | null>(null);
  const [loginHistory, setLoginHistory] = useState<LoginEvent[]>([]);
  const [loginHistoryLoading, setLoginHistoryLoading] = useState(false);

  // Fetch users and products
  useEffect(() => {
    fetchUsers();
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      const response = await api.get('/ideas/products');
      setAllProducts(Array.isArray(response.data) ? response.data : []);
    } catch {
      // Products may not be accessible
    }
    if (user?.id) {
      try {
        const myPerms = await getUserProducts(user.id);
        setAdminOwnedProductIds(new Set(
          myPerms.filter(p => p.permission_level === 'owner').map(p => p.product_id)
        ));
      } catch {
        setAdminOwnedProductIds(new Set());
      }
    }
  };

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const response = await api.get<User[]>('/auth/users');
      setUsers(response.data);
      setError('');

      // Fetch product assignments for each user
      const productsMap: Record<number, UserProduct[]> = {};
      for (const u of response.data) {
        try {
          const products = await getUserProducts(u.id);
          productsMap[u.id] = products;
        } catch {
          productsMap[u.id] = [];
        }
      }
      setUserProductsMap(productsMap);
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setError(error.response?.data?.detail || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleDeactivateUser = async (userId: number, username: string) => {
    if (!confirm(`Are you sure you want to deactivate ${username}?`)) {
      return;
    }

    try {
      await api.patch(`/auth/users/${userId}/deactivate`);
      setSuccessMessage(`User ${username} deactivated successfully`);
      fetchUsers(); // Refresh list
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setError(error.response?.data?.detail || 'Failed to deactivate user');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleActivateUser = async (userId: number, username: string) => {
    try {
      await api.patch(`/auth/users/${userId}/activate`);
      setSuccessMessage(`User ${username} activated successfully`);
      fetchUsers(); // Refresh list
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setError(error.response?.data?.detail || 'Failed to activate user');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleChangeRole = async (userId: number, username: string, newRole: string) => {
    if (!confirm(`Change ${username}'s role to ${newRole}?`)) {
      return;
    }

    try {
      await api.patch(`/auth/users/${userId}/role`, { role: newRole });
      setSuccessMessage(`User ${username}'s role changed to ${newRole}`);
      fetchUsers(); // Refresh list
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setError(error.response?.data?.detail || 'Failed to change role');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleCreateUser = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    try {
      await api.post('/auth/register', {
        username: createFormData.username,
        email: createFormData.email,
        full_name: createFormData.full_name,
        password: createFormData.password,
        role: createFormData.role,
        product_ids: createFormData.product_ids,
      });
      setSuccessMessage(`User ${createFormData.username} created successfully`);
      setShowCreateModal(false);
      setCreateFormData({
        username: '',
        email: '',
        full_name: '',
        password: '',
        role: 'voter',
        product_ids: [],
      });
      fetchUsers(); // Refresh list
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setError(error.response?.data?.detail || 'Failed to create user');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleSaveProducts = async () => {
    if (editingProductsUserId === null) return;
    const targetUser = users.find(u => u.id === editingProductsUserId);
    if (!targetUser) return;

    try {
      const assignments = editingProductIds.map(pid => ({
        product_id: pid,
        permission_level: editingPermissionLevels[pid] || 'view',
      }));
      await setUserProducts(editingProductsUserId, assignments);
      setSuccessMessage(`Product assignments updated for ${targetUser.username}`);
      setEditingProductsUserId(null);
      setEditingProductIds([]);
      setEditingPermissionLevels({});
      fetchUsers();
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setError(error.response?.data?.detail || 'Failed to update product assignments');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleResetPassword = async (userId: number, username: string) => {
    if (!confirm(`Reset password for ${username}? This will invalidate all their active sessions.`)) {
      return;
    }

    try {
      const result = await adminResetPassword(userId);
      setResetPasswordResult({ username: result.username, temporary_password: result.temporary_password });
      setResetPasswordCopied(false);
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setError(error.response?.data?.detail || 'Failed to reset password');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleUnlockUser = async (userId: number, username: string) => {
    try {
      await unlockUser(userId);
      setSuccessMessage(`Account ${username} unlocked`);
      fetchUsers();
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      const error = err as AxiosError<ApiError>;
      setError(error.response?.data?.detail || 'Failed to unlock user');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleShowLoginHistory = async (userId: number) => {
    setLoginHistoryUserId(userId);
    setLoginHistoryLoading(true);
    try {
      const events = await getUserLoginHistory(userId);
      setLoginHistory(events);
    } catch {
      setLoginHistory([]);
    } finally {
      setLoginHistoryLoading(false);
    }
  };

  const handleEditProducts = (userId: number) => {
    const currentProducts = userProductsMap[userId] || [];
    setEditingProductsUserId(userId);
    setEditingProductIds(currentProducts.map(p => p.product_id));
    const levels: Record<number, string> = {};
    currentProducts.forEach(p => { levels[p.product_id] = p.permission_level; });
    setEditingPermissionLevels(levels);
  };

  const toggleProductId = (productId: number, list: number[], setter: (ids: number[]) => void) => {
    if (list.includes(productId)) {
      setter(list.filter(id => id !== productId));
    } else {
      setter([...list, productId]);
    }
  };

  const getRoleBadgeColor = (role: string): string => {
    switch (role) {
      case 'admin':
        return 'bg-red-100 text-red-800';
      case 'voter':
        return 'bg-blue-100 text-blue-800';
      case 'product_owner':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatRelativeTime = (dateStr: string | null): string => {
    if (!dateStr) return 'Never';
    const diff = Date.now() - new Date(dateStr).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return `${Math.floor(days / 30)}mo ago`;
  };

  const isUserLocked = (u: User): boolean => {
    if (!u.locked_until) return false;
    return new Date(u.locked_until) > new Date();
  };

  const isDormant = (u: User): boolean => {
    if (!u.last_login_at) return true;
    const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
    return new Date(u.last_login_at).getTime() < thirtyDaysAgo;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">User Management</h1>
        {/* Messages */}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {successMessage && (
          <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
            {successMessage}
          </div>
        )}

        {/* Users Table */}
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">All Users</h2>
              <p className="text-sm text-gray-600 mt-1">
                Manage user accounts, roles, and access
              </p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center"
            >
              <svg
                className="w-5 h-5 mr-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Add User
            </button>
          </div>

          {loading ? (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500">No users found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Email
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Role
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Products
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Last Login
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-semibold">
                            {u.username?.charAt(0).toUpperCase()}
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900">
                              {u.username}
                              {u.id === user?.id && (
                                <span className="ml-2 text-xs text-gray-500">(You)</span>
                              )}
                            </div>
                            <div className="text-sm text-gray-500">{u.full_name}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">{u.email}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <select
                          value={u.role}
                          onChange={(e: ChangeEvent<HTMLSelectElement>) => handleChangeRole(u.id, u.username, e.target.value)}
                          disabled={u.id === user?.id}
                          className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getRoleBadgeColor(
                            u.role
                          )} ${u.id === user?.id ? 'cursor-not-allowed' : 'cursor-pointer'}`}
                        >
                          <option value="admin">Admin</option>
                          <option value="voter">Voter</option>
                          <option value="product_owner">Product Owner</option>
                        </select>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1">
                          {(userProductsMap[u.id] || []).length === 0 ? (
                            <span className="text-xs text-gray-400">None</span>
                          ) : (
                            (userProductsMap[u.id] || []).map(p => (
                              <span
                                key={p.product_id}
                                className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800"
                              >
                                {p.product_name}
                                <span className="ml-1 text-purple-600">({p.permission_level})</span>
                              </span>
                            ))
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={() => handleShowLoginHistory(u.id)}
                          className={`text-sm hover:underline ${u.last_login_at ? 'text-blue-600' : 'text-gray-400'}`}
                          title={u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Never logged in'}
                        >
                          {formatRelativeTime(u.last_login_at)}
                        </button>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {isUserLocked(u) ? (
                          <span className="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-amber-100 text-amber-800">
                            Locked
                          </span>
                        ) : (
                          <span
                            className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                              u.is_active
                                ? 'bg-green-100 text-green-800'
                                : 'bg-red-100 text-red-800'
                            }`}
                          >
                            {u.is_active ? 'Active' : 'Inactive'}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        {u.id === user?.id ? (
                          <span className="text-gray-400">Cannot modify yourself</span>
                        ) : (
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleEditProducts(u.id)}
                              className="text-purple-600 hover:text-purple-900 font-medium"
                            >
                              Products
                            </button>
                            <button
                              onClick={() => handleResetPassword(u.id, u.username)}
                              className="text-amber-600 hover:text-amber-900 font-medium"
                            >
                              Reset PW
                            </button>
                            {isUserLocked(u) && (
                              <button
                                onClick={() => handleUnlockUser(u.id, u.username)}
                                className="text-blue-600 hover:text-blue-900 font-medium"
                              >
                                Unlock
                              </button>
                            )}
                            {u.is_active ? (
                              <button
                                onClick={() => handleDeactivateUser(u.id, u.username)}
                                className="text-red-600 hover:text-red-900 font-medium"
                              >
                                Deactivate
                              </button>
                            ) : (
                              <button
                                onClick={() => handleActivateUser(u.id, u.username)}
                                className="text-green-600 hover:text-green-900 font-medium"
                              >
                                Activate
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Statistics */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-sm font-medium text-gray-500">Total Users</h3>
            <p className="mt-2 text-3xl font-bold text-gray-900">{users.length}</p>
          </div>
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-sm font-medium text-gray-500">Active Users</h3>
            <p className="mt-2 text-3xl font-bold text-green-600">
              {users.filter((u) => u.is_active).length}
            </p>
          </div>
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-sm font-medium text-gray-500">Dormant (30d+)</h3>
            <p className="mt-2 text-3xl font-bold text-amber-600">
              {users.filter((u) => u.is_active && isDormant(u)).length}
            </p>
          </div>
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-sm font-medium text-gray-500">Admins</h3>
            <p className="mt-2 text-3xl font-bold text-red-600">
              {users.filter((u) => u.role === 'admin').length}
            </p>
          </div>
        </div>
      </main>

      {/* Login History Modal */}
      {loginHistoryUserId !== null && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
          <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full mx-4">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                Login History — {users.find(u => u.id === loginHistoryUserId)?.username}
              </h3>
            </div>

            <div className="px-6 py-4 max-h-80 overflow-y-auto">
              {loginHistoryLoading ? (
                <p className="text-sm text-gray-500">Loading...</p>
              ) : loginHistory.length === 0 ? (
                <p className="text-sm text-gray-500">No login events recorded.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Time</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">IP</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Browser</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {loginHistory.map(e => (
                      <tr key={e.id}>
                        <td className="px-3 py-2 text-gray-900 whitespace-nowrap">
                          {new Date(e.logged_in_at).toLocaleString()}
                        </td>
                        <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                          {e.ip_address || '—'}
                        </td>
                        <td className="px-3 py-2 text-gray-600 truncate max-w-[200px]" title={e.user_agent || ''}>
                          {e.user_agent ? e.user_agent.split(' ').slice(0, 3).join(' ') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <button
                onClick={() => { setLoginHistoryUserId(null); setLoginHistory([]); }}
                className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Products Modal */}
      {editingProductsUserId !== null && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
          <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                Edit Product Access — {users.find(u => u.id === editingProductsUserId)?.username}
              </h3>
            </div>

            <div className="px-6 py-4">
              {(() => {
                const ownedProducts = allProducts.filter(p => adminOwnedProductIds.has(p.id));
                return ownedProducts.length === 0 ? (
                  <p className="text-sm text-gray-500">You don't have owner access to any products.</p>
                ) : (
                  <>
                    <div className="border border-gray-300 rounded-lg max-h-60 overflow-y-auto">
                      {ownedProducts.map(product => (
                        <div
                          key={product.id}
                          className="flex items-center justify-between px-3 py-2 hover:bg-gray-50"
                        >
                          <label className="flex items-center cursor-pointer flex-1">
                            <input
                              type="checkbox"
                              checked={editingProductIds.includes(product.id)}
                              onChange={() => {
                                toggleProductId(product.id, editingProductIds, setEditingProductIds);
                                if (!editingProductIds.includes(product.id)) {
                                  setEditingPermissionLevels(prev => ({ ...prev, [product.id]: prev[product.id] || 'view' }));
                                }
                              }}
                              className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                            />
                            <span className="ml-2 text-sm text-gray-700">{product.product_name}</span>
                          </label>
                          {editingProductIds.includes(product.id) && (
                            <select
                              value={editingPermissionLevels[product.id] || 'view'}
                              onChange={e => setEditingPermissionLevels(prev => ({ ...prev, [product.id]: e.target.value }))}
                              className="ml-2 px-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                            >
                              <option value="view">View</option>
                              <option value="edit">Edit</option>
                              <option value="owner">Owner</option>
                            </select>
                          )}
                        </div>
                      ))}
                    </div>
                    <p className="mt-2 text-xs text-gray-500">
                      Only products where you have owner access are shown.
                    </p>
                  </>
                );
              })()}
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
              <button
                type="button"
                onClick={() => {
                  setEditingProductsUserId(null);
                  setEditingProductIds([]);
                }}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveProducts}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Temporary Password Modal */}
      {resetPasswordResult && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
          <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                Password Reset — {resetPasswordResult.username}
              </h3>
            </div>

            <div className="px-6 py-4">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                <p className="text-sm font-medium text-amber-800 mb-1">
                  Share this temporary password with the user securely.
                </p>
                <p className="text-xs text-amber-700">
                  It will not be shown again. The user will be required to change it on next login.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <code className="flex-1 bg-gray-100 border border-gray-300 rounded px-3 py-2 text-sm font-mono text-gray-800 break-all select-all">
                  {resetPasswordResult.temporary_password}
                </code>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(resetPasswordResult.temporary_password);
                    setResetPasswordCopied(true);
                    setTimeout(() => setResetPasswordCopied(false), 2000);
                  }}
                  className="px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 whitespace-nowrap"
                >
                  {resetPasswordCopied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <button
                onClick={() => setResetPasswordResult(null)}
                className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
          <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Create New User</h3>
            </div>

            <form onSubmit={handleCreateUser} className="px-6 py-4">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Username *
                  </label>
                  <input
                    type="text"
                    required
                    value={createFormData.username}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setCreateFormData({...createFormData, username: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="johndoe"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email *
                  </label>
                  <input
                    type="email"
                    required
                    value={createFormData.email}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setCreateFormData({...createFormData, email: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="john@example.com"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={createFormData.full_name}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setCreateFormData({...createFormData, full_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="John Doe"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Password *
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={createFormData.password}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setCreateFormData({...createFormData, password: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Min 8 chars, upper/lower/digit/special"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role *
                  </label>
                  <select
                    value={createFormData.role}
                    onChange={(e: ChangeEvent<HTMLSelectElement>) => setCreateFormData({...createFormData, role: e.target.value, product_ids: []})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="product_owner">Product Owner</option>
                    <option value="voter">Voter</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>

                {(() => {
                  const ownedProducts = allProducts.filter(p => adminOwnedProductIds.has(p.id));
                  return ownedProducts.length > 0 ? (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Product Access
                      </label>
                      <div className="border border-gray-300 rounded-lg max-h-40 overflow-y-auto">
                        {ownedProducts.map(product => (
                          <label
                            key={product.id}
                            className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={createFormData.product_ids.includes(product.id)}
                              onChange={() => toggleProductId(product.id, createFormData.product_ids, (ids) => setCreateFormData({...createFormData, product_ids: ids}))}
                              className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                            />
                            <span className="ml-2 text-sm text-gray-700">{product.product_name}</span>
                          </label>
                        ))}
                      </div>
                      <p className="mt-1 text-xs text-gray-500">
                        Only products where you have owner access are shown.
                      </p>
                    </div>
                  ) : null;
                })()}
              </div>

              <div className="mt-6 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    setCreateFormData({
                      username: '',
                      email: '',
                      full_name: '',
                      password: '',
                      role: 'voter',
                      product_ids: [],
                    });
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                >
                  Create User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
