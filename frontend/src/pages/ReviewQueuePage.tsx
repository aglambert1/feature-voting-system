/**
 * ReviewQueuePage
 *
 * PM Review Queue dashboard showing all items needing review.
 * Supports filtering by:
 * - Queue type (ideas, alerts, reports)
 * - Status (pending, in_review, approved, rejected)
 * - Priority (low, normal, high, urgent)
 * - Product
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import Navigation from '../components/Navigation';
import ReviewQueueItem from '../components/ReviewQueueItem';
import { useProduct } from '../contexts/ProductContext';
import { getReviewQueue, getReviewQueueStats } from '../services/api';
import type { PMReviewQueueItem, PMReviewQueueStats, ApiError } from '../types';
import { ReviewQueueType, ReviewQueueStatus } from '../types';

const ReviewQueuePage = () => {
  const { products, selectedProductId, setSelectedProductId, loadingProducts } = useProduct();
  const [searchParams, setSearchParams] = useSearchParams();

  // State
  const [items, setItems] = useState<PMReviewQueueItem[]>([]);
  const [stats, setStats] = useState<PMReviewQueueStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Filters from URL
  const queueType = searchParams.get('type') || '';
  const status = searchParams.get('status') || 'pending';
  const priority = searchParams.get('priority') || '';

  const fetchQueue = useCallback(async () => {
    if (loadingProducts) return;

    setLoading(true);
    setError('');

    try {
      const productId = selectedProductId && selectedProductId !== 'all'
        ? selectedProductId
        : undefined;

      const [queueResponse, statsResponse] = await Promise.all([
        getReviewQueue({
          product_id: productId,
          queue_type: queueType || undefined,
          status: status || undefined,
          priority: priority || undefined,
          skip: (page - 1) * pageSize,
          limit: pageSize,
        }),
        productId ? getReviewQueueStats(productId) : Promise.resolve(null),
      ]);

      setItems(queueResponse.items);
      setTotal(queueResponse.total);
      if (statsResponse) {
        setStats(statsResponse);
      }
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, [selectedProductId, queueType, status, priority, page, loadingProducts]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleItemUpdate = (updatedItem: PMReviewQueueItem) => {
    setItems((prev) =>
      prev.map((item) => (item.id === updatedItem.id ? updatedItem : item))
    );
    // Refresh stats
    if (selectedProductId && selectedProductId !== 'all') {
      getReviewQueueStats(selectedProductId).then(setStats).catch(() => {});
    }
  };

  const handleFilterChange = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value) {
      newParams.set(key, value);
    } else {
      newParams.delete(key);
    }
    setSearchParams(newParams);
    setPage(1);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Review Queue</h1>
              <p className="text-gray-600">
                Review and approve ideas, competitive alerts, and reports
              </p>
            </div>
            <Link
              to="/product-intelligence"
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              ← Back to Products
            </Link>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="text-2xl font-bold text-yellow-600">{stats.total_pending}</div>
              <div className="text-sm text-gray-500">Pending</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="text-2xl font-bold text-blue-600">{stats.total_in_review}</div>
              <div className="text-sm text-gray-500">In Review</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="text-2xl font-bold text-green-600">{stats.total_approved}</div>
              <div className="text-sm text-gray-500">Approved</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="text-2xl font-bold text-red-600">{stats.total_rejected}</div>
              <div className="text-sm text-gray-500">Rejected</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
          <div className="flex flex-wrap gap-4">
            {/* Product Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Product</label>
              <select
                value={selectedProductId || 'all'}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedProductId(val === 'all' ? 'all' : parseInt(val));
                }}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Products</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.product_name}
                  </option>
                ))}
              </select>
            </div>

            {/* Type Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Type</label>
              <select
                value={queueType}
                onChange={(e) => handleFilterChange('type', e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Types</option>
                <option value={ReviewQueueType.IDEA}>Ideas</option>
                <option value={ReviewQueueType.COMPETITIVE_ALERT}>Alerts</option>
                <option value={ReviewQueueType.REPORT}>Reports</option>
              </select>
            </div>

            {/* Status Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
              <select
                value={status}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Statuses</option>
                <option value={ReviewQueueStatus.PENDING}>Pending</option>
                <option value={ReviewQueueStatus.IN_REVIEW}>In Review</option>
                <option value={ReviewQueueStatus.APPROVED}>Approved</option>
                <option value={ReviewQueueStatus.REJECTED}>Rejected</option>
                <option value={ReviewQueueStatus.DEFERRED}>Deferred</option>
              </select>
            </div>

            {/* Priority Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => handleFilterChange('priority', e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Priorities</option>
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-2 text-gray-500">Loading queue...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-600">{error}</p>
            <button
              onClick={fetchQueue}
              className="mt-2 text-sm text-red-700 hover:text-red-800 underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* Queue Items */}
        {!loading && !error && (
          <>
            {items.length === 0 ? (
              <div className="text-center py-12 bg-white border border-gray-200 rounded-lg">
                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <h3 className="mt-2 text-lg font-medium text-gray-900">Queue is empty</h3>
                <p className="mt-1 text-gray-500">
                  No items match your current filters.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {items.map((item) => (
                  <ReviewQueueItem
                    key={item.id}
                    item={item}
                    onUpdate={handleItemUpdate}
                    onError={setError}
                  />
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-6 bg-white border border-gray-200 rounded-lg p-4">
                <div className="text-sm text-gray-500">
                  Showing {(page - 1) * pageSize + 1} to{' '}
                  {Math.min(page * pageSize, total)} of {total} items
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <span className="px-3 py-1.5 text-sm">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};

export default ReviewQueuePage;
