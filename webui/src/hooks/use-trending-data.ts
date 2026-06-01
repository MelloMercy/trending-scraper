import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type {
  AggregateResponse,
  PlatformHistoryResponse,
  PlatformInfo,
  PlatformTrendingResponse,
  Region,
} from "@/lib/types";

export interface PerPlatformData {
  platform: PlatformInfo;
  latest: PlatformTrendingResponse | null;
  history: string[];
}

export interface TrendingData {
  platforms: PlatformInfo[];
  perPlatform: PerPlatformData[];
  aggregate: AggregateResponse | null;
  loading: boolean;
  error: string | null;
  lastFetchedAt: string | null;
  refresh: () => Promise<void>;
  reload: () => Promise<void>;
  setPerPlatformForDate: (platformId: string, payload: PlatformTrendingResponse) => void;
}

async function fetchPlatformBundle(p: PlatformInfo): Promise<PerPlatformData> {
  const [latest, hist] = await Promise.all([
    api.trendingLatest(p.id).catch<PlatformTrendingResponse | null>(() => null),
    api
      .trendingHistory(p.id)
      .then((r: PlatformHistoryResponse) => r.dates)
      .catch<string[]>(() => []),
  ]);
  return { platform: p, latest, history: hist };
}

/**
 * Centralized data loader for a region. Returns:
 *  - platforms (display order)
 *  - perPlatform (latest snapshot + history dates per platform)
 *  - aggregate (cross-platform consensus + LLM themes)
 *  - actions: reload (re-pull current data), refresh (POST /refresh then reload)
 */
export function useTrendingData(region: Region): TrendingData {
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([]);
  const [perPlatform, setPerPlatform] = useState<PerPlatformData[]>([]);
  const [aggregate, setAggregate] = useState<AggregateResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const platformsResp = await api.listPlatforms(region);
      const platforms = platformsResp.platforms;
      setPlatforms(platforms);

      const [perPlatformResults, agg] = await Promise.all([
        Promise.all(platforms.map(fetchPlatformBundle)),
        api.aggregateToday(region).catch(() => null),
      ]);
      setPerPlatform(perPlatformResults);
      setAggregate(agg);

      const newest = perPlatformResults
        .map((r) => r.latest?.fetched_at)
        .filter((x): x is string => Boolean(x))
        .sort()
        .pop();
      setLastFetchedAt(newest ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [region]);

  const refresh = useCallback(async () => {
    const result = await api.refresh(region);
    const ok = result.results.filter((r) => r.status === "ok").length;
    const total = result.results.length;
    await reload();
    return { ok, total };
  }, [reload, region]) as unknown as () => Promise<void>;

  const setPerPlatformForDate = useCallback(
    (platformId: string, payload: PlatformTrendingResponse) => {
      setPerPlatform((prev) =>
        prev.map((row) =>
          row.platform.id === platformId ? { ...row, latest: payload } : row
        )
      );
    },
    []
  );

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    platforms,
    perPlatform,
    aggregate,
    loading,
    error,
    lastFetchedAt,
    refresh,
    reload,
    setPerPlatformForDate,
  };
}
