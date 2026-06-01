import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Toaster, toast } from "sonner";
import { Activity, RadioTower, RefreshCw, Sparkles } from "lucide-react";

import { Sidebar } from "@/components/sidebar";
import { TrendsMarquee } from "@/components/trends-marquee";
import { FeaturedStory } from "@/components/featured-story";
import { SecondaryStories } from "@/components/secondary-stories";
import { BentoFeed } from "@/components/bento-feed";
import { TimelineView } from "@/components/timeline-view";
import { ThreadsSection } from "@/components/threads-section";
import { BriefView } from "@/components/brief-view";
import { CuratedView } from "@/components/curated-view";
import { PromptEditorView } from "@/components/prompt-editor-view";
import { ThreadDialog } from "@/components/thread-dialog";

import { useRegion } from "@/hooks/use-region";
import { useView } from "@/hooks/use-view";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard";
import { useTrendingData } from "@/hooks/use-trending-data";
import { useBrief } from "@/hooks/use-brief";
import { useCurated } from "@/hooks/use-curated";

import { api } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { Thread } from "@/lib/types";

const VIEW_LABEL: Record<string, { zh: string; en: string }> = {
  brief:    { zh: "简报",   en: "Brief" },
  curated:  { zh: "高信号", en: "Curated" },
  prompts:  { zh: "Prompt", en: "Prompts" },
  grid:     { zh: "杂志",   en: "Magazine" },
  timeline: { zh: "时间流", en: "Timeline" },
};

