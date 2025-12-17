/**
 * ProductCard Component
 *
 * Displays a product card in the list view with key information
 */

import { formatDistanceToNow } from 'date-fns';
import { Product } from '../../types';

interface ProductCardProps {
  product: Product & {
    product_name?: string;
    product_description?: string;
    product_category?: string;
    analysis_version?: number;
    analysis_count?: number;
    last_analyzed_at?: string;
  };
  onClick: () => void;
}

export default function ProductCard({ product, onClick }: ProductCardProps) {
  return (
    <div
      onClick={onClick}
      className="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer border border-gray-200"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {product.product_name || product.name}
          </h3>
          <div className="flex flex-wrap gap-2">
            {(product.analysis_version ?? 0) > 0 ? (
              <span className="inline-block px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full font-medium">
                ✓ Analyzed
              </span>
            ) : (
              <span className="inline-block px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full font-medium">
                Not Analyzed
              </span>
            )}
            {product.product_category && (
              <span className="inline-block px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full font-medium">
                {product.product_category}
              </span>
            )}
          </div>
        </div>
      </div>

      <p className="text-gray-600 text-sm mb-4 line-clamp-2">
        {product.product_description || product.description}
      </p>

      <div className="flex items-center justify-between text-sm">
        <div className="text-gray-500">
          {product.analysis_count ?? 0} {(product.analysis_count ?? 0) === 1 ? 'analysis' : 'analyses'}
        </div>
        {product.last_analyzed_at && (
          <div className="text-gray-500">
            {formatDistanceToNow(new Date(product.last_analyzed_at), {
              addSuffix: true,
            })}
          </div>
        )}
      </div>
    </div>
  );
}
