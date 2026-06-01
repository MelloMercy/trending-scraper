import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardMeta } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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
  PlatformInfo,
  PlatformTrendingResponse,
  Region,
} from "@/lib/types";

interface PlatformCardProps {
  platform: PlatformInfo;
  data: PlatformTrendingResponse | null;
  history: string[];
  region: Region;
  groups: AggregateGroup[];
  onDateChange: (platformId: string, payload: PlatformTrendingResponse) => void;
}

export function PlatformCard({
  platform,
  data,
  history,
  region,
  groups,
  onDateChange,
}: PlatformCardProps) {
  const today = todayISO();
  const items = data?.items ?? [];
  const isStale = data?.snapshot_date && data.snapshot_date !== today;

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
      /* swallow — UI stays on previous data */
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <span className="text-base">{emojiFor(platform.id)}</span>
          <span>{platform.name}</span>
          <Badge>{items.length}</Badge>
        </CardTitle>

        <CardMeta className={cn(isStale && "text-hot")}>
          {history.length > 0 && data?.snapshot_date ? (
            <Select
              value={data.snapshot_date}
              onValueChange={handleDateChange}
            >
              <SelectTrigger className="min-w-[8rem]">
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
        </CardMeta>
      </CardHeader>

      <div className="overflow-y-auto" style={{ maxHeight: "clamp(420px, 60vh, 720px)" }}>
        {!data ? (
          <ListSkeleton />
        ) : items.length === 0 ? (
          <EmptyState
            title={region === "intl" ? "No data yet" : "暂无数据"}
            hint={
              region === "intl"
                ? "Click ⟳ Refresh to fetch"
                : "点击右上角「刷新」抓取一次"
            }
          />
        ) : (
          <ul className="list-none m-0 p-0">
            {items.map((it) => {
              const consensus = consensusMap.get(it.title);
              return (
                <li
                  key={it.rank}
                  className="flex gap-3 items-start px-4 py-3 border-b border-border last:border-b-0 hover:bg-bg-2 transition-colors duration-150"
                >
                  <RankBadge rank={it.rank} />
                  <div className="flex-1 min-w-0">
                    <a
                      href={it.url ?? "#"}
                      target="_blank"
                      rel="noopener"
                      className="block clamp-2 text-base leading-snug text-fg hover:text-accent2 transition-colors duration-150"
                    >
                      {it.title}
                    </a>
                    {consensus && (
                      <ConsensusBadge n={consensus} region={region} />
                    )}
                    {it.hot_value && (
                      <div className="mt-1 text-xs text-muted tabular-nums">
                        {it.hot_value}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Card>
  );
}

function RankBadge({ rank }: { rank: number }) {
  const color =
    rank === 1
      ? "text-danger"
      : rank === 2
      ? "text-hot"
      : rank === 3
      ? "text-warning"
      : "text-muted-2";
  return (
    <div
      className={cn(
        "shrink-0 w-7 pt-0.5 text-sm font-bold tabular-nums",
        color
      )}
    >
      {rank}
    </div>
  );
}

function ConsensusBadge({ n, region }: { n: number; region: Region }) {
  return (
    <span className="inline-flex items-center ml-2 align-[2px] px-1.5 py-px rounded-full bg-warning/[0.14] text-warning text-[10px] font-semibold tracking-wide">
      {n} {region === "intl" ? "src" : "平台"}
    </span>
  );
}

function ListSkeleton() {
  return (
    <ul className="list-none m-0 p-0">
      {Array.from({ length: 6 }).map((_, i) => (
        <li
          key={i}
          className="flex gap-3 items-start px-4 py-3 border-b border-border last:border-b-0"
        >
          <div className="w-7 pt-1">
            <Skeleton className="h-3.5 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <Skeleton className="h-3.5 w-full mb-1.5" />
            <Skeleton className="h-3.5 w-3/5" />
          </div>
        </li>
      ))}
    </ul>
  );
}
