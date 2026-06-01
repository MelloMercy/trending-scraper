import { CoverImage } from "@/components/cover-image";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { emojiFor } from "@/data/platforms";
import type { AggregateGroup, PlatformInfo, Region } from "@/lib/types";

interface SecondaryStoriesProps {
  groups: AggregateGroup[];
  bigStoryThreadIdx: number | undefined; // skip this thread's items if same
  platforms: PlatformInfo[];
  region: Region;
  loading: boolean;
  startAt?: number;
  count?: number;
}

/**
 * Two-column row of cover-led secondary stories — picked from the next top
 * cross-platform groups after the featured one.
 */
export function SecondaryStories({
  groups,
  bigStoryThreadIdx: _bigStoryThreadIdx,
  platforms,
  region,
  loading,
  startAt = 0,
  count = 2,
}: SecondaryStoriesProps) {
  if (loading) {
    return (
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 mt-4">
        {Array.from({ length: count }).map((_, i) => (
          <Skeleton key={i} className="h-44 rounded-md" />
        ))}
      </div>
    );
  }

  const picks = pickSecondary(groups, startAt, count);
  if (picks.length === 0) return null;

  const platName = (id: string) =>
    platforms.find((p) => p.id === id)?.name ?? id;

  return (
    <div className="grid gap-4 grid-cols-1 md:grid-cols-2 mt-4">
      {picks.map((g, i) => {
        const rep = g.representative;
        return (
          <article
            key={i}
            className="group relative overflow-hidden rounded-md border border-border bg-panel hover:border-border-strong transition-colors duration-150 ease-smooth flex"
          >
            <CoverImage
              src={rep.cover}
              alt={rep.title}
              hueKey={rep.title}
              className="w-32 h-full shrink-0 min-h-[140px]"
            />
            <div className="flex-1 min-w-0 p-4 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-xs text-muted-2">
                <span>{emojiFor(rep.platform)}</span>
                <span>{platName(rep.platform)}</span>
                <span className="font-bold text-warning">#{rep.rank}</span>
                {g.n_platforms > 1 && (
                  <Badge variant="warning" className="ml-auto">
                    {g.n_platforms} {region === "intl" ? "src" : "平台"}
                  </Badge>
                )}
              </div>
              <h3 className="font-display text-md sm:text-lg leading-snug font-semibold m-0 clamp-2">
                <a
                  href={rep.url ?? "#"}
                  target="_blank"
                  rel="noopener"
                  className="text-fg hover:text-accent2 transition-colors duration-150"
                >
                  {rep.title}
                </a>
              </h3>
              {rep.hot_value && (
                <div className="mt-auto text-xs text-muted tabular-nums">
                  {rep.hot_value}
                </div>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

/**
 * Prefer groups with cover images and meaningful platform diversity.
 */
function pickSecondary(groups: AggregateGroup[], startAt: number, count: number) {
  const filtered = groups
    .slice(startAt)
    .filter((g) => g.representative.title && g.representative.title.length > 4);
  // Sort by: has-cover desc, n_platforms desc, original score order otherwise stable.
  const sorted = filtered
    .map((g, i) => ({
      g,
      i,
      hasCover: Boolean(g.representative.cover),
      diversity: g.n_platforms,
    }))
    .sort((a, b) => {
      if (a.hasCover !== b.hasCover) return a.hasCover ? -1 : 1;
      if (a.diversity !== b.diversity) return b.diversity - a.diversity;
      return a.i - b.i;
    });
  return sorted.slice(0, count).map((x) => x.g);
}
