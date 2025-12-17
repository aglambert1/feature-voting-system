import { useState, useEffect } from 'react';

/**
 * Custom hook for debouncing values.
 *
 * Delays updating the debounced value until the input value has stopped
 * changing for the specified delay period. Useful for search-as-you-type
 * to avoid triggering API calls on every keystroke.
 *
 * @param value - The value to debounce
 * @param delay - Delay in milliseconds (default: 500ms)
 * @returns The debounced value
 *
 * @example
 * const [searchText, setSearchText] = useState('');
 * const debouncedSearchText = useDebounce(searchText, 500);
 *
 * useEffect(() => {
 *   // This only runs 500ms after user stops typing
 *   if (debouncedSearchText) {
 *     searchAPI(debouncedSearchText);
 *   }
 * }, [debouncedSearchText]);
 */
export function useDebounce<T>(value: T, delay: number = 500): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    // Set up a timer to update the debounced value after the delay
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    // Clean up the timer if value changes before delay expires
    // This is the key to debouncing - we cancel the previous timer
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}
