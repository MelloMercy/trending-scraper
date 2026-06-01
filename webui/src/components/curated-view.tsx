import {
  AlertTriangle,
  ArrowUpRight,
  Database,
  ExternalLink,
  Mic2,
  Newspaper,
  RefreshCw,
  Rss,
  Sparkles,
  Zap,
} from "lucide-react";
import { useMemo } from "react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatRelativeTime } from "@/lib/utils";
import type {
  CuratedBlog,
  CuratedBuilder,
  CuratedPodcast,
  CuratedResponse,
  CuratedTweet,
} from "@/lib/types";

interface CuratedViewProps {
  curated: CuratedResponse | null;
  loading: boolean;
  error: string | null;
  onReload: (force?: boolean) => Promise<void>;
}

export function CuratedView({ curated, loading, error, onReload }: CuratedViewProps) {
  const signalMix = useMemo(() => buildSignalMix(curated), [curated]);

  if (loading && !curated) return <CuratedSkeleton />;
  if (error || !curated) {
    return <EmptyState title="高信号源加载失败" hint={error ?? "未知错误"} />;
  }

  return (
    <div className="max-w-[1120px] mx-auto">
      <header className="signal-surface rounded-md border border-border-strong shadow-elevated overflow-hidden mb-6">
        <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-warning text-xs font-bold uppercase mb-3">
              <Zap className="h-3.5 w-3.5" aria-hidden />
              Signal cockpit
            </div>
            <h1 className="font-display text-3xl font-bold m-0 leading-tight">
              高信号源
            </h1>
            <p className="text-sm text-muted leading-relaxed mt-3 mb-0 max-w-[70ch]">
              {curated.source.name} · {curated.stats.sources} sources · {curated.source.x_generated_at ? formatRelativeTime(curated.source.x_generated_at, "zh") : "刚刚"}
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <SignalChip icon={<Database className="h-3.5 w-3.5" />} label={`${curated.stats.sources} sources`} />
              <SignalChip icon={<Sparkles className="h-3.5 w-3.5" />} label={`${curated.stats.tweets} builder posts`} />
              <SignalChip icon={<Mic2 className="h-3.5 w-3.5" />} label={`${curated.stats.podcasts} podcasts`} />
              <SignalChip icon={<Rss className="h-3.5 w-3.5" />} label={`${curated.stats.blogs} blogs / RSS`} />
            </div>
          </div>

          <div className="rounded-md border border-border bg-bg/30 p-4">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div className="text-sm font-semibold">Signal radar</div>
              <div className="flex items-center gap-2">
                {curated.status === "partial" && <Badge variant="warning">partial</Badge>}
                <Button variant="outline" size="sm" onClick={() => void onReload(true)} disabled={loading}>
                  <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} aria-hidden />
                  刷新
                </Button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Stat label="Builders" value={curated.stats.builders} accent="primary" />
              <Stat label="X posts" value={curated.stats.tweets} accent="warning" />
              <Stat label="Podcasts" value={curated.stats.podcasts} accent="success" />
              <Stat label="Blogs" value={curated.stats.blogs} accent="hot" />
            </div>
          </div>
        </div>
      </header>

      {curated.errors && curated.errors.length > 0 && (
        <div className="mb-6 rounded-md border border-warning/50 bg-warning/[0.08] p-3 text-xs text-fg">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" aria-hidden />
            <div className="space-y-1 min-w-0">
              {curated.errors.slice(0, 3).map((err, i) => (
                <div key={i} className="break-words">{err}</div>
              ))}
            </div>
          </div>
        </div>
      )}

      {signalMix.length > 0 && (
        <section className="mb-6 glass-panel rounded-md p-3">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {signalMix.slice(0, 4).map((item) => (
              <div key={item.label} className="rounded-sm bg-bg/30 border border-border px-3 py-2">
                <div className="text-[11px] text-muted-2">{item.label}</div>
                <div className="mt-1 flex items-baseline justify-between gap-3">
                  <span className="text-sm text-fg font-semibold">{item.kind}</span>
                  <span className="text-lg font-bold tabular-nums text-primary">{item.count}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.12fr)_minmax(340px,0.88fr)] items-start">
        <section className="space-y-3">
          <SectionTitle icon={<Sparkles className="h-4 w-4" aria-hidden />} title="X / Builder Posts" count={curated.builders.length} />
          <div className="grid gap-3">
            {curated.builders.map((builder) => (
              <BuilderCard key={builder.handle ?? builder.name} builder={builder} />
            ))}
            {curated.builders.length === 0 && <EmptyState title="今天暂无 builder 动态" hint="上游 feed 没有新 X 内容" />}
          </div>
        </section>

        <div className="space-y-6">
          <ContentLane
            icon={<Mic2 className="h-4 w-4" aria-hidden />}
            title="Podcasts"
            count={curated.podcasts.length}
            empty={<EmptyState title="今天暂无播客更新" hint="配置的播客源没有新内容" />}
          >
            {curated.podcasts.slice(0, 8).map((podcast) => (
              <PodcastCard key={podcast.url ?? podcast.title} podcast={podcast} />
            ))}
          </ContentLane>

          <ContentLane
            icon={<Rss className="h-4 w-4" aria-hidden />}
            title="Blogs / RSS"
            count={curated.blogs.length}
            empty={<EmptyState title="今天暂无博客/RSS 更新" hint="配置的高信号源没有新文章" />}
          >
            {curated.blogs.slice(0, 10).map((blog) => (
              <BlogCard key={blog.url ?? blog.title} blog={blog} />
            ))}
          </ContentLane>
        </div>
      </div>
    </div>
  );
}

function SignalChip({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border bg-bg/40 px-3 py-1 text-xs text-fg">
      <span className="text-primary" aria-hidden>{icon}</span>
      {label}
    </span>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent: "primary" | "warning" | "success" | "hot";
}) {
  const color = {
    primary: "text-primary",
    warning: "text-warning",
    success: "text-success",
    hot: "text-hot",
  }[accent];
  return (
    <div className="rounded-sm border border-border bg-panel/60 p-3">
      <div className="text-xs text-muted-2">{label}</div>
      <div className={cn("font-display text-2xl font-semibold tabular-nums", color)}>{value}</div>
    </div>
  );
}

function SectionTitle({
  title,
  count,
  icon,
}: {
  title: string;
  count: number;
  icon?: ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-primary">{icon}</span>
      <h2 className="font-display text-lg font-semibold m-0">{title}</h2>
      <Badge>{count}</Badge>
      <span className="flex-1 h-px bg-border" />
    </div>
  );
}

function ContentLane({
  icon,
  title,
  count,
  children,
  empty,
}: {
  icon: ReactNode;
  title: string;
  count: number;
  children: ReactNode;
  empty: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <SectionTitle icon={icon} title={title} count={count} />
      <div className="grid gap-3">
        {count > 0 ? children : empty}
      </div>
    </section>
  );
}

function BuilderCard({ builder }: { builder: CuratedBuilder }) {
  return (
    <article className="glass-panel rounded-md p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h3 className="font-display text-lg font-semibold m-0 truncate">{builder.name}</h3>
          {builder.handle && <div className="text-xs text-muted-2">{builder.handle} on X</div>}
        </div>
        <Badge variant="primary">{builder.tweets.length}</Badge>
      </div>
      <div className="grid gap-2">
        {builder.tweets.slice(0, 3).map((tweet) => (
          <TweetRow key={tweet.id} tweet={tweet} />
        ))}
      </div>
    </article>
  );
}

function TweetRow({ tweet }: { tweet: CuratedTweet }) {
  return (
    <a
      href={tweet.url ?? "#"}
      target="_blank"
      rel="noopener"
      className="group block rounded-sm bg-bg/35 border border-border px-3 py-2.5 text-sm text-fg hover:border-border-strong hover:bg-panel-2 transition-colors"
    >
      <p className="m-0 leading-snug clamp-3">{decodeEntities(tweet.text)}</p>
      <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-2 tabular-nums">
        <span>{tweet.likes} likes</span>
        <span>{tweet.retweets} reposts</span>
        {tweet.is_quote && <span>quote</span>}
        <ArrowUpRight className="ml-auto h-3.5 w-3.5 text-muted-2 group-hover:text-primary" aria-hidden />
      </div>
    </a>
  );
}

function PodcastCard({ podcast }: { podcast: CuratedPodcast }) {
  return (
    <ContentCard
      title={podcast.title}
      source={podcast.name}
      url={podcast.url}
      meta={podcast.published_at}
      body={podcast.transcript_preview}
      footer={podcast.source_kind === "follow-builders-transcript"
        ? `${podcast.transcript_length.toLocaleString()} chars transcript`
        : `${podcast.transcript_length.toLocaleString()} chars RSS preview`}
      category={podcast.category}
      tags={podcast.tags}
      icon={<Mic2 className="h-4 w-4" aria-hidden />}
    />
  );
}

function BlogCard({ blog }: { blog: CuratedBlog }) {
  return (
    <ContentCard
      title={blog.title}
      source={blog.name}
      url={blog.url}
      meta={blog.published_at}
      body={blog.content_preview}
      footer={`${blog.content_length.toLocaleString()} chars article`}
      category={blog.category}
      tags={blog.tags}
      icon={<Newspaper className="h-4 w-4" aria-hidden />}
    />
  );
}

function ContentCard({
  title,
  source,
  url,
  meta,
  body,
  footer,
  category,
  tags,
  icon,
}: {
  title: string;
  source: string;
  url: string | null;
  meta: string | null;
  body: string;
  footer: string;
  category?: string;
  tags?: string[];
  icon: ReactNode;
}) {
  return (
    <article className="glass-panel rounded-md p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-muted-2 mb-1 flex items-center gap-1.5">
            <span className="text-primary">{icon}</span>
            <span>{source}{meta ? ` · ${formatDate(meta)}` : ""}</span>
          </div>
          <h3 className="font-display text-md font-semibold m-0 leading-snug">{decodeEntities(title)}</h3>
          {(category || (tags && tags.length > 0)) && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {category && <Badge>{category}</Badge>}
              {(tags ?? []).slice(0, 3).map((tag) => (
                <Badge key={tag}>{tag}</Badge>
              ))}
            </div>
          )}
        </div>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener"
            className="shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-sm text-muted-2 hover:text-fg hover:bg-panel-2 border border-transparent hover:border-border"
            aria-label="Open source"
            title="Open source"
          >
            <ExternalLink className="h-4 w-4" aria-hidden />
          </a>
        )}
      </div>
      {body && <p className="text-sm text-muted leading-relaxed mt-3 mb-0 clamp-3">{decodeEntities(body)}</p>}
      <div className="mt-3 pt-3 border-t border-border text-xs text-muted-2">{footer}</div>
    </article>
  );
}

function CuratedSkeleton() {
  return (
    <div className="max-w-[1120px] mx-auto">
      <Skeleton className="h-64 mb-6 rounded-md" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.12fr)_minmax(340px,0.88fr)]">
        <div>
          <Skeleton className="h-5 w-44 mb-3" />
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-md mb-3" />
          ))}
        </div>
        <div>
          <Skeleton className="h-5 w-32 mb-3" />
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-md mb-3" />
          ))}
        </div>
      </div>
    </div>
  );
}

function buildSignalMix(curated: CuratedResponse | null): Array<{ label: string; kind: string; count: number }> {
  if (!curated) return [];
  const counts = new Map<string, number>();
  for (const item of [...curated.blogs, ...curated.podcasts]) {
    const key = item.category || "source";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, kind: label.split("-").join(" "), count }))
    .sort((a, b) => b.count - a.count);
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    return formatRelativeTime(parsed.toISOString(), "zh");
  }
  return value;
}

function decodeEntities(text: string): string {
  return text
    .replaceAll("&apos;", "'")
    .replaceAll("&#39;", "'")
    .replaceAll("&quot;", "\"")
    .replaceAll("&amp;", "&")
    .replaceAll("&gt;", ">")
    .replaceAll("&lt;", "<");
}
