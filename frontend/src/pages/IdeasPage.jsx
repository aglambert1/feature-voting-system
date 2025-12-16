/**
 * IdeasPage
 *
 * Main page for browsing ideas:
 * - Fetches ideas from API
 * - Displays loading state
 * - Renders IdeaCard components
 * - Sorts by score (highest first)
 * - Empty state
 * - "Submit New Idea" button
 * - Navigation header
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { getIdeas } from '../services/api';
import api from '../services/api';
import IdeaCard from '../components/IdeaCard';
import Navigation from '../components/Navigation';

const IdeasPage = () => {
  const { user } = useAuth();

  // State
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(false);  // Don't show loading until product selected
  const [error, setError] = useState('');
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState(null);
  const [hasProducts, setHasProducts] = useState(true);
  const [loadingProducts, setLoadingProducts] = useState(true);

  // Fetch products on mount
  useEffect(() => {
    fetchProducts();
  }, []);

  // Fetch ideas when product selection changes
  useEffect(() => {
    if (!loadingProducts && selectedProductId) {
      fetchIdeas();
    }
  }, [selectedProductId, loadingProducts]);

  /**
   * Fetch products from API
   */
  const fetchProducts = async () => {
    try {
      setLoadingProducts(true);
      const response = await api.get('/product-intelligence/products');
      setProducts(response.data || []);
      setHasProducts(response.data.length > 0);

      // Auto-select first product if only one exists
      if (response.data.length === 1) {
        setSelectedProductId(response.data[0].id);
      }
    } catch (err) {
      console.error('Error fetching products:', err);
      setHasProducts(false);
    } finally {
      setLoadingProducts(false);
    }
  };

  /**
   * Fetch ideas from API
   */
  const fetchIdeas = async () => {
    if (!selectedProductId) {
      return;
    }

    try {
      setLoading(true);
      setError('');

      const params = { product_id: selectedProductId };
      const data = await getIdeas(params);

      // Ideas are already sorted by score on backend
      setIdeas(data.ideas || []);
    } catch (err) {
      setError(err.message || 'Failed to load ideas');
      console.error('Error fetching ideas:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handle vote update - refresh ideas
   */
  const handleVoteUpdate = async (ideaId) => {
    // Refetch ideas to get updated vote counts
    // Note: In production, you might want to update just the changed idea
    // For MVP, refetching all is simpler
    await fetchIdeas();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation Header */}
      <Navigation />

      {/* Main Content */}
      <main className="main-content max-w-7xl mx-auto py-8">
        {/* Page Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-3xl font-bold text-gray-900">All Ideas</h2>
            <p className="mt-2 text-gray-600">
              Vote on ideas to help prioritize features
            </p>
          </div>

          {/* Submit Button - disabled if no products */}
          {!loadingProducts && hasProducts ? (
            <Link
              to="/submit"
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
              Create a product first to start browsing ideas
            </p>
            <Link
              to="/product-intelligence"
              className="mt-6 inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg"
            >
              Go to Products
            </Link>
          </div>
        )}

        {/* Product Selector */}
        {!loadingProducts && hasProducts && (
          <div className="mb-6 bg-white rounded-lg border border-gray-200 p-4">
            <label htmlFor="product-filter" className="block text-sm font-medium text-gray-700 mb-2">
              Select Product
            </label>
            <select
              id="product-filter"
              value={selectedProductId || ''}
              onChange={(e) => setSelectedProductId(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            >
              <option value="">Select a product to view ideas...</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.product_name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Prompt to select product */}
        {!loadingProducts && hasProducts && !selectedProductId && (
          <div className="text-center py-12 text-gray-500 bg-white rounded-lg border border-gray-200">
            <p>Please select a product to view ideas</p>
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

        {/* Empty State */}
        {!loading && !error && ideas.length === 0 && (
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
              Be the first to submit an idea!
            </p>
            <Link
              to="/submit"
              className="mt-6 inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg"
            >
              Submit an Idea
            </Link>
          </div>
        )}

        {/* Ideas List */}
        {!loading && !error && ideas.length > 0 && (
          <div className="space-y-4">
            {ideas.map((idea) => (
              <IdeaCard
                key={idea.id}
                idea={idea}
                onVoteUpdate={handleVoteUpdate}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default IdeasPage;
