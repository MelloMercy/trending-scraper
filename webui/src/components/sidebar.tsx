import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";
import type { Region, Themes, View } from "@/lib/types";

interface SidebarProps {
  region: Region;
  onRegionChange: (r: Region) => void;
  view: View;
  onViewChange: (v: View) => void;
  onRefresh: () => void;
  refreshing: boolean;
  themes: Themes | null;
  onThreadClick?: (idx: number) => void;
}

export function Sidebar(props: SidebarProps) {
  const {
    region,
    onRegionChange,
    view,
    onViewChange,
    onRefresh,
    refreshing,
    themes,
    onThreadClick,
  } = props;

  const lang = region === "intl" ? "en" : "zh";
  const L = SIDEBAR_LABELS[lang];

  return (
    <aside className="lg:sticky lg:top-[var(--header-h)] lg:h-[calc(100vh-var(--header-h))] overflow-y-auto border-r border-border bg-bg/70 backdrop-blur-xl">
      <div className="px-5 py-6 flex flex-col gap-6">
        {/* Region */}
        <Section label={L.region}>
          <ToggleGroup
            type="single"
            value={region}
            onValueChange={(v) => v && onRegionChange(v as Region)}
            aria-label="区域"
            className="w-full"
          >
            <ToggleGroupItem value="cn" className="flex-1 justify-center">
              🇨🇳 国内
            </ToggleGroupItem>
            <ToggleGroupItem value="intl" className="flex-1 justify-center">
              🌍 国际
            </ToggleGroupItem>
          </ToggleGroup>
        </Section>

        {/* Today's threads navigation */}
        <div className="hidden lg:block">
          <Section
            label={L.threads}
            right={
              themes?.status === "ok" || themes?.status === "cached" ? (
                <Badge>{themes.threads.length}</Badge>
              ) : themes?.status === "disabled" ? (
                <Badge>off</Badge>
              ) : themes?.status === "error" ? (
                <Badge variant="danger">err</Badge>
              ) : null
            }
          >
            {themes && (themes.status === "ok" || themes.status === "cached") && themes.threads.length > 0 ? (
              <ul className="m-0 p-0 list-none space-y-px">
                {themes.threads.map((t, i) => (
                  <li key={i}>
                    <button
                      type="button"
                      onClick={() => onThreadClick?.(i)}
                      className={cn(
                        "group w-full flex items-center justify-between gap-2 pl-2 pr-2 py-1.5 rounded-xs",
                        "text-left text-sm text-fg hover:bg-panel-2 transition-colors duration-150 ease-smooth",
                        "border-l-2 border-transparent hover:border-warning/70"
                      )}
                    >
                      <span className="flex items-center gap-2 flex-1 min-w-0">
                        <span
                          className="w-1.5 h-1.5 rounded-full shrink-0"
                          style={{ backgroundColor: threadDotColor(i) }}
                          aria-hidden
                        />
                        <span className="truncate">{t.name}</span>
                      </span>
                      <span className="text-[10px] text-muted-2 tabular-nums shrink-0 group-hover:text-fg transition-colors">
                        {t.item_ids.length}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-xs text-muted-2 px-2 py-1">
                {themes?.status === "disabled"
                  ? "DeepSeek 未启用"
                  : themes?.status === "error"
                  ? "聚类失败"
                  : "—"}
              </div>
            )}
          </Section>
        </div>

        {/* View toggle */}
        <Section label={L.view}>
          <ToggleGroup
            type="single"
            value={view}
            onValueChange={(v) => v && onViewChange(v as View)}
            aria-label="视图"
            className="w-full grid grid-cols-2"
          >
            <ToggleGroupItem value="brief" className="justify-center text-xs">
              简报
            </ToggleGroupItem>
            <ToggleGroupItem value="curated" className="justify-center text-xs">
              高信号
            </ToggleGroupItem>
            <ToggleGroupItem value="prompts" className="justify-center text-xs">
              Prompt
            </ToggleGroupItem>
            <ToggleGroupItem value="grid" className="justify-center text-xs">
              杂志
            </ToggleGroupItem>
            <ToggleGroupItem value="timeline" className="justify-center text-xs">
              时间流
            </ToggleGroupItem>
          </ToggleGroup>
        </Section>

        {/* Refresh */}
        <div className="pt-1">
          <Button
            onClick={onRefresh}
            disabled={refreshing}
            variant="primary"
            className="w-full"
          >
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} aria-hidden />
            {refreshing ? L.refreshing : L.refreshBtn}
          </Button>
        </div>

        {/* Shortcuts hint */}
        <div className="hidden lg:block mt-auto pt-4 border-t border-border/60 text-xs text-muted-2 leading-relaxed">
          <div className="mb-1.5 font-semibold tracking-wide text-muted">{L.shortcuts}</div>
          <div className="grid grid-cols-2 gap-y-1">
            <Kbd>R</Kbd><span>{L.refreshShort}</span>
            <Kbd>B</Kbd><span>{lang === "en" ? "Brief" : "简报"}</span>
            <Kbd>C</Kbd><span>{lang === "en" ? "Curated" : "高信号"}</span>
            <Kbd>P</Kbd><span>Prompt</span>
            <Kbd>G</Kbd><span>{lang === "en" ? "Magazine" : "杂志"}</span>
            <Kbd>T</Kbd><span>{lang === "en" ? "Timeline" : "时间流"}</span>
            <Kbd>1</Kbd><span>{lang === "en" ? "China" : "国内"}</span>
            <Kbd>2</Kbd><span>{lang === "en" ? "World" : "国际"}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Section({
  label,
  right,
  children,
}: {
  label: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <h3 className="text-xs font-semibold tracking-wider text-muted uppercase m-0">
          {label}
        </h3>
        {right}
      </div>
      {children}
    </div>
  );
}

/**
 * Centralized sidebar labels — keep here so a region switch flips the entire
 * sidebar copy consistently. Mixing "REGION" (English caps) with "今日话题"
 * (Chinese) used to be jarring.
 */
const SIDEBAR_LABELS = {
  zh: {
    region: "区域",
    threads: "今日话题",
    view: "视图",
    shortcuts: "快捷键",
    refreshBtn: "刷新数据",
    refreshShort: "刷新",
    refreshing: "抓取中…",
  },
  en: {
    region: "REGION",
    threads: "TODAY'S THREADS",
    view: "VIEW",
    shortcuts: "SHORTCUTS",
    refreshBtn: "Refresh",
    refreshShort: "Refresh",
    refreshing: "Loading…",
  },
} as const;

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[20px] h-[20px] px-1 border border-border-strong rounded-xs font-mono text-[10px] text-fg bg-panel">
      {children}
    </kbd>
  );
}

/**
 * Deterministic per-thread accent color for the sidebar dots — gives the
 * eye a way to distinguish 6+ threads at a glance without relying on names.
 * Picks evenly-spaced hues with consistent saturation/lightness so all dots
 * read as the same "weight."
 */
function threadDotColor(idx: number): string {
  // 60° spacing → 6 distinct hues that cycle if more threads
  // Offset 22° puts the first thread near warm orange (matches the brand)
  const hue = (idx * 60 + 22) % 360;
  return `hsl(${hue} 65% 60%)`;
}
