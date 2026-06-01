/**
 * Tiny typed API client for the FastAPI backend.
 *
 * In dev, Vite proxies /api → http://localhost:11001.
 * In prod, FastAPI serves both the bundle and the API on the same origin.
 */
import type {
  AggregateResponse,
  BriefResponse,
  CuratedResponse,
  PlatformHistoryResponse,
  PlatformsResponse,
  PlatformTrendingResponse,
  PromptResponse,
  PromptsResponse,
  PromptUpdateResponse,
  Region,
  RefreshResponse,
} from "./types";

class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init);
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new ApiError(`${resp.status} ${resp.statusText}: ${text}`.trim(), resp.status);
  }
  return (await resp.json()) as T;
}

export const api = {
  listPlatforms(region?: Region) {
    const q = region ? `?region=${region}` : "";
    return request<PlatformsResponse>(`/api/platforms${q}`);
  },

  trendingLatest(platform: string) {
    return request<PlatformTrendingResponse>(`/api/trending/${platform}`);
  },

  trendingByDate(platform: string, date: string) {
    return request<PlatformTrendingResponse>(`/api/trending/${platform}/${date}`);
  },

  trendingHistory(platform: string) {
    return request<PlatformHistoryResponse>(`/api/trending/${platform}/history`);
  },

  aggregateToday(region: Region, force_llm = false) {
    const params = new URLSearchParams({ region });
    if (force_llm) params.set("force_llm", "true");
    return request<AggregateResponse>(`/api/aggregate/today?${params}`);
  },

  refresh(region?: Region) {
    const q = region ? `?region=${region}` : "";
    return request<RefreshResponse>(`/api/refresh${q}`, { method: "POST" });
  },

  briefToday(force = false) {
    const q = force ? "?force=true" : "";
    return request<BriefResponse>(`/api/brief/today${q}`);
  },

  curatedLatest(force = false) {
    const q = force ? "?force=true" : "";
    return request<CuratedResponse>(`/api/curated/latest${q}`);
  },

  listPrompts() {
    return request<PromptsResponse>("/api/prompts");
  },

  getPrompt(promptId: string) {
    return request<PromptResponse>(`/api/prompts/${promptId}`);
  },

  updatePrompt(promptId: string, content: string) {
    return request<PromptUpdateResponse>(`/api/prompts/${promptId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
  },
};

export { ApiError };