export default function App() {
  const [region, setRegion] = useRegion();
  const [view, setView] = useView();
  const [refreshing, setRefreshing] = useState(false);

  const data = useTrendingData(region);
  const briefState = useBrief(view === "brief");
  const curatedState = useCurated(view === "curated");

  // Thread dialog state — opened from sidebar nav, threads section card click, etc.
  const [openThread, setOpenThread] = useState<Thread | null>(null);

  const groups = useMemo(
    () => data.aggregate?.aggregate.groups ?? [],
    [data.aggregate]
  );
  const bigStory = data.aggregate?.aggregate.big_story ?? null;
  const themes = data.aggregate?.themes ?? null;
  const bigStoryThreadIdx = bigStory?.thread_idx;
  const platformCount = data.platforms.length;
  const threadCount = themes?.threads?.length ?? 0;

  // ---- Actions ----
  const refresh = useCallback(async () => {
    if (refreshing) return;
    setRefreshing(true);
    const t = region === "intl"
      ? { ok: (o: number, n: number) => `Fetched ${o}/${n} sources`, fail: (m: string) => `Fetch failed: ${m}` }
      : { ok: (o: number, n: number) => `已抓取 ${o}/${n} 个平台`,    fail: (m: string) => `抓取失败：${m}` };
    try {
      const result = await api.refresh(region);
      const ok = result.results.filter((r) => r.status === "ok").length;
      const total = result.results.length;
      await data.reload();
      (ok === total ? toast.success : toast.warning)(t.ok(ok, total));
    } catch (e) {
      toast.error(t.fail(e instanceof Error ? e.message : String(e)));
    } finally {
      setRefreshing(false);
    }
  }, [refreshing, region, data]);

  // ---- Keyboard shortcuts ----
  useKeyboardShortcuts(
    useMemo(
      () => ({
        r: refresh,
        b: () => setView("brief"),
        c: () => setView("curated"),
        g: () => setView("grid"),
        p: () => setView("prompts"),
        t: () => setView("timeline"),
        "1": () => setRegion("cn"),
        "2": () => setRegion("intl"),
      }),
      [refresh, setView, setRegion]
    )
  );

  // Surface load errors
  useEffect(() => {
    if (data.error) {
      toast.error(region === "intl" ? `Load failed: ${data.error}` : `加载失败：${data.error}`);
    }
  }, [data.error, region]);

  // Thread click → open ThreadDialog. Sidebar passes index; we resolve to Thread.
  const onThreadClick = useCallback(
    (idx: number) => {
      const t = themes?.threads?.[idx];
      if (t) setOpenThread(t);
    },
    [themes]
  );

  const lang = region === "intl" ? "en" : "zh";
  const viewLabel = VIEW_LABEL[view]?.[lang] ?? view;
  const regionLabel = lang === "en" ? "International" : "国内";

  return (
    <div className="min-h-screen flex flex-col bg-bg text-fg">
      {/* Top bar — brand · context | last-updated + refresh */}
      <header className="sticky top-0 z-10 flex items-center justify-between gap-4 px-5 sm:px-6 py-3 h-[var(--header-h)] border-b border-border bg-bg/90 backdrop-blur-xl">
        {/* Left: brand + current view context */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-sm grid place-items-center bg-gradient-to-br from-warning via-danger to-primary text-bg shadow-[0_0_28px_hsl(var(--primary)/0.20)] shrink-0">
            <RadioTower className="h-4 w-4" aria-hidden />
          </div>
          <h1 className="text-lg font-bold m-0 flex flex-col leading-tight shrink-0">
            <span>{lang === "en" ? "Daily Trending" : "每日热点"}</span>
            <span className="text-[11px] font-medium text-muted-2 hidden sm:inline">
              {viewLabel} · {regionLabel}
            </span>
          </h1>
        </div>

        {/* Right: last-updated + refresh icon */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="hidden lg:flex items-center gap-2">
            <HeaderPill icon={<Activity className="h-3.5 w-3.5" />} label={lang === "en" ? "Threads" : "话题"} value={threadCount || "—"} />
            <HeaderPill icon={<Sparkles className="h-3.5 w-3.5" />} label={lang === "en" ? "Sources" : "来源"} value={platformCount || "—"} />
          </div>
          <span className="text-xs text-muted-2 tabular-nums hidden sm:inline px-2">
            {data.lastFetchedAt
              ? lang === "en"
                ? `Updated ${formatRelativeTime(data.lastFetchedAt, "en")}`
                : `更新于 ${formatRelativeTime(data.lastFetchedAt, "zh")}`
              : lang === "en" ? "No data" : "暂无数据"}
          </span>
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing}
            className={cn(
              "inline-flex items-center justify-center w-8 h-8 rounded-sm",
              "text-muted-2 hover:text-fg hover:bg-panel-2 border border-border hover:border-border-strong transition-colors",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "focus-visible:outline-none"
            )}
            aria-label={lang === "en" ? "Refresh (R)" : "刷新 (R)"}
            title={lang === "en" ? "Refresh (R)" : "刷新 (R)"}
          >
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
          </button>
        </div>
      </header>

      {/* Trends marquee — sticky just under top bar */}
      <TrendsMarquee
        groups={groups}
        platforms={data.platforms}
        loading={data.loading}
        region={region}
      />

      {/* Sidebar + main grid */}
      <div className="flex-1 grid grid-cols-1 lg:[grid-template-columns:260px_1fr]">
        <Sidebar
          region={region}
          onRegionChange={setRegion}
          view={view}
          onViewChange={setView}
          onRefresh={refresh}
          refreshing={refreshing}
          themes={themes}
          onThreadClick={onThreadClick}
        />

        <main className="min-w-0 px-5 py-6 sm:px-6 lg:px-8 lg:py-8 max-w-[1320px] mx-auto w-full">
          {view === "brief" ? (
            <BriefView
              brief={briefState.brief}
              loading={briefState.loading}
              error={briefState.error}
              platforms={data.platforms}
              onReload={briefState.reload}
            />
          ) : view === "curated" ? (
            <CuratedView
              curated={curatedState.curated}
              loading={curatedState.loading}
              error={curatedState.error}
              onReload={curatedState.reload}
            />
          ) : view === "prompts" ? (
            <PromptEditorView />
          ) : view === "timeline" ? (
            <TimelineView
              groups={groups}
              region={region}
              platforms={data.platforms}
            />
          ) : (
            <>
              {/* Featured Story (cover-led hero) */}
              <FeaturedStory
                data={bigStory}
                loading={data.loading && !bigStory}
                region={region}
                platforms={data.platforms}
              />

              {/* Secondary stories — 2 cover cards */}
              <SecondaryStories
                groups={groups}
                bigStoryThreadIdx={bigStoryThreadIdx}
                platforms={data.platforms}
                region={region}
                loading={data.loading && groups.length === 0}
                startAt={1}
                count={2}
              />

              {/* Today's threads — inline, click to open dialog with full items */}
              <div className="mt-10">
                <ThreadsSection
                  themes={themes}
                  groups={groups}
                  loading={data.loading && !themes}
                  region={region}
                  onThreadOpen={setOpenThread}
                />
              </div>

              {/* Platform feed — bento style */}
              <section className="mt-6">
                <div className="flex items-baseline gap-3 mb-4">
                  <h2 className="font-display text-lg font-semibold tracking-tight m-0">
                    {region === "intl" ? "Platform Feeds" : "各平台热门"}
                  </h2>
                  <span className="flex-1 h-px bg-border" />
                  <span className="text-xs text-muted-2 tabular-nums">
                    {data.perPlatform.length} {region === "intl" ? "sources" : "个来源"}
                  </span>
                </div>

                <BentoFeed
                  perPlatform={
                    data.perPlatform.length > 0
                      ? data.perPlatform
                      : data.platforms.map((p) => ({
                          platform: p,
                          latest: null,
                          history: [],
                        }))
                  }
                  groups={groups}
                  region={region}
                  onDateChange={data.setPerPlatformForDate}
                />
              </section>
            </>
          )}
        </main>
      </div>

      {/* Thread detail dialog — full thread items list (no truncation) */}
      <ThreadDialog
        thread={openThread}
        open={openThread !== null}
        onOpenChange={(o) => !o && setOpenThread(null)}
        groups={groups}
        platforms={data.platforms}
        region={region}
      />

      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          classNames: {
            toast:
              "!bg-panel-2 !border !border-border-strong !text-fg !shadow-elevated",
            title: "!text-sm !font-medium",
            success: "!border-success",
            warning: "!border-warning",
            error: "!border-danger !text-danger",
          },
        }}
      />
    </div>
  );
}

function HeaderPill({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="inline-flex items-center gap-2 h-8 px-2.5 rounded-sm border border-border bg-panel/50 text-xs text-muted-2">
      <span className="text-primary" aria-hidden>{icon}</span>
      <span>{label}</span>
      <span className="text-fg font-semibold tabular-nums">{value}</span>
    </div>
  );
}
