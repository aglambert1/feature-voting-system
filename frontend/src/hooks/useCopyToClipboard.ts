import { useCallback, useEffect, useRef, useState } from 'react';

interface CopyToClipboardResult {
  /** Key of the item most recently copied (for per-row "Copied!" indicators). */
  copiedKey: string | number | null;
  /** Convenience: something was copied within the reset window. */
  copied: boolean;
  /** Copy text; pass a key when several copy targets share the hook. */
  copy: (text: string, key?: string | number) => Promise<void>;
}

/**
 * Clipboard copy with a transient "copied" flag that resets after `resetMs`.
 */
export function useCopyToClipboard(resetMs = 2000): CopyToClipboardResult {
  const [copiedKey, setCopiedKey] = useState<string | number | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const copy = useCallback(async (text: string, key: string | number = 'default') => {
    await navigator.clipboard.writeText(text);
    setCopiedKey(key);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopiedKey(null), resetMs);
  }, [resetMs]);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return { copiedKey, copied: copiedKey !== null, copy };
}
