/**
 * IdeaLifecycleSettingsPage
 *
 * Admin-only page for configuring idea lifecycle statuses.
 * Lifecycle statuses represent post-acceptance stages (e.g., "On Roadmap", "Delivered").
 * Max 3 statuses allowed.
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Navigation from '../components/Navigation';
import {
  getLifecycleStatuses,
  createLifecycleStatus,
  updateLifecycleStatus,
  deleteLifecycleStatus,
} from '../services/api';
import type { IdeaLifecycleStatus } from '../types';

const MAX_STATUSES = 3;

const IdeaLifecycleSettingsPage = () => {
  const [statuses, setStatuses] = useState<IdeaLifecycleStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  // New status form
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState('#8B5CF6');

  // Editing state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('');

  // Delete confirmation
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const fetchStatuses = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getLifecycleStatuses();
      setStatuses(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load lifecycle statuses');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatuses();
  }, [fetchStatuses]);

  const handleAdd = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    setError('');
    try {
      const created = await createLifecycleStatus({ name: newName.trim(), color: newColor });
      setStatuses(prev => [...prev, created]);
      setNewName('');
      setNewColor('#8B5CF6');
      setShowAddForm(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create status');
    } finally {
      setSaving(false);
    }
  };

  const handleStartEdit = (status: IdeaLifecycleStatus) => {
    setEditingId(status.id);
    setEditName(status.name);
    setEditColor(status.color);
  };

  const handleSaveEdit = async () => {
    if (!editingId || !editName.trim()) return;
    setSaving(true);
    setError('');
    try {
      const updated = await updateLifecycleStatus(editingId, {
        name: editName.trim(),
        color: editColor,
      });
      setStatuses(prev => prev.map(s => s.id === editingId ? updated : s));
      setEditingId(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update status');
    } finally {
      setSaving(false);
    }
  };

  const handleMove = async (id: number, direction: 'up' | 'down') => {
    const idx = statuses.findIndex(s => s.id === id);
    if (idx === -1) return;
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= statuses.length) return;

    const current = statuses[idx]!;
    const swap = statuses[swapIdx]!;

    setSaving(true);
    setError('');
    try {
      await Promise.all([
        updateLifecycleStatus(current.id, { position: swap.position }),
        updateLifecycleStatus(swap.id, { position: current.position }),
      ]);
      // Swap in local state
      const newStatuses = [...statuses];
      newStatuses[idx] = { ...swap, position: current.position } as IdeaLifecycleStatus;
      newStatuses[swapIdx] = { ...current, position: swap.position } as IdeaLifecycleStatus;
      newStatuses.sort((a, b) => a.position - b.position);
      setStatuses(newStatuses);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reorder');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setSaving(true);
    setError('');
    try {
      await deleteLifecycleStatus(id);
      setStatuses(prev => prev.filter(s => s.id !== id));
      setDeletingId(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete status');
      setDeletingId(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-3xl mx-auto py-8 px-4">
        {/* Header */}
        <div className="mb-6">
          <Link
            to="/product-intelligence"
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
          >
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Idea Lifecycle Settings</h1>
          <p className="mt-1 text-gray-600">
            Configure the lifecycle statuses that ideas pass through after being accepted.
            These stages will eventually sync with external planning tools (Aha!, Jira, etc.).
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
            <button onClick={() => setError('')} className="ml-2 underline">Dismiss</button>
          </div>
        )}

        {/* Loading */}
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-2 text-gray-500">Loading...</p>
          </div>
        ) : (
          <>
            {/* Status List */}
            <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-200">
              {statuses.length === 0 ? (
                <div className="p-6 text-center text-gray-500">
                  No lifecycle statuses configured. Add one to get started.
                </div>
              ) : (
                statuses.map((status, idx) => (
                  <div key={status.id} className="p-4">
                    {editingId === status.id ? (
                      /* Edit Mode */
                      <div className="flex items-center gap-3">
                        <input
                          type="color"
                          value={editColor}
                          onChange={(e) => setEditColor(e.target.value)}
                          className="w-8 h-8 rounded cursor-pointer border-0"
                        />
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="flex-1 border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                          onKeyDown={(e) => e.key === 'Enter' && handleSaveEdit()}
                        />
                        <button
                          onClick={handleSaveEdit}
                          disabled={saving || !editName.trim()}
                          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : deletingId === status.id ? (
                      /* Delete Confirmation */
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-red-700">
                          Delete "{status.name}"? This cannot be undone.
                        </span>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleDelete(status.id)}
                            disabled={saving}
                            className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                          >
                            {saving ? 'Deleting...' : 'Delete'}
                          </button>
                          <button
                            onClick={() => setDeletingId(null)}
                            className="px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Display Mode */
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span
                            className="w-4 h-4 rounded-full flex-shrink-0"
                            style={{ backgroundColor: status.color }}
                          />
                          <span className="font-medium text-gray-900">{status.name}</span>
                          {status.is_default && (
                            <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-500 rounded-full">Default</span>
                          )}
                          {status.idea_count > 0 && (
                            <span className="px-2 py-0.5 text-xs bg-blue-50 text-blue-600 rounded-full">
                              {status.idea_count} {status.idea_count === 1 ? 'idea' : 'ideas'}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          {/* Reorder buttons */}
                          <button
                            onClick={() => handleMove(status.id, 'up')}
                            disabled={idx === 0 || saving}
                            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                            title="Move up"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleMove(status.id, 'down')}
                            disabled={idx === statuses.length - 1 || saving}
                            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                            title="Move down"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                          {/* Edit button */}
                          <button
                            onClick={() => handleStartEdit(status)}
                            className="p-1 text-gray-400 hover:text-blue-600"
                            title="Edit"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          {/* Delete button */}
                          <button
                            onClick={() => setDeletingId(status.id)}
                            disabled={status.idea_count > 0}
                            className="p-1 text-gray-400 hover:text-red-600 disabled:opacity-30 disabled:cursor-not-allowed"
                            title={status.idea_count > 0 ? `Cannot delete: ${status.idea_count} ideas use this status` : 'Delete'}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Add New Status */}
            <div className="mt-4">
              {showAddForm ? (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center gap-3">
                    <input
                      type="color"
                      value={newColor}
                      onChange={(e) => setNewColor(e.target.value)}
                      className="w-8 h-8 rounded cursor-pointer border-0"
                    />
                    <input
                      type="text"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder="Status name (e.g., In Development)"
                      className="flex-1 border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                      autoFocus
                    />
                    <button
                      onClick={handleAdd}
                      disabled={saving || !newName.trim()}
                      className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                      {saving ? 'Adding...' : 'Add'}
                    </button>
                    <button
                      onClick={() => { setShowAddForm(false); setNewName(''); }}
                      className="px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowAddForm(true)}
                  disabled={statuses.length >= MAX_STATUSES}
                  className="w-full py-2 text-sm text-gray-600 border border-dashed border-gray-300 rounded-lg hover:border-gray-400 hover:text-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  title={statuses.length >= MAX_STATUSES ? `Maximum of ${MAX_STATUSES} lifecycle statuses` : 'Add a lifecycle status'}
                >
                  + Add Lifecycle Status
                  {statuses.length >= MAX_STATUSES && ` (${MAX_STATUSES} max)`}
                </button>
              )}
            </div>

            {/* Info Box */}
            <div className="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-lg">
              <div className="flex items-start space-x-3">
                <svg className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="text-sm text-blue-800">
                  <p className="font-medium mb-1">How lifecycle statuses work</p>
                  <p>
                    Lifecycle statuses track what happens to an idea after it's been accepted through triage.
                    They represent stages like planning, development, and delivery. In the future, these statuses
                    will sync automatically with external tools like Aha!, Jira, or Productboard.
                  </p>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
};

export default IdeaLifecycleSettingsPage;
