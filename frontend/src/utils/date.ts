/**
 * Shared date parsing and formatting.
 *
 * The backend serializes timestamps in UTC without a timezone indicator, so
 * naive `new Date(str)` parsing treats them as local time and shifts the
 * displayed value by the viewer's UTC offset. All formatters here parse via
 * parseUTCTimestamp to display correct local times.
 */

import { parseISO } from 'date-fns';

/**
 * Parse a UTC timestamp string from the backend.
 * Backend returns timestamps without timezone indicator, so we append 'Z' to treat as UTC.
 */
export function parseUTCTimestamp(timestamp: string): Date {
  // If timestamp already has timezone info, parse as-is
  if (timestamp.endsWith('Z') || timestamp.includes('+') || timestamp.includes('-', 10)) {
    return parseISO(timestamp);
  }
  // Otherwise, treat as UTC by appending Z
  // Replace space with T for ISO format compatibility
  return parseISO(timestamp.replace(' ', 'T') + 'Z');
}

/** "Jul 9, 2026" */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  return parseUTCTimestamp(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** "Jul 9, 2026, 02:30 PM" */
export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  return parseUTCTimestamp(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** "Never" / "Just now" / "5h ago" / "3d ago" / formatDate fallback */
export function formatRelativeDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Never';
  const date = parseUTCTimestamp(dateStr);
  const diffMs = Date.now() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateStr);
}
