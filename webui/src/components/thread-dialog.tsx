import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { emojiFor } from "@/data/platforms";
import { cn } from "@/lib/utils";
import type {
  AggregateGroup,
  PlatformInfo,
  Region,
  Thread,
} from "@/lib/types";

interface ThreadDialogProps {
  thread: Thread | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groups: AggregateGroup[];
  platforms: PlatformInfo[];
  region: Region;
}

/**
 * Modal that shows a thread's full contents — all items (not truncated to 5),
 * with platform / rank / link. Triggered from sidebar thread nav, threads
 * section card click, etc.
 */
export function ThreadDialog({
  thread,
  open,
  onOpenChange,
  groups,
  platforms,
  region,
}: ThreadDialogProps) {
  // Build a flat lookup the same way summary_cache item_ids reference
  const allItems = flattenItems(groups);
  const items = thread
    ? (thread.item_ids
        .map((id) => allItems[id])
        .filter((it): it is AggregateGroup["items"][number] => Boolean(it)))
    : [];

  const platName = (id: string) =>
    platforms.find((p) => p.id === id)?.name ?? id;

  // Sort: lowest rank first per platform = "best representative" up top
  const sorted = [...items].sort((a, b) => a.rank - b.rank);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-3">
            <span className="text-warning text-xl leading-none">📑</span>
            <div className="flex-1 min-w-0">
              <DialogTitle className="truncate">
                {thread?.name ?? "—"}
              </DialogTitle>
            </div>
            <Badge variant="success">
              {items.length} {region === "intl" ? "items" : "条"}
            </Badge>
          </div>
          {thread?.summary && (
            <DialogDescription className="mt-2">
              {thread.summary}
            </DialogDescription>
          )}
        </DialogHeader>

        <DialogBody className="max-h-[60vh]">
          {sorted.length === 0 ? (
            <div className="text-center text-muted py-8">
              {region === "intl" ? "No items in this thread" : "本话题暂无内容"}
            </div>
          ) : (
            <ul className="list-none m-0 p-0 space-y-2">
              {sorted.map((it, i) => (
                <ItemRow
                  key={`${it.platform}-${i}`}
                  rank={it.rank}
                  platform={it.platform}
                  platName={platName(it.platform)}
                  title={it.title}
                  url={it.url}
                  hotValue={it.hot_value}
                />
              ))}
            </ul>
          )}
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}

function ItemRow({
  rank,
  platform,
  platName,
  title,
  url,
  hotValue,
}: {
  rank: number;
  platform: string;
  platName: string;
  title: string;
  url: string | null;
  hotValue: string | null;
}) {
  const rankColor =
    rank === 1
      ? "text-danger"
      : rank === 2
      ? "text-hot"
      : rank === 3
      ? "text-warning"
      : "text-muted-2";

  return (
    <li>
      <a
        href={url ?? "#"}
        target="_blank"
        rel="noopener"
        className={cn(
          "flex items-start gap-3 px-3 py-2.5 rounded-sm border border-border",
          "hover:border-border-strong hover:bg-bg-2 transition-colors duration-150"
        )}
      >
        <span className="shrink-0 text-base leading-none mt-0.5">
          {emojiFor(platform)}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-xs text-muted-2 mb-1">
            <span>{platName}</span>
            <span className={cn("font-bold tabular-nums", rankColor)}>
              #{rank}
            </span>
            {hotValue && (
              <span className="text-muted-2 tabular-nums truncate">
                · {hotValue}
              </span>
            )}
          </div>
          <div className="text-sm text-fg leading-snug hover:text-accent2 transition-colors duration-150">
            {title}
          </div>
        </div>
        <ExternalLink className="h-3.5 w-3.5 text-muted-2 shrink-0 mt-1.5" aria-hidden />
      </a>
    </li>
  );
}

function flattenItems(groups: AggregateGroup[]): AggregateGroup["items"] {
  const all: AggregateGroup["items"] = [];
  groups.forEach((g) => g.items.forEach((it) => all.push(it)));
  return all;
}
