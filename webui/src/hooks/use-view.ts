import { useCallback, useState } from "react";
import type { View } from "@/lib/types";

const KEY = "trending.view";

function readView(): View {
  const v = localStorage.getItem(KEY);
  return v === "timeline" || v === "brief" || v === "curated" || v === "prompts" ? v : "grid";
}

/**
 * View state persisted to localStorage.
 */
export function useView(): [View, (v: View) => void] {
  const [view, setViewState] = useState<View>(readView);
  const setView = useCallback((v: View) => {
    setViewState(v);
    localStorage.setItem(KEY, v);
  }, []);
  return [view, setView];
}
