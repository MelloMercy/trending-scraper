import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  hint?: string;
  className?: string;
}

export function EmptyState({ title, hint, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center px-4 py-12 text-center",
        className
      )}
    >
      <svg
        className="text-muted-2 mb-3"
        width="48"
        height="48"
        viewBox="0 0 48 48"
        fill="none"
        aria-hidden
      >
        <rect x="8" y="10" width="32" height="28" rx="3" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M14 18h20M14 24h20M14 30h12"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
      <div className="text-sm text-muted">{title}</div>
      {hint && <div className="text-xs text-muted-2 mt-2">{hint}</div>}
    </div>
  );
}
