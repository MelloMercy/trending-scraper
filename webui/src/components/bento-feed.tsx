import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CoverImage } from "@/components/cover-image";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/empty-state";
import { api } from "@/lib/api";
import { emojiFor } from "@/data/platforms";
import { cn, todayISO } from "@/lib/utils";
import type {
  AggregateGroup,
  PlatformTrendingResponse,
  Region,
} from "@/lib/types";
import type { PerPlatformData } from "@/hooks/use-trending-data";

interface BentoFeedProps {
  perPlatform: PerPlatformData[];
  groups: AggregateGroup[];
  region: Region;
  onDateChange: (platformId: string, payload: PlatformTrendingResponse) => void;
}

/**
 * Magazine-style platform feed. Each platform is a column; first item per
 * column is rendered larger with cover thumbnail, rest as compact list rows.
 */
export function BentoFeed({
  perPlatform,
  groups,
  region,
  onDateChange,
}: BentoFeedProps) {
  return (
    <div className="grid gap-5 [grid-template-columns:repeat(auto-fit,minmax(400px,1fr))]">
      {perPlatform.map((row) => (
        <PlatformColumn
          key={row.platform.id}
          row={row}
          groups={groups}
          region={region}
          onDateChange={onDateChange}
        />
      ))}
    </div>
  );
}

