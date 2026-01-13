/**
 * ProductCard Component
 *
 * Displays a product card in the list view with summary information.
 * Updated format per UI redesign spec:
 * - {N} product info sources | {N} competitive alerts
 * - {N} ideas pending ({N} auto-responded) | Last analysis: {time}
 */

import { formatDistanceToNow } from 'date-fns';
import { Product, ProductPendingCounts, ProductSource } from '../../types';

interface ProductSourceData {
  sources?: ProductSource[];
}

interface ProductCardProps {
  product: Product & {
    product_name?: string;
    product_description?: string;
    product_category?: string;
    product_source_data?: ProductSourceData;
    analysis_version?: number;
    analysis_count?: number;
    last_analyzed_at?: string;
    pendingCounts?: ProductPendingCounts;
  };
  onClick: () => void;
  fullWidth?: boolean;
}

export default function ProductCard({ product, onClick, fullWidth = false }: ProductCardProps) {
  const pendingCounts = product.pendingCounts;

  // Count product info sources
  const sourceCount = product.product_source_data?.sources?.length || 0;

  // Get counts for display
  // Combine pending + needs_review as "awaiting review" - both need PO attention
  const ideasAwaitingReview = (pendingCounts?.ideas_pending || 0) + (pendingCounts?.ideas_needs_review || 0);
  const competitiveAlerts = pendingCounts?.competitive_alerts || 0;

  // Determine status indicator color
  const getStatusColor = () => {
    if (competitiveAlerts > 0) return 'bg-orange-500';
    if (ideasAwaitingReview > 0) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer border border-gray-200 ${
        fullWidth ? 'w-full' : ''
      }`}
    >
      <div className="p-6">
        {/* Header: Status dot + Product Name */}
        <div className="flex items-start gap-3 mb-3">
          <span className={`mt-1.5 w-3 h-3 rounded-full flex-shrink-0 ${getStatusColor()}`} />
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-gray-900 truncate">
              {product.product_name || product.name}
            </h3>
          </div>
        </div>

        {/* Summary line 1: Sources | Alerts */}
        <div className="text-sm text-gray-600 mb-1 ml-6">
          {sourceCount} product info {sourceCount === 1 ? 'source' : 'sources'}
          {competitiveAlerts > 0 && (
            <span className="text-orange-600 font-medium">
              {' '}| {competitiveAlerts} competitive {competitiveAlerts === 1 ? 'alert' : 'alerts'}
            </span>
          )}
          {competitiveAlerts === 0 && (
            <span className="text-gray-400"> | 0 competitive alerts</span>
          )}
        </div>

        {/* Summary line 2: Ideas awaiting review | Last analysis */}
        <div className="text-sm text-gray-600 ml-6">
          {ideasAwaitingReview > 0 ? (
            <span className="text-yellow-600 font-medium">
              {ideasAwaitingReview} {ideasAwaitingReview === 1 ? 'idea' : 'ideas'} awaiting review
            </span>
          ) : (
            <span>0 ideas awaiting review</span>
          )}
          <span className="text-gray-400"> | </span>
          {product.last_analyzed_at ? (
            <span>
              Last analysis: {formatDistanceToNow(new Date(product.last_analyzed_at), { addSuffix: false })}
            </span>
          ) : (
            <span className="text-gray-400">Not analyzed</span>
          )}
        </div>
      </div>
    </div>
  );
}
