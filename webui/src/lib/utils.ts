import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/**
 * Format an ISO timestamp as a human-readable relative time.
 * Backend writes `fetched_at` as `YYYY-MM-DDTHH:MM:SS` (no tz, local time).
 * Returns "刚刚" / "N 分钟前" / "N 小时前" / "HH:MM" / "MM-DD HH:MM".
 *
 * Pass `lang: "en"` for English labels.
 */
export function formatRelativeTime(iso: string, lang: "zh" | "en" = "zh"): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60_000);
  const hr = Math.floor(diff / 3_600_000);

  if (lang === "en") {
    if (diff < 60_000) return "just now";
    if (min < 60) return `${min} min ago`;
    if (hr < 24) return `${hr} hr ago`;
  } else {
    if (diff < 60_000) return "刚刚";
    if (min < 60) return `${min} 分钟前`;
    if (hr < 24) return `${hr} 小时前`;
  }

  // Older than 24h: show MM-DD HH:MM
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mi}`;
}
