import { CoverImage } from "@/components/cover-image";
import { Skeleton } from "@/components/ui/skeleton";
import { SourceChip } from "@/components/ui/source-chip";
import { emojiFor } from "@/data/platforms";
import { cn } from "@/lib/utils";
import type { BigStory, PlatformInfo, Region } from "@/lib/types";

interface FeaturedStoryProps {
  data: BigStory | null;
  loading: boolean;
  region: Region;
  platforms: PlatformInfo[];
}

/**
 * Magazine-style hero. Two variants by cover availability:
 *   - hasCover: full-bleed image with dark gradient for legibility (340px+)
 *   - noCover : compact editorial card with branded radial gradient and a giant
 *               serif glyph as visual anchor (240px). Skips the dark overlay
 *               that would otherwise drown the placeholder.
 */
export function FeaturedStory({ data, loading, region, platforms }: FeaturedStoryProps) {
  if (loading) return <FeaturedSkeleton />;
  if (!data) return null;

  const rep = data.representative;
  const isLLM = data.source === "llm";
  const cover = rep.cover;
  const hasCover = Boolean(cover);
  const platName = (id: string) =>
    platforms.find((p) => p.id === id)?.name ?? id;

  const label = isLLM
    ? region === "intl"
      ? "TOP THREAD · AI-CURATED"
      : "重磅话题 · AI 精选"
    : region === "intl"
    ? `BIG STORY · ${data.n_platforms} SOURCES`
    : `今日大故事 · ${data.n_platforms} 平台共识`;

  return (
    <article
      className={cn(
        "relative overflow-hidden rounded-lg border border-border-strong shadow-card flex flex-col",
        hasCover ? "min-h-[340px]" : "min-h-[240px]"
      )}
    >
      {hasCover ? (
        <>
          <CoverImage
            src={cover}
            alt={rep.title}
            hueKey={rep.title}
            className="absolute inset-0 w-full h-full"
          />
          {/* gradient overlay — legibility over photo */}
          <div className="absolute inset-0 bg-gradient-to-t from-bg/95 via-bg/65 to-bg/30" />
        </>
      ) : (
        <NoCoverBackground hueKey={rep.title} region={region} />
      )}

      {/* left accent stripe — region-aware */}
      <div
        className={cn(
          "absolute left-0 top-0 bottom-0 w-1",
          region === "cn"
            ? "bg-gradient-to-b from-hot to-warning"
            : "bg-gradient-to-b from-primary to-accent2"
        )}
      />

      <div className={cn("relative p-7 sm:p-9", hasCover && "mt-auto")}>
        <div className="inline-flex items-center gap-2 mb-3 px-3 py-1 rounded-full bg-warning/[0.16] text-warning text-xs font-bold uppercase tracking-[0.12em] backdrop-blur-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-warning" />
          {label}
        </div>

        <h2 className={cn(
          "font-display leading-[1.1] font-bold text-fg-strong m-0 max-w-[42ch]",
          hasCover ? "text-3xl sm:text-[40px] display-shadow" : "text-3xl sm:text-[36px]"
        )}>
          <a
            href={rep.url ?? "#"}
            target="_blank"
            rel="noopener"
            className="text-fg-strong hover:text-accent2 transition-colors duration-150 ease-smooth"
          >
            {rep.title}
          </a>
        </h2>

        {isLLM && data.thread_name && (
          <div className="flex flex-wrap items-baseline gap-2 mt-4 text-sm">
            <span className="bg-primary/[0.20] text-primary-strong px-2.5 py-0.5 rounded-full text-xs font-semibold backdrop-blur-sm">
              {data.thread_name}
            </span>
            {data.thread_summary && (
              <span className="text-fg/80 max-w-[64ch]">{data.thread_summary}</span>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-2 mt-5">
          {data.items.slice(0, 6).map((it, i) => (
            <SourceChip
              key={`${it.platform}-${i}`}
              href={it.url ?? "#"}
              target="_blank"
              rel="noopener"
              title={it.title}
              emoji={emojiFor(it.platform)}
              label={platName(it.platform)}
              rank={it.rank}
              className="backdrop-blur-sm bg-bg/40"
            />
          ))}
          {data.items.length > 6 && (
            <span className="inline-flex items-center px-3 py-0.5 rounded-full text-xs text-muted">
              +{data.items.length - 6}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}

/**
 * Editorial fallback when no cover image is available.
 * - Deterministic radial gradient hue derived from title (consistent per story)
 * - Giant low-opacity serif quote glyph in the corner as a visual anchor
 * - Base layer uses panel tokens so it reads as "card" not "broken image"
 */
function NoCoverBackground({ hueKey, region }: { hueKey: string; region: Region }) {
  const hue = hashHue(hueKey);
  // Region-aware corner tint — cn warm, intl cool
  const cornerHue = region === "cn" ? hue : (hue + 180) % 360;
  return (
    <div className="absolute inset-0 overflow-hidden bg-panel">
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: `
            radial-gradient(ellipse 60% 70% at 92% 18%, hsl(${cornerHue} 55% 32% / 0.55), transparent 60%),
            linear-gradient(135deg, hsl(var(--panel)) 0%, hsl(var(--panel-2)) 100%)
          `,
        }}
      />
      <div
        aria-hidden
        className="absolute right-6 top-2 font-display text-[180px] leading-none text-fg-strong/[0.045] select-none pointer-events-none"
      >
        “
      </div>
    </div>
  );
}

function hashHue(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h) % 360;
}

function FeaturedSkeleton() {
  return (
    <article className="relative overflow-hidden rounded-lg border border-border-strong shadow-card min-h-[340px] bg-panel-2 flex flex-col">
      <div className="mt-auto p-7 sm:p-9">
        <Skeleton className="h-5 w-44 mb-4 rounded-full" />
        <Skeleton className="h-10 w-3/4 mb-2" />
        <Skeleton className="h-10 w-1/2 mb-5" />
        <div className="flex gap-2">
          <Skeleton className="h-5 w-24 rounded-full" />
          <Skeleton className="h-5 w-28 rounded-full" />
          <Skeleton className="h-5 w-20 rounded-full" />
        </div>
      </div>
    </article>
  );
}
