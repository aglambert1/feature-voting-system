/**
 * IdeasPage
 *
 * Main page for browsing ideas:
 * - Fetches ideas from API with pagination
 * - Displays loading state
 * - Renders IdeaCard components
 * - Sorts by score (highest first)
 * - Empty state
 * - "Submit New Idea" button
 * - Navigation header
 * - Pagination controls
 * - PO mode: status filtering, respond modal, auto-responded filter
 */

import { useState, useEffect, useCallback, ChangeEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useProduct } from '../contexts/ProductContext';
import { getIdeas, checkCanRespond, getLifecycleStatuses } from '../services/api';
import IdeaCard from '../components/IdeaCard';
import IdeaResponseModal from '../components/IdeaResponseModal';
import Navigation from '../components/Navigation';
import type { IdeaListItem, ApiError, IdeaSortOption, IdeaLifecycleStatus } from '../types';
import { UserRole } from '../types';

const ITEMS_PER_PAGE = 20;

// Sort option labels for the dropdown
const SORT_OPTIONS: { value: IdeaSortOption; label: string; description: string }[] = [
  { value: 'pending_first', label: 'Needs Review', description: 'Ideas awaiting review first' },
  { value: 'most_votes', label: 'Most Popular', description: 'Highest voted ideas first' },
  { value: 'most_recent', label: 'Most Recent', description: 'Newest ideas first' },
  { value: 'my_ideas', label: 'My Ideas', description: 'Your submitted ideas first' },
];

