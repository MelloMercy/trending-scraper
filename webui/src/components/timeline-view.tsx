import { SourceChip } from "@/components/ui/source-chip";
import { EmptyState } from "@/components/empty-state";
import { emojiFor } from "@/data/platforms";
import type { AggregateGroup, PlatformInfo, Region } from "@/lib/types";

interface TimelineViewProps {
  groups: AggregateGroup[];
  region: Region;
  platforms: PlatformInfo[];
}

export function TimelineView({ groups, region, platforms }: TimelineViewProps) {
  if (!groups.length) {
    return (
      <EmptyState
        title={region === "intl" ? "No data" : "暂无数据"}
        className="max-w-[820px] mx-auto bg-panel border border-border rounded-md shadow-card"
      />
    );
  }

  const nameFor = (id: string) =>
    platforms.find((p) => p.id === id)?.name ?? id;

  return (
    <div className="max-w-[820px] mx-auto bg-panel border border-border rounded-md shadow-card overflow-hidden">
      {groups.map((g, i) => {
        const rep = g.representative;
        return (
          <div
            key={i}
            className="flex gap-3 px-4 py-3 border-b border-border last:border-b-0 hover:bg-bg-2 transition-colors duration-150"
          >
            <div className="shrink-0 w-6 h-6 mt-0.5 flex items-center justify-center text-xs font-bold tabular-nums text-muted border border-border-strong rounded-xs">
              {i + 1}
            </div>
            <div className="flex-1 min-w-0">
              <a
                href={rep.url ?? "#"}
                target="_blank"
                rel="noopener"
                className="block clamp-2 text-md leading-snug text-fg hover:text-accent2 transition-colors duration-150"
              >
                {rep.title}
              </a>
              <div className="flex flex-wrap gap-2 mt-2">
                {g.items.map((it, ci) => (
                  <SourceChip
                    key={ci}
                    href={it.url ?? "#"}
                    target="_blank"
                    rel="noopener"
                    title={it.title}
                    emoji={emojiFor(it.platform)}
                    label={nameFor(it.platform)}
                    rank={it.rank}
                  />
                ))}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
