import * as React from "react";
import { cn } from "@/lib/utils";

interface SourceChipProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  emoji: string;
  label: string;
  rank?: number;
}

/**
 * Pill-shaped tag for displaying a platform mention. Visually distinct from
 * Button — soft background, no border, hover lifts the background.
 */
export const SourceChip = React.forwardRef<HTMLAnchorElement, SourceChipProps>(
  ({ emoji, label, rank, className, children, ...props }, ref) => (
    <a
      ref={ref}
      className={cn(
        "inline-flex items-center gap-1 px-3 py-0.5 rounded-full bg-panel-3 border border-transparent",
        "text-xs font-medium text-fg transition-colors duration-150 ease-smooth",
        "hover:bg-bg-2 hover:border-border-strong hover:text-accent2",
        className
      )}
      {...props}
    >
      <span>{emoji}</span>
      <span>{label}</span>
      {typeof rank === "number" && (
        <span className="text-[10px] text-muted-2 tabular-nums font-normal -ml-0.5">
          #{rank}
        </span>
      )}
      {children}
    </a>
  )
);
SourceChip.displayName = "SourceChip";
