import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BriefResponse } from "@/lib/types";

interface UseBriefResult {
  brief: BriefResponse | null;
  loading: boolean;
  error: string | null;
  reload: (force?: boolean) => Promise<void>;
}

/**
 * Lazy-loads /api/brief/today. Cache-hit returns instantly; first call of the
 * day (or after force=true) may take 30-90s while DeepSeek synthesizes.
 */
export function useBrief(enabled: boolean): UseBriefResult {
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.briefToday(force);
      setBrief(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (enabled && !brief && !loading) {
      void reload();
    }
    // We intentionally don't depend on `reload`/`brief` to avoid loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  return { brief, loading, error, reload };
}
