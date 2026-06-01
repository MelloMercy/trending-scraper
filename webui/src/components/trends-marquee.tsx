import { useMemo } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { emojiFor } from "@/data/platforms";
import { cn } from "@/lib/utils";
import type { AggregateGroup, PlatformInfo, Region } from "@/lib/types";

interface TrendsMarqueeProps {
  groups: AggregateGroup[];
  platforms: PlatformInfo[];
  loading: boolean;
  region: Region;
}

/**
 * Horizontal-scrolling strip just under the header.
 * Shows top-8 stories as a quick-scan ticker.
 *
 * Density notes:
 * - Top-3 ranks are warning-colored + larger, so the eye lands on them first.
 * - Platform name is dropped (the emoji is a sufficient identifier in this
 *   compact format) — frees horizontal room for the headline itself.
 */
export function TrendsMarquee({ groups, platforms: _platforms, loading, region }: TrendsMarqueeProps) {
  const items = useMemo(() => groups.slice(0, 8), [groups]);

  if (loading) {
    return (
      <div className="sticky top-[var(--header-h)] z-[5] flex items-center gap-5 px-6 py-2.5 border-b border-border bg-bg/95 backdrop-blur overflow-x-auto whitespace-nowrap">
        <Skeleton className="h-3 w-12 shrink-0" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-40 shrink-0" />
        ))}
      </div>
    );
  }
  if (!items.length) return null;

  const sourcesSuffix = region === "intl" ? "src" : "源";

  return (
    <div className="sticky top-[var(--header-h)] z-[5] flex items-center gap-5 px-6 py-2.5 border-b border-border bg-bg/95 backdrop-blur overflow-x-auto whitespace-nowrap scroll-smooth">
      <span className="text-xs font-semibold tracking-wider text-warning uppercase shrink-0 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-warning animate-pulse" aria-hidden />
        {region === "intl" ? "Trending" : "热度榜"}
      </span>
      {items.map((g, i) => {
        const rep = g.representative;
        const isTop3 = i < 3;
        return (
          <a
            key={i}
            href={rep.url ?? "#"}
            target="_blank"
            rel="noopener"
            className="group flex items-center gap-2 text-fg hover:text-accent2 transition-colors duration-150 shrink-0"
            title={rep.title}
          >
            <span
              className={cn(
                "tabular-nums font-bold shrink-0 w-4 text-right",
                isTop3 ? "text-sm text-warning" : "text-xs text-muted-2"
              )}
            >
              {i + 1}
            </span>
            <span className="text-sm shrink-0" aria-hidden>{emojiFor(rep.platform)}</span>
            <span className="text-sm max-w-[320px] truncate group-hover:underline underline-offset-2 decoration-accent2/50">
              {rep.title}
            </span>
            {g.n_platforms > 1 && (
              <span className="text-[10px] font-semibold tracking-wide text-warning bg-warning/[0.14] px-1.5 py-0.5 rounded-full shrink-0 tabular-nums">
                {g.n_platforms} {sourcesSuffix}
              </span>
            )}
          </a>
        );
      })}
    </div>
  );
}
