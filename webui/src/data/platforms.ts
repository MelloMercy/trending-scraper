/**
 * Platform display metadata. Backend already returns `id`, `name`, `region`,
 * so we only own emojis here (UI concern).
 */
export const PLATFORM_EMOJI: Record<string, string> = {
  // cn
  douyin: "🎵",
  xiaohongshu: "📕",
  bilibili: "📺",
  zhihu: "💡",
  kr36: "💼",
  huxiu: "🐯",
  // intl — original 6
  bbc_world: "📰",
  hackernews: "🟧",
  theverge: "🌀",
  techcrunch: "🚀",
  nyt_world: "🗞️",
  arstechnica: "🔬",
  // intl — Tier-1 expansion (wire + politics)
  reuters: "📡",
  ap_news: "🌐",
  politico: "🏛️",
  axios: "⚡",
  semafor: "🔭",
};

export function emojiFor(platform: string): string {
  return PLATFORM_EMOJI[platform] ?? "🔥";
}
