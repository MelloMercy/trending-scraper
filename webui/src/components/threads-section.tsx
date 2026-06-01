import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { emojiFor } from "@/data/platforms";
import { cn } from "@/lib/utils";
import type {
  AggregateGroup,
  Region,
  Themes,
  Thread,
} from "@/lib/types";

interface ThreadsSectionProps {
  themes: Themes | null;
  groups: AggregateGroup[];
  loading: boolean;
  region: Region;
  /** Click handler to open the thread detail dialog */
  onThreadOpen?: (thread: Thread) => void;
}

export function ThreadsSection({ themes, groups, loading, region, onThreadOpen }: ThreadsSectionProps) {
  const title = region === "intl" ? "📑 Today's Threads" : "📑 今日话题";

  return (
    <section className="mb-8">
      <div className="flex items-center gap-3 mb-4">
        <h3 className="text-md font-semibold tracking-tight m-0 flex items-center after:content-[''] after:ml-3 after:inline-block after:w-6 after:h-px after:bg-border">
          {title}
        </h3>
        <ThreadsTag themes={themes} loading={loading} region={region} />
      </div>

      {loading ? (
        <ThreadsSkeleton />
      ) : !themes || themes.status === "disabled" ? (
        <DisabledState />
      ) : themes.status === "error" ? (
        <ErrorState error={themes.error} />
      ) : themes.threads.length === 0 ? (
        <DisabledState text="本次未生成话题（数据可能不足）" />
      ) : (
        <ThreadsGrid threads={themes.threads} groups={groups} onThreadOpen={onThreadOpen} />
      )}
    </section>
  );
}

function ThreadsTag({
  themes,
  loading,
  region,
}: {
  themes: Themes | null;
  loading: boolean;
  region: Region;
}) {
  if (loading) return null;
  if (!themes || themes.status === "disabled")
    return <Badge>未启用</Badge>;
  if (themes.status === "error")
    return <Badge variant="danger">出错</Badge>;
  // Dev info (model name) lives in the tooltip — keep the visible chip clean.
  return (
    <Badge
      className="cursor-help"
      title={themes.model ? `由 ${themes.model} 合成` : undefined}
    >
      AI · {themes.threads.length}{" "}
      {region === "intl" ? "threads" : "个话题"}
    </Badge>
  );
}

function flattenAllItems(groups: AggregateGroup[]) {
  const all: AggregateGroup["items"][number][] = [];
  groups.forEach((g) => g.items.forEach((it) => all.push(it)));
  return all;
}

function ThreadsGrid({
  threads,
  groups,
  onThreadOpen,
}: {
  threads: Themes["threads"];
  groups: AggregateGroup[];
  onThreadOpen?: (thread: Thread) => void;
}) {
  const all = flattenAllItems(groups);
  return (
    <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(340px,1fr))]">
      {threads.map((t, ti) => {
        const totalItems = t.item_ids.length;
        const truncated = totalItems > 5;
        return (
          <article
            key={ti}
            role="button"
            tabIndex={0}
            onClick={() => onThreadOpen?.(t)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onThreadOpen?.(t);
              }
            }}
            className={cn(
              "rounded-md bg-panel border border-border px-4 pt-4 pb-3",
              "transition-all duration-150 ease-smooth cursor-pointer",
              "hover:border-border-strong hover:-translate-y-px",
              "focus-visible:outline-none focus-visible:shadow-focus"
            )}
            aria-label={`Open thread: ${t.name}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <h4 className="flex-1 min-w-0 font-semibold text-base tracking-tight m-0 flex items-center gap-2 before:content-[''] before:w-1.5 before:h-1.5 before:rounded-full before:bg-primary before:shrink-0">
                {t.name}
              </h4>
              <Badge>{totalItems}</Badge>
            </div>
            {t.summary && (
              <p className="text-sm text-muted leading-snug mb-3 mt-0">
                {t.summary}
              </p>
            )}
            <ul className="list-none m-0 p-0 pt-2 border-t border-border space-y-1">
              {t.item_ids.slice(0, 5).map((id, li) => {
                const it = all[id];
                if (!it) return null;
                return (
                  <li key={li} className="flex gap-2 text-sm leading-snug">
                    <span className="text-muted-2 shrink-0">
                      {emojiFor(it.platform)}
                    </span>
                    {/* stopPropagation so deep-linking to source doesn't trigger card click */}
                    <a
                      href={it.url ?? "#"}
                      target="_blank"
                      rel="noopener"
                      onClick={(e) => e.stopPropagation()}
                      className="flex-1 min-w-0 text-fg hover:text-accent2 transition-colors duration-150 line-clamp-1"
                    >
                      {it.title}
                    </a>
                  </li>
                );
              })}
            </ul>
            {truncated && (
              <div className="mt-2 text-xs text-muted-2 text-right">
                +{totalItems - 5} <span className="text-muted-2/70">›</span>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

function ThreadsSkeleton() {
  return (
    <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(340px,1fr))]">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-md bg-panel border border-border px-4 pt-4 pb-3">
          <Skeleton className="h-5 w-1/3 mb-3" />
          <Skeleton className="h-3 w-full mb-1" />
          <Skeleton className="h-3 w-3/5 mb-3" />
          <Skeleton className="h-3 w-4/5 mb-1" />
          <Skeleton className="h-3 w-3/5 mb-1" />
        </div>
      ))}
    </div>
  );
}

function DisabledState({ text }: { text?: string } = {}) {
  return (
    <div
      className={cn(
        "rounded-md bg-panel border border-dashed border-border-strong p-6 text-center text-muted"
      )}
    >
      {text ?? (
        <>
          配置 DeepSeek API key 后启用：
          <br />
          <code className="inline-block mt-2 max-w-full overflow-x-auto bg-bg px-2 py-0.5 rounded-xs text-accent2 text-xs whitespace-nowrap">
            curl -X POST -H "Content-Type: application/json" -d
            {' \''}
            {"{"}"deepseek_api_key":"sk-..."{"}"}
            {'\''} http://localhost:11001/api/config
          </code>
        </>
      )}
    </div>
  );
}

function ErrorState({ error }: { error: string | null }) {
  return (
    <div className="rounded-md bg-panel border border-dashed border-danger p-6 text-center text-danger text-sm">
      {error ?? "未知错误"}
    </div>
  );
}
