/**
 * ReviewQueueCard Component
 *
 * Summary card showing pending items count for a review queue type.
 * Used in the Product Dashboard to show quick access to review queues.
 */

import { Link } from 'react-router-dom';

interface ReviewQueueCardProps {
  title: string;
  count: number;
  icon: 'ideas' | 'alerts' | 'reports';
  linkTo: string;
  maxDots?: number;
}

const ReviewQueueCard = ({
  title,
  count,
  icon,
  linkTo,
  maxDots = 5,
}: ReviewQueueCardProps) => {
  // Generate dot indicators
  const dots = [];
  for (let i = 0; i < maxDots; i++) {
    dots.push(
      <span
        key={i}
        className={`inline-block w-2 h-2 rounded-full ${
          i < count ? 'bg-blue-600' : 'bg-gray-200'
        }`}
      ></span>
    );
  }

  const getIcon = () => {
    switch (icon) {
      case 'ideas':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        );
      case 'alerts':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
        );
      case 'reports':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        );
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2 text-gray-700">
          {getIcon()}
          <span className="font-medium">{title}</span>
        </div>
        <span className="text-2xl font-bold text-gray-900">{count}</span>
      </div>

      {/* Dot indicators */}
      <div className="flex space-x-1 mb-3">
        {dots}
        {count > maxDots && (
          <span className="text-xs text-gray-500 ml-1">+{count - maxDots}</span>
        )}
      </div>

      <Link
        to={linkTo}
        className="inline-flex items-center text-sm text-blue-600 hover:text-blue-700 font-medium"
      >
        Review
        <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </Link>
    </div>
  );
};

export default ReviewQueueCard;
