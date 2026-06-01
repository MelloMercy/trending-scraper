/**
 * Type contracts mirroring the FastAPI backend in main.py.
 * Update these whenever you change a backend response shape.
 */

export type Region = "cn" | "intl";
export type View = "grid" | "timeline" | "brief" | "curated" | "prompts";

// ---- /api/platforms ----
export interface PlatformInfo {
  id: string;
  name: string;
  region: Region;
}
export interface PlatformsResponse {
  platforms: PlatformInfo[];
}

// ---- /api/trending/{platform} ----
export interface TrendingItem {
  rank: number;
  title: string;
  url: string | null;
  hot_value: string | null;
  cover: string | null;
  snapshot_date?: string;
  fetched_at?: string;
  region?: Region;
}
export interface PlatformTrendingResponse {
  platform: string;
  region: Region;
  snapshot_date: string | null;
  fetched_at: string | null;
  count: number;
  items: TrendingItem[];
}
export interface PlatformHistoryResponse {
  platform: string;
  dates: string[];
}

// ---- /api/aggregate/today ----
export interface AggregateItem extends TrendingItem {
  platform: string;
}
export interface AggregateGroup {
  rank: number;
  score: number;
  n_platforms: number;
  platforms: string[];
  representative: AggregateItem;
  items: AggregateItem[];
}
export interface BigStory extends AggregateGroup {
  source?: "rule" | "llm";
  thread_idx?: number;
  thread_name?: string;
  thread_summary?: string;
}
export interface Aggregate {
  snapshot_date: string;
  total_items: number;
  total_groups: number;
  consensus_count: number;
  big_story: BigStory | null;
  groups: AggregateGroup[];
}
export interface Thread {
  name: string;
  summary: string;
  item_ids: number[];
}
export type ThemesStatus = "ok" | "cached" | "disabled" | "error";
export interface Themes {
  status: ThemesStatus;
  model: string | null;
  threads: Thread[];
  error: string | null;
  created_at?: string;
  region?: Region;
}
export interface AggregateResponse {
  snapshot_date: string;
  region: Region;
  aggregate: Aggregate;
  themes: Themes;
  deepseek_enabled: boolean;
}

// ---- /api/brief ----
export interface BriefSourceRef {
  platform: string;
  title: string;
  rank: number;
  url: string | null;
}
export interface BriefItem {
  title: string;
  summary: string;
  cn_sources: BriefSourceRef[];
  intl_sources: BriefSourceRef[];
  days_running?: number | null;
  first_seen?: string | null;
}
export type BriefStatus = "ok" | "cached" | "disabled" | "error";
export interface BriefResponse {
  status: BriefStatus;
  snapshot_date: string;
  model?: string | null;
  created_at?: string;
  error?: string | null;
  narrative?: string;
  consensus?: BriefItem[];
  cn_only?: BriefItem[];
  intl_only?: BriefItem[];
  persistent?: BriefItem[];
  emerging?: BriefItem[];
}

// ---- /api/curated/latest ----
export interface CuratedSourceMeta {
  name: string;
  url: string;
  config_path?: string;
  local_sources?: number;
  x_generated_at: string | null;
  podcasts_generated_at: string | null;
  blogs_generated_at: string | null;
}
export interface CuratedStats {
  sources: number;
  builders: number;
  tweets: number;
  podcasts: number;
  blogs: number;
}
export interface CuratedTweet {
  id: string;
  text: string;
  url: string | null;
  created_at: string | null;
  likes: number;
  retweets: number;
  replies: number;
  is_quote: boolean;
}
export interface CuratedBuilder {
  name: string;
  handle: string | null;
  bio: string;
  tweets: CuratedTweet[];
}
export interface CuratedPodcast {
  name: string;
  title: string;
  url: string | null;
  published_at: string | null;
  transcript_preview: string;
  transcript_length: number;
  source_kind?: string;
  category?: string;
  tags?: string[];
  homepage?: string | null;
}
export interface CuratedBlog {
  name: string;
  title: string;
  url: string | null;
  published_at: string | null;
  author: string;
  content_preview: string;
  content_length: number;
  source_kind?: string;
  category?: string;
  tags?: string[];
  homepage?: string | null;
}
export interface CuratedResponse {
  status: "ok" | "partial" | "error";
  generated_at: string;
  source: CuratedSourceMeta;
  stats: CuratedStats;
  builders: CuratedBuilder[];
  podcasts: CuratedPodcast[];
  blogs: CuratedBlog[];
  errors?: string[] | null;
}

// ---- /api/prompts ----
export interface PromptValidation {
  ok: boolean;
  missing: string[];
  format_error: string | null;
}
export interface PromptFile {
  id: "cluster-cn" | "cluster-intl" | "daily-brief";
  filename: string;
  title: string;
  description: string;
  placeholders: string[];
  refresh_hint: string;
  content: string;
  size: number;
  line_count: number;
  updated_at: string;
  validation: PromptValidation;
}
export interface PromptsResponse {
  prompts: PromptFile[];
}
export interface PromptResponse {
  prompt: PromptFile;
}
export interface PromptUpdateResponse extends PromptResponse {
  updated: boolean;
}

// ---- /api/refresh ----
export interface RefreshResultItem {
  platform?: string;
  region?: Region;
  count?: number;
  status: "ok" | "error";
  error?: string;
}
export interface RefreshResponse {
  region: string;
  results: RefreshResultItem[];
}
