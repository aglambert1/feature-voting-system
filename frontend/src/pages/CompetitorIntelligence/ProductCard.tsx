/**
 * ProductCard Component
 *
 * Displays a product card in the list view with key information
 * and pending counts for PO review items.
 */

import { formatDistanceToNow } from 'date-fns';
import { Product, ProductPendingCounts } from '../../types';

interface ProductCardProps {
  product: Product & {
    product_name?: string;
    product_description?: string;
    product_category?: string;
    analysis_version?: number;
    analysis_count?: number;
    last_analyzed_at?: string;
    pendingCounts?: ProductPendingCounts;
  };
  onClick: () => void;
}

export default function ProductCard({ product, onClick }: ProductCardProps) {
  const pendingCounts = product.pendingCounts;
  const totalPending = pendingCounts
    ? pendingCounts.ideas_pending + pendingCounts.ideas_auto_responded + pendingCounts.competitive_alerts
    : 0;

  return (
    <div
      onClick={onClick}
      className="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer border border-gray-200"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              {product.product_name || product.name}
            </h3>
            {/* Total pending badge */}
            {totalPending > 0 && (
              <span className="inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white bg-red-500 rounded-full">
                {totalPending}
              </span>
            )}
          </div>
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

      {/* Pending counts breakdown */}
      {pendingCounts && totalPending > 0 && (
        <div className="flex flex-wrap gap-2 mb-4 text-xs">
          {pendingCounts.ideas_pending > 0 && (
            <span className="inline-flex items-center px-2 py-1 bg-yellow-50 text-yellow-700 rounded border border-yellow-200">
              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              {pendingCounts.ideas_pending} awaiting response
            </span>
          )}
          {pendingCounts.ideas_auto_responded > 0 && (
            <span className="inline-flex items-center px-2 py-1 bg-purple-50 text-purple-700 rounded border border-purple-200">
              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              {pendingCounts.ideas_auto_responded} auto-responses
            </span>
          )}
          {pendingCounts.competitive_alerts > 0 && (
            <span className="inline-flex items-center px-2 py-1 bg-orange-50 text-orange-700 rounded border border-orange-200">
              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              {pendingCounts.competitive_alerts} alerts
            </span>
          )}
        </div>
      )}

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
