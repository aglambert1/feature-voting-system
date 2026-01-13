/**
 * ProductListPage (Product Dashboard)
 *
 * Main page for Competitor Intelligence - lists all products with pending counts.
 * This is the default landing page for PO/Admin users.
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { getProductPendingCounts } from '../../services/api';
import ProductCard from './ProductCard';
import Navigation from '../../components/Navigation';
import { Product, ProductPendingCounts } from '../../types';

// Extended product type with pending counts
interface ProductWithCounts extends Product {
  product_name?: string;
  product_description?: string;
  product_category?: string;
  product_source_data?: { sources?: any[] };
  analysis_version?: number;
  analysis_count?: number;
  last_analyzed_at?: string;
  pendingCounts?: ProductPendingCounts;
}

export default function ProductListPage() {
  const [products, setProducts] = useState<ProductWithCounts[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const fetchPendingCounts = useCallback(async (productList: ProductWithCounts[]) => {
    // Fetch pending counts for each product in parallel
    const countsPromises = productList.map(async (product) => {
      try {
        const counts = await getProductPendingCounts(product.id);
        return { productId: product.id, counts };
      } catch {
        // If we can't get counts, return null (product might not have the new fields yet)
        return { productId: product.id, counts: null };
      }
    });

    const results = await Promise.all(countsPromises);

    // Update products with pending counts
    setProducts((prevProducts) =>
      prevProducts.map((product) => {
        const result = results.find((r) => r.productId === product.id);
        return {
          ...product,
          pendingCounts: result?.counts || undefined,
        };
      })
    );
  }, []);

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async (): Promise<void> => {
    try {
      setLoading(true);
      const response = await api.get<ProductWithCounts[]>('/product-intelligence/products');
      setProducts(response.data);

      // Store products in sessionStorage for other pages to use
      sessionStorage.setItem('products', JSON.stringify(response.data));

      // Fetch pending counts after products are loaded
      fetchPendingCounts(response.data);
    } catch (err: any) {
      setError(err.message || err.data?.detail || 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  const handleNewProduct = (): void => {
    navigate('/product-intelligence/products/create');
  };

  const handleViewProduct = (productId: number): void => {
    navigate(`/product-intelligence/products/${productId}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Product Intelligence
          </h1>
          <button
            onClick={handleNewProduct}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            + New Product
          </button>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {products.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg shadow">
            <div className="text-gray-500 mb-4">
              <svg
                className="mx-auto h-16 w-16 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              No products yet
            </h3>
            <p className="text-gray-500 mb-6">
              Get started by creating your first product
            </p>
            <button
              onClick={handleNewProduct}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Create First Product
            </button>
          </div>
        ) : (
          <>
            {/* Products Section Header */}
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Products</h2>

            {/* Grid - full width for single product, grid for multiple */}
            <div className={
              products.length === 1
                ? 'space-y-4'
                : 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6'
            }>
              {products.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onClick={() => handleViewProduct(product.id)}
                  fullWidth={products.length === 1}
                />
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