function PlatformColumn({
  row,
  groups,
  region,
  onDateChange,
}: {
  row: PerPlatformData;
  groups: AggregateGroup[];
  region: Region;
  onDateChange: (platformId: string, payload: PlatformTrendingResponse) => void;
}) {
  const { platform, latest, history } = row;
  const items = latest?.items ?? [];
  const today = todayISO();
  const isStale = latest?.snapshot_date && latest.snapshot_date !== today;

  const consensusMap = useMemo(() => {
    const m = new Map<string, number>();
    for (const g of groups) {
      if (g.n_platforms < 2) continue;
      for (const it of g.items) {
        if (it.platform === platform.id) m.set(it.title, g.n_platforms);
      }
    }
    return m;
  }, [groups, platform.id]);

  async function handleDateChange(date: string) {
    try {
      const payload = await api.trendingByDate(platform.id, date);
      onDateChange(platform.id, payload);
    } catch {
      /* swallow */
    }
  }

  const [hero, ...rest] = items;

  return (
    <section className="bg-panel border border-border rounded-md shadow-card overflow-hidden flex flex-col transition-colors duration-150 hover:border-border-strong">
      {/* Header */}
      <header className="flex items-center justify-between gap-3 px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 font-semibold text-md tracking-tight">
          <span className="text-base">{emojiFor(platform.id)}</span>
          <span>{platform.name}</span>
          <Badge>{items.length}</Badge>
        </div>
        <div className={cn("text-xs text-muted", isStale && "text-hot")}>
          {history.length > 0 && latest?.snapshot_date ? (
            <Select value={latest.snapshot_date} onValueChange={handleDateChange}>
              <SelectTrigger className="min-w-[7rem]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {history.map((d) => (
                  <SelectItem key={d} value={d}>
                    {d}
                    {d === today &&
                      (region === "intl" ? " · today" : " · 今日")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <span>{region === "intl" ? "no snapshot" : "无快照"}</span>
          )}
        </div>
      </header>

      {/* Body */}
      {!latest ? (
        <ColumnSkeleton />
      ) : items.length === 0 ? (
        <EmptyState
          title={region === "intl" ? "No data yet" : "暂无数据"}
          hint={region === "intl" ? "Click Refresh" : "点击侧栏「刷新数据」"}
        />
      ) : (
        <div className="flex flex-col">
          {/* Hero (rank #1) */}
          {hero && (
            <FeedHero
              item={hero}
              consensus={consensusMap.get(hero.title)}
              region={region}
            />
          )}
          {/* Rest of the items */}
          <ul
            className="list-none m-0 p-0 overflow-y-auto"
            style={{ maxHeight: "clamp(360px, 50vh, 580px)" }}
          >
            {rest.map((it) => (
              <FeedRow
                key={it.rank}
                rank={it.rank}
                title={it.title}
                url={it.url}
                cover={it.cover}
                hotValue={it.hot_value}
                consensus={consensusMap.get(it.title)}
                region={region}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function FeedHero({
  item,
  consensus,
  region,
}: {
  item: { rank: number; title: string; url: string | null; hot_value: string | null; cover: string | null };
  consensus?: number;
  region: Region;
}) {
  return (
    <a
      href={item.url ?? "#"}
      target="_blank"
      rel="noopener"
      className="block group border-b border-border"
    >
      <div className="relative h-32 overflow-hidden">
        <CoverImage
          src={item.cover}
          alt={item.title}
          hueKey={item.title}
          className="w-full h-full transition-transform duration-300 ease-smooth group-hover:scale-105"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-bg/90 via-bg/30 to-transparent" />
        <div className="absolute top-2 left-3 flex items-center gap-2">
          <span className="text-danger font-bold tabular-nums text-sm bg-bg/70 px-1.5 py-0.5 rounded-xs backdrop-blur-sm">
            #{item.rank}
          </span>
          {consensus && (
            <Badge variant="warning" className="backdrop-blur-sm">
              {consensus} {region === "intl" ? "src" : "平台"}
            </Badge>
          )}
        </div>
      </div>
      <div className="px-4 py-3">
        <h4 className="font-display text-md leading-snug font-semibold m-0 clamp-2 text-fg group-hover:text-accent2 transition-colors duration-150">
          {item.title}
        </h4>
        {item.hot_value && (
          <div className="mt-1 text-xs text-muted tabular-nums">
            {item.hot_value}
          </div>
        )}
      </div>
    </a>
  );
}

function FeedRow({
  rank,
  title,
  url,
  cover,
  hotValue,
  consensus,
  region,
}: {
  rank: number;
  title: string;
  url: string | null;
  cover: string | null;
  hotValue: string | null;
  consensus?: number;
  region: Region;
}) {
  const rankColor =
    rank === 2 ? "text-hot" : rank === 3 ? "text-warning" : "text-muted-2";

  return (
    <li className="border-b border-border last:border-b-0 hover:bg-bg-2 transition-colors duration-150">
      <a
        href={url ?? "#"}
        target="_blank"
        rel="noopener"
        className="flex items-start gap-3 px-4 py-2.5"
      >
        <span
          className={cn(
            "shrink-0 w-6 pt-0.5 text-sm font-bold tabular-nums",
            rankColor
          )}
        >
          {rank}
        </span>
        {cover && (
          <CoverImage
            src={cover}
            alt={title}
            hueKey={title}
            className="w-12 h-12 rounded-xs shrink-0"
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-sm leading-snug text-fg clamp-2 hover:text-accent2 transition-colors duration-150">
            {title}
            {consensus && (
              <span className="inline-flex items-center align-[2px] ml-1.5 px-1.5 py-px rounded-full bg-warning/[0.14] text-warning text-[10px] font-semibold tracking-wide">
                {consensus} {region === "intl" ? "src" : "平台"}
              </span>
            )}
          </div>
          {hotValue && (
            <div className="mt-0.5 text-xs text-muted tabular-nums">
              {hotValue}
            </div>
          )}
        </div>
      </a>
    </li>
  );
}

function ColumnSkeleton() {
  return (
    <div>
      <Skeleton className="h-32 w-full rounded-none" />
      <ul className="list-none m-0 p-0">
        {Array.from({ length: 4 }).map((_, i) => (
          <li key={i} className="flex items-start gap-3 px-4 py-2.5 border-b border-border last:border-b-0">
            <div className="w-6 pt-1">
              <Skeleton className="h-3 w-4" />
            </div>
            <div className="flex-1 min-w-0">
              <Skeleton className="h-3.5 w-full mb-1.5" />
              <Skeleton className="h-3.5 w-3/5" />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
