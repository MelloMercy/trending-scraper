import { Clipboard, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { emojiFor } from "@/data/platforms";
import { cn } from "@/lib/utils";
import type { BriefItem, BriefResponse, PlatformInfo } from "@/lib/types";

interface BriefViewProps {
  brief: BriefResponse | null;
  loading: boolean;
  error: string | null;
  platforms: PlatformInfo[];
  onReload: (force?: boolean) => void;
}

const SECTIONS: Array<{
  key: keyof Pick<BriefResponse, "consensus" | "cn_only" | "intl_only" | "persistent" | "emerging">;
  label: string;
  hint: string;
  accent: "primary" | "warning" | "success" | "hot" | "danger";
  emoji: string;
}> = [
  {
    key: "consensus",
    label: "跨地区共识",
    hint: "中外都在讨论的话题",
    accent: "warning",
    emoji: "🌐",
  },
  {
    key: "persistent",
    label: "持续在榜",
    hint: "已连续多日上榜",
    accent: "hot",
    emoji: "📈",
  },
  {
    key: "emerging",
    label: "今日新声",
    hint: "首次出现但多源覆盖",
    accent: "primary",
    emoji: "💡",
  },
  {
    key: "cn_only",
    label: "中文圈独有",
    hint: "国内热议、海外几乎缺席",
    accent: "danger",
    emoji: "🇨🇳",
  },
  {
    key: "intl_only",
    label: "国际独有",
    hint: "海外热议、国内几乎缺席",
    accent: "success",
    emoji: "🌍",
  },
];

export function BriefView({ brief, loading, error, platforms, onReload }: BriefViewProps) {
  if (loading && !brief) {
    return <BriefSkeleton />;
  }
  if (error || !brief) {
    return (
      <EmptyState
        title="加载简报失败"
        hint={error ?? "未知错误"}
      />
    );
  }
  if (brief.status === "disabled") {
    return (
      <EmptyState
        title="未启用 Daily Brief"
        hint="需要配置 DeepSeek API key。POST /api/config 写入 deepseek_api_key 后再试。"
      />
    );
  }
  if (brief.status === "error") {
    return (
      <EmptyState
        title="简报生成失败"
        hint={brief.error ?? "DeepSeek 调用出错，稍后再试或检查日志"}
      />
    );
  }

  const isEmpty = SECTIONS.every((s) => !brief[s.key] || (brief[s.key] || []).length === 0);

  return (
    <div className="max-w-[920px] mx-auto">
      <BriefHeader brief={brief} onReload={onReload} />

      {brief.narrative && (
        <article className="mb-8 p-6 rounded-lg bg-gradient-to-br from-panel-2 to-panel border border-border shadow-card relative overflow-hidden">
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-primary to-accent2" />
          <div className="flex items-center gap-2 text-xs font-bold tracking-[0.14em] uppercase text-primary-strong mb-3">
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            今日综述
          </div>
          <p className="font-display text-lg leading-relaxed text-fg m-0">
            {brief.narrative}
          </p>
        </article>
      )}

      {isEmpty ? (
        <EmptyState
          title="今日各分类暂无内容"
          hint="可能数据不足或 DeepSeek 返回了空结构。点上方刷新重试，或等明天再看（持续度需要多天数据）"
        />
      ) : (
        <div className="space-y-8">
          {SECTIONS.map((sec) => {
            const items = brief[sec.key] || [];
            if (items.length === 0) return null;
            return (
              <BriefSection
                key={sec.key}
                label={sec.label}
                hint={sec.hint}
                emoji={sec.emoji}
                accent={sec.accent}
                items={items}
                platforms={platforms}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

function BriefHeader({
  brief,
  onReload,
}: {
  brief: BriefResponse;
  onReload: (force?: boolean) => void;
}) {
  const cached = brief.status === "cached";
  const date = brief.snapshot_date;
  // Dev info — hidden in tooltip so the UI stays clean but it stays inspectable
  const devMeta = [brief.model, cached ? "cached" : null].filter(Boolean).join(" · ");

  function copyMarkdown() {
    const md = briefToMarkdown(brief);
    navigator.clipboard
      .writeText(md)
      .then(() => toast.success("简报 Markdown 已复制到剪贴板"))
      .catch((e) => toast.error("复制失败: " + e.message));
  }

  return (
    <header className="mb-6 flex items-baseline justify-between gap-3 flex-wrap">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight m-0 flex items-baseline gap-3">
          每日简报
          <span className="text-sm text-muted-2 font-normal tabular-nums">
            {date}
          </span>
        </h1>
        <p
          className="text-xs text-muted mt-1 cursor-help"
          title={devMeta ? `生成方式：${devMeta}` : undefined}
        >
          AI 跨地区话题合成 · 含多日持续度分析
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={copyMarkdown} title="复制为 Markdown">
          <Clipboard className="h-3.5 w-3.5" aria-hidden />
          复制 Markdown
        </Button>
        <Button
          variant="default"
          size="sm"
          onClick={() => onReload(true)}
          title="重新合成（消耗一次 DeepSeek 调用）"
        >
          重新合成
        </Button>
      </div>
    </header>
  );
}

function BriefSection({
  label,
  hint,
  emoji,
  accent,
  items,
  platforms,
}: {
  label: string;
  hint: string;
  emoji: string;
  accent: "primary" | "warning" | "success" | "hot" | "danger";
  items: BriefItem[];
  platforms: PlatformInfo[];
}) {
  const accentColor = {
    primary: "border-l-primary",
    warning: "border-l-warning",
    success: "border-l-success",
    hot: "border-l-hot",
    danger: "border-l-danger",
  }[accent];

  return (
    <section>
      <div className="flex items-baseline gap-3 mb-3">
        <h2 className="font-display text-lg font-semibold tracking-tight m-0 flex items-center gap-2">
          <span>{emoji}</span>
          {label}
        </h2>
        <Badge>{items.length}</Badge>
        <span className="text-xs text-muted-2 flex-1 min-w-0 truncate">{hint}</span>
      </div>
      <ul className="space-y-3 list-none m-0 p-0">
        {items.map((item, i) => (
          <BriefItemCard
            key={i}
            item={item}
            accentBorder={accentColor}
            platforms={platforms}
          />
        ))}
      </ul>
    </section>
  );
}

function BriefItemCard({
  item,
  accentBorder,
  platforms,
}: {
  item: BriefItem;
  accentBorder: string;
  platforms: PlatformInfo[];
}) {
  const platName = (id: string) =>
    platforms.find((p) => p.id === id)?.name ?? id;

  return (
    <li
      className={cn(
        "rounded-md bg-panel border border-border shadow-card p-4 pl-5 border-l-4",
        accentBorder,
        "hover:border-border-strong transition-colors duration-150"
      )}
    >
      <div className="flex items-baseline gap-2 mb-1.5">
        <h3 className="font-display text-md font-semibold tracking-tight m-0 flex-1 min-w-0">
          {item.title}
        </h3>
        {item.days_running && item.days_running > 1 && (
          <Badge variant="hot">▲ 第 {item.days_running} 天</Badge>
        )}
      </div>
      <p className="text-sm text-muted leading-snug m-0">{item.summary}</p>

      {(item.cn_sources.length > 0 || item.intl_sources.length > 0) && (
        <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-border">
          {item.cn_sources.map((s, i) => (
            <SourceLink key={`cn-${i}`} source={s} platName={platName} />
          ))}
          {item.intl_sources.map((s, i) => (
            <SourceLink key={`intl-${i}`} source={s} platName={platName} />
          ))}
        </div>
      )}
    </li>
  );
}

function SourceLink({
  source,
  platName,
}: {
  source: BriefItem["cn_sources"][number];
  platName: (id: string) => string;
}) {
  return (
    <a
      href={source.url ?? "#"}
      target="_blank"
      rel="noopener"
      title={source.title}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-panel-3 text-xs text-fg hover:text-accent2 hover:bg-bg-2 transition-colors duration-150 max-w-[300px]"
    >
      <span className="shrink-0">{emojiFor(source.platform)}</span>
      <span className="text-muted-2 shrink-0">{platName(source.platform)}</span>
      <span className="truncate">{source.title}</span>
      <span className="text-[10px] text-muted-2 tabular-nums shrink-0">#{source.rank}</span>
    </a>
  );
}

function BriefSkeleton() {
  return (
    <div className="max-w-[920px] mx-auto">
      <div className="mb-6">
        <Skeleton className="h-7 w-40 mb-2" />
        <Skeleton className="h-3 w-72" />
      </div>
      <Skeleton className="h-32 mb-8 rounded-lg" />
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="mb-8">
          <Skeleton className="h-5 w-44 mb-3" />
          {Array.from({ length: 2 }).map((_, j) => (
            <Skeleton key={j} className="h-24 mb-3 rounded-md" />
          ))}
        </div>
      ))}
    </div>
  );
}

// ---------- Markdown export ----------

function briefToMarkdown(brief: BriefResponse): string {
  const lines: string[] = [];
  lines.push(`# 每日简报 · ${brief.snapshot_date}`);
  lines.push("");
  if (brief.narrative) {
    lines.push(`> ${brief.narrative}`);
    lines.push("");
  }

  const sections: Array<[string, BriefItem[] | undefined]> = [
    ["🌐 跨地区共识", brief.consensus],
    ["📈 持续在榜", brief.persistent],
    ["💡 今日新声", brief.emerging],
    ["🇨🇳 中文圈独有", brief.cn_only],
    ["🌍 国际独有", brief.intl_only],
  ];

  for (const [heading, items] of sections) {
    if (!items || items.length === 0) continue;
    lines.push(`## ${heading}`);
    lines.push("");
    for (const it of items) {
      let title = it.title;
      if (it.days_running && it.days_running > 1) {
        title += ` · 第 ${it.days_running} 天`;
      }
      lines.push(`### ${title}`);
      if (it.summary) lines.push(it.summary);
      const srcs = [...it.cn_sources, ...it.intl_sources];
      if (srcs.length) {
        lines.push("");
        lines.push("**来源：**");
        for (const s of srcs) {
          const url = s.url ?? "#";
          lines.push(`- ${s.platform} #${s.rank}: [${s.title}](${url})`);
        }
      }
      lines.push("");
    }
  }

  lines.push("");
  lines.push(`---`);
  lines.push(`*由 trending-scraper + DeepSeek (${brief.model ?? "AI"}) 合成*`);
  return lines.join("\n");
}
