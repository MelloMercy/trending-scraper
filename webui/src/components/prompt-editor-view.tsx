import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  PlayCircle,
  RefreshCw,
  Save,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { PromptFile, Region } from "@/lib/types";

type PromptId = PromptFile["id"];
type RunTarget = Region | "brief";

export function PromptEditorView() {
  const [prompts, setPrompts] = useState<PromptFile[]>([]);
  const [activeId, setActiveId] = useState<PromptId>("cluster-cn");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<RunTarget | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const loadPrompts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listPrompts();
      setPrompts(data.prompts);
      const selected = data.prompts.find((p) => p.id === activeId) ?? data.prompts[0];
      if (selected) {
        setActiveId(selected.id);
        setDraft(selected.content);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [activeId]);

  useEffect(() => {
    void loadPrompts();
    // Initial fetch only; manual refresh handles later file changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activePrompt = useMemo(
    () => prompts.find((prompt) => prompt.id === activeId) ?? null,
    [activeId, prompts]
  );
  const dirty = Boolean(activePrompt && draft !== activePrompt.content);
  const localMissing = useMemo(
    () => activePrompt?.placeholders.filter((name) => !draft.includes(`{${name}}`)) ?? [],
    [activePrompt, draft]
  );
  const canSave = Boolean(activePrompt && dirty && localMissing.length === 0 && !saving);

  const selectPrompt = useCallback((prompt: PromptFile) => {
    setActiveId(prompt.id);
    setDraft(prompt.content);
    setSaveError(null);
  }, []);

  const savePrompt = useCallback(async () => {
    if (!activePrompt || !canSave) return;
    setSaving(true);
    setSaveError(null);
    try {
      const result = await api.updatePrompt(activePrompt.id, draft);
      setPrompts((current) =>
        current.map((prompt) => prompt.id === result.prompt.id ? result.prompt : prompt)
      );
      setDraft(result.prompt.content);
      toast.success("Prompt 已保存");
    } catch (e) {
      const message = extractPromptError(e);
      setSaveError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }, [activePrompt, canSave, draft]);

  const runRefresh = useCallback(async (target: RunTarget) => {
    setRunning(target);
    try {
      if (target === "brief") {
        const result = await api.briefToday(true);
        result.status === "error"
          ? toast.error(result.error ?? "Daily Brief 生成失败")
          : toast.success("Daily Brief 已刷新");
      } else {
        const result = await api.aggregateToday(target, true);
        result.themes.status === "error"
          ? toast.error(result.themes.error ?? "聚类刷新失败")
          : toast.success(target === "cn" ? "中文聚类已刷新" : "国际聚类已刷新");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(null);
    }
  }, []);

  if (loading && prompts.length === 0) return <PromptEditorSkeleton />;
  if (error || prompts.length === 0) {
    return (
      <EmptyState
        title="Prompt 加载失败"
        hint={error ?? "prompts/*.md 不可用"}
      />
    );
  }

  return (
    <div className="max-w-[1180px] mx-auto">
      <header className="signal-surface rounded-md border border-border-strong shadow-elevated overflow-hidden mb-6">
        <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-primary text-xs font-bold uppercase mb-3">
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
              Prompt workbench
            </div>
            <h1 className="font-display text-3xl font-bold m-0 leading-tight">
              Prompt 编辑器
            </h1>
            <p className="text-sm text-muted leading-relaxed mt-3 mb-0 max-w-[70ch]">
              prompts/*.md · {prompts.length} files · {activePrompt ? formatRelativeTime(activePrompt.updated_at, "zh") : "刚刚"}
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {prompts.map((prompt) => (
                <PromptTab
                  key={prompt.id}
                  prompt={prompt}
                  active={prompt.id === activeId}
                  dirty={prompt.id === activeId && dirty}
                  onClick={() => selectPrompt(prompt)}
                />
              ))}
            </div>
          </div>

          <div className="rounded-md border border-border bg-bg/30 p-4">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div className="text-sm font-semibold">Run targets</div>
              <Button variant="outline" size="sm" onClick={() => void loadPrompts()} disabled={loading}>
                <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} aria-hidden />
                重新读取
              </Button>
            </div>
            <div className="grid gap-2">
              <RunButton
                label="重跑 CN 聚类"
                active={running === "cn"}
                onClick={() => void runRefresh("cn")}
              />
              <RunButton
                label="重跑 INTL 聚类"
                active={running === "intl"}
                onClick={() => void runRefresh("intl")}
              />
              <RunButton
                label="重跑 Daily Brief"
                active={running === "brief"}
                onClick={() => void runRefresh("brief")}
              />
            </div>
          </div>
        </div>
      </header>

      {activePrompt && (
        <section className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)] items-start">
          <aside className="glass-panel rounded-md p-4">
            <div className="flex items-start gap-3">
              <div className="rounded-sm border border-border bg-bg/40 p-2 text-primary">
                <FileText className="h-4 w-4" aria-hidden />
              </div>
              <div className="min-w-0">
                <h2 className="font-display text-xl font-semibold m-0">{activePrompt.title}</h2>
                <div className="mt-1 text-xs text-muted-2">{activePrompt.filename}</div>
              </div>
            </div>

            <p className="mt-4 mb-0 text-sm leading-relaxed text-muted">
              {activePrompt.description}
            </p>

            <div className="mt-5">
              <div className="mb-2 text-xs font-semibold uppercase text-muted">Placeholders</div>
              <div className="flex flex-wrap gap-2">
                {activePrompt.placeholders.map((name) => (
                  <Badge
                    key={name}
                    variant={localMissing.includes(name) ? "danger" : "primary"}
                  >
                    {`{${name}}`}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-2">
              <Meta label="Lines" value={draft.split("\n").length} />
              <Meta label="Chars" value={draft.length} />
            </div>
          </aside>

          <article className="glass-panel rounded-md overflow-hidden">
            <div className="flex flex-col gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2 min-w-0">
                {localMissing.length > 0 ? (
                  <AlertTriangle className="h-4 w-4 text-danger shrink-0" aria-hidden />
                ) : dirty ? (
                  <AlertTriangle className="h-4 w-4 text-warning shrink-0" aria-hidden />
                ) : (
                  <CheckCircle2 className="h-4 w-4 text-success shrink-0" aria-hidden />
                )}
                <span className="text-sm font-semibold truncate">
                  {localMissing.length > 0
                    ? "占位符缺失"
                    : dirty
                    ? "有未保存修改"
                    : "已同步"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => activePrompt && setDraft(activePrompt.content)}
                  disabled={!dirty || saving}
                >
                  放弃修改
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => void savePrompt()}
                  disabled={!canSave}
                >
                  <Save className="h-3.5 w-3.5" aria-hidden />
                  {saving ? "保存中" : "保存"}
                </Button>
              </div>
            </div>

            <textarea
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value);
                setSaveError(null);
              }}
              spellCheck={false}
              className={cn(
                "block w-full min-h-[560px] resize-y bg-bg/40 px-4 py-4",
                "font-mono text-[13px] leading-relaxed text-fg tabular-nums",
                "border-0 outline-none focus-visible:shadow-none",
                "placeholder:text-muted-2"
              )}
              aria-label={`${activePrompt.title} prompt content`}
            />

            {(localMissing.length > 0 || saveError) && (
              <div className="border-t border-border px-4 py-3 text-xs text-danger bg-danger/[0.08]">
                {localMissing.length > 0
                  ? `缺少：${localMissing.map((name) => `{${name}}`).join("、")}`
                  : saveError}
              </div>
            )}
          </article>
        </section>
      )}
    </div>
  );
}

function PromptTab({
  prompt,
  active,
  dirty,
  onClick,
}: {
  prompt: PromptFile;
  active: boolean;
  dirty: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs transition-colors",
        active
          ? "border-primary bg-primary/[0.14] text-primary-strong"
          : "border-border bg-bg/40 text-muted hover:border-border-strong hover:text-fg"
      )}
    >
      <FileText className="h-3.5 w-3.5" aria-hidden />
      <span>{prompt.title}</span>
      {dirty && <span className="size-1.5 rounded-full bg-warning" aria-hidden />}
    </button>
  );
}

function RunButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      variant="outline"
      className="justify-start"
      onClick={onClick}
      disabled={active}
    >
      {active ? (
        <RefreshCw className="h-3.5 w-3.5 animate-spin" aria-hidden />
      ) : (
        <PlayCircle className="h-3.5 w-3.5" aria-hidden />
      )}
      {active ? "运行中" : label}
    </Button>
  );
}

function Meta({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-sm border border-border bg-bg/30 p-3">
      <div className="text-xs text-muted-2">{label}</div>
      <div className="font-display text-2xl font-semibold text-primary tabular-nums">{value}</div>
    </div>
  );
}

function PromptEditorSkeleton() {
  return (
    <div className="max-w-[1180px] mx-auto">
      <div className="signal-surface rounded-md border border-border-strong p-6 mb-6">
        <Skeleton className="h-4 w-40 mb-4" />
        <Skeleton className="h-9 w-64 mb-5" />
        <div className="flex gap-2">
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-7 w-36" />
          <Skeleton className="h-7 w-28" />
        </div>
      </div>
      <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <Skeleton className="h-64 rounded-md" />
        <Skeleton className="h-[620px] rounded-md" />
      </div>
    </div>
  );
}

function extractPromptError(error: unknown): string {
  if (!(error instanceof Error)) return String(error);
  const match = error.message.match(/\{.*\}$/s);
  if (!match) return error.message;
  try {
    const parsed = JSON.parse(match[0]) as {
      detail?: { message?: string; validation?: { missing?: string[]; format_error?: string | null } };
    };
    const detail = parsed.detail;
    if (!detail) return error.message;
    const missing = detail.validation?.missing;
    const formatError = detail.validation?.format_error;
    if (missing && missing.length > 0) {
      return `缺少占位符：${missing.map((name) => `{${name}}`).join("、")}`;
    }
    return formatError ?? detail.message ?? error.message;
  } catch {
    return error.message;
  }
}
