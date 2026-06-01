import { useEffect } from "react";

type Handlers = Partial<Record<string, () => void>>;

/**
 * Listen for single-key shortcuts (no modifiers). Ignored while typing.
 * Pass a map like { r: refresh, g: () => setView("grid") }.
 */
export function useKeyboardShortcuts(handlers: Handlers) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable]")) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const fn = handlers[e.key.toLowerCase()];
      if (fn) {
        e.preventDefault();
        fn();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handlers]);
}
