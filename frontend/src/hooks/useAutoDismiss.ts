import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * State that automatically resets to `clearedValue` after `timeoutMs`.
 *
 * Setting a new non-cleared value restarts the timer, so rapid successive
 * messages each get the full display window. Timer is cleaned up on unmount.
 *
 * Usage: const [message, setMessage] = useAutoDismiss('', 3000);
 */
export function useAutoDismiss<T>(clearedValue: T, timeoutMs = 3000): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(clearedValue);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearedRef = useRef(clearedValue);

  const set = useCallback((next: T) => {
    setValue(next);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (next !== clearedRef.current) {
      timerRef.current = setTimeout(() => setValue(clearedRef.current), timeoutMs);
    }
  }, [timeoutMs]);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return [value, set];
}