const IdeasPage = () => {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    products,
    selectedProductId,
    setSelectedProductId,
    loadingProducts,
    hasProducts
  } = useProduct();

  // Determine if user is PO or Admin
  const isPOOrAdmin = user?.role === UserRole.PRODUCT_OWNER || user?.role === UserRole.ADMIN;

  // Triage mode: when navigated from Product Dashboard
  const isTriageMode = searchParams.get('from') === 'dashboard';
  const triageProductId = searchParams.get('product');
  const triageProductName = isTriageMode && triageProductId
    ? products.find(p => p.id === parseInt(triageProductId))?.product_name
    : null;

  // Lifecycle status filter (PO/Admin only)
  const [lifecycleStatuses, setLifecycleStatuses] = useState<IdeaLifecycleStatus[]>([]);
  const [selectedLifecycleStatusId, setSelectedLifecycleStatusId] = useState<number | null>(null);

  // State
  const [ideas, setIdeas] = useState<IdeaListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  // Sort state - default depends on role (set in useEffect)
  const [sortBy, setSortBy] = useState<IdeaSortOption | undefined>(undefined);

  // PO mode state
  const [respondingToIdeaId, setRespondingToIdeaId] = useState<number | null>(null);
  const [respondingToIdeaTitle, setRespondingToIdeaTitle] = useState<string>('');

  // Pagination state
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalIdeas, setTotalIdeas] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(0);

  // Sync URL parameter with context on mount
  useEffect(() => {
    const productParam = searchParams.get('product');
    if (productParam) {
      if (productParam === 'all') {
        setSelectedProductId('all');
      } else {
        const productId = parseInt(productParam, 10);
        if (!isNaN(productId)) {
          setSelectedProductId(productId);
        }
      }
    }
  }, [searchParams, setSelectedProductId]);

  // Fetch lifecycle statuses for PO/Admin filter
  useEffect(() => {
    if (isPOOrAdmin) {
      getLifecycleStatuses()
        .then(setLifecycleStatuses)
        .catch(() => {}); // Non-critical, filter just won't show
    }
  }, [isPOOrAdmin]);

  /**
   * Fetch ideas from API with pagination and sorting
   */
  const fetchIdeas = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const skip = (currentPage - 1) * ITEMS_PER_PAGE;
      const baseParams = {
        skip,
        limit: ITEMS_PER_PAGE,
        ...(sortBy && { sort_by: sortBy }),
        ...(selectedLifecycleStatusId && { lifecycle_status_id: selectedLifecycleStatusId }),
      };
      const params = (selectedProductId === 'all' || selectedProductId === null)
        ? baseParams
        : { ...baseParams, product_id: selectedProductId };

      const response = await getIdeas(params);

      setIdeas(response.ideas || []);
      setTotalIdeas(response.total);
      setTotalPages(Math.ceil(response.total / ITEMS_PER_PAGE));
    } catch (err) {
      const error = err as ApiError;
      setError(error.message || 'Failed to load ideas');
      console.error('Error fetching ideas:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedProductId, currentPage, sortBy, selectedLifecycleStatusId]);

  // Fetch ideas when product selection, page, or sort changes
  useEffect(() => {
    if (!loadingProducts) {
      fetchIdeas();
    }
  }, [fetchIdeas, loadingProducts]);

  /**
   * Handle vote update - refresh ideas
   */
  const handleVoteUpdate = useCallback(async (_ideaId: number) => {
    await fetchIdeas();
  }, [fetchIdeas]);

  const handleProductChange = useCallback((e: ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    const newProductId = value === 'all' ? 'all' : parseInt(value);
    setSelectedProductId(newProductId);
    setCurrentPage(1);  // Reset to first page when changing product

    // Update URL to reflect the selection
    if (newProductId === 'all') {
      setSearchParams({});
    } else {
      setSearchParams({ product: newProductId.toString() });
    }
  }, [setSelectedProductId, setSearchParams]);

  const handleSortChange = useCallback((e: ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value as IdeaSortOption;
    setSortBy(value);
    setCurrentPage(1);  // Reset to first page when changing sort
  }, []);

  const handlePageChange = useCallback((newPage: number) => {
    setCurrentPage(newPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  // Handle opening the respond modal (with permission check)
  const handleRespond = useCallback(async (ideaId: number) => {
    const idea = ideas.find(i => i.id === ideaId);
    if (!idea) return;

    try {
      // Check if user has permission to respond to this idea
      const response = await checkCanRespond(ideaId);
      if (!response.can_respond) {
        setError('You do not have permission to respond to this idea. Only the product owner can respond.');
        return;
      }

      setRespondingToIdeaId(ideaId);
      setRespondingToIdeaTitle(idea.title);
    } catch (err) {
      console.error('Error checking respond permission:', err);
      setError('Failed to verify permission. Please try again.');
    }
  }, [ideas]);

  // Handle closing the respond modal
  const handleCloseResponseModal = useCallback(() => {
    setRespondingToIdeaId(null);
    setRespondingToIdeaTitle('');
  }, []);

  // Handle successful response
  const handleResponseSuccess = useCallback(() => {
    handleCloseResponseModal();
    fetchIdeas(); // Refresh the list
  }, [handleCloseResponseModal, fetchIdeas]);

  // Get product ID for the modal (use the selected product or the idea's product)
  const getProductIdForModal = (): number => {
    if (selectedProductId && selectedProductId !== 'all') {
      return selectedProductId;
    }
    const idea = ideas.find(i => i.id === respondingToIdeaId);
    return idea?.product_id || 0;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation Header */}
      <Navigation />

      {/* Main Content */}
      <main className="main-content max-w-7xl mx-auto py-8 px-4">
        {/* Back to Dashboard link (triage mode) */}
        {isTriageMode && triageProductId && (
          <Link
            to={`/product-intelligence/products/${triageProductId}`}
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
          >
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to {triageProductName || 'Product'} Dashboard
          </Link>
        )}

        {/* Page Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-3xl font-bold text-gray-900">
              {isTriageMode ? 'Idea Triage' : 'All Ideas'}
            </h2>
            <p className="mt-2 text-gray-600">
              {isTriageMode
                ? 'Review and respond to submitted ideas'
                : 'Vote on ideas to help prioritize features'
              }
            </p>
          </div>

          {/* Submit Button - hidden in triage mode, disabled if no products */}
          {!isTriageMode && (
            !loadingProducts && hasProducts ? (
              <Link
                to={selectedProductId !== 'all' ? `/submit?product=${selectedProductId}` : '/submit'}
                className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg shadow-sm transition-colors"
              >
                Submit New Idea
              </Link>
            ) : (
              <button
                disabled
                className="bg-gray-300 text-gray-500 font-medium px-6 py-3 rounded-lg shadow-sm cursor-not-allowed"
                title="Create a product first to submit ideas"
              >
                Submit New Idea
              </button>
            )
          )}
        </div>

        {/* Empty State - No Products */}
        {!loadingProducts && !hasProducts && (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
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
                d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
              />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              No products yet
            </h3>
            <p className="mt-2 text-gray-600">
              {user?.role === 'voter'
                ? "A product needs to be created before submitting ideas"
                : "Create a product first to start browsing ideas"
              }
            </p>
            {(user?.role === 'product_owner' || user?.role === 'admin') && (
              <Link
                to="/product-intelligence"
                className="mt-6 inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg"
              >
                Go to Products
              </Link>
            )}
          </div>
        )}

        {/* Filters: Product Selector and Sort */}
        {!loadingProducts && hasProducts && (
          <div className="mb-6 bg-white rounded-lg border border-gray-200 p-4">
            <div className={`grid grid-cols-1 gap-4 ${isPOOrAdmin && lifecycleStatuses.length > 0 ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
              {/* Product Filter */}
              <div>
                <label htmlFor="product-filter" className="block text-sm font-medium text-gray-700 mb-2">
                  Filter by Product
                </label>
                <select
                  id="product-filter"
                  value={selectedProductId ?? 'all'}
                  onChange={handleProductChange}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="all">All Products</option>
                  {products.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.product_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Sort Order */}
              <div>
                <label htmlFor="sort-order" className="block text-sm font-medium text-gray-700 mb-2">
                  Sort By
                </label>
                <select
                  id="sort-order"
                  value={sortBy || (isPOOrAdmin ? 'pending_first' : 'most_votes')}
                  onChange={handleSortChange}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Lifecycle Status Filter - PO/Admin only */}
              {isPOOrAdmin && lifecycleStatuses.length > 0 && (
                <div>
                  <label htmlFor="lifecycle-filter" className="block text-sm font-medium text-gray-700 mb-2">
                    Lifecycle Stage
                  </label>
                  <select
                    id="lifecycle-filter"
                    value={selectedLifecycleStatusId ?? ''}
                    onChange={(e) => {
                      const val = e.target.value;
                      setSelectedLifecycleStatusId(val ? parseInt(val) : null);
                      setCurrentPage(1);
                    }}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="">All Stages</option>
                    {lifecycleStatuses.map((status) => (
                      <option key={status.id} value={status.id}>
                        {status.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Results Count */}
        {!loading && !error && hasProducts && totalIdeas > 0 && (
          <div className="mb-4 text-sm text-gray-600">
            Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1}-{Math.min(currentPage * ITEMS_PER_PAGE, totalIdeas)} of {totalIdeas} ideas
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-gray-300 border-t-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading ideas...</p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="bg-red-50 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
            <button
              onClick={fetchIdeas}
              className="ml-4 text-red-800 underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* Empty State - No Ideas */}
        {!loading && !error && hasProducts && ideas.length === 0 && (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
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
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              No ideas yet
            </h3>
            <p className="mt-2 text-gray-600">
              {selectedProductId === 'all'
                ? "Be the first to submit an idea!"
                : "Be the first to submit an idea for this product!"
              }
            </p>
            <Link
              to={selectedProductId !== 'all' ? `/submit?product=${selectedProductId}` : '/submit'}
              className="mt-6 inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg"
            >
              Submit an Idea
            </Link>
          </div>
        )}

        {/* Ideas List */}
        {!loading && !error && ideas.length > 0 && (
          <>
            <div className="space-y-4">
              {ideas.map((idea) => (
                <IdeaCard
                  key={idea.id}
                  idea={idea}
                  onVoteUpdate={handleVoteUpdate}
                  showPOControls={isPOOrAdmin}
                  onRespond={isPOOrAdmin ? handleRespond : undefined}
                />
              ))}
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="mt-8 flex items-center justify-center gap-2">
                {/* Previous Button */}
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                  className={`px-4 py-2 rounded-md font-medium ${
                    currentPage === 1
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300'
                  }`}
                >
                  Previous
                </button>

                {/* Page Numbers */}
                <div className="flex gap-1">
                  {/* First page */}
                  {currentPage > 3 && (
                    <>
                      <button
                        onClick={() => handlePageChange(1)}
                        className="px-3 py-2 rounded-md bg-white text-gray-700 hover:bg-gray-50 border border-gray-300"
                      >
                        1
                      </button>
                      {currentPage > 4 && <span className="px-2 py-2">...</span>}
                    </>
                  )}

                  {/* Current page and neighbors */}
                  {Array.from({ length: totalPages }, (_, i) => i + 1)
                    .filter(page =>
                      page === currentPage ||
                      page === currentPage - 1 ||
                      page === currentPage + 1 ||
                      (currentPage <= 2 && page <= 3) ||
                      (currentPage >= totalPages - 1 && page >= totalPages - 2)
                    )
                    .map(page => (
                      <button
                        key={page}
                        onClick={() => handlePageChange(page)}
                        className={`px-3 py-2 rounded-md font-medium ${
                          page === currentPage
                            ? 'bg-blue-600 text-white'
                            : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300'
                        }`}
                      >
                        {page}
                      </button>
                    ))}

                  {/* Last page */}
                  {currentPage < totalPages - 2 && (
                    <>
                      {currentPage < totalPages - 3 && <span className="px-2 py-2">...</span>}
                      <button
                        onClick={() => handlePageChange(totalPages)}
                        className="px-3 py-2 rounded-md bg-white text-gray-700 hover:bg-gray-50 border border-gray-300"
                      >
                        {totalPages}
                      </button>
                    </>
                  )}
                </div>

                {/* Next Button */}
                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className={`px-4 py-2 rounded-md font-medium ${
                    currentPage === totalPages
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300'
                  }`}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {/* Response Modal */}
      {respondingToIdeaId && (
        <IdeaResponseModal
          ideaId={respondingToIdeaId}
          ideaTitle={respondingToIdeaTitle}
          productId={getProductIdForModal()}
          onClose={handleCloseResponseModal}
          onSuccess={handleResponseSuccess}
        />
      )}
    </div>
  );
};

export default IdeasPage;
