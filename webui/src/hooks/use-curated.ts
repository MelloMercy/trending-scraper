import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CuratedResponse } from "@/lib/types";

interface UseCuratedResult {
  curated: CuratedResponse | null;
  loading: boolean;
  error: string | null;
  reload: (force?: boolean) => Promise<void>;
}

export function useCurated(enabled: boolean): UseCuratedResult {
  const [curated, setCurated] = useState<CuratedResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      setCurated(await api.curatedLatest(force));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (enabled && !curated && !loading) {
      void reload(false);
    }
    // Avoid refetch loops; explicit reload handles freshness after first load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  return { curated, loading, error, reload };
}
